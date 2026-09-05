# Hermes (deep)

Install:

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
# or: pip install hermes-agent && hermes postinstall
```

Required env:

- Provider key for the configured Hermes model (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`, …)
- Optional: `HERMES_MODEL` / `HARNESSTEST_MODEL`

HarnessTest writes an isolated `HERMES_HOME` with:

- `default`: local terminal backend, approvals off, skills high trust
- `hardened`: docker terminal backend intent, approvals fail-closed, MCP `trust: untrusted`, env filter strips provider keys

Invokes:

```bash
hermes chat --oneshot -q "<task>"
```

Depth: full P0 (approval, container vs local, MCP env filter, skills = high trust).
