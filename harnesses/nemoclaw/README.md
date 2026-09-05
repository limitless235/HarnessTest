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

## Blockers observed in nested / restricted environments

| Check | Required for live deep | Notes |
| --- | --- | --- |
| `docker` CLI + daemon | yes | Install `docker.io`; start `dockerd` if no systemd |
| `docker run --rm hello-world` | yes | Overlayfs/`invalid argument` here means sandboxes cannot start |
| `openshell` + `nemoclaw` on PATH | yes | User-local: `~/.local/bin` |
| `NVIDIA_INFERENCE_API_KEY` / `NEMOCLAW_PROVIDER_KEY` (or other cloud key) | yes | Non-interactive `nemoclaw onboard` requires a provider key; Ollama/NIM needs GPU |

When blocked, HarnessTest records `live=False` with the probe message — scores are not fabricated.

## Profiles

- `default` — standard policy tier; sink may be allowlisted for observation
- `hardened` — strict tier; empty egress allowlist

Depth: full P0 (credential mediation + deny-by-default network vs OpenClaw baseline).

HarnessTest invokes `nemoclaw <sandbox> agent ...` and `nemoclaw <sandbox> exec` for credential-boundary probes.
