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
never in-sample, **calibration > edge** (well-calibrated, not ADP-beating), **track the benchmark & price
the cost**, keep a **lockbox**, **no LLM in the core**, guard every output, log to `findings.md` +
`glossary.md` as you go. Run everything via `uv run python steps/<script>.py`.

> **⟳ STRATEGIC REFRAME (2026-07-04) — read `docs/REFRAME-2026-07-04.md` + `docs/PERSONALIZATION.md`.**
> The objective is now **direct-indexing personalization**, not beating ADP. Per-phase impact:
> - **Phase 4 → "mean VALUE":** ingest **consensus projections → VBD**; **don't** build an edge-seeking
>   model; add an explicit **rookie model**; the bar is calibration, not beating ADP. (GBT/age-curve/
>   hier-Bayes below are **optional**, kept only if they improve calibration.)
> - **Phase 5 (distributions) → promoted to core** (the risk dial; the one value-side thing we build).
>   **Phase 8 (covariance) & Phase 10 (season sim) → promoted/earlier** (tracking error + the tracked
>   benchmark).
> - **Phase 6 → personalization intelligence** (where ADP is soft = how cheaply to indulge). **Phase 7 →
>   opportunity-adjusted** (drop causal counterfactual claims). **Phase 9 → + constrained optimizer +
>   cost-of-personalization report.** **Phase 11 → opponent model = core, Brier-scored; CFR dropped, MCTS
>   deprioritized.** **Phase 12 (NLP) + all in-app AI → deferred post-MVP.** **Phase 14 → Streamlit/Gradio
>   MVP first.**
> - **New: the Personalization spine** (constraint object · constrained optimizer · cost report ·
>   behavioral opponent model · availability · risk dial) — see the section at the end of this file and
>   `docs/PERSONALIZATION.md`. **The three signal layers are a hard contract:** value = consensus-VBD,
>   availability = ADP + behavioral, variance = our own distributions — never one "ADP" input.

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

### 0.9 — 2025 backfill + nflverse new-release migration → `data/sources/nflverse.py` *(NEW — do before Phase 3)*
- **Goal:** get the most-recent complete season (2025) into the store as a **projection-calibration
  holdout**, and migrate the frozen `nfl_data_py` weekly/seasonal pull onto nflverse's **current release
  structure** (post-2024 restructure — the real cause of the 2025 404).
- **Do:** read the **new `stats_player` release** directly (not `nfl_data_py`):
  `…/releases/download/stats_player/stats_player_week_{yr}.parquet` (weekly) +
  `stats_player_reg_{yr}.parquet` (seasonal). Map the renamed columns → our `weekly` schema
  (`player_id`→`gsis_id`, `passing_interceptions`→`interceptions`, `team`→`recent_team`); keep
  `season_type` (REG/POST). Append 2025 to `weekly`/`seasonal`. Ingest **2025 `depth_charts`** at the new
  **ISO8601-timestamp grain** (post-2024 they're append-with-timestamp, *not* week-assigned — store the
  timestamp; do not force a `week`). Re-run the **0.8 validator**.
- **Out:** extended `weekly`/`seasonal` (2014–2025) + timestamped `depth_charts_2025`; refreshed
  `data_health.json`. Reconcile 2025 fantasy points against a couple of known box scores.
- **Done:** 2025 weekly/seasonal join cleanly (same scoring reconstructs `fantasy_points_ppr` to ~1e-6);
  validator passes; **2025 added to a calibration-holdout set, NOT to the draft-backtest lockbox** (still
  no 2025 ADP board → `config`; upgrade to a full backtest season once Sleeper ADP lands).
- **Reuse:** `data/sources/nflverse.py` ingest + rename logic; `data/db.py`; the 1.1 scorer for the recon
  check. **Note:** `nfl_data_py` is frozen on the dead `player_stats` path — this step also future-proofs.

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

# Phase 4 — Mean VALUE *(⟳ reframed: consensus-VBD, not edge-seeking)*
*Goal (reframed): a **well-calibrated** value signal for the optimizer, leaning on **consensus
projections → VBD** rather than an own edge-seeking model — plus an explicit rookie model.*

> **⟳ REFRAMED (2026-07-04).** New primary steps: **4.1 consensus-projections ingest** (e.g. FantasyPros
> aggregate — PIT-snapshotted; source is an open decision, `PLAN.md`), **4.2 VBD value board** (reuse
> `valuation/vbd.py`), **4.3 rookie model** (draft capital + landing spot + athletic/college — consensus
> rookie value is thin; §4.4-caution), **4.4 calibration** (reliability/coverage). The GBT / age-curve /
> hier-Bayes / props-shrink steps below are **demoted to optional** — build them only if they measurably
> improve *calibration*, not to beat ADP.

