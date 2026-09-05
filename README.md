# HarnessTest

Security benchmark for AI agent harnesses. Assumes the model may be compromised and measures which architectural layer stops the attack.

## Model backend (local open-weight)

HarnessTest defaults to **Ollama** with a small open-weight model:

```bash
# already used in this project
ollama pull qwen2.5:1.5b
export HARNESSTEST_MODEL=qwen2.5:1.5b
export OLLAMA_HOST=http://127.0.0.1:11434
```

No cloud API keys are required for the `local` harness adapter.

| Harness | Depth | Notes |
| --- | --- | --- |
| `local` | Demo / control | Ollama tool loop with default vs hardened tool policy |
| `openclaw` | Brief baseline | Platform defaults, sandbox/tool/elevated split |
| `nemoclaw` | Deep | External OpenShell control plane |
| `hermes` | Deep | Layered in-agent defenses |
| `deepseek` | Deep | Plugin TCB + trajectories |

## Safety

- Synthetic secrets only (`fake_secret_*`)
- Egress only to a local controlled sink
- Non-weaponized sandbox probes only
- Scores come from live runs — never fabricated

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Ensure Ollama is running with the demo model
ollama serve   # if not already running
ollama pull qwen2.5:1.5b

python -m harnesstest.cli model
python -m harnesstest.cli probe --workspace fixtures/workspace

# Live demo against the local open-weight adapter
python -m harnesstest.cli run --harness local --profile default --attack kill_chain
python -m harnesstest.cli run --harness local --profile hardened --attack kill_chain

# Campaign (default + hardened)
python -m harnesstest.cli campaign --harness local
```

## Kill chain

```text
Untrusted README → objective change → tool call → FS read of planted secret
  → egress attempt → (optional) plugin/skill escalation
```

Each run records the first stage that stops the chain (or `none` if the chain completed).

## Layout

```text
attacks/           # adversarial fixtures + expected violation markers
fixtures/          # shared workspace (synthetic secrets, untrusted README)
harnesstest/       # runner, instrumentation, scorecard, adapters
reports/           # generated results
tests/
```
