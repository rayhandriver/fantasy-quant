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

Scripts cover **Phase 0 → 10** (`phase0_2_*` … `phase5_5_*`: ingest → harness → baselines → features →
value → distributions; `phase6_adp_bias`: ADP-softness scorecard; `phase8_covariance`: relationship
correlations + shrinkage, handcuff copula, roster risk, and the covariance-aware greedy checks;
`phase10_sim`: the season/playoff-sim calibration gate on DEV leagues), the **stage-0 chores**
(`stage0_adp_snapshot`: the recurring FFC 2026 snapshot — idempotent, run weekly until the season starts;
`stage0_sleeper_probe`: the read-only Sleeper API de-risk probe), plus the **personalization spine**
(`spine_1_config` · `spine_2_optimizer` · `spine_3_cost_report` · `spine_4_validate` — the realized-PAR
validation of the cost number). The spine's UI is the Streamlit app (Phase 14.1 / Session K1 — the cost report is its
**Cost** tab), launched differently:
```bash
uv sync --extra ui
uv run streamlit run app/main.py
```
