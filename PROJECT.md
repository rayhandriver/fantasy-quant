# PROJECT.md — the WHAT

The goal, scope, ground rules, and phased milestones. **This file is the WHAT.** The HOW lives in
`PLAN.md` (yours to manage). Rationale and parallels are in `docs/STRATEGY.md`.

## 1. Goal in one sentence
Build a **personalized, quant-inspired fantasy football draft model** — PIT features → distributional
projections → correlation-aware roster construction → a walk-forward backtest that proves an edge — and
wrap it in a **shareable web app for my league**.

## 2. Scope
**In scope (model core first):** data pipeline, PIT backtest harness, projections (mean + quantiles),
player covariance, VBD / conditional-VBD, structural-alpha + ADP-bias analysis, draft simulator, and a
lean league app on top.
**Deferred:** MCTS/CFR draft engine and any paid data sources — only if it crosses into a real product.

## 3. Settled decisions (2026-06-29)
- **Product target:** shareable app for my league (model-core-first inside it).
- **Backtest metric:** layered — **points-above-replacement** baseline first, then **season + playoff
  simulation** (championship/playoff probability) as the north-star.
- **Data:** **free / self-scraped** (nfl_data_py, Pro-Football-Reference, scraped FFCalculator + Underdog
  ADP). Pay only if it becomes a real product.
- **League baseline:** 10-team, full-PPR, 1-QB redraft.

## 4. Ground rules
PIT everywhere · walk-forward never in-sample · beat ADP + the prior baseline before shipping · reuse
before you write · guard every output · log decisions/findings/glossary as you go. (Full text: `CLAUDE.md`.)

## 5. Phases & "done when" (detail in docs/STRATEGY.md Part 7)
- **Phase 0 — Data pipeline + PIT backtest harness.** *Done when* any ranking method can be scored
  end-to-end on historical drafts, PIT-clean, with one call.
- **Phase 1 — Baseline projections + PAR metric.** *Done when* a documented baseline + VBD/points-above-
  replacement scorer backtests cleanly and is comparable to ADP.
- **Phase 2 — Factor projections + distributions.** GBT component models, age curves (delta method),
  hierarchical priors for thin samples, calibrated P10/P50/P90. *Done when* it beats Phase 1 OOS.
- **Phase 3 — Covariance + roster construction.** Shrunk player-week covariance, conditional-VBD,
  floor/ceiling via `(w)ᵀΣ(w)`. *Done when* correlation-aware rosters beat naive-BPA OOS.
- **Phase 4 — Season + playoff simulation (north-star).** Monte-Carlo season/bracket → title probability;
  handcuff real-option valuation. *Done when* title-prob ranking is stable and beats ADP + PAR OOS.
- **Phase 5 — League app.** FastAPI + Next.js, personalization layer, Sleeper live-draft sync. *Done when*
  my league can run a live draft through it with personalized recommendations.
- **Phase 6 (stretch) — MCTS/CFR engine + paid data.** Only after everything above is solid.

### Early self-contained workstream: ADP-bias mining
Can run in parallel with Phase 1–2 (it only needs the Phase-0 panel). A cross-sectional regression of
"ADP alpha" on pre-season features — *identical machinery to the intern repo's factor-return regression*.
See `docs/STRATEGY.md` Part 13. High value, low coupling.

## 6. Definition of done (whole project, v1)
A league-usable app whose recommendations come from a model that has **demonstrably beaten consensus ADP
(and a simple baseline) on a PIT walk-forward, with bootstrap CIs** — plus an honest scorecard of where it
does and doesn't add edge.
