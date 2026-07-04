# ROADMAP.md — status tracker

Status only — definitions/target files in `PROJECT.md` §5; full per-step detail in `docs/BUILD_PLAN.md`.
Legend: ☐ todo · ◐ in progress · ☑ done · ✗ dropped · ◔ deprioritized · ⟳ reframed.

> **⟳ STRATEGIC REFRAME (2026-07-04).** Objective pivots from *beat ADP* → **direct-indexing
> personalization** (`docs/REFRAME-2026-07-04.md`, `docs/PERSONALIZATION.md`). Phases 0–2 stay done &
> valid. Below: promotions (5, 8, 10 → core/earlier), reframes (4, 6, 7, 11), **CFR dropped**, **MCTS
> deprioritized**, **NLP + all in-app AI deferred**, and a new **Personalization spine** (bottom).

- ☑ **Setup** — env scaffold (uv + Python 3.12, repo, docs, git). *2026-06-29.*

**Phase 0 — Data foundation** ✅ **COMPLETE** — ☑ 0.2 nflverse *(8 tables, weekly↔snaps 0.24% unmatched)* · ☑ 0.3 PFR *(advanced 2018+, reconciles 0.00%)* · ☑ 0.4 ADP *(FFC 2010–2024; top-150 gsis-matched; PIT ✓; homonym-dedup; Underdog deferred)* · ☑ **0.5 Vegas markets** *(game_lines 2014–25 free; de-vig + implied totals ✓; props key-gated)* · ☑ 0.6 news ingest *(injuries/depth 2014+ native-gsis; news_raw RSS pipe; PIT ✓)* · ☑ 0.7 PIT panel *(weekly+preseason grains; leak-assert ✓; 41-col join)* · ☑ 0.8 validation *(9 hard gates PASS; data_health.json; caught+fixed a 0.4 homonym bug)*
**Phase 1 — Backtest harness** ✅ **COMPLETE** — ☑ **1.1 scoring** *(full-PPR reconstructs nflverse across 57.3k pw @1e-6; K/DST from pbp/game_lines; 9-starter QB/2RB/2WR/TE/FLEX+K+DST; K/DST identity bridge)* · ☑ **1.2 draft sim** *(10×15 snake, ADP+noise opponents, pluggable your_pick_fn, DraftState; ADP-typical + reproducible; adp_asof board)* · ☑ **1.3 walk-forward** *(rank_fn→K drafts→realized optimal-lineup pts, strict PIT; ADP pools 2036 vs worst-first 1458; survivorship LEFT-JOIN; PIT guard trips)* · ☑ **1.4 PAR metric** *(replacement QB10/RB24/WR24/TE12/K10/DST10; PAR ranks elite +818 vs scrub −943; PAR↔exp-wins 0.99)* · ☑ **1.5 significance** *(stationary block-bootstrap CIs; ADP-vs-ADP edge 0 not-sig; worst-first −578/season CI [−714,−438] sig; compare_to_baseline)*
**Phase 2 — Markets & baselines** ✅ **COMPLETE** — ☑ **2.1 VBD** *(value transform; monotonic; reuses 1.4 replacement)* · ☑ **2.2 baseline proj** *(prior-yr ppg, EB-shrunk, aged; on par w/ ADP: −59/season CI[−162,+33])* · ☑ **2.3 props-implied** *(math built+tested; free-data gap → no-op to ADP; activates on a props source)* · ☑ **2.4 ensemble-with-market** *(blend baseline+ADP; grid-fit w=0.25 → 2116 ≥ best component; vs ADP +80 CI[−22,+190] not-sig)*
**Phase 3 — Features (X)** *(unchanged — the engine)* ☐ 3.1 opportunity · ☐ 3.2 efficiency · ☐ 3.3 player · ☐ 3.4 environment · ☐ 3.5 exposures
**Phase 4 — Mean VALUE** *(⟳ consensus-VBD, not edge-seeking)* ☐ 4.1 **consensus-projections ingest** · ☐ 4.2 VBD value board · ☐ 4.3 **rookie model** · ☐ 4.4 calibration *(GBT/age-curve/hier-Bayes demoted to optional — only if they improve calibration, not to beat ADP)*
**Phase 5 — Distributions** *(⟳ PROMOTED to core — powers the risk dial; the one value-side thing we build ourselves; trim to what the dial needs)* ☐ 5.1 quantile · ☐ 5.2 conformal · ☐ 5.3 variance · ☐ 5.4 injury survival · ☐ 5.5 utility
**Phase 6 — Personalization intelligence** *(⟳ from ADP-bias mining: where ADP is soft = how cheaply to indulge a preference)* ☐ 6.1 ADP-alpha panel · ☐ 6.2 regression · ☐ 6.3 softness scorecard
**Phase 7 — Opportunity-adjusted projection** *(⟳ from "causal" — drop counterfactual claims; a feature, not causal inference)* ☐ 7.1 skill÷opportunity decompose · ☐ 7.2 situation multiplier · ☐ 7.3 rookie transport · ☐ 7.4 validate
**Phase 8 — Covariance & rosters** *(⟳ PROMOTED/earlier — tracking error is a covariance quantity; correlation appetite = a user dial)* ☐ 8.1 estimate · ☐ 8.2 shrinkage · ☐ 8.3 copula · ☐ 8.4 roster risk · ☐ 8.5 handcuff option
**Phase 9 — Valuation & draft policy** *(⟳ + constrained optimizer + cost report)* ☐ 9.1 conditional-VBD · ☐ **9.2 constrained optimizer** · ☐ **9.3 cost-of-personalization report** · ☐ 9.4 greedy policy · ☐ 9.5 win-prob objective *(the old "structural-alpha" → the cost report)*
**Phase 10 — Season/playoff sim** *(⟳ PROMOTED/earlier — the tracked benchmark + tail objective)* ☐ 10.1 season engine · ☐ 10.2 playoffs (championship prob) · ☐ 10.3 leverage
**Phase 11 — Draft engine** *(⟳ opponent model = core & Brier-verifiable)* ☐ 11.1 **behavioral opponent model** · ☐ 11.2 **per-pick availability distributions** · ☐ 11.3 realistic mock · ✗ CFR *(dropped — snake draft ≈ perfect-info)* · ◔ MCTS *(deprioritized — unverifiable + live-latency risk)* · ☐ auctions (later) · ☐ self-play RL (roadmap)
**Phase 12 — NLP/news** *(◔ DEFERRED post-MVP — no LLM in the core)* ☐ 12.1 sources · ☐ 12.2 LLM extract · ☐ 12.3 event-study · ☐ 12.4 validate
**Phase 13 — In-season co-pilot** *(the tax-loss-harvesting analog)* ☐ 13.1 re-project · ☐ 13.2 start/sit · ☐ 13.3 waivers/FAAB · ☐ 13.4 streaming · ☐ 13.5 trades
**Phase 14 — App** *(⟳ Streamlit/Gradio MVP first; FastAPI+Next.js later)* ☐ 14.1 **Streamlit/Gradio MVP** (autopilot+co-pilot, constraint-object UI, league sync, cost readout) · ☐ 14.2 personalization tiers · ☐ 14.3 explain · ◔ backend/Next.js/live-draft/widget *(deferred to the "have users" stage)*
**Phase 15 — Multi-format (roadmap)** ☐ 15.1 dynasty · ☐ 15.2 best-ball · ☐ 15.3 DFS

