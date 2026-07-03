# PROJECT.md — the WHAT (goal, scope, decisions, the phase plan)

The single source of truth for **what** we're building and **the plan**. The **HOW/lab-notebook** is
`PLAN.md`; the **WHY/rationale** is `docs/STRATEGY.md`; **status** is `ROADMAP.md`.

## 1. Goal
A **personalized, quant-inspired fantasy football decision engine** — PIT features → distributional
projections → correlation-aware roster construction → a walk-forward backtest that proves an edge —
delivered as a **shareable, season-long co-pilot app for my league** (draft + in-season).

## 2. Scope
**In scope:** data foundation (incl. **Vegas markets**), PIT backtest harness, projections (mean +
distributional), ADP-bias mining, causal player-in-system, covariance & roster construction, valuation &
draft policy, season/playoff simulation, a game-theory draft engine, an NLP/news pipeline, an in-season
co-pilot, and the app.
**Roadmap (deferred):** self-play RL, paid/tracking data, and multi-format (dynasty / best-ball / DFS).

## 3. Settled decisions
- **Product breadth:** **season-long co-pilot** (draft + waivers/FAAB + start-sit + trades). *(2026-06-29)*
- **Backtest metric:** layered — **points-above-replacement (PAR)** baseline first, then **season +
  playoff simulation** (championship/playoff probability) as the north-star. *(2026-06-29)*
- **Vegas betting markets are a FIRST-CLASS data source & projection anchor** — player props, game totals,
  spreads, win totals. A sharper market than ADP; used as features, a de-vig'd projection anchor, and a
  calibration target. *(revised 2026-06-29 — previously declined, now adopted)*
- **Data:** **free / self-scraped** (nfl_data_py, PFR, scraped FFCalculator + Underdog ADP, free odds-API /
  book scraping). Pay only if it becomes a real product. *(2026-06-29)*
- **League baseline:** 10-team, full-PPR, 1-QB redraft.
- **Deepest frontier focus:** NLP/news, the game-theory draft engine, and causal player-in-system. *(2026-06-29)*

## 4. Ground rules
PIT everywhere · walk-forward never in-sample · **beat ADP *and* the betting market + prior baseline**
before shipping · reuse before you write · guard every output · log as you go. (Full text: `CLAUDE.md` §3.)

**Sub-phase gate (workflow):** finish a sub-step → summarize what was accomplished → **ask permission
before starting the next sub-step.** No chaining sub-steps without approval, for the whole project.
*(User instruction, 2026-06-30; full text `CLAUDE.md` §3.7.)*

## 5. The phase plan (AlphaThena methodology: one focused file per aspect)
Each **step → its own module/notebook** (like the intern repo's separate files for wash-sales /
rebalancing / construction). Target module paths are indicative. Phase-level **Done-when** in bold.
Sequencing notes at the end of §5. **Full per-step detail (Goal · Do · Out · Done · Reuse) lives in
`docs/BUILD_PLAN.md`** — this §5 is the index.

### Phase 0 — Data foundation (PIT ingest → DuckDB)
- 0.1 ✅ Environment & repo scaffold
- 0.2 nflverse / nfl_data_py ingest (PBP, weekly, snaps, targets) → `data/sources/nflverse.py`
- 0.3 Pro-Football-Reference season panels → `data/sources/pfr.py`
- 0.4 ADP ingest — FFCalculator historical + Underdog best-ball, PIT snapshots → `data/sources/adp.py`
- 0.5 **Vegas markets ingest** — props / totals / spreads / win totals, de-vig'd → `markets/odds_ingest.py`
- 0.6 News / injury / depth-chart raw ingest (lay the pipe) → `news/ingest.py`
- 0.7 PIT panel / feature-store assembly (the join layer) → `data/panel.py`
- 0.8 Data validation & sanity gates (the hard-gate analog) → `data/validate.py`
- **Done when** any source is queryable PIT from DuckDB and the panel passes its gates.

### Phase 1 — Backtest harness (built before any modeling)
- 1.1 League scoring engine (PPR config) → `backtest/scoring.py`
- 1.2 Draft simulator (ADP-following opponents) → `draft/simulator.py`
- 1.3 Walk-forward harness (method → simulated drafts → season outcomes, strict PIT) → `backtest/walkforward.py`
- 1.4 PAR metric scorer → `backtest/metrics.py`
- 1.5 Significance (block-bootstrap CIs, ADP/market baselines) → `backtest/significance.py`
- **Done when** any ranking method is scored end-to-end on historical drafts, PIT-clean, in one call.

