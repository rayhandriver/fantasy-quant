# ROADMAP.md — phase status

Legend: ☐ not started · ◐ in progress · ☑ done

- ☑ **Setup** — environment scaffold (uv + Python 3.12, repo structure, docs, git). *2026-06-29.*
- ☐ **Phase 0** — Data pipeline (nfl_data_py / PFR / scraped ADP → DuckDB, PIT) + walk-forward backtest harness.
- ☐ **Phase 1** — Baseline projections + points-above-replacement (PAR) scorer.
- ☐ **Phase 2** — Factor (GBT) projections + age curves + hierarchical priors + calibrated quantiles.
- ☐ **Phase 3** — Player-week covariance (shrinkage) + conditional-VBD + roster floor/ceiling.
- ☐ **Phase 4** — Season + playoff simulation (championship/playoff probability) + handcuff real-option valuation.
- ☐ **Phase 5** — League app (FastAPI + Next.js, personalization, Sleeper live-draft sync).
- ☐ **Phase 6 (stretch)** — MCTS/CFR draft engine + paid data.

**Parallel workstream**
- ☐ **ADP-bias mining** — cross-sectional regression of "ADP alpha" on pre-season features (needs only the
  Phase-0 panel; reuses the intern factor-return regression). Can start right after Phase 0.

Next up: **Phase 0.**
