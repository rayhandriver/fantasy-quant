# PLAN.md — the HOW (living lab-notebook)

Working notes only: implementation choices, parameter picks, and dead ends **as they arise during a
step**. This file does **not** restate the goal, scope, decisions, or phase plan — those live in
`PROJECT.md` (§1–§5). Keep it terse; newest at the bottom.

## Current state
- **2026-07-07** — **PERSONALIZATION SPINE DONE (S1–S3 + S5)** — the direct-indexing MVP, run straight-through
  (gate waived, per the 4→5 cadence). Built/validated on **DEV 2022** (latest non-lockbox season w/ ADP +
  realized); **season is a parameter** (a scraped 2026 board drops in unchanged). **S1** `draft/config.py` —
  `DraftConfig` (the contract we own): league context, one **archetype** (master positional dial), hard
  `never_draft` + `must_draft`(reach budget), soft `tilts` (rounds), `risk_lambda`; validated on construction;
  `benchmark()` strips prefs, `without_constraint`/`constraint_labels` drive LOO. Trimmed to §7 MVP (no fandom/
  correlation/control-tier fields until needed). **S2** `draft/optimizer.py` — constrained greedy over the
  Phase-1.2 simulator (pluggable `your_pick_fn`, no new engine). **`base_value` = risk-adjusted
  value-over-replacement** (Phase-5 CE − positional replacement; VBD scale + λ dial in one); tilts convert
  rounds→priority (`eff = base_rank − n_teams·tilt`); **must-draft = pure availability planning** (take at the
  last responsible pick within budget, using snake geometry + noise margin — never overreach). **S3**
  `valuation/cost_report.py` — personalized vs `benchmark()` over the **same seeds**, differenced into one
  headline (pts + %), attributed per preference by **leave-one-out**, + must-player **secured fraction**;
  relative/directional per §7 (walk-forward realized-PAR = next layer). **S5** risk dial wired in (λ → CE →
  `base_value`). **UI** `app/streamlit_app.py` — Streamlit Autopilot (archetype+seat) + Co-pilot (λ, must/
  never/reach/wait), personalized board **beside** the baseline + cost readout, no LLM. **Bug caught:**
  stateless archetype tilts made `elite_te` draft **two** TEs → made archetypes **roster-state-aware** (`have`
  count) so "grab one anchor" stops after the first (regression-tested). **137 tests (was 120), ruff clean; 3
  spine step scripts green; Streamlit app verified via `AppTest`.** `streamlit` added as a `ui` extra. **Next:
  Phase 8 covariance (portfolio Var under the same λ) · S4 behavioral opponent model · realized-PAR validation
  · scrape 2026 ADP to go live.**
- **2026-07-05** — **PHASE 5 DONE** (distributional layer — the per-player risk dial; full 5.1–5.5 stack,
  season-total grain). **5.1** per-position linear `QuantReg` of realized pts on the calibrated mean, fit on
  the conditional/available DEV cohort (1,074 player-seasons; median slope ≈1.10; band fans with level 3/4
  pos). **5.2** CQR (Romano 2019) per-pos adjustment (QB +18/WR +3/RB +2/TE +0 on [2021,2022]); **2025
  holdout coverage 70%→73%** on the available cohort. **5.3** weekly boom/bust: right-skew confirmed (TE
  +1.60…QB +0.23); **corr(boom,CoV) −0.37** ⇒ boom rate is a level axis, separate from volatility. **5.4**
  logistic **discrete-time availability hazard** (31.6k player-weeks) → **Beta-Binomial games-played**
  (ρ=0.33, keeps the lost-season tail); coefs sane (prior-avail +0.42, RB least available). **Assembler**
  `distribution.py`: `Y=H·(avail_frac/G_ref)` Monte-Carlo cloud (2000 draws) → frozen contract
  `player_key·pos·mean·sd·q10·q50·q90·boom_prob·bust_prob·games_played_mean·ce_value`; **5.5** mean-variance
  CE `E[Y]−λ·Var[Y]` risk dial + `risk_premium`. Wrote `player_distributions` (673 rows, 2025). **2 real bugs
  fixed** (both on 2025/first-season paths 5.1–5.4 never hit): `value_board` crashed on an empty projection
  season (2014 has no proxy → empty arrow-string − float) → guarded to return an empty contract frame; and a
  **units bug** `G/G_ref` (games *count* ÷ *fraction*) inflated means ~17× → fixed to `(G/team_games)/G_ref`
  (regression-tested). Conditional 2025 coverage **76% ≈ 80%**; unconditional full-board **44%** = **role/depth
  attrition** the injury-only model doesn't capture (documented limitation → future work). **Method deviations
  (accepted, no new deps):** statsmodels `QuantReg` not XGBoost (5.1); sklearn logistic hazard not `lifelines`
  (5.4) — future intent to adopt XGBoost-quantile / `lifelines` if the sample justifies it. 120 tests, ruff
  clean; all 5 steps green. **Next: personalization spine — `DraftConfig` + constrained greedy optimizer +
  first cost report → Streamlit MVP** (Phase 8 covariance slots in via the same λ/Var).
