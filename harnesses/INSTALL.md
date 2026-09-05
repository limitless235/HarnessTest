# Local vendor tooling (not committed — see .gitignore)

OpenClaw, DeepSeek Harness, and npm globals are installed under `.vendor/` on this machine:

```bash
export PATH="/home/ubuntu/.nvm/versions/node/v22.22.3/bin:$PWD/.vendor/npm-global/bin:$PWD/.vendor/bin:$PATH"
export DEEPSEEK_HARNESS_ROOT="$PWD/.vendor/deepseek-harness"
```

- OpenClaw: `npm install -g openclaw@latest` with Node ≥ 22.22.3 into `.vendor/npm-global`
- Hermes: `pip install hermes-agent` (into the project venv)
- DeepSeek: shallow clone + `pnpm install && pnpm run build` in `.vendor/deepseek-harness`
- NemoClaw: requires Docker/OpenShell — not installable without Docker
