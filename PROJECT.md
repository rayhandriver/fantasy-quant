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
- **Phase 16 (situation-change beta lab) is a separate, non-core research track** — walled off from the
  frozen post-lockbox stack, never wired into the optimizer/VBD/cost report. *(2026-07-19)*
- **Competition-change signal is dual-sourced** (roster-turnover-derived **and** depth-chart-derived,
  compared side by side) rather than assumed to fail like Phase 12.3's depth-chart signal. *(2026-07-19)*
- **The coaching/playcaller history table is Claude-drafted via web research, user-reviewed before use** —
  no free source exists and playcalling duty is often ambiguous. *(2026-07-19)*
- **The scheme-fingerprint/transport hypothesis ships descriptive-only, explicitly labeled unvalidated** —
  the sample (~20–30 DEV transport events) is too thin for the FDR-gated bar the rest of the mining uses.
  *(2026-07-19)*
- **Phase 16 includes populating this year's (2026) real situation-change events**, not just the historical
  mining methodology, so the beta tab is immediately useful for this year's draft. *(2026-07-19)*

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
- UI ✅ Streamlit, **Phase 14.1 / Session K1** → **`app/main.py`** *(`uv sync --extra ui && uv run streamlit run app/main.py`)*. Four tabs on the **live** board: **Settings** (17.3 `LeagueSettings`, platform-agnostic, with the `lockbox_validated()` banner) · **Board** (the T27 value chain + the `why` arithmetic) · **Draft room** (any k of n seats against the calibrated 16.15 room, 14.J/16.17) · **Cost** (personalized roster beside the pure-value benchmark + the per-preference leave-one-out). Deterministic, no LLM. **Renders `draft/session.py`, which `steps/mock_draft.py` also renders — one computation, two renderers, so the app and the CLI cannot disagree.** The older `src/fantasy_quant/app/streamlit_app.py` was retired (deleted) here.
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

### Phase 10 — Season & playoff simulation (north-star metric) ✅ **COMPLETE** *(2026-07-09)*
- 10.1 ✅ Monte-Carlo season engine (schedule, byes, injuries) → `simulation/season.py` *(+ the weekly
  grain the Phase-5 deferral owed: `simulation/weekly.py` — top-down disaggregation, Phase-8 Σ imposed
  board-wide, Dirichlet(1/CoV²) week shares; sim league spread ≡ realized, ratio 1.02)*
- 10.2 ✅ Playoff bracket → championship/playoff probability → `simulation/playoffs.py`
- 10.3 ✅ Leverage-by-game-state (variance as a lever) → `simulation/leverage.py`
- **Done when** *(⟳ pipeline 2026-07-09: calibrated championship probs on DEV)* — **MET**: on 1,800
  DEV team-seasons, title Brier 0.0878 < 0.090 baseline with on-diagonal reliability, playoff 0.2302
  < 0.240; ranking stable across draws (0.975/0.949). *(The old "beats ADP + PAR OOS" clause retired with
  the reframe — the sim is the benchmark/objective layer, not an edge claim.)*

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

