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
if [[ -z "${NVIDIA_INFERENCE_API_KEY:-}${NEMOCLAW_PROVIDER_KEY:-}${NVIDIA_API_KEY:-}${OPENAI_API_KEY:-}${ANTHROPIC_API_KEY:-}" ]]; then
  echo "provider keys: MISSING (need NVIDIA_INFERENCE_API_KEY / NEMOCLAW_PROVIDER_KEY or other cloud key)"
  ok=1
else
  echo "provider keys: present"
fi
exit $ok
