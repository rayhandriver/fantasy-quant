# BUILD_PLAN.md — the detailed, step-by-step execution manual

The full build, one **working session per step**, each producing **one focused file** (the AlphaThena
methodology). `PROJECT.md` §5 is the index; this is the depth. `ROADMAP.md` tracks status.

**How to read each step:**
- **Goal** — the one-sentence point.
- **Do** — the concrete work (methods, the substance).
- **Out** — the module/artifact it produces + key outputs.
- **Done** — acceptance criteria (assert these, don't eyeball).
- **Reuse** — libraries / intern-repo analogs / earlier steps to build on.

**The discipline applies to every step** (see `CLAUDE.md` §3): point-in-time everywhere, walk-forward
never in-sample, beat ADP **and** the betting market before shipping, guard every output, log to
`findings.md` + `glossary.md` as you go. Run everything via `uv run python steps/<script>.py`.

---

# Phase 0 — Data foundation (PIT ingest → DuckDB)
*Goal of the phase: a clean, point-in-time, queryable store of every signal, with nothing dated after an
as-of leaking in. This is 60% of the eventual edge; do it slowly and correctly.*

### 0.1 — Environment & repo scaffold ✅ (done 2026-06-29)
- uv + Python 3.12, src-layout package, doc set, git. Nothing more to do.

### 0.2 — nflverse / nfl_data_py ingest → `data/sources/nflverse.py`
- **Goal:** land the core NFL signal (play-by-play, weekly, snaps, IDs) in DuckDB.
- **Do:** pull `import_pbp_data`, `import_weekly_data`, `import_seasonal_data`, `import_snap_counts`,
  `import_ngs_data` (aggregated Next Gen Stats — free), `import_ids`, `import_draft_picks`,
  `import_combine_data` for **2014→latest**. Normalize player IDs to `gsis_id` via `import_ids` (the join
  key everything hangs off). Write each to a DuckDB table with a `pulled_at` timestamp column. Cache raw
  pulls to `data/raw/nflverse/` (parquet) so you never re-hit the network mid-dev.
- **Out:** `data/sources/nflverse.py` (functions: `ingest_pbp`, `ingest_weekly`, `ingest_snaps`,
  `ingest_ngs`, `ingest_ids`); DuckDB tables `pbp`, `weekly`, `snaps`, `ngs`, `player_ids`, `draft_picks`.
- **Done:** a fresh `uv run` rebuilds all tables; row counts per season are sane (≈ each season's known
  totals); `gsis_id` joins weekly↔snaps with <1% unmatched.
- **Reuse:** `nfl_data_py` (the `data` extra, already installed); `duckdb`; pandas 3.0 (watch deprecated APIs).

### 0.3 — Pro-Football-Reference season panels → `data/sources/pfr.py`
- **Goal:** multi-year season-level panels (and anything nflverse lacks) as a cross-check + extra features.
- **Do:** scrape PFR fantasy + per-position season tables (httpx + BeautifulSoup), **respecting robots/rate
  limits** (sleep, cache aggressively to `data/raw/pfr/`). Map PFR player keys → `gsis_id` via name+team+season
  fuzzy match (fall back to a manual override table). Store as `pfr_seasonal`.
- **Out:** `data/sources/pfr.py` (`ingest_pfr_seasonal`, `map_pfr_ids`); table `pfr_seasonal` + an
  `id_overrides.csv` for unmatched names.
- **Done:** PFR season fantasy points reconcile with nflverse `seasonal` within a few % per player; unmatched
  names are logged, not silently dropped.
- **Reuse:** `httpx`, `beautifulsoup4`, `lxml`; the `player_ids` table from 0.2.

### 0.4 — ADP ingest (FFCalculator + Underdog), PIT snapshots → `data/sources/adp.py`
- **Goal:** the "market price" — historical ADP, snapshotted at fixed dates so it's PIT-valid.
- **Do:** scrape **Fantasy Football Calculator** historical ADP (10-team PPR, by season; it exposes
  date-stamped snapshots) and **Underdog** best-ball ADP. Store every snapshot with its `snapshot_date`
  and `source` + `format` (redraft/best-ball). Build a helper `adp_asof(season, as_of)` returning the latest
  snapshot ≤ `as_of`. Normalize to `gsis_id`.
- **Out:** `data/sources/adp.py` (`ingest_adp`, `adp_asof`); table `adp_snapshots(season, snapshot_date,
  source, format, gsis_id, adp, pos_rank)`.
- **Done:** `adp_asof` never returns a snapshot dated after `as_of` (assert); coverage spans ≥ 2015→present
  for at least one source; best-ball vs redraft are distinguishable.
- **Reuse:** scraping stack; `player_ids`. **Open question (PLAN.md):** how far back FFCalculator/Underdog go.

### 0.5 — Vegas markets ingest (props/totals/spreads, de-vig) → `markets/odds_ingest.py`
- **Goal:** the *sharper* market — player props and game lines as features, anchors, and calibration.
- **Do:** pull from a free odds API (the-odds-api.com free tier) and/or scrape books for: **player props**
  (rec yds, rush yds, rec, rush att, pass yds/TD, anytime-TD), **game totals**, **spreads**, **season win
  totals**. **De-vig** each market (proportional first; note Shin/power as alternatives) to fair
  probabilities/means. Derive **implied team total** = f(total, spread). Timestamp every line (`captured_at`)
  — odds move, so PIT means "the line as of date t." Backfill historical lines where free; **flag the
  historical-prop gap** (likely the one paid source) in `PLAN.md`.
- **Out:** `markets/odds_ingest.py` (`ingest_odds`, `devig`, `implied_team_total`, `odds_asof`); tables
  `props`, `game_lines`, `season_props`.
- **Done:** de-vig'd two-way props sum to ~1.0 (assert); `odds_asof` is PIT; implied team totals are sane
  (~17–30). Create the **markets package** (`src/fantasy_quant/markets/__init__.py`).
- **Reuse:** `httpx`; new `markets/` package; glossary "Betting-market terms."

### 0.6 — News / injury / depth-chart raw ingest → `news/ingest.py`
- **Goal:** lay the *pipe* for the Phase-12 NLP edge — capture raw text now, extract later.
- **Do:** ingest official **injury reports** (status: Q/D/O), **inactives** (90 min pre-kickoff), **depth
  charts** (nflverse `import_depth_charts` if available, else scrape), and a beat-writer/news text feed
  (RSS/scrape) — each row timestamped. Store raw; no NLP yet (that's 12.x). This early capture is what makes
  later PIT event-studies possible (you can't reconstruct yesterday's news after the fact).
- **Out:** `news/ingest.py` (`ingest_injuries`, `ingest_depth_charts`, `ingest_news_text`); tables
  `injuries`, `depth_charts`, `news_raw`. Create the **news package**.
- **Done:** each table has a timestamp; a day's injury report is reconstructable as-of that day.
- **Reuse:** scraping stack; new `news/` package.

### 0.7 — PIT panel / feature-store assembly → `data/panel.py`
- **Goal:** the unified, point-in-time join layer everything downstream reads from.
- **Do:** build `build_panel(as_of)` that assembles a `(season, week/player)` panel joining weekly stats,
  snaps, NGS, ADP-as-of, odds-as-of, injuries-as-of — **all filtered `≤ as_of` at the read** (predicate
  pushdown, the intern repo's PIT pattern). Provide both a **weekly** grain (for variance/in-season) and a
  **pre-season** grain (for draft projections). Materialize processed panels to `data/processed/`.
- **Out:** `data/panel.py` (`build_panel`, `preseason_panel(season, as_of)`, `weekly_panel(season, as_of)`).
- **Done:** two different `as_of` dates yield different panels; **no field dated after `as_of`** appears
  (assert, like intern Step 1.1); the same `gsis_id` lines up across all joined sources.
- **Reuse:** all of 0.2–0.6; `pyarrow` predicate pushdown; intern `pull_factor_data` PIT pattern.

### 0.8 — Data validation & sanity gates → `data/validate.py`
- **Goal:** the hard-gate analog — outputs that fail sanity never flow downstream.
- **Do:** assertions/report on coverage (% non-null per key field), ID-join rates, value ranges (no negative
  yards, fantasy points in plausible bounds), duplicate `(player, week)` rows, and PIT monotonicity. Emit a
  `data_health.json` per build. Document **survivorship** (which players are absent) as a known limitation.
- **Out:** `data/validate.py` (`validate_panel`, `data_health_report`); `analysis/results/data_health.json`.
- **Done:** the panel passes all gates or fails loudly with the offending rows; health report is committed.
- **Reuse:** intern `_validate_cov_hard_gate` philosophy.

---

# Phase 1 — Backtest harness (built BEFORE any modeling)
*Goal of the phase: the function that scores any ranking method on history, PIT-clean. Without this you
cannot tell if you're improving. This is the literal port of the intern `min_variance_backtest` discipline.*

### 1.1 — League scoring engine → `backtest/scoring.py`
- **Goal:** turn raw stats into fantasy points under a configurable ruleset.
- **Do:** implement `score(stats, ruleset)` for full-PPR 1-QB (and parametrized for half-PPR/TE-premium/
  superflex later). Reconstruct **historical weekly + season fantasy points** for every player-week from
  nflverse stats. Validate against nflverse's own `fantasy_points_ppr`.
- **Out:** `backtest/scoring.py` (`score`, `weekly_points`, `season_points`); a `RuleSet` pydantic model.
- **Done:** reconstructed PPR points match nflverse within rounding for a sample of players/weeks (assert).
- **Reuse:** `weekly` table (0.2); `pydantic` for the ruleset.

### 1.2 — Draft simulator → `draft/simulator.py`
- **Goal:** simulate a full snake draft against ADP-following opponents.
- **Do:** `simulate_draft(your_pick_fn, n_teams=10, rounds=15, adp, noise)` — opponents pick by ADP +
  Gaussian noise (the baseline opponent model; richer models come in 11.1). Your team is driven by a
  pluggable `your_pick_fn(state)`. Returns full rosters + pick log. Enforce roster rules (starter slots, bye
  legality optional here).
- **Out:** `draft/simulator.py` (`simulate_draft`, `DraftState`).
- **Done:** runs a 10×15 draft; ADP-only `your_pick_fn` produces an ADP-typical roster; reproducible with a seed.
- **Reuse:** `adp_asof` (0.4); `DraftState` becomes the input to every later policy.

### 1.3 — Walk-forward harness → `backtest/walkforward.py`
- **Goal:** the engine — *ranking method → simulated drafts → realized season outcomes*, across seasons, PIT.
- **Do:** `walk_forward(rank_fn, seasons=2015..last)` that, for each season: builds the **pre-season panel
  as-of that season's draft date** (strict PIT), generates `rank_fn`'s board, simulates K drafts from varied
  draft slots, then scores each resulting roster against that season's **actual** weekly results (optimal
  weekly lineups). Aggregate across seasons. **No data after the draft date may touch `rank_fn`.**
- **Out:** `backtest/walkforward.py` (`walk_forward`, returns per-season + pooled results).
- **Done:** swapping `rank_fn` is a one-arg change; a planted future-dated feature trips a PIT assert
  (synthetic test, like intern Step 5.1).
- **Reuse:** 1.1, 1.2, `preseason_panel` (0.7); intern `cov_builder_fn`-plug pattern.

### 1.4 — PAR metric scorer → `backtest/metrics.py`
- **Goal:** the simple headline metric — points-above-replacement of the resulting roster.
- **Do:** define positional **replacement levels** for 10-team PPR (e.g. last reliably-started player per
  slot), compute each roster's expected **starting-lineup PAR** (optimal weekly lineups, summed). Add
  secondary metrics: expected wins, final standing.
- **Out:** `backtest/metrics.py` (`par`, `expected_wins`, `replacement_levels`).
- **Done:** PAR ranks an obviously-good roster above an obviously-bad one; replacement levels documented.
- **Reuse:** 1.1; **open question (PLAN.md):** exact replacement definition.

### 1.5 — Significance → `backtest/significance.py`
- **Goal:** don't declare a winner on noise.
- **Do:** **stationary/moving-block bootstrap** on the per-season metric-difference series (method − ADP),
  return effect size + 95% CI. Always compare against the **ADP baseline and the market baseline**.
- **Out:** `backtest/significance.py` (`block_bootstrap_ci`, `compare_to_baseline`).
- **Done:** reproduces a known CI on synthetic data; respects autocorrelation (block, not iid, resampling).
- **Reuse:** intern `te_diff_bootstrap` analog; `numpy`.

---

# Phase 2 — Markets & baselines (sharp-market-anchored)
*Goal: cheap, strong baselines — including one built straight from the betting market — that everything
fancy must beat. Per the Part-11 lesson, beating these is the bar, not an afterthought.*

### 2.1 — Replacement levels & VBD baseline → `valuation/vbd.py`
- **Goal:** turn projected points into draftable cross-position value.
- **Do:** implement VBD = projected points − positional replacement; expose `vbd(projections, ruleset)`.
- **Out:** `valuation/vbd.py` (`vbd`, `replacement_baseline`).
- **Done:** VBD board is monotonic in points within a position; cross-position ordering is sane.
- **Reuse:** 1.4 replacement levels.

### 2.2 — Naive opportunity×efficiency baseline → `projections/baseline.py`
- **Goal:** a documented, simple projection to beat (prior-year volume × efficiency, lightly aged).
- **Do:** project season points from prior-year opportunity (targets/carries) × efficiency (YPC/YPR/TD rate),
  regressed lightly to positional means. No ML yet — deliberately dumb.
- **Out:** `projections/baseline.py` (`baseline_projection`).
- **Done:** backtests via the harness; produces a full board; logged as the baseline to beat.
- **Reuse:** 0.7 panel; 1.3 harness.

### 2.3 — Props-implied projection → `markets/props_projection.py`
- **Goal:** a projection built *directly from the sharp market* — often the toughest baseline to beat.
- **Do:** convert de-vig'd **season props / win totals** (and, where available, aggregated weekly props) into
  per-player season point projections. This is the market's own forecast, repackaged in fantasy points.
- **Out:** `markets/props_projection.py` (`props_projection`).
- **Done:** props-implied board backtests at/above ADP; documented as a primary baseline.
- **Reuse:** 0.5 `markets`; 1.1 scoring.

### 2.4 — Ensemble-with-market → `projections/ensemble.py`
- **Goal:** the reliable way to *not lose* the forecasting fight — blend, don't replace.
- **Do:** learn weights to combine {your model, ADP-implied, props-implied, consensus} via stacking /
  Bayesian model averaging; **shrink toward the market by confidence**. Start with the baseline + props.
- **Out:** `projections/ensemble.py` (`ensemble_projection`, `fit_weights`).
- **Done:** the ensemble backtests ≥ its best single component OOS.
- **Reuse:** 2.2, 2.3; `scikit-learn`.

---

# Phase 3 — Feature engineering (exposures `X`)
*Goal: the PIT exposure matrix — the fantasy analog of the intern style-exposure matrix. One file per
factor family so each is independently testable.*

### 3.1 — Opportunity factors → `features/opportunity.py`
- **Do:** target share, snap %, route participation, carry/touch share, **air yards, aDOT, WOPR**, red-zone
  targets/carries, goal-line carries, vacated targets/touches (from departures). All PIT, prior-to-as-of.
- **Out:** `features/opportunity.py`; **Done:** finite, ranges sane, PIT-asserted. **Reuse:** 0.2 snaps/NGS/pbp.

### 3.2 — Efficiency factors (+ TD-regression flags) → `features/efficiency.py`
- **Do:** YPRR, YAC, catch rate, contested-catch, **TD rate + over/under-TD-luck flags**, QB EPA/play. Mark
  efficiency as partly mean-reverting (used differently from opportunity).
- **Out:** `features/efficiency.py`; **Done:** TD-regression flag correlates with next-year TD drop in-sample
  check; PIT-asserted. **Reuse:** 0.2 pbp.

### 3.3 — Player-intrinsic factors → `features/player.py`
- **Do:** age, draft capital, athletic profile (combine, breakout age, college dominator), experience /
  breakout-year flags, playstyle archetype.
- **Out:** `features/player.py`; **Done:** age computed as-of correctly (no future birthdays); finite.
  **Reuse:** 0.2 draft/combine/ids.

### 3.4 — Team/environment factors (+ implied team total) → `features/environment.py`
- **Do:** O-line quality, QB quality (for pass-catchers), scheme/PROE, pace, **Vegas implied team total &
  win total** (0.5), teammate competition, coaching/OC-change flags.
- **Out:** `features/environment.py`; **Done:** implied-team-total feature joins PIT; finite. **Reuse:** 0.5
  markets, 0.2 pbp.

### 3.5 — Standardized PIT exposure matrix `X` → `features/exposures.py`
- **Do:** assemble 3.1–3.4 into one matrix, cross-sectional **winsorized z-scores** per as-of, archetype/
  position dummies; handle missingness explicitly (the intern Step 1.2 recipe).
- **Out:** `features/exposures.py` (`build_exposures(as_of)`); **Done:** finite, mean-centered, columns
  documented, PIT. **Reuse:** intern `standardize_exposures`.

---

# Phase 4 — Mean projection models
*Goal: the best point projection you can build — then prove it beats the Phase-2 baselines AND the market.*

### 4.1 — GBT component models → `projections/gbt.py`
- **Do:** per-position **XGBoost/LightGBM** models for the components (targets, catch rate, YPR, TD rate for
  WR; touches, YPC, TD, target share for RB; etc.), with **nested cross-validation** (small-n discipline).
  Compose components → points. Feature importances logged.
- **Out:** `projections/gbt.py` (`fit_components`, `project`); **Done:** beats 2.2 baseline OOS; CV honest
  (no leakage across seasons). **Reuse:** `xgboost`/`lightgbm`; 3.5 X; 1.3 harness.

### 4.2 — Age curves (delta method) → `projections/age_curves.py`
- **Do:** Tom Tango **delta method** per position (year-over-year deltas averaged across players, smoothed) —
  robust vs cross-sectional polynomial selection bias. Apply as a multiplier in projections.
- **Out:** `projections/age_curves.py` (`age_curve`, `apply_aging`); **Done:** curves match known shapes (RB
  cliff ~28-30, WR peak 25-27); improves OOS. **Reuse:** 0.2 seasonal panels.

### 4.3 — Hierarchical-Bayes thin-sample priors → `projections/hier_bayes.py`
- **Do:** **PyMC** hierarchical model pooling rookies / injury-returns / new-system players toward
  **archetype-level priors** (partial pooling). Install `uv sync --extra bayes` here.
- **Out:** `projections/hier_bayes.py` (`fit_hier`, `posterior_mean`); **Done:** shrinks thin samples
  sensibly; beats naive point estimates for low-`n` players OOS. **Reuse:** `pymc`; 3.5 X.

### 4.4 — Props-anchored shrinkage → `projections/market_shrink.py`
- **Do:** shrink the model projection toward the **de-vig'd prop mean** by a confidence weight (more shrink
  where your model is uncertain / where the market is liquid). The disciplined "don't fight the sharp market"
  step.
- **Out:** `projections/market_shrink.py` (`market_shrink`); **Done:** shrunk projections beat un-shrunk OOS
  on players with liquid props. **Reuse:** 0.5/2.3 props; 4.1.

### 4.5 — Calibration vs market & realized → `projections/calibration.py`
- **Do:** bias-statistic analog (realized ÷ predicted ≈ 1) + reliability plots; compare your projection to
  the market and to realized. Flag systematic over/under by position.
- **Out:** `projections/calibration.py` (`calibration_report`); **Done:** calibration ≈ 1 or the miscalibration
  is documented + corrected. **Reuse:** intern `bias_statistic`.

---

# Phase 5 — Distributional projections
*Goal: the full distribution F(points), not just the mean — the prerequisite for floor/ceiling, variance
preference, and the season simulator.*

### 5.1 — Quantile regression → `projections/quantile.py`
- **Do:** XGBoost **quantile loss** for P10/P50/P90 per player (season and weekly grains).
- **Out:** `projections/quantile.py` (`project_quantiles`); **Done:** quantiles ordered, coverage roughly
  nominal. **Reuse:** `xgboost`.

### 5.2 — Conformal prediction → `projections/conformal.py`
- **Do:** wrap projections in **split/conformalized quantile regression** for distribution-free **calibrated**
  intervals; validate empirical coverage.
- **Out:** `projections/conformal.py` (`conformal_intervals`); **Done:** P90/P10 coverage within tolerance of
  90/10% OOS. **Reuse:** 5.1; `scikit-learn`.

### 5.3 — Boom/bust variance (GARCH-like) → `projections/variance.py`
- **Do:** model **week-to-week variance** itself (volatility clustering); classify consistency vs boom/bust;
  per-player variance estimate for the covariance/sim.
- **Out:** `projections/variance.py` (`week_variance`, `boom_bust_score`); **Done:** high-variance players
  flagged match intuition; variance predicts realized weekly std OOS. **Reuse:** weekly panel; `statsmodels`.

### 5.4 — Injury survival/hazard → `projections/injury.py`
- **Do:** **survival/hazard model** (time-to-injury, recurrent events) with age/usage/position covariates →
  per-player **games-missed distribution**. Feeds handcuff valuation + season sim.
- **Out:** `projections/injury.py` (`games_missed_dist`, `injury_hazard`); **Done:** position base rates match
  known actuarial rates (RB highest); produces a distribution, not a point. **Reuse:** 0.2 injuries; `lifelines`
  (add dep) or `statsmodels`.

### 5.5 — Expected-utility (floor/ceiling) scoring → `valuation/utility.py`
- **Do:** position-dependent **utility function** over each player's distribution — concave (floor) for
  starters, convex (ceiling) for late dart-throws — making "consistency vs volatility" concrete.
- **Out:** `valuation/utility.py` (`expected_utility`); **Done:** utility ranks a safe floor above a volatile
  bust for a starter slot, and inverts for a bench dart. **Reuse:** 5.1–5.3 distributions.

---

# Phase 6 — ADP-bias mining (self-contained; start after Phase 1)
*Goal: find persistent, exploitable ADP biases — the intern factor-return regression, repurposed. High
value, low coupling.*

### 6.1 — ADP-alpha panel → `adp/panel.py`
- **Do:** build `(player, season)` → pre-season **ADP** + end-of-season **finish**; define **ADP alpha**
  (finish-rank − ADP-rank, or points − slot-replacement). PIT snapshot date fixed per season.
- **Out:** `adp/panel.py` (`adp_alpha_panel`); **Done:** PIT, survivorship documented. **Reuse:** 0.4, 1.4.

### 6.2 — Cross-sectional ADP-alpha regression → `adp/regression.py`
- **Do:** regress ADP alpha on **pre-season** features (age, prior TD rate, rookie flag, games-missed,
  team/OC change, target share, draft capital, ADP source). Walk-forward, **block-bootstrap CIs**, never
  in-sample.
- **Out:** `adp/regression.py` (`fit_adp_alpha`); **Done:** coefficients stable across seasons or honestly
  null. **Reuse:** intern `phase2_factor_returns` analog; 1.5.

### 6.3 — Bias scorecard → `adp/scorecard.py`
- **Do:** rank biases by stable effect size, **correct for multiple testing** (BH/FDR), write a scorecard;
  expose the significant biases as a tilt the projections/board can apply.
- **Out:** `adp/scorecard.py` + `analysis/results/adp_biases.json`; **Done:** a short, honest list of biases
  with CIs (or "none survive"). **Reuse:** 6.2.

---

# Phase 7 — Causal "player-in-system" [DEEP]
*Goal: answer the counterfactual "how would X do in offense Y?" — the crux of trades, coaching changes,
rookies. Beyond correlational factors.*

### 7.1 — Skill ÷ opportunity decomposition → `causal/decompose.py`
- **Do:** model production = player-intrinsic latent (skill, transferable) × team-conferred situation
  multiplier (opportunity, predictable). Estimate both from history (mixed-effects / latent-variable).
- **Out:** `causal/decompose.py` (`decompose`, `skill`, `situation_multiplier`); **Done:** skill is more
  stable across team-changes than raw production (validate on movers). **Reuse:** 3.x features; `pymc`/`statsmodels`.

### 7.2 — Counterfactual re-projection → `causal/counterfactual.py`
- **Do:** on a situation change (trade/FA/scheme), swap the situation multiplier and re-project; use
  **matching / synthetic control** on historical comparable transitions to estimate the counterfactual.
- **Out:** `causal/counterfactual.py` (`reproject_on_move`); **Done:** beats naive carry-over on held-out moves
  (7.4). **Reuse:** 7.1.

### 7.3 — College→NFL transport (rookies) → `causal/rookie_transport.py`
- **Do:** transfer-learning / causal-transport from college production + draft capital + landing spot →
  rookie projection with uncertainty.
- **Out:** `causal/rookie_transport.py` (`project_rookie`); **Done:** rookie projections calibrated vs realized
  on past classes. **Reuse:** 0.2 draft/combine; 4.3 priors.

### 7.4 — Held-out transition validation → `causal/validate.py`
- **Do:** strict OOS test on player-moves the model didn't see; compare counterfactual vs naive vs market.
- **Out:** `causal/validate.py`; **Done:** documented win/loss vs baselines on transitions. **Reuse:** 1.3, 1.5.

---

# Phase 8 — Covariance & roster construction
*Goal: the most direct reuse of your internship — a shrunk player-week covariance and roster floor/ceiling.*

### 8.1 — Player-week covariance → `covariance/estimate.py`
- **Do:** estimate the `k×k` player-week covariance from weekly points; annualize/scale; hard-gate (PSD,
  symmetric, finite).
- **Out:** `covariance/estimate.py` (`player_covariance`); **Done:** passes a hard gate (intern analog).
  **Reuse:** intern `_ewma_covariance`, `_validate_cov_hard_gate` philosophy.

### 8.2 — Structured correlations + shrinkage → `covariance/shrinkage.py`
- **Do:** impose structure (QB-WR1 +0.4, RB1/RB2 −0.3, handcuff −) and apply **Ledoit-Wolf / QIS** shrinkage
  for stability in high dimension.
- **Out:** `covariance/shrinkage.py` (`shrink`, `structured_corr`); **Done:** shrunk Σ better-conditioned;
  out-of-sample portfolio variance improves. **Reuse:** intern QIS/Ledoit-Wolf.

### 8.3 — Copulas for handcuff tail-dependence → `covariance/copula.py`
- **Do:** Clayton/Gumbel **copulas** for the asymmetric handcuff payoff (worthless until starter injured, then
  valuable).
- **Out:** `covariance/copula.py` (`handcuff_copula`); **Done:** captures lower/upper-tail dependence the
  Gaussian Σ misses. **Reuse:** `scipy`; 5.4 injury.

### 8.4 — Roster floor/ceiling via `(w)ᵀΣ(w)` → `valuation/roster_risk.py`
- **Do:** compute a roster's variance/floor/ceiling from Σ + the weekly distributions; the tracking-error
  machinery, repurposed.
- **Out:** `valuation/roster_risk.py` (`roster_variance`, `roster_floor_ceiling`); **Done:** stacked roster
  shows higher ceiling, anti-correlated shows higher floor. **Reuse:** intern TE calc; 8.1–8.3.

### 8.5 — Handcuff real-option valuation → `valuation/handcuff.py`
- **Do:** price the handcuff as a contingent claim using 5.4 injury probabilities:
  `P(injury)·E[replacement] + (1−P)·E[standalone]`.
- **Out:** `valuation/handcuff.py` (`handcuff_value`); **Done:** values move correctly with starter fragility +
  backup's contingent ceiling. **Reuse:** 5.4; 8.3.

---

# Phase 9 — Valuation & draft policy
*Goal: turn projections + risk into draft decisions, and measure the structural ("tax") alpha.*

### 9.1 — Conditional-VBD → `valuation/conditional_vbd.py`
- **Do:** value of a pick = points now − **E[best available at your next pick]** (expectation over the draft
  flow between your picks) — the option-pricing VBD.
- **Out:** `valuation/conditional_vbd.py` (`conditional_vbd`); **Done:** values reflect positional runs/scarcity;
  beats static VBD OOS. **Reuse:** 1.2 sim; 2.1 VBD.

### 9.2 — Structural-alpha backtest → `valuation/structural_alpha.py`
- **Do:** **the headline number** — holding projections = ADP, measure the finish/title-odds lift from
  structure/schedule/variance optimization alone (the TLH analog).
- **Out:** `valuation/structural_alpha.py` + `analysis/results/structural_alpha.json`; **Done:** a CI'd "X%
  better finish from construction alone." **Reuse:** 1.3, 8.4, 10.x (once available).

### 9.3 — Greedy draft policy → `draft/greedy_policy.py`
- **Do:** the live policy — pick argmax conditional-VBD/utility given roster state + needs + bye/stack logic;
  fast (sub-second) for live use.
- **Out:** `draft/greedy_policy.py` (`greedy_pick`); **Done:** beats ADP drafting OOS; runs in <1s/pick.
  **Reuse:** 9.1, 5.5, 8.4.

### 9.4 — Win-probability / CVaR objective → `valuation/objective.py`
- **Do:** define the objective the policy/sim optimizes — **P(playoffs/title)** and/or **CVaR**, not symmetric
  variance; expose game-state leverage (chase ceiling when behind).
- **Out:** `valuation/objective.py` (`win_prob_objective`, `cvar`); **Done:** objective is differentiable from
  the sim outputs; documented. **Reuse:** 10.x.

---

# Phase 10 — Season & playoff simulation (north-star metric)
*Goal: the championship/playoff-probability engine that becomes the true scoring metric.*

### 10.1 — Monte-Carlo season engine → `simulation/season.py`
- **Do:** simulate a full season from player distributions (5.x) + covariance (8.x): schedule, **bye weeks**,
  **injury games-missed** (5.4), weekly optimal lineups, head-to-head matchups. Create the **simulation** package.
- **Out:** `simulation/season.py` (`simulate_season`); **Done:** simulated win/points distributions match
  historical league variance. **Reuse:** 5.x, 8.x, 1.1.

### 10.2 — Playoffs → title/playoff probability → `simulation/playoffs.py`
- **Do:** simulate the bracket → **championship & playoff probabilities** per roster — the north-star metric.
- **Out:** `simulation/playoffs.py` (`title_probability`); **Done:** title-prob ranking stable across seeds;
  beats ADP + PAR OOS. **Reuse:** 10.1.

### 10.3 — Leverage-by-game-state → `simulation/leverage.py`
- **Do:** quantify when to add/cut variance (DFS-GPP leverage applied season-long) based on standings/odds.
- **Out:** `simulation/leverage.py` (`leverage_advice`); **Done:** raising variance when behind improves
  simulated title odds. **Reuse:** 10.1–10.2; 9.4.

---

# Phase 11 — Game-theory draft engine [DEEP]
*Goal: treat the draft as the adversarial game it is — beat the greedy policy by looking ahead and modeling
opponents.*

### 11.1 — Live opponent modeling → `draft/opponent_model.py`
- **Do:** per-opponent **Bayesian posterior over their board** (Dirichlet/categorical over positions+players),
  updated each pick; trained from league history + mocks; enables **exploitative** play.
- **Out:** `draft/opponent_model.py` (`OpponentModel.update/predict`); **Done:** predicts held-out league picks
  better than ADP-noise. **Reuse:** 1.2; mock data (14.7).

### 11.2 — MCTS draft engine → `draft/mcts.py`
- **Do:** **Monte-Carlo Tree Search** over draft states — top-K branching, cheap rollout policy (9.3), value
  caching; opponents sampled from 11.1.
- **Out:** `draft/mcts.py` (`mcts_pick`); **Done:** beats greedy (9.3) vs realistic opponents OOS; meets the
  live time budget (pruned). **Reuse:** 9.x, 10.x, 11.1.

### 11.3 — CFR / exploitative refinement → `draft/cfr.py`
- **Do:** **counterfactual regret minimization** (poker-AI) for the imperfect-information structure; exploit
  opponent mistakes rather than play Nash.
- **Out:** `draft/cfr.py`; **Done:** improves on MCTS vs exploitable opponents OOS. **Reuse:** 11.1–11.2.

### 11.4 — Auction-draft support → `draft/auction.py`
- **Do:** nomination strategy, **budget allocation as a stochastic knapsack**, winner's-curse-aware bidding,
  the $1 endgame.
- **Out:** `draft/auction.py` (`auction_bid`, `nominate`); **Done:** beats naive budget-splitting in auction sims.
  **Reuse:** 9.1 values.

### 11.5 — Self-play RL (frontier) → `draft/selfplay.py`
- **Do:** AlphaZero-style value+policy net trained on simulated drafts; only after 11.1–11.3 are solid.
- **Out:** `draft/selfplay.py`; **Done:** matches/beats MCTS at lower live cost. **Reuse:** 1.2 env; 11.2.

---

# Phase 12 — NLP / live-news pipeline [DEEP]
*Goal: convert unstructured news into timestamped, PIT structured signal — the freshest-information edge.*

### 12.1 — Source scrapers/streams → `news/sources.py`
- **Do:** robust collectors for beat writers, injury reports, depth charts, **inactives**, transactions —
  timestamped, deduped, rate-limited.
- **Out:** `news/sources.py`; **Done:** continuous capture; each item has a reliable `captured_at`. **Reuse:** 0.6.

### 12.2 — LLM extraction → `news/extract.py`
- **Do:** **use Claude** to extract structured fields from text — role change, projected snap/route share,
  injury severity/timeline, "coachspeak" decoded — into PIT features with confidence.
- **Out:** `news/extract.py` (`extract_signal`); **Done:** extracted fields agree with hand-labeled samples;
  features are timestamped. **Reuse:** Claude API (see `/claude-api`); 12.1.

### 12.3 — Event-study → `news/event_study.py`
- **Do:** measure how ADP/props move on news and the **exploitable lag**; quantify which news types move markets.
- **Out:** `news/event_study.py`; **Done:** documented lag/impact per news type. **Reuse:** 0.4/0.5 markets; 12.2.

### 12.4 — Signal validation → `news/validate.py`
- **Do:** does an extracted signal improve projections/decisions OOS on the walk-forward? Kill signals that don't.
- **Out:** `news/validate.py`; **Done:** only validated signals feed the model. **Reuse:** 1.3, 1.5.

---

# Phase 13 — In-season co-pilot [CORE — season breadth]
*Goal: the season-long decision engine — the draft is only ~1 of 17+ decisions.*

### 13.1 — Weekly re-projection → `inseason/reproject.py`
- **Do:** update player distributions each week (state-space/Kalman flavor) with new results + news (12.x).
- **Out:** `inseason/reproject.py` (`reproject_week`); **Done:** weekly forecasts beat preseason-static OOS.
  **Reuse:** 5.x, 12.x. Create the **inseason** package.

### 13.2 — Start/sit optimizer → `inseason/lineup.py`
- **Do:** weekly lineup optimization under the **win-probability objective** + matchup + leverage (10.3).
- **Out:** `inseason/lineup.py` (`optimal_lineup`); **Done:** beats projection-max lineup on simulated win%.
  **Reuse:** 9.4, 10.x.

### 13.3 — Waivers/FAAB → `inseason/waivers.py`
- **Do:** sequential budget auction — **bandit + auction theory**, bid-shading, the option value of holding budget.
- **Out:** `inseason/waivers.py` (`faab_bid`); **Done:** beats naive %-of-budget bidding in sims. **Reuse:** 11.4.

### 13.4 — Streaming bandit → `inseason/streaming.py`
- **Do:** explore/exploit over the waiver pool for QB/TE/DST streaming.
- **Out:** `inseason/streaming.py` (`stream_pick`); **Done:** beats static-hold in sims. **Reuse:** 5.x.

### 13.5 — Trade finder → `inseason/trades.py`
- **Do:** value trades by **surplus**, surface **mutually-beneficial** deals (market-making), flag buy-low/
  sell-high on model-vs-perception gaps.
- **Out:** `inseason/trades.py` (`evaluate_trade`, `find_trades`); **Done:** proposed trades raise both teams'
  simulated win% (or yours, for buy-low). **Reuse:** 10.x values.

---

# Phase 14 — The app (shareable league co-pilot)
*Goal: wrap the proven model in a personalized, multi-user product your league can actually use.*

### 14.1 — Backend → `app/backend/`
- **Do:** **FastAPI** service over DuckDB/Postgres exposing projections, boards, sim, valuations; auth for
  league-mates. Create the **app** package.
- **Out:** `app/backend/` (`main.py`, routers); **Done:** endpoints return model outputs; auth works. **Reuse:** all model packages.

### 14.2 — Personalization layer → `app/backend/personalization.py`
- **Do:** per-user **archetype prefs, per-factor over/under-weights, draft style, anchor picks** → a
  personalized board from the same model; **always show vs the pure baseline** (anti-bias guardrail).
- **Out:** `app/backend/personalization.py`; **Done:** different user configs yield sensibly different boards.
  **Reuse:** 2.x, 9.x.

### 14.3 — Frontend → `app/frontend/`
- **Do:** **Next.js + TypeScript** UI — board, player cards (floor/ceiling), config panel, draft view.
- **Out:** `app/frontend/`; **Done:** renders a live board from the API. **Reuse:** 14.1 API. (Installs Node.)

### 14.4 — Sleeper live-draft sync → `app/backend/live_draft.py`
- **Do:** poll the **Sleeper draft API** (Redis state, WebSockets push) → live pick stream → next-pick rec
  via 9.3/11.2; manual entry as the universal fallback.
- **Out:** `app/backend/live_draft.py`; **Done:** a live Sleeper draft updates state and returns a rec inside
  the pick clock. **Reuse:** 9.3, 11.2.

### 14.5 — Explainability + preference learning → `app/backend/explain.py`
- **Do:** "why this pick" (SHAP / counterfactual); learn user tendencies from their actual picks (revealed
  preference) to refine personalization.
- **Out:** `app/backend/explain.py`; **Done:** each rec ships with a human-readable why. **Reuse:** 4.1, 14.2.

### 14.6 — Ambient widget → `app/widget/`
- **Do:** browser extension (DOM read) for desktop drafts; Android floating bubble (overlay + MediaProjection
  OCR) as the "corner widget"; iOS via Live Activities + API/manual (see `STRATEGY.md` Part 14).
- **Out:** `app/widget/`; **Done:** ambient rec updates as picks happen on ≥1 platform. **Reuse:** 14.4.

### 14.7 — Mock-draft simulator → `app/backend/mock_draft.py`
- **Do:** let users mock-draft vs the engine (practice) — **also generates opponent-model training data** (11.1).
- **Out:** `app/backend/mock_draft.py`; **Done:** a full mock runs end-to-end; picks logged for 11.1. **Reuse:** 1.2, 11.1.

---

# Phase 15 — Multi-format (roadmap)
- **15.1 Dynasty/keeper** → `formats/dynasty.py`: multi-year asset pricing (closest to your equity work).
- **15.2 Best-ball** → `formats/bestball.py`: no in-season management; pure draft + variance.
- **15.3 DFS GPP** → `formats/dfs.py`: ownership/leverage, game stacks, field-relative scoring.
- *Only after the redraft co-pilot (0–14) is proven.*

---

## Cross-cutting (every phase)
- **Log:** outcome → `findings.md`; new terms → `glossary.md`; per-step notes/dead-ends → `PLAN.md`.
- **Gate:** every modeling step must **beat ADP + the betting market + the prior baseline** on the
  walk-forward, with bootstrap CIs, or it's a documented finding — not shipped.
- **Status:** tick `ROADMAP.md` as each step lands.
