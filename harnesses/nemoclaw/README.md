# NemoClaw (deep)

Install (needs Docker + OpenShell):

```bash
curl -fsSL https://www.nvidia.com/nemoclaw.sh | bash
# see https://github.com/NVIDIA/NemoClaw
```

Required env:

- Provider key accepted by NemoClaw onboarding (`NVIDIA_API_KEY`, `OPENAI_API_KEY`, …)
- Optional: `NEMOCLAW_SANDBOX` (default `harnesstest`), `NEMOCLAW_MODEL`

HarnessTest focuses on **credential mediation** and **deny-by-default network** vs OpenClaw baseline.

Invokes `nemoclaw agent -m ... --json` and `nemoclaw exec` for credential-boundary probes.

Profiles:

- `default` — standard policy tier; sink may be allowlisted for observation
- `hardened` — strict tier; empty egress allowlist

Depth: full P0.
