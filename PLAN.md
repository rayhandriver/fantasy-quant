# PLAN.md — the HOW (living lab-notebook)

Working notes only: implementation choices, parameter picks, and dead ends **as they arise during a
step**. This file does **not** restate the goal, scope, decisions, or phase plan — those live in
`PROJECT.md` (§1–§5). Keep it terse; newest at the bottom.

## Current state
- **2026-07-03** — **PHASE 1 COMPLETE.** Phase **1.5 done** (significance: stationary block-bootstrap CIs;
  ADP-vs-ADP edge 0 not-sig; worst-first −577.6/season CI [−714,−438] sig; block SE 0.239 > iid 0.090).
  Harness scores any rank_fn end-to-end PIT with CIs vs ADP in one call. **Next: Phase 2 — markets & baselines.**
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

**1.5 significance:**
- `block_bootstrap_ci` = **stationary bootstrap** (geometric blocks, expected ≈ n^{1/3}); `expected_block=1`
  = iid → the two are directly comparable. Returns point/CI/SE/`significant` (CI excludes 0).
- `compare_to_baseline` runs a **paired** walk-forward (same seeds → matched opponents/seats) and bootstraps
  the **per-season** PAR-diff series (11 pts). Replacement level cancels → PAR-diff = starter-pts diff.
- Market baseline = same call with a market `rank_fn` (Phase 2.3). Small-`n` reality: 11 seasons, block ≈ 2.

## Open questions (to resolve at the relevant step)
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
- **14.2 app:** how many personalization levers to expose in v1.

## Dead ends
- _(none yet)_
