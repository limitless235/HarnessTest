#!/usr/bin/env bash
# Best-effort NemoClaw/OpenShell installer for HarnessTest deep campaigns.
set -euo pipefail
export PATH="${HOME}/.local/bin:${PATH}"

echo "==> Checking Docker"
if ! command -v docker >/dev/null 2>&1; then
  echo "BLOCKER: docker not on PATH. Install docker.io and ensure the daemon is reachable."
  exit 2
fi
if ! docker info >/dev/null 2>&1; then
  echo "BLOCKER: docker CLI present but daemon not reachable."
  docker info 2>&1 | head -20 || true
  exit 3
fi
if ! docker run --rm hello-world >/tmp/harnesstest-docker-hello.log 2>&1; then
  echo "BLOCKER: docker daemon up but containers cannot start (often overlayfs/nested-env)."
  tail -20 /tmp/harnesstest-docker-hello.log || true
  echo "Continuing install of CLIs for dry-run checks; live sandboxes will remain blocked."
fi

echo "==> Installing NemoClaw (non-interactive third-party accept)"
curl -fsSL https://www.nvidia.com/nemoclaw.sh \
  | NEMOCLAW_ACCEPT_THIRD_PARTY_SOFTWARE=1 bash -s -- --yes-i-accept-third-party-software

echo "==> Verifying"
command -v nemoclaw || true
command -v openshell || true
nemoclaw --help 2>&1 | head -20 || true

echo ""
echo "Preferred free path (Local Ollama, no NVIDIA key):"
echo "  export NEMOCLAW_PROVIDER=ollama"
echo "  export NEMOCLAW_MODEL=\${HARNESSTEST_MODEL:-qwen2.5:7b}"
echo "  export NEMOCLAW_YES=1 NEMOCLAW_ACCEPT_THIRD_PARTY_SOFTWARE=1"
echo "  nemoclaw onboard --non-interactive --yes --fresh --name harnesstest --no-gpu \\"
echo "    --yes-i-accept-third-party-software"
echo ""
echo "Cloud alternative: set NVIDIA_INFERENCE_API_KEY / NEMOCLAW_PROVIDER_KEY, then onboard."
echo "Then: harnesstest campaign --harness nemoclaw"
