# ROADMAP.md — status tracker

Status only — definitions/target files in `PROJECT.md` §5; full per-step detail in `docs/BUILD_PLAN.md`.
Legend: ☐ todo · ◐ in progress · ☑ done · ✗ dropped · ◔ deprioritized · ⟳ reframed.

> **⟳ STRATEGIC REFRAME (2026-07-04).** Objective pivots from *beat ADP* → **direct-indexing
> personalization** (`docs/REFRAME-2026-07-04.md`, `docs/PERSONALIZATION.md`). Phases 0–2 stay done &
> valid. Below: promotions (5, 8, 10 → core/earlier), reframes (4, 6, 7, 11), **CFR dropped**, **MCTS
> deprioritized**, **NLP + all in-app AI deferred**, and a new **Personalization spine** (bottom).

- ☑ **Setup** — env scaffold (uv + Python 3.12, repo, docs, git). *2026-06-29.*

**Phase 0 — Data foundation** ✅ **COMPLETE** — ☑ 0.2 nflverse *(8 tables, weekly↔snaps 0.24% unmatched)* · ☑ 0.3 PFR *(advanced 2018+, reconciles 0.00%)* · ☑ 0.4 ADP *(FFC 2010–2024; top-150 gsis-matched; PIT ✓; homonym-dedup; Underdog deferred)* · ☑ **0.5 Vegas markets** *(game_lines 2014–25 free; de-vig + implied totals ✓; props key-gated)* · ☑ 0.6 news ingest *(injuries/depth 2014+ native-gsis; news_raw RSS pipe; PIT ✓)* · ☑ 0.7 PIT panel *(weekly+preseason grains; leak-assert ✓; 41-col join)* · ☑ 0.8 validation *(9 hard gates PASS; data_health.json; caught+fixed a 0.4 homonym bug)*
**0.9 — 2025 backfill + nflverse new-release migration** ✅ **DONE** *(2026-07-05)* — ☑ new-release ingest (`stats_player` release; renamed cols conformed) → **weekly 79,250 (2025 REG 18,539+POST 882) / seasonal 8,702**; 2025 reconstructs `fantasy_points_ppr` to 2.4e-6 · ☑ timestamped `depth_charts_ts` (554k rows, dt Aug-25→Mar-26; week-grain table untouched) · ☑ 0.8 validator PASS on extended store. *Root cause: nflverse restructured stats releases post-2024; frozen `nfl_data_py` hits the dead old path. 2025 = **calibration holdout** (`config.CALIBRATION_SEASONS`); draft-backtest lockbox stays 2023+2024 (`DEV_SEASONS`=2014–22); 2025 ADP → Sleeper later.*
**Phase 1 — Backtest harness** ✅ **COMPLETE** — ☑ **1.1 scoring** *(full-PPR reconstructs nflverse across 57.3k pw @1e-6; K/DST from pbp/game_lines; 9-starter QB/2RB/2WR/TE/FLEX+K+DST; K/DST identity bridge)* · ☑ **1.2 draft sim** *(10×15 snake, ADP+noise opponents, pluggable your_pick_fn, DraftState; ADP-typical + reproducible; adp_asof board)* · ☑ **1.3 walk-forward** *(rank_fn→K drafts→realized optimal-lineup pts, strict PIT; ADP pools 2036 vs worst-first 1458; survivorship LEFT-JOIN; PIT guard trips)* · ☑ **1.4 PAR metric** *(replacement QB10/RB24/WR24/TE12/K10/DST10; PAR ranks elite +818 vs scrub −943; PAR↔exp-wins 0.99)* · ☑ **1.5 significance** *(stationary block-bootstrap CIs; ADP-vs-ADP edge 0 not-sig; worst-first −578/season CI [−714,−438] sig; compare_to_baseline)*
**Phase 2 — Markets & baselines** ✅ **COMPLETE** — ☑ **2.1 VBD** *(value transform; monotonic; reuses 1.4 replacement)* · ☑ **2.2 baseline proj** *(prior-yr ppg, EB-shrunk, aged; on par w/ ADP: −59/season CI[−162,+33])* · ☑ **2.3 props-implied** *(math built+tested; free-data gap → no-op to ADP; activates on a props source)* · ☑ **2.4 ensemble-with-market** *(blend baseline+ADP; grid-fit w=0.25 → 2116 ≥ best component; vs ADP +80 CI[−22,+190] not-sig)*
**Phase 3 — Features (X)** ✅ **COMPLETE** *(2026-07-05; the engine)* — ☑ **3.1 opportunity** *(share/WOPR/aDOT/RZ; Hill/Jacobs top)* · ☑ **3.2 efficiency** *(rates + TD-regression flag corr −0.50 next-yr; QB EPA gated)* · ☑ **3.3 player** *(age as-of, draft capital, combine; rookies flagged)* · ☑ **3.4 environment** *(pass rate/pace/implied-total corr +0.86; 32 tm/szn)* · ☑ **3.5 exposures** *(build_exposures: 545×48, winsor-z per pos, PIT-guarded; 100% ADP-board cover; lagged WOPR↔pts +0.46; 2025 holdout builds)*
**Phase 4 — Mean VALUE** *(⟳ consensus-VBD, not edge-seeking)* ✅ **COMPLETE** *(2026-07-05)* — ☑ **4.1 consensus ingest** *(two-track: live FantasyPros scrape re-scored to full-PPR — 528 players, 99% gsis, corr 1.000 vs FP; historical baseline **proxy**; PIT + dispatch)* · ☑ **4.2 VBD value board** *(draft-time replacement from projections; QBs 6→0 in top-15 vs raw; frozen contract player_key·pos·proj_points·source·vbd·pos_rank·overall_rank)* · ☑ **4.3 rookie model** *(per-position ridge on draft capital + landing spot; OOS Spearman +0.62; +76 rookies into proxy board)* · ☑ **4.4 calibration** *(proxy bias 0.60 played / 0.46 incl-DNP; reliability bin-corr 0.99; correction→0.96; **2025 holdout bias 0.58, Spearman +0.57**)* · GBT/age-curve/hier-Bayes/props-shrink **demoted to optional**
**Phase 5 — Distributions** *(⟳ PROMOTED to core — the risk dial; the one value-side thing we build ourselves)* ✅ **COMPLETE** *(2026-07-05; season-total grain)* — ☑ **5.1 quantile** *(per-pos linear QuantReg on the calibrated mean; median slope ≈1.10; band fans with level 3/4 pos)* · ☑ **5.2 conformal** *(CQR; 2025 holdout coverage 70%→73% on the available cohort)* · ☑ **5.3 variance** *(weekly boom/bust + CoV; right-skew confirmed; corr(boom,CoV) −0.37 ⇒ separate axis)* · ☑ **5.4 injury survival** *(logistic discrete-time hazard → Beta-Binomial games-played, ρ=0.33; RB least available)* · ☑ **5.5 utility** *(mean-variance CE = E[Y]−λ·Var[Y] risk dial; assembler writes frozen `player_distributions`)* — **conditional 2025 coverage 76% ≈ 80% target**; unconditional 44% = role/depth attrition (documented limitation). *Deviations (no new deps): statsmodels QuantReg not XGBoost; sklearn hazard not lifelines — future intent to adopt those if the sample justifies. Weekly-grain distribution = future work (folds into Phase-10 sim).*
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

