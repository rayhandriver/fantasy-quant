# PROJECT.md — the WHAT (goal, scope, decisions, the phase plan)

The single source of truth for **what** we're building and **the plan**. The **HOW/lab-notebook** is
`PLAN.md`; the **WHY/rationale** is `docs/STRATEGY.md` (see its **Part 0 reframe**); **status** is
`ROADMAP.md`; the **personalization design contract** is `docs/PERSONALIZATION.md`.

> **⟳ STRATEGIC REFRAME (2026-07-04) — supersedes the original objective.** The goal pivots from *"beat
> ADP"* to a **direct-indexing personalization engine**: build the best team the user wants, and honestly
> **price what each preference costs** vs the consensus-optimal team. Team strength is now a **tracked
> benchmark**, not the objective. Rationale + full spec: `docs/REFRAME-2026-07-04.md` and
> `docs/PERSONALIZATION.md`. **Phases 0–2 stay valid.** §1/§2/§6 below reflect the reframe.

## 1. Goal
A **personalized, quant-inspired fantasy football decision engine** that builds each user a
fully-optimized roster from their own constraints and archetype, and **honestly prices the cost of every
personalization decision** against the consensus-optimal team — delivered as a **shareable, season-long
co-pilot app for my league** (draft + in-season). Value = **consensus projections → VBD**; availability =
**ADP + a behavioral opponent model**; risk = **our own distributional layer** (the three signal layers;
see `docs/PERSONALIZATION.md` §2). Team strength is a **benchmark we track within a tolerance budget**, not
a fight we try to win.

## 2. Scope
**In scope (reframed):** data foundation (incl. **Vegas markets** + a new **consensus-projections
ingest** for the value signal); PIT backtest harness; a **preference-specification layer** (the constraint
object); a **constrained draft optimizer**; the **cost-of-personalization report**; a **behavioral
opponent model** + **per-pick availability** forecasts; a **trimmed distributional layer** for the risk
dial; covariance & roster construction; season/playoff simulation (championship probability = the tracked
benchmark + tail objective); an in-season co-pilot; and the **app (Streamlit/Gradio MVP first)**.
**Reframed roles:** projections lean on **consensus (VBD)**, not an edge-seeking model (+ an explicit
**rookie model**); ADP-bias mining → **personalization intelligence**; causal → **opportunity-adjusted**
projection (no counterfactual claims); opponent modeling → **core, Brier-verifiable**.
**Deferred / roadmap:** **all in-app AI/LLM features** (post-MVP; AI on the edges, deterministic core);
CFR (**dropped** — a snake draft is near-perfect-information); heavy live MCTS (**deprioritized**);
self-play RL; paid/tracking data; auctions; multi-format (dynasty / best-ball / DFS).

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
- **⟳ Direct-indexing reframe:** personalization is the objective; team strength is a **tracked
  benchmark**, not a fight to win. "Beat ADP" demoted to optional. *(2026-07-04)*
- **Three signal layers:** value = **consensus projections → VBD**; availability = **ADP + behavioral
  model**; variance = **our own distributional layer**. Never one "ADP" input. *(2026-07-04)*
- **Calibration > edge:** projections must be **well-calibrated**, not ADP-beating. *(2026-07-04)*
- **AI deferred:** no LLM in the core; all in-app AI is post-MVP (AI on the edges, deterministic core). *(2026-07-04)*
- **UI = Streamlit/Gradio first**, not FastAPI+Next.js (validate the idea before a production frontend). *(2026-07-04)*
- **Draft engine:** **drop CFR**, **deprioritize live MCTS**; the opponent model is core & Brier-verifiable. *(2026-07-04)*
- **Own the contracts:** the human owns the constraint object + projection output shape; delegate interiors. *(2026-07-04)*

## 4. Ground rules
PIT everywhere · walk-forward never in-sample · **calibration > edge** (well-calibrated, not ADP-beating) ·
**track the benchmark, price the cost** · keep a true **lockbox** (freeze recent seasons, evaluate once) ·
**no LLM in the core** · **own the contracts** · reuse before you write · guard every output · log as you
go. (Full text: `CLAUDE.md` §3; reframe: `docs/REFRAME-2026-07-04.md`.)

