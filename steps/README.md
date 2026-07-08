# steps/

Phased, **runnable** scripts — one per `PROJECT.md` phase/step — that orchestrate the reusable logic in
`src/fantasy_quant/`. Mirrors the intern-repo's `steps/` convention: each script is a discrete working
session with a clear "done when," and records its outcome in `../findings.md`.

Run with uv (no activation needed):
```bash
uv run python steps/<script>.py
```

Keep reusable primitives in the package (`src/fantasy_quant/...`); keep these files as thin, documented
drivers.

Scripts cover **Phase 0 → 6** (`phase0_2_*` … `phase5_5_*`: ingest → harness → baselines → features →
value → distributions; `phase6_adp_bias`: ADP-softness scorecard) plus the **personalization spine**
(`spine_1_config` · `spine_2_optimizer` · `spine_3_cost_report` · `spine_4_validate` — the realized-PAR
validation of the cost number). The spine's UI is the Streamlit app, launched differently:
```bash
uv sync --extra ui
uv run streamlit run src/fantasy_quant/app/streamlit_app.py
```