*Decision-support surfacing + consolidated UI (added 2026-07-23; **all app/UI work lands here — "app strictly
last"**). Every UI/tab/readout deferred out of the engine phases consolidates into the app: the Phase-16.6 Beta
Lab tab, the 16.12 availability/reach-risk readout + `P(available at your pick)`, the 16.15 opponent-personality
selector, the 17.3 custom-league-settings form, and the `docs/PLAYER-VIEW.md` cards/deep-pages. Plus five
broadly-useful **surfacing readouts (E–I)** that read already-frozen machinery (near-zero modeling risk):*
- 14.E **Tier-cliff / scarcity board** — surface positional value cliffs ("after these 3 RBs, a drop"); reuses
  the `positional_cliff` already built for 9.1. Helps novices see *why* to draft a position now.
- 14.F **Roster-construction risk readout** — a live "your team" panel: bye-week clustering, team
  over-concentration, handcuff gaps; reuses `valuation/roster_risk.py` + the 8.5 handcuff engine.
- 14.G **Uncertainty-aware board** — ranges not false-precise ranks ("these three are a coin-flip"); reuses the
  Phase-5 distributions + the PLAYER-VIEW confidence flags.
- 14.H **Playoff-week SOS lens** — each player's weeks-15–17 matchup difficulty, keyed to the league's playoff
  weeks (`LeagueFormat`); descriptive/face-validity (a schedule lens, like 16.4). Lands in the Next.js frontend.
- 14.I **Draft grade / team report** — after any mock, grade the roster vs the room (projected wins, title odds,
  positional holes, biggest reach & best value) via the Phase-10 sim + cost report. Closes the learning loop.
- **Done-when (surfacing):** E/F/G/I render in the Streamlit MVP (14.1) reading frozen outputs, unit-tested for
  correct wiring (no new modeling gate); H lands in the frontend (14.3); D's live run-detection alert (16.16)
  surfaces in the live-draft view (14.4).

### Phase 17 — League-Format Fidelity & Custom Settings *(new 2026-07-23; makes the engine give **correct**
advice for ANY league, not just 10-team full-PPR 1-QB — a broad, all-users correctness track, not a personal
preference)*
*Goal: the engine today hard-codes the vanilla format (`RosterSlots.qb=1`, `flex=1`, `season.py` raises
`NotImplementedError` for multi-flex), so it gives **silently wrong** advice for superflex / custom leagues.
This track generalizes the format contracts so any user's league maps on cleanly. **Not a modeling change to
the frozen stack** — it's a config generalization; the lockbox-validated 10-team full-PPR 1-QB result stays
valid, and non-default formats are supported but **labeled "not lockbox-validated"** (the eval was one format).
IDP (individual defensive players) is **flagged future-work** — nflverse IDP data is too thin to project
honestly.*
- 17.1 Roster + lineup generalization — generalize `RosterSlots` (arbitrary `qb` count, multiple flex,
  superflex/OP slot, no-kicker, bench/team-count) and the vectorized optimal-lineup solver in
  `simulation/season.py` (remove the single-FLEX `NotImplementedError`); recompute VBD replacement levels per
  format so the value board is correct (superflex → QBs rise into the top tier). → `draft/simulator.py`
  (`RosterSlots`), `simulation/season.py`, `backtest/metrics.py` (replacement).
- 17.2 Custom scoring generalization — extend `RuleSet` to arbitrary per-stat point values (TE-premium, custom
  passing-TD, PPR variants, bonuses) with standard/half/full presets; re-score consensus + realized through the
  chosen `RuleSet` (already partly supported — `rec` is configurable; extend to the full stat map). →
  `backtest/scoring.py`.
- 17.3 Generic league-settings input contract — a **platform-agnostic** settings object + parser/validator that
  builds `RuleSet` + `RosterSlots` + `LeagueFormat` from arbitrary user input (presets **or** full custom: add
  superflex/multi-flex, drop the kicker, change team/bench count, custom scoring). The contract the Phase-14
  app form binds to; NOT tied to any platform (ESPN/Yahoo/Sleeper users all hand-enter). → `draft/config.py`
  (a `LeagueSettings` builder). *(Optional future: a Sleeper free-API auto-import convenience on top — secondary,
  never the primary path.)*
- 17.4 Keeper support — remove kept players from the draftable pool and **re-inflate everyone's effective ADP**;
  price a keeper's cost as the forfeited draft pick. → `draft/simulator.py` (pool init), `adp/` (effective-ADP
  recompute). *(The nearer-term subset of the deferred Phase-15.1 dynasty.)*
- **Done when** a superflex mock drafts QBs into the early rounds (17.1), the lineup solver matches a
  brute-force optimum on random multi-flex rosters (17.1), a custom-scoring board re-ranks sensibly (17.2), the
  settings contract round-trips presets + a fully-custom league (17.3), and a keeper league removes kept players
  + shifts ADP (17.4) — each with face-validity / correctness unit tests; non-default formats labeled
  **not-lockbox-validated**.

### Phase 15 — Multi-format (roadmap)
- 15.1 Dynasty/keeper multi-year asset pricing · 15.2 Best-ball · 15.3 DFS GPP (ownership/leverage) → `formats/`

### ★ Phase 16 — Situation-Change Beta Lab *(new 2026-07-19; non-core, exploratory — a separate research
track, not a change to the frozen stack)*
*Goal: test whether ADP misprices offseason "changed situation" events (team change, QB change, teammate
competition change, coaching/scheme change) that consensus year after year seems to over/under-react to —
and surface any real signal (or an honest non-signal) on a walled-off, read-only tab, never wired into the
optimizer/VBD/cost report. Distinct from Phase 7 (which tested a blunt team-fixed-effect re-projection and
was dropped) — this asks whether **ADP itself**, not the projection, is mispriced by these events, using
Phase 6's already-validated ADP-alpha mining methodology extended with new features.*
- 16.1 Team-change + new-starting-QB ADP-alpha extension — add `team_changed`, `new_starting_qb` (>50%
  team-attempts threshold) to the Phase 6.1 panel; refit 6.2's regression + 6.3's BH-FDR scorecard,
  DEV-only, same season-block-bootstrap discipline → `adp/panel.py`, `adp/regression.py`.
