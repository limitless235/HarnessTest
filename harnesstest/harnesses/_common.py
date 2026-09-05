"""Shared helpers for harness adapters. Prefers local Ollama open-weight models."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from harnesstest.adapters import RunRequest, RunResponse
from harnesstest.models import Profile

DEFAULT_OLLAMA_MODEL = os.environ.get("HARNESSTEST_MODEL", "qwen2.5:1.5b")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

PROVIDER_ENV_KEYS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "DEEPSEEK_API_KEY",
    "NVIDIA_API_KEY",
    "OPENROUTER_API_KEY",
    "GOOGLE_API_KEY",
    "GEMINI_API_KEY",
)


def which(cmd: str) -> str | None:
    return shutil.which(cmd)


def ollama_ready(model: str | None = None) -> tuple[bool, str]:
    try:
        import httpx

        base = OLLAMA_HOST.rstrip("/")
        r = httpx.get(f"{base}/api/tags", timeout=2.0)
        r.raise_for_status()
        names = [m.get("name", "") for m in r.json().get("models", [])]
        want = model or DEFAULT_OLLAMA_MODEL
        if any(n == want or want in n for n in names):
            return True, f"ollama ready model={want} host={base}"
        if names:
            return False, f"ollama up at {base} but missing {want}; have={names}"
        return False, f"ollama up at {base} but no models pulled"
    except Exception as exc:  # noqa: BLE001
        return False, f"ollama not reachable at {OLLAMA_HOST}: {exc}"


def cloud_provider_key() -> tuple[bool, str]:
    present = [k for k in PROVIDER_ENV_KEYS if os.environ.get(k)]
    if present:
        return True, f"provider credentials present: {', '.join(present)}"
    return (
        False,
        "no cloud provider API keys in environment "
        f"(checked: {', '.join(PROVIDER_ENV_KEYS)})",
    )


def any_provider_key() -> tuple[bool, str]:
    """True if either local Ollama or a cloud key can drive a model."""
    ok, msg = ollama_ready()
    if ok:
        return True, msg
    cloud_ok, cloud_msg = cloud_provider_key()
    if cloud_ok:
        return True, f"{cloud_msg} (ollama: {msg})"
    return False, f"no local ollama model and no cloud API keys ({msg})"


def resolve_model(explicit: str | None = None) -> str:
    return explicit or os.environ.get("HARNESSTEST_MODEL") or DEFAULT_OLLAMA_MODEL


def run_cmd(
    argv: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 300,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        argv,
        cwd=str(cwd) if cwd else None,
        env=merged,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def profile_dir(req: RunRequest, harness: str) -> Path:
    d = req.workspace / ".runtime" / "harness" / harness / req.profile.value
    d.mkdir(parents=True, exist_ok=True)
    return d


def trajectory_path(req: RunRequest, harness: str) -> Path:
    return profile_dir(req, harness) / f"{req.attack.value}.trajectory.txt"


def combine_output(proc: subprocess.CompletedProcess[str]) -> str:
    parts = [p for p in (proc.stdout or "", proc.stderr or "") if p]
    return "\n".join(parts)


def parse_policy_denials(text: str) -> list[str]:
    needles = (
        "policy denied",
        "denied by policy",
        "network policy",
        "egress blocked",
        "permission denied",
        "approval required",
        "human_approval_denied",
        "blocked by sandbox",
        "credential not available",
        "tool blocked",
        "exec-policy",
        "network disabled",
        "shell disabled",
        "policy denied",
    )
    lower = text.lower()
    return [n for n in needles if n in lower]


def unavailable(msg: str) -> RunResponse:
    return RunResponse(error=msg, live=False, notes=msg)


def hardened(req: RunRequest) -> bool:
    return req.profile == Profile.HARDENED
