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

### 16.1 — Team-change + new-starting-QB ADP-alpha extension → `adp/panel.py`, `adp/regression.py`
- **Do:** add `team_changed` (offseason team differs from prior season, trade/FA/waiver — free off the
  existing panel) and `new_starting_qb` (team's QB1 by pass attempts changed year-over-year, >50%
  team-attempts threshold to count as "starter") to the Phase 6.1 panel; refit 6.2's regression + 6.3's
  BH-FDR scorecard on the enlarged feature set.
- **Out:** updated `adp/panel.py` (`FEATURES`), `adp/regression.py`, `adp/scorecard.py` outputs.
- **Done:** each new feature reports a season-block-bootstrap CI + BH-FDR-adjusted p-value + sign-stability
  %, same discipline as DURABILITY — survive or honestly drop, no threshold moved after seeing the result.
- **Reuse:** `adp/panel.py`, `adp/regression.py`, `adp/scorecard.py` (Phase 6) wholesale — only the feature
  set changes.

### 16.2 — Competition-change signal, dual-sourced → `adp/panel.py`
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

### 16.3 — Playcaller/coaching history table → `data/sources/coaches.py` (or a static reference table)
- **Do:** Claude drafts a table (HC/OC · team · seasons · `is_playcaller` flag · ambiguous-case notes) via
  web research, covering DEV-window playcaller changes (2014–2022) plus this year's relevant hires;
  **user reviews and corrects before it's used anywhere downstream.** Scope: the ~10–15 fantasy-relevant
  moves/year, not a comprehensive scrape of all 32 teams' full staff history.
- **Out:** a small, versioned, human-approved reference table.
- **Done:** user has explicitly signed off on the table's contents before 16.4 consumes it.
- **Reuse:** none — this is the one piece with no existing free source (`home_coach`/`away_coach` in
  `pbp`/`schedules` is head coach, not necessarily playcaller — checked, insufficient alone).

### 16.4 — Scheme fingerprint + transport → `causal/` or a new `situation/fingerprint.py`
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

### 16.5 — 2026 live situation-change event board → a small hand/research-built reference table
- **Do:** identify this year's actual offseason situation-change events (trades, FA signings, coaching
  hires that already happened) via research, similar in spirit and scope to 16.3.
- **Out:** a current-season event list feeding the 16.6 tab.
- **Done:** the beta tab has real, current content for this year's draft, not just historical proof of
  concept.
- **Reuse:** 16.3's research/review workflow.

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

### 16.10 — Curated hype-board override → `adp/hype_board.py` + `reference/hype_board.csv`
- **Do:** a small editable table (`player_key · pick_delta · note · source`), Claude-drafted via web research
  + **user-reviewed before use** (same contract as the 16.3 playcaller table), capturing the qualitative
  narrative residual pure market signals miss. A loader applies it as a bias on the opponent utility /
  survival on top of the quantitative drift, live-season only, PIT-stamped.
- **Out:** `reference/hype_board.csv` (versioned), `adp/hype_board.py` (`load_hype_board`, `apply_hype`).
- **Done:** the board loads, is user-approved before wiring, and shifts a hyped player's simulated draft slot
  in the expected direction; explicitly labeled **curated, not a backtested claim.**
- **Reuse:** 16.3's research/review workflow; the 16.9 shock as the application channel.

### 16.11 — Live 2026 momentum / ADP velocity → `adp/momentum.py`
- **Do:** compute ADP **velocity** = slope of a player's ADP across the Stage-0 2026 snapshot **series**
  (`adp_snapshots`, banked weekly since 2026-07-09). Feed it as an additional live drift input.
- **Out:** `adp/momentum.py` (`adp_velocity(con, season)`), a per-player slope + recency-weighted current ADP.
- **Done:** velocity computes on the 2026 series; **explicitly labeled forward-only / not backtestable** (no
  historical intra-season series), validated **live on 2026** as snapshots accrue — the 16.4-style
  descriptive-honesty bar, not a walk-forward gate.
- **Reuse:** `adp_snapshots` series, `data/sources/adp.py`.

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

**Done-when (personality cluster):** 16.13 enriches the board read-only; 16.14's 5 personalities pass
face-validity + mechanics unit tests; 16.15 assigns a realistic room, couples the shock, and surfaces the
selector — the whole cluster provably isolated from the frozen value stack.

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
