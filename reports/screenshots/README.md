# Live run screenshots (2026-09-05)

Evidence from a fresh Ollama/`qwen2.5:1.5b` campaign on branch `cursor/harnesstest-scaffold-b308`.

## What ran

| Target | Result | Notes |
| --- | --- | --- |
| **local** | PASS (live) | default+hardened × kill_chain, network_egress, secret_exfil, indirect_prompt_injection |
| **hermes** | PASS (live) | full deep campaign (12 attacks) via Ollama custom provider |
| **openclaw** | PASS (live, brief) | kill_chain + network_egress × default+hardened; one egress exit=1 but still live |
| **nemoclaw** | SKIPPED | `nemoclaw` CLI missing; Docker/OpenShell unavailable |
| **deepseek** | SKIPPED | `dsh` vendor checkout missing; no cloud provider API keys |

Scores are from live adapter runs only — not invented.

## Files

- `02-scorecard-chrome*.png` — rendered `scorecard.md`
- `03-run-evidence-logs.png` — campaign completion logs
- `04` / `07-terminal-output*.png` — terminal-style campaign output
- `05-scorecard-local-section.png` — local harness dimension scores
- `06-scorecard-killchain-table.png` — first-stop table
- `scorecard.html` / `run-evidence.html` / `terminal-output.html` — HTML used for capture

Canonical scorecard: [`../scorecard.md`](../scorecard.md).