**Next up (reframed MVP path):** ~~0.9 backfill~~ ✅ · ~~Phase 3 features `X`~~ ✅ · ~~Phase 4 consensus-VBD
value + rookie model~~ ✅ · ~~Phase 5 per-player distribution + risk dial~~ ✅ → now (4) the **constraint
object** (`DraftConfig`) + a **constrained greedy optimizer** (max consensus-VBD/CE s.t. constraints, plan
around ADP availability) + a first **cost report** vs the consensus-VBD-optimal team; then (5) a
**Streamlit/Gradio** UI. **Phase 8 covariance** can slot in via the same λ/Var the risk dial exposes. Full
MVP scope: `docs/PERSONALIZATION.md` §7.

**Open decisions (reframe §10 — tracked in `PLAN.md`):** real completed-draft data (Sleeper) for the
behavioral model; a **consensus-projections source** (FantasyPros aggregate — free/PIT?); the benchmark
set. **Resolved:** lockbox = **2023 + 2024** (dev on 2014–2022; `config.DEV_SEASONS`). 2025 excluded (no
weekly rollup / ADP board yet — see `findings.md`).

**Phase-2 finding (still true — now a feature, not a failure):** consensus ADP is a strong baseline the
naive model can't *significantly* beat — so we **stop trying**, lean on consensus for value, and compete on
personalization + honest cost transparency instead.