- 16.2 Competition-change signal, **dual-sourced** — build both a **roster-turnover-derived** feature
  (via `draft_picks` + team roster deltas year-over-year, meaningful-prior-usage threshold) and a
  **depth-chart-derived** one (reusing `depth_charts_ts`, the same source Phase 12.3 already found doesn't
  separate for in-season promo/demo) side by side in the same mining framework, to see empirically whether
  roster-turnover avoids that null result rather than assuming it does.
- 16.3 Playcaller/coaching history table — Claude-drafted via web research (HC/OC · team · seasons ·
  playcaller y/n, ambiguous cases flagged), **delivered for user review/correction before use**. Feeds
  16.4 only, not the FDR-gated ADP-alpha regression (sample too thin for that bar).
- 16.4 Scheme fingerprint + transport — per-playcaller-regime role-share aggregates (WR1/2/3 target share,
  RB carry share, TE target/route share, team pass rate/PROE, RZ split), reusing Phase 3.1/3.4 features; a
  transport function reweighting a new team's personnel by an incoming playcaller's historical fingerprint.
  **Shipped as descriptive/labeled-hypothesis, not a backtested claim** (thin sample, ~20–30 clean DEV
  transport events) — no formal statistical gate, unlike 16.1/16.2.
- 16.5 2026 live situation-change board — identify this year's actual offseason events (trades, FA
  signings, coaching hires), hand-researched like 16.3, so the tab has real current content for this
  year's draft, not just a historical proof of concept.
- 16.6 Beta Lab tab → `app/streamlit_app.py` — a clearly-labeled, **read-only** tab (no optimizer/VBD/
  cost-report coupling) showing 2026-flagged players, whichever of 16.1/16.2's signals survived their gate
  (with CI + sign-stability, same as DURABILITY), and the 16.4 fingerprints framed as hypotheses.

