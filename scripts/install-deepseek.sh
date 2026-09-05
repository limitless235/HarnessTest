#!/usr/bin/env bash
# Clone + build DeepSeek Harness into .vendor for HarnessTest deep campaigns.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${DEEPSEEK_HARNESS_ROOT:-$ROOT/.vendor/deepseek-harness}"
export PATH="${HOME}/.nvm/versions/node/v22.22.3/bin:${ROOT}/.vendor/npm-global/bin:${PATH}"

mkdir -p "$(dirname "$DEST")"
if [[ ! -d "$DEST/.git" ]]; then
  echo "==> Cloning deepseek-harness → $DEST"
  git clone --depth 1 https://github.com/deepseek-ai/deepseek-harness.git "$DEST"
else
  echo "==> Reusing checkout at $DEST"
fi

cd "$DEST"
command -v pnpm >/dev/null || npm install -g pnpm
echo "==> pnpm install"
pnpm install
echo "==> pnpm run build"
pnpm run build

mkdir -p "$ROOT/.vendor/bin"
cat > "$ROOT/.vendor/bin/dsh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
ROOT="\$(cd "\$(dirname "\$0")/.." && pwd)/deepseek-harness"
export PATH="${HOME}/.nvm/versions/node/v22.22.3/bin:\${PATH}"
cd "\$ROOT"
exec pnpm dsh "\$@"
EOF
chmod +x "$ROOT/.vendor/bin/dsh"

echo "export DEEPSEEK_HARNESS_ROOT=$DEST"
echo "export PATH=$ROOT/.vendor/bin:\$PATH"
echo "Prefer Ollama: HARNESSTEST_MODEL=qwen2.5:7b OLLAMA_API_KEY=ollama-local"
echo "Or set DEEPSEEK_API_KEY for cloud."
"$ROOT/.vendor/bin/dsh" --help | head -20 || true
