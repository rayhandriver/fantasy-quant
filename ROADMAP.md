# ROADMAP.md — status tracker

Status only — definitions/target files in `PROJECT.md` §5; full per-step detail in `docs/BUILD_PLAN.md`.
Legend: ☐ todo · ◐ in progress · ☑ done.

- ☑ **Setup** — env scaffold (uv + Python 3.12, repo, docs, git). *2026-06-29.*

**Phase 0 — Data foundation** ✅ **COMPLETE** — ☑ 0.2 nflverse *(8 tables, weekly↔snaps 0.24% unmatched)* · ☑ 0.3 PFR *(advanced 2018+, reconciles 0.00%)* · ☑ 0.4 ADP *(FFC 2010–2024; top-150 gsis-matched; PIT ✓; homonym-dedup; Underdog deferred)* · ☑ **0.5 Vegas markets** *(game_lines 2014–25 free; de-vig + implied totals ✓; props key-gated)* · ☑ 0.6 news ingest *(injuries/depth 2014+ native-gsis; news_raw RSS pipe; PIT ✓)* · ☑ 0.7 PIT panel *(weekly+preseason grains; leak-assert ✓; 41-col join)* · ☑ 0.8 validation *(9 hard gates PASS; data_health.json; caught+fixed a 0.4 homonym bug)*
**Phase 1 — Backtest harness** ✅ **COMPLETE** — ☑ **1.1 scoring** *(full-PPR reconstructs nflverse across 57.3k pw @1e-6; K/DST from pbp/game_lines; 9-starter QB/2RB/2WR/TE/FLEX+K+DST; K/DST identity bridge)* · ☑ **1.2 draft sim** *(10×15 snake, ADP+noise opponents, pluggable your_pick_fn, DraftState; ADP-typical + reproducible; adp_asof board)* · ☑ **1.3 walk-forward** *(rank_fn→K drafts→realized optimal-lineup pts, strict PIT; ADP pools 2036 vs worst-first 1458; survivorship LEFT-JOIN; PIT guard trips)* · ☑ **1.4 PAR metric** *(replacement QB10/RB24/WR24/TE12/K10/DST10; PAR ranks elite +818 vs scrub −943; PAR↔exp-wins 0.99)* · ☑ **1.5 significance** *(stationary block-bootstrap CIs; ADP-vs-ADP edge 0 not-sig; worst-first −578/season CI [−714,−438] sig; compare_to_baseline)*
**Phase 2 — Markets & baselines** ✅ **COMPLETE** — ☑ **2.1 VBD** *(value transform; monotonic; reuses 1.4 replacement)* · ☑ **2.2 baseline proj** *(prior-yr ppg, EB-shrunk, aged; on par w/ ADP: −59/season CI[−162,+33])* · ☑ **2.3 props-implied** *(math built+tested; free-data gap → no-op to ADP; activates on a props source)* · ☑ **2.4 ensemble-with-market** *(blend baseline+ADP; grid-fit w=0.25 → 2116 ≥ best component; vs ADP +80 CI[−22,+190] not-sig)*
**Phase 3 — Features (X)** ☐ 3.1 opportunity · ☐ 3.2 efficiency · ☐ 3.3 player · ☐ 3.4 environment · ☐ 3.5 exposures
**Phase 4 — Mean projections** ☐ 4.1 GBT · ☐ 4.2 age curves · ☐ 4.3 hier-Bayes · ☐ **4.4 props-shrink** · ☐ 4.5 calibration
**Phase 5 — Distributions** ☐ 5.1 quantile · ☐ 5.2 conformal · ☐ 5.3 variance · ☐ 5.4 injury survival · ☐ 5.5 utility
**Phase 6 — ADP-bias mining** ☐ 6.1 panel · ☐ 6.2 regression · ☐ 6.3 scorecard
**Phase 7 — Causal player-in-system [DEEP]** ☐ 7.1 decompose · ☐ 7.2 counterfactual · ☐ 7.3 rookie transport · ☐ 7.4 validate
**Phase 8 — Covariance & rosters** ☐ 8.1 estimate · ☐ 8.2 shrinkage · ☐ 8.3 copula · ☐ 8.4 roster risk · ☐ 8.5 handcuff option
**Phase 9 — Valuation & draft policy** ☐ 9.1 conditional-VBD · ☐ 9.2 structural-alpha · ☐ 9.3 greedy policy · ☐ 9.4 win-prob objective
**Phase 10 — Season/playoff sim** ☐ 10.1 season engine · ☐ 10.2 playoffs · ☐ 10.3 leverage
**Phase 11 — Game-theory engine [DEEP]** ☐ 11.1 opponent model · ☐ 11.2 MCTS · ☐ 11.3 CFR · ☐ 11.4 auction · ☐ 11.5 self-play RL
**Phase 12 — NLP/news [DEEP]** ☐ 12.1 sources · ☐ 12.2 LLM extract · ☐ 12.3 event-study · ☐ 12.4 validate
**Phase 13 — In-season co-pilot** ☐ 13.1 re-project · ☐ 13.2 start/sit · ☐ 13.3 waivers/FAAB · ☐ 13.4 streaming · ☐ 13.5 trades
**Phase 14 — App** ☐ 14.1 backend · ☐ 14.2 personalization · ☐ 14.3 frontend · ☐ 14.4 live-draft · ☐ 14.5 explain · ☐ 14.6 widget · ☐ 14.7 mock draft
**Phase 15 — Multi-format (roadmap)** ☐ 15.1 dynasty · ☐ 15.2 best-ball · ☐ 15.3 DFS

**Next up:** Phase 3.1 (opportunity factors) — begin the PIT exposure matrix `X` that the real
projection models (Phase 4) consume. Phase 6 (ADP-bias) and the cross-cutting workstreams 7 (causal) and
12 (NLP) can start alongside modeling — see `PROJECT.md` §5 sequencing.

**Phase-2 finding:** consensus ADP is a strong baseline — the naive model matches but doesn't
*significantly* beat it. Real edge must come from Phases 3–5. The betting-market baseline (2.3) is
blocked by the free-data gap (props paywalled) — revisit if the project crosses the paid line.