### 4.1 — Consensus-projections ingest (two-track) → `projections/consensus.py` ✅ *(2026-07-05)*
- **Do:** the reframe's VALUE mean. **Live track:** scrape the free FantasyPros consensus board, re-score
  its projected component stats to **full-PPR via our `RuleSet`** (not FantasyPros' scoring), gsis-match,
  PIT-stamp → `consensus_projections`. **Historical track:** no free consensus exists 2014–24, so the
  Phase-2 baseline is the documented consensus **proxy**. `consensus_projection(con, season, as_of)`
  dispatches between them behind one `[player_key, pos, proj_points]` shape.
- **Done:** 2026 board = **528 players, 99% gsis-matched**; our full-PPR ↔ FP FPTS **corr 1.000**; PIT +
  two-track dispatch verified. Retry-guard rejects a transient truncated page. **Reuse:** 1.1 `score_offense`,
  0.4 `match_adp_to_gsis`, 2.2 baseline.

### 4.2 — VBD value board (the frozen contract) → `valuation/value_board.py` ✅ *(2026-07-05)*
- **Do:** consensus mean → **draft-time VBD** (replacement from the **projection** at QB10/RB24/… ranks, not
  realized — the season being drafted has none) → within-position + overall ranks. Freeze the output shape
  `player_key·pos·proj_points·source·vbd·pos_rank·overall_rank` — the contract Phase 5 wraps.
- **Done:** VBD demotes 1-QB QBs from **6→0** in the top-15 vs a raw-points sort; board builds off both
  tracks; contract asserted. **Reuse:** 2.1 `vbd`, 1.4 `replacement_ranks`.

### 4.3 — Rookie value model → `projections/rookie.py` ✅ *(2026-07-05)*
- **Do:** rookies have no prior production but do have **draft capital + landing spot** — a small per-position
  **ridge** (closed-form, dependency-free) on `log(draft_ovr)` + landing-spot env (implied total, target
  competition, pass rate), fit **walk-forward** on strictly-prior seasons. Fills rookies the proxy board
  misses (instead of an ADP punt). **College production deferred** (user decision).
- **Done:** OOS **Spearman +0.62** vs realized rookie points (5 seasons); draft-capital signal −0.59 pooled;
  fills +76 rookies into the 2021 proxy board. **Reuse:** 3.3 player, 3.4 environment, 1.1 scoring.

### 4.4 — Calibration report → `projections/calibration.py` ✅ *(2026-07-05)*
- **Do:** the real done-criterion (*calibration > edge*). Per-position **bias ratio** (Σreal/Σpred),
  monotone **reliability table**, per-position **correction factor** (deflate by the bias); **conditional**
  (played) and **unconditional** (DNP=0 survivorship haircut) universes; dev on `DEV_SEASONS`, verdict read
  **once** on the 2025 holdout.
- **Done:** proxy bias **0.60** (played) / 0.46 (incl. DNP), reliability bin-corr **0.99**, correction pulls
  2022 to **0.96**; **2025 holdout bias 0.58, Spearman +0.57** (consistent OOS). **Reuse:** intern
  bias-statistic idea, 1.1 `season_points`.

> **Optional / demoted (build only if they measurably improve *calibration*, not to beat ADP):** GBT
> component models (`projections/gbt.py`, xgboost/lightgbm + nested CV), Tango **age curves**
> (`age_curves.py`), **hier-Bayes** thin-sample priors (`hier_bayes.py`, PyMC), **props-anchored shrinkage**
> (`market_shrink.py`, once a props source lands). Deferred per the 2026-07-04 reframe.

---

# Phase 5 — Distributional projections *(⟳ PROMOTED to core)*
*Goal: the full distribution F(points), not just the mean — the prerequisite for floor/ceiling, variance
preference, and the season simulator.*

> **⟳ PROMOTED (2026-07-04).** This is **the one value-side thing we build ourselves** (consensus/ADP are
> point estimates) and it **powers the per-round risk dial** — no risk feature without it. For the MVP,
> **trim** to the minimal per-player variance/distribution the dial needs; the full 5.1–5.5 stack comes later.

> **✅ BUILT (2026-07-05) — full 5.1–5.5 stack.** **Grain = season-total only** (what the draft dial +
> optimizer consume); a **weekly-grain distribution is deferred to future work** (start/sit; folds into the
> Phase-10 season sim). **Method deviations (accepted with the user, no new deps):** 5.1 uses statsmodels
> linear `QuantReg` (not XGBoost); 5.4 uses a scikit-learn logistic discrete-time hazard (not `lifelines`) —
> both right for ~a-few-hundred player-seasons/position under the no-overfit rule. **Future intent
> (documented, not scheduled): adopt XGBoost quantile regression (5.1) and a `lifelines` survival model
> (5.4) if the sample or residual signal justifies the extra flexibility.** Assembler `distribution.py`
> composes the four factors into a Monte-Carlo cloud → frozen `player_distributions` contract. Calibration:
> conditional (available cohort) 2025 coverage **76% ≈ 80%**; unconditional full-board **44%** = **role/depth
> attrition** the injury-only model doesn't capture → **future work: a role/depth survival haircut beyond
> injury.** Findings: `findings.md` "Phase 5" (2026-07-05).

### 5.1 — Quantile regression → `projections/quantile.py` ✅
- **Do:** ~~XGBoost **quantile loss**~~ → **built as a per-position linear statsmodels `QuantReg`** of realized
  season points on the calibrated mean (season grain; the no-overfit rule beats XGBoost on ~300 rows/pos).
  P10/P25/P50/P75/P90 per player. *(Future: revisit **XGBoost quantile loss** and a **weekly grain** if warranted.)*
- **Out:** `projections/quantile.py` (`quantile_projection`); **Done:** quantiles ordered (crossing repaired
  by sort), median slope ≈1.10, band fans with level 3/4 pos. **Reuse:** `statsmodels`.

### 5.2 — Conformal prediction → `projections/conformal.py` ✅ *(CQR; 2025 holdout coverage 70%→73%)*
- **Do:** wrap projections in **split/conformalized quantile regression** for distribution-free **calibrated**
  intervals; validate empirical coverage.
- **Out:** `projections/conformal.py` (`conformal_intervals`); **Done:** P90/P10 coverage within tolerance of
  90/10% OOS. **Reuse:** 5.1; `scikit-learn`.

### 5.3 — Boom/bust variance (GARCH-like) → `projections/variance.py` ✅ *(weekly CoV + boom/bust; corr(boom,CoV) −0.37)*
- **Do:** model **week-to-week variance** itself (volatility clustering); classify consistency vs boom/bust;
  per-player variance estimate for the covariance/sim.
- **Out:** `projections/variance.py` (`week_variance`, `boom_bust_score`); **Done:** high-variance players
  flagged match intuition; variance predicts realized weekly std OOS. **Reuse:** weekly panel; `statsmodels`.

### 5.4 — Injury survival/hazard → `projections/injury.py` ✅
- **Do:** built as a **logistic discrete-time availability hazard** (a logit on person-period player-week rows
  *is* the survival model, the right tool for a 17-week horizon vs. continuous-time Cox) with age/position/
  prior-avail/week covariates → **Beta-Binomial games-played distribution** (over-dispersion ρ keeps the
  lost-season tail). *(Future: a **`lifelines`** continuous-time/recurrent-event survival model if the extra
  flexibility is justified.)* Feeds handcuff valuation + season sim.
- **Out:** `projections/injury.py` (`availability_projection`, `sample_games`, `fit_availability`); **Done:**
  RB least available (matches actuarial); ρ=0.33; produces a distribution, not a point. **Reuse:** 0.2 injuries;
  `scikit-learn`. *Limitation: grid conditions on ≥1 appearance → no role/depth attrition (documented; future work).*

### 5.5 — Expected-utility (floor/ceiling) scoring → `valuation/utility.py` ✅ *(mean-variance CE = E[Y]−λ·Var[Y]; assembler → `player_distributions`)*
- **Do:** position-dependent **utility function** over each player's distribution — concave (floor) for
  starters, convex (ceiling) for late dart-throws — making "consistency vs volatility" concrete.
- **Out:** `valuation/utility.py` (`expected_utility`); **Done:** utility ranks a safe floor above a volatile
  bust for a starter slot, and inverts for a bench dart. **Reuse:** 5.1–5.3 distributions.

---

# Phase 6 — Personalization intelligence *(⟳ reframed from ADP-bias mining)*
*Goal (reframed): map **where ADP is soft** — not to "beat" it, but to tell the app **how cheaply a user
can indulge a preference** ("good news, you can wait a round on your guy").*

> **⟳ REFRAMED (2026-07-04).** Same machinery (ADP-alpha panel → cross-sectional regression → scorecard),
> new use: the output is a **softness map** feeding the cost report and reach-budget advice, not an
> edge-to-beat-ADP. Note FFC ADP is soft money; best-ball ADP is the sharper reference (caution §4.5).

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

# Phase 7 — Opportunity-adjusted projection *(⟳ reframed from "causal")*
*Goal (reframed): a **skill ÷ opportunity** decomposition used as a **feature** for re-projecting role
changes — the practical 80%, without the causal-inference claims.*

> **⟳ REFRAMED (2026-07-04).** **Drop the causal counterfactual framing** — "how would X do in offense Y"
> is **not identifiable** from observational NFL data; presenting it as causal oversells it. Keep the
> tractable core (intrinsic-skill latent × situation multiplier) as a projection feature; validate on
> held-out moves; never present a causal claim untested OOS.

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

# Phase 9 — Valuation & draft policy *(⟳ + constrained optimizer + cost report)*
*Goal: turn the value signal + risk into draft decisions via a **constrained optimizer**, and **price the
cost of personalization** against the benchmark team.*

> **⟳ REFRAMED (2026-07-04).** Add two first-class steps (the AlphaThena optimizer analog): a
> **constrained draft optimizer** — maximize **consensus-VBD value** subject to hard excludes
> (never-draft), soft tilts (± rounds), archetype priors, and the per-round risk dial, planning around
> **ADP availability** — and the **cost-of-personalization report** (tracking-error decomposition vs the
> consensus-VBD-optimal team; the old "structural-alpha" number, repurposed). See `docs/PERSONALIZATION.md`.

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

# Phase 11 — Draft engine *(⟳ opponent model = core & Brier-verifiable; CFR dropped)*
*Goal (reframed): predict **draft flow** — who survives to each pick — with a **behavioral opponent
model**, scored against real completed drafts.*

> **⟳ REFRAMED (2026-07-04).** The opponent model moves from unverifiable frontier flex to **core,
> verifiable infrastructure**: its job (who's available at each pick) has **hard ground truth**, Brier-
> scorable over thousands of picks. New/primary steps: **11.1 behavioral opponent model** (positional
> runs, reaches for favorites, hometown/name-brand bias, rookie hype, K/DST panic, handcuffs — replacing
> "ADP + Gaussian noise"), **11.2 per-pick availability distributions** (survival over simulated flow),
> **11.3 realistic mock** (configurable opponent personalities). **✗ Drop CFR** (a snake draft is
> near-perfect-information — CFR is a category error). **◔ Deprioritize heavy live MCTS** (unverifiable vs
> good greedy value-based drafting; live-latency risk). Auctions/self-play = later. **Needs real
> completed-draft data (Sleeper) — open decision, `PLAN.md`.**

### 11.1 — Live opponent modeling → `draft/opponent_model.py`
- **Do:** per-opponent **Bayesian posterior over their board** (Dirichlet/categorical over positions+players),
  updated each pick; trained from league history + mocks; enables **exploitative** play.
- **Out:** `draft/opponent_model.py` (`OpponentModel.update/predict`); **Done:** predicts held-out league picks
  better than ADP-noise. **Reuse:** 1.2; mock data (14.7).

### 11.2 — MCTS draft engine → `draft/mcts.py` ✗ **BUILT & DROPPED** *(2026-07-19, Session D research gate)*
- **Built:** a **determinized-UCT** (PIMC / SO-ISMCTS) over draft states — top-K greedy candidates as actions,
  the ADP+noise room determinized per iteration, greedy rollouts, portfolio-CE leaf value, UCB1 selection
  (`draft/mcts.py::mcts_pick`/`mcts_pick_fn`). **Reused:** 9.x greedy + `portfolio_value`, 1.2 sim, 10.x sim.
- **Gate (`steps/phase11_2_mcts.py`, `analysis/phase11_mcts.json`):** vs the greedy over 9 DEV seat-seasons
  (2020–22 × slots 1/6/10, k=5, 100 iters). **Beats greedy IN-OBJECTIVE** (Δ portfolio CE +77, CI[+47,+107],
  89 %) **but NOT on realized OOS points** (Δ +32, CI[−90,+145]∋0, 56 %) at 8.5 s/pick. **Verdict: DROP** —
  a snake draft is near-perfect-info and the objective's OOS link is unresolvable on ~10 seasons, so harder
  search buys no realized edge. Kept in-repo like Phase 7 / props / CFR. **11.5 self-play RL stays roadmap
  a fortiori.** *(User chose to build the benchmark rather than defer the gate.)*

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

# Phase 12 — NLP / live-news pipeline ✅ **COMPLETE** *(2026-07-13, Session C — a qualified KEEP)*
*Goal: convert unstructured news into timestamped, PIT structured signal — the freshest-information edge.*

> **✅ DONE (2026-07-13).** The gate said a **qualified yes**: the **injury** signal is a real, significant
> KEEP; the **depth-chart** signal a DROP. **AI on the edges, deterministic core** was literalized — the LLM
> (a gated `ClaudeClient`, Haiku 4.5, behind `ANTHROPIC_API_KEY`) only extracts a structured fact; the
> deterministic core prices the impact (a DEV-calibrated availability multiplier). The default extractor is
> offline rules (runs in tests) so the core stays LLM-free. See `findings.md`/`glossary.md` (Phase 12).

### 12.1 — Source scrapers/streams → `news/sources.py` ✅ *(2026-07-13 — the PIT news stream: 18k injury + 16k depth events, native-gsis; forward-only RSS)*
- **Do:** robust collectors for beat writers, injury reports, depth charts, **inactives**, transactions —
  timestamped, deduped, rate-limited.
- **Out:** `news/sources.py`; **Done:** continuous capture; each item has a reliable `captured_at`. **Reuse:** 0.6.

### 12.2 — LLM extraction → `news/extract.py` ✅ *(2026-07-13 — offline rules default + gated `ClaudeClient` seam + deterministic `structured_injury_signal`)*
- **Do:** **use Claude** to extract structured fields from text — role change, projected snap/route share,
  injury severity/timeline, "coachspeak" decoded — into PIT features with confidence.
- **Out:** `news/extract.py` (`extract_signal`); **Done:** extracted fields agree with hand-labeled samples;
  features are timestamped. **Reuse:** Claude API (see `/claude-api`); 12.1.

### 12.3 — Event-study → `news/event_study.py` ✅ *(2026-07-13 — injury exploitable lag +5.86 pts/start sig; depth-chart change DOES NOT separate → DROP)*
- **Do:** measure how ADP/props move on news and the **exploitable lag**; quantify which news types move markets.
- **Out:** `news/event_study.py`; **Done:** documented lag/impact per news type. **Reuse:** 0.4/0.5 markets; 12.2.

### 12.4 — Signal validation → `news/validate.py` ✅ *(2026-07-13 — news-aware forecast beats injury-blind 13.1 +3.4→4.3 pts/pw designated, 6/6 DEV; injury KEEP, depth drop)*
- **Do:** does an extracted signal improve projections/decisions OOS on the walk-forward? Kill signals that don't.
- **Out:** `news/validate.py`; **Done:** only validated signals feed the model. **Reuse:** 1.3, 1.5.

---

# Phase 13 — In-season co-pilot [CORE — season breadth]
*Goal: the season-long decision engine — the draft is only ~1 of 17+ decisions.*

### 13.1 — Weekly re-projection → `inseason/reproject.py` ✅ *(2026-07-12)*
- **Do:** update player distributions each week (state-space/Kalman flavor) with new results + news (12.x).
- **Out:** `inseason/reproject.py` (`reproject_week`); **Done:** weekly forecasts beat preseason-static OOS.
  **Reuse:** 5.x, 12.x. Create the **inseason** package.
- **Design note (2026-07-11, from the S6/Phase-13-before-12 reorder):** Phase 13 is now built *before*
  Phase 12 exists. Build the state-space update with a generic news-feature slot in its input contract
  (even though nothing populates it yet) so that if Phase 12 survives its own keep-or-drop gate, it plugs
  in as an added feature later rather than triggering a rebuild of 13.1.
- **DONE (2026-07-12):** a **scalar Kalman filter** on each player's per-week level (`preseason_prior` →
  `reproject_week` → `RestOfSeason`); prior worth `PRIOR_WEEKS=5` pseudo-obs, `process_var` optional
  random-walk; **PIT by construction** (reads only weeks ≤ t); the **`news` slot is wired and no-ops**
  (Phase-12 hook honored). **Beats the static preseason level OOS in 6/6 DEV seasons, +0.396 ppg/wk MAE
  gain, season-block CI [+0.32,+0.48]** (`steps/phase13_1_reproject.py`; `analysis/phase13_reproject.json`).

### 13.2 — Start/sit optimizer → `inseason/lineup.py` ✅ *(2026-07-12 — co-pilot PASS; variance tilt = opt-in finding)*
- **Do:** weekly lineup optimization under the **win-probability objective** + matchup + leverage (10.3).
- **Out:** `inseason/lineup.py` (`optimal_lineup`); **Done:** beats projection-max lineup on simulated win%.
  **Reuse:** 9.4, 10.x.
- **DONE (2026-07-12):** the **done-bar that PASSES is the co-pilot** — mean-max on 13.1's *re-projected*
  means beats *set-and-forget* (frozen preseason) on realized points **6/6 DEV, +2.08 pts/lineup-week**
  (CI[+1.56,+2.54]). **FINDING:** the win-probability **variance tilt** (10.3 leverage at the lineup grain)
  does **not** beat mean-max OOS even for big underdogs (0/6; a single legal swap barely moves the ~35-pt
  team sd — consistent with Phase-10.3, where leverage only bit at *whole-team* 1.6× spread changes). So
  `optimal_lineup` **default = `objective="mean"`** and the tilt is retained **opt-in** `objective="win"`,
  off by default (the Phase-7 / props "kept, not the default" pattern). `steps/phase13_2_lineup.py` reports
  both; `analysis/phase13_lineup.json`.

### 13.3 — Waivers/FAAB → `inseason/waivers.py` ✅ *(2026-07-12 — pragmatic FAAB; rigor owed to 15.4 / T9)*
- **Do:** sequential budget auction — **bandit + auction theory**, bid-shading, the option value of holding budget.
- **Out:** `inseason/waivers.py` (`faab_bid`); **Done:** beats naive %-of-budget bidding in sims. **Reuse:** 11.4.
- **⚠ stale reuse pointer:** "11.4" was **auction-draft support**, which was **deferred out of Phase 11 into
  Phase 15.4** — `draft/auction.py` does **not** exist. Per user decision (2026-07-12), 13.3 shipped the
  **pragmatic** bidder now; the rigorous equilibrium/DP version is owed → **`docs/TECH-DEBT.md` T9** (15.4).
- **DONE (2026-07-12):** pure `faab_bid(value, budget_remaining, weeks_remaining, *, value_scale, opp_bids,
  option_kappa, shade_frac)` — (1) marginal rest-of-season value (over replacement, from 13.1) → `value_scale`
  willingness-to-pay, (2) **rationed** by the option value of budget `1/(1+κ·(weeks−1))`, (3) **first-price
  shaded** to `argmax_b (value−b)·P(win|b)` vs a belief about the field. Done-bar `faab_skill` /
  `steps/phase13_3_waivers.py`: a **mixed-field** waiver sim (sharp agent vs a naive %-of-budget bidder, rest
  alternating — user decision) → the sharp agent acquires more realized value **5/6 DEV, +30.0/szn CI
  [+21.7,+38.8]**, higher value-per-dollar. **Key modeling finding:** score only a team's **top-`n_useful`=4**
  pickups (diminishing returns) + bid **marginal-over-roster**, else the objective rewards *volume* and naive
  aggression wins (0/6 → 5/6). `analysis/phase13_waivers.json`.

### 13.4 — Streaming bandit → `inseason/streaming.py` ✅ *(2026-07-12 — matchup-streaming beats static-hold 6/6 DEV on DST)*
- **Do:** explore/exploit over the waiver pool for QB/TE/DST streaming.
- **Out:** `inseason/streaming.py` (`stream_pick`); **Done:** beats static-hold in sims. **Reuse:** 5.x.
- **DONE (2026-07-12):** pure, position-agnostic `stream_pick(proj, *, held, switch_margin, n_seen, ucb_c)` —
  a contextual **bandit** over the waiver pool: greedy **exploit** on `matchup_projection = own +
  (opp_allow − league_mean)` (own scoring level + opponent-offense generosity, both **empirical-Bayes** shrunk
  toward the prior season via `_shrink`, `PRIOR_GAMES=4` — the soft **explore**; optional `ucb_c` optimism
  bonus for explicit explore, off by default), with a **switch-margin hysteresis** (`SWITCH_MARGIN=1.0`) so we
  don't churn the wire for a trivial upgrade. Done-bar `streaming_skill` / `steps/phase13_4_streaming.py`,
  demonstrated on **DST** (strongest matchup signal + real `dst_weekly_points` scores; schedule from
  `game_lines`): `n_managers=300`, each a random 8-unit slice of the waiver-tier defenses (outside top-10 by
  prior-season points) → matchup-streaming beats **static-hold** (roster the preseason-best unit, start every
  week, eat its bye) **6/6 DEV, +1.46 DST pts/wk CI[+0.88,+2.09]**. **Signal isolation (13.3 anti-churn lesson
  applied):** a **random-streaming** control (random available unit each week) — matchup beats random **5/6**
  (2018 miss +0.2; the opponent signal is real but modest) — proving the *matchup signal*, not just the churn,
  adds value. **Scope:** DST demonstration; `stream_pick` is position-agnostic (QB/TE would feed 13.1
  re-projected means as `proj`) — a documented extension, not built (the 13.2 "one passing bar + noted
  extension" pattern). PIT throughout. `analysis/phase13_streaming.json`.

### 13.5 — Trade finder → `inseason/trades.py` ✅ *(2026-07-12 — market-making; proposed trades raise both teams' sim win% 6/6 DEV)*
- **Do:** value trades by **surplus**, surface **mutually-beneficial** deals (market-making), flag buy-low/
  sell-high on model-vs-perception gaps.
- **Out:** `inseason/trades.py` (`evaluate_trade`, `find_trades`); **Done:** proposed trades raise both teams'
  simulated win% (or yours, for buy-low). **Reuse:** 10.x values.
- **DONE (2026-07-12):** three pure kernels. `lineup_value(values, pos, slots)` = a roster's value counting
  **only its optimal starting lineup** (reuses the 13.2 greedy `_fill`) — a player's worth is his *marginal*
  starting-lineup contribution, ~0 past positional need (the 13.3/13.4 diminishing-returns lesson made
  positional). `evaluate_trade(...)` prices a swap as the *change* in each side's `lineup_value`; `mutual` iff
  **both** gain > `ACCEPT_MARGIN=5` (anti-churn hysteresis). `find_trades(my, opponents, values, *, market,
  rank)` = the **market-maker**: searches each opponent's surplus (`_benched`) for mutual **1-for-1 / 2-for-1**
  legal deals that arbitrage **complementary positional surpluses**, ranks by the **worse-off side's** gain
  `min(mine, theirs)` (`rank="balanced"` — the fairest win-win a two-signature trade needs; `rank="mine"` is a
  self-interested skim), and — given a `market` perception — tilts toward **selling high / buying low** on the
  model-vs-market `edge`. Done-bar `trade_skill` / `steps/phase13_5_trades.py`: `n_leagues=40` snake-drafted
  **imbalanced** leagues/season, `n_focal=4` maker seats run `find_trades`, execute the top proposal, and
  re-simulate the **Phase-10 MC season** (shared player-weekly cache + fixed schedule → pre/post differ *only*
  by the two swapped rosters, a paired low-variance comparison). **Both** teams' mean playoff-prob **rise 6/6
  DEV** — maker season-block CI **[+0.014,+0.021]**, partner **[+0.012,+0.021]**, weaker side **[+0.011,+0.019]**.
  **Signal isolation (13.3/13.4 anti-churn control):** a **random-trade** control lifts both sides ~never
  (~0–10%); proposed trades beat it **6/6**, so it is the *surplus signal*, not roster churn. **Key correction:**
  ranking by the maker's own gain only cleared a *marginal* partner floor (worse side died in MC noise) →
  ranking by `min(maker, partner)` makes both sides gain robustly — the objective must reward *mutual* benefit
  or the maker just skims. **Scope:** value currency = preseason model ros mean (self-consistent with the sim →
  PIT-trivial); in-season this `values` slot is 13.1's re-projected mean (fed in, the 13.4→13.1 pattern). Sim
  trades **1-for-1** (count-neutral); **2-for-1** consolidation supported by kernels + unit-tested, not simmed.
  Gate = **season-block bootstrap on each side's gain** (per-season two-CI test underpowered at n≈14–48/season;
  2018 partner grazes 0, echoing 13.4's 2018 miss). PIT throughout. `analysis/phase13_trades.json`.
  **→ Phase 13 / S7 COMPLETE.**

---

# Phase 14 — The app *(⟳ Streamlit/Gradio MVP first; Next.js later)*
*Goal: wrap the model in a personalized product — starting as a **Python (Streamlit/Gradio) MVP**, not a
production web stack.*

> **⟳ REFRAMED (2026-07-04).** **Highest-leverage engineering decision: do NOT build FastAPI + Next.js to
> use this yourself.** Build the first interface in **Streamlit/Gradio** (sliders, upload, live output in
> days, zero frontend engineering) to validate the personalization idea. Expose the **Autopilot +
> Co-pilot** tiers over the constraint object with defaulted sliders + the "one-line why." FastAPI +
> Next.js + live-draft sync + widget become a later **"I have users and want polish"** step. **Own the
> contracts, delegate the interiors.**

### 14.1 — Backend → `app/backend/`
- **Do:** **FastAPI** service over DuckDB/Postgres exposing projections, boards, sim, valuations; auth for
  league-mates. Create the **app** package. **Include the per-player endpoint** that powers the
  `PLAYER-VIEW.md` cards: returns the 8 bar values + **overall & within-position percentiles** + the
  confidence flag (`source`/`no_prior`), read straight from the frozen contracts.
- **Out:** `app/backend/` (`main.py`, routers); **Done:** endpoints return model outputs; the per-player
  bar endpoint returns dual-baseline percentiles; auth works. **Reuse:** all model packages.

### 14.2 — Personalization layer → `app/backend/personalization.py`
- **Do:** per-user **archetype prefs, per-factor over/under-weights, draft style, anchor picks** → a
  personalized board from the same model; **always show vs the pure baseline** (anti-bias guardrail).
- **Out:** `app/backend/personalization.py`; **Done:** different user configs yield sensibly different boards.
  **Reuse:** 2.x, 9.x.

### 14.3 — Frontend → `app/frontend/`
- **Do:** **Next.js + TypeScript** UI — board, **the interactive player card + per-player deep page (full
  spec: `docs/PLAYER-VIEW.md`, 2026-07-23)**, config panel, draft view. Player card = a two-tier
  interaction: **hover → 5-bar overview** (bar + number), **click → `/player/<key>` deep page** (all 8
  bars + one-line why + weekly-distribution band + situation context). Bars are quasi-meters over the
  frozen contracts (`value_board`, `player_distributions`, Phase-6 durability, Phase-3 opportunity,
  Phase-16 situation-change); **green = good for the drafter always** (risk bars inverted), **dual
  baseline** (overall primary + within-position secondary), Phase-16 bar walled-off & visually distinct,
  a confidence flag on rookie/`no_prior`/`proxy` rows.
- **Out:** `app/frontend/`; **Done:** renders a live board + hover cards + deep pages from the API.
  **Reuse:** 14.1 API (per-player endpoint returns 8 bar values + overall/positional percentiles + the
  confidence flag), all frozen contracts, `docs/PLAYER-VIEW.md`. (Installs Node.) **Dep:** bar #6
  needs Phase 16 (its only new-signal dependency; all other bars already frozen).

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

## Phase 14 — decision-support surfacing + consolidated UI *(added 2026-07-23; "app strictly last")*
*All UI deferred out of the engine phases lands here: the 16.6 Beta Lab tab, the 16.12 availability/reach-risk
readout, the 16.15 personality selector, the 17.3 custom-settings form, the `docs/PLAYER-VIEW.md` cards. Plus
five broadly-useful readouts (E–I) that read **already-frozen** machinery — near-zero modeling risk, big legibility
win for novice and sharp alike. Done-bar for all: **renders correctly reading frozen outputs + unit-tested wiring**
(no new modeling gate); H is descriptive/face-validity.*

### 14.E — Tier-cliff / scarcity board → `app/` (Streamlit 14.1)
- **Do:** show positional **value cliffs** on the board ("after these 3 RBs, a big VBD drop") from the
  `positional_cliff` term already built for 9.1 scarcity; annotate each position's next cliff distance.
- **Out:** a board overlay/column; **Done:** cliffs render + match `positional_cliff`. **Reuse:** 9.1
  `RiskModel`/`positional_cliff`, `value_board`.
### 14.F — Roster-construction risk readout → `app/` (Streamlit 14.1)
- **Do:** a live "your team" panel — **bye-week clustering** ("4 starters off in Wk 11"), **team
  over-concentration**, **handcuff gaps** ("you have Bijan, not his backup — option value X").
- **Out:** a roster panel; **Done:** the three risks compute for a drafted roster. **Reuse:**
  `valuation/roster_risk.py`, `valuation/handcuff.py` (8.5), nflverse bye/team data.
### 14.G — Uncertainty-aware board → `app/` (Streamlit 14.1)
- **Do:** render **ranges, not false-precise ranks** — each player's `q10..q90` band + a coin-flip flag when
  adjacent players overlap; the PLAYER-VIEW confidence flag on rookie/`no_prior`/`proxy` rows.
- **Out:** a distribution-aware board rendering; **Done:** bands + flags show from frozen `player_distributions`.
  **Reuse:** Phase-5 `player_distributions`, PLAYER-VIEW confidence indicator.
### 14.H — Playoff-week SOS lens → `app/frontend/` (14.3)
- **Do:** each player's weeks-15–17 matchup difficulty, keyed to the league's playoff weeks (`LeagueFormat`),
  from opponent points-allowed (the 13.4 machinery).
- **Out:** a playoff-SOS column/lens; **Done:** computes for the league's playoff weeks, **descriptive/labeled**
  (a schedule lens, no backtested-edge claim). **Reuse:** `inseason/streaming.py` opp-allowed, `LeagueFormat`.
### 14.I — Draft grade / team report → `app/backend/` + `app/`
- **Do:** after any mock, grade the roster vs the room — projected wins/title odds (Phase-10 sim), positional
  strengths/holes, biggest reach & best value (cost report).
- **Out:** a post-draft report; **Done:** grade + report render for a completed mock. **Reuse:** `simulation/`
  (Phase 10), `valuation/cost_report.py`, 14.7 mock output.

---

# Phase 15 — Multi-format (roadmap) → ✅ **CORE COMPLETE** *(2026-07-13, Session C: 15.2/15.3/15.4; dynasty deferred)*
- ◔ **15.1 Dynasty/keeper** → `formats/dynasty.py`: multi-year asset pricing (closest to your equity work).
- ☑ **15.2 Best-ball** → `formats/bestball.py`: **DONE 2026-07-13** — variance-is-good (ceiling beats mean 6/6 DEV, weekly CoV). no in-season management; pure draft + variance.
- ☑ **15.3 DFS GPP** → `formats/dfs.py`: **DONE 2026-07-13** — leverage beats chalk 6/6 (MECHANICS; no free salary/ownership feed). ownership/leverage, game stacks, field-relative scoring.
- ☑ **15.4 Auction drafts** → `draft/auction.py` (absorbed from Phase 11.4): **DONE 2026-07-13** — auction values + the exact `endgame_cap` $1-endgame continuation + winner's-curse `auction_bid` + `nominate`; budget-state bidder beats naive budget-splitting 6/6 DEV (+66→+128 lineup pts). **Discharges TECH-DEBT T9** (`faab_bid` now consumes `endgame_cap`).
- *15.1 dynasty deferred (user scope, Session C); the rest done.*

---

# Phase 16 — Situation-Change Beta Lab *(new 2026-07-19; scoped, not yet built — awaiting go-ahead)*
*Goal of the phase: test whether ADP systematically misprices offseason "changed situation" events (team
change, QB change, teammate competition change, coaching/scheme change) — a hypothesis the user believes
consensus over/under-reacts to year after year — and, whatever the answer, surface it on a **walled-off,
read-only tab**, never wired into the frozen optimizer/VBD/cost report. This is **not** a rerun of Phase 7
(which tested whether a team-fixed-effect improves mean *projection accuracy* and was dropped); it's an
extension of Phase 6's already-validated ADP-alpha mining (the same machinery that found DURABILITY
under-priced) with new features Phase 6.2 never tested. Full scoping rationale + the 4 answered
design questions: `PLAN.md`, 2026-07-19 entry.*

### 16.1 — Team-change + new-starting-QB ADP-alpha extension → `adp/panel.py`, `adp/regression.py` — ✅ **DONE 2026-07-24 (NULL)**
*Result: `team_changed` coef −2.5 VOR/SD (p_fdr 0.82), `new_starting_qb` −0.1 (p_fdr 0.98) — both honestly
ruled out; the crowd prices offseason team/QB changes right for value. PIT catch: derived team-of-record
from `weekly` Week-1 (the ADP board `team` column leaks an end-of-season crosswalk). `SITUATION_FEATURES`
walled off from the pinned frozen `FEATURES`; Phase-6 DURABILITY drift check reproduces +14.6. Done-bar
`steps/phase16_1_situation_alpha.py`, `analysis/phase16_1_situation_alpha.json`, `tests/test_phase16.py`.*
- **Do:** add `team_changed` (offseason team differs from prior season, trade/FA/waiver — free off the
  existing panel) and `new_starting_qb` (team's QB1 by pass attempts changed year-over-year, >50%
  team-attempts threshold to count as "starter") to the Phase 6.1 panel; refit 6.2's regression + 6.3's
  BH-FDR scorecard on the enlarged feature set.
- **Out:** updated `adp/panel.py` (`FEATURES`), `adp/regression.py`, `adp/scorecard.py` outputs.
- **Done:** each new feature reports a season-block-bootstrap CI + BH-FDR-adjusted p-value + sign-stability
  %, same discipline as DURABILITY — survive or honestly drop, no threshold moved after seeing the result.
- **Reuse:** `adp/panel.py`, `adp/regression.py`, `adp/scorecard.py` (Phase 6) wholesale — only the feature
  set changes.

### 16.2 — Competition-change signal, dual-sourced → `adp/panel.py` — ✅ **DONE 2026-07-24 (BOTH WASH OUT)**
*Result: `competition_change_roster` (weekly usage + `draft_picks`, 25 %) coef −9.9 VOR/SD and
`competition_change_depth` (`depth_charts` new-top-2 entrant, 72 %) +9.8 — **opposite signs, neither
survives FDR** (both p_fdr 0.087) → both wash out, echoing Phase 12.3's depth-chart null. Depth used
`depth_charts` (2014–24), NOT `depth_charts_ts` (2025-only). Done-bar `steps/phase16_2_competition.py`,
`analysis/phase16_2_competition.json`.*
- **Do:** build **two** independent operationalizations of "a same-position teammate arrived/departed" and
  mine both through the same 16.1 pipeline: (a) **roster-turnover-derived** — via `draft_picks` + team
  roster deltas year-over-year, thresholded on the departing/arriving player's prior-season usage; (b)
  **depth-chart-derived** — reusing `depth_charts_ts`, the same source and rank-delta logic Phase 12.3
  already used for in-season promo/demo (which found no separation there).
- **Out:** two new panel features (`competition_change_roster`, `competition_change_depth`) mined and
  reported side by side.
- **Done:** an honest empirical answer to whether roster-turnover avoids Phase 12.3's null result, or
  whether both wash out — not assumed either way.
- **Reuse:** `draft_picks`, `depth_charts_ts` (already ingested); Phase 12.3's rank-delta logic as a
  starting point for (b).

### 16.3 — Playcaller/coaching history table → `reference/coaches.csv` — ☑ **DONE (2026 half signed off 2026-07-24; MERGED onto the frozen schema 2026-07-25)**
*The **2026 half is DONE and user-signed-off** at `confidence=high`. User reviewed the Claude draft across
**three correction rounds**; the final file is preserved verbatim at
`reference/coaches_2026_signed_off_2026-07-24.csv` (32 rows, all 32 teams, season 2026). **The merge onto
the frozen schema is ☑ DONE (2026-07-25)** — whitespace stripped, reordered to `season,team,…`,
`confidence=high` added, `in_house` backfilled on the historical rows, the 7 stale low-confidence 2026 rows
replaced. The merged file is `reference/coaches.csv`; the signed-off original is retained verbatim.*
- **Do:** Claude drafts a table (HC/OC · team · seasons · `is_playcaller` flag · ambiguous-case notes) via
  web research, covering DEV-window playcaller changes (2014–2022) plus this year's relevant hires;
  **user reviews and corrects before it's used anywhere downstream.** Scope: the ~10–15 fantasy-relevant
  moves/year, not a comprehensive scrape of all 32 teams' full staff history.
- **Out:** a small, versioned, human-approved reference table.
- **Done:** ☑ **for 2026** — user explicitly signed off 2026-07-24 at `confidence=high`. ☐ **for the
  historical half** — see 16.3b, which 16.4 hard-depends on.
- **Reuse:** none for the playcaller column — this is the one piece with no existing free source. **BUT
  (found 2026-07-24):** `pbp.home_coach`/`away_coach` yields a free, exact, PIT **head-coach**-per-team-season
  table for **all 352 team-seasons 2014–2025** — insufficient alone (HC ≠ playcaller, as previously checked)
  but a valid **scaffold** that reduces the research burden to the OC/playcaller column only.

**Validation performed on the signed-off 2026 file (all PASS):** 32/32 teams · no empty cells · no person
holding a job on two teams · `play_caller` always ∈ {`head_coach`, `offensive_coordinator`} · `hc_calls_plays`
agrees with `play_caller` on all 32 rows · **all 11 inter-team move chains cross-reference** (Stefanski
CLE→ATL, Harbaugh BAL→NYG, Monken BAL→CLE, Nagy KC→NYG, Daboll→TEN, Petzing ARI→DET, M. LaFleur LAR→ARI,
Doyle CHI→BAL, Kubiak SEA→LV, McDaniel MIA→LAC, Robinson ATL→TB) · the 11 unplaced names are all outgoing
coaches (expected). Only residue = cosmetic trailing whitespace on 5 name fields (BAL ×2, LV, PHI ×2) —
**strip on ingest.**

**⚠ Three aggregates were never externally verified** (internal consistency ≠ factual accuracy; recorded so
a future reader knows the boundary of what was checked): **10 new head coaches** for 2026 (2025 cycle had 7;
2022 hit ~10, so high but not impossible) · **Mike McDaniel leaving the MIA head-coaching job to be LAC's
OC** (internally consistent across both rows, but a sitting HC taking a coordinator role is rare) · **56 %
of HCs calling plays** (18/32, vs a ~40–50 % norm). User signed off with these flagged.

**★ FROZEN SCHEMA for `reference/coaches.csv` (user decision 2026-07-24 — `change_from_prev` is DROPPED):**
```
season, team, head_coach, offensive_coordinator, play_caller, hc_calls_plays, in_house, confidence, notes
```
- **`in_house` (replaces `change_from_prev`)** — semantics **reverse-engineered and verified 32/32** on the
  signed-off file: **"the season's play-caller was already on this team's staff the previous season."**
  `in_house=0` ⇒ a **new playcaller regime** ⇒ **a 16.4 transport event.** Note this is *not* the same as
  "new to the play-calling role": **DEN 2026 is `in_house=1` yet a genuinely new regime** (Payton hands the
  offense to Davis Webb, already the QB coach) — so `in_house=0` is a *sufficient* but not *necessary*
  trigger. 16.4 should treat `in_house=0` as the primary event set and note the internal-promotion cases.
- **Ingest transform:** strip whitespace on all name fields · reorder to `season,team,…` · add
  `confidence` (=`high` for all 32 signed-off 2026 rows) · **backfill `in_house` for the 16 historical
  rows** (they currently carry `change_from_prev`, which is being dropped — derive `in_house` per row) ·
  replace the 7 stale low-confidence 2026 rows with the signed-off 32 · keep the `#` header comments.

### 16.3b — Historical playcaller regimes — ☑ **BUILT 2026-07-25; ★ USER REVIEW GATE OPEN**
*The signed-off file is **2026-only**. 16.4 fingerprints a playcaller from their **past** regimes and
transports that onto a new roster — so 2026 supplies **destinations, not sources**. **23 of the 32 incoming
2026 playcallers have no historical row at all** (Mike LaFleur, Coen, Kubiak, Slowik, Moore, Monken,
McDaniels, Robinson, O'Connell, Canales, Z. Taylor, Schottenheimer, Webb, Petzing, Caley, Steichen, Reich,
Mannion, McCarthy, Fleury, Doyle, Brady, Blough), and the 9 that do (Shanahan, McVay, Reid, Stefanski,
B. Johnson, M. LaFleur, Nagy, McDaniel, Daboll) average ~1 season each. **User decision 2026-07-24 = the
FULL historical build:***
- **Do:** (a) auto-scaffold `head_coach` for all 352 team-seasons 2014–2025 from `pbp` (free, exact, PIT);
  (b) research the **OC / play_caller** column for the prior regimes of the 23 uncovered names; (c) user
  reviews before 16.4 consumes it — same review contract as the 2026 half.
- **Out:** `reference/coaches.csv` covering both the historical fingerprint source-set and the 2026 targets.
- **Done:** every 2026 playcaller with a prior NFL playcalling regime has ≥1 historical row; user signs off.
- **Note:** this was the largest remaining item in Session E.

**Built 2026-07-25** — `src/fantasy_quant/situation/coaches.py` (new package) + done-bar
`steps/phase16_3b_coach_history.py` + `analysis/phase16_3b_coach_history.json` + 10 tests. **All gates PASS.**
- **The table:** 204 rows on the frozen schema — 172 historical (2014-2025) + the 32 signed-off 2026 rows;
  confidence 178 high / 25 med / 1 low. Plus **`reference/coach_lineage.csv`** (5 rows, the first-time
  play-caller fallback — see below).
- **(a) scaffold ☑ and it does more than save labour.** `pbp` gives an exact head coach for **384**
  team-seasons 2014-2025 (the "352" figure was 11 seasons; 12 x 32 = 384). Beyond filling the column, it
  **audits** every researched row: **157 auditable rows, 0 MISMATCH**, 1 legitimate `split_season`
  (2018 CLE). Review effort therefore belongs on `offensive_coordinator` / `play_caller` / `hc_calls_plays`.
  **Limitation:** pbp's coach field is game-level only through **2023**; from 2024 it is a season-level coach
  of record, so its `interim` column is a **lower bound** on mid-season changes.
- **(b) research ☑, web-verified.** Inclusion rule: a season counts only if the person called plays for the
  **majority** of the team's games; sub-majority stints are excluded and documented in an adjacent `notes`.
  Verification overturned five plausible drafts — Monken's pre-BAL OC stints were **not** play-calling,
  Schottenheimer did **not** call plays as DAL's OC (McCarthy did), Steichen's LAC years are 2019-20 not
  2020-21, Daboll called NYG plays in **2024 only**, and the Stefanski/CLE 2024 + McCarthy/GB 2015 holes are
  **real exclusions**, not missing rows.
- **★ the transport set is 17, not 13.** `in_house=0` gives 13; `new_regimes()` adds the internal promotions
  **structurally** (the table's own prior-season row names a different play-caller) rather than trusting the
  flag: **DEN, PHI, WAS** (as CLAUDE.md warned) **plus MIA** (Slowik was on Miami's 2025 staff). That check
  needs a complete predecessor season, so 2025 was completed for the 11 missing teams — cross-validated
  against ESPN's 32-play-caller survey, which independently confirmed all 21 rows already present.
- **★ coverage:** 9/32 play-callers with ~1 season each → **27/32 with a median of 4 prior seasons**
  (70 regimes, 43 distinct play-callers). **12 of the 17 transport teams have their own history**; the other
  **5 (BAL, DEN, PHI, SEA, WAS) have genuinely FIRST-TIME play-callers** — Doyle, Webb, Mannion, Fleury,
  Blough, each verified individually.
- **★ LINEAGE FALLBACK (user direction 2026-07-25 — supersedes the earlier "16.4 says nothing" plan).** A
  first-time play-caller is not a blank: they came up inside somebody's system, so fall back to **that
  mentor's** regimes and assume broad continuity, tagged as weaker evidence. `reference/coach_lineage.csv`
  names the mentor; a gate asserts **every mentor is itself a play-caller in `coaches.csv`**, so the fallback
  always resolves to a real fingerprint. Doyle→Ben Johnson (CHI 2025), Webb→Sean Payton, Mannion→Matt LaFleur
  (GB), Fleury→Kyle Shanahan (SF), Blough→Kliff Kingsbury. **Sean Payton (NO 2014-21, DEN 2023-25) and Kliff
  Kingsbury (ARI 2019-22, WAS 2024-25) were added to `coaches.csv` solely to make their mentees
  fingerprint-able** (+15 rows). Result: **12 own · 5 lineage · 0 none — all 17 transport teams covered.**
  `same_team` marks DEN and WAS, where the mentee is promoted inside the same building so lineage and team
  continuity coincide (the strongest form); at **BAL, PHI and SEA they disagree** and 16.4 must report both
  sides rather than pick silently (`prev_play_caller` carries the continuity reading).
- **(c) ★ REVIEW GATE OPEN** — the historical half is Claude-researched. **16.4 must not consume it until the
  user signs off**, the same contract as the 2026 half.

### 16.4 — Scheme fingerprint + transport → `situation/fingerprint.py` — ☑ **DONE 2026-07-25** (descriptive only)
*Review gate closed first: the user fact-checked the historical rows and lifted all 26 non-`high` ones, so
`reference/coaches.csv` is 204 rows all at `confidence=high`; the edits were confidence-only, so 16.3b's
machine audits carry over. Built as `situation/fingerprint.py` + `steps/phase16_4_fingerprint.py` +
`analysis/phase16_4_fingerprint.json` + 15 tests.*
- **Decisions locked with the user (2026-07-25):** **no season cap** — fingerprints use all 2014–2025
  seasons on file, lockbox years included, with **no provenance column** (an initial DEV-cap answer was
  reversed on the record); **EB shrinkage** toward the league-season baseline; partial regimes cut to the
  weeks actually called; metric set **extended with concentration (HHI), aDOT and pace**; output at **both**
  team and player grain; role-share deltas **plus a unitless implied multiplier**, no points column.
- **Built:** 14 metrics per team-season, z-scored **within season** (league drift ≠ personality), pooled per
  play-caller and EB-shrunk by regime length (`k = σ²/τ²`, method of moments). **41 play-callers / 64
  spells / 169 regime-seasons.** All **17** transport teams resolve — 12 own · 5 lineage · **0 silent** —
  and BAL/PHI/SEA carry **both** priors (mentor lineage vs. outgoing caller), never a silent pick.
- **★ Headline (deflationary):** only **20.9 %** of implied role-share movement is the incoming coach; the
  other **79.1 %** is the incumbent slot regressing toward the league mean, which any hire would produce.
  Every player row therefore splits into `reversion_pp` + `scheme_pp`.
- **★ Most useful by-product — trait stability.** Portable between jobs: `rz_pass_rate` (k=1.7),
  `team_adot`/`plays_pg` (1.8), **`carry_hhi` (2.0)**. Not portable: **`wr1_tgt_share` (k=17.9)** — the
  alpha receiver's target share is a roster fact, not a scheme fact. The added concentration metrics paid
  for themselves; the headline stat everyone quotes turned out to be the least coach-driven of the 14.
- **Guard added:** `assert_regime_coverage` makes an unexplained dropped regime an **error** — the first run
  silently deleted Sean McVay's nine Rams seasons because `pbp` says `LA` and the table says `LAR`. Fixed by
  reusing `adp.panel._canon_team`; a unit test also reconciles an unrestricted team-season against
  `features/environment.py` exactly (16.4 needs **week** grain, 3.4 is season grain).

*(original spec, for the record)*
- **Do:** per-playcaller-regime aggregate role-share stats (WR1/2/3 target share, RB carry share, TE
  target/route share, team pass rate/PROE, RZ usage split) reusing Phase 3.1/3.4 features; a transport
  function reweighting a new team's current personnel by an incoming playcaller's historical fingerprint
  (methodologically adjacent to 7.3's rookie transport, but a distinct hypothesis — scheme-specific, not a
  blunt team fixed-effect).
- **Out:** fingerprint table per playcaller-regime; transport output for 2026-relevant coaching moves.
- **Done:** **ships descriptive-only, explicitly labeled as an unvalidated hypothesis** — no BH-FDR gate,
  no backtested-edge claim (sample ~20–30 clean DEV transport events, too thin for that bar). The done-bar
  is "computes correctly and is honestly labeled," not "beats a baseline."
- **Reuse:** `features/opportunity.py` (3.1), `features/environment.py` (3.4), `causal/rookie_transport.py`
  (7.3) as a structural template for the transport mechanic.
- **The 2026 transport-event set (corrected 2026-07-25): 17 of 32 teams** — 13 external hires (`in_house=0`)
  **+ 4 internal promotions** (DEN, MIA, PHI, WAS: `in_house=1` but a different play-caller last season), 15
  are continuity. **16.4 can only transport 12 of the 17** — BAL, DEN, PHI, SEA and WAS have first-time
  play-callers with no prior regime **of their own** — for those, 16.4 transports the **mentor's** regime
  from `reference/coach_lineage.csv`, tagged as weaker evidence, per the user's 2026-07-25 direction.
  **Consume all of this via `situation.coaches.fingerprint_source(df, 2026)`** (returns `own`/`lineage`/`none`
  per team, plus `same_team` and `prev_play_caller`); use `new_regimes()` for the transport set and
  `coverage()` for prior-season counts. Do **not** re-derive any of it from the `in_house` flag alone.

### 16.5 — 2026 live situation-change event board → `reference/situation_events_2026.csv` — ☑ **REBUILT AS DERIVED 2026-07-25** (mechanism column awaits user research)
*`situation/events.py` + `steps/phase16_5_situation_events.py` generate the board from the warehouse;
**138 events over 30 teams**, one row per affected draftable player. Hand research is narrowed to the
`mechanism`/`notes` columns. Feeds the 16.6 Beta Lab tab (app phase).*
- **Do:** enumerate this season's situation-change events **exhaustively at a stated ADP cutoff** —
  team changes, rookies/returners, same-position room churn, and changed play-caller/QB context.
- **Out:** a current-season event list feeding the 16.6 tab.
- **Done:** the beta tab has real, current content for this year's draft, not just historical proof of
  concept.
- **Reuse:** `adp/panel._canon_team`; `situation.coaches.fingerprint_source` for the play-caller columns.
- **★ Method changed 2026-07-25 — hand-research REPLACED by derivation, on evidence.** The researched
  board was 9 rows and **missed 16 of the 23 team changes among draftable skill players**, including
  **A.J. Brown PHI→NE at ADP 13.6**, while carrying Tyler Allgeier at ADP 167; it had no row at all for
  the two highest-ADP players in the league (Bijan Robinson 1.6, Jahmyr Gibbs 1.8), both with a changed
  backfield. A tracker recap is not a frame over the players you actually draft. Three warehouse tables
  pin the whole thing down for free: **2026 `adp_snapshots`** (draftable board + current team), **2026
  `consensus_projections`** (an *independent* second read on team — **0 disagreements** over 183 shared
  players), **2025 `weekly`** (prior team + prior workload).
- **What is still human:** the **mechanism** (trade vs FA vs draft) and its terms — no feed carries it.
  It lives in the step's `ANNOTATIONS` block and is merged onto the derived rows, so the derivation owns
  *who/where* and research owns *how*. **111 rows are still `mechanism=unknown`.**
- **The ADP-board `team` column is safe here and only here.** `adp/panel.py` documents it as unusable
  for historical seasons (backfilled boards carry an end-of-season crosswalk — the Sep-1 2022 board has
  McCaffrey on SF). That contamination is *retroactive*: a snapshot of a season not yet played cannot
  encode a trade not yet made. `events.board()` cross-checks it anyway and raises on disagreement.
- **`new_qb` deliberately fires on unsettled rooms.** A team with **no** QB anywhere on the ADP board
  maps to `(unsettled)` and counts as changed (2026: ARI, ATL, CLE, NYJ, PIT) — those are the *least*
  settled rooms in the league, so defaulting them to "no change" would be backwards. Known false
  positive, left visible: the prior-season baseline is the attempts leader (matching `adp/panel.
  _starting_qb`, so the flag means the same thing as in 16.1), which fires when an incumbent missed time
  and a backup led attempts — 2026 WAS, Jayden Daniels against a Marcus Mariota baseline.
- **Aaron Jones Sr. withdrawn.** The derivation finds no MIN RB-room churn and no team change, reaching
  independently the same "not a 2026 event" conclusion the manual re-verification did (its premise was a
  timeshare with Jordan Mason, whose trade actually closed 16 Mar 2025). Recorded in the step's
  `WITHDRAWN` dict rather than silently dropped.

### 16.6 — Beta Lab tab → `app/streamlit_app.py`
- **Do:** add a new, clearly-labeled tab (e.g. "🧪 Beta: Situation Watch") showing 2026-flagged players
  (from 16.5), whichever of 16.1/16.2's signals survived their FDR gate (with CI + sign-stability, same
  presentation as the existing DURABILITY credit), and the 16.4 fingerprints framed as hypotheses, not
  recommendations.
- **Out:** a new tab in the existing Streamlit app.
- **Done:** the tab renders and is **provably read-only** — no code path from it touches
  `draft/optimizer.py`, `valuation/value_board.py`, or `valuation/cost_report.py`.
- **Reuse:** `app/streamlit_app.py`'s existing tab/sidebar structure (currently 155 lines — cheap to extend).

## Phase 16 — availability-side track (16.7–16.12) *(added 2026-07-23, user request — folded in)*
*Goal of the track: 16.1–16.6 ask "does a changed situation make a player **out-earn** his ADP (realized
value)?"; this track asks the sibling "does narrative/situation make a player **drafted earlier** than his
ADP (draft-slot **drift**)?" — the availability signal. It fixes a concrete UX failure: a target falls to the
user across 10 mock drafts, then gets **sniped early** in the real draft because many drafters share the read
(this year's case: Ladd McConkey). It extends the **availability/opponent model** (`draft/opponent_model.py`,
`draft/availability.py`, `draft/simulator.py`), which is **already outside the value-stack lockbox** (predicts
draft flow, not player value, walk-forward-scored) — so it does not spend or contaminate the frozen value
eval. **Validation bar (user 2026-07-23): walk-forward + an own held-out metric on what backtests; momentum
is validated live on 2026 only.** Full scoping + the 4 answered decisions: `PLAN.md`, 2026-07-23 entry. Two
hard data constraints drive the design: (i) **momentum is forward-only** — FFC history is one ~Sep-1 board/
season, so no historical intra-season ADP series exists; (ii) **true ECR isn't stored** — we keep FantasyPros
projections (points), not expert rank, so the "expert-rank-minus-ADP" gap uses the VBD-`overall_rank`-vs-ADP
proxy. What is backtestable: the Sleeper human corpus (149 drafts, 2017–2020) gives `actual_slot − ADP`.*

### 16.7 — Draft-slot-drift panel & target → `adp/drift_panel.py`
- **Do:** the availability twin of 16.1's VOR-alpha panel. Compute `drift = actual_draft_slot −
  preseason_ADP` per (player, draft) from the Sleeper human corpus (`sleeper_draft_picks`, `is_human`,
  2017–2020) joined to the FFC / `sleeper_human` ADP board; aggregate to per-player-season mean drift (the
  backtestable target). PIT: preseason ADP only, no post-draft data.
- **Out:** `adp/drift_panel.py` (`build_drift_panel(con, seasons)`), a per-player-season drift table.
- **Done:** the panel builds PIT-clean for 2017–2020; drift distribution reported (mean≈0 by construction,
  fat both tails); documented as thin (the only historical draft-slot ground truth we have).
- **Reuse:** `adp/panel.py` join machinery, `data/sources/sleeper.py`, `adp_snapshots`.
- **☑ BUILT 2026-07-25 (`adp/drift_panel.py`, `steps/phase16_7_drift_panel.py`).** Three deviations from
  the spec above, each forced by a measurement:
  1. **`PRESEASON_WINDOW` (Aug 1 – Sep 15) added** — the corpus contains drafts from **February to
     November**; an offseason startup or in-season draft vs a September board is a different market, not
     drift. Biggest single filter: 117 human complete drafts → 42.
  2. **Units are rounds, not picks** (`pick_no / teams` vs `adp / board_teams`), so 6/8/14/16-team rooms
     join the 10/12-team FFC board instead of being discarded (+7 drafts).
  3. **Sign flipped** vs the `actual_slot − ADP` above: **`drift > 0` = drafted EARLIER** (matches the
     existing `sleeper.build_tendencies` `reach`), and **`drift_centered`** — drift minus its own draft's
     mean — is the headline target, removing each room's level offset.
  Actual span **2017–2024, not 2017–2020** (the corpus is deeper than scoped); **34 drafts / 4,495 boarded
  picks / 436 players**. 2025 drops entirely: **FFC publishes no 2025 board** (verified live). Positional
  means: **TE +0.46 rounds, WR +0.08, RB −0.16, QB −0.20**.

### 16.8 — Drift feature model → `adp/drift_model.py`
- **Do:** fit `drift ~ features` walk-forward (leave-one-season-out over 2017–2020), season-block bootstrap,
  same discipline as 6.2. Features: **VBD-ADP gap** (`value_board.overall_rank` − ADP-board rank), **source
  divergence** (FFC public ADP − `sleeper_human` sharper ADP), and the **situation-change flags** reused from
  16.1/16.2 (`team_changed`, `new_starting_qb`, competition-change).
- **Out:** `adp/drift_model.py` (`fit_drift`, `predict_drift`), a coefficient scorecard + held-out metrics.
- **Done:** an honest predicts-or-doesn't verdict — **drift MAE / Spearman vs a naive `drift = 0` baseline**,
  with CIs; each feature reports sign-stability. Survive-or-drop, no threshold moved post-hoc.
- **Reuse:** `valuation/value_board.py` (`overall_rank`), `adp/regression.py` bootstrap harness, 16.1/16.2
  situation features.
- **☑ BUILT 2026-07-25 (`adp/drift_model.py`, `steps/phase16_8_drift_model.py`) — VERDICT: DOES NOT
  PREDICT (honest null).** Bar fixed in advance: skill > 2 % of baseline MAE, CI clear of 0.
  Headline **+1.05 % CI[−1.48, +4.96]**, Spearman +0.208. **Ablation without `source_divergence`:
  −1.75 %** — *worse than assuming everyone drafts at ADP*.
  - **★ The ablation is the result.** All apparent skill traces to the one feature derived from the
    target's own sibling drafts, and it was **already** leave-one-draft-out. Computing a sibling-derived
    feature leave-one-out is **not sufficient** — report the fit without it too. See glossary,
    "the ablation rule".
  - **True ECR was not usable** (0.11 banked the archive and proved it kickoff-dated — 1 of 38 drafts
    post-dates its own stamp), so the **VBD-gap proxy stands** and the reason is now measured.
  - **Situation flags null again** — `team_changed`, `new_starting_qb`, both competition flags
    insignificant and sign-unstable, mirroring the 16.1/16.2 value-side null.
  - **Survives the ablation** (sig + 100 % sign-stable) → what 16.9 should shape its shock with, as
    descriptive room behaviour and **not** a per-player forecast: **`rookie` +0.73 rounds**,
    **`adp_stdev` +0.35/SD**, `vbd_gap` +0.18/SD, `adp_rounds` −0.19/SD, `pos_WR` +0.47.

### 16.9 — Correlated per-draft narrative shock → `draft/simulator.py`, `draft/opponent_model.py`
- **Do:** the user's key insight — independent per-opponent sampling washes out clustering, so a hyped player
  *always* falls. Draw **one shared hype shock per simulated draft**, applied to every AI opponent (a `hype`
  term in `opponent_model.candidate_utility` / a shift on the 11.2 survival mean), so hyped players go early
  **consistently within a draft**. The shock magnitude is driven by the 16.8 drift prediction (+ 16.10/16.11).
- **Out:** a `hype`/`drift` feature on the opponent model + a per-draft shock draw in the simulator loop.
- **Done:** the simulator reproduces the **realized cross-draft dispersion** of a player's draft slot in the
  Sleeper corpus (variance match, not just mean), and **availability Brier does not regress** vs the current
  11.2 default. Validated on the human corpus, walk-forward.
- **Reuse:** `draft/opponent_model.py` (conditional-logit utility), `draft/availability.py` (`simulate_survival`),
  `draft/simulator.py` opponent loop.
- **☑ BUILT 2026-07-26 (Session G) — the shock is an honest NULL; the level done-bar was met by a bug fix.**
  `adp/narrative.py` + `steps/phase16_9_narrative.py` + `analysis/phase16_9_narrative.json` + 9 tests.
  - **The premise inverted:** the simulator did not under-disperse, it **over**-dispersed by 59 %. Cause was
    a **choice-set contract violation** — 11.1 is fit on `build_choice_frame(top_k=40)` but both
    `make_opponent_pick_fn` and `simulate_survival` drew from the **whole board**. Now share
    `opponent_model.CHOICE_TOP_K`, asserted by test. Level error **59.5 % → 8.8 %**; availability Brier
    **+0.0644 → +0.0708** (improves — no regression, on 7,792 windows).
  - **The shock does not earn its keep.** Realized depth slope +0.679; band ON +0.077; +shock **+0.057**.
    Swept over a **50× size range** the slope never moved beyond its own between-sample noise (two runs at
    one setting: +0.249 / +0.057) → the calibration is **unidentified**, reported as such.
  - **Why it structurally cannot:** `top_k` is a hard rank filter applied **before** utility, so no additive
    shock pulls a player into the candidate set — it only reshuffles within it. Residual shape miss traced to
    `adp_s` being linear in raw ADP → **T15** (an 11.1 respecification, deliberately not attempted here).
  - **Shipped:** band **ON by default**; shock **built/wired/tested, default OFF** ("kept, not default", as
    Phase 7 / props / the 13.2 win-tilt). 16.10 and 16.15 still get their expression channel, now a correct one.

### 16.10 — Curated hype-board override → `adp/hype_board.py` + `reference/hype_board.csv`
- **Do:** a small editable table (`player_key · pick_delta · note · source`), Claude-drafted via web research
  + **user-reviewed before use** (same contract as the 16.3 playcaller table), capturing the qualitative
  narrative residual pure market signals miss. A loader applies it as a bias on the opponent utility /
  survival on top of the quantitative drift, live-season only, PIT-stamped.
- **Out:** `reference/hype_board.csv` (versioned), `adp/hype_board.py` (`load_hype_board`, `apply_hype`).
- **Done:** the board loads, is user-approved before wiring, and shifts a hyped player's simulated draft slot
  in the expected direction; explicitly labeled **curated, not a backtested claim.**
- **Reuse:** 16.3's research/review workflow; the 16.9 shock as the application channel.
- **☑ BUILT 2026-07-26 (Session G 2/2)** — `adp/hype_board.py` + `reference/hype_board.csv` (24 rows,
  20 directional claims, `reviewed=false`) + `steps/phase16_10_hype_board.py` + `tests/test_hype.py`.
  **All 5 gates PASS**; sign agreement **94 %** on 18 resolvable claims, corr(claim, shift) **+0.72**.
  - **Method = derived rows, curated claims** (16.5's *derived-vs-curated* rule): `nominate()` ranks
    the live board on the 16.8 ablation survivors + 16.11 momentum, the human writes
    `pick_delta`/`note`/`source`. **16 of 24 rows machine-nominated**; the rest are research-only,
    which is the split working. Regeneration merges forward, so a signed row survives a re-run.
  - **★ Elasticity ≈ 0.44 realized picks per claimed pick** — ADP is one term among many and `top_k`
    filters before utility. A curated row is a **nudge, not a repricing**; never surface `pick_delta`
    as a predicted draft slot.
  - **Four measurement defects found and fixed, each of which had produced a plausible wrong list:**
    partial coefficients used without their depth/position controls (→ an ADP-120–175 list, then a
    TE-flooded one); `log(adp)` alone leaking curvature (→ the top of the board surfacing spuriously);
    momentum entered in rounds/week against weights in rounds (→ the loudest live mover dropped out);
    and a signed composite ranked one-sided (→ the strongest *fader* claim dropped out). See findings.
  - **Two done-bar traps:** undrafted players must be **censored, not dropped** (else hype reports a
    deep player moving *later*), and claims must be applied **leave-one-in** (a draft is zero-sum, so
    20 simultaneous claims crowd each other out). → **T16** for the 15-round expressibility limit.

### 16.11 — Live 2026 momentum / ADP velocity → `adp/momentum.py`
- **Do:** compute ADP **velocity** = slope of a player's ADP across the Stage-0 2026 snapshot **series**
  (`adp_snapshots`, banked weekly since 2026-07-09). Feed it as an additional live drift input.
- **Out:** `adp/momentum.py` (`adp_velocity(con, season)`), a per-player slope + recency-weighted current ADP.
- **Done:** velocity computes on the 2026 series; **explicitly labeled forward-only / not backtestable** (no
  historical intra-season series), validated **live on 2026** as snapshots accrue — the 16.4-style
  descriptive-honesty bar, not a walk-forward gate.
- **Reuse:** `adp_snapshots` series, `data/sources/adp.py`.
- **☑ BUILT 2026-07-26 (Session G 2/2)** — `adp/momentum.py` + `steps/phase16_11_momentum.py` +
  `analysis/phase16_11_momentum.json`. **All 5 honesty gates PASS.** 192 players, **3 FFC snapshots**
  over 15 days. Built **before 16.10**, since derived-first nomination makes momentum an input to it.
  - Sign-flipped to 16.7's convention (`velocity > 0` = drafted earlier), **centered** on the board's
    own median slope (the pool deepens through a preseason, so every ADP creeps later together — the
    median player must end at exactly zero, now asserted), and **EB-shrunk** by each player's own
    standard error (3 snapshots ⇒ 1 residual df; **44 %** of the raw spread survives; 2-snapshot
    players shrink to exactly 0).
  - `momentum_summary` leads with `backtestable: False`; `movers()` filters kickers, whose ADP swings
    15+ picks between boards and dominates a raw sort.

### 16.12 — Consumption: realism + advice + app readout → `draft/`, `draft/optimizer.py` (9.4), `app/`
- **Do:** wire the drift signal into all three consumers the user chose (**both** realism and advice):
  **(a) realism** — mock-draft opponents reflect 16.8/16.9/16.10/16.11 drift; **(b) advice (opt-in)** — drift
  adjusts the Phase-9.4 `survival_prob`/lookahead so the drafter's *own* pick advice accounts for it ("he
  won't last — consider reaching"), gated on, never touching the frozen value contracts; **(c) app** — an
  honest `P(available at your pick)` + a "draft-market drift / reach-risk" readout on the player deep page
  (per `docs/PLAYER-VIEW.md`), and the drift board on the 16.6 Beta Lab tab.
- **Out:** drift-aware opponent flow (default), an opt-in drift term in `draft/optimizer.py` lookahead, the
  app readout fields.
- **Done:** switching the drift signal on measurably changes mock realism (dispersion match) + the availability
  readout; the opt-in advice path changes a pick on a hyped-player example; **the frozen value/distribution/
  optimizer/VBD/cost-report stack is provably untouched** (drift feeds only the opponent model + an opt-in
  lookahead + the app).
- **Reuse:** `draft/optimizer.py` (`survival_prob`, `RiskModel`), `draft/availability.py`, `app/streamlit_app.py`,
  `docs/PLAYER-VIEW.md` spec.
- **☑ BUILT 2026-07-26 (Session G 2/2)** — `draft/drift.py` + `steps/phase16_12_consumption.py` +
  `tests/test_drift_consumption.py`. **All 6 gates PASS.** Per the user decision, **(c) is engine-side
  only** — the UI stays in Phase 14 ("app strictly last").
  - **(a)** 179 players shift >0.5 picks; hyped rows move **+2.90 picks earlier** on average.
  - **(b)** `RiskModel.hype` shifts effective ADP inside the 9.1/9.4 urgency term (mean survival change
    −0.029). Only 3 of 20 claims reprice at a 60-pick window — correct and self-limiting, since
    `survival_prob` saturates beyond it: advice moves exactly the players near *your* window.
  - **(c)** `availability_readout` returns `p_available` **and** `p_available_baseline` side by side,
    plus `drift_picks`, a 3-bucket `reach_risk` and a `drift_material` flag. Reporting the *pair* is
    the point — an unbacktested adjustment never reaches a human as a bare number.
  - **(d) isolation, the gate that protects the spent lockbox:** `DriftConfig()` is a provable no-op
    and a `RiskModel` built without `hype` is **bit-identical** to the pre-16.12 frozen path. Asserted
    by constructing the model the old way and comparing with `array_equal`, plus a companion assertion
    that the opt-in path *does* change something so the guarantee cannot pass vacuously. Drift also
    rides only the `scarcity_w > 0` branch, so a covariance-only greedy is untouched.

**Done-when (availability track):** 16.7/16.8 report an honest walk-forward drift-predictability verdict on
the Sleeper corpus; 16.9 reproduces realized draft-slot dispersion without regressing availability Brier;
16.10 loads + applies a user-reviewed hype board; 16.11 computes live 2026 momentum (labeled forward-only);
16.12 wires realism + opt-in advice + the app readout — all outside the frozen value stack.

## Phase 16 — opponent-personality set (16.13–16.15) *(added 2026-07-23, user request — folded in)*
*Goal of the cluster: the behavioral opponent model (11.1) predicts the **average** manager; a realistic
mock-draft room also wants **heterogeneous** opponents so practice drafts feel like a real league.
`draft/personalities.py` (Phase 11.3) already ships six ADP/behavioral tilts (`balanced`, `chalk`, `zero_rb`,
`reacher`, `homer`, `rookie_hawk`), but **none tilt on risk or value** — the live board carries only
`adp`/`pos`, so a ceiling-seeking "upside chaser" and a floor-seeking "safe" drafter can't be built. This
cluster enriches the opponent board with the frozen Phase-5 distribution + `value_board` fields (read-only)
and ships the **5 headline personalities** the user asked for. **User decisions (2026-07-23):** "auto-draft/
BPA" = **ADP autopilot only** (no value-board opponent — `chalk` already covers ADP-following, this makes it
deterministic); **enrich with the real frozen fields** (highest fidelity); **validation = face-validity +
unit-tested mechanics** (a realism/UX feature, no corpus Brier gate); the Phase-16.9 narrative shock expresses
**through** the ceiling/hype personalities (unifies the two systems). Note the concept split: these are
**opponent personalities**, distinct from `config.py` **archetypes** (which are the *user's own* draft
strategy). Full scoping + the 4 answered decisions: `PLAN.md`, 2026-07-23 (personalities) entry.*

### 16.13 — Opponent-board enrichment → `draft/simulator.py`
- **Do:** attach the frozen, **read-only** Phase-5 distribution fields (`boom_prob`, `q90`, `bust_prob`,
  `q10`, `games_played_mean`) + `value_board` fields (`vbd`, `overall_rank`) to the opponent board that
  `DraftState.draftable_pool` reads, PIT (draft-season projections only). A small join helper off the frozen
  `player_distributions` + `value_board` contracts, keyed by `player_key`/`gsis_id`.
- **Out:** an enriched board build in `draft/simulator.py` (extra columns, present when available), a join
  helper; the extra columns are optional so ADP-only callers are unaffected.
- **Done:** the sim board carries the risk/value columns for covered players; missing rows (rookies/no-prior)
  are `NaN` and handled by the personality's fallback; **no modeling change** (reads frozen outputs only).
- **Reuse:** `projections/distribution.py` `player_distributions` contract, `valuation/value_board.py`,
  the existing board-load path in `draft/simulator.py`.
- **☑ DONE 2026-07-26 (Session H)** — `draft/enrichment.py` (the join helper) + `draft/simulator.py`
  (`PASSTHROUGH_COLS`, `board_player_key`). Coverage on the live 2026 board **81.8 % distribution /
  85.8 % value**; the whole skill-player gap is **one WR** (the rest is 22 DEF + 18 PK, which carry no
  projection by construction). An ADP-only board is byte-for-byte unchanged, asserted.
  - **Source note:** reads `cached_distribution(con, season, …)`, **not** the `player_distributions`
    table — that table holds **2025 only**, so a live-season mock would have found it empty. Same
    reader `optimizer.assemble_value` uses; PIT via `as_of = draft_date(con, season)`.
  - **Scope added beyond the spec, and it is load-bearing:** `mean` (as a control) plus the derived
    `upside`/`floor` (`residual_shape`), because the raw quantiles turned out to be a *level* signal
    — see 16.14 below. Also `rookie` (which `_prepare_board` had been dropping) and `cos`.
  - **Placement note:** the join helper is in a new `draft/enrichment.py`, not in `simulator.py` as
    the heading says. `simulator.py` is a Phase-1 leaf that ten modules import; pulling `value_board`
    + `distribution` + `situation.events` into it would invert the dependency graph. The passthrough
    half — the part that genuinely belongs there — did go into `simulator.py`.
  - **★ Two personalities that had never worked now do.** `homer` scaled a `fandom` coefficient whose
    feature was identically 0 (nothing in the mock path ever passed `fav`) and `rookie_hawk` scaled a
    column `_prepare_board` discarded. Both were literal no-ops from Phase 11.3 through a full phase
    and a green test suite, because **an inert personality still completes a legal draft.**

### 16.14 — Risk/value personality set → `draft/personalities.py`
- **Do:** extend `Personality` with a `signal_weights: dict` term (a linear bonus on the enriched board
  columns, applied in `make_opponent_pick_fn` after the β-utility), and add the **5 headline personalities**:
  1. **Autopilot** — deterministic lowest-ADP-available (behavioral features zeroed via `override`, `sample=
     False` argmax on ADP) — the literal Sleeper autopick / "BPA every time" in the ADP sense.
  2. **Balanced** — the fitted average human (already shipped; kept as the anchor).
  3. **Upside Chaser** — `signal_weights={"boom_prob": +, "q90": +}` + `scale={"rookie": …}`; punts floor;
     an `early_pos_penalty` off, high-ceiling early.
  4. **Safe / Floor** — `signal_weights={"q10": +, "games_played_mean": +, "bust_prob": −}`; leans veteran/
     durable (Phase-6 DURABILITY-consistent); cools the softmax (chalkier).
  5. **Homer / Narrative-Chaser** — `scale={"fandom": …}` + a bonus on the 16.10 hype-board delta; the
     channel the 16.9 per-draft narrative shock is applied through.
- **Out:** an extended `Personality` dataclass + `personalities()` returning the 5 headliners (plus the
  existing `zero_rb`/`reacher`/`rookie_hawk` as library extras), + `make_opponent_pick_fn` honoring
  `signal_weights` and the deterministic Autopilot path.
- **Done:** **face-validity** checks pass — Upside Chaser's drafted pool skews **younger / higher `q90`**,
  Safe skews **more durable / higher `q10` / lower `bust_prob`**, Autopilot draws **pure ADP order**, Homer
  **reaches for `fandom`/hype names**, Balanced ≈ the fitted model — plus unit tests that each tilt shifts
  utility in the intended direction. **No corpus Brier gate** (user decision — realism/UX feature).
- **Reuse:** the existing `Personality`/`make_opponent_pick_fn` machinery (Phase 11.3), 16.13's enriched
  board, 16.10's hype board.
- **☑ DONE 2026-07-26 (Session H)** — `draft/personalities.py`, `steps/phase16_13_personalities.py`,
  `tests/test_personalities.py` (30 offline tests). **496 tests total, ruff clean, all seven
  live-board face-validity checks PASS**; `autopilot` reproduces `pick_by_adp(noise=0)` *exactly*
  over a whole draft, not merely in tendency.
  - **★★ THE SPEC AS WRITTEN BUILDS TWO PERSONALITIES THAT AGREE WITH EACH OTHER.** `signal_weights=
    {"boom_prob": +, "q90": +}` vs `{"q10": +, …}` runs, passes a synthetic test, and on the real
    board `safe_floor` drafts a **higher** mean `q90` than `upside_chaser`. Measured within position
    on the frozen board: `corr(q90, mean)` = **+0.984 / +0.985 / +0.999** (2022 / 2025 / 2026) and
    `corr(q90, q10)` = +0.62…+0.74. **The raw quantiles are a *level* signal — "is this player
    good" — not a shape signal.** Both weights are quality tilts; the two managers just drafted good
    players from opposite-sounding rationales. Shipped build weights `upside`/`floor` (16.13's
    level-residualized versions): orthogonal to level by construction, `corr(upside, floor) = −0.86`.
    *This is the 16.10 lesson recurring on a **signal** instead of a coefficient, and it presented
    the same way — as a plausible result rather than an error.*
  - **Mechanisms:** `signal_weights` (utility per within-position sd of the live pool);
    `max_reach_picks`, a reach ceiling in **ADP picks** converted through the model's own `β_adp_s`
    exactly as `apply_hype` does, covering the discretionary tilt but *not* β reshaping or
    `early_pos_penalty` (capping those would silently neuter `zero_rb` and `autopilot`); `hype_gain`,
    the per-seat multiplier on the shared shock that **16.15 will route the 16.9 narrative shock
    through**; `fav_teams`, which finally makes the fitted `fandom` term reachable.
  - **User addition (2026-07-26):** with no hype/`cos`/favourite-team target on the clock, a story
    chaser must take best value rather than manufacture a reach. Not special-cased — it falls out of
    the reach ceiling, and is tested as an **exact** pick-log equality against `balanced`.
  - **Ceilings were measured, not guessed:** at 10 picks every tilt sits inside `balanced`'s own
    noise over 8 pooled seeds (real but illegible); at 18 the ordering separates and holds. Shipped
    **18 / 15 / 24** (the homer spends `MAX_PICK_DELTA`, the largest single-player claim the curated
    hype board may make).
  - **Read the effect sizes honestly:** ±0.05 z on a pooled drafted pool. A manager who reaches at
    most 1–2 rounds cannot move 90 picks much, and one seeded draft cannot even resolve the sign —
    every face-validity number pools 8–12 drafts. The bar is **direction and mutual opposition**, not
    magnitude.
  - **New tech debt T17** (🟠) surfaced by 16.13's coverage report: `availability_projection` returns
    **0 rows** for an unplayed season, so the live Phase-5 `mean` collapses to **37 %** of the
    consensus projection it is built from. Session H is insulated by the within-position
    standardization (a uniform multiplier cancels); `games_played_mean` is the one casualty and is
    now inert on a live board.

### ★ 16.14R — the personality contract, REVISED *(2026-07-27, user design review after the live mock)*

**Status: spec agreed, NOT built. Runs as its own session AFTER the T15 respecification** (it depends
on T15's round-varying width function — see `PLAN.md` §2026-07-27). Supersedes the seat definitions in
16.14 above where they conflict; 16.14's *mechanisms* (`signal_weights`, `hype_gain`, the
level-residualized `upside`/`floor`) all stand.

**★ The organizing idea: separate WIDTH from DIRECTION.** Every seat is `width(round) ×
personality_multiplier` for *how far* it deviates from ADP, and `signal_weights` for *which way*. The
old absolute `max_reach_picks` ceiling cannot express this — T15 proved width must vary by round (3.3
picks in R1 → 27.1 in R15), so any single pick-count ceiling is wrong at one end by construction.
**The multiplier replaces the ceiling as the primary reach control.**

| seat | width mult | direction | notes |
|---|---|---|---|
| **autopilot** | 0 | pure ADP | **unchanged** — user confirmed no change needed |
| **balanced** | 1.0 (= corpus) | ablation survivors + enriched tie-break | situation channel opt-in, default OFF |
| **reacher** | **≤2.0** | rookies, hype board, media narrative | inherits 16.9 shock + 16.10 from the retired homer |
| **safe** | ~0.8 | `q10`/`bust_prob`, durability **net of level** | |
| **value hawk** | bounded window (open) | best available board value | **replaces homer**; `fandom` falls out of use |

- **Autopilot — no change.** ★ The user's diagnosis of its mock win, and it is the right one: *it was
  not drafting well, it was harvesting what the reaching seats spilled* (mean drift −19.8 picks). It
  needs no fix; **T15 fixes it by fixing everyone else.** This retires the standings half of T15's
  acceptance bar #3 — see the rewritten bar in `docs/TECH-DEBT.md`.
- **Balanced — the intent was never implemented.** Today `balanced` is the raw fitted β with *every*
  tilt off: no `signal_weights`, no `fav_teams`, `max_reach_picks=None`. It is not misbehaving against
  its spec; the holistic spec never existed. It produced the draft's 42-pick reach. Build it as:
  1. **width** = the T15-respecified β, corpus-matched by round;
  2. **direction** = the **16.8 ablation survivors** — `rookie` (+0.94 rounds), `adp_stdev` (+0.27/SD),
     `vbd_gap` (+0.26/SD), `pos_WR`, `pos_TE`. `adp_stdev` is the most valuable of these for the
     "makes sense" character: *where the crowd disagrees with itself, someone jumps* — and it is
     fitted-supported, not declared;
  3. **tie-break inside the reach window** = the 16.13-enriched board (`upside`/`floor`, injury,
     bust_prob). This is where "holistic / high-quality / makes sense" actually lives — among
     near-equivalent candidates prefer the healthier, higher-floor one. Behaviourally plausible and
     **claims no alpha**;
  4. **situation/coach (16.4/16.5)** = a **labelled opt-in channel, default OFF** — the 16.10 hype-board
     pattern. See the §"level, not the residual" note below for why it is not a deviation driver.
- **Reacher — reaches most, capped at 2× balanced.** Rookies, beneficial situation changes, media
  attention. ★ **It absorbs the narrative channel from the retired homer**: the 16.9 per-draft shock and
  the 16.10 hype board both route here. Arguably a better home than homer was — the user's reacher
  description *is* the narrative chaser.
- **Safe — reach slightly under balanced (~0.8×), prefer proven/durable/low-regression, still finish
  with a medium-high quality team.** ⚠ **T17 trap:** the availability fix turned `games_played_mean`
  from four inert cohort constants into a real forecast **and thereby into a level proxy** (+0.46…+0.90
  within position), so weighting durability *and* projection level double-counts. Durability must enter
  **net of level** — residualize it the way 16.13 residualized `upside`/`floor`.
- **★ Value Hawk — replaces Homer; the user calls it "the brainchild of the project".** Reverses the
  2026-07-23 decision that cut it ("BPA = ADP autopilot only"). It is the *smartest researched human*:
  it uses the full accumulated stack to build the best **projected** team, and reaches decisively but
  rarely for a player inside a bounded window who is better than anything ahead of him. Mechanically
  that is **bounded-window argmax on the value board = the Phase-9 greedy with a reach constraint**,
  which we already have. Two consequences worth stating:
  - **Benefit:** it is our own optimizer sitting in a seat — the best dogfood in the project.
  - ⚠ **Cost:** deleting homer retires the `fandom` coefficient (+35.5 picks, ×2.5 ⇒ **89** — the
    single largest coefficient in the model and a major reach driver). Removing that seat removes a
    real pathology, but `fandom` stays fitted-and-unused; do not delete the feature.

**★★ THE EVALUATION TRAP — state this before the seat is built.** If value hawk optimizes our value
board and the room is scored by our value board, **it wins by construction and proves nothing.** The
lockbox already reported personalization as noise-dominated on realized points (all archetype-cost CIs
∋ 0). So: projected-points ranking of the room is **descriptive** (does the room behave sensibly?);
any **evaluative** claim must run on realized points in a backtest season. Same family as *an inert
thing still passes* and the 16.14 "two personalities that agree with each other" lesson.

**☐ THREE OPEN DECISIONS — settle before this session starts:**
1. **Value hawk's objective — VBD or portfolio CE?** Recommendation: **portfolio CE** (correlation-aware,
   what the Phase-9 greedy maximizes) since "best possible team" is a roster-level claim. Cost: it is
   our most opinionated object, and it sharpens the evaluation trap above.
2. **Value hawk's reach window**, in the same width units as everyone else. Suggested start
   **~1.0–1.25× balanced** — a sharp drafter reaches *decisively but rarely*, not far.
3. **How much of the enriched board balanced sees.** 16.4 scheme fingerprints and 16.5 situation events
   are **not on the 16.13 board today** (only Phase-5 distributions + value_board fields). If the
   situation channel ships default-OFF we can defer the plumbing; making it live is real scope.

**Done-when (16.14R):** the width multipliers reproduce the corpus reach curve per seat; balanced's
drafted pool shows the survivor tilts + the enriched tie-break without breaking its corpus match;
value hawk beats the room on the *descriptive* projection metric **and that is reported as descriptive**;
reacher's max reach ≤ 2× balanced's at every round; safe's durability tilt is level-residualized.

---

## ★★ 16.14R — THE EXECUTION ORDER (written 2026-07-27 session 5, after the 2×5 mock room)

> **★ STATUS (2026-07-28): ALL SEVEN STEPS DONE.** Run straight through under a waived §3.7 gate
> (user instruction). Steps and their artifacts:
> **1** `adp/boards.py` `include_dst` + `DraftState.mandatory_needs` + `SKILL_POSITIONS` (T20 ☑,
> T21 ☑) · **2** `steps/phase16_14r_2_floor.py` → `analysis/phase16_14r_floor.json` (T19 ☑, **T22
> opened**) · **3** `steps/phase16_14r_3_context.py` → `..._context.json` · **4**
> `steps/phase16_14r_4_safe_floor.py` → `..._safe_floor.json` · **5**
> `steps/phase16_14r_5_reacher.py` → `..._reacher.json` · **6**
> `steps/phase16_14r_6_value_hawk.py` → `..._value_hawk.json` · **7**
> `steps/phase16_14r_7_room.py` → `..._room.json` + `analysis/mock_16_14R_picks.csv`, plus
> `steps/phase16_14r_signal_report.py` → `analysis/t19_signals.csv`.
>
> **Two deviations from the text below, both forced by measurement and both written up in
> `PLAN.md`/`findings.md`:** step 2's fix was a change of **scale** (ratios to the projected level),
> not of estimator — Tobit *and* the rank both failed on the raw quantiles; and step 5's per-round
> corpus-p95 ceiling had to become part of the **mechanism** (`CORPUS_REACH_P95`), because a count
> budget bounds how *often* a seat reaches and never how *far*.

**Read this before starting 16.14R.** A full 15-round mock was run with **2 seats each of
autopilot / value_hawk / safe_floor / reacher / balanced** (`analysis/` not written — DEV run;
driver + CSVs in the session scratchpad, method reproduced in `findings.md` §"The 2×5 mock room").
The user reviewed all 150 picks by eye and raised three seat-level objections. **All three have a
measured mechanism, and two of them are defects in things 16.14R was going to build *on top of*.**
That changes the order: **the signals and the board have to be repaired before any personality is
re-specified**, or each rework tunes around a broken input.

The seven steps below are the plan of record. **Stop and report after each** (CLAUDE.md rule 7).

### Step 1 — Roster legality + the K/DST guarantee → `adp/boards.py`, `draft/simulator.py`
User instruction (2026-07-27): *every* seat must finish with at least one K and one DST whenever
`rounds >= slots.starters`. Today **no seat ever drafts a DST and `autopilot` averages 0.16 kickers**.
- **1a.** Thread `include_dst` through `_ffc_board`/`resolve_board`, **default OFF**, and turn it on in
  `mock.room_board`. Team defenses are already in `adp_snapshots` (60 DEF rows for 2026 FFC PPR
  10-team: SEA 94.7, DEN 100.9, LAR 106.5) and are dropped only by the `gsis_id IS NOT NULL` clause —
  they carry `ffc_player_id` instead. Everything downstream already supports them: `board_player_key`
  name-keys defenses *by design*, `canon_pos` maps `DEF→DST`, `DRAFTABLE` includes `DST`.
  Default-OFF is load-bearing — see Step 1c.
- **1b.** `DraftState.mandatory_needs(team)` = unfilled **non-flexable** starter demand (QB/K/DST from
  `RosterSlots.base_demand()` minus `flex_positions`). In `draftable_pool`, when a team's remaining
  picks equal its unfilled mandatory slots, restrict the pool to those positions. A **hard filter
  applied before utility** — the same class of object as `BandSpec`, so it does not touch the fitted
  β's meaning. Gate the whole rule on `rounds >= slots.starters`.
- **1c.** **Exclude K/DST from the simulation candidate band.** `build_choice_frame(skill_only=True)`
  — the default the shipped β was fit under — restricts candidates to QB/RB/WR/TE, but the sim bands
  the *whole board*, so the fitted β can nominate kickers it never saw. That is the Session-G
  choice-set contract violation in a second home, live today (it is why `value_hawk` took Brandon
  Aubrey at pick 119). Fixing it is what makes 1a safe: DST goes on the board for the roster rule,
  never into the choice set.
- **Done:** a test asserts every seat ends with ≥1 K and ≥1 DST at `rounds=15`, and that **no**
  forcing happens at `rounds < 9`. Re-run the batch and confirm bars #1/#2 are unmoved.

### Step 2 — Repair `floor` before any personality consumes it → `draft/enrichment.py`
**`floor` is inverted at depth and this is why `safe_floor` drafts boom-or-bust players.** `floor` is
`q10` residualized on `mean` within position, but **`q10` is censored at exactly 0 for 42.9 % of
offensive board rows** (59.0 % past ADP 100, 5.7 % inside ADP 50). Regressing a censored variable on
level hands the largest positive residuals to players just above the censoring point, so:
`corr(floor, adp)` = **+0.179 RB / +0.124 WR**. The highest-`floor` RBs on the live board are
**Jonah Coleman** (ADP 171, mean 35.2, q10 1.3) and **Jaydon Blue** (ADP 140, mean 38.7, q10 1.8);
the highest-`floor` WR is **Zachariah Branch** (ADP 165). The seat was not misbehaving — those are
the players the board told it were safest.
- Replace the linear residualization with a **censoring-aware** fit (Tobit) or a rank-based
  conditional quantile (q10 percentile within an ADP neighbourhood rather than a global
  within-position regression).
- **Also decide `boom_prob`/`bust_prob`:** they are exactly **0 for 64.7 % / 56.0 %** of offensive
  rows, so `safe_floor`'s `bust_prob: −0.35` — a third of its weight budget — is inert on more than
  half the board. Either widen the Phase-5 threshold so they discriminate, or drop them from
  `SIGNAL_COLS`. **Do not leave an inert weight in a shipped personality** (fourth instance of
  *an inert thing still passes*).
- **Done (state it as an opposition, per the 16.14 lesson):** `corr(floor, adp) <= 0` within **every**
  position, and the top-10 `floor` list is not dominated by ADP > 130 players. Report the new
  top-floor lists to the user before any seat consumes them.

### Step 3 — Board scope: the three things the value hawk is blind to → `draft/enrichment.py`
This settles **16.14R open decision #3** with evidence. The user's value-hawk objections (DK Metcalf,
Dylan Sampson, James Cook) are **not mis-weights — they are blind spots**. None of the following is
on the 16.13 board, so *no* objective function over today's board can avoid those picks:
1. **Signed** situation change. `cos` exists but is **unsigned**: `COS_WEIGHTS` scores *how loud the
   story is*, never whether it is good or bad. Rachaad White reads `cos` **1.0** (max) and DK Metcalf
   **0.6**. Split into magnitude + direction.
2. **Committee / depth-chart share** (Sampson behind Judkins) — available from `depth_charts`.
3. **TD-dependency / regression risk** (Cook) — from the Phase-3 efficiency work.
- Ships as **labelled, read-only, default-OFF** context, per the "level, not the residual" rule.
- **Done:** coverage report + a spot-check that Sampson/Metcalf/Cook carry the expected signals.

### Step 4 — `safe_floor` rework → `draft/personalities.py`
Objective becomes **lowest downside**, not *highest residual floor*: the Step-2 floor, an explicit
penalty on `q90 − q10` spread, rookie and injury-return penalties (Carnell Tate, Malik Nabers), and a
**minimum projected level** so "reliably useless" cannot win. **Done (opposition form):** `safe_floor`
and `reacher` disagree on ≥ X % of picks, and its drafted pool shows *lower spread* than `balanced` —
not merely higher floor.

### Step 5 — `reacher`: direction first, then a reach budget → `draft/personalities.py`
**The reacher currently has width with no direction.** Its literal definition is
`Personality("reacher", temperature=2.2, width_mult=WIDTH_REACHER)` — **no `signal_weights` at all**.
The user's "these reaches are nonsensical and have no basis" is exact: it is a hot softmax over a
widening band with zero opinion attached. Mean `pool_rank` **20.5** vs a corpus p90 of 13.1.
- **5a. Direction first** — rookies, the 16.10 hype board, the 16.9 shock (the retired homer's
  channel, which 16.14R already assigns here). *A reacher that reaches **for something** is most of
  the fix.*
- **5b. Then the budget** (user's spec, 2026-07-27): ≤2–3 **large** reaches (>25 picks) permitted only
  in round 5+; 3–5 **medium** (8–15 picks) in round 3+; rounds 1–3 clamped near `balanced`.
  ⚠ **Architectural note:** a budget is **stateful per seat**, and `make_opponent_pick_fn` is a
  stateless softmax today. This needs per-seat draft memory — scope it before starting.
- **Done:** reacher's max reach ≤ 2× balanced's at *every* round (already in the done-when), plus a
  hard per-round deviation ceiling at the corpus p95.

### Step 6 — Build `value_hawk` properly → `draft/personalities.py`, `draft/optimizer.py`
Bounded-window argmax on the value board = the Phase-9 greedy with a reach constraint, **on the
Step-3 board**. **This resolves 16.14R open decision #1 in favour of portfolio CE, and the argument
is now measured, not aesthetic:** within position, `corr(vbd, adp)` = **−0.955 RB / −0.924 WR /
−0.859 QB / −0.907 TE**, and `signal_bonus` z-scores *within position* — so `pos_z(vbd)` destroys
VBD's only non-ADP content (the cross-position comparison) and the seat becomes a chalk tilt with
extra width. Measured in the mock: it gained **+0.065** vbd-z over `balanced` and finished **5.5/10**,
behind `safe_floor`. **A `signal_weights` value hawk cannot work.** CE is roster-level and survives.
Report its projection ranking as **descriptive** (the evaluation trap, unchanged).

### Step 7 — Room composition + full re-measure
Drop to **≤1 autopilot**. Over 60 seeded drafts it finished **1.69 / 10** and won **48.3 %** while
2-of-10 seats over-represents a behaviour that is **0.2 %** of real seats. Re-run all five T15 bars,
the seat-faithfulness population, and the **16.10 done-bar at 15 rounds to close T16**.

**What the mock already proved about composition (do not re-derive):** swapping `homer` +
`upside_chaser` for `value_hawk` + a second `safe_floor` moved the open T15 faithfulness gap from
median `pool_rank` **10.40 → 8.59** (corpus 7.62) and the moderate band **13.5 % → 24.3 %** (corpus
54.3 %) **with no model change at all**. Some of what reads as a model defect is a composition choice.

### 16.15 — Mock-room composition + hype coupling + app → `draft/simulator.py`, `app/`
- **Do:** (a) a **configurable opponent seat-assignment** — a default *realistic mix* over the 9 opponents
  (e.g. a couple Autopilot/Balanced, one each Upside/Safe/Homer/Reacher), user-overridable; (b) **couple the
  hype shock** — route the 16.9 per-draft narrative shock so it is expressed through the Upside/Homer seats
  (hyped players get over-drafted *because* those personalities reach); (c) a **Phase-14 app control** to
  pick/see opponent personalities in a mock draft (the "who am I drafting against" selector).
- **Out:** a seat-assignment helper + default mix in `draft/simulator.py`; the shock→personality coupling;
  an app selector spec noted in `docs/PLAYER-VIEW.md` / the Phase-14 mock-draft view.
- **Done:** a mock runs against a named, realistic, user-tunable personality room; the hype shock rides the
  right seats; the app exposes the selector — **all read-only w.r.t. the frozen value/optimizer/cost stack.**
- **Reuse:** `draft/simulator.py` `simulate_draft` opponent-fn plumbing, 16.9's shock, `app/streamlit_app.py`.
- **☑ BUILT 2026-07-27** (`draft/personalities.py` — `DEFAULT_ROOM`/`make_room`/
  `normalized_hype_gains`/`make_room_pick_fn`; `steps/phase16_15_mock_room.py` →
  `analysis/phase16_15_mock_room.json`; selector spec `docs/PLAYER-VIEW.md` §9; 12 tests).
  - **Deviation from this plan, deliberate:** the room lives in `personalities.py`, **not**
    `simulator.py`. Composing a room needs `Personality`, and making the draft engine every earlier
    phase runs on import the Phase-16 personality library would invert the layering — a realism
    feature underneath the frozen optimizer/sim path. `personalities.py` already imports only
    `opponent_model`, so this adds no import edge.
  - **(a) composition ☑** — hand-set default mix, **corpus-checked** on 3,309 eligible-redraft
    managers (median QB share 12.6 %, RB 31 %, **1.7 % RB-light** ⇒ no `zero_rb` seat by default).
    The corpus can *check* a mix but cannot supply one: tendency is observable, personality is a
    latent label. Position share is computed **from picks alone** because the stored `avg_reach` is
    a pooled-board mismatch (**T18**).
  - **(b) hype coupling ☑, and it is a NULL at the shipped shock size** — Phase 16's fifth. The
    calibrated 16.9 draw is **1.48 ADP picks**; largest per-seat move **0.036**, routing-vs-gain
    **+0.07**. The *same* shock ×10 gives **+0.91** (sweep ×1→×40: +0.07 · +0.53 · +0.84 · +0.91 ·
    +0.95), so the mechanism is correct and waiting on a signal worth routing. The done-bar gates
    the **mechanism** at `AMP_GATE` and **reports** the shipped size — tuning the shock up to pass
    would tune a calibrated parameter to a face-validity check.
  - **★ Ceiling scope changed:** `max_reach_picks` bounds a seat's **own opinion**
    (`signal_weights` + fandom excess); the shared shock is applied **outside** it. 16.9 fitted the
    shock uncapped and uniform, so clipping it uses a fitted parameter outside its estimation
    conditions. Folded in, a seat whose signals saturate its ceiling cannot express the story and
    **nothing fails**. Visible only once the bar was restated across **all nine seats** — the
    two-ended *chasers − autopickers* gap passes on a room routing the story backwards.
  - **(c) app selector ☑** — spec only (the app itself is Phase 14, by the app-strictly-last rule):
    `docs/PLAYER-VIEW.md` §9 carries the call contract, the per-personality UI labels, the default
    room, and four honesty rules (not predictive · the hype channel is a null · composition
    redistributes rather than amplifies · the ceiling bounds opinion, not the room's story).

**Done-when (personality cluster):** 16.13 enriches the board read-only; 16.14's 5 personalities pass
face-validity + mechanics unit tests; 16.15 assigns a realistic room, couples the shock, and surfaces the
selector — the whole cluster provably isolated from the frozen value stack.

### 0.11 — ECR + Underdog ADP ingest → `data/sources/`, `steps/phase0_11_ecr_underdog.py` *(added 2026-07-23)*
- **Do:** ingest two new market sources. **(a) FantasyPros ECR** — the expert-consensus *rank* pages (distinct
  from the projection pages `consensus.py` already scrapes), giving the *true* expert-rank-minus-ADP signal 16.8
  currently proxies with the VBD-ADP gap; live-only, PIT-stamped. **(b) Underdog ADP** — the sharp best-ball
  market (deferred back in Phase 0.4), the cleanest `source_divergence` input for 16.8 and the realistic board
  for best-ball (15.2).
- **Out:** `data/sources/ecr.py` + `data/sources/underdog.py` (or extensions), rows in `adp_snapshots`/a new
  `ecr_snapshots`, gsis-matched; freshness/schema gates (T7 pattern).
- **Done:** ECR + Underdog boards ingest gsis-matched ≥95 %, PIT-clean; 16.8 can consume both. **Validation:**
  in 16.8, does true-ECR beat the VBD-proxy on drift MAE?
- **◐ PART-BUILT 2026-07-25 (`data/sources/ecr.py`, `steps/phase0_11_ecr.py`) — ECR ☑, Underdog deferred.**
  **17,264 rows, 2017–2026 × {ppr, half-ppr, standard}**, 99.2 % gsis on top-150 skill; carries rank,
  **expert disagreement** (`ecr_std`, min/max over 90–243 experts), tier, ECR delta. Also covers **2025,
  where FFC has no board at all**.
  - **★ The stated validation question is UNANSWERABLE and that is now measured, not assumed.** The
    `?year=` archive is genuinely historical, but every board is a single **end-of-preseason snapshot**
    stamped 9/06–9/11 — after the drafts it would explain (**1 of 38** corpus drafts post-dates its own
    stamp). `ecr_asof` enforces this structurally: a draft-day as-of returns an **empty frame**. So 16.8
    keeps the VBD proxy; ECR is a **live-season** input (16.10/16.11) and a season-outcome expert baseline.
  - **⚠ `is_preseason` flag added:** the 2023 PPR board carries `as_of = 2024-02-12` (re-touched after the
    Super Bowl) — it saw the season it should precede. Flagged per row, excluded from draft-season baselines.
  - **Underdog DEFERRED (user decision), not attempted:** no keyless endpoint — marketing routes 404, board
    is a JS app on an unpublished API. Recorded so it is not re-discovered.
- **Reuse:** `data/sources/adp.py` (match/snapshot machinery), `projections/consensus.py` (`_pull_fp` pattern),
  `data/validate.py` gates.

### 16.16 — Live-draft reactive re-estimation (run detection) → `draft/opponent_model.py` *(added 2026-07-23, item D)*
- **Do:** mid-draft, detect a positional **run** (elevated recent pick-rate for a position vs its ADP-implied
  rate) and update the room's live tendencies (bump the `pos_run3`/positional pressure so availability
  forecasts react) — "RBs are flying, your window is closing faster than ADP says." Extends the 11.1/11.2
  opponent/availability model (portable Tier-A features, no corpus refit).
- **Out:** a run-detector + a live tendency adjustment in `draft/opponent_model.py`/`draft/availability.py`; a
  surfaced alert wired into the Phase-14.4 live-draft view.
- **Done:** **face-validity in replay** — on real Sleeper drafts, the detector fires on actual runs and the
  updated availability forecast beats the static one *within the run window* (a light held-out check, not a full
  Brier gate). **Reuse:** `draft/availability.py` `simulate_survival`, 11.1 features, the Sleeper corpus.
- **☑ BUILT 2026-07-26 (Session G 2/2) — the detector WORKS, reacting to it DOES NOT. Phase 16's fourth
  null; ships DEFAULT OFF (`RUN_W = 0`).** `opponent_model.detect_run`/`run_bonus`, an opt-in `run_w` in
  `simulate_survival` + `availability_brier` (both inert at 0), `steps/phase16_16_run_detection.py`.
  - **Q1 fires correctly — after a fix.** Intensity is a position's share of the last 10 picks minus its
    share of the **live candidate set** (top-40 by ADP). Scored against the *whole remaining pool* — which
    is WR-heavy at every depth — it fired on **61 %** of 7,957 replayed windows and *anti*-discriminated
    (0.268 vs 0.278). Against the candidate set the threshold sweep is **monotone**: at intensity 0.50 a
    flagged position takes **0.382** of the next 5 picks vs 0.274 unflagged (**+0.109**). The threshold is
    a free parameter, so the whole curve is reported rather than one flattering point.
  - **Q2 fails, monotonically.** Paired availability Brier on 4,300 run-opened windows: `run_w`
    **0.0 → 0.2121 · 0.5 → 0.2123 · 1.0 → 0.2128 · 2.0 → 0.2186**. Every bump is worse, in order of size.
    *Likely reading (flagged as a reading): **double-counting** — 11.1 already carries `pos_run3`, so an
    extra positional bump adds bias without information. Confirming it means refitting 11.1 (cf. T15).*
  - **Kept, not default** — the detector is a genuinely useful **live-draft alert** for 14.4 ("RBs are
    flying"), a UX claim its face-validity evidence supports independently of forecasting.

# Phase 17 — League-Format Fidelity & Custom Settings *(new 2026-07-23; correct advice for ANY league)*
*Goal: the engine hard-codes vanilla 10-team full-PPR 1-QB (`RosterSlots.qb=1`, `flex=1`, `season.py` raises
`NotImplementedError` for multi-flex), so it gives **silently wrong** advice for superflex / custom leagues —
a correctness gap that hits every non-vanilla user regardless of skill. This track generalizes the format
contracts. **Not a modeling change to the frozen stack** (a config generalization); the lockbox-validated
default result stays valid, non-default formats are supported but **labeled not-lockbox-validated**. **IDP =
future-work** (nflverse IDP data too thin). User decisions (2026-07-23): a **platform-agnostic manual settings
form** (not Sleeper auto-import — users are on ESPN/Yahoo/etc.); "anything at all" = offense + K + DST +
superflex/flex/roster-count + PPR/custom scoring; IDP deferred; optional platform auto-import is a secondary
future convenience. Full scoping: `PLAN.md`, 2026-07-23 (formats) entry.*

### 17.1 — Roster + lineup generalization → `draft/simulator.py`, `simulation/season.py`
- **Do:** generalize `RosterSlots` (arbitrary `qb` count, **multiple flex**, a **superflex/OP** slot,
  no-kicker, custom bench/team-count) and the vectorized optimal-lineup solver in `season.py` (remove the
  single-FLEX `NotImplementedError` — handle ≥1 flex + superflex correctly); recompute VBD replacement levels
  per format (`backtest/metrics.py`) so the value board is right — **superflex lifts QBs into the top tier.**
- **Out:** a generalized `RosterSlots` + multi-flex solver + format-aware replacement.
- **Done:** the solver **matches a brute-force optimum** on random multi-flex rosters; a superflex value board
  drafts QBs early (face-validity vs the 1-QB board). **Reuse:** `simulation/season.py` `lineup_points_matrix`,
  `backtest/metrics.py` replacement, `draft/simulator.py`.
### 17.2 — Custom scoring generalization → `backtest/scoring.py`
- **Do:** extend `RuleSet` to arbitrary per-stat point values (TE-premium, custom passing-TD, PPR variants,
  bonuses) with standard/half/full presets; consensus + realized re-score through the chosen `RuleSet`
  (partly there — `rec` is already configurable; extend to the full stat map + presets).
- **Out:** a full custom `RuleSet` + presets. **Done:** a TE-premium / custom-scoring board re-ranks sensibly;
  scoring round-trips. **Reuse:** `backtest/scoring.py` `RuleSet`/`score_offense`.
### 17.3 — Generic league-settings input contract → `draft/config.py`
- **Do:** a **platform-agnostic** `LeagueSettings` object + parser/validator that builds `RuleSet` +
  `RosterSlots` + `LeagueFormat` from arbitrary user input — presets **or** full custom (add superflex/
  multi-flex, drop the kicker, change team/bench count, custom scoring). The contract the Phase-14 app form
  binds to. Validate (legal roster, sane scoring); clear errors.
- **Out:** `draft/config.py` `LeagueSettings` builder + validation. **Done:** round-trips presets + a
  fully-custom league into correct `RuleSet`/`RosterSlots`/`LeagueFormat`; bad input errors cleanly.
  **Reuse:** existing `RuleSet`/`RosterSlots`/`LeagueFormat`/`DraftConfig`. *(Optional future: a Sleeper
  free-API auto-import that pre-fills the form — secondary, never the primary path.)*
### 17.4 — Keeper support → `draft/simulator.py`, `adp/`
- **Do:** keeper settings that **remove kept players from the draftable pool** and **re-inflate everyone's
  effective ADP** (the board shifts up); price a keeper's cost as the forfeited draft pick.
- **Out:** keeper-aware pool init + effective-ADP recompute. **Done:** kept studs vanish from the board, ADP
  shifts up sensibly (face-validity). **Reuse:** `draft/simulator.py` pool init, `adp/` ADP machinery.
  *(The nearer-term subset of the deferred Phase-15.1 dynasty.)*
- **Done-when (Phase 17):** superflex mock drafts QBs early; solver matches brute-force multi-flex optimum;
  custom-scoring board re-ranks; the settings contract round-trips presets + full-custom; keeper league removes
  players + shifts ADP — all with correctness/face-validity unit tests; non-default formats labeled
  **not-lockbox-validated**.

---

# Personalization spine *(NEW — the reframe's MVP-critical track; spec: `docs/PERSONALIZATION.md`)*
*Goal of the group: the direct-indexing machinery — a constraint object, a constrained optimizer, and an
honest cost report — layered on Phases 0–5. Cross-phase; this is what the near-term MVP is built around.*

### S1 — Preference-spec layer → `personalization/config.py`
- **Do:** a pydantic `DraftConfig` (league context incl. **superflex**, archetype, must/never + reach
  budgets, tilts in rounds, risk dials, fandom/character/injury/rookie tilts, benchmark set, control tier)
  + a **precedence-chain resolver** (explicit > league-inferred > archetype-implied > population prior).
- **Out:** `personalization/config.py` (`DraftConfig`, `resolve`) + archetype preset table.
- **Done:** any partial input resolves to a complete, valid config; `never_draft`/roster legality inviolable.

### S2 — Constrained optimizer → `personalization/optimizer.py`
- **Do:** maximize **consensus-VBD value** s.t. hard excludes + soft tilts (± rounds) + archetype priors +
  per-round risk dial, planning around **ADP availability**; greedy first (live-usable), lookahead later.
- **Out:** `personalization/optimizer.py` (`optimize_pick`, `optimize_board`).
- **Done:** excludes never appear; a tilt shifts a player ~its budget; output is one legal, fully-filled roster.

### S3 — Cost-of-personalization report → `personalization/cost.py`
- **Do:** build the **benchmark-optimal** roster (same optimizer, no personal constraints) and decompose
  the value / championship-equity gap **per decision**; lead with **relative/directional** cost.
- **Out:** `personalization/cost.py` (`cost_report`) + `analysis/results/cost_report_*.json`.
- **Done:** "locking X / refusing Y cost ~N PAR and ~M% title-prob," per-decision, vs ≥1 benchmark.

### S4 — Behavioral opponent model → availability → `draft/opponent_model.py`, `draft/availability.py`
- **Do:** fit opponent behavior (positional runs, reaches, hometown/name-brand bias, rookie hype, K/DST
  panic, handcuffs) from **real completed drafts** (Sleeper — open decision); survival → **per-pick
  availability distributions**; Brier-score vs held-out picks.
- **Out:** `draft/opponent_model.py`, `draft/availability.py` (`availability_at(pick)`).
- **Done:** beats ADP+noise on held-out pick prediction (Brier); powers the realistic mock + "who's left next."

### S5 — Risk dial → `personalization/risk.py`
- **Do:** map the per-round/global risk + correlation appetite to a value/variance objective the optimizer
  uses (powered by the trimmed Phase-5 distributions).
- **Out:** `personalization/risk.py`. **Done:** raising the dial shifts the board toward higher ceiling.

### S6 — Adaptive archetypes → `draft/config.py` (`"adaptive"` + `_adaptive_tilt`) ✅ *(2026-07-12)*
- **Do:** archetypes as configs; the **adaptive** one re-evaluates when value falls to it (elite RBs slide
  → drop Zero RB). **Out:** *(implemented in `draft/config.py`, where the spine lives, not a new
  `personalization/` package)*. **Done:** adaptive beats its static parent when the board diverges from ADP,
  in sim.
- **DONE (2026-07-12):** a **wrapper on an `adaptive_parent`** that **melts a *fade*** in proportion to
  ADP slide (`slide=(overall−adp)/n_teams`; `ADAPT_DECAY`, `ADAPT_SLIDE_WEIGHT` — sliding value melts ~2× a
  reach; a fade only melts toward 0; reaching archetypes untouched; no board context ⇒ = parent, so
  leave-one-out/benchmark behave). Threaded via `total_tilt_rounds(adp=, overall_pick=)` + `_greedy_eff`.
  **Done-bar PASS** (`steps/spine_5_adaptive.py`): does no harm in the ADP room, **banks team-value in the
  realistic Phase-11 behavioral (board-breaking) room** — adaptive(zero_rb) +2.0, adaptive(hero_rb) +15.6.

### S7 — In-season weekly-edge harvester → `inseason/*` *(the tax-loss-harvesting analog; = Phase 13, pulled in)*
- **Do:** start/sit (floor vs ceiling by matchup), FAAB, streaming, trades respecting "never trade my
  favorites," buy-low/sell-high. **Done:** each beats a naive heuristic on backtested seasons.

---

## Cross-cutting (every phase)
- **Log:** outcome → `findings.md`; new terms → `glossary.md`; per-step notes/dead-ends → `PLAN.md`.
- **Gate (⟳ reframed 2026-07-04):** the bar is **calibration + honest cost**, not beating ADP. A value
  step must be **well-calibrated** (reliability/coverage); an availability step must beat ADP+noise on
  **Brier** over real picks; the cost report must lead with **robust relative/directional** numbers.
  Keep a **lockbox** (freeze recent seasons; evaluate the final stack once). "Beat ADP" is optional.
- **Status:** tick `ROADMAP.md` as each step lands.
