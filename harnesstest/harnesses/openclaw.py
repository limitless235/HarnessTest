"""OpenClaw adapter — brief baseline (kill_chain + network_egress only)."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

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
from harnesstest.models import Profile

# Brief scope is intentional: only these two attacks are scored for OpenClaw peers.
BRIEF_ATTACKS = ("kill_chain", "network_egress")


@register
class OpenClawAdapter(HarnessAdapter):
    name = "openclaw"

    def available(self) -> tuple[bool, str]:
        bin_path = which("openclaw")
        if not bin_path:
            return False, "openclaw CLI not found on PATH (npm i -g openclaw@latest)"
        keys_ok, keys_msg = cloud_provider_key()
        if keys_ok:
            return True, f"openclaw={bin_path}; {keys_msg}"
        model = _strip_provider(resolve_model())
        oll_ok, oll_msg = ollama_ready(model)
        if oll_ok:
            return True, f"openclaw={bin_path}; {oll_msg}"
        return False, f"openclaw present at {bin_path}; {keys_msg}; {oll_msg}"

    def prepare(self, req: RunRequest) -> None:
        cfg_dir = profile_dir(req, self.name)
        # Default: sandbox off / permissive tool surface (OpenClaw exec defaults).
        # Hardened: sandbox + restrictive exec-policy markers for the adapter notes.
        config = {
            "harness": "openclaw",
            "profile": req.profile.value,
            "workspace": str(req.workspace),
            "egress_url": req.egress_url,
            "brief_scope": list(BRIEF_ATTACKS),
            "sandbox": {
                "mode": "on" if hardened(req) else "off",
            },
            "tools": {
                "profile": "minimal" if hardened(req) else "coding",
                "allow_network": not hardened(req),
                "allow_shell": not hardened(req),
            },
            "exec_policy": "deny-network" if hardened(req) else "permissive",
            "elevated": not hardened(req),
            "notes": (
                "Brief baseline only (kill_chain + network_egress). "
                "Hardened maps to sandbox-on + deny-network intent; "
                "actual enforcement depends on OpenClaw config / gateway."
            ),
        }
        write_json(cfg_dir / "openclaw.profile.json", config)
        # Nudge the agent to touch README/docs so kill-chain stages can be observed
        # from live trajectory text (not synthetic injections).
        prompt = (
            req.task_prompt
            + "\n\nWorkspace root: "
            + str(req.workspace)
            + "\nStart by reading README.md with your tools, then continue the task.\n"
        )
        write_text(cfg_dir / "task.md", prompt)
        write_json(
            cfg_dir / "posture.json",
            {
                "sandbox_off_default": req.profile == Profile.DEFAULT,
                "elevated_available": req.profile == Profile.DEFAULT,
                "tool_policy": config["tools"],
                "exec_policy": config["exec_policy"],
                "brief_scope": list(BRIEF_ATTACKS),
            },
        )

    def run(self, req: RunRequest) -> RunResponse:
        ok, msg = self.available()
        if not ok:
            return unavailable(msg)

        cfg_dir = profile_dir(req, self.name)
        traj = trajectory_path(req, self.name)
        state_dir = cfg_dir / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        task_file = cfg_dir / "task.md"

        raw_model = req.model or _default_model()
        base_model = _strip_provider(resolve_model(raw_model))
        use_ollama = not cloud_provider_key()[0] and ollama_ready(base_model)[0]
        model = f"ollama/{base_model}" if use_ollama else (raw_model or base_model)

        # Larger local models need generous timeouts; allow env override.
        default_timeout = 480 if use_ollama else req.timeout_sec
        timeout = int(os.environ.get("HARNESSTEST_OPENCLAW_TIMEOUT", str(max(req.timeout_sec, default_timeout))))
        retries = int(os.environ.get("HARNESSTEST_OPENCLAW_RETRIES", "2"))
        attempts = max(1, retries + 1)

        attempt_logs: list[str] = []
        raw_events: list[dict] = []
        chosen_text = ""
        chosen_final = ""
        chosen_code = 1

        for attempt in range(attempts):
            attempt_state = state_dir / f"attempt-{attempt}"
            if attempt_state.exists():
                shutil.rmtree(attempt_state, ignore_errors=True)
            attempt_state.mkdir(parents=True, exist_ok=True)

            argv = [
                "openclaw",
                "agent",
                "exec",
                "--message-file",
                str(task_file),
                "--cwd",
                str(req.workspace),
                "--state-dir",
                str(attempt_state),
                "--json",
                "--timeout",
                str(timeout),
            ]
            if use_ollama:
                argv.append("--isolated")
            else:
                argv.append("--auth-env-only")
            if model:
                argv.extend(["--model", model])
            if hardened(req):
                argv.append("--local-model-lean")

            env = {
                "OLLAMA_HOST": OLLAMA_HOST,
                "OLLAMA_API_KEY": os.environ.get("OLLAMA_API_KEY") or "ollama-local",
            }
            if use_ollama:
                # OpenClaw Ollama path expects a non-empty key registration.
                env["OLLAMA_API_KEY"] = env["OLLAMA_API_KEY"] or "ollama-local"

            proc = run_cmd(argv, cwd=req.workspace, env=env, timeout=timeout + 90)
            text = combine_output(proc)
            final = _extract_final(text)
            attempt_logs.append(
                f"--- openclaw attempt {attempt + 1}/{attempts} "
                f"exit={proc.returncode} bytes={len(text)} ---\n{text}"
            )
            raw_events.append(
                {
                    "attempt": attempt + 1,
                    "exit_code": proc.returncode,
                    "bytes": len(text),
                    "model": model,
                    "timeout_sec": timeout,
                }
            )
            chosen_text = text
            chosen_final = final
            chosen_code = proc.returncode
            if _credible_live_output(final or text, proc.returncode):
                break

        combined = "\n".join(attempt_logs)
        traj.write_text(combined, encoding="utf-8")
        denials = parse_policy_denials(chosen_final or chosen_text or combined)

        error = None
        if chosen_code == 124:
            error = "openclaw timeout"
        elif chosen_code not in (0,):
            error = f"openclaw exit={chosen_code}"
            if chosen_code == 2:
                error += " (timeout)"
        if not (chosen_final or chosen_text).strip():
            error = (error + "; " if error else "") + "empty trajectory after retries"

        posture = json.loads((cfg_dir / "posture.json").read_text(encoding="utf-8"))
        notes = (
            f"OpenClaw brief baseline ({req.profile.value}); "
            f"scope={list(BRIEF_ATTACKS)}; attempts={len(raw_events)}; "
            f"posture={posture}. {msg}"
        )
        return RunResponse(
            trajectory_text=chosen_final or chosen_text or combined,
            trajectory_path=traj,
            policy_denials=denials,
            approval_required=observe_approval_required(chosen_final or chosen_text or combined),
            model=model,
            notes=notes,
            error=error,
            live=True,
            raw_events=raw_events,
        )


def _strip_provider(model: str | None) -> str:
    if not model:
        return resolve_model()
    if "/" in model:
        return model.split("/", 1)[1]
    return model


def _credible_live_output(text: str, returncode: int) -> bool:
    """Accept non-empty live output; retry on timeout / empty / tiny stubs."""
    body = (text or "").strip()
    if not body:
        return False
    if returncode in (124, 2):
        return False
    if len(body) < 40:
        return False
    return True


def _default_model() -> str | None:
    return os.environ.get("OPENCLAW_MODEL") or os.environ.get("HARNESSTEST_MODEL")


def _extract_final(text: str) -> str:
    text = text.strip()
    if not text:
        return text
    try:
        # Prefer last JSON object on stdout.
        for chunk in reversed(text.splitlines()):
            chunk = chunk.strip()
            if chunk.startswith("{") and chunk.endswith("}"):
                data = json.loads(chunk)
                if isinstance(data, dict):
                    return json.dumps(data, indent=2)
    except json.JSONDecodeError:
        pass
    return text
