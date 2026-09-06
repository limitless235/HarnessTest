#!/usr/bin/env bash
# Dry-run availability check — never fabricates scores.
set -euo pipefail
export PATH="${HOME}/.local/bin:${PATH}"
ok=0
echo "docker: $(command -v docker || echo MISSING)"
if command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then
    echo "docker daemon: OK"
    if docker run --rm hello-world >/tmp/harnesstest-docker-hello.log 2>&1; then
      echo "docker run: OK"
    else
      echo "docker run: FAILED (containers cannot start — see /tmp/harnesstest-docker-hello.log)"
      ok=1
    fi
  else
    echo "docker daemon: UNREACHABLE"; ok=1
  fi
else
  ok=1
fi
echo "nemoclaw: $(command -v nemoclaw || echo MISSING)"
echo "openshell: $(command -v openshell || echo MISSING)"
command -v nemoclaw >/dev/null || ok=1
command -v openshell >/dev/null || ok=1

# Cloud key OR local Ollama counts as a valid inference path.
OLLAMA_HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
MODEL="${NEMOCLAW_MODEL:-${HARNESSTEST_MODEL:-qwen2.5:7b}}"
if [[ -n "${NVIDIA_INFERENCE_API_KEY:-}${NEMOCLAW_PROVIDER_KEY:-}${NVIDIA_API_KEY:-}${OPENAI_API_KEY:-}${ANTHROPIC_API_KEY:-}" ]]; then
  echo "provider keys: present"
elif curl -fsS "${OLLAMA_HOST%/}/api/tags" >/tmp/harnesstest-ollama-tags.json 2>/dev/null \
  && grep -q "\"${MODEL}\"" /tmp/harnesstest-ollama-tags.json 2>/dev/null; then
  echo "provider: Local Ollama OK (model=${MODEL} host=${OLLAMA_HOST})"
else
  echo "provider: MISSING (need Local Ollama model=${MODEL} at ${OLLAMA_HOST}, or NVIDIA_INFERENCE_API_KEY / NEMOCLAW_PROVIDER_KEY / cloud key)"
  ok=1
fi
exit $ok
