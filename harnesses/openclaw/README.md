# OpenClaw (brief baseline)

Install:

```bash
npm install -g openclaw@latest
# or: curl -fsSL https://openclaw.ai/install.sh | bash -s -- --no-onboard
```

Required env (any one provider key used by OpenClaw auth-env-only):

- `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / etc.
- Optional: `OPENCLAW_MODEL` or `HARNESSTEST_MODEL` (e.g. `openai/gpt-4.1-mini`)

HarnessTest invokes:

```bash
openclaw agent exec --message-file <task> --cwd <workspace> --state-dir <dir> \
  --auth-env-only --json --timeout <sec> [--model ...] [--local-model-lean]
```

Profiles:

- `default` — sandbox-off / coding tools / elevated-capable posture (baseline)
- `hardened` — lean tools + sandbox-on intent

Depth: brief — `kill_chain` + `network_egress` only.
