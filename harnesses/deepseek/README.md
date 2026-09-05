# DeepSeek Harness (deep)

Install:

```bash
git clone https://github.com/deepseek-ai/deepseek-harness.git
cd deepseek-harness
pnpm install && pnpm run build
# expose `dsh` on PATH, or set DEEPSEEK_HARNESS_ROOT to the checkout
```

Required env:

- `DEEPSEEK_API_KEY` (or another provider key the checkout is configured to use)
- Optional: `DEEPSEEK_HARNESS_ROOT`, `DEEPSEEK_MODEL` / `HARNESSTEST_MODEL`

HarnessTest writes a `cordis.yml` overlay:

- `default`: includes synthetic high-TCB `ht-weather-helper` plugin
- `hardened`: excludes untrusted plugin; sandbox on; append-only trajectory

Trajectories are parsed from `session.jsonl` when produced (`Model-visible means logged`).

Depth: full P0 + plugin TCB + trajectory parsing.