**★ Personalization spine** *(the reframe's new MVP-critical track — cross-phase; spec in `docs/PERSONALIZATION.md`)*
☐ **S1** preference-spec layer (constraint object + UI) · ☐ **S2** constrained optimizer (max consensus-VBD s.t. constraints/archetype, plan around ADP availability) · ☐ **S3** cost-of-personalization report (vs the consensus-VBD-optimal team) · ☐ **S4** behavioral opponent model → availability forecasts · ☐ **S5** per-round risk dial (from Phase 5) · ☐ **S6** adaptive archetypes · ☐ **S7** in-season weekly-edge harvester

**Next up (reframed MVP path):** the personalization spine **on top of Phases 0–2**, not a beat-ADP model.
Concretely: (1) Phase 3 features `X`; (2) **consensus-projections ingest → VBD value** (Phase 4 reframed)
+ a **rookie model**; (3) a **minimal per-player distribution** for the risk dial (trimmed Phase 5); (4)
the **constraint object** + a **constrained greedy optimizer** + a first **cost report** vs the
consensus-VBD-optimal team; (5) a **Streamlit/Gradio** UI. Full MVP scope: `docs/PERSONALIZATION.md` §7.

**Open decisions (reframe §10 — tracked in `PLAN.md`):** real completed-draft data (Sleeper) for the
behavioral model; a **consensus-projections source** (FantasyPros aggregate — free/PIT?); the benchmark
set; the **lockbox** seasons.

**Phase-2 finding (still true — now a feature, not a failure):** consensus ADP is a strong baseline the
naive model can't *significantly* beat — so we **stop trying**, lean on consensus for value, and compete on
personalization + honest cost transparency instead.