**Sub-phase gate (workflow):** finish a sub-step → summarize what was accomplished → **ask permission
before starting the next sub-step.** No chaining sub-steps without approval, for the whole project.
*(User instruction, 2026-06-30; full text `CLAUDE.md` §3.7.)*

## 5. The phase plan (AlphaThena methodology: one focused file per aspect)
Each **step → its own module/notebook** (like the intern repo's separate files for wash-sales /
rebalancing / construction). Target module paths are indicative. Phase-level **Done-when** in bold.
Sequencing notes at the end of §5. **Full per-step detail (Goal · Do · Out · Done · Reuse) lives in
`docs/BUILD_PLAN.md`** — this §5 is the index.

> **⟳ Reframe impact on the phases (2026-07-04; details in `ROADMAP.md` + `docs/BUILD_PLAN.md`):**
> **Promoted to core/earlier:** 5 (distributions — the risk dial), 8 (covariance — tracking error), 10
> (season sim — the tracked benchmark). **Reframed:** 4 → **consensus-VBD value + rookie model** (not an
> edge-seeking projection); 6 → **personalization intelligence** (where ADP is soft = how cheaply to
> indulge); 7 → **opportunity-adjusted** (drop causal claims); 11 → **core opponent model** (Brier-scored),
> **CFR dropped**, **MCTS deprioritized**. **New (the personalization spine, `docs/PERSONALIZATION.md`):**
> preference-spec layer · constrained optimizer · cost-of-personalization report · behavioral opponent
> model · per-pick availability · risk dial. **Deferred:** 12 (NLP) + all in-app AI. The app (14) starts
> as a **Streamlit/Gradio MVP**.

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

### Phase 3 — Feature engineering (exposures `X`) ✅ **COMPLETE** *(2026-07-05)*
- 3.1 Opportunity factors (target/snap/route/carry share, air yards, WOPR, RZ) → `features/opportunity.py`
- 3.2 Efficiency factors (YPRR, YAC, catch/TD rate + **TD-regression flags**) → `features/efficiency.py`
- 3.3 Player-intrinsic (age, draft capital, athletic, experience) → `features/player.py`
- 3.4 Team/environment (O-line, QB, PROE/pace, **Vegas implied team total**) → `features/environment.py`
- 3.5 Standardized PIT exposure matrix `X` → `features/exposures.py`
- **Done when** a finite, documented, PIT exposure matrix is produced for any as-of date.

### Phase 4 — Mean VALUE *(⟳ reframed: consensus-VBD, not edge-seeking)* ✅ **COMPLETE** *(2026-07-05)*
- 4.1 **Consensus-projections ingest** (two-track: live FantasyPros scrape + historical baseline proxy) → `projections/consensus.py`
- 4.2 **VBD value board** (consensus → draft-time VBD → ranks; the frozen contract) → `valuation/value_board.py`
- 4.3 **Rookie model** (draft capital + landing spot, per-position ridge) → `projections/rookie.py`
- 4.4 **Calibration** (bias ratio, reliability, correction; 2025 holdout) → `projections/calibration.py`
- **Done when** the value signal is **well-calibrated** (bias ≈ 1 after correction, monotone reliability, holdout rank-fidelity) — *not* when it beats ADP.
- *Optional/demoted (only if they improve calibration):* GBT `gbt.py` · age curves `age_curves.py` · hier-Bayes `hier_bayes.py` · props-shrink `market_shrink.py`.

