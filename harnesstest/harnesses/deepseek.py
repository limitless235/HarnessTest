"""DeepSeek Harness adapter — deep (plugin TCB + append-only trajectories)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

from harnesstest.adapters import HarnessAdapter, RunRequest, RunResponse, register
from harnesstest.harnesses._common import (
    OLLAMA_HOST,
    cloud_provider_key,
    combine_output,
    hardened,
    observe_approval_required,
    ollama_ready,
    parse_policy_denials,
    profile_dir,
    resolve_model,
    run_cmd,
    trajectory_path,
    unavailable,
    which,
    write_json,
    write_text,
)
from harnesstest.models import AttackId


@register
class DeepSeekAdapter(HarnessAdapter):
    name = "deepseek"

    def available(self) -> tuple[bool, str]:
        dsh = which("dsh")
        checkout = os.environ.get("DEEPSEEK_HARNESS_ROOT")
        if checkout and not Path(checkout).is_dir():
            checkout = None
        keys_ok, keys_msg = cloud_provider_key()
        model = resolve_model()
        oll_ok, oll_msg = ollama_ready(model)

        if dsh:
            if keys_ok or oll_ok:
                backend = keys_msg if keys_ok else oll_msg
                return True, f"dsh={dsh}; {backend}"
            return False, f"dsh={dsh}; {keys_msg}; {oll_msg}"
        if checkout:
            if keys_ok or oll_ok:
                backend = keys_msg if keys_ok else oll_msg
                return True, f"deepseek-harness checkout at {checkout}; {backend}"
            return False, f"deepseek-harness checkout at {checkout}; {keys_msg}; {oll_msg}"
        return (
            False,
            "dsh not found. Install: ./scripts/install-deepseek.sh "
            "(clone deepseek-harness, pnpm install && pnpm run build); "
            "set DEEPSEEK_HARNESS_ROOT or put dsh on PATH",
        )

    def prepare(self, req: RunRequest) -> None:
        cfg_dir = profile_dir(req, self.name)
        plugin_dir = cfg_dir / "plugins" / "ht-weather-helper"
        plugin_dir.mkdir(parents=True, exist_ok=True)

        write_text(
            plugin_dir / "index.ts",
            """import type { Context } from '@deepseek-ai/cordis'

export const name = 'ht-weather-helper'

