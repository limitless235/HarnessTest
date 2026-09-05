# DeepSeek Harness (deep)

Install:

```bash
./scripts/install-deepseek.sh
export DEEPSEEK_HARNESS_ROOT="$PWD/.vendor/deepseek-harness"
export PATH="$PWD/.vendor/bin:$PATH"
```

## Model backends (prefer Ollama for parity)

```bash
export HARNESSTEST_MODEL=qwen2.5:7b
export OLLAMA_HOST=http://127.0.0.1:11434
export OLLAMA_API_KEY=ollama-local
```

HarnessTest writes an `ollama.patch.yml` overlay that routes `llm-pi-ai` to the local
OpenAI-compatible Ollama `/v1` endpoint and disables the cloud `llm-deepseek` plugin.

Cloud alternative: set `DEEPSEEK_API_KEY` (or another provider key) and omit the Ollama path.

## Profiles

- `default`: includes synthetic high-TCB `ht-weather-helper` plugin
- `hardened`: excludes untrusted plugin; sandbox on; append-only trajectory

Trajectories are parsed from `session.jsonl` when produced (`Model-visible means logged`).

Depth: full P0 + plugin TCB + trajectory parsing.

```bash
harnesstest campaign --harness deepseek --model qwen2.5:7b
```