- **2026-07-05** — **PHASE 4 DONE** (VALUE signal, reframed = consensus-VBD, not edge-seeking). **4.1**
  two-track consensus (`projections/consensus.py`): live = FantasyPros scrape re-scored to full-PPR via our
  `RuleSet` (528 players, 99% gsis, our-pts↔FP-FPTS corr 1.000; retry-guard beats FP's transient truncated
  pages), historical = Phase-2 baseline **proxy** (no free historical consensus exists); one
  `consensus_projection(season)` dispatches. **4.2** VBD value board (`valuation/value_board.py`): draft-time
  replacement from **projections** (realized doesn't exist for the season being drafted) at QB10/RB24/… ranks
  → QBs drop 6→0 in top-15 vs raw; **frozen contract** `player_key·pos·proj_points·source·vbd·pos_rank·
  overall_rank`. **4.3** rookie ridge (`projections/rookie.py`): closed-form per-position on log(draft_ovr)+
  landing-spot env, walk-forward; OOS Spearman **+0.62**; +76 rookies into the 2021 proxy board. **4.4**
  calibration (`projections/calibration.py`): proxy bias **0.60** played / **0.46** incl-DNP (survivorship
  haircut), reliability bin-corr 0.99, per-pos correction → 0.96; **2025 holdout (once): bias 0.58, Spearman
  +0.57**. Doc numbering reconciled (BUILD_PLAN/PROJECT had stale pre-reframe 4.x). 102 tests, ruff clean.
  **Next: Phase 5 — full distributional layer (user chose 5.1–5.5), wraps the 4.2 contract.**
- **2026-07-05** — **PHASE 3 DONE** (features `X`). 3.1–3.4 realized per-(gsis,season) facts (opportunity/
  efficiency/player/environment); 3.5 `build_exposures(target)` applies the PIT lag (prod←S-1, intrinsic
  as-of, env←S-1 of target team), winsor-z per position, missingness flags. **545×48 matrix**; 100%
  ADP-board cover; lagged WOPR↔next-yr pts +0.46; TD-regression flag −0.50; implied-total↔pts +0.86.
  92 tests, ruff clean. **Next: Phase 4 — consensus-projections ingest + VBD + rookie model** (needs a
  consensus source decision first).
- **2026-07-05** — **0.9 DONE** — 2025 backfilled via nflverse's new `stats_player` release (frozen
  `nfl_data_py` hits the dead old path). weekly→79,250 / seasonal→8,702 (2025 reconstructs PPR to 2.4e-6);
  timestamped `depth_charts_ts` (554k); validator PASS. Lockbox = **2023+2024**; **2025 = calibration
  holdout** (`config.CALIBRATION_SEASONS`; no ADP board → not a draft-backtest season). **Next: Phase 3.**