export function apply(ctx: Context) {
  // SYNTHETIC HarnessTest plugin — high TCB surface.
  ctx.on('agent/step', () => {
    // no-op stub; live runs use real dsh plugin loading
  })
}
""",
        )
        write_json(
            plugin_dir / "package.json",
            {"name": "ht-weather-helper", "version": "0.0.0", "private": True},
        )

        plugins = [{"name": "core"}]
        if req.attack == AttackId.PLUGIN_SUPPLY_CHAIN or not hardened(req):
            plugins.append(
                {
                    "name": "ht-weather-helper",
                    "path": str(plugin_dir.resolve()),
                    "trust": "high",
                }
            )
        if hardened(req):
            plugins = [p for p in plugins if p.get("name") != "ht-weather-helper"]
            plugins.append({"name": "trajectory", "append_only": True})

        cordis = {
            "plugins": plugins,
            "sandbox": {"enabled": hardened(req)},
            "trajectory": {"append_only": True, "path": str(cfg_dir / "session.jsonl")},
            "network": {"allow": [] if hardened(req) else [req.egress_url]},
        }
        write_text(cfg_dir / "cordis.yml", yaml.safe_dump(cordis, sort_keys=False))
        write_json(cfg_dir / "deepseek.profile.json", cordis)
        write_text(cfg_dir / "task.md", req.task_prompt + "\n")

        model = resolve_model(req.model or os.environ.get("DEEPSEEK_MODEL"))
        use_ollama = not cloud_provider_key()[0] and ollama_ready(model)[0]
        if use_ollama:
            base = OLLAMA_HOST.rstrip("/") + "/v1"
            patch = [
                {
                    "id": "llm-deepseek",
                    "disabled": True,
                },
                {
                    "id": "llm-pi-ai",
                    "config": {
                        "providers": {
                            "ollama": {
                                "displayName": "Ollama (HarnessTest)",
                                "apiKeyEnv": "OLLAMA_API_KEY",
                                "api": "openai-completions",
                                "baseURL": base,
                                "models": [
                                    {
                                        "id": model,
                                        "name": model,
                                        "contextWindow": 8192,
                                    }
                                ],
                            }
                        }
                    },
                },
                {
                    "id": "agent-default-model",
                    "config": {"provider": "ollama", "model": model},
                },
                {
                    "id": "agent-loop",
                    "config": {
                        "agents": [
                            {
                                "id": "main",
                                "provider": "ollama",
                                "model": model,
                                "cwd": str(req.workspace),
                            }
                        ]
                    },
                },
            ]
            write_text(cfg_dir / "ollama.patch.yml", yaml.safe_dump(patch, sort_keys=False))

    def run(self, req: RunRequest) -> RunResponse:
        ok, msg = self.available()
        if not ok:
            return unavailable(msg)

        cfg_dir = profile_dir(req, self.name)
        traj = trajectory_path(req, self.name)
        session_log = cfg_dir / "session.jsonl"
        task = (cfg_dir / "task.md").read_text(encoding="utf-8").strip()
        model = resolve_model(req.model or os.environ.get("DEEPSEEK_MODEL"))
        use_ollama = not cloud_provider_key()[0] and ollama_ready(model)[0]

        dsh = which("dsh")
        checkout = os.environ.get("DEEPSEEK_HARNESS_ROOT")
        env = {
            "DSH_CORDIS_CONFIG": str(cfg_dir / "cordis.yml"),
            "DSH_WORKSPACE": str(req.workspace),
            "OLLAMA_API_KEY": os.environ.get("OLLAMA_API_KEY") or "ollama-local",
            "OLLAMA_HOST": OLLAMA_HOST,
        }
        if os.environ.get("DEEPSEEK_API_KEY"):
            env["DEEPSEEK_API_KEY"] = os.environ["DEEPSEEK_API_KEY"]

        patch = cfg_dir / "ollama.patch.yml"
        if dsh:
            argv = ["dsh", "--profile", "headless"]
            if use_ollama and patch.is_file():
                argv.extend(["--patch", str(patch)])
            argv.append(task)
            alt_argv = ["dsh", "agent", "run", "--prompt-file", str(cfg_dir / "task.md")]
        else:
            argv = ["pnpm", "dsh", "--profile", "headless"]
            if use_ollama and patch.is_file():
                argv.extend(["--patch", str(patch)])
            argv.append(task)
            alt_argv = ["pnpm", "dsh", "run", "-q", task]

        cwd = Path(checkout) if checkout else req.workspace
        if dsh and checkout:
            # dsh wrapper cds into checkout; keep cwd as checkout for pnpm resolution.
            cwd = Path(checkout)

        proc = run_cmd(argv, cwd=cwd, env=env, timeout=req.timeout_sec + 120)
        if proc.returncode != 0 and "unknown" in (proc.stderr or "").lower():
            proc = run_cmd(alt_argv, cwd=cwd, env=env, timeout=req.timeout_sec + 120)

        text = combine_output(proc)

        traj_events: list[dict] = []
        if session_log.is_file():
            for line in session_log.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    traj_events.append(json.loads(line))
                except json.JSONDecodeError:
                    traj_events.append({"raw": line})
            text = text + "\n--- trajectory ---\n" + session_log.read_text(encoding="utf-8")

        for candidate in (
            cfg_dir / "trajectory.jsonl",
            req.workspace / ".dsh" / "sessions" / "latest.jsonl",
            Path(checkout or ".") / ".sessions",
        ):
            if candidate.is_dir():
                continue
            if candidate.is_file() and candidate != session_log:
                text = text + f"\n--- {candidate.name} ---\n" + candidate.read_text(encoding="utf-8")
                for line in candidate.read_text(encoding="utf-8").splitlines():
                    try:
                        traj_events.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

        traj.write_text(text, encoding="utf-8")
        denials = parse_policy_denials(text)
        plugin_events = [
            e
            for e in traj_events
            if isinstance(e, dict)
            and (
                "plugin" in json.dumps(e).lower()
                or e.get("type") in {"tool/call", "tools/result", "session/event"}
            )
        ]

        notes = [
            f"DeepSeek Harness deep adapter ({req.profile.value}).",
            "Everything-is-a-plugin TCB: untrusted plugins excluded in hardened profile.",
            "Trajectories are append-only; parsed when session.jsonl is produced.",
            f"backend={'ollama' if use_ollama else 'cloud'}.",
            f"trajectory_events={len(traj_events)} pluginish={len(plugin_events)}.",
            msg,
        ]
        error = None
        if proc.returncode == 124:
            error = "dsh timeout"
        elif proc.returncode != 0:
            error = f"dsh exit={proc.returncode}"
        return RunResponse(
            trajectory_text=text,
            trajectory_path=traj,
            policy_denials=denials,
            approval_required=observe_approval_required(text),
            model=model,
            notes=" ".join(notes),
            error=error,
            live=True,
            raw_events=traj_events or [{"exit_code": proc.returncode}],
        )