### Phase 5 — Distributional projections ✅ **COMPLETE** *(2026-07-05)*
- 5.1 ✅ Quantile regression (P10/P50/P90) → `projections/quantile.py` *(per-pos linear `QuantReg` on the calibrated mean; median slope ≈1.10; band fans with level 3/4 pos)*
- 5.2 ✅ Conformal prediction intervals (CQR, calibrated) → `projections/conformal.py` *(2025 holdout coverage 70%→73% on the available cohort)*
- 5.3 ✅ Boom/bust variance → `projections/variance.py` *(weekly CoV + boom/bust rates; corr(boom,CoV) −0.37 ⇒ separate axis)*
- 5.4 ✅ Injury availability: discrete-time hazard → games-played dist → `projections/injury.py` *(logistic hazard + Beta-Binomial ρ=0.33; RB least available)*
- 5.5 ✅ Expected-utility (risk dial) scoring → `valuation/utility.py` *(mean-variance CE = E[Y]−λ·Var[Y]); assembler `projections/distribution.py` writes the frozen `player_distributions` contract*
- **Done when** per-player predictive distributions are calibrated (coverage ≈ nominal): **conditional (available cohort) 2025 coverage 76% ≈ 80% target.** Unconditional full-board 44% is **role/depth attrition** the injury-only model doesn't capture — a documented limitation.
- **Grain:** season-total only (what the draft dial/optimizer consume). **Weekly-grain distribution = future work** (start/sit, folds into the Phase-10 season sim).
- **Method notes:** used statsmodels `QuantReg` (5.1) + scikit-learn logistic hazard (5.4), *not* XGBoost/`lifelines`, per the small-sample no-overfit rule (no new deps). **Future intent:** adopt **XGBoost quantile** / **`lifelines` survival** if the sample or residual signal justifies it.

### ★ Personalization spine — the direct-indexing MVP ✅ **COMPLETE (S1–S3 + S5)** *(2026-07-07)*
*Cross-phase MVP track (spec: `docs/PERSONALIZATION.md`); built on Phases 0–5, straight-through. On DEV 2022; season is a parameter (2026 board drops in when scraped).*
- S1 ✅ Constraint object → `draft/config.py` *(`DraftConfig`: league · archetype (state-aware master dial) · never/must(+reach budget) · tilts · risk λ; validated; `benchmark()` + leave-one-out helpers. MVP subset of §3.)*
- S2 ✅ Constrained greedy optimizer → `draft/optimizer.py` *(over the Phase-1.2 simulator; `base_value` = risk-adjusted value-over-replacement (CE − replacement); tilts→priority; must-draft = availability planning, no overreach.)*
- S3 ✅ Cost-of-personalization report → `valuation/cost_report.py` *(personalized vs `benchmark()` on the same seeds → headline pts/% + per-preference **leave-one-out** + must-player secured fraction. Relative/directional per §7.)*
- S5 ✅ Risk dial **wired in** *(Phase-5 λ/CE flows through `base_value`; UI exposes it. Phase-8 covariance will swap per-player Var for portfolio Var under the same λ.)*
- UI ✅ Streamlit **Autopilot + Co-pilot** → `app/streamlit_app.py` *(`uv run streamlit run …`; personalized board beside the pure-value baseline + cost readout; deterministic, no LLM. `ui` extra.)*
- **Done when** you can draft any 2022 seat, express preferences, and get a personalized board **and** an honest relative cost vs the value-optimal team, from a Python UI — **met.** 137 tests, ruff clean; 3 spine step scripts green; app verified via `AppTest`.
- **Deferred (not MVP):** S4 behavioral opponent model *(MVP = ADP+noise)* · S6 adaptive archetypes · S7 in-season harvester · a **walk-forward realized-PAR validation** of the cost · scraping a **2026 ADP** board to go live.

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

## 6. Definition of done (reframed 2026-07-04)
**v1:** a league-usable, season-long **personalization co-pilot** that (a) produces **well-calibrated**
projections and risk dials (reliability diagrams, interval coverage), (b) accurately predicts **draft
availability** (Brier-scored over real picks), and (c) honestly **prices the cost of each personalization
decision** against one or more benchmarks (lead with relative/directional cost). "Beat ADP" is an optional
secondary curiosity, not a requirement.

**MVP (near-term, needs none of Phases 11–15, no in-app AI):** you can sit down for a real draft this
season, express your preferences, and get personalized pick recommendations with an honest relative cost
readout — from a **Python (Streamlit/Gradio) UI, with no LLM in the loop**. (Full MVP scope:
`docs/PERSONALIZATION.md` §7.)