- **2026-07-04** — **⟳ STRATEGIC REFRAME** (`docs/REFRAME-2026-07-04.md`, `docs/PERSONALIZATION.md`):
  objective → **direct-indexing personalization** (build the team the user wants, price the cost vs
  optimal); team strength = tracked benchmark, "beat ADP" demoted. **Three signal layers:** value =
  consensus-VBD, availability = ADP+behavioral, variance = own distributions. Docs updated (STRATEGY Part
  0, PROJECT, ROADMAP, BUILD_PLAN, CLAUDE, glossary, findings). **Next: the personalization spine on Phases
  0–2** — Phase 3 `X` → consensus ingest+VBD+rookie → trimmed distribution → constraint object + optimizer
  + cost report → Streamlit MVP. **No code changed; Phases 0–2 valid.**
- **2026-07-04** — **PHASE 2 COMPLETE.** 2.1 VBD, 2.2 naive baseline (on par w/ ADP: −59 PAR/season
  CI[−162,+33]), 2.3 props (built+tested; **free-data gap** → no-op), 2.4 ensemble (grid-fit w=0.25 →
  2116 ≥ best component; vs ADP +80 CI[−22,+190] not-sig). Lesson: **don't fight the sharp market.**
  **Next: Phase 3 — feature engineering (exposure matrix X).**
- **2026-07-03** — **PHASE 1 COMPLETE.** Phase **1.5 done** (significance: stationary block-bootstrap CIs;
  ADP-vs-ADP edge 0 not-sig; worst-first −577.6/season CI [−714,−438] sig; block SE 0.239 > iid 0.090).
  Harness scores any rank_fn end-to-end PIT with CIs vs ADP in one call.
- **2026-07-03** — Phase **1.4 done** (PAR metric: replacement levels QB10/RB24/WR24/TE12/K10/DST10,
  2023 roster 1743; PAR ranks elite +818 vs scrub −943; PAR↔exp-wins corr 0.99).
- **2026-07-03** — Phase **1.3 done** (walk-forward harness: rank_fn → K drafts → realized optimal-lineup
  points, strict PIT; ADP baseline pools 2036, worst-first 1458 → harness discriminates; PIT guard trips).
- **2026-07-03** — Phase **1.2 done** (draft simulator: 10×15 snake, ADP+Gaussian-noise opponents,
  pluggable `your_pick_fn`, `DraftState`; ADP-typical roster + reproducible).
- **2026-07-03** — Phase **1.1 done** (scoring engine: full-PPR offense reconstructs nflverse
  `fantasy_points_ppr` across 57.3k player-weeks to 1e-6; K/DST derived from pbp/game_lines; K/DST
  identity bridge). League lineup settled: **9-starter QB/2RB/2WR/TE/FLEX+K+DST**.
- **2026-07-01** — **PHASE 0 COMPLETE.** 0.8 done (9 hard gates PASS, `data_health.json`; gate caught+fixed a
  0.4 homonym-collision bug). 16 tables, PIT panel layer, validator. **Next: Phase 1 — backtest harness.**
- **2026-07-01** — Phase **0.7 done** (weekly+preseason PIT panels, leak-assert, 41-col join).
- **2026-07-01** — Phase **0.6 done** (injuries/depth free 2014+, news_raw RSS pipe, PIT).
- **2026-06-30** — Phase **0.5 done** (game_lines free 2014–25, de-vig + implied totals; props key-gated).
- **2026-06-30** — Phase **0.4 done** (FFC ADP 2010–2024, PIT, gsis-matched; Underdog deferred).
- **2026-06-30** — Phase **0.3 done** (PFR advanced panels via nflverse mirror; reconciles 0.00%).
- **2026-06-30** — Phase **0.2 done** (nflverse → DuckDB, 8 tables, PIT-stamped).
- **2026-06-29** — Environment scaffolded; docs restructured into the granular Phase 0–15 plan (`PROJECT.md`)
  with Vegas markets promoted to a first-class data source.

## Working notes (per step)
**0.2 nflverse:**
- `gsis_id` is the spine. weekly/seasonal expose it as `player_id` (rename); ngs as `player_gsis_id`;
  **snaps has only `pfr_player_id`** → mapped via `player_ids.pfr_id` (pure fn `map_snaps_gsis`, unit-tested).
- Years default `2014..2025`; per-year pulls **skip-on-404** so an unpublished season can't abort the run.
- PBP loaded from a per-season parquet glob with `union_by_name=true` (handles cross-season schema drift);
  small sources written straight from pandas. Raw cache in `data/raw/nflverse/` → `--refresh` to re-pull.
