# OpenClaw (deep P0)

Install:

```bash
npm install -g openclaw@latest
# or: curl -fsSL https://openclaw.ai/install.sh | bash -s -- --no-onboard
```

## Depth

OpenClaw is scored as a **deep** peer (parity with Hermes / NemoClaw / DeepSeek):

| Attack | Included |
| --- | --- |
| `kill_chain` | yes |
| `network_egress` | yes |
| `secret_exfil` | yes |
| `indirect_prompt_injection` | yes |
| `credential_boundary` | yes |
| `plugin_supply_chain` | yes |

Campaigns always run **default + hardened** for the full set (`--brief-only` still limits to kill_chain + network_egress).

## Model backends

Prefer local Ollama (parity with Hermes/local):

```bash
export HARNESSTEST_MODEL=qwen2.5:7b   # or 3b / 1.5b if RAM is tight
export OLLAMA_HOST=http://127.0.0.1:11434
export OLLAMA_API_KEY=ollama-local    # any non-empty value
# Optional reliability knobs (7b local needs headroom):
export HARNESSTEST_OPENCLAW_TIMEOUT=900
export HARNESSTEST_OPENCLAW_RETRIES=1
export HARNESSTEST_OPENCLAW_CTX=8192
export HARNESSTEST_RUNTIME=/tmp/harnesstest-runtime
```

Cloud keys (`OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / …) also work via `--auth-env-only`.

## Invocation

HarnessTest invokes (with retries on empty stubs; activity-bearing timeouts stop early):

```bash
openclaw agent exec --message-file <task> --cwd <workspace> --state-dir <dir> \
  --json --thinking off --timeout <sec> --config <exec.json> \
  --model ollama/<model> [--local-model-lean]
```

Notes:

- `--config` is used instead of `--isolated` so context stays at ~8k (isolated defaults are too large for local 7b).
- Agent state lives under `HARNESSTEST_RUNTIME` (default `/tmp/harnesstest-runtime`), not inside the attack workspace.
- Hardened adds `--local-model-lean`.

Profiles:

- `default` — sandbox-off / coding tools / elevated-capable posture (baseline)
- `hardened` — lean tools + sandbox-on + deny-network intent

Non-zero exits and timeouts remain `live_with_error` in the scorecard (observed scores, not silent clean passes).