*Availability-side track (16.7–16.12; added 2026-07-23, user request — folded into Phase 16). The 16.1–16.6
track asks "does a changed situation make a player **out-earn** his ADP (realized-points alpha)?"; this track
asks the sibling question "does narrative/situation make a player **drafted earlier** than his ADP (draft-slot
drift)?" — the availability signal, not the value signal. It fixes the concrete UX failure the user named: a
target falls to you in 10 mock drafts, then gets sniped in the real draft because many drafters share the
read. It extends the **availability/opponent model** (`draft/opponent_model.py`, `draft/availability.py`,
`draft/simulator.py`), which is **already outside the value-stack lockbox** (it predicts draft flow, not
player value, and is walk-forward-scored) — so none of this spends or contaminates the frozen value eval.
Validation bar (user, 2026-07-23): **walk-forward + an own held-out metric** on what is backtestable; the
momentum signal is validated **live on 2026 only** (see 16.11's data constraint).*
- 16.7 Draft-slot-drift panel & target — the availability twin of 16.1's VOR-alpha panel. Build
  `drift = actual_draft_slot − preseason_ADP` per (player, draft) from the **Sleeper human corpus** (149
  human drafts, 2017–2020, real pick-by-pick slots via `sleeper_draft_picks`) joined to the FFC/`sleeper_human`
  ADP board, aggregated to a per-player-season mean drift (the backtestable target). → `adp/drift_panel.py`
  (new), reusing `adp/panel.py` join machinery. **Data note:** this is the only historical draft-slot ground
  truth we have (2017–2020); documented as thin.
- 16.8 Drift feature model (market-derived, backtestable) — fit `drift ~ features` walk-forward, season-block
  bootstrap, same discipline as 6.2. Features: **VBD-ADP gap** (`value_board.overall_rank` − ADP rank — "the
  projections say he's underpriced," a free ECR proxy since we store projections, not FantasyPros' expert
  *rank*), **source divergence** (FFC public ADP vs `sleeper_human` sharper ADP), and the **situation-change
  flags** reused from 16.1/16.2. Own held-out metric: drift MAE / Spearman vs a naive `drift=0` baseline →
  an honest predicts-or-doesn't verdict. → `adp/drift_model.py` (new).
- 16.9 Correlated per-draft narrative shock (simulator realism) — the user's key insight: independent
  per-opponent sampling washes out clustering, so a hyped player *always* falls. Draw **one shared hype shock
  per simulated draft**, applied to all AI opponents (a `hype` term in the conditional-logit
  `candidate_utility` / a survival-mean shift), so hyped players go early **consistently within a draft**.
  Done-bar: the simulator reproduces the **realized cross-draft dispersion** of a player's draft slot in the
  Sleeper corpus, and availability Brier does not regress vs the current 11.2 default. → extend
  `draft/simulator.py`, `draft/opponent_model.py`, `draft/availability.py`.
- 16.10 Curated hype-board override — `reference/hype_board.csv` (`player_key · pick_delta · note · source`),
  Claude-drafted via web research + **user-reviewed before use** (same contract as the 16.3 playcaller table),
  the qualitative residual pure market signals miss (the McConkey case). Applied as a bias on the opponent
  utility / survival on top of the quantitative signals, live-season only, PIT-stamped. → `adp/hype_board.py`
  (loader + wiring).
- 16.11 Live 2026 momentum signal (forward-only) — ADP **velocity** = slope of a player's ADP across the
  Stage-0 2026 snapshot **series** (`adp_snapshots`, banked weekly since 2026-07-09). **Hard data constraint:
  NOT backtestable** — FFC history is one ~Sep-1 board per season, so there is no historical intra-season ADP
  series; momentum is validated **live on 2026 only** as snapshots accrue (documented, like 16.4's descriptive
  bar). → `adp/momentum.py` reading the snapshot series.
- 16.12 Consumption — realism + advice + app (user chose **both**). **Realism:** mock-draft opponents reflect
  16.8/16.9/16.10/16.11 drift. **Advice (opt-in, never touches frozen value):** drift feeds the Phase-9.4
  `survival_prob`/lookahead so your *own* pick advice accounts for it ("he won't last — consider reaching").
  **App:** an honest `P(available at your pick)` + a "draft-market drift / reach-risk" readout on the player
  deep page (extends `docs/PLAYER-VIEW.md`, walled-off + tagged like the situation bar), and the drift board
  on the 16.6 Beta Lab tab.
- **Done when** (value-side, unchanged) 16.1/16.2 report an honest survive-or-drop verdict (same discipline as
  Phase 6/7/12); 16.3 is user-approved; 16.4 computes for the 2026-relevant coaching moves; 16.5 is populated;
  16.6 ships in the app, provably isolated from the frozen core. **(availability-side)** 16.7/16.8 report an
  honest walk-forward drift-predictability verdict on the Sleeper corpus; 16.9 reproduces realized draft-slot
  dispersion without regressing availability Brier; 16.10 loads + applies a user-reviewed hype board; 16.11
  computes live 2026 momentum; 16.12 wires realism + opt-in advice + the app readout — **all outside the
  frozen value stack**, all walk-forward or explicitly labeled live-only.
- **Data prerequisite 0.11 (ECR + Underdog ADP; added 2026-07-23, feeds 16.8).** A FantasyPros **ECR**
  (expert-consensus-rank) scrape — the *true* expert-rank-minus-ADP signal 16.8 currently proxies with the
  VBD-ADP gap — plus **Underdog** ADP (the sharp best-ball market — the cleanest `source_divergence` input, and
  it makes best-ball realistic). Extends the Phase-0 data foundation (`data/sources/`); ECR is live-only,
  Underdog backfills where available. → `steps/phase0_11_ecr_underdog.py`, `data/sources/`.
- **16.16 Live-draft reactive re-estimation (run detection; added 2026-07-23, item D).** Mid-draft, detect a
  positional **run** and update the room's tendencies live ("4 RBs gone in 6 picks — your RB window is closing
  faster than ADP says"). The engine logic extends the 11.1/11.2 opponent/availability model; the alert surfaces
  in the Phase-14.4 live-draft view. **Face-validity in replay** against real Sleeper drafts. → extend
  `draft/opponent_model.py` / `draft/availability.py`; surface in `app/`.

*Opponent-personality set (16.13–16.15, + the seat map 16.17 added 2026-07-30; the set added 2026-07-23,
user request — folded into the availability track).
The behavioral opponent model (11.1) predicts the *average* manager; a realistic practice room also wants
*heterogeneous* opponents. `draft/personalities.py` (Phase 11.3) already ships six ADP/behavioral tilts
(`balanced`, `chalk`, `zero_rb`, `reacher`, `homer`, `rookie_hawk`) — but **none tilt on risk or value**
(the live sim board carries only `adp`/`pos`), so an "upside chaser" (ceiling) and a "safe" (floor) drafter
can't be expressed. This cluster enriches the opponent board with the frozen Phase-5/value fields and ships
the 5 headline personalities the user asked for. **Decisions (user 2026-07-23):** the "auto-draft/BPA"
personality = **ADP autopilot only** (no value-board opponent); **enrich with the real frozen distribution/
value fields**; **validation = face-validity + unit-tested mechanics** (no corpus Brier gate — a realism/UX
feature); the 16.9 narrative shock expresses **through** the ceiling/hype personalities.*
- 16.13 Opponent-board enrichment — attach the frozen, **read-only** Phase-5 distribution (`boom_prob`,
  `q90`, `bust_prob`, `q10`, `games_played_mean`) + `value_board` (`vbd`, `overall_rank`) fields to the sim
  opponent board (`DraftState.draftable_pool` source), PIT, so risk/value personalities have signal to tilt
  on. → `draft/simulator.py` board build + a join helper. **No modeling change** (read-only).
- 16.14 Risk/value personality set — extend `Personality` to tilt on the enriched columns (a `signal_weights`
  term beyond the β-tilt), and ship the **5 headline personalities**: (1) **Autopilot** — deterministic
  lowest-ADP-available (the literal Sleeper autopick; behavioral features zeroed, argmax); (2) **Balanced** —
  the fitted average human (already exists); (3) **Upside Chaser** — tilts to `boom_prob`/`q90` + youth/
  rookies, punts floor; (4) **Safe / Floor** — tilts to `q10`/`games_played_mean`/Phase-6 DURABILITY, low
  `bust_prob`, veterans; (5) **Homer / Narrative-Chaser** — favorite-team (`fandom`) + hyped names (the 16.10
  hype board), the channel the 16.9 shock rides through. → `draft/personalities.py`. `zero_rb`/`reacher`/
  `rookie_hawk` stay as library extras.
- 16.15 Mock-room composition + hype coupling + app — a **configurable opponent seat-assignment** (a default
  realistic mix, user-overridable), the wiring where the 16.9 per-draft narrative shock is applied **through**
  the Upside/Homer personalities, and the Phase-14 app control to pick/see opponent personalities in a mock.
  → `draft/simulator.py` seat assignment + `app/` / `docs/PLAYER-VIEW.md`.
- 16.17 **The seat map — multi-seat human control** *(added 2026-07-30, user request)*: the user picks **how
  many seats they drive**, not just which one — assign personalities to 6 of 10 and draft the other 4 teams
  yourself. 16.15 made any *opponent* seat configurable; the *human* side is fixed at one because
  `DraftState.your_team` is a single int and the `team → seat` map is positional arithmetic repeated in three
  places, so the engine supports only 1-human and 0-human rooms. → one `SeatMap` (`HUMAN` or a `Personality`
  per seat) + `DraftState.human_teams` + per-seat pick functions + a `--seats` CLI, in
  `draft/personalities.py` / `draft/simulator.py` / `steps/mock_draft.py`; UI in **14.J**. **Pure plumbing —
  the done-bar is bit-identity with today's room at k=1 and k=0.** Two honesty rules travel with it: k human
  teams in one draft are **one** observation (their picks deplete each other's pools), and the T15 realism
  bars describe a **fully-simulated** room.
- **Done when** (personalities) 16.13 enriches the board read-only; 16.14's 5 personalities pass **face-
  validity** checks (Upside skews young / high-`q90`, Safe skews durable / high-`q10`, Autopilot draws pure
  ADP order, Homer reaches for `fandom`/hype names, Balanced ≈ the fitted model) + unit-tested tilt mechanics;
  16.15 assigns a realistic room, couples the hype shock, and exposes the selector in the app; **16.17 lets any
  subset of seats be human — a 10-team mock runs for k = 0…10 human seats with the k=1 and k=0 paths
  bit-identical to today's** — **all read-only w.r.t. the frozen value stack.**

**Sequencing:** 0 → 1 gate everything. Phase 6 (ADP-bias) can run right after Phase 1. Phases 7 (causal)
and 12 (NLP) are **cross-cutting workstreams** — start them alongside, not strictly after, the modeling
phases. **Phase 16 runs after the lockbox eval and before Phase 14** (user decision, 2026-07-19) — it's a
new research track built on the now-frozen stack, and its tab ships inside the Phase-14 app from day one
rather than being retrofitted later. The app (14) consumes whatever modeling exists; a thin v1 can wrap
Phases 1–2 early.

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
