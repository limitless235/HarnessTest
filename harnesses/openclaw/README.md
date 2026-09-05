# OpenClaw (brief baseline)

Install:

```bash
npm install -g openclaw@latest
# or: curl -fsSL https://openclaw.ai/install.sh | bash -s -- --no-onboard
```

## Brief scope (intentional)

OpenClaw is scored as a **brief peer baseline** only:

| Attack | Included |
| --- | --- |
| `kill_chain` | yes |
| `network_egress` | yes |
| `secret_exfil` / `indirect_prompt_injection` / `credential_boundary` / `plugin_supply_chain` | **no** (deep targets only) |

Campaigns always run **default + hardened** for those two attacks.

## Model backends

Prefer local Ollama (parity with Hermes/local):

```bash
export HARNESSTEST_MODEL=qwen2.5:7b   # or 3b / 1.5b if RAM is tight
export OLLAMA_HOST=http://127.0.0.1:11434
export OLLAMA_API_KEY=ollama-local    # any non-empty value
# Optional reliability knobs:
export HARNESSTEST_OPENCLAW_TIMEOUT=480
export HARNESSTEST_OPENCLAW_RETRIES=2
```

Cloud keys (`OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / …) also work via `--auth-env-only`.

## Invocation

HarnessTest invokes (with retries on empty/timeout):

```bash
openclaw agent exec --message-file <task> --cwd <workspace> --state-dir <dir> \
  --isolated --json --timeout <sec> --model ollama/<model> [--local-model-lean]
```

Profiles:

- `default` — sandbox-off / coding tools / elevated-capable posture (baseline)
- `hardened` — lean tools + sandbox-on + deny-network intent

Trajectories must be non-empty for a credible live row; the adapter retries transient failures and records each attempt in the trajectory file.
