# NemoClaw (deep)

Install (needs a working Docker that can `docker run`, plus OpenShell):

```bash
./scripts/install-nemoclaw.sh
# or:
curl -fsSL https://www.nvidia.com/nemoclaw.sh \
  | NEMOCLAW_ACCEPT_THIRD_PARTY_SOFTWARE=1 bash -s -- --yes-i-accept-third-party-software
export PATH="$HOME/.local/bin:$PATH"
```

Dry-run availability (never invents scores):

```bash
./scripts/check-nemoclaw.sh
```

## Free Local Ollama path (preferred for HarnessTest)

No `NVIDIA_INFERENCE_API_KEY` required when Ollama is already running with a usable model:

```bash
export OLLAMA_HOST=http://127.0.0.1:11434
export HARNESSTEST_MODEL=qwen2.5:7b   # or whatever is pulled
export NEMOCLAW_PROVIDER=ollama
export NEMOCLAW_MODEL="${HARNESSTEST_MODEL}"
export NEMOCLAW_YES=1
export NEMOCLAW_ACCEPT_THIRD_PARTY_SOFTWARE=1
export NEMOCLAW_SANDBOX=harnesstest

nemoclaw onboard --non-interactive --yes --fresh --name harnesstest --no-gpu \
  --yes-i-accept-third-party-software

harnesstest campaign --harness nemoclaw
```

## Blockers observed in nested / restricted environments

| Check | Required for live deep | Notes |
| --- | --- | --- |
| `docker` CLI + daemon | yes | Install `docker.io`; start `dockerd` if no systemd |
| `docker run --rm hello-world` | yes | Overlayfs/`invalid argument` here means sandboxes cannot start; remount Docker `data-root` onto ext4 if needed |
| `openshell` + `nemoclaw` on PATH | yes | User-local: `~/.local/bin` |
| Inference: Local Ollama **or** cloud key | yes | Prefer `NEMOCLAW_PROVIDER=ollama` + pulled model; cloud: `NVIDIA_INFERENCE_API_KEY` / `NEMOCLAW_PROVIDER_KEY` |

When blocked, HarnessTest records `live=False` with the probe message — scores are not fabricated.

## Profiles

- `default` — standard policy tier; sink may be allowlisted for observation
- `hardened` — strict tier; empty egress allowlist

Depth: full P0 (credential mediation + deny-by-default network vs OpenClaw baseline).

HarnessTest invokes `nemoclaw <sandbox> agent ...` and `nemoclaw <sandbox> exec` for credential-boundary probes.
