"""OpenClaw adapter — brief baseline (kill-chain + egress)."""

from __future__ import annotations

import json
from pathlib import Path

from harnesstest.adapters import HarnessAdapter, RunRequest, RunResponse, register
from harnesstest.harnesses._common import (
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
        oll_ok, oll_msg = ollama_ready(resolve_model())
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
                "Brief baseline profile. Hardened maps to sandbox-on + deny-network "
                "intent; actual enforcement depends on OpenClaw config / gateway."
            ),
        }
        write_json(cfg_dir / "openclaw.profile.json", config)
        write_text(
            cfg_dir / "task.md",
            req.task_prompt + "\n\nWorkspace root: " + str(req.workspace) + "\n",
        )
        # Capture factual posture for scorecard notes even before a live turn.
        write_json(
            cfg_dir / "posture.json",
            {
                "sandbox_off_default": req.profile == Profile.DEFAULT,
                "elevated_available": req.profile == Profile.DEFAULT,
                "tool_policy": config["tools"],
                "exec_policy": config["exec_policy"],
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

        model = req.model or _default_model()
        use_ollama = not cloud_provider_key()[0] and ollama_ready(resolve_model(model))[0]
        if use_ollama and (not model or "/" not in model):
            # OpenClaw provider/model form
            model = f"ollama/{resolve_model(model)}"

        argv = [
            "openclaw",
            "agent",
            "exec",
            "--message-file",
            str(task_file),
            "--cwd",
            str(req.workspace),
            "--state-dir",
            str(state_dir),
            "--json",
            "--timeout",
            str(req.timeout_sec),
        ]
        if use_ollama:
            argv.append("--isolated")
        else:
            argv.append("--auth-env-only")
        if model:
            argv.extend(["--model", model])
        if hardened(req):
            argv.append("--local-model-lean")

        # Small local models can be slow; keep a bounded timeout so campaigns finish.
        timeout = max(req.timeout_sec, 180 if use_ollama else req.timeout_sec)
        # Replace --timeout value
        if "--timeout" in argv:
            i = argv.index("--timeout")
            argv[i + 1] = str(timeout)

        env = None
        if use_ollama:
            env = {"OLLAMA_API_KEY": "ollama-local"}

        proc = run_cmd(argv, cwd=req.workspace, env=env, timeout=timeout + 60)
        text = combine_output(proc)
        traj.write_text(text, encoding="utf-8")

        denials = parse_policy_denials(text)
        final = _extract_final(text)
        error = None
        if proc.returncode not in (0,):
            error = f"openclaw exit={proc.returncode}"
            if proc.returncode == 2:
                error += " (timeout)"

        posture = json.loads((cfg_dir / "posture.json").read_text(encoding="utf-8"))
        notes = (
            f"OpenClaw brief baseline ({req.profile.value}). "
            f"posture={posture}. {msg}"
        )
        return RunResponse(
            trajectory_text=final or text,
            trajectory_path=traj,
            policy_denials=denials,
            approval_required=observe_approval_required(final or text),
            model=model,
            notes=notes,
            error=error,
            live=True,
            raw_events=[{"exit_code": proc.returncode}],
        )


def _default_model() -> str | None:
    import os

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
                    if data.get("final"):
                        return json.dumps(data, indent=2)
                    return json.dumps(data, indent=2)
    except json.JSONDecodeError:
        pass
    return text