### Phase 2 — Markets & baselines (sharp-market-anchored)
- 2.1 Replacement levels & VBD baseline → `valuation/vbd.py`
- 2.2 Naive opportunity×efficiency baseline → `projections/baseline.py`
- 2.3 **Props-implied projection** (de-vig props → player projection) → `markets/props_projection.py`
- 2.4 **Ensemble-with-market** (blend model + ADP + props, learned weights) → `projections/ensemble.py`
- **Done when** PAR-ranked baselines (incl. the props-implied one) backtest cleanly vs ADP.

### Phase 3 — Feature engineering (exposures `X`)
- 3.1 Opportunity factors (target/snap/route/carry share, air yards, WOPR, RZ) → `features/opportunity.py`
- 3.2 Efficiency factors (YPRR, YAC, catch/TD rate + **TD-regression flags**) → `features/efficiency.py`
- 3.3 Player-intrinsic (age, draft capital, athletic, experience) → `features/player.py`
- 3.4 Team/environment (O-line, QB, PROE/pace, **Vegas implied team total**) → `features/environment.py`
- 3.5 Standardized PIT exposure matrix `X` → `features/exposures.py`
- **Done when** a finite, documented, PIT exposure matrix is produced for any as-of date.

### Phase 4 — Mean projection models
- 4.1 GBT component models per position (XGBoost/LightGBM) → `projections/gbt.py`
- 4.2 Age curves (delta method) → `projections/age_curves.py`
- 4.3 Hierarchical-Bayes thin-sample priors → `projections/hier_bayes.py`
- 4.4 **Props-anchored shrinkage** (shrink model toward de-vig prop means) → `projections/market_shrink.py`
- 4.5 Calibration vs market & realized → `projections/calibration.py`
- **Done when** mean projections beat the Phase-2 baselines *and* hold up against the market OOS.

### Phase 5 — Distributional projections
- 5.1 Quantile regression (P10/P50/P90) → `projections/quantile.py`
- 5.2 Conformal prediction intervals (calibrated) → `projections/conformal.py`
- 5.3 Boom/bust variance (GARCH-like clustering) → `projections/variance.py`
- 5.4 Injury survival/hazard → games-missed distribution → `projections/injury.py`
- 5.5 Expected-utility (floor/ceiling) scoring → `valuation/utility.py`
- **Done when** per-player predictive distributions are calibrated (coverage ≈ nominal).

### Phase 6 — ADP-bias mining (self-contained; can start after Phase 1)
- 6.1 ADP-alpha panel construction → `adp/panel.py`
- 6.2 Cross-sectional ADP-alpha regression (intern factor-return analog) → `adp/regression.py`
- 6.3 Bias scorecard (walk-forward, multiple-testing corrected) → `adp/scorecard.py`
- **Done when** stable, significant ADP biases are identified with CIs (or honestly ruled out).

### Phase 7 — Causal "player-in-system" **[DEEP]**
- 7.1 Skill ÷ opportunity decomposition (intrinsic × situation multiplier) → `causal/decompose.py`
- 7.2 Counterfactual re-projection on situation change (matching / synthetic control) → `causal/counterfactual.py`
- 7.3 College→NFL transport for rookies → `causal/rookie_transport.py`
- 7.4 Held-out transition validation → `causal/validate.py`
- **Done when** counterfactual re-projections beat naive carry-over on held-out player moves.

### Phase 8 — Covariance & roster construction
- 8.1 Player-week covariance estimation → `covariance/estimate.py`
- 8.2 Structured correlations + shrinkage (Ledoit-Wolf/QIS) → `covariance/shrinkage.py`
- 8.3 Copulas for handcuff tail-dependence → `covariance/copula.py`
- 8.4 Roster floor/ceiling via `(w)ᵀΣ(w)` → `valuation/roster_risk.py`
- 8.5 Handcuff real-option valuation → `valuation/handcuff.py`
- **Done when** correlation-aware rosters beat naive-BPA rosters OOS.