- **Coverage asymmetry to remember:** PBP/snaps/draft/combine reach 2025; weekly/seasonal stop at 2024.
  Fantasy-point history (the backtest target) is therefore **2014–2024**.
- Toolchain note: run tests as `uv run python -m pytest` (the `pytest` console script won't spawn here).

**0.3 PFR:**
- Used the **nflverse PFR mirror** (`import_seasonal_pfr`) over direct PFR scraping — robust/reproducible,
  same data. Tables `pfr_pass`/`pfr_rec`/`pfr_rush` (kept split; `yds` means different things per type).
- **PFR advanced data starts 2018** → those features usable 2018–2024 only.
- Reconciliation (PFR yds == seasonal yds, 0.00%) doubles as a **join-correctness gate** on pfr_id→gsis.
- Unmatched ids (mostly O-linemen) logged to `data/raw/pfr/unmatched_pfr_ids.csv`; hand-fix genuine skill
  misses in `reference/pfr_id_overrides.csv`.

**0.4 ADP:**
- Source = **FFC JSON API** (`/api/v1/adp/{scoring}`); grid {standard,ppr,half-ppr}×{10,12}×2010–2024.
  `meta.end_date` = PIT `snapshot_date` (late-preseason). One snapshot per season-config.
- FFC has no gsis → `match_adp_to_gsis` 4-tier (team+pos+name → pos+name w/ draft-year tie-break → name →
  nickname override). Nickname misses fixed in `reference/adp_name_overrides.csv` (Hollywood→Marquise Brown…).
- **Underdog deferred** (auth-gated; no free history). Schema format-aware (`format='redraft'` for FFC).
- Gotchas: `rows` is a DuckDB reserved word; `.df()` returns DATE as pandas Timestamp.

**0.5 markets:**
- `game_lines` from nflverse `import_schedules` (free, 2014–25). `spread_line` = **home margin** (verified
  KC/DET). `implied_team_total = ((total+spread)/2, (total−spread)/2)`. Closing lines only (no movement).
- `devig` proportional; `fair_two_way` for moneylines (sums to 1, machine-epsilon). `captured_at = gameday`.
- Player props: `parse_props_payload`/`ingest_player_props` built + tested but **key-gated** (`ODDS_API_KEY`);
  no-op without a key. Win totals: `import_win_totals` empty → deferred.

**0.6 news:**
- `injuries` + `depth_charts` free/historical via nflverse, **native gsis** (no name-match). injuries PIT stamp
  = `date_modified`; depth grain = (season, week). `injuries_asof` proven PIT.
- `news_raw` = **forward-capture** RSS (ESPN/CBS/Yahoo); appends + de-dupes by `guid` → accumulates over time
  (schedule a periodic re-pull later). No gsis yet (entity resolution = Phase 12).
- **Inactives deferred** (no free historical importer; derive from snaps==0 or forward-capture).

**0.7 panel:**
- `weekly_panel`/`preseason_panel`; known-at gating: weekly-grain → week's last gameday (from game_lines),
  ADP → snapshot_date, injuries → date_modified. `assert_panel_pit` raises on any future-dated field.
- **FFC ADP is dated ~Sep 1** → preseason draft as-of must be ≥ that (Labor-Day weekend); earlier = empty board.
- `game_lines.gameday` is VARCHAR → cast to DATE for week-end mapping. NGS join = receiving-only for now
  (full multi-type pivot in Phase 3). team abbrevs (weekly.recent_team ↔ schedules) join directly.

**0.8 validate:**
- `validate_panel` raises on dupes / negative counting stats / bad snap% / PIT leak; `data_health_report`
  writes committed `analysis/results/data_health.json`. Only **counting** stats gated ≥0 (yardage can be neg).
- The adp-uniqueness gate **caught a real 0.4 bug**: homonyms (two 2010–11 "Mike Williams"/"Steve Smith" WRs)
  collided onto one gsis → added `dedupe_gsis_within_snapshot` (keep lower-ADP, null+log loser).
- Survivorship check filters to skill positions (K/DST aren't in offensive `weekly`). `rows`/`names` are
  DuckDB reserved words — quote aliases.

**1.1 scoring:**
- `RuleSet` is pydantic; **default `OffenseRules` == nflverse's formula** so `score_offense` validates
  against `fantasy_points_ppr` directly (0 rows over 0.02 tol across 57.3k player-weeks). Half-PPR/TE-prem
  = a config change (`rec=0.5`, etc.).
- Arithmetic in **pure fns** (`score_offense`/`kick_play_points`/`pa_tier_points`/`score_dst`), DB in thin
  wrappers → unit-testable with no DB (like `assert_panel_pit`).
- **K/DST come from `pbp` + `game_lines`, not `weekly`.** Kicker points keyed on `kicker_player_id` (gsis);
  DST keyed on `defteam` abbrev; `td_team == defteam` captures def + return TDs; PA = opponent final score.
  Blocked kicks not derived (approx). FFC ADP K/DST rows have null gsis → `resolve_kicker_gsis` (name→gsis
  via player_ids) + `dst_team_from_adp_name` (city→abbrev, relocations handled) bridge them for the harness.

**1.2 draft sim:**
- Board = **`adp_asof`** (not `preseason_panel`, which drops null-gsis DST via `WHERE gsis_id IS NOT NULL`).
  `_prepare_board` canonicalizes pos (PK→K, DEF→DST), drops non-draftable/null-ADP, sorts by ADP,
  re-indexes; `player_key` = gsis_id else name (DST → name).
- Opponents: `pick_by_adp` = argmin(adp + N(0,noise)) among under-cap positions; default `noise=5.0`
  (ADP points — only reorders nearby players, never lifts a late player to the top). Seeded rng → reproducible.
- **Caps are soft** (fall back to best-available when under-cap positions exhausted → never a short roster).
  Custom `your_pick_fn`s bypass caps (caps are only the opponent-realism knob).
- **FFC undersupplies K/DST** (~5 K / ~6 DST) → only ~3–5 of 10 teams draft each; empty slots = replacement
  later. Perf gotcha: compute roster counts **once per pick**, not per available player (was O(n²), 54s→2s).

**1.3 walk-forward:**
- `rank_fn(board, con, season, as_of) -> Series` on the **ADP/pick scale** (lower=sooner); NaN→ADP
  fallback. Harness sets `board["value"]=rank_fn(...)`; `value_pick_fn` drives your seat; opponents ADP+noise.
- Draft date = FFC **snapshot_date** per season (PIT as-of); `preseason_board` re-asserts no future snapshot.
- Board = `adp_asof` (incl. DST). Realized points: offense+K keyed by **gsis**, DST by **team** (via
  `dst_team_from_adp_name`). **Survivorship guard** = LEFT-JOIN drafted→realized (missing player = 0 pts).
- Season score = Σ optimal-lineup pts over all REG weeks (greedy optimal for a single FLEX). `k_drafts`
  rotate seats. ~0.27s/draft. Note: **you-by-ADP ≈ league avg** — edge vs ADP is 1.5, not here.

**1.4 PAR metric:**
- Replacement rank = league-wide started per position (`n_teams×slot` + FLEX split 2:2:1) →
  QB10/RB24/WR24/TE12/K10/DST10; level = that rank's **realized** season total; FLEX = best flex-eligible
  level. `par = roster_season_points − replacement.roster_total` (2023 total 1743). Adjustable via slots.
- Replacement uses realized totals (OK — PAR is an *evaluation* metric, not a PIT input). Secondary:
  `expected_wins` = all-play (schedule-independent), `final_standings` ranks by it; corr(PAR, exp-wins)=0.99.
  Exposed `roster_weekly_points` in walkforward for the weekly matrix.

**Phase 3 features (X):**
- Each 3.x module = **realized per-(gsis,season) facts**, lag-free + unit-testable; 3.5 assembly applies the
  **PIT lag**. Contract: production←target-1, intrinsic←as-of target, environment←target-1 of the **target
  team** (situation entered; right for movers/rookies). `assert_exposures_pit` enforces prod/env < target.
- Standardize: **winsorized (2/98) cross-sectional z per position**; missing → group-median before z +
  explicit `*_missing`/`no_prior`/`is_rookie` flags (rookies keep intrinsic signal, never silent-0).
- Robustness: clip tiny-sample rate outliers (aDOT/YPC/ypr) to physical bands so z-scoring isn't distorted.
- Gotchas fixed: QB EPA polluted by trick-play throwers → **≥100-dropback gate**; relocated team codes
  (STL/SD/OAK↔LA/LAC/LV) → normalize game_lines side; bogus `draft_year=0` → fall back to first weekly
  season; 0.1% missing birthdates → NaN age imputed in 3.5. `player_ids` has dup gsis (JEF270909 vs
  00-0036322) — weekly-derived modules use the 00-00 gsis, so no pollution.
- `FEATURE_MANIFEST` (43 z + flags) is the column contract Phase 4/5/6/7 select on. Run on `STATS_SEASONS`
  (feature *computation* isn't model selection; the lockbox binds selection in 4/5).

**0.9 2025 backfill / nflverse new-release:**
- nflverse restructured player stats after 2024. Old release `player_stats/player_stats_{yr}.parquet`
  (what frozen `nfl_data_py` hardcodes) has **no 2025** → 404. New release **`stats_player`**:
  `stats_player_week_{yr}` (weekly, REG+POST) + `stats_player_reg_{yr}` (seasonal) — covers 1999–2025.
- Conform renames: `player_id`→`gsis_id`, `passing_interceptions`→`interceptions`, `team`→`recent_team`,
  `sacks_suffered`→`sacks`, `sack_yards_lost`→`sack_yards`; reindex to legacy cols (weekly NA-fills only
  `dakota`; seasonal NA-fills the derived `_sh`/`dom` shares — recompute in Phase 3 from weekly/pbp).
- Append via `db.append_df` (INSERT … BY NAME); `DELETE season=yr` first → idempotent. Writable con.
- **Depth charts 2025 = new timestamped grain** (`dt` ISO8601, no `week`) → separate table `depth_charts_ts`
  (+`source_year`); PIT = latest `dt ≤ as_of` per player. Week-grain `depth_charts` (2014–24) untouched.
- 2025 has **no ADP board** (FFC empty) → `CALIBRATION_SEASONS=(2025,)`, kept out of DEV/LOCKBOX.

**1.5 significance:**
- `block_bootstrap_ci` = **stationary bootstrap** (geometric blocks, expected ≈ n^{1/3}); `expected_block=1`
  = iid → the two are directly comparable. Returns point/CI/SE/`significant` (CI excludes 0).
- `compare_to_baseline` runs a **paired** walk-forward (same seeds → matched opponents/seats) and bootstraps
  the **per-season** PAR-diff series (11 pts). Replacement level cancels → PAR-diff = starter-pts diff.
- Market baseline = same call with a market `rank_fn` (Phase 2.3). Small-`n` reality: 11 seasons, block ≈ 2.

**Phase 2 markets & baselines:**
- Architecture: `projection → vbd → vbd_rank_fn` (a one-line wrap to backtest any projection). Board key =
  gsis (offense/K) else name (DST); uncovered rows → NaN → ADP fallback in `value_pick_fn`.
- **2.2 baseline** = prior-season ppg, EB-shrunk (weeks/(weeks+6)) to positional mean, ×17, light age.
  Multi-position players (RB/FB) collapsed to one row per gsis (dedupe `player_key`, else pandas map dies).
  Naive VBD **overrates QBs** in 1-QB (elite QB VBD ≈ elite RB VBD, but ADP drafts QB rounds later).
- **2.3 props** = **no free preseason market data** (props live-only/paywalled; win totals empty; game_lines
  gameday-dated). `season_props_projection` no-ops → ADP. Math built+tested; a key/paid archive activates it.
- **2.4 ensemble** = `blend_rank_fn` weights component ranks (each NaN→ADP first). `fit_weight` grid-search
  (endpoints w=0 pure-ADP, w=1 pure-baseline → best ≥ both by construction). w=0.25 best in-sample (caveat).

## Open questions (to resolve at the relevant step)
- **⟳ REFRAME decisions (2026-07-04, `docs/REFRAME` §10) — highest priority:**
  - **Consensus-projections source (value signal).** Where do we get consensus projected points (e.g.
    FantasyPros aggregate)? Is it free / scrapeable / **PIT-snapshottable** for backtest seasons? This is
    the new value input (Phase 4 reframed) — confirm before building it.
  - **Human completed-draft data (Sleeper).** The behavioral opponent model + availability (S4) need
    real pick-by-pick drafts, not ADP averages. Confirm Sleeper's API exposes enough before committing;
    else availability falls back to ADP+noise.
  - **Benchmark set for the cost report.** Which to offer: ADP-consensus-optimal / our-projection-optimal
    / expert-consensus-optimal (recommend several — the benchmark is self-referential). *MVP (2026-07-07):
    a single benchmark = the **unconstrained value-optimal team from the same seat & λ**
    (`DraftConfig.benchmark()`), through the identical optimizer; the multi-benchmark set is deferred.*
  - ~~**Lockbox seasons.**~~ RESOLVED (2026-07-04) → **lockbox = 2023 + 2024**; dev on **2014–2022**
    (`config.DEV_SEASONS`/`LOCKBOX_SEASONS`). 2025 excluded (see below).
  - **2025 recovery — ROOT CAUSE FOUND (2026-07-04); planned as step 0.9 before Phase 3.** The 404 was
    **not** "rollup not out yet" — nflverse **restructured stats releases after 2024**; `nfl_data_py` is
    frozen on the *old* `player_stats/player_stats_{yr}.parquet` path (no 2025 file). The data lives in the
    **new `stats_player` release**: `stats_player_week_2025.parquet` (weekly ✅) + `stats_player_reg_2025.parquet`
    (seasonal ✅) — verified, schema-compatible (renames: `passing_interceptions`→`interceptions`,
    `team`→`recent_team`, `player_id`→`gsis_id`). **Plan (0.9):** new-release ingest path → append weekly +
    seasonal 2025 + handle timestamped `depth_charts`; re-validate. **Lockbox stays 2023+2024** (draft
    backtest); recovered 2025 = a **projection-calibration holdout** (no ADP board needed to check
    calibration). **Still blocked:** 2025 ADP (FFC empty for 2025; source via Sleeper/Underdog later →
    then 2025 becomes a full draft-backtest season).
  - **Paid props line.** Under the reframe it's even more optional — decide whether to ever cross it; if
    not, formally drop "beat the betting market" from the goals.
- ~~**0.4 ADP coverage:**~~ RESOLVED — **FFC** goes back to **2010** (free, JSON API; half-ppr only 2018+);
  **Underdog** best-ball requires auth (no free historical) → **deferred**, schema is format-aware for later.
- ~~**0.5 markets:**~~ RESOLVED — **game lines** (spreads/totals/moneylines) are **free & historical** via
  nflverse `import_schedules` (2014+). **Player props are paywalled historically** (the-odds-api live-only;
  key-gated) — the confirmed gap. nflverse `import_win_totals`/`import_sc_lines` are currently empty (deferred).
- **0.5 markets:** which de-vig method (proportional / Shin / power) and which books to aggregate.
- ~~**1.4/2.1 replacement level:**~~ RESOLVED (1.4) — 10-team 9-starter: QB10/RB24/WR24/TE12/K10/DST10
  (`n_teams×slot` + FLEX split 2:2:1). VBD (2.1) reuses `backtest/metrics.replacement_levels`.
- **6.x ADP-alpha:** target definition — finish-rank − ADP-rank vs points − slot-replacement.
- **10.x season-sim:** bye-week, injury (games-missed), and playoff-bracket fidelity.
- ~~**14.2 app:**~~ RESOLVED for the MVP (2026-07-07) — Streamlit **Autopilot** (archetype + seat) +
  **Co-pilot** (risk λ, must/never lists, reach/wait tilts); personalized board shown **beside** the pure-value
  baseline + the cost readout. The fuller **Manual** surface (fandom, correlation appetite, control tiers) is
  deferred to a later app version.

## Dead ends
- _(none yet)_
