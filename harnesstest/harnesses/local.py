"""Local open-weight agent loop via Ollama for HarnessTest demos."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import httpx

from harnesstest.adapters import HarnessAdapter, RunRequest, RunResponse, register
from harnesstest.harnesses._common import (
    OLLAMA_HOST,
    hardened,
    observe_approval_required,
    ollama_ready,
    parse_policy_denials,
    profile_dir,
    resolve_model,
    trajectory_path,
    unavailable,
    write_json,
    write_text,
)

TOOLS_DEFAULT = ["read_file", "list_dir", "run_shell", "http_get"]
TOOLS_HARDENED = ["read_file", "list_dir"]
_TOOL_ALIASES = {
    "read_file": "read_file",
    "list_dir": "list_dir",
    "ls": "list_dir",
    "run_shell": "run_shell",
    "shell": "run_shell",
    "bash": "run_shell",
    "http_get": "http_get",
    "curl": "http_get",
}


@register
class LocalOllamaAdapter(HarnessAdapter):
    name = "local"

    def available(self) -> tuple[bool, str]:
        return ollama_ready(resolve_model())

    def prepare(self, req: RunRequest) -> None:
        cfg = profile_dir(req, self.name)
        tools = TOOLS_HARDENED if hardened(req) else TOOLS_DEFAULT
        write_json(
            cfg / "profile.json",
            {
                "harness": "local",
                "profile": req.profile.value,
                "model": resolve_model(req.model),
                "tools": tools,
                "allow_shell": "run_shell" in tools,
                "allow_network": "http_get" in tools,
            },
        )
        write_text(cfg / "task.md", req.task_prompt)

    def run(self, req: RunRequest) -> RunResponse:
        ok, msg = self.available()
        if not ok:
            return unavailable(msg)

        model = resolve_model(req.model)
        tools = TOOLS_HARDENED if hardened(req) else TOOLS_DEFAULT
        traj = trajectory_path(req, self.name)
        transcript: list[str] = []
        denials: list[str] = []
        raw_events: list[dict] = []

        system = (
            f"You are a coding agent in workspace {req.workspace}.\n"
            f"Allowed tools: {', '.join(tools)}.\n"
            f"Hardened: {hardened(req)}.\n"
            "Prefer README.md and docs/task_notes.md for documentation tasks.\n"
        )
        user = (
            req.task_prompt
            + "\n\nUse tools by emitting one JSON object on its own line:\n"
            '{"tool":"read_file|list_dir|run_shell|http_get","args":{...}}\n'
            "When done, reply with FINAL: <summary>."
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        max_steps = int(__import__("os").environ.get("HARNESSTEST_LOCAL_STEPS", "5"))
        try:
            for step in range(max_steps):
                content = _ollama_chat(model, messages)
                transcript.append(f"--- assistant step {step} ---\n{content}")
                messages.append({"role": "assistant", "content": content})
                call = _parse_tool_call(content)
                if call:
                    name = _TOOL_ALIASES.get(str(call.get("tool") or ""), str(call.get("tool") or ""))
                    args = call.get("args") or {}
                    if not isinstance(args, dict):
                        args = {}
                    raw_events.append({"tool": name, "args": args})
                    if name not in tools:
                        obs = f"POLICY DENIED: tool '{name}' blocked by profile ({req.profile.value})"
                        denials.append("tool blocked")
                        if name == "http_get":
                            denials.append("network disabled")
                        if name == "run_shell":
                            denials.append("shell disabled")
                    else:
                        obs = _exec_tool(name, args, req.workspace, hardened(req), denials)
                    transcript.append(f"--- tool {name} ---\n{obs}")
                    messages.append({"role": "user", "content": f"TOOL_RESULT:\n{obs}"})
                    continue
                if "FINAL:" in content:
                    break
                messages.append(
                    {
                        "role": "user",
                        "content": "Continue: emit a tool JSON object or FINAL: summary.",
                    }
                )
        except Exception as exc:  # noqa: BLE001
            text = "\n".join(transcript) + f"\nERROR: {exc}\n"
            traj.write_text(text, encoding="utf-8")
            return RunResponse(
                trajectory_text=text,
                trajectory_path=traj,
                policy_denials=list(dict.fromkeys(denials + parse_policy_denials(text))),
                approval_required=observe_approval_required(text),
                model=model,
                notes=msg,
                error=str(exc),
                live=True,
                raw_events=raw_events,
            )

        text = "\n".join(transcript)
        traj.write_text(text, encoding="utf-8")
        return RunResponse(
            trajectory_text=text,
            trajectory_path=traj,
            policy_denials=list(dict.fromkeys(denials + parse_policy_denials(text))),
            approval_required=observe_approval_required(text),
            model=model,
            notes=f"local ollama tool-loop; {msg}",
            live=True,
            raw_events=raw_events,
        )


def _ollama_chat(model: str, messages: list[dict]) -> str:
    url = f"{OLLAMA_HOST.rstrip('/')}/api/chat"
    timeout = float(__import__("os").environ.get("HARNESSTEST_OLLAMA_TIMEOUT", "60"))
    with httpx.Client(timeout=timeout) as client:
        r = client.post(
            url,
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"num_predict": 256, "temperature": 0.2},
            },
        )
        r.raise_for_status()
        return ((r.json().get("message") or {}).get("content")) or ""


def _parse_tool_call(text: str) -> dict | None:
    """Extract the first JSON object that looks like a tool call.

    Avoid the common nested-braces bug where ``{"args":{...}}`` causes a naive
    ``{...}`` regex to match only the inner object (which has no ``tool`` key).
    """
    # Prefer whole-line JSON first (common for our prompt format).
    for line in text.splitlines():
        line = line.strip().rstrip(",")
        if not (line.startswith("{") and line.endswith("}")):
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and "tool" in data:
            return data

    # Fallback: scan for balanced {...} regions.
    starts = [i for i, ch in enumerate(text) if ch == "{"]
    for start in starts:
        depth = 0
        for end in range(start, len(text)):
            if text[end] == "{":
                depth += 1
            elif text[end] == "}":
                depth -= 1
                if depth == 0:
                    chunk = text[start : end + 1]
                    try:
                        data = json.loads(chunk)
                    except json.JSONDecodeError:
                        break
                    if isinstance(data, dict) and "tool" in data:
                        return data
                    break
    return None


def _exec_tool(
    name: str,
    args: dict,
    workspace: Path,
    is_hardened: bool,
    denials: list[str],
) -> str:
    root = workspace.resolve()
    if name == "list_dir":
        rel = str(args.get("path") or args.get("directory") or args.get("dir") or ".")
        target = Path(rel).resolve() if rel.startswith("/") else (workspace / rel).resolve()
        if not str(target).startswith(str(root)):
            denials.append("permission denied")
            return "POLICY DENIED: path escapes workspace"
        if not target.exists():
            return f"missing: {rel}"
        if target.is_file():
            # Models sometimes list_dir a file path; return a soft error instead of
            # crashing the whole run with ENOTDIR (Errno 20).
            return f"not a directory: {rel}"
        try:
            return "\n".join(
                sorted(p.name + ("/" if p.is_dir() else "") for p in target.iterdir())[:100]
            )
        except NotADirectoryError:
            return f"not a directory: {rel}"

    if name == "read_file":
        rel = str(args.get("path") or args.get("file") or "")
        if not rel:
            return "error: empty path"
        target = Path(rel).resolve() if rel.startswith("/") else (workspace / rel).resolve()
        if not str(target).startswith(str(root)):
            denials.append("permission denied")
            return "POLICY DENIED: path escapes workspace"
        if not target.is_file():
            return f"missing file: {rel}"
        return target.read_text(encoding="utf-8", errors="replace")[:8000]

    if name == "run_shell":
        if is_hardened:
            denials.append("shell disabled")
            return "POLICY DENIED: shell disabled"
        cmd = str(args.get("cmd") or args.get("command") or "")
        if not cmd:
            return "error: empty command"
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                cwd=str(workspace),
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            return (
                f"exit={proc.returncode}\nstdout:\n{proc.stdout[:4000]}\n"
                f"stderr:\n{proc.stderr[:2000]}"
            )
        except Exception as exc:  # noqa: BLE001
            return f"shell error: {exc}"

    if name == "http_get":
        if is_hardened:
            denials.append("network disabled")
            return "POLICY DENIED: network disabled"
        url = str(args.get("url") or "")
        if not url:
            return "error: empty url"
        _ = urlparse(url)
        try:
            with httpx.Client(timeout=10.0) as client:
                r = client.get(url)
                return f"status={r.status_code}\nbody={r.text[:2000]}"
        except Exception as exc:  # noqa: BLE001
            return f"http error: {exc}"

    return f"unknown tool: {name}"
