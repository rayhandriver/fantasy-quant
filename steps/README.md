# steps/

Phased, **runnable** scripts — one per `PROJECT.md` phase/step — that orchestrate the reusable logic in
`src/fantasy_quant/`. Mirrors the intern-repo's `steps/` convention: each script is a discrete working
session with a clear "done when," and records its outcome in `../findings.md`.

Run with uv (no activation needed):
```bash
uv run python steps/<script>.py
```

Keep reusable primitives in the package (`src/fantasy_quant/...`); keep these files as thin, documented
drivers. Empty for now — Phase 0 lands the first scripts (data ingest + the backtest harness).