### Phase 9 — Valuation & draft policy
- 9.1 Conditional-VBD (expected best-available at next pick) → `valuation/conditional_vbd.py`
- 9.2 Structural-alpha backtest (the "tax-alpha" number) → `valuation/structural_alpha.py`
- 9.3 Greedy draft policy → `draft/greedy_policy.py`
- 9.4 Win-probability / CVaR objective → `valuation/objective.py`
- **Done when** the greedy conditional-VBD policy beats ADP drafting OOS.

### Phase 10 — Season & playoff simulation (north-star metric)
- 10.1 Monte-Carlo season engine (schedule, byes, injuries) → `simulation/season.py`
- 10.2 Playoff bracket → championship/playoff probability → `simulation/playoffs.py`
- 10.3 Leverage-by-game-state (variance as a lever) → `simulation/leverage.py`
- **Done when** title-probability ranking is stable and beats ADP + PAR OOS.

### Phase 11 — Game-theory draft engine **[DEEP]**
- 11.1 Live opponent modeling (Bayesian board inference) → `draft/opponent_model.py`
- 11.2 MCTS draft engine (top-K, rollouts, value caching) → `draft/mcts.py`
- 11.3 CFR / exploitative refinement → `draft/cfr.py`
- 11.4 Auction-draft support (nomination, budget knapsack) → `draft/auction.py`
- 11.5 Self-play RL (frontier) → `draft/selfplay.py`
- **Done when** the engine beats the greedy policy (Phase 9) vs realistic opponents OOS.

### Phase 12 — NLP / live-news pipeline **[DEEP]**
- 12.1 Source scrapers/streams (beat writers, injury, depth charts, inactives) → `news/sources.py`
- 12.2 LLM extraction → structured, timestamped features → `news/extract.py`
- 12.3 Event-study: market reaction & exploitable lag → `news/event_study.py`
- 12.4 Signal validation on the walk-forward → `news/validate.py`
- **Done when** an extracted news signal demonstrably improves projections/decisions OOS.

### Phase 13 — In-season co-pilot **[CORE — season breadth]**
- 13.1 Weekly re-projection (state-space update + news) → `inseason/reproject.py`
- 13.2 Start/sit lineup optimizer (win-prob objective) → `inseason/lineup.py`
- 13.3 Waivers/FAAB bandit + bidding → `inseason/waivers.py`
- 13.4 Streaming bandit (QB/TE/DST) → `inseason/streaming.py`
- 13.5 Trade finder (surplus, mutually-beneficial, buy-low/sell-high) → `inseason/trades.py`
- **Done when** each in-season decision tool beats a naive heuristic on backtested seasons.

### Phase 14 — The app
- 14.1 FastAPI backend + DuckDB/Postgres → `app/backend/`
- 14.2 Personalization layer (archetypes, factor weights, draft style, anchors) → `app/backend/personalization.py`
- 14.3 Next.js + TypeScript frontend → `app/frontend/`
- 14.4 Sleeper live-draft sync (Redis + WebSockets) → `app/backend/live_draft.py`
- 14.5 Explainability ("why this pick") + preference learning → `app/backend/explain.py`
- 14.6 Ambient widget (browser ext / Android bubble) → `app/widget/`
- 14.7 Mock-draft simulator (also feeds Phase-11 opponent models) → `app/backend/mock_draft.py`
- **Done when** my league can run a live draft + manage the season through it with personalized recs.

### Phase 15 — Multi-format (roadmap)
- 15.1 Dynasty/keeper multi-year asset pricing · 15.2 Best-ball · 15.3 DFS GPP (ownership/leverage) → `formats/`

**Sequencing:** 0 → 1 gate everything. Phase 6 (ADP-bias) can run right after Phase 1. Phases 7 (causal)
and 12 (NLP) are **cross-cutting workstreams** — start them alongside, not strictly after, the modeling
phases. The app (14) consumes whatever modeling exists; a thin v1 can wrap Phases 1–2 early.

## 6. Definition of done (v1)
A league-usable **season-long co-pilot** whose recommendations come from a model that has **demonstrably
beaten consensus ADP *and* the betting market (and a simple baseline) on a PIT walk-forward, with
bootstrap CIs** — plus an honest scorecard of where it does and doesn't add edge.
