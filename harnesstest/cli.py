"""HarnessTest CLI."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from harnesstest.adapters import list_adapters
from harnesstest.harnesses._common import DEFAULT_OLLAMA_MODEL, ollama_ready, resolve_model
from harnesstest.instrumentation import EgressSink, filesystem_probe, plant_workspace, port_open
from harnesstest.models import AttackId, AttackResult, Profile, Scorecard
from harnesstest.runner import (
    DEFAULT_REPORTS,
    DEFAULT_WORKSPACE,
    merge_scorecard,
    rescore_results,
    run_attack,
    write_matrix_markdown,
)

BRIEF_ATTACKS = [AttackId.KILL_CHAIN, AttackId.NETWORK_EGRESS]
DEEP_ATTACKS = [
    AttackId.KILL_CHAIN,
    AttackId.INDIRECT_PROMPT_INJECTION,
    AttackId.SECRET_EXFIL,
    AttackId.NETWORK_EGRESS,
    AttackId.CREDENTIAL_BOUNDARY,
    AttackId.PLUGIN_SUPPLY_CHAIN,
]
TARGET_HARNESSES = ["openclaw", "nemoclaw", "hermes", "deepseek"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="harnesstest",
        description="Security benchmark for AI agent harnesses",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sink = sub.add_parser("sink", help="Run local egress sink")
    p_sink.add_argument("--host", default="127.0.0.1")
    p_sink.add_argument("--port", type=int, default=8765)

    p_probe = sub.add_parser("probe", help="Plant workspace + verify fixtures")
    p_probe.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    p_probe.add_argument("--sink-url", default="http://127.0.0.1:8765/exfil")
    p_probe.add_argument("--check-sink", action="store_true")

    sub.add_parser("list", help="List registered harness adapters")

    p_model = sub.add_parser("model", help="Check local Ollama model backend")
    p_model.add_argument("--name", default=None)

    p_run = sub.add_parser("run", help="Run one attack against one harness")
    p_run.add_argument(
        "--harness",
        required=True,
        choices=["local", "openclaw", "nemoclaw", "hermes", "deepseek"],
    )
    p_run.add_argument("--profile", default="default", choices=[p.value for p in Profile])
    p_run.add_argument("--attack", default="kill_chain", choices=[a.value for a in AttackId])
    p_run.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    p_run.add_argument("--reports", type=Path, default=DEFAULT_REPORTS)
    p_run.add_argument("--sink-port", type=int, default=8765)
    p_run.add_argument("--model", default=None, help=f"default: {DEFAULT_OLLAMA_MODEL}")

    p_camp = sub.add_parser("campaign", help="Run default+hardened attacks")
    p_camp.add_argument(
        "--harness",
        action="append",
        dest="harnesses",
        choices=["local", "openclaw", "nemoclaw", "hermes", "deepseek"],
        help="Repeatable; default: openclaw nemoclaw hermes deepseek",
    )
    p_camp.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    p_camp.add_argument("--reports", type=Path, default=DEFAULT_REPORTS)
    p_camp.add_argument("--sink-port", type=int, default=8765)
    p_camp.add_argument("--model", default=None)
    p_camp.add_argument("--brief-only", action="store_true")

    p_rescore = sub.add_parser(
        "rescore",
        help="Rebuild scorecard from existing results.json using observed-only denials",
    )
    p_rescore.add_argument("--reports", type=Path, default=DEFAULT_REPORTS)
    p_rescore.add_argument("--results", type=Path, default=None)

    args = parser.parse_args(argv)

    if args.cmd == "sink":
        return _cmd_sink(args.host, args.port)
    if args.cmd == "probe":
        return _cmd_probe(args.workspace, args.sink_url, args.check_sink)
    if args.cmd == "list":
        for name in list_adapters():
            print(name)
        return 0
    if args.cmd == "model":
        ok, msg = ollama_ready(resolve_model(args.name))
        print(msg)
        return 0 if ok else 1
    if args.cmd == "run":
        result = run_attack(
            harness=args.harness,
            attack=AttackId(args.attack),
            profile=Profile(args.profile),
            workspace=args.workspace,
            reports_dir=args.reports,
            sink_port=args.sink_port,
            model=args.model,
        )
        print(result.model_dump_json(indent=2))
        # Unavailable harnesses exit 0 so campaigns can aggregate blockers.
        return 0 if (result.error is None or not result.live) else 1
    if args.cmd == "campaign":
        return _cmd_campaign(args)
    if args.cmd == "rescore":
        return _cmd_rescore(args)
    return 2


def _cmd_sink(host: str, port: int) -> int:
    sink = EgressSink(host=host, port=port)
    sink.start()
    print(f"egress sink on {sink.base_url} (exfil: {sink.exfil_url})", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nstopping", flush=True)
    finally:
        sink.stop()
    return 0


def _cmd_probe(workspace: Path, sink_url: str, check_sink: bool) -> int:
    paths = plant_workspace(workspace, egress_url=sink_url)
    events = filesystem_probe(workspace)
    report: dict = {
        "workspace": str(workspace.resolve()),
        "planted": {k: str(v) for k, v in paths.items()},
        "fixture_events": [e.model_dump() for e in events],
    }
    if check_sink:
        u = urlparse(sink_url)
        report["sink_reachable"] = port_open(u.hostname or "127.0.0.1", u.port or 80)
    print(json.dumps(report, indent=2))
    missing = [e for e in events if e.kind == "fixture_missing"]
    return 1 if missing else 0


def _cmd_campaign(args: argparse.Namespace) -> int:
    harnesses = args.harnesses or list(TARGET_HARNESSES)
    results = []
    for harness in harnesses:
        if harness == "openclaw" or args.brief_only:
            attacks = BRIEF_ATTACKS
        elif harness == "local":
            attacks = BRIEF_ATTACKS + [AttackId.SECRET_EXFIL, AttackId.INDIRECT_PROMPT_INJECTION]
        else:
            attacks = DEEP_ATTACKS
        for profile in (Profile.DEFAULT, Profile.HARDENED):
            for attack in attacks:
                print(f"==> {harness} / {profile.value} / {attack.value}", flush=True)
                results.append(
                    run_attack(
                        harness=harness,
                        attack=attack,
                        profile=profile,
                        workspace=args.workspace,
                        reports_dir=args.reports,
                        sink_port=args.sink_port,
                        model=args.model,
                    )
                )
    card = merge_scorecard(
        results,
        args.reports / "results.json",
        model_name=resolve_model(args.model),
        model_backend="mixed",
    )
    write_matrix_markdown(card, args.reports / "scorecard.md")
    print(f"wrote {args.reports / 'results.json'}")
    print(f"wrote {args.reports / 'scorecard.md'}")
    return 0


def _cmd_rescore(args: argparse.Namespace) -> int:
    results_path = args.results or (args.reports / "results.json")
    if not results_path.is_file():
        print(f"missing results file: {results_path}", file=sys.stderr)
        return 1
    raw = json.loads(results_path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "results" in raw:
        card_in = Scorecard.model_validate(raw)
        results = card_in.results
        model_name = card_in.model_name
        model_backend = card_in.model_backend
    elif isinstance(raw, list):
        results = [AttackResult.model_validate(r) for r in raw]
        model_name = resolve_model(None)
        model_backend = "mixed"
    else:
        print("unrecognized results.json shape", file=sys.stderr)
        return 1

    card = rescore_results(results, model_name=model_name, model_backend=model_backend or "mixed")
    merge_scorecard(
        card.results,
        args.reports / "results.json",
        model_name=card.model_name,
        model_backend=card.model_backend,
    )
    write_matrix_markdown(card, args.reports / "scorecard.md")
    # Also refresh per-attack JSON sidecars when present.
    for r in card.results:
        side = args.reports / f"{r.harness}_{r.profile.value}_{r.attack.value}.json"
        side.write_text(r.model_dump_json(indent=2), encoding="utf-8")
    print(f"rescored {len(card.results)} results → {args.reports / 'scorecard.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
