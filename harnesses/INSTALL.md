# Local vendor tooling (not committed — see .gitignore `.vendor/`)

```bash
# Node for OpenClaw / DeepSeek
export PATH="$HOME/.nvm/versions/node/v22.22.3/bin:$PWD/.vendor/npm-global/bin:$PWD/.vendor/bin:$PATH"
export OLLAMA_API_KEY=ollama-local
export DEEPSEEK_HARNESS_ROOT="$PWD/.vendor/deepseek-harness"
```

Install notes:

- **OpenClaw**: Node ≥ 22.22.3; `npm install -g openclaw@latest` into `.vendor/npm-global`
- **Hermes**: `pip install hermes-agent` (venv). Works with local Ollama via custom provider
- **DeepSeek**: clone + `pnpm install && pnpm run build`; expose `dsh` or set `DEEPSEEK_HARNESS_ROOT`
- **NemoClaw**: Docker + OpenShell required (`curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash`)
