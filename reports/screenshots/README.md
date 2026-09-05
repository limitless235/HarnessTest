# Live run screenshots (2026-09-05)

Evidence from Ollama/`qwen2.5:7b` campaigns on branch `cursor/harnesstest-scaffold-b308`
(earlier captures used `1.5b`; scorecard.md is authoritative for current scores).

## What ran

| Target | Result | Notes |
| --- | --- | --- |
| **local** | PASS (live) | default+hardened × kill_chain, network_egress, secret_exfil, indirect_prompt_injection @ 7b |
| **hermes** | PASS (live) | full deep campaign (12 attacks) via Ollama custom provider @ 7b |
| **openclaw** | PASS (live, brief) | kill_chain + network_egress × default+hardened @ 7b; retries/Ollama wired; kill-chain stages observed |
| **nemoclaw** | BLOCKED | CLIs installed; `docker run` fails (overlayfs); no provider key for onboard — recorded live=False |
| **deepseek** | PASS (live, deep) | checkout+build + Ollama `llm-pi-ai` patch; 12/12 live (some `dsh exit=1` still scored from trajectories) |

Scores are from live adapter runs only — not invented. Profiles scored separately; no synthetic denials.

## Files

- `02-scorecard-chrome*.png` — rendered `scorecard.md`
- `03-run-evidence-logs.png` — campaign completion logs
- `04` / `07-terminal-output*.png` — terminal-style campaign output
- `05-scorecard-local-section.png` — local harness dimension scores
- `06-scorecard-killchain-table.png` — first-stop table
- `scorecard.html` / `run-evidence.html` / `terminal-output.html` — HTML used for capture

Canonical scorecard: [`../scorecard.md`](../scorecard.md).
