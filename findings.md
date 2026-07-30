# Findings — fantasy-quant

Running record of what each step produced and what it taught. Newest at the bottom. (Mirrors the
intern-repo's findings log.)

---

## Setup — environment scaffold (2026-06-29)

**Goal:** stand up the repo and toolchain before any modeling code.

**What was done:**
- Repo at `~/projects/fantasy-quant` (kept fully separate from the internship — see the relocation note below).
- **uv** package manager + **pinned Python 3.12** (deliberately not the machine's system 3.14, for ML-wheel
  compatibility — XGBoost/LightGBM/PyMC).
- `pyproject.toml`: core scientific + scraping + viz + notebook stack; optional extras `data`
  (nfl_data_py) and `bayes` (pymc/arviz); `dev` group (pytest/ruff/mypy).
- **src layout** → the package installs editable, so `import fantasy_quant` needs no `sys.path` bootstrap
  (an improvement over the intern repo).
- Doc set mirroring intern-repo discipline: `README`, `CLAUDE`, `PROJECT`, `PLAN`, `ROADMAP`, `glossary`,
  `findings`; full strategy analysis ported to `docs/STRATEGY.md`.
- Local git initialized.

**Next:** Phase 0 — data pipeline + PIT walk-forward backtest harness.



## Relocation & internship separation (2026-06-29)

**Goal:** guarantee this project is 100% separate from the Bitbucket-based internship environment.

**Audit (all clean):** independent git repo (no umbrella git over `~/dev`); **no remote** on this repo
(internship's `intern-repo` → bitbucket, untouched); no hard path deps on the internship's `dev/venv` or
`dev/data`; separate uv-managed Python 3.12 venv; no global git URL rewrites forcing bitbucket.

**Action taken:** moved the repo **out of the internship's `~/dev/repo/` tree** to `~/projects/fantasy-quant`
(uv re-synced + Jupyter kernel re-registered at the new path; `import fantasy_quant` verified). Remote will
be a **private GitHub** repo only — never Bitbucket.



## 0.2 — nflverse ingest (2026-06-30)

**Goal:** land the core NFL signal in DuckDB, PIT-stamped, normalized onto `gsis_id`.

**What was built:**
- `config.py` (env/path resolution), `data/db.py` (DuckDB helpers — `write_df`, `write_parquet_glob`,
  every row stamped `pulled_at`), `data/sources/nflverse.py` (per-source ingest + orchestration),
  `steps/phase0_2_nflverse.py` (driver), `tests/test_nflverse_ingest.py` (no-network transform tests).
- Raw pulls cached to `data/raw/nflverse/*.parquet` (PBP per-season under `pbp/`) so re-runs don't hit
  the network. `--refresh` forces a re-pull.

**Result (DuckDB tables, stamped `pulled_at`):**

| table | rows | season span |
|---|---|---|
| player_ids | 12,465 | (crosswalk, no season) |
| weekly | 59,829 | 2014–2024 |
| seasonal | 6,682 | 2014–2024 |
| snaps | 300,812 | 2014–2025 |
| ngs | 26,723 | 2016–2025 |
| draft_picks | 3,077 | 2014–2025 |
| combine | 4,080 | 2014–2025 |
| pbp | 580,005 | 2014–2025 |

**Done-criterion — PASS:** weekly↔snaps `gsis_id` join (REG, skill positions) = **0.243% unmatched**
(135 / 55,517 player-weeks), under the <1% gate. weekly grain clean: **0** duplicate `(gsis_id,season,week)`
groups, **0** null `gsis_id`. Per-season weekly counts stable (~5.3k–5.7k).

**What it taught / notes:**
- **2025 coverage is asymmetric**: nflverse already has 2025 **PBP/snaps/draft/combine**, but the
  aggregated **weekly/seasonal** player tables stop at **2024** (clean 404, auto-skipped by the per-year
  guard). → usable *fantasy-points* history is **2014–2024 (11 seasons)**; the small-`n` constraint stands.
- The `gsis_id` join key is solid for weekly/seasonal/ngs (native) and snaps (mapped via `player_ids.pfr_id`).
  The 135 unmatched snaps are fringe players missing a `pfr_id` in the crosswalk — logged, not dropped.
- **pytest console-script doesn't spawn under `uv run`** in this env; use `uv run python -m pytest`.

**Next:** 0.3 — Pro-Football-Reference season panels (cross-check + extra features).



## 0.3 — PFR advanced season panels (2026-06-30)

**Goal:** add the advanced PFR metrics nflverse's base tables lack, + cross-check identity.

**Source decision (documented):** pulled PFR's advanced season tables via
`nfl_data_py.import_seasonal_pfr` (the **nflverse PFR mirror**) instead of scraping
pro-football-reference.com directly — same PFR data, but reproducible/cached and respectful of
PFR's bot-protection. The raw httpx+bs4 scraping stack is held for 0.4 ADP (genuinely needs it).

**What was built:** `data/cache.py` (shared raw-pull caching, reused by 0.3+), `data/sources/pfr.py`
(`ingest_pfr_seasonal`, `map_pfr_ids`, `match_rate`, `reconcile`), `steps/phase0_3_pfr.py`,
`tests/test_pfr_ingest.py`, and committed `reference/pfr_id_overrides.csv` (+ `reference/README.md`).

**Result (3 tables, gsis-mapped, `pulled_at`-stamped):**

| table | rows | span | features added |
|---|---|---|---|
| pfr_pass | 848 | 2018–2025 | pressures/blitzes/hurries, on-target%, play-action, RPO, scrambles |
| pfr_rec | 4,130 | 2018–2025 | YBC, YAC, ADOT, broken tackles, drops, drop% |
| pfr_rush | 2,820 | 2018–2025 | YBC, YAC/att, broken tackles |

**Done-criterion — PASS:** PFR yards vs nflverse `seasonal` (matched, REG, >50 yds):
rec **median abs % diff = 0.000%** (2,381 player-seasons), rush **0.000%** (1,114). Exact agreement
confirms the `pfr_id→gsis_id` mapping is correct. gsis match: pass 100%, rush 99.7%, rec 98.2%.

**What it taught / notes:**
- **PFR advanced stats start in 2018** ("Data not available before 2018"). So these features are
  usable **2018–2024** (vs 2014 for nflverse base). Models needing pre-2018 history fall back to base.
- The 85 unmatched `pfr_id`s are mostly **offensive linemen** (Dawkins, Decker, Fant) who appear in
  PFR tables but aren't skill players — logged to `data/raw/pfr/unmatched_pfr_ids.csv`, not dropped.
  Genuine skill-player misses can be hand-fixed in `reference/pfr_id_overrides.csv`.

**Next:** 0.4 — ADP ingest (FFCalculator + Underdog), PIT snapshots.



## 0.4 — ADP ingest (FFCalculator, PIT snapshots) (2026-06-30)

**Goal:** the "market price" — historical ADP, snapshotted PIT, mapped to `gsis_id`.

**What was built:** `data/sources/adp.py` (`ingest_adp`, `normalize_name`, `match_adp_to_gsis`,
`adp_asof`, `coverage`, `match_rate`), `steps/phase0_4_adp.py`, `tests/test_adp_ingest.py`,
committed `reference/adp_name_overrides.csv`.

**Source:** Fantasy Football Calculator public JSON API. Pulled the full grid
**scoring ∈ {standard, ppr, half-ppr} × teams ∈ {10, 12} × 2010–2024**, throttled 0.5s, cached to
`data/raw/adp/`. FFC's `meta.end_date` (late Aug / early Sep) is the PIT `snapshot_date`.

**Result:** `adp_snapshots` = **14,144 rows**, coverage **2010–2024 (15 seasons)**.
- ppr/standard: all 15 seasons; **half-ppr only 2018+** (7 seasons — FFC didn't track it earlier).

**Done-criterion — PASS:**
- Coverage ≥ 2015→present ✓ (2010–2024).
- `adp_asof(2020, as_of)` PIT: **0 rows** the day *before* the snapshot (no leak), full 203-player
  board the day *after*; asserts internally that no returned row is future-dated.
- gsis matching after overrides: **top-150 ADP 0.000% unmatched**, all-skill 0.02%.

**Identity work (the crux):** FFC has no `gsis_id`, only a name. `match_adp_to_gsis` is a 4-tier
matcher: (1) team+pos+normalized-name, (2) pos+name with **draft-year disambiguation** for same-name
players across eras (e.g. the two Mike Williamses), (3) name-only, (4) manual nickname overrides.
Pre-overrides left 8 players unmatched — all nickname/short-form (Hollywood→Marquise Brown, Gabe→
Gabriel Davis, Chig→Chigoziem Okonkwo, Ben/Benjamin Watson, …); added to
`reference/adp_name_overrides.csv` → top-150 went to 100%. Remaining 2 unmatched are FFC's
"Deleted Deleted" placeholder (correctly left null).

**Underdog best-ball — DEFERRED (data gap, open question resolved):** Underdog's public endpoints
require auth (404/301 unauthenticated); no free *historical* best-ball ADP. The schema is
format-aware (`source`/`format` columns; FFC = `redraft`) so best-ball slots in later without a
migration. Logged in `PLAN.md`.

**Notes / reserved words:** `rows` is a DuckDB reserved keyword (quote aliases); DuckDB `.df()`
returns DATE columns as pandas Timestamps (compare with `pd.Timestamp`, not `datetime.date`).

**Next:** 0.5 — Vegas markets ingest (props / totals / spreads / win totals, de-vig).



## 0.5 — Vegas markets ingest (de-vig'd) (2026-06-30)

**Goal:** the *sharper* market — spreads/totals/props as features, anchors, calibration.

**What was built:** `markets/` package + `markets/odds_ingest.py` (`ingest_game_lines`,
`ingest_player_props`, `parse_props_payload`, `devig`, `american_to_prob`, `decimal_to_prob`,
`fair_two_way`, `implied_team_total`, `odds_asof`, `implied_total_sanity`), `steps/phase0_5_markets.py`,
`tests/test_markets.py`.

**The free/paid split (confirmed):**
- **FREE + historical (landed):** game **spreads, totals, moneylines, spread/over odds** via
  nflverse `import_schedules` → table **`game_lines`** (3,295 games, **2014–2025**), with derived
  **implied team totals** and de-vig'd fair win probs.
- **PAID/gated (built, key-gated):** **player props** via the-odds-api are **live-only**; historical
  prop lines are the paid gap. `ingest_player_props` no-ops with a warning unless `ODDS_API_KEY` is set
  (it isn't) — but `parse_props_payload` + `devig` are unit-tested so the path is ready for a key.
- **Win totals DEFERRED:** nflverse `import_win_totals` returns empty ("source in flux"); `import_sc_lines`
  also empty. Revisit later.

**Done-criteria — ALL PASS:**
- De-vig'd two-way market sums to 1.0: `max|home_wp + away_wp − 1| = 2.2e-16` (machine epsilon).
- Implied team totals sane: **median 22.8**, range 9.8–36.2, **100% in [10,40]**.
- `odds_asof` PIT: 0 rows the day before the first 2020 game, 269 after the season — asserts no
  future-dated line escapes.
- Spot-check 2023 wk1 KC/DET (home −4, total 53): KC **28.5** / DET **24.5**, win probs **0.637/0.363**.

**Notes:**
- **Sign convention** (verified): nflverse `spread_line` = **home** margin (positive ⇒ home favored);
  `implied_team_total = ((total+spread)/2, (total−spread)/2)`.
- These are **closing lines** (one per game, dated gameday) — no intra-week line-movement history from
  this source. `captured_at = gameday`.
- De-vig is **proportional** (Shin/power noted as alternatives for later).

**Next:** 0.6 — News / injury / depth-chart raw ingest (lay the Phase-12 NLP pipe).



## 0.6 — News / injury / depth-chart raw ingest (2026-07-01)

**Goal:** lay the *pipe* for the Phase-12 NLP edge — capture timestamped raw signal now (no NLP yet).

**What was built:** `news/` package + `news/ingest.py` (`ingest_injuries`, `ingest_depth_charts`,
`ingest_news_text`, `parse_rss`, `injuries_asof`), `steps/phase0_6_news.py`, `tests/test_news_ingest.py`.

**Result (3 tables, timestamped):**

| table | rows | span / grain | timestamp | source |
|---|---|---|---|---|
| injuries | 65,866 | 2014–2025 | **`date_modified`** (PIT) | nflverse `import_injuries` (native gsis) |
| depth_charts | 955,989 | 2014–2024 | (season, week) | nflverse `import_depth_charts` (native gsis) |
| news_raw | 109 | forward-only | `captured_at` | RSS: ESPN 23 / CBS 36 / Yahoo 50 |

**Done-criterion — PASS:** injuries reconstructable as-of a day. `injuries_asof(2023-10-25)` returns
1,782 reports filed ≤ that date (latest 2023-10-21) and correctly **excludes 3,817 later reports**;
asserts no returned report is future-dated. injuries carry **0% null gsis_id**.

**What it taught / notes:**
- **injuries + depth_charts are free & historical** with native `gsis_id` — no name-matching needed.
  injuries `report_status` ∈ {Out, Questionable, Doubtful, null=no-report}.
- **`news_raw` is forward-capture only** — news can't be backfilled, so the archive starts now and
  **accumulates**: `ingest_news_text` appends + de-dupes by `guid` (earliest `captured_at` wins).
  Re-run periodically (a scheduled job later) to build history. No `gsis_id` yet (entity resolution
  is Phase 12).
- **Inactives (90-min list) deferred** — no clean free historical importer; derivable later from
  snaps==0 or forward-captured.

**Next:** 0.7 — PIT panel / feature-store assembly (the unified join layer).



## 0.7 — PIT panel / feature-store assembly (2026-07-01)

**Goal:** the unified point-in-time join layer everything downstream reads from.

**What was built:** `data/panel.py` (`build_panel`, `weekly_panel`, `preseason_panel`,
`assert_panel_pit`), `steps/phase0_7_panel.py`, `tests/test_panel.py`. Materializes to
`data/processed/panel_{grain}_{season}_{as_of}.parquet`.

**The PIT contract (the crux):** a source contributes a row only if its *known-at* time ≤ `as_of`:
- weekly stats / snaps / NGS → known at that week's **last gameday** (from `game_lines`);
- ADP → its `snapshot_date`; injuries → `date_modified`; game context → kickoff.
`assert_panel_pit` runs on every build and **raises** if any dated field exceeds `as_of`.

**Two grains:**
- `weekly_panel(season, as_of)` — `(gsis_id, season, week)`; weekly stats + snaps + receiving-NGS +
  odds/implied-team-total + ADP + injury-status, restricted to weeks finished ≤ as_of. **41 columns.**
- `preseason_panel(season, as_of)` — the draftable ADP board as-of + identity/age + injury-as-of.

**Done-criteria — ALL PASS:**
- **Two as-of dates differ:** 2023 as-of Oct-15 = 1,549 rows (weeks 1–5); as-of Dec-10 = 3,825 rows
  (weeks 1–13). Later strictly includes more.
- **No field after as_of:** real panels assert clean on build; a **planted future value is caught**.
- **gsis lines up:** Justin Jefferson 2023 wk5 on one row — pts_ppr 5.8, tgt 6, snap% 0.71,
  team_implied 24.5, ADP 1.4, NGS separation 3.40 (all six sources joined; the low pts is real — he
  left wk5 injured).
- **Preseason board** (2023 as-of Sep-4): 190 players, correct top-5 (Jefferson/CMC/Chase/Hill/Ekeler),
  ages computed, **Ja'Marr Chase flagged Questionable** (his real preseason status).

**What it taught / notes:**
- **FFC season-aggregate ADP is dated ~Sep 1** (end of the preseason draft window). A draft as-of
  *before* that (e.g. Aug 30) correctly yields an **empty board** — PIT working as intended; use a
  Labor-Day-weekend (≥ snapshot_date) as-of for draft panels.
- `game_lines.gameday` is stored VARCHAR → `CAST(... AS DATE)` when computing week-end dates.
- NGS join is receiving-only for now (marquee metrics); full multi-type NGS pivot lands in Phase 3.

**Next:** 0.8 — Data validation & sanity gates (the hard-gate analog).



## 0.8 — Data validation & sanity gates (2026-07-01) — **PHASE 0 COMPLETE**

**Goal:** the hard-gate analog — bad data fails loudly here instead of poisoning a model later.

**What was built:** `data/validate.py` (`validate_panel` — hard gates that raise; `data_health_report`
— store-wide report), `steps/phase0_8_validate.py`, `tests/test_validate.py`, and the committed
`analysis/results/data_health.json`.

**Gates (all PASS):** value ranges (no negative counting stats; offense_pct∈[0,1.01]; total_line∈[20,80];
implied totals∈[0,45]); uniqueness (weekly `(gsis,season,week,type)`; game_lines `game_id`; adp
`(gsis,season,source,scoring,teams)`); join rates (weekly↔snaps 0.24%, ADP top-150 0.08%). Panel
hard-gate validated 5,391 rows (2022 weekly).

**The gate earned its keep — it caught a real 0.4 bug:** the adp-uniqueness gate flagged **14 groups**
where one `gsis_id` mapped to two ADP rows in a snapshot. Root cause: **homonyms** — two different
"Mike Williams" (WR) and two "Steve Smith" (WR) in the 2010–11 boards both resolved to the same gsis
(draft-year proximity favored the same candidate for both). **Fix (in 0.4):** `dedupe_gsis_within_snapshot`
enforces a gsis maps to ≤1 row per snapshot — keep the lower-ADP (more prominent) row, NULL + log the
loser. Re-ran ingest → gate clean. (This is exactly the intern `_validate_cov_hard_gate` philosophy paying off.)

**Survivorship documented** in the report: for 2022, **0** top-150 *skill* ADP players had no weekly
appearance (the earlier "busts" were **kickers** — structurally absent from the offensive `weekly` table,
so the check now filters to QB/RB/WR/TE). 77 weekly gsis aren't in `player_ids` (minor fringe-player gap).
Note preserved: weekly panels contain only players who recorded stats — join drafted-but-DNP from ADP to
avoid survivorship-flattered backtests.

---

### ✅ PHASE 0 — DATA FOUNDATION: COMPLETE (2026-07-01)
**16 DuckDB tables**, all PIT-stamped, covering nflverse (2014–24), PFR-advanced (2018–24), FFC ADP
(2010–24), Vegas game lines (2014–25), injuries (2014–25), depth charts (2014–24), and a forward-capture
news pipe. A **PIT panel layer** (`build_panel`) joins them leak-free in two grains, and a **hard-gate
validator** with a committed `data_health.json` guards the lot. 26 unit tests; every step's done-criteria
met. This is the "60% of the edge" groundwork — done slowly and correctly.

**Next:** Phase 1 — the backtest harness (built *before* any modeling): scoring engine, draft simulator,
walk-forward harness, PAR metric, block-bootstrap significance.



## 1.1 — League scoring engine (2026-07-03) — **PHASE 1 STARTED**

**Goal:** turn raw stats into fantasy points under a configurable ruleset — the first brick of the
backtest harness, built *before* any modeling (the intern `min_variance_backtest` discipline).

**League config settled (user decision, 2026-07-03):** 10-team full-PPR, 1-QB, **full 9-starter
lineup `QB / 2·RB / 2·WR / TE / FLEX + K + DST`** (15 roster spots). Choosing K + DST pulled
kicker & team-defense scoring into 1.1 — they aren't in the offensive `weekly` table.

**What was built:** `backtest/scoring.py` — pydantic `RuleSet` (`OffenseRules`/`KickingRules`/
`DstRules`); **pure, unit-tested scorers** `score_offense`, `kick_play_points`, `pa_tier_points`,
`score_dst`; thin DB wrappers `weekly_points`, `season_points`, `kicker_weekly_points`,
`dst_weekly_points`; identity resolvers `resolve_kicker_gsis`, `dst_team_from_adp_name`.
Plus `steps/phase1_1_scoring.py` and `tests/test_scoring.py` (8 tests).

**Done-criteria — ALL PASS:**
- **Offense (hard gate):** reconstructed full-PPR == nflverse `fantasy_points_ppr` across
  **57,301 player-weeks (2014–2024)**, worst `|diff| = 2.9e-6` (float32 epsilon), **0** rows over a
  0.02 tolerance. Default `OffenseRules` reproduce nflverse exactly (pass 0.04 / TD 4, INT −2, rush/rec
  0.1 / TD 6, reception +1 PPR, ST-TD 6, 2pt +2, fumble-lost −2).
- **Kickers (pbp-derived):** FG by distance (0–39=3 / 40–49=4 / 50+=5) + PAT from `pbp` FG/XP plays,
  keyed on `kicker_player_id` (gsis). 2022 leaders Tucker 164 / Carlson 162 / Maher 161 — matches real
  fantasy-K leaderboards; weekly range 0–23.
- **DST (pbp + PA-derived):** sacks / INT / fumble-rec / def+return-TD (`td_team = defteam`) / safety +
  points-allowed tiers from `game_lines` final scores. 2022 leaders NE 177 / DAL 164 / SF 156 / PHI 149
  — the actual top 2022 fantasy defenses; weekly range −4…26.
- **Identity (K/DST bridge):** FFC ADP K/DST rows carry **null gsis** (`_NON_GSIS_POS`), so
  `resolve_kicker_gsis` (name→gsis via `player_ids`, PK/K) and `dst_team_from_adp_name`
  ("Philadelphia Defense"→PHI, relocations handled) connect them to a scoreable key. 2022 draftable
  board: **kickers 5/5, defenses 6/6** resolved.

**What it taught / notes:**
- nflverse's fantasy formula is **exactly reproducible** from `weekly` components — no external
  reference table needed; the offense scorer *is* its own validation.
- **K/DST live entirely in `pbp`/`game_lines`, not `weekly`** → their own derivation + identity bridge.
  `td_team == defteam` cleanly captures defensive *and* kick/punt-return TDs (verified on 2022 plays).
  DST points-allowed uses the opponent's **final** score. Blocked-kick DST points are **not** derived
  (documented approximation; `DstRules.block` defined but unused).
- Kept the arithmetic in pure functions (DB-free) so it unit-tests without network/DB — mirrors the
  0.7 `assert_panel_pit` pattern.

**Next:** 1.2 — draft simulator (ADP-following opponents) — **pending user approval (sub-phase gate).**



## 1.2 — Draft simulator (2026-07-03)

**Goal:** simulate a full snake draft vs ADP-following opponents — the second brick of the harness,
and the `DraftState` that becomes the input to every later draft policy (Phases 9/11).

**What was built:** `draft/simulator.py` — `RosterSlots` (frozen dataclass: 9-starter slots + bench
+ per-position **caps**), `DraftState` (snake geometry, availability, roster counts/needs, pick log),
`simulate_draft(board, your_pick_fn, n_teams=10, rounds=15, noise, seed)`, pick policies
`pick_by_adp` (opponents) + `adp_pick_fn` (default your-seat), `canon_pos`, `_prepare_board`.
Plus `steps/phase1_2_draft.py` and `tests/test_draft.py` (9 tests).

**Done-criteria — ALL PASS (board = `adp_asof(2022, Sep-5)`, 157 players, seed 42, your seat 4):**
- **10×15 = 150 picks**, snake order verified (R1 seats 0–9, R2 seats 9–0, R3 0–9).
- **ADP-typical roster:** your pure-ADP roster = RB6/WR5/TE2/QB2 (15, within caps, RB/WR-heavy) —
  reads like a real ADP draft (J.Taylor R1 … depth WR/TE late).
- **Reproducible:** same seed → identical pick log; different seed → different.

**What it taught / notes:**
- **Board source = `adp_asof`, not `preseason_panel`** — the panel filters `gsis_id IS NOT NULL`,
  which drops the 6 team defenses (null gsis); `adp_asof` keeps them. Kickers *are* gsis-matched in
  `adp_snapshots`; only DST is null-gsis → `player_key` falls back to the name.
- **Caps are SOFT:** they steer opponents off over-drafting a position *while an under-cap
  alternative exists*, but when supply is exhausted a team takes best-available anyway (never a short
  roster). Tested both ways (ample-supply caps hold; RB/WR-only board forces a documented overflow).
- **FFC undersupplies K/DST** — its aggregate board lists only ~5 K / ~6 DST, so only ~3–5 of 10 teams
  draft each. The harness will treat empty K/DST slots as replacement-level (realistic streaming);
  worth revisiting if K/DST edge matters.
- **Custom `your_pick_fn`s are not cap-bound** (caps are only the opponent-realism knob) — real
  policies self-limit via `state.starter_needs()`. Perf: roster counts computed once per pick
  (an earlier per-available-player version was O(n²), ~54s → ~2s).

**Next:** 1.3 — walk-forward harness (rank_fn → drafts → realized season, strict PIT) — **pending user
approval (sub-phase gate).**



## 1.3 — Walk-forward harness (2026-07-03)

**Goal:** the engine — *ranking method → simulated drafts → realized season outcomes*, across seasons,
strictly PIT. Ties 1.1 (scoring) + 1.2 (draft sim) together; everything in Phases 2–15 plugs in here.

**What was built:** `backtest/walkforward.py` — `rank_by_adp` baseline + the `rank_fn(board, con,
season, as_of)` contract; pure `optimal_lineup_points` (greedy = optimal for a single FLEX);
`build_realized`/`Realized` (offense+K by gsis, DST by team — per-season weekly-point pivots);
`roster_season_points` (survivorship-safe); `draft_date`, `preseason_board` (PIT-asserted), and
`walk_forward(...) -> WalkForwardResult` (per-draft / per-season / pooled). Small simulator additions:
`DraftState.draftable_pool`, `value_pick_fn`, a `value` column through `_prepare_board`. Plus
`steps/phase1_3_walkforward.py` and `tests/test_walkforward.py` (8 tests).

**Done-criteria — ALL PASS (2014–2024, 6 drafts/season, rotating seats):**
- **One-call end-to-end:** ADP baseline scores every season PIT-clean — pooled **2036 ± 195** starter-pts
  (per-season 1856–2327). `rank_fn` is fed the PIT board; opponents draft ADP+noise; rosters scored on
  the season's **actual** weekly results via optimal lineups.
- **Swapping `rank_fn` = one arg, and the harness discriminates:** a deliberately-bad worst-ADP-first
  `rank_fn` pools at **1458** — **577 pts below** ADP. The engine can tell a good method from a bad one.
- **Reproducible:** same seed → identical `per_draft`.
- **PIT guard:** a planted future-dated ADP snapshot trips `assert_panel_pit` (intern Step 5.1 analog).

**What it taught / notes:**
- **rank_fn contract:** returns a draft-priority per board row on the **ADP/pick scale** (lower = sooner),
  NaN → falls back to that player's ADP; `value_pick_fn` drives your seat off it. Baseline returns `adp`,
  so "you drafting by ADP" ≈ league-average (edge vs ADP is measured in 1.5, not here).
- **Survivorship guard is structural:** rosters are scored by LEFT-JOIN of drafted players → realized
  weekly points, so a drafted bust who never played contributes **0** (proven: adding a never-played
  player doesn't change a roster's total). The `weekly` table only holds players who recorded stats.
- **Draft date = the FFC ADP snapshot** per season (PIT as-of); `preseason_board` re-asserts no future
  snapshot leaks. Season score = sum of optimal-lineup points over all REG weeks (fantasy-regular /
  playoff weighting is a 1.4/2.x refinement).
- Perf ~0.27s/draft (66-draft baseline ~18s); driver runs baseline+swap+repro+PIT in ~48s.

**Next:** 1.4 — PAR metric scorer (replacement levels + points-above-replacement) — **pending user
approval (sub-phase gate).**



## 1.4 — PAR metric scorer (2026-07-03)

**Goal:** the harness's headline number — points-above-replacement of a drafted roster — and the
per-position replacement levels it needs (the standing PLAN.md open question, resolved here).

**What was built:** `backtest/metrics.py` — `replacement_ranks` (last-starter rank per position with
FLEX split), `replacement_levels`/`ReplacementLevels` (season-point level per position + a replacement
roster total), `par(roster, realized, replacement, slots)`, and secondary metrics `expected_wins`
(all-play win% × weeks — schedule-independent) + `final_standings`. Refactored `walkforward.py` to
expose `roster_weekly_points`. Plus `steps/phase1_4_metrics.py` and `tests/test_metrics.py` (7 tests).

**Replacement-level definition (resolved):** the "last reliably-started player" per slot in a 10-team
9-starter league. Dedicated starters league-wide = `n_teams × slot`; the single FLEX is split across
RB/WR/TE ∝ dedicated demand (2:2:1). → ranks **QB10 / RB24 / WR24 / TE12 / K10 / DST10**; each level =
that rank's realized season points; FLEX level = best flex-eligible replacement. Adjustable via
`slots`/`n_teams`. **2023 levels:** QB 274 · RB 191 · WR 219 · TE 143 · K 149 · DST 139 → replacement
roster **1743 pts**.

**Done-criteria — ALL PASS:**
- **PAR ranks good above bad:** an elite-starter roster scored **+818 PAR** (2561 pts) vs a ~40th-ranked
  scrub roster at **−943 PAR** (800 pts) — a 1761-pt gap; good > 0 > bad.
- **Replacement levels documented** (above) + committed in code.
- **Secondary metrics align:** across a real 2023 draft, PAR ↔ expected-wins correlate **0.99** and the
  top-PAR team finishes 1st (all-play standings). Expected wins = all-play (each week, fraction of the
  league you outscore), so a boom/bust roster can rank slightly differently from raw PAR — as intended.

**What it taught / notes:**
- Replacement is computed from **realized** season totals — fine because PAR is an *evaluation* metric
  on realized outcomes (not a PIT projection input). PAR of the 1.3 rosters ≈ starter_points − 1743.
- Full schedule/playoff simulation is Phase 10; `expected_wins` (all-play) is the cheap, unbiased proxy
  here — no schedule luck. `final_standings` ranks by it.

**Next:** 1.5 — significance (block-bootstrap CIs, method − ADP/market) — **pending user approval
(sub-phase gate).**



## 1.5 — Significance (block-bootstrap CIs) (2026-07-03)

**Goal:** don't declare a winner on noise — put a confidence interval on the method − ADP edge.

**What was built:** `backtest/significance.py` — `block_bootstrap_ci` (stationary bootstrap, expected
block ≈ n^{1/3}; `expected_block=1` degrades to iid) → point/CI/SE/`significant`; `compare_to_baseline`
(paired walk-forward method vs baseline → per-season PAR-difference series → 95% CI). Plus
`steps/phase1_5_significance.py` and `tests/test_significance.py` (7 tests).

**Done-criteria — ALL PASS:**
- **Recovers known results:** iid bootstrap SE ≈ σ/√n; the CI brackets the observed statistic.
- **Block, not iid:** on AR(1) φ=0.85, block SE **0.239** ≫ iid SE **0.090** — autocorrelation is respected.
- **Real comparison:** ADP vs ADP → edge **0**, not significant (no false positive); worst-first vs ADP →
  edge **−577.6 PAR/season**, 95% CI **[−714, −438]**, SIGNIFICANT (every season negative). Matches the
  1.3 pooled gap (2036 − 1458 = 578).

**What it taught / notes:**
- **Paired design** (same seeds → matched opponents/seats) isolates the method; the season's replacement
  level cancels in the difference, so a PAR difference = a starter-points difference.
- The **market baseline** plugs in as any `baseline` rank_fn once Phase 2.3 (props-implied) exists — the
  "beat ADP **and** the market" gate becomes one `compare_to_baseline` call each.
- Block bootstrap on *iid* data slightly lowers SE with longer blocks (harmless small-sample artifact);
  the property that matters — wider SE under autocorrelation — holds.

---

### ✅ PHASE 1 — BACKTEST HARNESS: COMPLETE (2026-07-03)
Five focused modules (AlphaThena "one file per aspect"): **`scoring`** (full-PPR incl. K/DST from
pbp/game_lines — reconstructs nflverse to 1e-6 over 57.3k player-weeks), **`draft/simulator`**
(ADP+noise snake draft, pluggable `your_pick_fn`, `DraftState`), **`walkforward`** (rank_fn → K drafts →
realized optimal-lineup points, strict PIT, survivorship-safe), **`metrics`** (PAR + replacement levels +
all-play wins), **`significance`** (block-bootstrap CIs). **Any ranking method is now scored end-to-end
on 2014–2024 drafts, PIT-clean, with 95% CIs vs the ADP baseline, in one `compare_to_baseline` call** —
the measuring stick built *before* any modeling. **65 unit tests**; every step's done-criteria met.

**Next:** Phase 2 — markets & baselines (VBD · naive opportunity×efficiency · **props-implied** ·
**ensemble-with-market**): the cheap, strong baselines everything fancy must beat, plugged straight into
this harness as `rank_fn`s.



## Phase 2 — Markets & baselines (2026-07-04)

The first methods scored through the Phase-1 harness. Architecture: a **projection** → **VBD** → a
harness **`rank_fn`** (`vbd_rank_fn` in `valuation/vbd.py`), so any projection backtests with a one-line
wrap. Board rows a projection doesn't cover fall back to ADP (via `value_pick_fn`'s NaN handling).

### 2.1 — VBD baseline → `valuation/vbd.py`
- **Built:** `vbd(proj, replacement)` (= proj points − positional replacement, reusing 1.4's
  `replacement_levels`), `vbd_rank_fn(projection_fn)`, `board_key`, `replacement_baseline`.
- **Done — PASS:** VBD is monotonic in points within a position; the cross-position top board is a sane
  RB/WR/QB/TE mix. **Note:** naive VBD ranks elite QBs very high (Hurts/Allen top-5) — the classic 1-QB
  artifact (the market prices QB streaming; the 2.4 ensemble corrects it).

### 2.2 — Naive baseline projection → `projections/baseline.py`
- **Built:** `baseline_projection(con, season, as_of)` — prior-season (S-1) points-per-game, empirical-
  Bayes shrunk to the positional mean (weight = weeks/(weeks+6)), ×17 games, light age penalty. Offense
  + K, keyed by gsis. PIT (only S-1 + as-of ages). Rookies/no-history → NaN → ADP fallback (a last-year
  model can't forecast rookies; pretending would flatter it).
- **Done — PASS (board + harness backtest; beating ADP not required):** covers 170/202 of the 2023
  board. **Backtest 2014–24: pooled 1977 vs ADP 2036 → edge −59 PAR/season, 95% CI [−162, +33], NOT
  significant.** Honest finding: the naive last-year VBD board is **statistically on par with ADP**
  (slightly below), dragged by QB over-drafting. (2014 diff is exactly 0 — no 2013 data → projection
  empty → equals ADP.)

### 2.3 — Props-implied projection → `markets/props_projection.py`
- **Built + unit-tested:** `props_projection(props, ruleset)` maps de-vig'd **season** prop expectations
  (rec/rush/pass yds, receptions, TDs, INTs) → fantasy points; `season_props_projection`, `props_available`.
- **THE DATA GAP (confirmed, documented):** there is **no free historical preseason market signal.**
  Player props are the-odds-api **live-only** (key-gated, no key); `import_win_totals` is **empty**; and
  `game_lines` are **gameday-dated closing lines** (earliest 2023 line = Sep 7, after Labor-Day drafts) —
  so zero pre-draft signal. `season_props_projection` therefore **no-ops to an empty frame → ADP fallback**,
  and 2.3 **cannot be backtested as a preseason board on free data.** The math is built + tested so
  `vbd_rank_fn(season_props_projection)` activates the moment a props source (a key or a paid historical
  archive) is wired in — no code change. This is the confirmed "pay only if it becomes a product" line.

### 2.4 — Ensemble-with-market → `projections/ensemble.py`
- **Built:** `blend_rank_fn(components, weights)` (weighted blend of rank_fns, each NaN→ADP first),
  `ensemble_rank_fn(w_baseline)` (baseline-VBD blended with ADP; props slot in as a 3rd component when
  available), `fit_weight` (grid-search w through the harness).
- **Done — PASS (ensemble ≥ best single component):** grid-fit finds an **interior optimum at w=0.25**
  (25% baseline / 75% ADP): pooled **2116 > pure ADP 2041 > pure baseline 1985**. The blend pulls the
  baseline's aggressive QB ranks back toward the market. Fitted ensemble vs ADP: edge **+80 PAR/season,
  95% CI [−22, +190], not significant** — so it **matches ADP** (leans positive). Caveat: w was picked
  **in-sample** on 11 seasons, so +80 is optimistic (a nested CV is Phase 4's job); the CI honestly spans 0.

### ✅ PHASE 2 — MARKETS & BASELINES: COMPLETE (2026-07-04)
The baselines-to-beat are set and wired into the harness: **VBD** (value transform), the **naive
projection** (on par with ADP, −59 CI[−162,+33]), the **props-implied** path (built, unit-tested, blocked
by the documented free-data gap), and the **ensemble** (a little model + mostly market ≥ either alone
in-sample; matches ADP OOS). **Headline lesson — "don't fight the sharp market":** consensus ADP is a
strong, hard-to-beat baseline; the naive model adds no *significant* edge yet. Real signal must come from
Phases 3–5 (opportunity/efficiency features, GBT/hierarchical projections, distributions). 74 unit tests.

**Next:** Phase 3 — feature engineering (the PIT exposure matrix `X`): opportunity, efficiency,
player-intrinsic, and team/environment factors — the inputs the real projection models consume.



## ⟳ Strategic Reframe — direct indexing for fantasy (2026-07-04)

**Decision (not a finding from code):** the project's **objective and definition of done are replaced**.
From *"beat consensus ADP and prove it with bootstrap CIs"* → *"build a **personalization engine** that
gives the user the team they want and honestly **prices what that costs** vs the consensus-optimal team."*
Team strength becomes a **tracked benchmark**, personalization the objective. Full doc:
`docs/REFRAME-2026-07-04.md`; design contract: `docs/PERSONALIZATION.md`. **Phases 0–2 stay valid; no code
changed.** Docs updated: STRATEGY (Part 0), PROJECT, ROADMAP, BUILD_PLAN, CLAUDE, PLAN, glossary.

**Why (this project's own numbers made the case):** "beat ADP on a ~10-season walk-forward" is very likely
**unachievable even for a good model**. Our 2.2 finding was −59 PAR/season, 95% CI [−162, +33] → SE ≈ 50
PAR/season; detecting an 80-PAR edge (~4% over the ~2036 ADP base — a *large* edge) at 80% power needs
≈ **27 seasons**; we have ≈ 10. The best in-sample blend (+80 PAR) still had a CI crossing zero. So we
**stop fighting an unwinnable inferential battle** and pivot to problems checkable **within a single
draft** (calibration, availability, cost) — the same reason AlphaThena's business works without alpha.

**The three signal layers (now a hard architectural contract):** "based around ADP" is split into
**value** = consensus projections → VBD (*not* ADP order; ADP is draft-order, not points), **availability**
= ADP + a behavioral opponent model, **variance** = our own distributional layer. The optimizer maximizes
**consensus-VBD value** s.t. constraints, plans around **ADP availability**, uses **variance** for the risk
dial. Big simplification: we lean on consensus for the mean and **drop the "build a better projection"
burden** (Phase 4 reframed to consensus-VBD + a rookie model).

**Seven methodological cautions carried forward as constraints:**
1. **Lockbox** — PIT ≠ out-of-sample; freeze recent season(s), evaluate the final stack once (guards
   in-sample selection over ~10 seasons). Recorded in `CLAUDE.md` §4.
2. **Calibration > edge** — a miscalibrated projection is now a *visibly wrong number the user sees*, so
   calibration rigor matters *more* (reliability diagrams, interval coverage).
3. **Mean vs tail** — season PAR is a mean metric, championship prob a tail metric; both must exist (a
   user-facing risk toggle). Note: the harness's perfect-hindsight optimal-lineup scoring rewards
   high-variance bench players — don't let it confound the distributional work.
4. **Rookies must not punt to ADP** — build an explicit rookie model (draft capital / landing spot /
   athletic-college); rookie RB/WR is a rich mispricing and a user who loves a rookie needs an honest number.
5. **FFC ADP is soft money** — best-ball ADP (Underdog) is the sharper reference; matters for the benchmark
   and for availability prediction.
6. **Benchmark is self-referential** — "optimal" is our own model's; offer cost vs **multiple** benchmarks.
7. **Cost-number uncertainty** — lead with **relative/directional** cost (robust); stay humble on absolute
   championship-equity deltas.

**Scope guardrails:** all in-app **AI/LLM deferred** post-MVP (AI on the edges, deterministic core);
**Streamlit/Gradio MVP** first (not FastAPI+Next.js); **CFR dropped** (snake draft ≈ perfect-info), **MCTS
deprioritized**; **own the contracts** (the `DraftConfig` object + projection output shape).

**Open decisions (tracked in `PLAN.md`):** consensus-projections source (free/PIT?); Sleeper completed-draft
data for the behavioral model; the benchmark set; the lockbox seasons; the paid-props go/no-go.

**Next (reframed MVP path):** the personalization spine on Phases 0–2 — Phase 3 `X` → consensus ingest +
VBD + rookie model → a trimmed per-player distribution → the constraint object + constrained greedy
optimizer + a first cost report → a Streamlit UI. See `docs/PERSONALIZATION.md` §7.



## Phase 3 — Feature engineering: the PIT exposure matrix `X` (2026-07-05)

**Goal:** the standardized, point-in-time exposure matrix — the engine's output that Phases 4–7 consume
(rookie model, distributions, ADP-softness, opportunity-adjusted). Built straight through 3.1→3.5.

**Architecture (the contract that sets up future phases):** each factor module produces **realized
per-(gsis, season) facts** (lag-free, testable); **`build_exposures(con, target)` applies the PIT lag**:
production ← target-1, intrinsic ← as-of target, environment ← target-1 of the player's **target-season
team** (the situation they're *entering* — right for movers *and* rookies). Then winsorized
cross-sectional **z per position**, explicit missingness flags, `assert_exposures_pit`.

- **3.1 opportunity** (`features/opportunity.py`) — target/carry/snap/air-yards share, WOPR, aDOT, RZ
  volume. 6,688 rows. Elite WRs/RBs top the board (Hill/Adams tgt-share 0.33; Jacobs carry-share 0.77).
- **3.2 efficiency** (`features/efficiency.py`) — catch rate, YPR/YPC/YPT, YAC, **TD-regression flag**
  (actual − RZ-opportunity-expected TDs), QB EPA/CPOE. **Done-check: corr(TD-over-expected, next-year
  TD/gm change) = −0.50** on DEV seasons (the flag captures mean reversion). *Deep check caught a real
  bug:* trick-play throwers (Drake London/Derrick Henry) polluted QB EPA → fixed with a ≥100-dropback
  gate; now Purdy/Tua/Dak top 2023 EPA correctly.
- **3.3 player-intrinsic** (`features/player.py`) — age **as-of Sep-1** (JJ: 21.2 as a 2020 rookie, +1/yr),
  experience, draft capital (UDFA sentinels), combine athletic profile. College deferred. Handles bogus
  draft_year=0 (→ first-season), missing birthdates (0.1% fringe → NaN, imputed in 3.5).
- **3.4 environment** (`features/environment.py`) — team pass rate, early-down pass rate (PROE proxy),
  pace, points, pass/rush EPA, **Vegas implied team total**, target HHI. 32 teams/season;
  **corr(implied total, realized pts) = +0.86**; 2023 top offenses SF/DAL/MIA/KC/BUF. *Fixed* relocated-
  franchise code mismatch (STL/SD/OAK↔LA/LAC/LV) + season-median safety fill.
- **3.5 exposure matrix** (`features/exposures.py`) — `build_exposures` → **545 players × 48 features**
  (43 z + `is_rookie`/`is_undrafted`/`changed_team`/`no_prior`/`age_missing`/`athletic_missing`).
  `FEATURE_MANIFEST` documents the columns.

**Readiness checks for future phases — ALL PASS:** finite + unique + z mean-centered per position; PIT
(seasons differ; guard rejects non-lagged); **89 rookies flagged with live intrinsic signal** (rookie
model ready); **X covers 100% of the top-150 draftable ADP board** (optimizer/6 ready); **lagged WOPR_z
↔ next-season points corr = +0.46** pooled over 3,920 DEV player-seasons (Phase 4/5 have real signal);
2025 calibration-holdout matrix builds (610 players, finite). All modules run on `STATS_SEASONS`
(features are computation, not model selection — the lockbox binds *selection*, done in 4/5).

**Notes:** rate outliers from tiny samples (aDOT/YPC on 1–2 touches) are **clipped** to physical bands so
they don't distort z-scoring. Universe = skill players active in the target season (mild survivorship,
documented — the model universe standard). 15 new unit tests; ruff clean. **Phase 3 COMPLETE.**

**Next:** Phase 4 (reframed) — **consensus-projections ingest → VBD value** + a **rookie model** (uses X's
intrinsic signal) + calibration. Needs a consensus-projections source decision first (`PLAN.md`).



## Lockbox set + 2025-data diagnosis (2026-07-04)

**Decision — lockbox = 2023 + 2024** (frozen; dev on **2014–2022**). Encoded in `config.py`
(`FANTASY_SEASONS` 2014–24, `LOCKBOX_SEASONS` = (2023, 2024), `DEV_SEASONS` = 2014–22) and `CLAUDE.md` §4.
Set **before** Phase 3 selects any features (reframe caution #1). All development / feature+model selection
runs on `DEV_SEASONS`; the final chosen stack is evaluated on the lockbox **exactly once**.

**Why not 2025 (diagnosed on request):** the 2025 season **is fully played** in the raw store — `game_lines`
has all 285 games with final scores (2025-09-04 → 2026-02-08) and `pbp` has REG wk 1–18 + POST 19–22
(48.8k plays). But **four derived tables lack 2025**, so it can't be a fantasy/draft season yet:
- `weekly` + `seasonal`: **404 upstream** — live-tested `import_weekly_data([2025])` → HTTP 404. nflverse
  publishes raw pbp first; the **aggregated player-stats rollup for 2025 isn't out yet**. Our Jun-30 cache
  froze that 404 (per-year skip-on-fail); `--refresh` re-pull is needed once it lands.
- `adp_snapshots`: no 2025 FFC ADP board pulled (needed as the preseason draft board).
- `depth_charts`: nflverse stops at 2024.
A draft-backtest season needs **both** a preseason ADP board (to draft from) **and** realized weekly points
(to score) — 2025 has neither. **Recovery (deferred, logged in `PLAN.md`):** periodic `--refresh` re-pull,
or reconstruct 2025 weekly from `pbp` ourselves (bigger job; still needs an ADP board).



## 2025 recovery — ROOT CAUSE FOUND + plan (2026-07-04, corrects the entry above)

The above "the 2025 rollup isn't out yet" was **wrong**. Root cause (user hint confirmed): **nflverse
restructured its stats releases after the 2024 season.** `nfl_data_py` is frozen and hardcodes the *old*
path `…/releases/download/player_stats/player_stats_{yr}.parquet` — which has **no 2025 file** → the clean
404. The stats moved to a **new release** (`stats_player`) with new filenames, and **2025 is present there.**
Verified live by querying the nflverse-data GitHub release assets + downloading the files:

| Need | New nflverse file (`releases/download/stats_player/…`) | Verified |
|---|---|---|
| **weekly 2025** | `stats_player_week_2025.parquet` | ✅ 19,421 rows, wk 1–20 (incl. POST), `fantasy_points_ppr` + all counting stats (JJ wk1 4-44 → 14.8 PPR) |
| **seasonal 2025** | `stats_player_reg_2025.parquet` | ✅ 2,020 rows, `fantasy_points_ppr`, `games` |
| history (bonus) | `stats_player_week_1999…2025` (27 files) | ✅ the new release also covers all prior years |

**Schema:** new file is compatible + richer (115 cols). "Missing" cols are just **renames**:
`player_id`→`gsis_id` (our ingest already does this), `passing_interceptions`→`interceptions`,
`team`→`recent_team`; `sacks`→`sacks_suffered` (not used in scoring). Has `season_type` (REG/POST),
2pt, fumbles-lost, targets, air-yards share, plus full defensive stats.

**Two remaining 2025 caveats:**
- **`depth_charts` 2025 changed format** (user note, per the nflverse GitHub): from 2025 on, depth charts
  are **not week-assigned** — each update is appended with an **ISO8601 timestamp** (assign to a point in
  the season yourself). The 2025 file *is* available now (`import_depth_charts([2025])` → 554k rows); the
  ingest must handle timestamped (not weekly) grain.
- **ADP 2025 is genuinely absent from FFC** (re-probed across scoring/teams): FFC serves 2024 and **2026**
  (the current board, dated today) but returns **0 players for 2025**. A historical preseason board
  after-the-fact is the hard part → source later from **Sleeper** (wanted anyway for the opponent model),
  Underdog, or FantasyPros.

**The plan (folded into ROADMAP/BUILD_PLAN as step 0.9):**
1. Add a **new-release ingest path** to `data/sources/nflverse.py` (read the `stats_player` URLs; map the
   ~3 renamed cols) → append **weekly + seasonal 2025**; also migrate the source off frozen `nfl_data_py`
   for these products (future-proofing). Handle the **timestamped depth_charts** grain.
2. Re-run the **0.8 validator** on the extended store.
3. **Lockbox stays 2023 + 2024** for the *draft-backtest* (needs an ADP board). Recovered **2025 becomes a
   projection-calibration holdout** (realized outcomes exist; no board needed to check calibration — and
   calibration is the reframe's core bar). It **upgrades to a full draft-backtest season** once a 2025 ADP
   source lands (Sleeper).
4. Sequencing: **do 0.9 before Phase 3** so the feature matrix `X` can include 2025 (features come from
   pbp/snaps/ngs, all already 2025-present, but a consistent weekly/seasonal join is cleaner with 0.9 done).

**0.9 DONE (2026-07-05):** `data/sources/nflverse.py` gained `conform_stats_player` (pure; rename +
reindex to legacy schema), `backfill_stats_new_release` (append weekly/seasonal from the new
`stats_player` release, idempotent), `ingest_depth_charts_ts` (timestamped grain → `depth_charts_ts`);
`db.append_df` (INSERT … BY NAME). `steps/phase0_9_backfill_2025.py` + `tests/test_backfill_2025.py`
(3 tests). **Results:** weekly **59,829 → 79,250** (2025 REG 18,539 + POST 882), seasonal → 8,702; **2025
reconstructs `fantasy_points_ppr` to 2.4e-6** (proves the new-release schema is scoring-compatible);
`depth_charts_ts` = 554,215 rows (`dt` 2025-08-03 → 2026-03-14, 2,985 players); **0.8 validator PASS** on
the extended store. `config` gained `STATS_SEASONS` (2014–25) + `CALIBRATION_SEASONS` (2025); `FANTASY_SEASONS`/
`DEV_SEASONS`/`LOCKBOX_SEASONS` unchanged (2025 stays out of the draft-backtest — no ADP board). 77 tests, ruff clean.


## Phase 4 — Mean VALUE: consensus-VBD + rookie model + calibration (2026-07-05)

**Reframe recap:** Phase 4 is no longer "build a better projection." Value = **consensus projections →
VBD**; the bar is **calibration, not beating ADP** (our Phase-2 backtest already proved that fight is
unwinnable on ~10 seasons). Built 4.1→4.4 straight through (gate waived for the phase, per user).

**Decision locked (with the user):** the consensus source is a **two-track / free** design — because free
*current-season* consensus is scrapeable but free *historical/PIT* consensus does not exist:
- **Live track** — scrape the free **FantasyPros** projection pages, re-score their projected component
  stats to **full-PPR via our own `RuleSet`** (so consensus points are identical in scale to the rest of
  the repo, not FantasyPros' scoring), gsis-match, PIT-stamp.
- **Historical track** — the **Phase-2 baseline is the consensus proxy** for 2014–24 (and 2025). The
  optimizer machinery is identical; only the mean's provenance differs, and the live board is what a real
  user actually drafts on. Honest, and unblocks everything for free.

### 4.1 — consensus ingest → `projections/consensus.py`
- `consensus_projection(con, season, as_of)` dispatches: a scraped board for `season` in the store → PIT
  read; else → baseline proxy. Same `[player_key, pos, proj_points]` shape both ways → drops into `vbd_rank_fn`.
- **Gotcha (caught by the numbers):** FantasyPros sometimes serves a **truncated ~10-row shell** on a cold
  CDN hit (RB/K came back with 10 rows while WR/TE were full, and the bad pull got cached). Fix: `_pull_fp`
  **retries below a per-position row floor** and keeps the largest table, so a partial page is never cached.
  A coverage assertion (RB≥40, WR≥50) guards the step. K reliably serves only its top ~10 without JS —
  fine for a 10-team draft.
- **Results (2026 live board):** **528 players, 99% gsis-matched** (3 unmatched = 2026 rookies not yet in
  the `player_ids` crosswalk — expected; draft data lands late). Our full-PPR reconstruction ↔ FantasyPros'
  own FPTS: **corr 1.000, MAD ~1 pt** (the tiny gap = 2-pt/return-TDs we don't reconstruct). PIT verified
  (board dated today invisible to an earlier as-of).

### 4.2 — VBD value board → `valuation/value_board.py`  **(the frozen contract)**
- **Key correctness point:** VBD replacement must come from **projected** points at the replacement rank
  (QB10/RB24/…), **not** `metrics.replacement_levels` (which reads *realized* season points — nonexistent
  for the season being drafted). First cut used realized → replacement 0 → `vbd == proj_points` → QBs not
  demoted (a silent bug the numbers exposed). `projection_replacement()` fixes it.
- Frozen **contract**: `player_key · pos · proj_points · source · vbd · pos_rank · overall_rank`
  (`source` ∈ consensus/proxy/rookie). This is what Phase 5 wraps. 0-point projections (listed bodies with
  no forecast) dropped.
- **Sanity that matters:** QBs in the top-15 go **6 (by raw points) → 0 (by VBD)** in 1-QB — VBD correctly
  moves scarcity to RB/WR; the board leads RB/WR/RB/WR… with the top TE at overall #10 (looks like a real
  VBD board).

### 4.3 — rookie model → `projections/rookie.py`
- Rookies are the one place the mean goes blind (no prior production). Model = **per-position ridge**
  (closed-form numpy, dependency-free — respects small-n / no-deep-nets) on **`log(draft_ovr)` + landing-spot
  env** (implied team total, target competition, pass rate), fit **walk-forward** on strictly-prior seasons.
- **Gotcha:** 2014's landing-spot env needs 2013, which predates the store → all-NaN env poisoned the pooled
  fit (all-NaN weights → all-NaN predictions). Fix: league-typical env fallbacks + drop residual-NaN training
  rows. Root-cause found by tracing NaN back through the fit, not by loosening asserts.
- **Results:** OOS **Spearman(pred, realized rookie pts) = +0.62** (453 rookies, 5 DEV seasons); the
  dominant signal is draft capital (**corr(draft_ovr, realized) = −0.59** pooled, 728 rookies — earlier
  picks score more). Top-projected 2021 rookies = Lawrence/Chase/Waddle/Najee — the high-capital names.
  Integration: fills **+76 rookies** into the 2021 proxy board (642 → 718), so the historical board stops
  being blind to rookies. (QB busts like Zach Wilson rank high — the model uses ex-ante draft capital,
  correctly; that's a *variance* story for Phase 5, not a mean error.)

### 4.4 — calibration → `projections/calibration.py`  **(the real done-criterion)**
- Measures the value mean vs realized: per-position **bias ratio** (Σreal/Σpred), monotone **reliability
  table**, per-position **correction factor** (= the bias itself; `corrected = pred·bias` pulls Σreal/Σcorr
  → 1). Two universes: **conditional** (played) and **unconditional** (projected-but-DNP = 0, the honest
  survivorship-safe draft-day view). K/DST excluded (scored via separate pbp paths, not `season_points` —
  a bug the first run surfaced as K bias 0.01).
- **Finding — the projection is optimistic and it's mostly games-played attrition, not rank error:** proxy
  bias **0.60** (conditional) / **0.46** (incl. DNP as 0) — the ~40% gap is dominated by players not
  playing a full 17 (partial seasons, injuries, washouts), *not* by mis-ranking: **reliability climbs
  monotonically** (bin-corr **0.99**, mean realized 35→218 across deciles) and **Spearman +0.52**. So the
  fix is a **scale correction**, not a new model — per-position factors pull 2022 bias to **0.96**.
- **Holdout (read once):** the **2025** calibration season gives **bias 0.58, Spearman +0.57** — nearly
  identical to DEV, so the miscalibration is *stable* and the correction generalizes to an unseen season.
  This is "calibration > edge" operationalized: we didn't try to beat ADP; we made the number honest.

**Phase 4 net:** the personalization spine now has a real, calibrated **value layer** — a live consensus
board a user can draft on today (2026), a frozen VBD contract for the optimizer + Phase 5 to build on, a
validated rookie fill, and a documented+corrected calibration with a clean 2025-holdout check. 102 tests,
ruff clean. **Next: Phase 5 distributions (full 5.1–5.5), wrapping the 4.2 contract → the risk dial.**

## Phase 5 — Distributional projections: the per-player risk dial (2026-07-05)

**Reframe recap:** distributions are **the one value-side thing we build ourselves** (consensus/ADP are
point estimates) and they **power the per-round risk dial** — no risk feature without them. Phase 5 turns
the 4.2 calibrated mean into a **full season distribution F(points) per player**, assembled from four
factors and frozen into a contract the optimizer (Phase 9) and copula/roster layer (Phase 8) consume.
**Grain decision: season-total only** — that is exactly what the draft dial + optimizer consume; a
weekly-grain distribution (start/sit, in-season) is deferred to the season simulator (Phase 10) and noted
as future work. User chose the **full 5.1–5.5 stack** run straight-through (sub-phase gate waived).

**Method deviations from BUILD_PLAN (accepted with the user 2026-07-05; no new deps):** 5.1 uses a
**statsmodels linear `QuantReg`**, not XGBoost quantile loss; 5.4 uses a **scikit-learn logistic
discrete-time hazard**, not `lifelines`. Both are the right call for ~a-few-hundred player-seasons/position
(the no-deep-models, no-overfit rule) and avoid a heavy dependency. **Future intent (documented, not
scheduled):** revisit **XGBoost quantile regression** (5.1) and a **`lifelines` survival model** (5.4) once
the sample or the residual signal justifies the extra flexibility. See BUILD_PLAN Phase 5 notes.

**5.1 — quantile regression (`projections/quantile.py`).** Per-position linear `QuantReg` of realized
season points on the **calibrated mean** (the 4.2 board × the 4.4 per-position correction), one line per
τ ∈ {.1,.25,.5,.75,.9}, fit walk-forward on the **conditional (available) DEV cohort** (weeks ≥ 0.85·season
→ the *if-healthy* distribution; injury attrition is a separate factor, 5.4, so it isn't double-counted).
1,074 player-seasons. **Median-line slope ≈ 1.10** (τ.50 recovers the mean); the outer τ lines **fan out
with level** (heteroscedastic spread — a 300-pt projection is wider than a 60-pt one) for **3/4 positions**
(QB fans through the intercept, not the slope — slopes QB 0.83, RB 1.10, WR 1.19, TE 1.29). Quantile
crossing repaired by sorting the fitted quantiles.

**5.2 — conformalized quantile regression (`projections/conformal.py`).** CQR (Romano 2019): conformity
score `E = max(q_lo−y, y−q_hi)`, per-position adjustment `d = ⌈(1−α)(n+1)⌉/n` empirical quantile of E,
band → `[q_lo−d, q_hi+d]`, α=0.2 (80% target). Fit `d` on held-out DEV seasons **[2021, 2022]**:
**QB +18, WR +3, RB +2, TE +0** pts (QB intervals were the most too-tight). **2025 holdout (read once):
coverage 70% → 73%** on the available cohort (n=176) — conformal moves it toward the 80% target without
worsening it (per-pos QB 94 / WR 73 / RB 71 / TE 64%).

**5.3 — boom/bust weekly variance (`projections/variance.py`).** From realized weekly points: per-player
weekly mean/sd/**CoV**, **boom rate** (share of weeks clearing a position "great game" line) and **bust
rate**. Confirmed fantasy weekly scoring is **right-skewed** (the boom tail): skew **TE +1.60, RB/WR +1.27,
QB +0.23**. Key finding: **`corr(boom_prob, CoV) = −0.37`** — boom rate tracks scoring *level* (elite
players clear the line often *and* steadily), so it's a **separate axis** from volatility, not the same
knob. Carried through the contract as a consistency signal (a different, complementary axis from the
season-total spread).

**5.4 — availability: discrete-time hazard → games-played distribution (`projections/injury.py`).** The 4.4
calibration found the mean's biggest *level* miss is **games-played attrition**, not mis-ranking. We model
it as the **other factor**: a logistic **discrete-time availability hazard** on the person-period grid
(31,623 player-weeks, base availability 70.6%) with age / position / prior-season-availability / week; then
games-played ~ **Beta-Binomial** over team games with method-of-moments over-dispersion **ρ = 0.33** so the
distribution keeps the fat *lost-season* tail (a torn ACL zeroes the year — a plain Binomial would miss it).
Coefficients are actuarially sane: **prior-avail +0.42** (durability persists), **age −0.10**, **week −0.18**,
**RB −0.16 (least available), WR −0.10, TE −0.11** vs the QB reference — matching the known RB-highest injury
rate. Universe = established contributors (prior games ≥ 8); rookies/backups fall to a median-availability
fallback in the assembler. Documented limitation: the grid conditions on ≥1 appearance, so a pre-Week-1
whole-season miss is under-counted (the 4.4 unconditional haircut partly covers it).

**Assembler + 5.5 utility (`projections/distribution.py`, `valuation/utility.py`).** The four factors compose
into a **Monte-Carlo sample cloud per player** (2000 draws): `Y = H · (avail_fraction / G_ref)`, H drawn from
the conformal-widened conditional quantiles (its own asymmetry *is* the boom skew — no separate injection),
availability from 5.4, normalized by the cohort's mean availability fraction (~0.93) so a typical draw returns
≈ H (injury downside lives entirely in the multiplier, never double-counted inside H). **Frozen contract:**
`player_key·pos·mean·sd·q10·q50·q90·boom_prob·bust_prob·games_played_mean·ce_value`. The **mean-variance
certainty equivalent** `CE(λ)=E[Y]−λ·Var[Y]` is the risk dial (λ=0 risk-neutral; larger λ docks volatility);
`risk_premium=λ·Var` is the honest per-player cost of uncertainty, and it slots straight into the Phase-8
covariance work (Var → portfolio tracking-error variance, same λ). 2025 board = **673 players**; per-position
mean season points QB 187 / RB 110 / WR 109 / TE 82 (top QB ~279) — sane. λ dial verified: it docks the most
volatile player far more than the steadiest as risk aversion rises. Persisted to **`player_distributions`**
(673 rows, season 2025; gitignored store).

**Two real bugs found wiring the phase together (2025/early-season paths that 5.1–5.4 never exercised — they
ran only on seasons ≥ 2016):**
- **`value_board` crashed on an empty projection season.** The assembler trains on *all* DEV seasons < target
  (2014–2022); **2014 has zero consensus/proxy rows** (the proxy baseline can't forecast the first season, no
  prior). An empty `mean` frame made `vbd()` do `float64 − empty-arrow-string` (pandas 3.0's `.map` over an
  empty arrow-string series returns an empty *large_string* — nothing to infer float from) → `ArrowNotImplemented`.
  **Fix:** `value_board` now returns an empty contract-shaped frame when there's no projection (guarded before
  the VBD arithmetic). A latent Phase-4 robustness bug, surfaced by Phase 5.
- **Season means were ~17× too high (units mismatch).** `sample_player_season` computed `Y = H · (G / G_ref)`
  with **G a games *count* (0–17)** but **G_ref a *fraction* (~0.93)**, so `G/G_ref ≈ 17`. A WR read **4524**
  season points. **Fix:** convert the sampled games to a fraction first — `Y = H · ((G/team_games) / G_ref)` —
  so a typical-availability draw returns ≈ H. Guarded by a regression test (`test_sample_player_season_is_on_the_H_scale`).

**Calibration read + the honest limitation.** Two coverage numbers on the 2025 holdout: **conditional
(available cohort, weeks ≥ 0.85·season, n=176): 76%** — near the 80% target, median |q50−realized| = 47 pts;
this is the population the interval is calibrated for (consistent with 5.2). **Unconditional (full 673-player
board, realized 0 for anyone who never played): 44%** — dragged down by **122/673 projected bodies who never
earned a snap**. That gap is **role/depth attrition**, which the injury-only availability model (5.4)
deliberately does **not** capture (it models games-missed for players *with* a role, not "never earned one").
This is a **documented Phase-5 limitation**, not a coverage the distribution promises → **future work: a
role/depth survival haircut beyond injury** (e.g. a depth-chart/opportunity-driven "makes the roster / holds
the role" probability layered under the availability multiplier).

**Phase 5 net:** the risk dial exists end-to-end — a calibrated per-player season distribution wrapping the
4.2 value contract, with an explicit λ that prices each player's uncertainty in points, ready for the Phase-8
covariance and the constrained optimizer. **18 new unit tests (120 total), ruff clean; all five step scripts
green; `player_distributions` persisted.** **Next: the personalization spine — `DraftConfig` constraint object
+ constrained greedy optimizer + first cost report → Streamlit MVP** (Phase 8 covariance can slot in via the
same λ/Var).

---

## Personalization spine (S1–S3 + S5) — the direct-indexing MVP (2026-07-07)

Built the reframe's MVP spine on top of Phases 0–5, straight-through (sub-phase gate waived by the user, per
the 4→5 cadence). **On DEV 2022** (latest non-lockbox season with an ADP board + realized outcomes); **season
is a parameter**, so a scraped 2026 board drops in unchanged. New modules: `draft/config.py` (the contract),
`draft/optimizer.py`, `valuation/cost_report.py`, `app/streamlit_app.py`; three `steps/spine_*` scripts; 17
unit tests in `test_spine.py`. **137 tests total, ruff clean; all spine step scripts green; the Streamlit app
verified headlessly via `AppTest`.** `streamlit` added as a `ui` extra.

- **S1 — `DraftConfig` (the contract we own).** The MVP subset of `PERSONALIZATION.md` §3: league context,
  one archetype (a master positional dial), hard `never_draft` + `must_draft` (with a per-player **reach
  budget** in rounds), soft per-player `tilts`, and `risk_lambda`. Normalized + validated on construction
  (contradictory must∩never, unknown archetype, out-of-range seat/λ all raise). `benchmark()` strips every
  preference (same seat & λ) → the value-optimal peer; `without_constraint(label)` / `constraint_labels()`
  drive the cost report's leave-one-out. **Left out on purpose** (half-used schema > honest scope): fandom
  excludes, correlation appetite, control tiers, benchmark sets — added when needed.
- **S2 — constrained greedy optimizer.** Reuses the Phase-1.2 simulator via a pluggable `your_pick_fn`; no new
  draft engine. **Value signal `base_value` = risk-adjusted value-over-replacement**: the Phase-5 certainty
  equivalent (mean − λ·Var) minus its own positional replacement level, so cross-position priority is on the
  VBD scale *and* carries the λ dial; players with no distribution fall back to plain Phase-4 VBD, DST to ADP.
  Priority scale = the harness's own `(-value).rank()` (lower = sooner). **Tilts** convert rounds→priority as
  `eff = base_rank − n_teams · tilt_rounds`. **must-draft** is a pure **availability-planning** rule (no value
  tilt): take a must-player only at the last responsible moment — when he's within the reach budget *and*
  unlikely to survive to your next pick (ADP ≤ next-pick + noise margin, from the snake geometry) — so value
  is never wasted reaching. The benchmark runs the identical machinery (only the config differs), so the cost
  is a **pure preference cost**.
- **S3 — cost-of-personalization report.** Personalized vs `benchmark()` drafted over the **same seeds** (same
  opponents, same value index), differenced into one headline (points + % of benchmark), then attributed per
  preference by **leave-one-out** (drop one constraint, redraft, the value it recovers = its cost). Also
  reports each must-player's **secured fraction** across drafts (reach-budget honesty). Relative/directional
  per §7 — a projected draft-day gap; a **walk-forward realized-PAR validation is the next layer**.
- **S5 — risk dial.** Already built (Phase 5 `utility.risk_adjusted_board`); here it's *wired in* — λ flows
  through CE into `base_value`, so the whole optimizer/report respond to the dial. The UI exposes it as a
  slider. Phase-8 covariance will replace per-player `Var` with portfolio `Var` under the same λ.
- **S1 UI (S4 of the "signature seven" is deferred).** Streamlit **Autopilot** (archetype + seat) **+
  Co-pilot** (λ slider, must/never/reach/wait lists) with defaulted controls and one-line "why"; always shows
  the personalized roster **beside the pure-value baseline** + the cost readout (guardrail §8). Deterministic,
  **no LLM**. Value-index assembly (~8 s) is `@st.cache_data`-keyed on (season, λ); a report is ~3–4 s.

**Bug caught (design):** the first archetypes were **stateless** `(pos, round)` tilts, so `elite_te` ("get a
top TE early") kept firing every round ≤ 4 and drafted **two** elite TEs (Kyle Pitts *and* Dalton Schultz),
cratering a test roster's value and inflating the cost to a bogus ~53 %. **Fix:** made the "grab one anchor"
archetypes **roster-state-aware** — the tilt now takes `have` (count already at the position), supplied by the
pick policy from `roster_counts`, so `elite_te`/`hero_rb`/`late_qb` stop reaching once you hold your anchor.
Regression-guarded (`test_get_one_archetypes_stop_after_the_first`, `test_elite_te_takes_one_te_early_not_two`).
*(Not a bug — flagged for honesty:* a must-draft can carry a **negative** `base_value` (e.g. A.J. Brown off an
injury-shortened 2021 → pessimistic 2022 proxy projection); insisting on him is then genuinely costly, and the
report says so. The value signal is only as good as the projection feeding it.)*

**Spine net:** you can sit down for a 2022 draft from any seat, express preferences (archetype + must/never/
tilts + risk λ), and get a personalized board **and an honest, relative cost** vs the value-optimal team —
from a Streamlit UI, no LLM in the loop. **Next:** Phase 8 covariance (portfolio `Var` under the same λ) ·
S4 behavioral opponent model · a walk-forward realized-PAR validation of the cost · scrape 2026 ADP to go live.

## Spine step 4 — realized-PAR validation of the cost number (2026-07-08)
The cost report prices personalization in **projected** `base_value`; step 4 (`valuation/cost_validation.py`,
`steps/spine_4_validate.py`) asks whether that projected cost shows up in **realized** points. Each archetype
is drafted vs its `bpa` benchmark over **matched seeded opponents**, both scored on realized optimal-lineup
season points (survivorship-safe); because both share the season's replacement level, their starter-point
difference **is** the PAR difference. Per-season realized-cost series → stationary block-bootstrap 95% CI +
a projected↔realized cross-check. Runs on **`VALIDATION_SEASONS` = 2017–2022** (a season is only scored once
it has ≥ 3 prior DEV seasons — the conformal minimum; earlier seasons still train, but their board isn't
trustworthy). Availability is **not** validated (a real draft-day Brier needs pick-by-pick logs the FFC
aggregates lack — deferred to a Sleeper scrape).

**Result (6 seasons, 60 drafts each):** projected archetype costs are all **tiny** (within ±13 `base_value`
pts of the benchmark — soft tilts barely move projected value). Realized costs are **noise-dominated**: only
**late_qb** is distinguishable from 0 — a **realized GAIN of ~59 pts/season** (CI [−95, −25]), i.e. waiting on
QB in a 1-QB league historically *added* real points (textbook late-round-QB, now measured on our own data).
zero_rb / hero_rb / elite_te all straddle 0. The **projected→realized cross-check is ~nil** (Spearman ρ =
−0.04, sign agreement 33 % over 24 subject-seasons). **Reading:** on ~6 seasons the projected draft-day cost
does **not** predict realized-season point differences — it's a *draft-day decision aid*, not a season
forecast, exactly the §7 humility. (Single-archetype late_qb is not multiple-testing corrected — suggestive,
directionally very plausible.)

*Re-run 2026-07-09 under the Phase-8 covariance-aware optimizer (same seeds):* conclusions unchanged —
**late_qb** still a REAL GAIN (−65.5 pts/season, CI [−97, −34]); **elite_te** now nominally a small gain
(−16.7, CI [−31.1, −1.3] — barely excludes 0 and is not multiple-testing corrected; read as suggestive);
zero_rb / hero_rb straddle 0; projected↔realized still ≈ nil (ρ = −0.06). The projected cost remains a
draft-day aid, not a season forecast.

## Phase 6 — ADP-bias mining: where the market is soft (2026-07-08)
Reframed goal: not "beat the draft market" but *find where ADP is systematically soft, so we know how cheaply
a preference can be indulged.* **6.1** (`adp/panel.py`) builds a **1,504-row** panel of drafted offensive
players over **9 DEV seasons**; target = **value-over-replacement alpha** = realized VOR − **leave-one-season-
out isotonic** ADP-implied VOR (monotone in ADP pos-rank, never fit on the season it scores → no outcome
leaks into a player's own baseline; per-position mean alpha ≈ 0, |max| = 1.2, and the famous breakouts —
McCaffrey '19 +241, Kamara '17, Kupp '21 — top the list). **6.2** (`adp/regression.py`) regresses alpha on
PIT traits (rookie, experience, ADP dispersion, prior-season durability & efficiency; position dummies as
controls) with **season-block-bootstrap** CIs (respecting the ~9-season effective sample, not 1,504 correlated
rows). **6.3** (`adp/scorecard.py`) applies **Benjamini-Hochberg FDR** + a **walk-forward sign-stability** floor
(≥ 60 %).

**Result:** R² = **0.017** (ADP already prices almost everything — the honest baseline). After both guards,
**exactly one stable bias survives: prior-season games played (durability) is UNDER-priced** (+14.6 VOR per SD,
95 % CI [+11.4, +21.0], p_fdr = 0.001, **100 % sign-stable across 8 seasons**). Reframe reading: indulging a
preference toward **last-year-durable** players is essentially **free** — the crowd systematically
under-drafts availability. Prior-season **efficiency** (pts/game) is *over*-priced (−11.8) but **ruled out**
(p_fdr = 0.06, only 62 % stable) — the recency/efficiency-chasing bias is suggestive, not bankable. Rookie,
experience, and ADP-disagreement are honestly ruled out. This satisfies the Phase-6 done-criterion ("stable,
significant biases with CIs, or honestly ruled out"). **Scope:** analysis only — how this softness signal
would price a preference cheaper in the cost report is a documented follow-on, not wired in yet.

## Phase 8 — Covariance & rosters: the portfolio layer + covariance-aware picks (2026-07-09)
The most direct internship reuse: a roster is a portfolio, `Var(team) = 1ᵀΣ1`. With 17-week seasons a raw
500×500 sample covariance is hopeless (n ≪ k), so `covariance/estimate.py` (**8.1**) imposes structure —
`Σ = D^½·R·D^½` with **D** from the Phase-5 season sds (no re-estimation) and **R** a **relationship-typed
correlation** pooled across every same-team pair of each kind (QB1-WR1, RB1-RB2, …; ~250–700 pairs per type
vs 17 weeks per pair; cross-team = 0; estimated on both-active weeks so availability dependence is never
double-counted). Every Σ passes the **hard gate** (finite/symmetric/PSD) behind a diagonal-preserving
Higham-style repair. **8.2** (`covariance/shrinkage.py`) shrinks each pooled estimate toward a documented
structural prior with EB weight `n/(n+κ)` — the Ledoit-Wolf philosophy adapted to typed blocks (literal LW
needs the raw high-dim matrix our sample can't produce; documented deviation).

**Correlation findings (DEV ≤ 2022):** the folk stack numbers are REAL — QB1-WR1 = **+0.37** empirical
(prior +0.40; 287 pairs), QB1-TE1 +0.28, QB1-WR2 +0.27. But **RB1-RB2 both-active is only −0.05** (folk
−0.30): the backfield's negative dependence lives in **availability**, not performance — precisely why the
copula (below) carries it separately. **OOS done-bar:** walk-forward QB1+WR1 stack-variance prediction —
shrunk ρ **halves** the error vs assuming independence (MAE 21.7 vs 45.8, 217 pairs; only ρ differs by
construction). Board Σ (142 players, 2022): gate PASS, condition number 9.1.

**8.3** (`covariance/copula.py`, targeted scope per 2026-07-09 decision): the handcuff payoff is *tail*
dependence — backup booms exactly when starter busts — expressed as a **90°-rotated Clayton** fit by pooled
Kendall τ on **zero-filled** RB1/RB2 weeks (absence *is* the event). On 288 real DEV backfields: τ = −0.14 →
θ = 0.34, λ_L = 0.13; P(backup top-quartile | starter bottom-quartile) = **0.393 empirical vs 0.391 Clayton
vs 0.346 Gaussian** (independence 0.25) — the Clayton nails the tail the Gaussian misses. **8.4**
(`valuation/roster_risk.py`): roster Σ → portfolio mean/sd/floor/ceiling (Gaussian team-total approx,
documented) + **Iman–Conover** to impose R on the Phase-5 sample clouds without touching any marginal;
done-bar holds on the real 2022 board (stack sd 155 vs 131 independent; hedge floor higher). **8.5**
(`valuation/handcuff.py`): backup priced as a contingent claim — pooled elevation ratio **1.77** (backup 5.8
ppg with starter → 10.3 without, 506 real starter-out weeks); option premium moves correctly with starter
fragility (+19.5 pts at 30 % out vs +3.9 at 6 %).

**9.1 pulled forward (user decision 2026-07-09): the greedy is covariance-aware.** Each pick now maximizes
the *marginal portfolio CE*: `base_value_j − 2λ·σ_j·Σ_{i∈roster, same team} ρ_ij σ_i`, mapped through the
static value→rank curve so ADP-fallback (K/DST) timing and all must/never/tilt mechanics are untouched, and
λ=0 reproduces the old greedy exactly (regression-tested). Live on the 2022 board: rostering the top QB
pushes his WR1 **102 picks down** at λ=0.01 while other-team players are untouched. The cost report's
yardstick upgrades to **portfolio CE** = Σ base_value − 2λ·Σ cross-cov, and it now renders a **risk profile**
(portfolio sd vs independent sd, floor/ceiling, named stacks/hedges). **Honest observation:** the value-greedy
already diversifies across NFL teams naturally, so both λ settings usually draft ≈ zero same-team covariance —
the penalty is a *guard-rail that binds when preferences push toward a stack*, not a rebalancer. Spine
re-validated post-change: spine-3 checks PASS; spine-4 realized-PAR sweep re-run (see updated numbers there).
16 new pure tests (`tests/test_phase8.py`); suite green; ruff clean.

## Phase 6 → cost report: the market-softness credit is wired in (2026-07-09)
The one FDR-stable Phase-6 bias — **durability under-pricing** (+14.6 realized VOR per SD of prior-year
games, 100 % sign-stable) — now prices personalization in the report (`adp/softness.py`; user decision
2026-07-09: **credit + net line, the raw headline is never silently moved**). Mechanics: the signal is
**frozen with provenance** (`DURABILITY`: coef +14.5856, CI [+11.36, +20.98], μ=10.57, σ=6.37 — the DEV
panel's own moments, so exposure × coef is unit-honest); each roster's **exposure** = Σ z(prior-year games)
over its offensive players (rookies at raw 0, exactly the panel convention), PIT via the season−1 feature
builder; **credit = (your exposure − benchmark's, averaged over the same paired drafts as the headline) ×
coef**, carried with the coefficient's CI; **net effective cost = raw − credit**, explicitly labeled a
*historical-bias estimate, not a projection*. `steps/phase6_adp_bias.py` doubles as the **drift check**
(recomputes the scorecard, asserts the frozen numbers within 5 %). Live read on 2022 (zero_rb + prefs,
seat 5): the personalized roster carries **+0.3 SD** more durability than its benchmark → **+4.4 pts**
credit [CI +3.4, +6.3]; raw −5.2 → net −9.6. Small for soft archetypes, by construction — the line exists
so a *durability-leaning* preference is visibly cheaper than the raw number claims (and a fragile-leaning
one visibly dearer). 6 new pure tests (`tests/test_softness.py`); spine-3 gates extended (net ≡ raw − credit,
headline string unchanged).

## Stage 0 — the 2026 snapshot series is live + the Sleeper probe (2026-07-09)
THE PIPELINE's only time-sensitive item, done first: **FFC 2026 ADP is now being banked** as a PIT snapshot
*series* (`data/sources/adp.py::snapshot_adp` + `steps/stage0_adp_snapshot.py`). First pull 2026-07-09:
**1,028 rows across the full grid** (standard/ppr/half-ppr × 10/12 teams; the ppr-10 board = 201 players),
gsis match **99.3 %** on skill rows — the 2026 rookie class is already in nflverse rosters, so no
name-match debt — and the `adp_asof` PIT guard passes (day-before-first-snapshot = empty). Design choices
that matter: each pull caches a **date-keyed raw parquet** and the ingest **replays the whole cache,
appending only missing `(season, config, snapshot_date)` keys** — idempotent per day and self-healing if a
0.4 rebuild ever recreates `adp_snapshots` (a rebuild only restores the one-per-season historical
snapshots). `snapshot_date` joins the homonym-dedupe and pos_rank keys (a series has many snapshots per
season — the 0.4 code assumed one). Scheduling reality: a Claude Code cron is **session-only**, so the
durable mechanism is layered — in-session weekly job + a **standing chore in CLAUDE.md §2** (any session:
if the latest 2026 snapshot is > 6 days old, run the script) + a Windows Task Scheduler one-liner as the
zero-dependency fallback. 4 pure tests (`tests/test_stage0.py`).

**Sleeper probe (read-only, public endpoints — `steps/stage0_sleeper_probe.py` →
`analysis/results/sleeper_probe.json`): the stage-3 identity risk is retired.** Sleeper's own `gsis_id`
field is sparse (**31.3 %** of the draftable top-300 by search_rank), which would have been a blocker — but
nflverse `player_ids` carries a native **`sleeper_id`** column, and `sleeper player_id →
player_ids.sleeper_id → gsis_id` covers **297/300 = 99.0 %** of draftables (misses are camp bodies).
Ingest gotchas recorded: the crosswalk stores `sleeper_id` as DOUBLE (`4984.0` — cast before joining) and
Sleeper pads some `gsis_id` values with leading whitespace. Also confirmed: `state/nfl` (season 2026 live),
the 12,200-player dump, trending adds; **no public ADP endpoint exists** — Sleeper "ADP" must be *derived*
from completed drafts at scale, and **pick-by-pick shape is unconfirmed** until we probe a real
username/league (none of the public seed accounts expose a completed draft; the user's own league does this
for free at step 0.10). Verdict: **PARTIAL — identity solved, draft-shape deferred to 0.10 by design.**

## Phase 10 — season/playoff simulation: calibrated championship probabilities (2026-07-09)
**The engine the reframe promoted is live and PASSES its done-bar: preseason championship/playoff
probabilities are calibrated on DEV.** New package `simulation/` (weekly · season · playoffs · leverage) +
`steps/phase10_sim.py` + 15 pure tests; the Phase-5 weekly-grain deferral is folded in as planned.

**Design (user decisions 2026-07-09).** League = `LeagueFormat(10 teams, reg 1–14, 6-team playoff 15–17,
top-2 byes, reseeded semis, PF tiebreak)` — a parameter, not a constant. Weekly grain = **top-down
disaggregation**: season totals are drawn by the Phase-5 sampler itself (now `return_games=True`, same rng
stream), correlated **board-wide once** with the Phase-8 Σ via an Iman–Conover *permutation*
(`correlation_permutation` — regression-tested equal to `correlate_samples`, and the games-played companion
rides along with its own draw), then each draw is split across the player's active weeks: real NFL bye
(from `game_lines`, PIT) forced to zero, missed games placed uniformly at random, active-week shares
**Dirichlet(α = 1/CoV²)** from his own 5.3 weekly volatility. Weeks sum *exactly* to the season draw — all
Phase-5 calibration survives by construction. Rostered K/DST score the prior season's top-10 weekly
average as a constant; cloudless offense players (deep sleepers) the prior season's replacement level per
week. Lineups: **optimal weekly for all 10 teams** (the Phase-1 convention, symmetric; a vectorized
evaluator regression-tested equal to `optimal_lineup_points` makes 90k league-weeks cheap).

**The calibration gate (1,800 team-seasons: 2017–2022 × 30 ADP+noise leagues × 10 teams; preseason
predictions vs the SAME rosters+schedule replayed on realized weekly points):**
- **Title: Brier 0.0878 < 0.0900** (constant-0.1 baseline); reliability essentially on the diagonal —
  predicted 0.036/0.076/0.123/0.184/0.282 vs realized 0.045/0.073/0.123/0.186/0.235 per bin.
- **Playoff: Brier 0.2302 < 0.2400** (constant-0.6); bins near-diagonal, mild edge-bin overconfidence.
- **League points spread matches reality: sim-sd / realized cross-team sd = 1.02** (the 10.1 "matches
  historical league variance" criterion). Ranking stability across fresh draws: playoff Spearman 0.975,
  title 0.949 (title is resolution-limited among near-equal ADP rosters, by construction).
- **10.3 leverage behaves like theory says** at realized week-8 standings with predicted futures
  (18 leagues): mean-preserving variance ↑ (1.6× vs 0.6×) moves the trailing team's playoff prob
  **+0.018** and the leader's **−0.028**; title effects ≈ 0 between equal-strength teams in a knockout —
  the lever is about *making the cut*, exactly the DFS-GPP logic. `leverage_advice` returns the curve +
  verdict (add/cut/hold) from any mid-season state (`simulate_league` resumes from `start_week/wins0/pf0`).

**Documented limitations (honest, non-blocking):** (a) team season-points 80%-interval coverage is
**62.4%** — the Phase-5 *unconditional* role/depth-attrition gap propagates (its known limitation, not a
new one); (b) a level bias of **−137 pts/season/team** (~−8/wk): predicted optimal-lineup totals run low —
prime suspects are prior-year weekly CoV understating realized week-to-week spread (the lineup max feeds on
spread) and the replacement-constant fallback for cloudless players; probabilities — the deliverable — are
relative within a league and calibrate anyway. Revisit only if a consumer needs absolute points.
**What Phase 9.5 gets for free:** `title_probability`/`playoff_prob` per roster = the `make_playoffs` vs
`championship_or_bust` objectives, now with a calibration certificate.

## Full-codebase audit → remediation register (2026-07-10)

**Goal:** review the whole engine in detail, catalogue where problems do/could occur, and record the exact
long-run fix per item. No modeling code changed — audit + docs only.

**Health:** 194 tests pass, ruff clean, DuckDB present (309 MB), 2026 ADP snapshot fresh. Code is mature and
unusually well-documented; PIT/lockbox discipline is enforced structurally (at the read). The issues below
are latent risks and honestly-documented modeling limits, not broken code.

**8 problems, each with its fix, now tracked in `docs/TECH-DEBT.md` (T1–T8) and sequenced in ROADMAP ★ THE
PIPELINE:**
- **T1 (🔴 now):** a full session (Phase 10 + Stage 0) is uncommitted — only in the working tree.
- **T2 (🔴 → ☑ done 2026-07-10):** the 2026 ADP snapshot series + 2025 `stats_player` backfill were
  **unreproducible** and lived only on the gitignored WSL disk with no backup. → added `steps/backup_db.py`
  (idempotent, md5-verifying) and ran it: 6 snapshot parquets + 3 backfill parquets + a timestamped 295 MB
  `.duckdb` dump now at `/mnt/c/Users/rayha/fantasy-quant-backup/`, byte-identical to source; wired into the
  weekly Stage-0 chore. Optional stretch left open: git-LFS on `data/raw/adp/snapshots/`.
- **T3 (🟠 pre-lockbox):** downside under-modeled — unconditional coverage **44 %**, points coverage **62 %**.
  Two causes: `injury.availability_frame` gate `prior_games≥8` (`injury.py:87`) drops the volatile cohort to
  a flat median + shared `rho`; and **role/depth attrition is unmodeled** (`Y=H·(G/G_ref)` has no role term).
  → cohort availability prior + a **role-survival haircut** `Y=H·(G/G_ref)·R` (reuse `estimate.py:role_ranks`).
- **T4 (🟠 pre-lockbox, with T3):** sim level bias **−137 pts/team/season**. Prior-yr weekly CoV
  (`weekly.py:203`, single season) understates spread feeding the lineup max; flat K/DST + cloudless constant
  fallbacks (`weekly.py:120–140`) never spike. → attribute by roster slot, pool CoV over 2–3 seasons, jitter
  the fallbacks. (Widening spread also lifts T3 — hence done together.)
- **T5 (🟠 at the lockbox):** the eval is one-shot with accumulating DEV researcher-df. → pre-register the
  frozen stack + metrics; 2025 full-stack dress rehearsal; track the DEV decision count.
- **T6 (🟡 with 9.5):** `assemble_distribution` recomputed by the optimizer (`optimizer.py:100`) and the sim
  (`weekly.py:195`); shares a draw only by the default `seed=0` and diverges silently otherwise. → one
  memoized `cached_distribution` + a threaded seed.
- **T7 (🟡 opportunistic):** FantasyPros/FFC scrapes fail silently; `props_projection` is a no-op. → freshness/
  schema guards in `data/validate.py` as red tests; archive raw payloads; formally shelve the props layer.
- **T8 (🟡):** `DraftConfig.objective` (`config.py:141`) is a dead label — nothing consumes it; opponents are
  still ADP+noise. → **9.5** routes `objective` to Phase-10 `title_prob`/`playoff_prob` (now); the behavioral
  opponent model needs a real Sleeper league (step 0.10 → Phase 11), with the availability Brier owed from S4.

**Takeaway:** the two 🔴 items are pure loss-avoidance (do now). T3+T4 are the real modeling work and the
highest-leverage fixes to land **before** the lockbox freeze, because the one-shot eval and the app's
"honest distributions" pitch both rest on the distributions being correctly wide.

### 2026-07-10 — T7 done: scrape guards + raw-payload archival + props formally shelved
Hardened the two external scrapes that are the value/availability spine so they **fail loudly** instead of
ingesting garbage, and closed the props no-op limbo.
- **Freshness/schema gates** (`data/validate.py`, wired into `data_health_report._scrape_gates`): three pure,
  injectable gates — `adp_freshness_gate` (live-season FFC snapshot ≤ 6 days old, i.e. the CLAUDE.md §2
  Stage-0 chore promoted to an assertion), `board_size_gate` (FantasyPros board in 400–700; 2026 = 528),
  `match_rate_gate` (gsis-match ≥ 95 %; 2026 ran ~0.99). Each fires **only when the relevant live board is
  present**, so historical-only dev stores stay green (no false alarms). 7 new unit tests, wall-clock-free.
- **Raw-payload archival** (`cache.archive_text`): every FFC/FantasyPros pull date-stamps its raw JSON/HTML
  under `data/raw/**/payloads/` (gitignored, one file/day) so a broken scrape can be diffed against last-good
  shape. Best-effort — an archiving error never sinks the pull. 3 new tests.
- **Props layer — SHELVED** (user decision): formally deferred, not a silent no-op. Consistent with the
  reframe's "don't fight the sharp market"; the de-vig math stays built + tested for a future `ODDS_API_KEY`.
  Marked in `props_projection.py` + `ROADMAP.md` 2.3 (⏸️).
**Takeaway:** the spine now has a schema-drift tripwire and a forensic trail; the only remaining tech-debt
before the lockbox is the modeling pair **T3+T4**.

## Phase 9 completion — draft policy: scarcity/lookahead + the win-prob objective (2026-07-10)
Closed out Phase 9 (9.1 scarcity half · 9.4 lookahead · 9.5 win-prob objective), folding in **T6**.

- **T6 — one shared draw cloud.** `distribution.cached_distribution` memoizes the Phase-5 assembler on
  `(season, ruleset, n_draws, seed)` and both consumers (`assemble_value`, `build_weekly_model`) read it;
  `samples` is bit-identical with/without the games companion (same rng stream), so the sim and the draft
  value can no longer silently diverge once a non-zero seed is threaded. `optimize_draft(winprob=True)`
  builds the sim on the **same seed** as the value index.
- **9.1 scarcity + 9.4 lookahead — one urgency term.** `positional_cliff` = the value drop below a player
  at his position in the current pool (a scarce tier that won't refill); `survival_prob` = P(he lasts to
  your next pick) from snake geometry + ADP-noise. Their product `scarcity_w·cliff·(1−survival)` is added to
  the marginal-CE score in `RiskModel.effective_rank`: **urgency fires only when a player is both well above
  his positional fallback AND about to vanish.** `scarcity_w=0` reproduces the covariance-only greedy exactly
  (the Phase-8 regression test pins it). 2022 DEV: 11/15 picks differ from the covariance-only board.
- **9.5 win-prob objective — `objective` is real (T8a).** Opt-in `winprob_pick_fn`: portfolio-CE/scarcity
  **prefilter → top-k**, then for each candidate finish the draft greedily (you) vs ADP+noise (opponents)
  and score the league with a **Phase-10 mini-sim**; take the candidate maximizing the routed metric —
  `make_playoffs`→`playoff_prob`, `championship_or_bust`→`title_prob`. Common random numbers across
  candidates. 2022 DEV: the two objectives draft **8–9 different roster slots**; the title-max board carries
  **+0.09 title prob** over the playoff-max board on an independent 1,000-world eval.
- **Finding — the title objective is resolution-limited.** At 60 sims/pick `championship_or_bust` chases sim
  noise and *under*-performs `make_playoffs` on realized title prob; at ≥~200 sims it correctly exceeds it.
  Title is a ~1-in-10 event, so it needs a healthy sim budget; `make_playoffs` (6-in-10) resolves cheaply.
  This is the same "title is resolution-limited" limitation the Phase-10 calibration gate documented — the
  policy inherits it. Default `winprob_sims=200`; `steps/phase9_policy.py` is the done-bar.
**Takeaway:** the greedy now plans (scarcity + snake-aware availability) and the objective finally *does
something*, consuming the calibrated Phase-10 probabilities — but only make-the-cut is cheap to optimize;
chasing the title needs compute. **Next: step 0.10 Sleeper ingest → the behavioral opponent model (T8b).**

## Sleeper account check — resolves but EMPTY (2026-07-11) → 0.10 still blocked
The user created a Sleeper account to unblock step 0.10 (behavioral opponent model, T8b). Verified via the
public read-only API: **`MadBawa` → user_id `1381536159267573760`**, `is_bot:false`, nothing private leaked
(email/phone null). **But it's brand-new and empty** — `/user/.../leagues/nfl/2026` and `/drafts/nfl/2026`
both return `null` (no leagues, no drafts). **Identity resolves; there is no draft data behind it**, so 0.10
cannot proceed — pick-by-pick drafts are the whole point. Full reference (API flow, identity crosswalk from
the 2026-07-09 probe, tiered unblock path) is now consolidated in **`docs/SLEEPER.md`**. **Recommendation:**
because the account is empty, the next autonomous session should be **T3+T4** (pre-lockbox modeling pair);
return to Sleeper once the user runs mock drafts (plumbing) or the real 2026 draft season lands (Aug–Sep,
gold-standard behavioral signal). **Takeaway:** a username was necessary but not sufficient — the Sleeper
step needs *drafts*, not just an account.

## T3 + T4 — downside coverage & sim level bias (2026-07-11) ☑
The pre-lockbox modeling pair (TECH-DEBT T3, T4). Attribution-first, then fix, all tuned on DEV
(2014–2022); the 2025 holdout read **once** at the end (T5 discipline; 2025 is the calibration holdout,
not the lockbox 2023/24).

### Attribution spike (read-only) — reshaped both fixes
- **T4 owns the OFFENSE (weekly-disaggregation) path, not the K/DST fallbacks.** Decomposing the
  team-points bias by roster slot: offense (CoV path) −140, K/DST (fallback path) **+16** (slightly high).
  So the "flat K/DST constant" candidate was a non-issue — jittering it would have made the bias *worse*.
  K/DST left untouched.
- **Per-player weekly CoV is already well-calibrated** from the prior season (RB 0.67 model vs 0.63
  realized; WR 0.70 vs 0.70), so "stale single-season CoV" was also wrong — pooling doesn't move the bias.
- **The real cause is structural:** the mean-preserving Dirichlet week-split reproduces each player's
  marginal weekly CoV but its light tails understate the weekly optimal-lineup MAX (a tail statistic),
  because a mean-preserving split caps weekly upside at the season total. It needs ~1.8–2.0× the true CoV.
- **T3 diagnosis:** 31 % of board players realize below their own q10, and **~95 % of those barely played**
  (weeks < 50 %, realized ≈ 0 with q10 > 0); only 6 % miss above q90. So the downside miss is an
  **availability / roster-security** phenomenon, *not* the "plays-but-produces-less" case the planned
  healthy-conditioned production haircut targeted.

### T3-A — cohort availability prior (the main coverage lever)
`injury.cohort_availability_prior` routes the sub-`prior_games≥8` cohort (rookies/backups, ~17–21 % of the
board, RB/WR-heavy) off the single median fallback to a `(pos × draft-capital tier)` prior for both
`avail_p` and its Beta-Binomial `rho`. Recovers signal the median erased: hi-capital rookie RB plays 0.67
of games vs lo-capital 0.42, fat `rho` (0.37–0.42 vs the 0.15 shared fallback). **Alone: DEV uncond
coverage 39 % → 63 %, conditional 79 % → 76 %.**

### T3-B — role-loss WASHOUT mixture (reformulated from the diagnosis)
The originally-specified production haircut (crater = below replacement, conditioned on healthy)
**did not work**: it added ~0 to unconditional coverage and dropped conditional to ~72 %, because the
dominant miss is *not-playing*, not *low per-game output*. Reformulated as an **availability** mixture:
`injury.role_retention` estimates a tier-specific **washout** rate (played < 40 % of games) + the low
`crater_avail` (≈0.15) and `keep_frac`; `distribution.sample_player_season` draws, with prob `p_crater`, a
*replacement* low-availability branch (not additive → injury not double-counted). Applied to **established,
deep-projected** players only — pure role loss; elite/starter washouts are injury, already in `G`.
Restricting to the deep tier was the frontier-best (DEV uncond 70 / cond 75, vs 62/69 hitting all tiers).
`covariance/estimate.role_ranks` reuse turned out unnecessary — tiers key on projection rank vs the
startable/replacement rank (simpler, PIT).

**T3 result — 2025 holdout (read once): unconditional 80 %-interval coverage 44 % → 77 %, conditional
76 % → 76 % (held).** DEV: uncond 39 % → 70 %, cond 79 % → 75 %.

### T4 — weekly-spread correction κ
`weekly.SPREAD_KAPPA` (per-position) inflates the *effective* weekly CoV to restore the lineup-max tail.
**Mean-preserving per player** (row sums still equal each season draw), so season totals and the whole
Phase-5 / T3 calibration are untouched — only intra-season shape moves. QB is a single mean-preserving
slot (barely responds) → smallest inflation. Also pooled `wk_cov` over the prior **two** seasons.

**κ is a genuine trade-off, not a free win.** Higher κ closes more bias and lifts coverage but
over-disperses the sim (spread ratio ↑) and eventually flips the dog-leverage gate (at high baseline
variance a longshot no longer gains from *more* variance). Swept on the DEV gate:
- κ≈2.0: coverage 79 %, bias −96, **but** spread 1.37 and the dog-leverage gate **breaks**.
- κ≈1.6: all gates pass (dog +0.013), spread 1.28, but coverage 71 % and bias −133.
- **κ = {QB 1.4, RB/WR 1.8, TE 1.7} (chosen):** the highest κ that keeps every hard gate passing —
  **1,800 DEV team-seasons: points coverage 62 % → 77.2 %, bias −137 → −113, title Brier 0.0881 (< 0.09),
  playoff 0.2342 (< 0.24), stability 0.979/0.949, dog-leverage +0.0009, all gates PASS.**

**Residual T4 limitation (documented):** ~−113 pts/team/season remains, concentrated in the early/COVID DEV
seasons (2017/18/20 start ~−220 at κ=1.0) and partly a **projection-level** shortfall κ can't fix (κ is
mean-preserving). Since the championship/playoff deliverable is *relative within a league*, it stays
calibrated anyway (Brier + reliability diagonal hold). Fully closing the absolute level would need a
non-mean-preserving weekly-upside term (breaks the Phase-5 sum invariant → gated behind explicit approval)
or better early-season projections — future work.

**Takeaway:** T3 fixed the downside coverage via **availability**, not production (the diagnosis overturned
the original per-game-haircut spec); T4's mean-preserving κ lifts coverage and cuts the bias under a hard
leverage/spread ceiling. Both harden the exact distributions the Phase-9.5 win-prob objective consumes.
210 → 216 unit tests pass, ruff clean. **Next: T5 pre-registration before the lockbox eval.**

---

## Step 0.10 — Sleeper draft ingest (2026-07-11): the pick-by-pick data pipe

**What & why.** The reframe's availability signal is "ADP + a *behavioral* opponent model," and the model
is Brier-verifiable only against **real completed drafts**. Step 0.10 builds the ingest that turns Sleeper
drafts into PIT store tables + a derived ADP board — the plumbing Phase 11 fits on. User banked **3 mock
drafts** on `MadBawa`; this session ingested + verified them. Scope (user decision): *stretch* — plumbing +
a first behavioral/ADP artifact + sim wiring, built **corpus-ready** for many mocks and future real leagues.

**The data (field-verified on the 3 mocks; all `complete` snake, 10-team × 15-round PPR, 2026, 150 picks each):**
- **Mocks aren't on the user endpoint.** `GET /user/<id>/drafts/nfl/2026` returns `[]` for the mocks — they
  are reached **only by `draft_id`** (from the board URL). (Real leagues *do* surface via user→leagues→drafts.)
- **`picked_by` is the human's own picks only.** 45/450 picks (15 × 3, all `is_human_slot`) carry
  `picked_by = <user_id>`; the **405 bot picks have `picked_by = null`** and `roster_id = null`. `draft_order`
  is a single entry → the user's `human_slot` (3 / 6 / 8 across the three mocks). **⇒ solo-vs-bots mocks have
  no persistent opponent identity** — the decisive finding for scope: a mock keys behavioral stats by
  `draft_slot`; only a **real human league** keys by `picked_by` (the signal the Phase-11 fit needs).
- **Identity crosswalk (measured on all 450 picks):** QB/RB/WR/TE **100 %**, K **80 %**, team DEF **0 %**
  (their `player_id` is the team abbr — no gsis — bridged to a `dst_team` key, matching `_NON_GSIS_POS`).
  Unmatched *skill* players are logged, not dropped (none in this corpus).

**What shipped.** `src/fantasy_quant/data/sources/sleeper.py` (keyless public API, 404-tolerant + retry +
raw-payload archival; pure `parse_*`/`crosswalk`/`build_*` + thin DB wrappers). Tables `sleeper_drafts` +
`sleeper_draft_picks` (idempotent upsert by `draft_id`, so re-ingest replaces and new drafts accumulate).
`build_mock_adp` emits rows in the **`adp_snapshots` contract** (`source="sleeper_mock"`): `adp` = mean
pick, `stdev`/`high`(min)/`low`(max)/`times_drafted`; so `adp_asof(source="sleeper_mock")` **and the draft
simulator consume it with zero code change** — verified by drafting a 2026 mock against it. `build_tendencies`
→ POC `sleeper_tendencies` (per-slot positional cadence + reach-vs-ADP; reach is corpus-relative on n=3, a
plumbing POC not a fit). Three pure gates in `validate.py` (contiguous-unique picks, skill gsis ≥95 %, human
slot resolved) wired into `data_health_report`, firing only when the tables exist.

**Board sanity (170 players, 3 drafts):** Bijan 1.33, Gibbs 2.67, Chase 3.00, Puka 3.33 … 2026 rookies
present (Hampton, Love, McConkey). All 0.10 gates PASS; the existing ADP gates stay green with the
`sleeper_mock` rows added (top-150 unmatched 0.12 %, freshness fresh, uniqueness holds).

**Takeaway.** The *ingest* is done and corpus-ready; the *behavioral fit* + availability Brier (T8b, Phase 11)
remain **blocked on real-league pick logs** (bot mocks are weak signal, no opponent identity). Grow the corpus
by adding draft ids / a username to `ingest_drafts`. **226 tests, ruff clean.** Next buildable pipeline item:
**Phase 7** (opportunity-adjusted projection); Phase-11 fit resumes when real leagues land.

### 0.10b — corpus crawler + human/bot separation (2026-07-11, same session)

Per the user's data plan (gather real-human drafts via **human mock lobbies**; build the corpus infra now),
added the crawler that scales the corpus without hand-collecting ids.
- **Crawl + participant expansion** (`crawl_expand`): BFS from seed usernames (walk each user's
  `leagues→drafts` across 2018–2026) + seed draft_ids, then for any *human* (multi-manager) draft, pull the
  seated user_ids from `draft_order` and crawl their histories too — so **one human mock lobby → its ~10
  humans → their leagues**, the multiplier that makes a real corpus reachable without joining many leagues.
  Rate-limited, dedups against the store, `max_drafts`-capped. Verified offline with a fake HTTP client
  (username→league→draft discovery + a 2-manager draft expanding to a second user); live smoke test against
  the current store correctly reports 0 new / 0 human drafts.
- **Human vs bot ADP split:** each draft tagged `is_human` (≥2 distinct `picked_by`); real drafts feed a
  **`sleeper_human`** board, bots a **`sleeper_mock`** board — bot ADP (Sleeper's algorithm) never dilutes the
  human ADP the opponent model wants. `_upsert` made schema-drift-safe so the corpus schema can evolve.
- **Behavioral seed:** `sleeper_manager_profiles` — per real manager across all their drafts: positional pick
  share, mean reach-vs-ADP, top NFL teams. The Phase-11 opponent-model input (empty until real drafts land).
- **Data-appetite finding (quantified):** board mean-ADP SE ≈ σ_pick/√N (mid-round σ≈15 → N=20 ⇒ ±3–4
  picks); a Brier-verifiable opponent model needs **~50 real human drafts min, ~100–150 ideal** — sourced
  cheaply via human mock lobbies + participant-expansion crawling, not by joining many leagues. Bot mocks add
  ADP only (cap ~10–20; FFC already covers production ADP). See `docs/SLEEPER.md` for the table.

**Status:** ingest + crawler complete and corpus-ready. **232 tests, ruff clean.**

### 0.10c — league-seeding + iterative snowball + a REAL live corpus (2026-07-11, same session)

User couldn't find live human mock lobbies (too early in the season) but chose to **web-search public
leagues**. Key reframe: *live* mocks are irrelevant — the crawler reads **historical** leagues, and every
2018–25 human league is public in the API now (and better: they have realized outcomes → the availability
Brier is computable). Enhanced the crawler + ran it live.
- **League-ID seeding + iterative BFS** (`crawl_expand`): seed from `league:<id>` (→ its drafts + members)
  as well as usernames/draft_ids; the participant expansion is now a real multi-level snowball (a human
  draft's `draft_order` managers are queued and crawled until no new users / `max_drafts`).
- **Found + validated public seeds:** the official Sleeper API-docs example leagues resolve live and are real
  human drafts — `289646328504385536` (2018, 12-team, 180 picks, **all `picked_by` populated, 12 managers**)
  and `206827432160788480` (2017, 10-team). This **confirmed the core assumption**: real-league drafts carry
  full per-manager opponent identity (only bot mocks are sparse).
- **Live crawl result:** snowballing from those 2 seeds reached the connected co-manager component —
  **149 human + 117 bot drafts (2017–2020), 289 manager profiles, `sleeper_human` board ≈2,580 rows/season,
  skill gsis-match 99.8 %.** All gates PASS. Real behavioral signal (e.g. a manager seen in 16 drafts, avg
  reach −10, fav teams CLE/LAR/NO). **The Phase-11 *data* blocker is cleared** — a first fit + Brier can run.
- **Two real bugs the live data exposed (both fixed):** (1) `sleeper_drafts.league_id` was inferred `INT32`
  when first seen all-NULL (bot mocks) → real string league_ids couldn't append → made `_upsert` a full
  **type-drift-safe rewrite** (also atomic, no delete-then-fail gap). (2) The multi-season ADP board has a
  gsis appearing in several seasons → the reach `.map`/`.merge` fanned out (`InvalidIndexError`) → made the
  reach join **season-aware + collapsed to one ADP per key** (`_attach_reach`).
- **Corpus-quality finding:** a crawl is ~44 % **abandoned drafts** (116/266; people quit mid-draft) + some
  auctions/linear. Fix: derived artifacts (ADP boards, manager profiles) use **complete snake/linear only**;
  the integrity gate checks **no duplicate `pick_no`** (real corruption) and *reports* incompleteness rather
  than failing it. **234 tests, ruff clean, all data-health gates PASS.**

## Phase 11 — behavioral opponent model + availability (2026-07-11) ☑ core DONE
The reframe's promise cashed: the opponent model's job (who gets picked, given the board) has hard ground
truth, so it is **Brier-verifiable** — and it verifies.
- **11.1 fit — a conditional (McFadden) logit beats ADP.** At each pick the manager chooses one of the
  top-40 available-by-ADP skill players; utility = β·features, choice prob = softmax over the *candidate
  set* (grouped-softmax NLL + L2, vectorized `np.*.reduceat`, scipy L-BFGS). Fit on **7,900 real human picks
  across 9 seasons**, using **FFC as the ADP board** (external consensus → no circularity with the Sleeper
  corpus that the `sleeper_human` board would introduce). **Walk-forward (leave-one-season-out) log-loss
  3.613→3.501, gain +0.113 CI[+0.101,+0.124]; Brier +0.0088 CI[+0.0076,+0.0100]** — beats the ADP-only
  baseline (a logit on ADP alone ≡ "ADP + logistic noise", strictly stronger than the sim's ADP+Gaussian).
- **The behavioral story (interpretable coefs):** **fandom +1.03 is the *strongest* signal** — managers
  reach hard for players on their favorite teams; then **rookie hype +0.45**, **roster need +0.33**, mild
  positional-run chasing +0.07; TE/QB go a touch earlier than raw ADP, RB/WR a touch later.
- **Two bugs the real data exposed (both fixed):** (1) a scalar-reduction `TypeError` in the NLL
  (`X[chosen] @ beta` is a vector — needed `.sum()`); (2) **`fav_teams` is stored comma-separated**
  (`"CLE,MIA,DET"`), not JSON — the `json.loads` silently fell back to empty, zeroing fandom across 307k
  rows (statistically impossible → the tell). Fixing the `.split(",")` **~tripled** the log-loss gain
  (+0.040→+0.113): fandom was the single biggest missing signal.
- **Candidate-set gotcha:** with K/DST as candidates but never as (skill-only) *choices*, the never-pick-
  K/DST signal inflated every skill position dummy (+3 to +3.9) and *hurt* top-1 accuracy while helping
  log-loss. Restricting the candidate universe to skill players fixed the dummies to interpretable relative
  preferences. Absolute log-loss is high (~3.5, near ln 40) because the exact pick among ~40 similar players
  is genuinely high-entropy — the **proper-scoring gain over ADP** is the deliverable, not top-1.
- **11.2 availability Brier — the owed S4 metric, and it's a rout.** MC-simulate the intervening opponent
  picks under the fitted model → per-player survival to your next pick; score on real windows vs the
  incumbent `survival_prob`. **Behavioral Brier 0.158 vs best-tuned ADP+noise 0.316** (swept noise 3–36 so
  the baseline isn't a strawman; **default noise-5 is 0.419 — worse than a base-rate constant**, i.e. the
  MVP placeholder is badly overconfident on the contested band). **Gain +0.159 CI[+0.083,+0.264].** Promotes
  from opt-in to the S4 default.
- **11.3 realistic mock — personalities differentiate.** A `Personality` tilts the fitted β (scale/override,
  temperature, round-dependent positional penalty); plugged into `simulate_draft` via a new backward-
  compatible `opponent_pick_fn` hook. Behavioral opponents draft a human-like first-3-rounds mix
  (**RB14/WR14**) where pure ADP+noise robotically takes **RB21/WR9**; `zero_rb` drops early RBs to 5.
- **Scope kept honest:** MCTS/CFR/auction/self-play stay out (deprioritized/dropped/roadmap) — the
  *verifiable* core (fit + availability + configurable mocks) is what Phase 11 owed, and it's done + green.

## Phase 7 — opportunity-adjusted projection (2026-07-11) ✗ BUILT & DROPPED
A keep-or-drop gate that **dropped** — a clean negative result, exactly what the gate is for.
- **7.1 skill÷opportunity decomposition** = a **two-way fixed-effects (AKM worker/firm) split** of
  position-and-season-relative log-ppg into a per-player **skill** effect (transferable) × a per-team
  **situation** multiplier (opportunity); ridge-regularized (weak identification for non-movers), movers
  identify the split. Face-valid: top skill = **Kelce, McCaffrey, A.Brown, Kamara, Elliott, Cook,
  Jefferson, Barkley, Hill, Bell** (elite, team-independent). **But skill does NOT travel better than raw
  production** across moves (Spearman skill↔realized **0.458** < prior-rate↔realized **0.587**) — the
  ridge-shrunk skill estimate is noisier than just last year's rate.
- **7.2 re-projection** done right as an **information-preserving delta** (`log opp = log prior_rate −
  situation[old] + situation[new]`; non-movers ≡ naive). On **466 role-changers** the situation swap is a
  **wash-to-slightly-worse than naive carry-over** (ppg-MAE 2.972 vs 2.901; gain −0.070 **CI[−0.152,+0.014]
  includes 0**), and the existing **EB-shrunk market baseline beats it** (2.821). *(First-pass reconstruction
  from scratch — `pos_base + skill + situation` — was much worse, MAE 3.29; the delta form is the fair test.)*
- **7.3 rookie transport** *works* but duplicates Phase 4.3: draft-capital + landing-spot situation + combine
  forty → a rookie **distribution** (point + 1σ band). Held-out **1σ coverage 0.66** (≈ target 0.68, well-
  calibrated) and **Spearman(pred, realized) +0.53** (vs 4.3's +0.62). Conditional-on-playing (documented
  survivorship: never-play draftees are out of sample).
- **Verdict (as-written bar): DROP.** Overall it's within tolerance of the consensus proxy, but it is not
  *strictly better on role-changers* (the second half of the bar). **Thesis-consistent:** a team fixed-effect
  carries no exploitable move-signal beyond carrying the player's realized rate forward — consensus already
  prices situation changes. Code stays in-repo as a validated-and-dropped experiment (cf. props/CFR).



## Session A — S6 adaptive archetypes + Phase 13.1 re-projection + 13.2 start/sit (2026-07-12)

**Goal:** the first in-season substeps, plus the adaptive draft archetype. Session A of the ROADMAP
session-bundling plan (S6 + 13.1–13.2). All three DEV done-bars PASS; 261 tests, ruff clean. The code
for all three pre-existed from the interrupted session; this session verified it, added the missing
tests + done-bar runners, ran the validations, and recorded the results. Lockbox (2023+24) untouched.

**S6 — adaptive archetypes (`draft/config.py` `adaptive` + `_adaptive_tilt`; `steps/spine_5_adaptive.py`).**
- The static archetypes (`zero_rb`, `hero_rb`, …) are fixed `(pos, round, have)` fade/reach curves that
  assume the room drafts on ADP. When it doesn't — an elite RB slides two rounds past his ADP — a static
  Zero-RB keeps fading the very value that fell to it. **`adaptive` = a wrapper on an `adaptive_parent`
  that melts a *fade* in proportion to how far a candidate has diverged from his ADP** (`slide = (overall
  − adp)/n_teams`; a fade decays by `ADAPT_DECAY·max(|slide|, ADAPT_SLIDE_WEIGHT·max(0,slide))`, so value
  actively *sliding to us* melts it ~2× faster than a reach). A fade only melts toward 0, never flips to a
  reach; reaching archetypes (positive tilt, e.g. `elite_te`) are untouched (no fade to melt). With no
  board context it reproduces its parent to the float (the leave-one-out / benchmark path).
- **Done-bar PASS** (behavioral vs ADP room, team-value, block-bootstrap over 2017–22 × 6 seeds):
  `adaptive(zero_rb)` **+2.0** team-value in the behavioral room (board-divergence 4.25 rd) and 0.0 in the
  ADP room (do-no-harm); `adaptive(hero_rb)` **+15.6** (CI[+6.8,+23.0]) in the behavioral room, ADP-room
  CI includes 0. **Reading:** adaptive does no harm on an ADP board and banks value when it breaks — and
  *that boards break is the Phase-11 finding* (behavioral opponents diverge sharply from ADP), so this is
  the realistic case, not a corner one.

**13.1 — weekly re-projection (`inseason/reproject.py`; `steps/phase13_1_reproject.py`). PASS.**
- A scalar **Kalman filter** on each player's per-week scoring *level*: the preseason Phase-5/10 season
  projection ÷ active weeks is the prior `m0`, worth `PRIOR_WEEKS=5` pseudo-obs; each played week nudges
  the level toward realized, weighted by his own 5.3 weekly noise `r`; `process_var>0` makes it a slow
  random walk (recent form outweighs a hot September; default 0). **PIT by construction** — a re-projection
  *at* week `t` reads only weeks `≤ t`. A **reserved `news` slot** (per-player level shift) is wired through
  the input contract now and defaults to a no-op, so Phase-12 news/NLP plugs in later without a rebuild.
- **Done-bar PASS**: re-projection's forecast MAE on the *future* played weeks beats the frozen preseason
  level in **6/6** DEV validation seasons — mean gain **+0.396 ppg/week**, season-block CI **[+0.32,+0.48]**
  (per-season gains +0.28…+0.56, each with a per-player-clustered CI excluding 0). Results land, the value
  signal sharpens.

**13.2 — start/sit (`inseason/lineup.py`; `steps/phase13_2_lineup.py`). Co-pilot PASS; variance-tilt DROP-as-default.**
- **The done-bar (PASS) is the co-pilot beating set-and-forget.** The weekly mean-max lineup ranked by
  13.1's **re-projected** means outscores the same lineup ranked by the **frozen preseason** level on
  **realized** points: **6/6** DEV seasons, **+2.08 pts/lineup-week** (season-block CI [+1.56,+2.54]),
  winning ~80% of lineup-weeks. This is where 13.2 delivers — not a clever objective, just feeding 13.1's
  better means into the ordinary "start your best" lineup.
- **FINDING — the win-probability *variance tilt* does not pay at the lineup grain.** The Phase-10.3
  leverage idea (trailing → add variance; leading → cut it) applied as a single legal start/sit swap
  **fails to beat mean-max OOS even for big underdogs**: mean win% gain **+0.0002** overall, **−0.0006**
  for underdogs, **0/6** seasons clearing the bar; a diagnostic split shows even deficit-> +15-pt underdog
  swaps net **−0.015** win%. **Why:** one swap moves team spread by a tiny fraction of the ~35-pt team sd,
  so the second-order variance benefit is swamped by the first-order mean cost — fully consistent with
  Phase-10.3, where leverage only bit at *whole-team* spread changes of 1.6×. **Resolution:** `optimal_lineup`
  default flipped to `objective="mean"`; the tilt is retained as opt-in `objective="win"` but off by
  default — the Phase-7 / props pattern (kept, not the default). *No amount of tuning `LEV_GAMMA/LEV_SCALE`
  rescues it: a bigger tilt makes bigger bad swaps, a smaller one makes no swaps → gain → 0.*
- **Design note honored:** 13.1's `news` slot reserves the Phase-12 hook per the 2026-07-11 reorder note.

**13.3 — waivers / FAAB (`inseason/waivers.py`; `steps/phase13_3_waivers.py`). Done-bar PASS.**
- **What it is.** A pure `faab_bid(value, budget, weeks_remaining, …)` that turns three forces into one
  sealed first-price bid: (1) **marginal value** (rest-of-season points over the freely-available
  replacement, from 13.1's re-projection) → willingness-to-pay via `value_scale`; (2) the **option value of
  budget** — a closed-form ration `1/(1+κ·(weeks−1))` (`OPTION_KAPPA=0.15`) that shades every bid down early
  (many future pickups) and → 1 in the final week (use-it-or-lose-it); (3) **first-price shading** — bid the
  surplus-maximiser `argmax_b (value−b)·P(win|b)` against a belief `opp_bids` about the field (else a flat
  `SHADE_FRAC=0.9`). Naive %-of-budget ignores all three.
- **Done-bar (PASS)**: in `n_leagues=200` **mixed-field** waiver seasons per DEV year (sharp `faab_bid` in
  seat 0, naive %-of-budget in seat 1, the rest alternating — so the sharp agent competes with equally-sharp
  opponents, not only fish), the sharp agent acquires **more realized rest-of-season value** than naive in
  **5/6** seasons — mean gain **+30.0** value/season, season-block CI **[+21.7,+38.8]** — and at a higher
  value-per-dollar (e.g. 3.47 vs 2.94). PIT: perceived value from 13.1 (weeks ≤ t); realized (weeks > t)
  only scores.
- **KEY FINDING — the objective must have diminishing returns or *volume* wins.** The first cut banked the
  full value of **every** acquisition; the naive agent then won on sheer aggression (25 %/round grabs more
  players) despite a tie on value-per-dollar → **smart lost 0/6**. Real FAAB has limited startable slots, so
  only your **best few** pickups actually contribute. Modeling that — score = **top-`n_useful`=4** realized
  pickups, and the sharp agent bids **marginal value over the pickups it already holds** (a 13th add that
  won't start is worth ~0) — makes budget genuinely scarce, rewards selectivity, and flips the result to
  **5/6 PASS**. Lesson (reusable for 13.4/13.5): a waiver/streaming/trade sim without a roster/slot constraint
  rewards churn, not skill.
- **Scope (user decision 2026-07-12): pragmatic now, rigor owed.** 13.3's spec said "reuse 11.4", but 11.4
  (auction support) was deferred to **Phase 15.4** and `draft/auction.py` doesn't exist. So `faab_bid` uses
  fixed/heuristic params (linear `value_scale`, closed-form ration, static `opp_bids`), **not** an equilibrium
  / budget-state DP. The rigorous upgrade is logged as **`docs/TECH-DEBT.md` T9** (fold into Phase 15.4). No
  real FAAB transaction data exists (the Sleeper corpus is draft picks only), so the field is synthetic and
  the done-bar is a relative sim result, not a Brier-verified fit.

**13.4 — streaming (`inseason/streaming.py`; `steps/phase13_4_streaming.py`). Done-bar PASS.**
- **What it is.** *Streaming* = not rostering one unit at a matchup-driven position all year, but picking up
  whichever freely-available unit has the **best matchup this week**. A contextual bandit over the waiver
  pool: the pure `stream_pick(proj, held, switch_margin, …)` starts the projected-best available streamer,
  keeping the currently-held one unless a challenger beats it by `SWITCH_MARGIN=1.0` pts (hysteresis). The
  projection is `matchup_projection = own + (opp_allow − league_mean)` — the unit's own scoring level plus how
  generous this week's opponent offense is to opposing defenses — with both terms **empirical-Bayes** shrunk
  (`PRIOR_GAMES=4`) toward the prior season (`_shrink`), so one flukey game doesn't crown a streamer (the
  shrinkage *is* the soft-explore; an optional `UCB_C` optimism bonus makes explore explicit).
- **Done-bar (PASS)**: demonstrated on **DST** (strongest matchup signal + real weekly scores from
  `dst_weekly_points`). Per DEV year, `n_managers=300` managers each get a random 8-unit slice of the
  waiver-tier defenses (outside the top-10 by prior-season points); we score **realized** DST points for
  matchup-streaming vs **static-hold** (roster the preseason-best unit, start it every week, eat its bye).
  Matchup-streaming wins **6/6** seasons — mean **+1.46 DST pts/week**, season-block CI **[+0.88, +2.09]**.
- **Signal isolation (the 13.3 anti-churn lesson applied).** Streaming's edge over static-hold is partly just
  churn (more roster moves = more weekly selection), so a second control — matchup-streaming vs
  **random**-streaming (pick a random available unit each week) — isolates the *signal*: matchup beats random
  **5/6** seasons (+0.2 to +2.5 pts/wk). The one miss (2018, +0.2) is an honest finding: the opponent-offense
  signal is real but **modest**, biting hardest in seasons where defenses are dispersed. The `switch_margin`
  hysteresis + the random control are how 13.4 avoids "rewarding churn, not skill."
- **Scope.** The done-bar runs on DST; `stream_pick` is **position-agnostic** (QB/TE streaming would feed
  13.1 re-projected means in as `proj`), but no separate QB/TE matchup model is built here — a documented
  extension, the Phase-13.2 "one passing bar + noted extension" pattern. PIT throughout: ratings read only
  weeks strictly before the decision week; the schedule (who plays whom) is public pre-season; realized points
  only ever *score*.

**13.5 — trades / market-making (`inseason/trades.py`; `steps/phase13_5_trades.py`). Done-bar PASS.**
- **What it is.** A trade is the one *cooperative* in-season move — both GMs must agree, so a completed trade
  is one that helps **both** rosters. That's possible because a team scores its **optimal starting lineup**,
  not its raw talent, so a player's worth is his *marginal* contribution to a startable lineup, which collapses
  past a roster's positional need (a 4th good RB rides the bench at ~0). Trades arbitrage **complementary
  surpluses**: each side ships from a position it is deep and fills a hole. The pure kernels: `lineup_value`
  (roster value = its optimal-lineup sum only, reusing the 13.2 greedy fill — the diminishing-returns lesson
  made positional); `evaluate_trade` (a swap's *change* in each side's lineup value; `mutual` iff **both** gain
  more than `ACCEPT_MARGIN`, the anti-churn hysteresis); `find_trades` (the market-maker — searches every
  opponent's surplus for mutual 1-for-1 / 2-for-1 deals, ranks by the **worse-off side's** gain — the fairest
  win-win a completed trade needs — and tilts toward **selling high / buying low** on a model-vs-market gap).
- **Done-bar (PASS)**: proposed trades must **raise both teams' simulated playoff probability** in the Phase-10
  MC season engine (schedule, H2H variance, playoffs — everything the additive lineup-value proxy ignores).
  Per DEV year, `n_leagues=40` snake-drafted **imbalanced** leagues; for `n_focal=4` maker seats we run
  `find_trades`, execute the top proposal, and re-simulate (a shared player-weekly cache + fixed schedule, so
  pre/post differ *only* by the two swapped rosters — a paired, low-variance comparison). Result: **6/6**
  seasons both the maker's and the partner's mean playoff-prob **rise** — maker across-season gain
  **+0.014→+0.021**, partner **+0.012→+0.021** (season-block CIs excluding 0; weaker side **[+0.011, +0.019]**).
- **Signal isolation (the 13.3/13.4 anti-churn control).** A **random-trade** control (swap equal counts at
  random) lifts both sides essentially never (~0–10%); proposed trades lift both sides **6/6** seasons far more
  often (`both_rise` 0.27–0.75). So it is the *surplus logic*, not mere roster shuffling, that creates the
  mutual gains. The sell-high/buy-low tilt is real but modest (`sell_high_rate` ~0.5–0.6: the maker ships the
  market-overvalued asset a slim majority of the time).
- **KEY design correction — "fair" ranking, not "greedy" ranking.** The first cut ranked proposals by the
  **maker's own** gain: the maker then reliably gained (+0.02 playoff prob) but only cleared a *marginal* floor
  for the partner, whose sim gain didn't survive MC noise → the worse-off side sat at ~0. Ranking by
  `min(maker, partner)` — the fairest win-win a two-signature trade actually needs — makes both sides gain
  robustly. This is the market-making analog of the 13.3 diminishing-returns lesson: the objective has to
  reward the *right* thing (mutual benefit), or the maker just skims.
- **Statistics note.** Per-season trade counts are small and jittery (n≈14–48; upstream `cached_distribution`
  board-ordering wobbles run-to-run), so the per-season two-CI test is underpowered (2018's partner CI grazes 0,
  an honest weak-surplus season echoing 13.4's 2018 miss). The **load-bearing test is the season-block bootstrap
  on each side's gain** (the 13.4 device) — decisive and stable across reruns — plus the 6/6 random control.
- **Scope.** Value currency = the preseason model rest-of-season mean, **self-consistent** with the sim that
  scores it (so the bar is PIT-trivial and fair). In-season this `values` slot is 13.1's re-projected mean over
  weeks ≤ t — fed in, not re-derived (the 13.4→13.1 extension pattern). The done-bar trades **1-for-1** (count-
  neutral, no roster-size bookkeeping); **2-for-1** consolidation is supported by the kernels and unit-tested
  but left out of the sim. PIT throughout; lockbox unread.

---

## Session C (2026-07-13) — Phase 12 news/NLP + Phase 15 multi-format/auction (all done-bars PASS; ruff clean; 306 tests)

**Overall.** Built the whole session straight through (user authorization). Ran the overdue Stage-0 FFC ADP
snapshot chore first (banked the 2026-07-18 boards, 99.2% gsis). Then Phase 12 (news/NLP) and Phase 15
(15.2 best-ball, 15.3 DFS, 15.4 auction; 15.1 dynasty deferred per user scope). +30 tests (19 `test_news`,
11 `test_phase15`), all DEV-only, lockbox untouched.

### Phase 12 — news/NLP: a **qualified KEEP** (injury signal pays; depth-chart signal doesn't)
- **12.3 event study — the load-bearing finding.** On the historical, PIT structured feeds (2017–22):
  **an injury designation predicts a large, significant production loss the stale set-and-forget lineup
  hasn't priced** — Out plays 0% and loses **+8.4 pts** vs the player's own clean-week baseline, Doubtful
  +8.2, Questionable plays 55% and loses **+3.9**; the overall exploitable lag is **+5.86 pts/start, CI
  [+5.5,+6.2]**. In contrast, **depth-chart changes do NOT separate** (promotion −0.87 vs demotion −0.77,
  separation −0.10, not directional) — nflverse depth-team ranks are too noisy/lagging → **DROP the depth
  signal** (the gate doing its job, like props/Phase 7).
- **12.4 keep-or-drop gate — PASS.** Priced status→availability multiplier on DEV (Out≈0.001, Doubtful≈0.01,
  Questionable≈0.56 — exactly `E[pts|status]/baseline`), filled 13.1's reserved `news` slot with a per-week
  level shift, and walk-forward-scored a news-aware weekly forecast vs the injury-blind 13.1. **On the
  designated subset (where it applies): MAE 6.5→2.5, gain +3.4→+4.3 pts/player-week, 6/6 DEV, season-block
  CI [+3.4,+4.0].** Diluted leaguewide gain +0.5 (also CI-clear). The scoring universe per week = players
  who played OR carried a designation (byes excluded).
- **The guardrail, literalized.** `extract.py` splits the two jobs the reframe demands: the LLM (a gated
  `ClaudeClient`, Haiku 4.5, behind `ANTHROPIC_API_KEY`) only turns fuzzy free-text into a structured
  `ExtractedSignal` (extraction); the deterministic core prices the signal into points (calibrated on DEV).
  The default path is the offline **rules** extractor — runs in every test, no network — so the core stays
  LLM-free. Free-text RSS is forward-only (109 rows, can't be backfilled) → the validated signal is the
  structured injury feed; the LLM path is a real but forward-only seam (the honest free-data consequence).

### Phase 15 — multi-format + auction
- **15.4 auction (+ T9). PASS 6/6.** A budget-state bidder — auction values (VOR→$, studs soak the surplus,
  last slots ≈$1) + the exact **$1-endgame** continuation (`endgame_cap`: never bid so much you can't fill
  the other slots at $1) + winner's-curse-shaded English bidding on **marginal** value (a 4th RB is worth
  $1 to a full backfield) — beats **naive budget-splitting** (bid `budget/slots`, value-blind) by **+66→
  +128 realized starting-lineup pts, season-block CI [+78,+108]**. **Discharges T9:** `faab_bid` now
  consumes `endgame_cap` (pass `slots_remaining`); the FAAB *value* done-bar is unchanged under the upgrade
  because winner-selection is **scale-invariant among symmetric bidders** (the continuation form changes
  prices/budget-efficiency, not who wins) — so the committed 13.3 result is untouched (no regression).
- **15.2 best-ball. PASS 6/6 — "variance is GOOD," the exact mirror of the 13.2 managed-lineup finding.**
  Best-ball auto-keeps each week's boom and discards the duds, so the weekly total is **convex** in a
  player's spread. A ceiling-aware drafter (rank `mean·(1+κ·wk_cov)`, κ=0.1) beats mean-only by **+37→+104
  pts/season, CI [+55,+93]**. **Key correction:** the signal is **weekly CoV**, *not* season-total sd —
  tilting on season sd (which carries injury/bust downside) drafts *worse* players and lost by −90; switching
  to `wk_cov` flipped it to a clean win. The convexity accrues to swing/depth slots (a locked starter's
  best-ball value ≈ his season total regardless of variance) — hence the small κ.
- **15.3 DFS GPP. PASS 6/6 — MECHANICS ONLY (honest data caveat).** No free DK/FD salary or ownership feed
  exists (the same gap that shelved props) → salaries synthesised monotone-in-projection, ownership modeled
  projection-driven. Under those mechanics a **leverage** lineup (fade high-owned studs) beats **chalk**
  (projection-max) by **+0.71→+1.12 payout, CI [+0.79,+1.01]**. The load-bearing mechanic is **duplication +
  prize-splitting**: the field folds to chalk (a 40% duplicate share) so a high-scoring chalk lineup splits
  first place ~80 ways (payout ~0.01) while the unique contrarian keeps it (~1.1). Not Brier-validated —
  wire a real DFS feed and the same kernels become validatable. Two build corrections en route: ownership
  had to chase **projection** (studs=chalk), not points-per-$ (which made scrubs "chalk"); and the salary
  cap must bind on the **weekly** projection scale (season-mean ÷16) with a wide-enough pool for cheap punts.

## Session D — MCTS research gate → T5 pre-registration → LOCKBOX EVAL (2026-07-19)
The engine-complete-before-app pipeline's closeout: the explicit MCTS research gate (before the
lockbox; CFR stays dropped), the T5 freeze/pre-registration + 2025 dress rehearsal, and the single
one-shot lockbox evaluation on 2023+2024. DEV-only until the lockbox line.

### 11.2 — MCTS draft engine: the research gate → **DROP** (a *textured* drop, not a flat one)
Built a genuine **determinized-UCT** (single-observer information-set MCTS / PIMC) over snake-draft
states (`draft/mcts.py`): top-K greedy candidates as actions, the ADP+noise room determinized per
iteration, **greedy rollouts**, and the **portfolio-CE** leaf value — i.e. the tree searches *on top of*
the exact Phase-9 greedy it is benchmarked against, optimising the same covariance-aware objective the
greedy climbs. Head-to-head on **9 DEV seat-seasons** (2020–22 × slots 1/6/10, k=5, 100 iters), same
board + same room (common random numbers), each roster scored three ways (`steps/phase11_2_mcts.py`,
`analysis/phase11_mcts.json`):
- **In-objective (portfolio CE): MCTS beats greedy +77.2, season-block CI [+46.9, +106.8], 89 % win-rate.**
  The search is *correct and works* — with a real iteration budget it reliably finds higher-CE rosters
  than the myopic greedy (a myopic greedy leaves plannable CE on the table; lookahead recovers it). At
  low budget (15 iters, the smoke) it *underperformed* the greedy even in-objective (−9 CE) — resolution-
  limited, the same lesson as the 9.5 title objective.
- **Out-of-sample (realized optimal-lineup points): Δ +31.9, CI [−90.3, +145.4] ∋ 0, 56 % win-rate.** The
  in-model CE gain **does not survive to realized points** — a coin flip. The greedy already banks the
  *realizable* plannable value; the extra CE the search extracts is largely in-model (optimising the
  covariance/CE objective harder), and that objective's residual edge over consensus is **unresolvable on
  ~10 seasons** (the standing Phase-2 / reframe finding). Predicted playoff prob rose +0.050 (89 %), but
  that is the model scoring its own rosters — circular with the CE it maximised.
- **Live budget: 8.5 s/pick (max 9.4).** ~100× the greedy's instant pick.
- **Verdict (as-written bar — beat greedy on realized pts OOS with a CI clear of 0): DROP.** Not because
  the search is broken (it demonstrably improves the objective) but because a snake draft is
  **near-perfect-information** and the objective's OOS link is too noisy for harder optimisation to pay —
  paying 100× the compute buys **no measurable realized edge**. Kept in-repo like Phase 7 / props / CFR;
  the covariance-aware greedy (+ 9.1/9.4 scarcity, 9.5 win-prob opt-in) is the frozen policy. Self-play RL
  (11.5) stays roadmap a fortiori — a heavier bet on the same objective whose OOS edge just failed to
  resolve. **This closes the optional research gate: no MCTS/RL in the frozen stack.**

### LOCKBOX EVALUATION — 2023 + 2024 — spent EXACTLY ONCE (2026-07-19)
The single held-out measurement of the frozen stack, pre-registered in `PLAN.md` §"⭐ T5
PRE-REGISTRATION" (committed `7bd6e10` *before* this ran) and reported **as-is** — no tuning, no
re-run of any metric. `steps/lockbox_eval.py --which lockbox` (30 ADP+noise leagues × 500 sims,
matching the DEV calibration gate; `analysis/lockbox_eval.json`). **Read against the decision-count
caveat: ≈35–40 selection decisions were made on DEV, so a *marginal* number is weak evidence and a
*decisive* one is strong.**

- **(1) Season/playoff sim — the north-star (600 team-seasons).** **Title Brier 0.0884 < 0.09 baseline
  — BEATS, and essentially identical to DEV (0.0881): the championship-probability calibration HOLDS
  OUT OF SAMPLE** (the single most important result — the reframe's north-star generalises). Playoff
  Brier **0.2398 vs 0.24 — a *marginal* beat** (DEV was a clearer 0.2342); by the decision-count caveat
  this is weak, honest evidence the playoff-cut calibration is near the baseline on these two seasons.
  Seed stability 0.945 (≥0.9 ✓); leverage directions correct (trailing +0.003 playoff prob at 1.6×,
  leader −0.017 ✓). Level bias **−76 pts** (smaller than DEV's −113). Points coverage **89.2 %** and
  spread ratio **1.40** — the sim slightly **over**-disperses on the lockbox (the mirror of DEV's
  *under*-coverage; the T4 κ inflation, tuned to lift DEV coverage 62→77 %, over-shoots to 89 % here).
  **Every hard gate the DEV gate defines PASSES on the lockbox.**
- **(2) Projection calibration — value = consensus→VBD (n=848).** Rank **Spearman 0.538** (holds; DEV/2025
  ≈0.57), overall **bias 0.620**, MAE 75.2. The value signal is **well-calibrated in rank, ~40–60 %
  optimistic in level** — exactly the standing finding (games-played attrition), **holding out of
  sample**, not a surprise.
- **(2b) Distribution 80 %-interval coverage (Phase-5 + T3).** **Conditional (players who play) 80.1 % —
  bang on the 80 % target OOS**: the risk layer is excellently calibrated for players who play.
  Unconditional 72.1 % — the **documented residual attrition gap** (a projected body who never plays;
  T3 lifted DEV 44→77 %) persists at a similar level OOS. Never claimed fixed → holds as the known
  limitation.
- **(3) Cost-of-personalization — realized-PAR archetype sweep (20 drafts each).** Per-archetype realized
  costs are **small and noise-dominated** — hero_rb +42.8, late_qb +26.8, elite_te +19.5, zero_rb −12.6
  PAR, **all CIs span 0** on 2 seasons. Projected→realized cross-check **Spearman +0.60, sign agreement
  75 % (n=8)** — a *weakly positive* directional link (better than DEV's ≈0). Consistent with the S3
  finding: **personalization is cheap and the projected cost is a draft-day aid, not a season forecast.**
  *(Harness note: this component crashed the first run — `validate_archetypes` swept S6's `adaptive`
  archetype, which needs an `adaptive_parent` (a latent bug from Session A that also breaks
  `spine_4_validate.py` on DEV → logged **TECH-DEBT T10**). Fixed at the harness level — sweep the 4
  static preference archetypes only; the **frozen modeling stack was untouched** — and computed once,
  its first and only look.)*

**Bottom line (reported as-is).** The reframe's honest-value claims **generalise out of sample**:
**calibrated championship probabilities** (title Brier 0.088 < 0.09, ≈ DEV), a **well-calibrated
conditional risk layer** (80.1 %), **rank-calibrated value** (Spearman 0.54), and **cheap, honestly-
priced personalization** — with the **known level-optimism / unconditional-attrition limitation
persisting** (projection bias 0.62; unconditional coverage 72 %; a *marginal* playoff Brier). No claim
of out-forecasting consensus is made or needed (proven unwinnable on ~10 seasons). **The lockbox is now
spent; the modeling stack is frozen. Nothing modeling-side changes on the basis of this result.**

## Session E (2026-07-24) — T10 + Phase-16 value-side (situation-change ADP-alpha) — an honest NULL

**Scope.** T10 warm-up + Phase-16 value track substeps 16.1–16.2 (16.3/16.5 drafted for review; 16.4
gated). Walled off from the frozen cost report; DEV-only (2014–22); lockbox untouched. 316 tests, ruff clean.

**T10 (`adaptive` archetype sweep) — fixed.** `validate_archetypes` prices `adaptive` **per parent**
(`adaptive(zero_rb/late_qb/elite_te/hero_rb)` as distinct subjects); `spine_4_validate` green again.
Adaptive≈parent on an ADP board (S6's own prediction), elite_te REAL-GAIN reads unchanged. Harness fix only.

**16.1 — team change + new starting QB → NULL.** Extended the Phase-6 ADP-alpha panel with two PIT
situation flags. **Neither is a stable ADP bias:** `team_changed` coef **−2.5 VOR/SD** (p_fdr 0.82,
stability 62 %), `new_starting_qb` **−0.1** (p_fdr 0.98, stability 50 %). Same discipline as DURABILITY
(season-block-bootstrap CI + BH-FDR + sign stability). Reading: **the crowd prices offseason team/QB
changes about right for value.**
- **PIT catch (a real leak avoided).** The ADP-board `team` column is contaminated with an *end-of-season*
  crosswalk — the Sep-1 **2022** board lists McCaffrey on SF, Toney on KC, Claypool on CHI, all *mid-season
  trades that had not happened at draft day*. Using it would leak future trades into a "draft-day" feature.
  Team-of-record is therefore derived from `weekly` (the **Week-1 team**, PIT), verified leak-free
  (McCaffrey→CAR/0). A franchise-alias map collapses relocations (OAK/LV, LA/LAR, FA→missing) so a
  relocation never reads as a player changing teams.

**16.2 — competition change, dual-sourced → BOTH WASH OUT (echoes Phase 12.3).** Two independent
operationalizations of "a same-position teammate arrived/left" (the player himself always excluded):
`competition_change_roster` (weekly usage + `draft_picks`, startable-caliber churn, 25 % rate) and
`competition_change_depth` (`depth_charts` **new competitor cracking the top-2**, 72 %). **The two disagree
in sign** (roster **−9.9** VOR/SD, depth **+9.8**) and **neither survives FDR** (both p_fdr 0.087, stability
67 %) — the sign-flip across measurements is the hallmark of a non-signal. Data notes: depth used
`depth_charts` (2014–24), not `depth_charts_ts` (2025-only); a raw depth *set-difference* floods to ~90 %
(reshuffle noise), so the "new entrant" definition was used; materiality is a leaguewide top-N-per-position
finish (`MATERIAL_RANK`), because a low bar (any deep-bench churn) hits ~every room every year.

**Wall-off & drift.** `FEATURES` (the frozen 5-trait softness model) stays **pinned**; situation flags live
in `SITUATION_FEATURES`/`PHASE16_FEATURES`, mined only by the Phase-16 steps. The Phase-6 drift check
reproduces frozen `DURABILITY` +14.6 exactly — the cost report is untouched.

**16.3 + 16.5 drafted (awaiting review).** `reference/coaches.csv` (playcaller history) and
`reference/situation_events_2026.csv` (2026 moves), both with a `confidence` column. 2026 web data was
**contradictory** (esp. head-coach assignments) → 2026 coaching rows flagged low/VERIFY. **User must
review/correct `coaches.csv` before 16.4 (scheme fingerprint) consumes it.**

**Bottom line.** The value-side situation track is an **honest null** — consensus efficiently prices
offseason situation changes for value. Phase 16's real edge is the **availability (draft-drift)** side
(16.7–16.12), not value alpha. Reinforces the reframe: *don't fight the sharp market.*

### 16.3 review loop — the 2026 coaching table, SIGNED OFF (2026-07-24, same session, later)

**Outcome: the 2026 half of 16.3 is ☑ DONE at `confidence=high`.** User took the Claude draft through
**three correction rounds**; the signed-off artifact is preserved verbatim at
`reference/coaches_2026_signed_off_2026-07-24.csv` (32 rows, all 32 teams). Merge into
`reference/coaches.csv` is the **first action of the next session** (transform spec in `BUILD_PLAN.md` 16.3).

**What the review process actually caught.** The Claude draft was structurally sound but factually
unreliable — a useful calibration on the "Claude-drafts / user-reviews" contract this substep was designed
around. Errors found by **cross-referencing rows against each other** (no external source needed):
- **4 hard internal contradictions.** HOU said Slowik left for "Miami's **head coaching** job" while MIA
  listed Hafley as HC and Slowik as OC · HOU flagged Caley `in_house=1` while JAX said Udinski was
  "replacing Nick Caley" · BAL said Doyle was "**promoted**" while CHI said he left Chicago · LV had Kubiak
  leaving Seattle while SEA said "**Ryan Grubb** departs" (a year stale).
- **3 notes incoherent on their face** — DAL *"Klayton Adams replaces Klayton Adams?"* (literal question
  mark), IND *"replacing Jim Bob Cooter with Jim Cooter"* (same person), HOU (above).
- **2 rows stale by a full hiring cycle** — NE *"Vrabel replaces Jerod Mayo"* (a 2025 hire) and NYJ
  *"Glenn replaces Robert Saleh"* (Glenn hired 2025; Saleh fired Oct **2024**, Ulbrich finished that year).
- **Method note:** the highest-yield check was **not** fact-checking individual cells but **building the
  move graph** — every "X departs" in one row must match an "X arrives" in another. That found every
  contradiction above with zero external lookups. Worth reusing for 16.3b and any future curated table.

**★ KEY FINDING — `in_house` semantics, reverse-engineered and verified 32/32.** The user's file replaced
the draft's `change_from_prev` with a new `in_house` column and never defined it. Testing candidate readings
against all 32 rows, **exactly one is self-consistent**: *"the season's play-caller was already on this
team's staff the previous season."* It holds **32/32** on the final file. Two consequences:
- **`in_house=0` ⇒ a new playcaller regime ⇒ a 16.4 transport event.** The 2026 event set is therefore
  **13 of 32 teams** (19 continuity) — that is what 16.4 transports onto.
- **It is NOT equivalent to the dropped `change_from_prev`.** `DEN 2026` is `in_house=1` *and* a genuinely
  new regime (Payton hands the offense to Davis Webb, already the QB coach); PHI/WAS are the same shape.
  So `in_house=0` is **sufficient but not necessary** for "new scheme." User chose to drop
  `change_from_prev` anyway (schema simplicity) — **16.4 must therefore handle the internal-promotion
  regime-change cases explicitly rather than keying purely on `in_house=0`.**
- Two false positives in my own checker are recorded so they aren't re-flagged: **BUF/KC/NE** notes describe
  an incoming *coordinator* while the *play-caller* is Brady/Reid/McDaniels (all in-house — flag correct);
  **ARI** "LaFleur **retains** play-calling" means he kept the duties from Hackett, not that he was already
  on staff (he came from LAR — `in_house=0` correct).

**Signed off with three unverified aggregates, recorded deliberately** (internal consistency ≠ factual
accuracy): **10 new head coaches** for 2026 (2025 had 7; 2022 hit ~10) · **McDaniel leaving the MIA HC job
to coordinate at LAC** · **56 % of HCs calling plays** (18/32 vs a ~40–50 % norm). These are the boundary of
what was checked — no external source was consulted for any of them.

**16.3b opened — the real 16.4 blocker.** The signed-off file is **2026-only**, but 16.4 fingerprints a
playcaller from their **past** regimes. **23 of 32 incoming 2026 playcallers have no historical row**, and
the 9 that do average ~1 season. **User chose the full historical build.** Enabling find: `pbp.home_coach`/
`away_coach` gives a free, exact, PIT **head-coach**-per-team-season table for **all 352 team-seasons
2014–2025** — insufficient alone (HC ≠ playcaller, as Phase-16 scoping already established) but a valid
**scaffold** that cuts the research down to the OC/playcaller column only.

**Stage-0 chore run this session** (crossed the >6-day threshold): FFC 2026 snapshot banked **2026-07-24**
(6 configs, 1,202 rows, gsis 99.3 %, `adp_asof` PIT gate clean) → `stage0_adp_snapshot: PASS`; then
`steps/backup_db.py` copied the 2026 ADP series + 2025 backfill + a timestamped `.duckdb` to
`/mnt/c/Users/rayha/fantasy-quant-backup/`, all checksums verified.

### 16.3 merge + 16.3b historical playcaller regimes — DONE (2026-07-25), awaiting user review

**Scope.** The two actions the ★★ pointer put first: merge the signed-off 2026 coaching table into
`reference/coaches.csv` on the frozen schema, then build the **historical** half 16.4 needs. Plus a
re-verification of the 16.5 event board. New package `src/fantasy_quant/situation/` (created at its
phase, per CLAUDE.md §5) with `coaches.py`; done-bar `steps/phase16_3b_coach_history.py`; 10 new tests
(**326 total**, was 316), ruff clean. **DEV-only, lockbox untouched, still walled off from the frozen
cost report** — nothing here is imported by the optimizer, the value board or the cost report.

**The table.** `reference/coaches.csv` is now **189 rows** on the frozen schema
(`season,team,head_coach,offensive_coordinator,play_caller,hc_calls_plays,in_house,confidence,notes`):
157 historical (2014–2025) + the 32 signed-off 2026 rows. `change_from_prev` is dropped; `in_house` is
backfilled on every historical row. Confidence: **167 high / 21 med / 1 low**.

**★ The head-coach scaffold turned out to be an AUDIT, not just a labour saver.** `pbp.home_coach`/
`away_coach` gives an exact head coach for all **384** team-seasons 2014–2025 (the pointer said 352 —
that was 11 seasons; 12 × 32 = 384). The intended use was to save research. The larger value is that it
**checks every researched row for free**: a row whose `head_coach` disagrees with pbp is almost always a
row about the wrong regime. Result: **157 auditable rows, 0 MISMATCH**, one legitimate `split_season`
(2018 CLE — Kitchens called plays for Gregg Williams' interim half, so the correct head coach is Williams,
not Jackson). That reduces the user's review to the `offensive_coordinator` / `play_caller` /
`hc_calls_plays` columns, which is where the judgement actually lives.

**⚠ Data limitation found (2026-07-25): pbp's coach field is game-level only through 2023.** 19 of the
2014–2023 team-seasons show two coaches; **from 2024 it is a season-level coach of record** — Dennis Allen
appears for all 17 of NO 2024 and Brian Daboll for all 17 of NYG 2025, though both were fired in-season.
So the scaffold's `interim` column is a **lower bound** on mid-season changes and must not be read as
"nobody was fired in 2024–25". It is still exactly sufficient for the audit (identity of the franchise-
season's head coach), which is all we use it for.

**Research method + inclusion rule.** Drafted from knowledge, then **web-verified** name by name
(Wikipedia career tables + contemporaneous reporting), then run through the move-graph cross-reference.
A season is included only if the named person called plays for the **majority** of the team's games;
excluded partial seasons are documented in an adjacent row's `notes` (McDaniels LV 2023 — fired after 8
of 17; Kubiak DEN 2022 — took over 20 Nov; Brady BUF 2023 — interim from mid-November; Schottenheimer JAX
2021 — final four games).

**★ Verification overturned five drafts that "sounded right".** This is the payoff for not trusting recall:
- **Todd Monken's pre-Baltimore OC stints were NOT play-calling** — Koetter kept the calls at TB 2016–18
  and Kitchens at CLE 2019. His only fingerprint-able regime is **BAL 2023–25**.
- **Brian Schottenheimer did not call plays as Dallas's OC** (2023–24) — McCarthy did. Those seasons are
  *McCarthy* regimes; Schottenheimer's are SEA 2018–20 and DAL 2025 as head coach.
- **Shane Steichen's Chargers years are 2019 (interim, from 30 Oct) + 2020**, not 2020–21; 2021–22 are PHI.
- **Brian Daboll called the Giants' plays in exactly one season, 2024** — Kafka called 2022, 2023 and 2025.
- **Kevin Stefanski's Cleveland spell has a real hole at 2024** (Ken Dorsey took the calls in Week 8 and
  kept them); Stefanski resumed in 2025. Likewise **McCarthy's Green Bay spell has a real hole at 2015**
  (Tom Clements). Both are genuine exclusions, not missing rows.

**★ The 2026 transport set is 17 teams, not 13** — and finding that required a scope correction mid-build.
`in_house=0` yields 13, but the frozen semantics make it *sufficient, not necessary*: an internal promotion
is `in_house=1` and still a new regime. `new_regimes()` detects those **structurally** (the table's own
previous-season row names a different play-caller) rather than trusting the flag — but that only works if
the prior season is *in* the table, and only 21 of 32 teams had a 2025 row. Completing 2025 for the missing
11 (cross-validated against ESPN's 32-play-caller survey, which independently confirmed all 21 rows already
present) lifts the set to **13 external + 4 internal promotions = 17**: the DEN (Payton→Webb), PHI
(Patullo→Mannion) and WAS (Kingsbury→Blough) cases CLAUDE.md warned about, **plus MIA** (Slowik was already
on Miami's staff in 2025), which nobody had flagged. Lesson: a flag that encodes "sufficient but not
necessary" must be paired with a structural check, and the structural check needs a complete predecessor.

**★ The honest coverage answer — some 2026 play-callers cannot be fingerprinted at all.** 16.4 coverage
went from 9/32 play-callers with ~1 season each to **27/32 with a median of 4 prior seasons** (68 regimes
over 157 team-seasons, 43 distinct play-callers). **12 of the 17 transport teams are fingerprint-able**
(ARI, ATL, CLE, DET, LAC, LV, MIA, NYG, NYJ, PIT, TB, TEN). The other **5 — BAL, DEN, PHI, SEA, WAS — have
genuinely FIRST-TIME play-callers** (Declan Doyle, Davis Webb, Sean Mannion, Brian Fleury, David Blough),
each verified individually. No amount of research creates a regime for them, so 16.3b's done-bar is *not*
"every play-caller has history" — it is "the table is right, and the five who have none are known and
labelled." 16.4 must transport for 12 and say *nothing* for 5 rather than inventing a prior.

**Move-graph cross-reference, second outing.** Re-run on the merged table it produced **12 findings, 0 HARD**:
10 `note:` internal promotions (all explainable, and they are what the transport-set correction above is
built on) and 2 `check:` one-season holes (Stefanski/CLE 2024, McCarthy/GB 2015 — both real, both documented
in `notes`). The check was sharpened this session to distinguish `HARD:` (a self-contradiction), `check:`
(must be explained) and `note:` (expected), and to stop flagging multi-year absences — a coach leaving and
returning years later (McDaniels at NE) is ordinary, a one-season hole is not.

**16.5 re-verified (2026-07-25) — three real errors in a 9-row board.** Michael Pittman Jr.'s destination
was `UNKNOWN`; he was **traded IND→PIT**. David Montgomery was typed `free_agent`; it was a **trade** (DET→HOU
for Juice Scruggs + a 2026 4th + a 2027 7th). **Jordan Mason SF→MIN is not a 2026 event at all** — that trade
closed **16 March 2025**, so the row was stale, and the Aaron Jones row that depended on it rested on a stale
premise. Removed the Mason row (documented in the file header so the diff is reviewable), downgraded Jones,
resolved Pittman, corrected Montgomery, raised the four confirmed moves to `high`, added **Kyler Murray
ARI→MIN** (surfaced during verification; a new-starting-QB event for the Minnesota pass catchers), and left
**Tyler Allgeier ATL→ARI** at `low` because no 2026 source re-confirmed it.

**★ LINEAGE FALLBACK — the user overrode "16.4 says nothing" (2026-07-25, same session).** Reviewing the
above, the user pushed back on leaving five teams blank: a first-time play-caller should fall back to the
previous year's situation as a baseline and assume broad continuity — *"Declan Doyle served as OC under the
Bears and Ben Johnson, so we can expect his offensive schemes to be functionally similar to the Bears last
year."* That is a better answer than silence, and it turned out to be **fully achievable**: all five
first-time play-callers trace to a mentor who is (or could be made) a play-caller in the table.
- **New `reference/coach_lineage.csv`** (5 rows): Doyle→**Ben Johnson** (CHI 2025, OC while Johnson called),
  Webb→**Sean Payton** (DEN 2023-25, QB coach then pass-game coordinator), Mannion→**Matt LaFleur** (GB
  2024-25), Fleury→**Kyle Shanahan** (SF 2019-25, seven years inside the system), Blough→**Kliff Kingsbury**
  (WAS 2024-25). The table names a **person, not a scheme** — 16.4 looks the mentor up in `coaches.csv` and
  fingerprints their regimes, and a gate asserts every mentor is itself a play-caller there.
- **Two mentors had to be added to `coaches.csv` to make their mentees fingerprint-able:** **Sean Payton**
  (NO 2014-2021 + DEN 2023-2024; DEN 2025 already present) and **Kliff Kingsbury** (ARI 2019-2022 + WAS
  2024). +15 rows → **204 total** (172 historical), 70 regimes. Payton's addition also produced a satisfying
  self-check: the legacy 2022 NO row (Carmichael, `in_house=1`) now reads as an internal promotion off
  Payton's 2021 regime, exactly as it should.
- **`fingerprint_source(df, season)`** resolves `own` → `lineage` → `none` per team and is the single API
  16.4 should consume. **Result: 12 own · 5 lineage · 0 none — all 17 transport teams covered**, up from 12.
- **★ The genuinely interesting part: lineage and team continuity do not always agree.** `same_team` marks
  where they coincide — **DEN** (Payton hands his own QB coach the offense) and **WAS** (Blough promoted over
  Kingsbury) are same-building promotions, the strongest form of the fallback. But at **BAL** (lineage Ben
  Johnson vs 2025 continuity Todd Monken), **PHI** (Matt LaFleur vs Kevin Patullo) and **SEA** (Kyle Shanahan
  vs Klint Kubiak) the two priors point at different schemes. 16.4 must **report both** rather than pick
  silently; the step prints an explicit `NB` line for each. SEA is the mild case — Kubiak is from the same
  wide-zone family as Shanahan, so the two readings nearly agree anyway.

**★ 16.5 REBUILT AS DERIVED — the user asked "9 rows? I anticipated a much larger comprehensive csv", and
was right (2026-07-25, same session).** The answer was not to research harder; it was that
**hand-research was the wrong method for this file**, and the evidence is measurable. Diffing the 2026
ADP board against 2025 `weekly` shows the 9-row researched board **missed 16 of the 23 team changes among
draftable skill players** — including **A.J. Brown PHI→NE at ADP 13.6**, a first-round pick — while
carrying Tyler Allgeier at ADP 167. It had no row at all for **the two highest-ADP players in the league**
(Bijan Robinson 1.6, Jahmyr Gibbs 1.8), both of whom have a changed backfield. A tracker recap surfaces
what was *newsworthy*; it is not a frame over the players you actually draft.

Unlike `coaches.csv` — which genuinely has no free source — almost all of this **is** free. Three
warehouse tables pin it down: 2026 `adp_snapshots` (the draftable board *and* current team), 2026
`consensus_projections` (an **independent** second read on team), 2025 `weekly` (prior team + workload).
New `src/fantasy_quant/situation/events.py` + `steps/phase16_5_situation_events.py` generate the board;
**138 events over 30 teams**, one row per affected draftable player, and the human contribution narrows
to what no feed carries.
- **Dual-sourced with zero slack:** ADP-board team vs projections team agreed on **all 183** shared skill
  players; `events.board()` raises rather than picking a side.
- **The board's `team` column is safe here and only here.** `adp/panel.py` documents it as unusable
  historically (backfilled boards carry an end-of-season crosswalk — the Sep-1 2022 board lists McCaffrey
  on SF, a trade not yet made at draft time). That contamination is **retroactive**: a snapshot of a
  season not yet played cannot encode a trade not yet made. Worth stating explicitly, because the two
  facts look contradictory until you notice the direction of time.
- **Four event types, strongest wins:** `team_change` (24) · `new_to_league` (19) · `room_change` (59,
  stayed put but a same-position draftable player arrived or left) · `context_only` (36, only the
  play-caller and/or QB changed). Departures include 2025 producers (≥100 car+tgt+att) who left the
  draftable pool entirely — a retirement vacates opportunity exactly like a trade does.
- **A new starting QB is an offense-wide event same-position churn cannot see.** `new_qb_map` fires on 9
  teams. Two deliberate calls: a team with **no** QB anywhere on the ADP board maps to `(unsettled)` and
  **counts as changed** (ARI, ATL, CLE, NYJ, PIT) — those are the *least* settled rooms in the league, so
  defaulting them to "no change" is backwards; and the prior-season baseline stays the attempts leader to
  match `adp/panel._starting_qb`, which produces a **known false positive** when an incumbent missed time
  and a backup led attempts (WAS: Jayden Daniels against a Marcus Mariota baseline). Left visible in the
  file rather than silently patched.
- **Research is not discarded, it is merged.** `merge_annotations` overlays the 8 surviving hand-verified
  rows' `mechanism`/`notes`/`confidence` onto the derived rows (`evidence=derived+web`) — the derivation
  owns *who/where*, research owns *how*. An annotation matching no derived row is returned as an orphan
  and must be explained, never dropped.
- **A quiet cross-validation:** **Aaron Jones Sr.** falls out as an orphan — no team change, no MIN
  RB-room churn. The derivation independently reached the same "not a 2026 event" conclusion the manual
  re-verification had, whose premise (a timeshare with Jordan Mason) rested on a trade that closed 16 Mar
  2025. Recorded in the step's `WITHDRAWN` dict.

**Status: 16.3 ☑ · 16.3b ☑ (built, gated, self-consistent, lineage fallback wired) · 16.5 ☑ (derived,
138 events; `mechanism` still unresearched on 111 rows). 344 tests, ruff clean. ★ REVIEW GATE — the
historical coaching rows and the lineage table are Claude-researched and 16.4 must not consume them until
the user signs off**, the same contract as the 2026 half. 16.5's derived columns are machine-checked, so
its review surface is only `mechanism`/`confidence`/`notes`.

### 16.4 — scheme fingerprints + transport — DONE (2026-07-25), **descriptive only**

The review gate closed first: the user fact-checked the historical table and lifted the 26 non-`high`
rows, so `reference/coaches.csv` is **204 rows, all `confidence=high`** and signed off end to end. The
edits were confidence-only — no `head_coach`/`offensive_coordinator`/`play_caller`/`hc_calls_plays` value
moved — so the 16.3b machine audits (pbp head-coach 0 MISMATCH, move-graph 0 HARD) carry over untouched.

**Decisions locked before building** (the user reversed an initial DEV-cap answer, on the record): no
season cap — fingerprints use **all 2014–2025 seasons on file**, lockbox years included, with **no
provenance column**; EB shrinkage toward the league-season baseline; partial regimes cut to the weeks
actually called; the BUILD_PLAN metric set **extended with concentration (HHI), aDOT and pace**; output at
**both team and player grain**; role-share deltas **plus a unitless implied multiplier**, no points column.

**What it is.** `situation/fingerprint.py` + `steps/phase16_4_fingerprint.py` +
`analysis/phase16_4_fingerprint.json`. 14 metrics per team-season, **z-scored within season** so that
league drift in pass rate and pace never reads as a coach's personality, aggregated per play-caller and
**EB-shrunk** by regime length (`k = σ²/τ²` by method of moments, so the weight is estimated, not chosen).
**41 play-callers / 64 play-caller×team spells over 169 regime-seasons**; all **17** transport teams
resolve (12 own · 5 lineage · **0 silent**), and **BAL/PHI/SEA** carry two priors side by side (mentor
lineage vs. the outgoing caller) rather than a silent pick.

- **★ THE HEADLINE, and it is a deflationary one: only 20.9 % of the implied role-share movement is the
  incoming coach.** The other **79.1 %** is the incumbent slot regressing toward the league mean — which
  *any* hire whatsoever would produce. Mean |reversion| **5.77 pp** vs mean |scheme| **1.53 pp**. The
  player board therefore splits every move into `reversion_pp` and `scheme_pp` and the step prints the
  ratio; publishing only the total `delta_pp` would have overstated the phase by roughly 5×. This is the
  same shape of result as the value-side 16.1/16.2 null — situation change is a smaller lever than the
  narrative around it, and the honest deliverable says so.
- **★ Trait stability is the actually useful output.** The EB constant *is* the finding — it measures how
  much of a trait a coach carries between jobs. Most portable: **`rz_pass_rate` (k=1.7)**, `wr2_tgt_share`
  (1.7), `rb_tgt_share` (1.8), `team_adot` (1.8), `plays_pg` (1.8), **`carry_hhi` (2.0)**. Least portable
  by a wide margin: **`wr1_tgt_share` (k=17.9, max weight 0.40)** — the alpha receiver's target share is a
  **roster** fact, not a scheme fact. Adding the concentration measures paid for itself: backfield
  concentration (bellcow vs committee) is both the most fantasy-relevant thing a play-caller does and one
  of the most portable, while the headline "target share" everyone quotes is the least.
- **Partial regimes cut to their own games.** Six seasons carry a pinnable window (`PARTIAL_WEEKS`, e.g.
  Nagy CHI 2020 = first 9, Reich IND 2022 = first 9, Reich CAR 2023 = weeks 1–6); three are flagged but
  too vague to pin (`UNRESOLVED_PARTIAL` — Brady CAR 2021's "~13 of 17", Morton DET 2025, Kelly LV 2025)
  and are **dropped rather than guessed**. Specs resolve against weeks the team *actually played*, so a
  bye never shifts a boundary. NB the IND window is keyed to **2022** — the note documenting it sits on
  the 2021 row, which was itself a full season.
- **★ A silent join failure nearly deleted a coach.** `pbp`/`weekly` write the Rams as `LA`;
  `reference/coaches.csv` writes `LAR`. The first run dropped **Sean McVay's entire nine-season tenure**
  and reported it as an ordinary empty result — a missing coach and a failed join look identical. Fixed by
  reusing `adp.panel._canon_team` (rather than a local map) and locked down by
  `assert_regime_coverage`, which makes *a drop without a stated reason* an error. Generalizable: any
  cross-source join in this repo should go through the canonical mapper, and "no rows" must never be an
  acceptable silent outcome.
- **Reconciliation, not reinvention.** 16.4 re-derives tendencies at **week** grain (3.4 is season-grain
  and cannot express a partial regime), so a unit test asserts an unrestricted team-season reproduces
  `features/environment.py`'s `pass_rate`/`early_down_pass_rate`/`plays_pg` exactly on an in-memory DB.
- **Labeling.** No FDR gate, no baseline, no edge claim — the clean-transport sample is far too thin, and
  BUILD_PLAN scopes 16.4 this way deliberately. The done-bar is "computes correctly and is honestly
  labeled". Walled off: reads `pbp`/`weekly`/`adp_snapshots`, writes nothing, and touches neither
  `draft/optimizer.py` nor `valuation/value_board.py` nor `valuation/cost_report.py`.

**Status: SESSION E COMPLETE — 16.1 ☑(null) · 16.2 ☑(null) · 16.3 ☑ · 16.3b ☑ · 16.4 ☑(descriptive) ·
16.5 ☑(derived) · T10 ☑. 16.6 tab deferred to the Phase-14 app block.** 359 tests (+15), ruff clean; DEV-only,
lockbox untouched, walled off from the frozen cost report. **The value-side track closes as an honest
null with one genuinely useful by-product: a measured ranking of which offensive traits a play-caller
actually carries between jobs.**

---

## Session F — data 0.11 (ECR) + availability drift 16.7–16.8 *(2026-07-25)*

**Headline: the availability side returns an honest null too — but a textured one, and the route to it
produced two data findings worth more than the model.** 382 tests (+23), ruff clean. DEV + lockbox
seasons both used (availability track is outside the frozen value stack, user decision 2026-07-25);
nothing model-side changed.

### 0.11 — the FantasyPros ECR archive exists, and is unusable for the thing it was scoped for
- **The archive is real.** `?year=YYYY` on the cheatsheet pages genuinely serves that season's board —
  2020 → McCaffrey/Barkley/Elliott, 2018 → Gurley/Johnson/Brown. Ingested **17,264 rows, 2017–2026 ×
  {ppr, half-ppr, standard}**, 99.2 % gsis match on the top-150 skill players. It carries what we never
  stored: consensus **rank**, the experts' **disagreement** (`ecr_std`, min/max over 90–243 experts),
  tier, and ECR delta. `projections/consensus.py` keeps FantasyPros *points*, not rank.
- **★ But every archived board is a single END-OF-PRESEASON snapshot**, stamped 9/06–9/11 — i.e. at
  kickoff, *after* the drafts it would explain. Measured on the 16.7 corpus: **1 of 38** preseason drafts
  starts on or after its own season's ECR stamp. So BUILD_PLAN §0.11's stated validation ("does true-ECR
  beat the VBD-proxy on drift MAE?") **cannot be answered**, and 16.8 keeps the VBD-gap proxy. This is a
  property of the archive's grain, not of the scrape.
- The guard is **structural, not advisory**: `ecr_asof` refuses a board dated after the caller's as-of, so
  a draft-day as-of returns an **empty frame** rather than a quietly future-dated board. Asserted for all
  9 historical seasons in the done-bar.
- Banked anyway because it is free, vendor-deletable, and genuinely PIT-clean for anything scored on the
  **season outcome** (a ~Sep-7 board precedes Week 1) — a real expert baseline for the Phase-6/16.1 value
  work, and the live-2026 input for 16.10/16.11. **It also covers 2025, where FFC has no board at all.**
- **⚠ One board is not preseason at all: 2023 PPR carries `as_of = 2024-02-12`** — re-touched after the
  Super Bowl, so it saw the season it is supposed to precede. Flagged per-row as `is_preseason=False`
  rather than silently mixed in; the step fails only if the archive changes shape systemically (<90 %).
- **Underdog ADP deferred, not attempted** (user decision): no keyless endpoint — the marketing routes
  404 and the board is a JS app on an unpublished API. Recorded so the next session does not re-discover it.

### 16.7 — the drift panel, and why it is thin
- **★ The Sleeper corpus is not a preseason corpus.** Draft start times run from **February to November**.
  A February dynasty startup or a November in-season draft measured against a September ADP board is not
  drift, it is a different market. `PRESEASON_WINDOW` (Aug 1 – Sep 15) is the single biggest filter, and
  BUILD_PLAN did not have it. Funnel: **117 human complete drafts → 42 in-window snake redraft → 34 with
  an FFC board** = 4,495 boarded picks, 436 players, 8 seasons (2017–2024). The 8 eligible 2025 drafts drop
  because **FFC publishes no 2025 board** — confirmed against the live API (`"No ADP data found."`).
- **Units are rounds, not picks** (`pick_no / teams`, `adp / board_teams`), which is what lets 6-, 8-, 14-
  and 16-team rooms join a 10/12-team board instead of being discarded (+7 drafts, ~20 % more picks).
- **Sign convention: `drift > 0` = drafted EARLIER than the board** (a reach). This mirrors the existing
  `sleeper.build_tendencies` `reach`, and is the **negative** of the `actual_slot − ADP` in BUILD_PLAN
  §16.7 — flipped deliberately so "positive = hyped = goes early" reads the same through 16.8–16.12.
- **`drift_centered` is the headline target.** Each room carries its own level offset (board depth vs
  draft depth; K/DST consume slots the offense-only panel never sees), so raw drift hides a draft fixed
  effect. Centering within the draft asks the real question: did this player go early *relative to how
  this room drafted overall*. Raw sd 1.69 rounds → centered 1.54.
- **Face validity is good:** the biggest fallers are **QBs** (Rodgers, Roethlisberger, Rivers — FFC's board
  overstates QB demand vs real 1-QB rooms), and the biggest reaches are hyped rookie pass-catchers
  (Kincaid, Hyatt 2023). Positional means: **TE +0.46 rounds (reached), WR +0.08, RB −0.16, QB −0.20**.

### 16.8 — the verdict: drift does NOT predict
Bar fixed before reading the result: skill > 2 % of baseline MAE with a bootstrap CI clear of zero.

| fit | MAE | baseline | skill | CI | Spearman |
|---|---|---|---|---|---|
| headline (all features) | 1.0494 | 1.0605 | **+1.05 %** | [−1.48 %, +4.96 %] | +0.208 |
| ablation (no `source_divergence`) | 1.0785 | 1.0600 | **−1.75 %** | [−4.10 %, +0.74 %] | +0.084 |

- **★ The ablation is the finding.** Without `source_divergence` the model is *worse than assuming
  everyone goes at ADP*. All apparent skill traces to the one feature built from the target's own sibling
  drafts — and it was **already** computed leave-one-draft-out. Even held out, drafts from the same season
  share rooms, drafters and local ADP quirks, so the honest read is that the headline +1.05 % is residual
  self-prediction, not signal. Had the ablation not been run (user decision to add it), this would have
  been written up as a weak positive.
- **Rank without level.** Spearman +0.21 with skill ≈ 0 means the model orders *who* gets reached better
  than chance while being unable to reduce absolute error — the same shape as the Phase-4.4 finding
  (well-calibrated in rank, wrong in level).
- **The situation flags are null on the availability side too** — `team_changed`, `new_starting_qb` and
  both competition-change flags are insignificant and sign-unstable, exactly as they were on the value
  side in 16.1/16.2. **Situation change is a smaller lever than the narrative around it, measured twice
  now, from two independent directions.**
- **★ What does survive the ablation** (significant + 100 % sign-stable, so this is what 16.9 should shape
  its shock with — as descriptive room behaviour, never a per-player forecast):
  **`rookie` +0.73 rounds** (rooms systematically reach for rookies by three-quarters of a round),
  **`adp_stdev` +0.35/SD** (the crowd's *own disagreement* is the best available reach predictor —
  where the market is unsure, someone jumps), `vbd_gap` +0.18/SD, `adp_rounds` −0.19/SD, `pos_WR` +0.47.
- `days_to_board` is significant in the headline and **not** in the ablation — i.e. the board-vs-draft
  timing artifact was being absorbed by `source_divergence`, which is a further reason to distrust it.

### Carried forward
- **16.9 must not be handed a quantitative drift prediction to amplify.** Its done-bar (reproduce realized
  cross-draft *dispersion*) is a variance match and needs no mean signal — `aggregate_player_season`
  already emits `sd_drift` for it. Shape the shock with `rookie` / `adp_stdev`, not a fitted per-player drift.
- **16.10's curated hype board is now the primary narrative channel**, and its "curated, not a backtested
  claim" label is load-bearing rather than a caveat — the quantitative route was measured and did not clear.
- The panel is genuinely thin (34 drafts, several seasons 1–3 deep). Growing the Sleeper human corpus via
  `reference/sleeper_seeds.txt` → `steps/phase0_10b_crawl.py` is the one thing that would let 16.8 be re-asked.

**Incidental find (pre-existing, not from this session): the data-health report is permanently red.**
`steps/phase0_8_validate.py` ends in `GATES FAILED` on every run — verified it fails identically on a clean
HEAD checkout. The one failing gate is `adp: unique (gsis, season, source, scoring, teams)`, 1,028 offending
groups, **all season 2026 and all explained by the Stage-0 weekly snapshot series** (0 groups have more rows
than distinct `snapshot_date`s, i.e. no genuine duplicates). The gate's key predates Stage 0 and needs
`snapshot_date` in it. Logged as **TECH-DEBT T12** and deliberately *not* fixed here: it is a frozen-data-layer
validation rule, not part of the walled-off Phase-16 track, and quietly editing a gate mid-session is the
behaviour the discipline exists to prevent. Worth fixing soon — an always-red validator cannot warn anyone.

---

## Session F.5 — corpus expansion (2026-07-25): the crawl was un-reseeded, not exhausted

**Scope, agreed up front:** grow the Sleeper corpus and verify what it bought. Deliberately **not** in
scope: re-asking 16.8, re-fitting Phase 11, personalities, S6 adaptive, the 2025 dress rehearsal. Those
depend on knowing what the crawl produced, which is what this session measures. **395 tests** (was 382),
ruff clean, all data-health gates **PASS**.

### What the corpus did

| | Before | After | × |
|---|---|---|---|
| Human drafts | 149 | **7,699** | 51.7× |
| Bot drafts | 117 | 822 | 7.0× |
| Picks | 17,082 | **1,207,687** | 70.7× |
| Manager profiles | 289 | **24,696** | 85× |
| Seasons | 2017–2020 | 2017–2026 | — |

367 managers walked, 8,207 leagues expanded, 10,700 drafts discovered → 8,148 ingested / 2,552 dead,
**70 minutes** wall clock, queue fully drained, no early stop.

### ★ The 16.7 funnel — the actual deliverable

| Stage | Before | After | × |
|---|---|---|---|
| Human complete | 132 | 7,619 | 57.7× |
| Eligible (redraft · snake · preseason window) | 42 | 1,426 | 34× |
| **With board → the panel** | **34** | **1,144** | **33.6×** |
| Panel rows (picks) | 4,495 | 157,349 | 35× |
| Distinct players | 436 | 490 | 1.1× |
| `sd_drift` | 1.691 | 2.086 | — |
| **`drift_centered_sd`** (16.9's target) | 1.5375 | **1.8161** | — |

All 16.7 checks PASS. **2025 still drops entirely** — 278 eligible drafts with no FFC board. ECR covers
every season 2017–2026 and remains the candidate fallback (an F.6 decision, not taken here).

Note `n_players` barely moved (436 → 490) while drafts grew 34×: the panel is bounded by the *board*, not
the corpus. What grew is **observations per player**, which is exactly what a dispersion target needs.

### ★ Why the old crawl stalled at 266 drafts — three mechanical defects, none methodological

1. **The frontier was never fed back in.** `load_seeds()` reads only `reference/sleeper_seeds.txt` (3
   draft ids, 2 league ids). The 289 managers the crawl *discovered* live in `sleeper_manager_profiles`
   and were never used as seeds, so every re-run re-walked the same tiny neighbourhood.
2. **Participant expansion dead-ended on re-runs.** `crawl_expand` queued a draft's co-managers only when
   the id was *new* — but `crawl_and_ingest` pre-seeds `existing_ids` with the entire store, so every
   already-ingested draft reported "not new" and its participants were never queued. Expansion is now
   keyed on *"have we expanded this draft"*. A regression test fails on the old condition and passes on
   the new one (verified by temporarily reverting the fix, not by inspection).
3. **The budget was denominated in attempts, not successes.** `MAX_DRAFTS=500` counted *discovered* ids;
   **263 of that 500** never resolved, so over half the budget bought nothing and every re-run re-bought
   the same nothing. Dead ids are now retired in `sleeper_crawl_queue`.

**The general lesson:** all three failure modes look identical from outside — *the crawl returns nothing
new, so the graph must be exhausted*. It wasn't. Before concluding a data source is tapped out, check
that the crawler can still reach past what it has already stored.

### ★ The league cache — a 5.4× speedup, and why the smoke test earned its keep

A 3-manager smoke test measured **26 s/manager**, which projected to ~4 hours against my ~1 hr estimate.
The cause: `discover_draft_ids` calls `/league/<id>/drafts` per league per user, but a manager frontier is
*built out of shared leagues* — co-managers re-request the same league once each. A run-scoped
`seen_leagues` set (persisted to `sleeper_crawl_leagues`) took discovery to **4.8 s/manager**.

*When a graph is crawled from its nodes but its cost lives on its edges, dedupe the edges* — and the more
connected the corpus, the bigger the win, which is the same property that makes the corpus worth having.

**Pacing:** the old flat `time.sleep(0.05)` measured **29 calls/s** — *above* Sleeper's documented
~1000/min — because a fixed nap adds to response latency rather than absorbing it. Replaced with a
token-bucket limiter at a deliberate 10/s, plus hard 429 backoff.

### ★★ Format contamination — a hardcoded label that became a bug at scale

The crawl turned a passing gate red: `ADP top-150 gsis match` failed at **3.5 %** unmatched. The
crosswalk was fine; the **population** was wrong. `_refresh_board` hardcoded `scoring="ppr"`, so every
complete human snake draft landed on a single board labelled PPR redraft — and at frontier scale only
**1,312 of 7,399** such drafts actually are PPR redraft, against 2,547 dynasty_2qb, 952 2qb, 861 dynasty
and 610 IDP. The board was **82 % contaminated**, and the IDP rooms were pushing DB/DL/LB players onto a
board that is supposed to be offensive redraft.

Boards are now **redraft-only and split per (season, scoring)**, labelled in FFC's vocabulary so
`adp_asof` reads both sources interchangeably: `sleeper_human` = 7,129 ppr · 3,197 half-ppr · 2,247
standard. Unmatched rate fell **3.52 % → 0.61 %** and the data-health report is **green for the first
time** (T12 also closed this session).

**This is the finding to carry forward.** The same code was harmless at 149 drafts and seriously wrong at
7,699 — nothing changed but the input distribution. *A hardcoded label is a bug that scales with your
corpus.* Re-audit derived artifacts after any step change in input volume, not only after code changes.
And note the detector: a join-rate gate on a derived artifact is a cheap canary for "the wrong rows are
in here."

### Banked for Phase 17 (per the ingest-and-bank decision)

Nothing is filtered at ingest, so the non-redraft corpus is now real data rather than a future crawl:
**dynasty_2qb 2,607 · 2qb 1,021 · dynasty 861 · idp 610 · dynasty_ppr 396 · dynasty_half_ppr 160 ·
dynasty_std 20 · idp_1qb 18 = 5,693 complete human drafts.** Phase 17 (superflex/keeper/custom scoring)
would otherwise have paid these 70 minutes again.

### What this unblocks (for F.6 — measured, not yet acted on)

- **Phase 11.2 availability Brier (T8b)** was the thinnest result in the repo — `n_drafts: 21`. The
  binding constraint was repeated managers; there are now **12,578 managers with ≥2 drafts and 1,330 with
  10+**. This is the largest proportional firming available.
- **Phase 11.1** goes from 7,900 choice groups toward ~200k, which is the regime where per-manager random
  effects become viable — a modelling decision, not a re-run.
- **16.8** can be re-asked against a ~5.8× tighter CI (√(1144/34)). The pre-registered **>2 % skill bar
  stands unmoved** and the `source_divergence` ablation remains mandatory; with thousands of independent
  leagues the shared-room contamination that ablation exposed is genuinely diluted for the first time.
- **The frozen 2023+2024 lockbox is untouched** — verified three ways: `lockbox_eval.py` routes
  `--which lockbox` to `source="ffc"`/`_board_ffc`, its seats use `_noisy_adp_pick` (ADP+noise, not the
  behavioral model), and `cost_validation.py` likewise. Only `--which dress` (2025) reads `sleeper_human`.
  Growing the corpus **cannot** contaminate the spent lockbox or the frozen value stack.

## Session F.6 — the re-derivation sweep (2026-07-26): a contaminated corpus invents effects

Session F.5 grew the Sleeper corpus 52× and deliberately re-derived nothing. This session ran the
sweep. **411 tests** (was 395), ruff clean, all data-health gates PASS. DEV-only; the spent
2023+2024 lockbox is untouched.

### ★★ The finding: the behavioral path had the F.5 contamination bug too — and it was worse there

F.5 fixed format contamination on the **ADP board** path (`REDRAFT_SCORING`, snake, complete). The
**behavioral** path never got the same treatment: `build_choice_frame` and `availability_brier`
selected on `is_human AND picked_by IS NOT NULL` and scored every draft against a single hardcoded
10-team PPR board. Of 7,699 human drafts, **1,426 are eligible** (complete · snake · redraft
scoring · preseason window); the other 74 % are dynasty, 2QB, IDP, auction or abandoned rooms.

Re-fitting 11.1 on the eligible corpus did not merely sharpen the estimate — **it deleted two
"behavioral findings" that were pure format leakage**:

| coefficient | contaminated | redraft-only | what it really was |
|---|---|---|---|
| `adp_s` | −0.848 | **−1.683** | ADP discipline, halved by rooms that ignore redraft ADP |
| `rookie` | +0.446 | **+0.111** | **dynasty** rooms, where rookie picks are the currency |
| `is_QB` | +0.169 | **−0.028** | **2QB/superflex** rooms, where QBs go early by rule |
| `need` | +0.335 | +0.474 | real, and was being diluted |

The old fit told a story — *managers reach for rookies and quarterbacks* — that was entirely an
artifact of which leagues were in the pool. **A contaminated corpus does not just add noise; it
manufactures plausible, publishable effects.** Noise you can see in a CI. This you cannot.

The walk-forward *improved* on the smaller, cleaner corpus: pooled held-out log-loss gain
**+0.1738** CI[+0.1693,+0.1781] (was +0.1126), Brier gain +0.0177. 70,614 choice groups (was
7,900), 9 seasons including 2025.

### ★ 16.8 re-asked: more data made the LEAK stronger, not the signal

Same pre-registered bar (skill > 2 %, CI clear of 0), same mandatory `source_divergence` ablation,
34× the panel (1,144 FFC-boarded drafts, 157,349 picks):

| | Session F (34 drafts) | Session F.6 (1,144 drafts) |
|---|---|---|
| headline skill | +1.05 % CI[−1.48,+4.96] | **+9.25 % CI[+3.29,+13.91]** |
| ablation (no `source_divergence`) | −1.75 % | **+0.01 % CI[−1.98,+1.84]** |

The headline now clears the bar four times over — **and the ablation is exactly zero.** With
thousands of sibling drafts per season the leave-one-draft-out board estimates each room's own
consensus *better*, so the contaminated feature predicts *better*. F.5 expected the extra data to
dilute the leak; it concentrated it.

**The durable lesson (glossary: "the ablation rule", now with teeth): scale does not launder a
leak — it strengthens it.** A leak-prone feature converges on the target as n grows, so a rising
headline is exactly what a leak looks like from the outside. Only the ablation separates them.

Verdict unchanged in substance: **DOES NOT PREDICT** without the leak-prone feature. 16.9 still
shapes its shock from descriptive room behaviour — the ablation survivors are `rookie` (+0.94
rounds), `adp_stdev` (+0.27/SD), `vbd_gap` (+0.26/SD), `pos_WR`, `pos_TE`.

### ★ 11.2 availability Brier: the thin result was ~2× optimistic

`n_drafts: 21` was **a default argument** (`max_drafts_per_season=3`), not a corpus limit — the
thinnest number in the repo was a parameter nobody re-read. At 28/season:

| | before | after |
|---|---|---|
| windows / drafts | 1,501 / 21 | **36,972 / 252** |
| behavioral Brier | 0.1576 | 0.1978 |
| gain vs best-tuned ADP+noise | +0.1587 | **+0.0864** CI[+0.0769,+0.0980] |

Still beats the best-tuned baseline decisively, but the effect is **half** what 21 drafts implied.
*When a headline rests on a sample size you did not choose deliberately, treat it as an upper
bound.*

### ★ The ECR fallback has to be calibrated, and the first version was not

Adopting ECR as the 2025 board (FFC publishes none) recovers 278 eligible drafts. Used **raw**, it
is not unit-safe: ECR ranks 544–724 players where FFC boards ~200 and compresses ADP (2024 PPR:
ECR rank 396 ↔ FFC ADP 193.5). The first panel run duly reported **Efton Chism at +17.5 rounds**,
every top-10 reach a 2025 fringe name, and a 2025 drift sd of **2.67** against ~1.75 elsewhere.

Fix: isotonic rank→ADP calibration fitted on the overlapping seasons plus truncation at FFC's
median board depth (182). 2025 sd → **1.82**, in line with its siblings, and the reach list becomes
recognisable football (Judkins, Mixon, Robinson). **A fallback source is not a drop-in until its
units are shown to match** — and the tell was distributional, not an error.

The pre-registered 16.8 headline stays FFC-only regardless; ECR is reported as a labelled
sensitivity (+6.06 % headline / −1.15 % ablation — same conclusion).

### ★ Third instance of the hardcoded-label family: board `teams`

`sleeper_human` boards are labelled with the **modal league size** of the drafts that built them —
10 in 2017, 12 from 2019 on, 32 for one thin 2022 cohort. Every consumer asks for `teams=10`
(`draft_date`/`adp_asof` default). So the 2025 dress rehearsal reported *"no ADP board — skipping
season sim"* while a perfectly good 727-player board sat in the table, and the archetype sweep then
died with `KeyError: 'subject'` on an empty frame.

Fixed at harness level (the frozen `walkforward` readers are untouched): look the label up instead
of assuming it. **The 2025 season sim has now run for the first time** — 300 team-seasons, playoff
Brier 0.2325 < 0.240, title Brier 0.0905 vs 0.090 (a marginal miss), points coverage 0.88, level
bias +31.5. The cost sweep is structurally impossible on 2025 (it prices against FFC only) and now
says so instead of crashing.

### Corrections to the F.5 plan's premises

- **Repeat-manager depth was counted on the wrong population.** "12,578 managers with ≥2 drafts,
  1,330 with 10+" counts *all* formats. Within the eligible redraft corpus it is **2,589 with ≥2
  and 111 with ≥10**.
- **Per-manager random effects: not built** (the pre-authorised rule was "extend only if the pooled
  fit leaves signal on the table"). Ablating `mgr_lean` costs +0.0276 log-loss of a +0.1738 total —
  the per-manager channel is ~16 % of the edge and is already carried by a pooled, shrunk feature.
  On 111 deep managers, random effects would be mostly prior.
- **11.1 is fitted on a sampled 60 drafts/season** (~70.6k groups), an explicit budget: the full
  eligible corpus builds an ~8M-row choice frame that does not fit in this box's ~3 GB. The knob is
  reported in `analysis/phase11_opponent_model.json`, not silent.

### S6 adaptive, re-validated on the new β

Both done-bars still PASS and got stronger: adaptive(zero_rb) **+6.6** team-value in the behavioral
room (was +2.0), adaptive(hero_rb) **+19.4 CI[+4.5,+32.9]** (was +15.6, now clear of zero).

### Two new defects found while verifying, both logged not fixed

- **T13 — the Phase-5 distribution cloud is not reproducible across processes.** Same inputs, fresh
  process: per-player `q10`/`q90` differ every run and dress-rehearsal coverage wobbles **75.5 %
  ↔ 76.5 %**. Determinism holds *within* a process and against the global RNG (both tested), so the
  nondeterminism is inside the assembly. **Today's 76.5 % is not an improvement on Session D's
  75.5 % — it is the same number twice.** In the frozen risk layer, so it is documented, not
  patched.
- **T14 — 11.2's bootstrap is O(n_boot × n_drafts × n_windows)** (a linear scan per draft per
  replicate). Cheap at 21 drafts, ~45 min at 252; it dominated a 100-minute step run.

---

## Session G (2026-07-26) — applying the availability drift

### T14, fixed — and the diagnosis it arrived with was wrong

`availability_brier` at an identical call went **396.4 s → 12.7 s (31×)**; at full committed scale
(36,972 windows) **~163 min → ~5.2 min**. Outputs are **bit-identical**, verified against the
pre-fix implementation retained as a test oracle (`_simulate_survival_reference`).

**★ THE DURABLE LESSON — a complexity class is not a profile.** F.6 opened T14 from *reading* the
code: it spotted `np.flatnonzero(draft_of_win == u)` inside a 400-replicate loop, correctly derived
O(n_boot × n_drafts × n_windows), and concluded it "dominated a ~100-minute step run." Measured at
exactly that scale, **the bootstrap runs in 0.79 s — 0.008 % of the run.** The asymptotic reasoning
was sound and the conclusion was still off by four orders of magnitude, because the constant factor
lived somewhere else entirely: `cProfile` put **99.3 % of the time in `simulate_survival`**, and
within it not in arithmetic but in **pandas** — `cand.iloc[ai]` (195 s) and rebuilding the feature
matrix column-by-column in `candidate_utility` (169 s), over ~648 k calls in a *9-draft* sample
(~13 M at full scale). The slow thing was an O(1)-per-pick operation called 13 million times; the
thing that looked slow was an O(n³) scan over arrays small enough not to matter.

*Generalization: when a hot path mixes numpy with pandas row-slicing, the pandas call is the
default suspect regardless of what the loop structure suggests. Profile before opening a
performance ticket — and treat a ticket written without a profile as a hypothesis, not a finding.*

### What was fixed

1. **The real one.** `OpponentModel.candidate_matrix` is split out of `candidate_utility`;
   `simulate_survival` builds **one design matrix per seat context** and indexes rows rather than
   re-deriving every column from pandas at each simulated pick. `pos_run3` — the only column that
   moves within a draw — is overwritten in place. This rests on a **row-wise-columns invariant**
   (`candidate_matrix(board)[rows] == candidate_matrix(board.iloc[rows])`), now asserted by its own
   test so a future cross-row feature (a rank, a share, a within-board z-score) breaks the test
   instead of silently corrupting the hoist.
2. **The prescribed one.** `_draft_blocks` precomputes per-draft index blocks in one stable argsort.
   Kept despite being ~0.008 % of runtime: it removes a real hazard as the corpus grows, and costs
   five lines.

**Bit-identity was a design constraint, not a bonus.** 11.2's committed `brier_gain_vs_best =
+0.0864` is a *reported result*; a refactor that moved probabilities in the last bits would
invalidate it silently. So both changes preserve **RNG call order and summation order** — the same
`X[ai] @ beta` over the same rows, not an algebraically-equal rearrangement. A 460× algebraic
bootstrap (per-draft sums/counts) was measured and **rejected** on exactly this ground: exact in
exact arithmetic, but it consumes the RNG differently, so replicate draws would not match. Trading
comparability of a published number for speed on a 0.79 s component is a bad trade.

**Knock-on:** the 16.9 availability-Brier non-regression gate can now run at full committed scale in
~5 min, so the reduced-sample compromise it was scoped under is only needed during iteration.

### 16.9 — the narrative shock is a NULL; the defect underneath it was a choice-set contract violation

**Verdict: the correlated per-draft shock does not earn its keep** (Phase 16's third consecutive
null, after the 16.1/16.2 value side and 16.8's availability side). What the session actually
found is a real bug in how the fitted opponent model was being *used*, and fixing that met the
level done-bar on its own. `analysis/phase16_9_narrative.json`, 240 simulated drafts matched
one-for-one against realized eligible drafts, 7,792 Brier windows.

**★ The defect: a conditional logit applied outside its choice set.** 11.1 is fit by
`build_choice_frame(top_k=40)` — at each real pick the candidate set is the **top 40 still-available
players by ADP**. Both consumers of that β were simulating against the **entire** board:
`personalities.make_opponent_pick_fn` used the whole cap-respecting pool, and
`availability.simulate_survival` the whole board. A conditional logit's coefficients are only
interpretable *relative to the candidate set they were estimated on*, so this spread pick
probability over players 100+ slots away. Both now read one constant,
`opponent_model.CHOICE_TOP_K`, and a test asserts fit and simulation still agree on it.

| | pooled `drift_centered_sd` | vs realized 1.816 | availability Brier gain |
|---|---|---|---|
| band OFF (pre-Session-G) | 2.897 | **+59.5 %** | +0.0644 CI[+0.0539,+0.0765] |
| band ON (`top_k=40`) | 1.976 | **+8.8 %** | **+0.0708** CI[+0.0609,+0.0823] |

Two independent metrics improve, so this is not a tuning choice. A band sweep is monotone
(k=20→1.33, 30→1.67, 40→1.94, 60→2.33, 120→2.81, ∞→2.89), which is itself the tell: simulated
dispersion was being set almost entirely by an unexamined implementation detail rather than by
anything behavioural.

**★ The premise inverted under measurement.** The phase was opened on the intuition that
independent per-seat sampling washes out clustering, so the simulator must **under**-disperse. It
**over**-dispersed, by 59 %. The mechanism (one shared draw per draft) was right; the deficit it was
built to repair was not there. *Measure the gap before building the thing that closes it* — three
phases in a row now, the intuition named a real phenomenon and the measurement rejected the
direction.

**★ What is genuinely still wrong — the shape, not the level.** Realized cross-draft dispersion
climbs steeply with board depth (Spearman(sd_drift, ADP rounds) = **+0.679**): the consensus top of
the board goes at the same slot in every room while a round-12 flier swings wildly. Simulated, over
the same 1,346 matched player-seasons:

    realized +0.679 | band OFF +0.480 | band ON +0.077 | band ON + shock +0.057

So the band **fixes the level and costs the shape** — and band-OFF looked shape-right for the wrong
reason (an unbounded candidate set lets deep players go anywhere, mimicking depth-dependent
dispersion while inflating total variance by 59 %). Right-shaped and wrong-sized versus right-sized
and wrong-shaped. The band is still correct because it is the *contract*, not because it wins on
this metric.

**★ Why the shock cannot close it, and how we know it is not a tuning failure.** Across a **50×
range of shock sizes** (intercept −5.0 → −1.0) the matched depth slope never moves: +0.246, +0.242,
+0.245, +0.235, +0.249, +0.222, +0.180. Two runs at the *same* intercept on different draft samples
gave +0.249 and +0.057 — **the metric's own sampling noise exceeds the entire effect of the
parameter**, so the calibration is unidentified and its "best intercept = −2.0" is a draw from
noise, not an optimum. Reported as such rather than as a fitted value.

The reason is structural: `top_k` is a **hard rank filter applied before utility**, so no shock of
any size can pull a player into the candidate set. A player at ADP rank 100 simply cannot be taken
until ~60 ahead of him are gone — his slot variance is capped by the band, not by his utility. An
additive utility shock only reshuffles *within* the band.

**★ Where the remaining miss actually lives (→ T15).** Utility is linear in raw ADP
(`adp_s = adp/50`), which makes dispersion roughly uniform *in rank* — exactly the flat profile
observed. Real drafting is sharp at the top (everyone agrees on the top 5) and diffuse at depth.
Closing this needs the *candidate set or the utility curvature* to vary with depth — a soft/widening
band, or log-ADP / rank-based utility — which is an **11.1 respecification**, not a 16.9 knob.
Logged as **T15** rather than attempted here, because it means refitting a validated component.

**Shipping decision:** band **ON by default** (it is the contract, and it improves the two metrics
that matter). Shock **built, wired, tested, default OFF** — the repo's established "kept, not
default" pattern (Phase 7, props, the 13.2 win-tilt, MCTS). It is available for 16.10/16.15, which
need a *channel* to express a curated narrative through, and that channel is now correct even
though the quantitative shock has no measured skill.

---

## Session G (2/2) — 16.10 hype board · 16.11 momentum · 16.12 consumption · 16.16 run detection *(2026-07-26)*

**Headline: Phase 16's availability track closes with a fourth null, and the two channels that ship
are both explicitly unbacktested and default OFF.** 16.16's run detector *works* — it fires
selectively and its discrimination rises monotonically with the firing threshold — but reacting to
it makes the availability forecast monotonically **worse**. The curated hype board (16.10) and the
live momentum series (16.11) do what they are supposed to mechanically, and neither can be
validated even in principle. So the deliverable of this half-session is a set of correctly-wired,
honestly-labelled, off-by-default channels plus a *provable* isolation guarantee for the frozen
stack — not a new edge.

**Built in dependency order, not spec order.** Because the hype-board nomination is derived-first
(user decision), 16.11 is an *input* to 16.10 and was built first.

### 16.11 — live ADP momentum (`adp/momentum.py`, `steps/phase16_11_momentum.py`)

Velocity over the Stage-0 within-season snapshot series, in picks/week, sign-flipped so
`velocity > 0` = drafted earlier (16.7's convention, end to end). All descriptive-honesty gates
PASS. **192 players, 3 FFC snapshots (2026-07-09/18/24) over 15 days.**

Two mechanical corrections, both required:

* **Centering.** The board *deepens* through a preseason (2026 PPR: 201 → 216 → 225 boarded players
  across the three dates), so every ADP creeps later together. Velocity is net of the board's own
  median slope (−0.058 picks/wk), leaving the median player at exactly zero movement — an
  invariant the step now asserts rather than claims.
* **EB shrinkage.** Three snapshots give **one residual degree of freedom** per player. Shrinking
  by each player's own standard error retains **44 %** of the raw spread and behaves correctly:
  Alvin Kamara (se 0.04) keeps −5.21 of −5.21, while Tyjae Spears (se 2.12) falls from +4.15 to
  +2.11. Two-snapshot players have infinite standard error and shrink to exactly zero.

**This is forward-only and structurally unbacktestable** — not for want of effort. FFC publishes one
board per season and 0.11 established the FantasyPros ECR archive is kickoff-dated, so no historical
intra-season ADP series exists anywhere reachable. `momentum_summary` leads with
`backtestable: False` so the label travels with the data.

*Also worth keeping: a raw sort of movers is dominated by kickers (Trey Smack −15.3, Cairo Santos
+22.6), whose ADP is nearly arbitrary between boards. `movers()` filters to skill positions — a hype
readout that shows them is reporting noise with names on it.*

### 16.10 — the curated hype board (`adp/hype_board.py`, `reference/hype_board.csv`)

**24 rows, 20 directional claims, written `reviewed=false`.** All five gates PASS. The review gate
is structural: `load_hype_board` drops unreviewed rows by default, so the shipped board is inert
until you sign it, *independently* of whether the channel is switched on.

**Method: derived rows, curated claims.** 16.5's *derived-vs-curated* rule applied where the answer
genuinely is not in a feed. `nominate()` ranks the live board using the three coefficients that
survived 16.8's ablation (`rookie` +0.73, `adp_stdev` +0.35/SD, `vbd_gap` +0.18/SD) plus 16.11
momentum; the human writes `pick_delta`/`note`/`source`. **16 of 24 rows were machine-nominated**;
the other 8 exist only because research found something no table carries — which is the split
working as intended, and is where the human budget belongs.

**★ Three measurement defects found and fixed, each of which had produced a plausible-looking but
wrong candidate list.** This is the same family as F.5/F.6/16.9: every one presented as a result.

1. **Partial coefficients need their controls.** 16.8's weights were fit with `adp_rounds` and
   position dummies in the model, so they mean "holding depth and position fixed". Used
   unconditionally they rank players by **depth** — ADP standard deviation grows mechanically with
   ADP (0.7 picks at the top of the 2026 board, 33 near the bottom) — and the first run returned an
   ADP-120-to-175 list with nothing from the early rounds. Adding a position control then fixed a
   second, separate flooding: our value board likes *every* TE more than ADP does, which is a real
   value claim about a position and no evidence at all that an individual TE has a narrative.
2. **Nest the functional form.** Controlling on `log(adp)` alone leaked curvature: Bijan Robinson,
   Jahmyr Gibbs and Ja'Marr Chase surfaced as "unusually disputed" purely from misfit, and dropped
   out once `adp` was added alongside. The 1.01 debate is genuinely real (confirmed in the
   research — consensus was Bijan through May, Gibbs ahead by June) but **the derivation was not
   detecting it**, and a plausible output is exactly how that goes unnoticed.
3. **Commensurate units.** The 16.8 weights are in *rounds of drift*; velocity is *rounds per
   week*. Entered directly, momentum was nearly inert and dropped Daniel Jones — the single loudest
   live mover, +5.3 picks/wk, a locked-in starter on a fresh $88M deal — out of the top 45
   entirely. Multiplying by a data-derived horizon (weeks to a nominal Sep-1 draft) makes it rounds;
   it is **capped at ±2 rounds** because linearly extrapolating a three-point slope five weeks
   forward is not a credible forecast.

**★ A fourth: the composite is signed, so ranking by raw score nominates only risers.** Zach
Charbonnet — the strongest claim on the board at −10 picks (placed on the PUP list, out a minimum
four games) — fell off the list entirely. `nominate` now ranks by |score|, which surfaces the real
faders (Alvin Kamara at the momentum floor, Isiah Pacheco, Adonai Mitchell, Baker Mayfield).

**★ What the channel actually buys: elasticity ≈ 0.44 realized picks per claimed pick**
(corr(claim, shift) **+0.72**, sign agreement **94 %** on 18 resolvable claims). ADP is only one
term in the fitted utility and `top_k` is a hard rank filter applied before it, so **a curated row
is a nudge, not a repricing.** `pick_delta` must never be surfaced to a user as a predicted change
in draft slot.

**★ Two measurement traps in the done-bar itself, both of which first reported the mechanism
backwards.**

* **Censoring, not dropping.** Averaging only the slots a player *was* taken at reported that
  hyping Cam Ward (ADP 167.7) pushed him **later**. It did not: it made him get drafted *at all* in
  rooms where he had gone untaken, and every new appearance near the final pick drags a conditional
  mean backwards. Undrafted is now scored `n_picks + 1`, with `draft_rate` reported alongside —
  for a deep player the channel legitimately expresses as *more often drafted* before *earlier*.
* **Crowding-out.** A draft has a fixed number of picks, so hype is zero-sum. Applying all 20
  claims at once made the hyped players compete with each other: a +4 row (Kenyon Sadiq) got drafted
  *less* often while +12 and +8 rows rose. That is correct behaviour and worth knowing for 16.12,
  but it is not what "does this row move this player" asks — so the per-claim gate runs
  **leave-one-in** against a shared baseline.

**★ And a structural one worth carrying: a claim can be below the simulator's resolution.** At the
league-standard 15 rounds (150 picks against a 201-deep board), a +12-pick claim on a board-rank-171
player produced a **bit-identical** 30-draft result, and only moved when the offset was raised ~5×.
At 18 rounds it resolves. *Check the measurement design can contain the effect before concluding
the effect is absent* — and note the consequence for the product: **in a standard 15-round league
several curated rows cannot express at all** (→ T16).

### 16.12 — consumption (`draft/drift.py`, `steps/phase16_12_consumption.py`)

All three consumers wired, plus the fourth thing that actually matters. **All six gates PASS.**

* **(a) realism** — `drift_utility` converts pick-space claims to opponent utility through the
  fitted model's *own* `adp_s` coefficient, so "six picks early" means exactly what it would have
  meant had his ADP been six picks lower, and the units follow automatically if 11.1 is ever refit.
  Measured: **179 players shift >0.5 picks and the hyped rows move +2.90 picks earlier on average** —
  note the ripple is far wider than the 20 claims, because a draft is zero-sum.
* **(b) advice, opt-in** — `RiskModel.hype` shifts effective ADP inside the 9.1/9.4 urgency term,
  so a hyped player prices as likelier to be gone by your next turn (mean survival change **−0.029**,
  max **−0.38**). Worth knowing: **only 3 of 20 claims reprice at all** at a 60-pick window, because
  `survival_prob` saturates at 1.0 for anyone far beyond it. That is correct and self-limiting — the
  advice path moves exactly the players near *your* window, which is the only place advice matters.
* **(c) readout, engine-side only** — `availability_readout` returns `p_available` **and**
  `p_available_baseline` side by side, plus `drift_picks`, a three-bucket `reach_risk` label and a
  `drift_material` flag. UI stays in Phase 14 per the standing "app strictly last" rule. Reporting
  the *pair* is deliberate: the honest presentation of an unbacktested adjustment is never the
  adjusted number alone. On the 2026 board 18 picks out: 162 `likely available`, 19 `coin flip`,
  2 rows materially moved by drift.
* **(d) isolation — the one that protects Session D.** `DriftConfig()` is a provable no-op and a
  `RiskModel` built without `hype` is **bit-identical** to the pre-16.12 frozen path;
  `tests/test_drift_consumption.py` asserts it by constructing the model the old way and comparing
  with `array_equal`, and separately asserts the opt-in path *does* change something so the
  guarantee cannot pass vacuously. The drift term also rides only the `scarcity_w > 0` branch, so a
  covariance-only greedy is untouched.

### 16.16 — run detection: **the detector works, reacting to it does not** (Phase 16's fourth null)

**Question 1 — does it fire on real runs? Yes, and this took a fix.** Run intensity = a position's
share of the last 10 picks minus its share of the **live candidate set** (top-40 available by ADP).
The first implementation used the *whole remaining pool* as the baseline; because a board is
WR-heavy at every depth, the reference rate for a scarce position is near zero, and the detector
fired on **61 %** of real windows while the flagged position was taken *slightly less* often over
the next five picks (0.268 vs 0.278) — no discrimination at all. Against the candidate set — the
same choice-set discipline Session G established for the fitted β, now applied to a rate — the
threshold sweep is cleanly monotone across 7,957 replayed windows:

| threshold | fires | flagged pos. share of next 5 | vs unflagged | discrimination |
|---|---|---|---|---|
| 0.10 | 86.8 % | 0.277 | 0.277 | −0.001 |
| 0.20 | 50.0 % | 0.290 | 0.263 | +0.027 |
| 0.30 | 22.5 % | 0.303 | 0.269 | +0.034 |
| 0.40 |  8.0 % | 0.345 | 0.271 | +0.074 |
| 0.50 |  2.4 % | **0.382** | 0.274 | **+0.109** |

The threshold is a free parameter, so the whole curve is reported rather than one number chosen to
look good — and monotonicity across the entire sweep is the real evidence, not the operating point.

**Question 2 — does reacting help? No, and it degrades monotonically.** Paired availability Brier on
4,300 run-opened windows: **run_w 0.0 → 0.2121 · 0.5 → 0.2123 · 1.0 → 0.2128 · 2.0 → 0.2186.** Every
non-zero bump is worse than static, in order of size.

*The most likely reading — flagged as a reading, not a separately tested result — is
**double-counting**: 11.1 already carries a `pos_run3` term, so an additional positional bump adds
bias without adding information. A monotone degradation in the bump size is the signature of that
rather than of a signal that is merely useless.* Confirming it would mean re-fitting 11.1 without
`pos_run3`, which is an 11.1 respecification and out of scope here (cf. T15).

**Ships DEFAULT OFF (`RUN_W = 0`), null reported** — the pre-agreed 16.9 treatment. The detector
itself is kept and is genuinely useful as a **live-draft alert** for 14.4 ("RBs are flying"),
which is a UX claim its face-validity evidence *does* support, quite separately from forecasting.

### The shape of Phase 16, now that it is done

Four honest nulls on the availability side (16.8 drift model, 16.9 narrative shock, 16.16 run
reaction) plus the value side's three (16.1, 16.2, 16.4's deflationary 20.9 %). Everything that
ships from this phase is either a *contract fix* that improved a validated metric (the 16.9
choice-set band: level error 59.5 % → 8.8 %, availability Brier +0.0644 → +0.0708) or an explicitly
curated, opt-in, default-OFF channel. **Phase 16 did not find an edge. It found four ways the
apparent edges were measurement artifacts, and shipped the plumbing to express a human's judgment
honestly when the model has nothing to say.**

## Session H (2026-07-26) — opponent personalities: 16.13 board enrichment · 16.14 the five headliners

**496 tests** (was 466), ruff clean, both done-bars PASS on the live 2026 board.
`steps/phase16_13_personalities.py` → `analysis/phase16_13_personalities.json`.

### 16.13 — enriching the mock board (`draft/enrichment.py`, `draft/simulator.py`)

A read-only join off two frozen contracts — `distribution.cached_distribution` and `value_board`,
the same two readers `optimizer.assemble_value` already uses — attaching `boom_prob · q90 ·
bust_prob · q10 · games_played_mean · mean · vbd · overall_rank`, plus `rookie` (Sleeper
`years_exp == 0`) and `cos` (16.5's event board). `simulator.PASSTHROUGH_COLS` carries whatever is
present through `_prepare_board`; an ADP-only board is byte-for-byte what it always was, asserted.

**Coverage on the 2026 board: 81.8 % distribution / 85.8 % value, and the shortfall is exactly
right** — 22 DEF + 18 PK + one WR. Kickers and defenses carry no projection at all, so the only
skill-player gap in the entire league is a single receiver. Reported rather than assumed, because a
silent NaN pool is read by a personality as "neutral", which is indistinguishable from "average".

**Two personalities that had never worked started working.** `homer` scaled a `fandom` coefficient
whose feature was identically 0 — `make_opponent_pick_fn` never passed `fav` — and `rookie_hawk`
scaled a `rookie` column `_prepare_board` dropped on the floor. Both had been literal no-ops since
Phase 11.3, through a full phase and a test suite, because **a personality that does nothing still
completes a legal draft**. New entry in the glossary under *inert personality*.

### ★★ 16.14's first cut built two personalities that agreed with each other

The obvious build is an upside chaser weighting `q90` and a safe drafter weighting `q10`. It ran, it
passed a synthetic face-validity test, and **on the real board `safe_floor` drafted a *higher*
mean `q90` than `upside_chaser`.**

The measurement, within position, on the frozen board:

| season | corr(q90, mean) | corr(q90, q10) | corr(gpm, mean) | distinct gpm |
|--------|-----------------|----------------|-----------------|--------------|
| 2022   | +0.984          | +0.739         | +0.791          | 298          |
| 2025   | +0.985          | +0.712         | +0.800          | 307          |
| 2026   | **+0.999**      | +0.616         | **+0.000**      | **4**        |

`q90` is not a ceiling signal. It is a **level** signal — "is this player good" — and so is `q10`.
Weighting either buys quality, which is why two opposite-sounding managers drafted the same players
from opposite rationales. Neither a bug in the code nor noise: it reproduces in every season.

**The fix is the control, not the coefficient.** `enrichment.residual_shape` regresses the level out
inside each position, leaving `upside` / `floor` — *more ceiling (floor) than a player projected
this high usually carries*. `corr` with `mean` is 0 by construction and `corr(upside, floor)` is
**−0.86** on 2022/2025: genuinely opposed for the first time. On 2026 it is only −0.20, which is
T17 showing through.

**This is the fourth member of the F.5/F.6/16.9/16.10 family, and the closest relative is 16.10.**
There it was *a coefficient is not transportable without its controls* — partial weights used
unconditionally ranked by board depth. Here it is a **signal** rather than a coefficient and the
missing control is the projected level, but the failure mode is identical and it presented the same
way: **as a plausible modelling result rather than as an error.** The only reason it was caught is
that the face-validity bar was stated as *the two must disagree with each other*, not merely *each
must differ from balanced* — a weaker bar passes a broken build.

**The synthetic fixture was complicit and has been fixed.** It drew `q90` and `q10` independently,
so the residualization looked unnecessary and the two personalities looked cleanly opposed. It now
generates both from a shared **level** plus an opposing **shape** factor, reproducing the real
board's correlation structure (`corr(q90, mean)` ≈ 0.98, `corr(upside, floor)` ≈ −0.86). *A fixture
that is easier than reality is a fixture that certifies bugs.*

### 16.14 — the five headliners (`draft/personalities.py`)

`autopilot · balanced · upside_chaser · safe_floor · homer`, plus the 11.3 library extras
(`chalk`, `zero_rb`, `reacher`, `rookie_hawk`) unchanged. Three mechanisms:

* **`signal_weights`** — utility per within-position sd of the live candidate pool.
* **`max_reach_picks`** — a reach ceiling in **ADP picks**, converted through the model's own
  `β_adp_s` exactly as `apply_hype` does. Covers the discretionary tilt (hype + signals + fandom
  excess) and deliberately *not* β reshaping or `early_pos_penalty`, so `zero_rb` and `autopilot`
  are not silently neutered. The user's requested fallback — *"if there is no reasonable hype or COS
  pick at the slot, go for best value, don't reach for a crazy target"* — is not special-cased; it
  falls out, and is tested as an **exact** pick-log equality.
* **`hype_gain`** — a per-seat multiplier on the shared per-draft shock, which is the dial 16.15
  will use to route 16.9's narrative shock through the seats that would actually chase it.

**The ceilings were measured, not guessed.** At a 10-pick ceiling every tilt is real but illegible —
pooled over 8 seeds, `upside_chaser` and `safe_floor` sit inside `balanced`'s own noise on every
signal they weight, because a ±0.17-utility clip is nothing against a softmax over 40 candidates. At
18 the ordering separates and stays separated. Shipped at 18 / 15 / 24 (the homer's ceiling is
`MAX_PICK_DELTA`, the largest claim the curated hype board may make about one player).

**Live-board face validity** (12 pooled drafts each, 10×15, mean within-position z of what each room
drafted):

| personality | upside | floor | boom | bust | cos | q90(raw) |
|-------------|--------|-------|------|------|-----|----------|
| autopilot   | −0.073 | +0.021 | +0.103 | +0.038 | −0.111 | **+0.344** |
| balanced    | −0.052 | −0.032 | +0.081 | +0.018 | −0.089 | +0.270 |
| upside_chaser | **+0.023** | −0.039 | **+0.117** | +0.019 | −0.047 | +0.260 |
| safe_floor  | −0.083 | **+0.040** | +0.084 | **−0.042** | −0.114 | +0.273 |
| homer       | −0.054 | −0.026 | +0.067 | +0.026 | **+0.008** | +0.261 |

All seven checks pass, including `autopilot_is_pure_adp_order` as an **exact** equality against
`pick_by_adp(noise=0)` over the whole draft. Note `upside_chaser` carries the *lowest* raw `q90` of
the tilting seats — the correct signature of a shape tilt: chasing upside means declining to chase
level. **Effect sizes are small (±0.05 z) and that is honest** — a manager who reaches at most 1–2
rounds cannot move a 90-player drafted pool much, and the whole room still drafts roughly the top of
the board. Face validity here is about *direction and opposition*, not magnitude.

**A pleasing emergent behaviour:** a homer *with* a favourite team chases changed situations
**less** than a homer without one (`cos` −0.012 vs +0.008). The reach ceiling is a shared budget, so
fandom crowds out narrative — which is exactly how a real homer behaves.

**Validation is face validity + 30 offline unit tests, with no Brier gate** (user decision,
2026-07-23). That is the right bar and worth stating plainly: 11.1 already owns *predicts the
average manager*, and deviating from it is the entire point of a personality. A personality set that
scored better against the corpus would be a worse personality set.

### New tech debt: T17 — the live season has no per-player availability

Found by 16.13's coverage report and pinned down exactly: `availability_projection(con, 2026)`
returns **0 rows**, because it predicts each player's hazard at his covariates *for the target
season* and a season that has not been played has no `weekly` rows. Every player therefore falls to
the T3-A cohort prior — **4 distinct `games_played_mean` values across 480 players**, ~6.6 of 17
games — and the Phase-5 `mean` collapses to **37 % of the consensus projection it is built from**
(2025: 75 %). Levels for the live season are wrong by about a factor of two.

**What saves Session H from it:** the collapse is close to a common multiplier, and 16.14
standardizes every signal **within position** before weighting it, so a uniform multiplicative bias
cancels. The one casualty is `games_played_mean`, now inert on a live board (corr with everything =
0.00); `safe_floor` keeps the weight anyway, since the defect is upstream and temporary while the
intent is permanent. Blocker for Phase 14 surfacing distribution numbers; not for H or I. Full entry
and the fix in `docs/TECH-DEBT.md`.

## Session H2 (2026-07-27) — T17 repaired · 16.13 revised · 16.15 the mock room

**524 tests** (was 496), ruff clean, every done-bar PASS on the live 2026 board.
`steps/phase16_15_mock_room.py` → `analysis/phase16_15_mock_room.json`; `steps/phase5_5_utility.py`
carries the T17 guard. Session H is now complete (16.13 · 16.14 · 16.15) and committed.

### T17 — the live season's availability, repaired (and the guard that outlives it)

`injury.projected_availability_frame` builds an unplayed season's covariates from the most recent
completed season, with `team_games` from the schedule rather than `week.nunique()` of a season with
no weeks, and stamps `covariate_source` (`observed` | `rolled_forward`) so the substitution shows up
in the output. **The 2026 level ratio goes 0.37 → 0.721**, against 0.683 on the 2025 holdout.

**The guard is the durable half.** `distribution.level_ratio` / `assert_level_band` assert the
distribution's mean sits within 0.55–0.85 of the consensus projection it is built from, and they run
**on the live unplayed season as well as the holdout — the live one is the one that breaks**. A
gate that only runs where the data is complete would not have caught this, which is the whole
lesson: T17 produced no exception, no empty frame and no failing test, just a board at 37 % of
itself. *Assert the relationship between a derived quantity and its input, not merely that the
derivation ran.*

**Honest caveat, printed by the step rather than buried:** the rolled-forward path sits *above* the
observed range (0.638–0.683), because a draft-day forecast cannot condition on a player appearing.
Unconditionality, not a defect — but a live number is mildly optimistic against how the backtest
seasons scored.

### ★★ THE FINDING — an upstream fix can break a downstream signal *by making it better*

Repairing T17 turned `games_played_mean` from four cohort constants into a real per-player forecast.
In the same move it turned it into a **level** column: `corr(games_played_mean, mean)` within
position is **+0.90 / +0.47 / +0.51 / +0.46** (QB/RB/TE/WR, 2026), where under the broken data it
was **+0.00** — inert, and documented as inert. So `safe_floor`'s durability weight became a quality
tilt at the moment the data improved, with no code change and a green suite.

This is **the third instance of the 16.14 collinearity lesson** (`q90`/`q10` were level, not shape)
and the first to arrive through *data* rather than code. Fixed the same way: `residual_shape` gained
a `durability` column, level regressed out within position, and `safe_floor` weights that.
`SIGNAL_COLS ⊆ PASSTHROUGH_COLS` is now asserted, because a weightable-but-dropped signal has
shipped three times (`fandom`, `rookie`, `durability`).

**What it costs to state generally:** a regression test pins a signal's *behaviour*, not its
*meaning*. Nothing in the suite could have caught this, because every test still passed and the
personality still drafted. The only thing that catches it is re-measuring a signal's correlation
with the level **after any change to the data it is built from** — the F.5 rule ("re-audit derived
artifacts after a step change in input volume") generalized from volume to quality.

**Measured bound on what the weight can do,** recorded so nobody re-litigates it: `durability` is
−0.34 against `floor` and +0.23 against `bust_prob` on the 2026 board (−0.28 inside the hazard
group, so not a cohort artifact). *At a fixed level, floor and availability point in opposite
directions.* Turning the weight on gains a stable +0.05 durability z and costs ~0.02 of floor, but
it cannot make `safe_floor` an above-average durability buyer — its gap to `balanced` is
+0.010 / −0.001 / −0.009 as the draft count grows, i.e. noise. The done-bar therefore A/Bs the
weight **against itself off**, not against `balanced`.

### 16.15 — the mock room (`draft/personalities.py`, `steps/phase16_15_mock_room.py`)

`DEFAULT_ROOM` + `make_room` + `normalized_hype_gains` + `make_room_pick_fn`. Filed in
`personalities.py`, **not** `simulator.py` as BUILD_PLAN specifies: composing a room needs
`Personality`, and making the draft engine every earlier phase runs on import the Phase-16
personality library would put a realism feature underneath the frozen optimizer path. No new import
edge either way.

**The default mix is hand-set, and the corpus can only check it, not supply it** — a manager's
*tendency* is observable, his *personality* is a latent label nothing in the data assigns. On 3,309
eligible-redraft managers (≥30 picks, complete snake/linear, 8–14 teams): median QB share 12.6 %, RB
share 31 %, and only **1.7 % draft RB-light** — which is why no `zero_rb` seat sits in a default
room, though it stays one override away. That check computes position share **from picks alone, no
ADP reference**, deliberately: the stored `avg_reach` reports a +91.9-pick mean QB reach and is a
pooled-board mismatch rather than a behaviour (**new T18**).

**Gains are normalized to room-mean 1.** 16.9 fitted the shock's magnitude with the draw applied
uniformly across seats, so applying the shipped gains raw (autopilot 0 · safe 0.5 · balanced 1 ·
upside 1.5 · homer 2.5) would let *room composition silently rescale a calibrated parameter*. A room
of all autopilots has no channel and is left at zero rather than divided by it.

### ★ The shock rides OUTSIDE the reach ceiling — and the bar that hid it

`max_reach_picks` now bounds a seat's **own opinion** (`signal_weights` + fandom excess); the shared
16.9 draw is added after the clip. Folded into the same clip — the H1 build — a seat whose signals
already saturate its ceiling cannot express the story at all, and **nothing fails**, because a
personality that ignores the shock still completes a legal draft.

**Two things made this visible, and both are reusable:**

1. **State the bar across the whole room, not at its two ends.** The original check was
   *chasers − autopickers*, which passes on a room that routes the story backwards: the autopickers'
   share of hyped players **falls** when the channel opens (they get sniped by whoever *is*
   chasing), so the gap widens either way. The bar is now `spearman(Δ loud-share, seat gain)` over
   all nine seats. This is the 16.14 "state your bars as oppositions" lesson with a second clause:
   *an opposition between two extremes cannot see the middle going backwards.*
2. **A control has to be the same measurement.** The first sweep used a zero *vector* as the
   channel-off arm; `argsort` on zeros labels the top-25 rows by board order — i.e. by ADP, which
   autopick seats take by construction — producing a large fake effect on exactly the seats it
   should say nothing about. The control must close the channel (`hype=None`) while keeping the
   **same loud labels**.

**Scope of the defect, stated precisely,** because the first diagnosis overstated it: on the test
fixture (`β_adp_s = −0.85`) the clip bit hard — `homer` 90 % of candidates, 17 % of the shock
surviving. On the **live board with the fitted β (−1.68)** the caps are ~2× larger and `homer`
clips **0.0 %**, `upside_chaser` 26 %, `safe_floor` 33 %. So on today's board the fold-in changed
little; it would bite after any 11.1 refit that shrank `β_adp_s`. The fix is justified on the
principle rather than the current magnitude: **16.9 fitted the shock uncapped and uniform, so
passing it through a 16.14 clip uses a fitted parameter outside its estimation conditions** — *a
coefficient is not transportable without its controls*, for the third time in this phase.

### ★★ 16.15's headline is a NULL — Phase 16's fifth — and it is 16.9's null, not a new one

At the shipped shock size the room does essentially nothing: the calibrated draw is **1.48 ADP
picks**, the largest per-seat change in hyped-player share is **0.036**, and its rank correlation
with seat gain is **+0.070**. Amplify the *same* shock and the correlation climbs
**+0.07 → +0.53 → +0.84 → +0.91 → +0.95** at ×1 · ×2 · ×5 · ×10 · ×20, then flattens.

So the coupling is **built correctly and waiting on a signal worth routing**. 16.9 already reported
its own magnitude as unidentified; 16.15 faithfully routing a null cannot manufacture an effect, and
tuning the shock upward to make this substep look better would be tuning a calibrated parameter to a
face-validity check. The done-bar therefore **gates the mechanism** at ×10 (`AMP_GATE`, the smallest
amplification that resolves cleanly — the Phase-9.5 `winprob_sims ≥ 200` move) and **reports the
shipped size as a null**. Same shape as 16.16: *the detector works, reacting to it does not.*

**Phase 16 in total: five honest nulls** (16.1/16.2 value-side situation, 16.8 drift, 16.9 shock,
16.16 run reaction, 16.15 shipped-size coupling) plus 16.4's deflationary 20.9 %. What ships from
the phase is contract fixes, curated opt-in channels defaulted OFF, and a realism feature that is
labelled as realism.

## Live mock draft (2026-07-27) — a human in the room, and T15 measured from both sides

**What this was.** The first end-to-end human-in-the-loop use of the engine: the user drafted a full
10-team full-PPR 15-round snake from seat 7 against `DEFAULT_ROOM`, one pick at a time, on the live
2026 FFC board with 16.13 enrichment. No modelling code was written or changed — the harness is a
thin driver over `DraftState` + `personalities.make_room_pick_fn` (kept at
`/tmp/.../scratchpad/mockdraft.py`; **promote it to `steps/` if we want repeatable human mocks**).
**Nothing in the repo's model path was touched this session; this entry is a measurement + doc
update only.**

**Why it matters more than a normal validation run.** Every done-bar Phase 16 shipped is an
aggregate: Brier, log-loss, rank correlation, share-of-hyped-players. A human watching one draft
found, in under ten picks, a defect that **every one of those gates passed over** — because the
gates score *whether the room is better than a baseline*, and none of them score *whether the room
is possible*. The single most transferable lesson here:

> ★ **An aggregate metric cannot see an impossible event.** 11.1's log-loss gain (+0.174), 11.2's
> availability Brier (+0.086) and 16.9's dispersion match are all real and all still hold — while
> the same model drafts Kenneth Walker III (ADP 22.5) at pick 4 and leaves three consensus top-6
> players on the board at pick 14. **Add at least one bar per subsystem that a domain expert could
> fail by eye**, and run it in front of one before shipping the subsystem.

### ★ The measurement (this is the deliverable)

Mean |drift| in **10-team ADP picks**, the simulated room vs **1,420 realized human drafts /
197,227 boarded picks / 2017–2025**, both via `adp/drift_panel.build_drift_panel`'s own definition
(`drift = adp_rounds − slot_rounds`, positive = drafted earlier):

| round | corpus mean | **sim mean** | corpus p90 | **sim p90** |
|---|---|---|---|---|
| 1 | **3.3** | **11.4** | **6.6** | **27.7** |
| 2 | 5.7 | 15.2 | 12.4 | 30.8 |
| 3 | 7.8 | 9.4 | 16.5 | 15.2 |
| 4 | 9.8 | 13.9 | 21.2 | 22.7 |
| 5 | 11.6 | 12.8 | 25.2 | 19.5 |
| 8 | 15.1 | 10.3 | 35.6 | 20.3 |
| 12 | 18.0 | 21.4 | 35.8 | 33.4 |
| 15 | 27.1 | 15.0 | 51.7 | 23.6 |

**The corpus grows monotonically 3.3 → 27.1 picks. The simulator is flat at ~10–21 with no trend.**
The defect is a **shape** error, not a scale error: ~3.5× too wide in round 1, ~1.8× too *narrow* by
round 15. Shrinking the softmax globally — the obvious fix — would make the late rounds worse.

**★ The user's pre-data estimate was right to one decimal.** Asked what a plausible early reach
looks like, before seeing any of this, he said "5–8 picks". The corpus round-1 p90 is **6.6**. Worth
recording because it is the argument for doing this exercise at all: *domain intuition priced a
parameter our fitted model got wrong by 3.5×.*

**★ The fall side is the same defect, and it is the one a user actually notices.** Corpus players at
ADP ≤ 12: mean realized slot **pick 8.4**, only **23.7 %** fall past pick 10, **p95 = pick 17**. In
the simulated draft: Nacua (ADP 2.7) → **14**, CMC (5.1) → **19**, JSN (5.9) → **20**, J. Taylor
(7.7) → **21**, Achane (9.5) → **22**. Five top-12 players past the corpus's 95th percentile *in a
single draft*; Rashee Rice (27.3) → **59**.

**★ And the spilled value goes to the seats with no opinion.** Per-seat mean drift in picks
(+ = reached): `autopilot` **−19.8** · `balanced` +4.3 · `safe_floor` +5.3 · `homer` +6.9 ·
`upside_chaser` +8.7 · `reacher` **+14.5** (max **+52.2**). Final top-9 consensus projection:
**autopilot 1st (2,589) and 2nd (2,586)**, the user 3rd (2,519), `upside_chaser` 9th and `reacher`
10th. **A room where following ADP blindly wins is a room that is wrong**, and unlike "does this
look realistic", that is an *objective* regression test needing no human judgement.

### ★ Why the 7,699-draft corpus could not have fixed this — the arithmetic

`_ADP_SCALE = 50`, fitted `adp_s = −1.683` ⇒ **one ADP pick = 0.0337 utility**. The other fitted
coefficients in the same units: `is_TE` **+16.8 picks**, `need` **+14.1**, `is_RB` **−12.1**,
`fandom` **+35.5** (×2.5 for `homer` ⇒ **89**), `rookie` +3.3. The pick is then a softmax over
`CHOICE_TOP_K = 40` candidates spanning ~45 ADP picks in round 1 — a **1.35** utility spread end to
end, so the 40th-best available is still **26 %** as likely as the best. Analytically, with an
ADP-only utility: `P(best available) = 4.8 %`, `P(20th-or-worse) = 33.8 %`, **expected reach 16.8
picks**, before any personality tilt fires.

> ★ **The fit is not wrong for the data it saw; the specification cannot represent the data.**
> `adp_s` is linear in raw ADP, pooled over every round, so one coefficient must fit round 12 (the
> top-40 spans ADP ~100–200) and round 1 (spans ADP 1–45) at once. MLE compromises, and the
> compromise is absurd precisely where a human looks first. **More data estimates a misspecified
> coefficient more precisely.** This is why F.5's 52× corpus expansion left it untouched — and it is
> the counterpart to F.6's lesson: *contamination invents effects; misspecification hides them in
> plain sight while every aggregate gate stays green.*

### ★ The functional form is measured — and it is NOT the log transform

Regressing corpus width on pick number gives mean|reach| ∝ `pick^0.5…0.6`. For reference: the
current **linear** ADP term implies `pick^0.0` (flat — what we see), a **log-ADP** term implies
`pick^1.0` (width proportional to depth — too tight in round 1, too wide at 15). So the honest
candidate is a **fractional power** (`adp^~0.45` in utility, or a free exponent estimated jointly),
or a rank-in-available-pool transform. **T15's earlier "log-ADP" suggestion is superseded**, and my
own mid-draft recommendation of log was corrected by this measurement. Choose among the candidates
by **refit log-loss**, not by curve-fitting to the table above — the table is the acceptance bar,
not the estimator.

### ★ What `Personality.max_reach_picks` does and does not bound (a live re-confirmation)

The 42-pick reach of the draft was made by **`balanced`** — no `signal_weights`, no `fav_teams`,
`max_reach_picks = None`, i.e. the fitted average manager with every 16.14 tilt switched off. The
reach ceiling clips a seat's **own opinion** only (`signal_weights` + fandom excess) and cannot
touch the β softmax underneath. Session H already stated this in the docstring; **a human seeing
the room for the first time read the ceiling as a promise about total behaviour.** If a clip is
shipped for Phase 14 it has to bound the *pick*, be labelled as an override outside the estimated
path, and be separable — because it moves 11.2's Brier and 16.9's calibration the moment it is on.

### Caveats on the measurement itself

- The corpus panel is **boarded offensive players only** (no K/DST, no off-board late picks), 8–14
  team leagues normalized to rounds then rescaled to 10-team picks. Corpus *maxima* (95–143 picks)
  are tail artifacts of that normalization plus keeper/odd rooms — **use p90, not max**.
- The sim side is **one draft** (135 opponent picks, ~9 per round), so the per-round sim cells are
  noisy. The shape claim rests on the corpus curve plus the analytic softmax derivation; the single
  draft is the illustration, not the evidence. **Re-measure over ≥50 seeded drafts before/after any
  fix** — cheap, and it turns every number above into a real A/B.

## Personality design review (2026-07-27) — situation explains the level, not the residual

Follow-on to the live mock draft above: the user reviewed each seat's intended character. Docs-only;
the settled contract is `docs/BUILD_PLAN.md` §16.14R, the session order is `PLAN.md` §2026-07-27.
Two things here are findings rather than decisions.

### ★ Why "situation is a null for alpha but not for human behaviour" is half right — and the half that
### is right changes the design

The user's instruction for `balanced` was to weigh coaching and situation changes because *even though
16.1/16.2/16.8 measured them as nulls, they visibly drive how humans draft.* We have in fact measured
exactly that second claim, twice, from two independent directions, and it came back null both times:
16.8 in Session F on 34 drafts (+1.05 % CI[−1.48,+4.96]) and **re-asked in F.6 on 1,144 drafts /
157,349 picks — headline +9.25 % but the mandatory ablation at +0.01 % CI[−1.98,+1.84]**. The features
that *do* move human draft behaviour are `rookie` (+0.94 rounds), `adp_stdev` (+0.27/SD), `vbd_gap`
(+0.26/SD), `pos_WR`, `pos_TE`. Situation flags are not among them.

But the reconciliation rescues the intuition, and it is the useful part:

> ★ **A drift model can only see deviation from ADP. If the market has already priced a player's
> changed situation into his ADP, a human drafting on that situation drafts him _at_ ADP — there is no
> residual left to detect.** "Situation drives human behaviour" and "situation does not predict drift"
> are therefore both true simultaneously. **Situation explains the level; the drift model only ever
> sees the residual.**

**The design rule that follows** (now in 16.14R): situation/coach data belongs in a personality as
*what it already agrees with ADP about*, not as a reason to deviate from ADP. Wiring it as a reach
driver would add a term we have twice measured at zero. It ships as a labelled opt-in channel,
default OFF — the 16.10 hype-board pattern.

**Generalizable:** *before concluding a signal is behaviourally inert, check whether the target you
measured it against has already absorbed it.* A residual-target null is much weaker evidence than a
level-target null, and the two are easy to conflate because both print "not significant". This is the
sibling of the ablation rule (F.6): there, more data strengthened a leak; here, the wrong target
hides a real effect in the baseline.

### ★ `balanced` was never given the thing everyone assumed it had

Recorded because it explains the 42-pick reach without any appeal to the T15 misspecification.
`balanced` is the raw fitted β with **every** 16.14 tilt switched off — no `signal_weights`, no
`fav_teams`, `max_reach_picks=None`. Its documented character ("the fitted average manager") was
accurate; the *holistic, high-quality, makes-sense* behaviour the room's designer expected of it was
never implemented anywhere. **A seat whose spec is "the anchor" quietly acquires the qualities people
assume anchors have.** The T15 fix and 16.14R's `signal_weights` are separate repairs to the same
observed symptom, and it is worth not confusing them: T15 fixes *how far* it deviates, 16.14R fixes
*which way*.

### ★ The evaluation trap the value hawk creates

`value_hawk` replaces `homer` and optimizes our own value board. If the room is then scored on our own
projections, **it wins by construction and the result carries no information** — the argmax ran, that
is all. The lockbox already reported personalization as noise-dominated on realized points (archetype
cost CIs ∋ 0). Standing rule for the 16.14R session: room rankings on projected points are
**descriptive**; any **evaluative** claim runs on realized points in a backtest season. Same family as
*an inert thing still passes* and 16.14's two-personalities-that-agree.

## T15 step 0 (2026-07-27) — the A/B harness, and the defect re-measured at 900 drafts

`src/fantasy_quant/draft/mock.py` + `steps/t15_0_baseline.py` + `steps/mock_draft.py` (the live
driver, promoted from the session scratchpad) + `tests/test_mock.py`. **No model changed**: every
pick still runs the shipped 11.1 β and 11.3 personalities. What is new is that the room is run
**900 times** (8 FFC-boarded seasons × 100 seeded drafts, plus 100 on the 2026 live board) and
measured **by the same functions, on the same boards, as the realized human corpus** — a simulated
draft leaves `mock.sim_drift_panel` as `drift_panel.PANEL_COLS`, so a function reading the panel
cannot tell the two apart. Frozen at `analysis/t15_baseline.json`.

The corpus side is **FFC-only: 1,144 drafts / 157,349 boarded picks**. The 1,420-draft figure T15
quotes pools in ECR-boarded 2025, which `adp/boards.py` forbids in a headline; both are reported so
they reconcile.

### ★ The correction: the simulator is NOT flat, and the ratio column is the honest statement

| round | corpus mean | sim mean | corpus p90 | sim p90 | **ratio** |
|---|---|---|---|---|---|
| 1 | **2.87** | **12.15** | 5.23 | 29.51 | **4.24** |
| 3 | 7.19 | 14.09 | 15.44 | 27.10 | 1.96 |
| 5 | 10.84 | 16.39 | 23.21 | 28.60 | 1.51 |
| 9 | 14.83 | 17.63 | 32.56 | 31.60 | 1.19 |
| 12 | 18.51 | 17.69 | 36.60 | 32.60 | 0.96 |
| 15 | **27.10** | **15.55** | 52.33 | 29.10 | **0.57** |

Spearman(round, mean|drift|): **corpus +1.000, sim +0.646** (2026 board: +0.725). At one draft the
sim read as flat with no trend; at 800 it **rises 12.2 → 17.6 through round 9 and then turns over**,
falling to 15.6 by round 15. So "flat at ~10–21 with no trend" (the register's original wording, off
one draft) is superseded: the curve is **too high at the top, too shallow in the middle, and
inverted late**, crossing the corpus at ~round 11. The single scalar a fix must move is the ratio
column going 4.24 → 0.57; a uniform shrink moves the whole column down and makes the right-hand end
worse, which is the same conclusion by a better-resolved route.

**The pre-registered bars tighten** on the FFC-only corpus: round-1 mean **2.87** (not 3.3) and p90
**5.23** (not 6.6). The user's unprompted pre-data estimate — "5–8 picks is reasonable early" —
still brackets the realized p90.

### ★ Bar 2 at scale: the live mock's five falling elites were the median draft, not a bad draw

Consensus top-12 (ADP ≤ 12), in 10-team picks:

| | mean slot | p95 | share past pick 10 | n |
|---|---|---|---|---|
| corpus (FFC, matched) | **7.8** | **17.5** | **18.9 %** | 13,234 |
| sim (matched) | **14.1** | **30.0** | **57.9 %** | 9,500 |
| sim (2026 live board) | 14.3 | 30.0 | 59.0 % | 1,200 |

**Three in five consensus elites fall past pick 10 in the simulated room, against one in five in
1,144 real drafts**, and the simulated p95 (30.0) sits at nearly twice the corpus p95 (17.5). This
is the most user-visible half of T15 and it needed no judgement call to state.

### ★ Bar 3 inverts once faithfulness is matched — and it retires the quantile form of the bar

At **fixed** `pool_rank` edges the simulated harvest is roughly right:

| `pool_rank` bin | corpus harvest (sd) | n | sim harvest (sd) | n |
|---|---|---|---|---|
| [1, 2) | **+17.59** (17.0) | 19 | **+20.51** (2.1) | 1,568 |
| [2, 3) | +12.39 (10.6) | 186 | +16.82 (1.4) | 32 |
| [5, 8) | +4.35 (8.7) | 4,791 | +6.14 (2.2) | 147 |
| [12, 20) | −3.11 (9.7) | 1,512 | −6.31 (3.7) | 4,165 |

A seat that deviates *this much* takes home about what a human who deviates that much takes home —
+20.5 vs +17.6 at the chalk end, inside the corpus's own sd of 17.0. The **quantile** form of the
same bar reports **+20.43 (sim) vs +8.50 (corpus)**, an apparent 2.4× failure, purely because "the
most faithful quintile" means `pool_rank` **1.28** in the sim and **4.28** in the corpus. *A
quantile-matched comparison across two populations with different distributions compares two
different behaviours and calls the difference an effect.* The fixed-edge table is the bar; the
quantile number is kept in the artifact only so the two reconcile.

### ★★ THE FINDING — the room has no moderate drafters, and `autopilot` has no human counterpart

| | median `pool_rank` | moderate (2–8) | chalk (<2) |
|---|---|---|---|
| corpus (FFC, matched, 12,146 seats) | **7.62** | **54.3 %** | **0.2 %** |
| sim (8,000 seats) | 12.27 | **2.2 %** | **19.6 %** |

Real managers are a **continuum** centred where half of them sit; the simulated room is **bimodal** —
two `autopilot` seats at `pool_rank` 1.28 and everything else past 11, with the band containing 54 %
of humans essentially **empty (2.2 %)**. Two facts follow, and they are separate repairs:

1. **T15's target is a distribution, not a scale.** "Make early reaches smaller" would move the
   extremists left and leave the middle empty. A depth-varying `adp_s` reshapes *where the mass
   sits* — which is what the acceptance bars should be read against.
2. **★ `autopilot` over-represents a behaviour that is 0.2 % of reality by ~100×.** Two of ten seats
   draft more faithfully than 99.8 % of 12,146 realized human seats. 16.14R settled "autopilot: no
   change" on the grounds that its mock **win** was harvested spill — that still holds, and this does
   not reopen it. But *how many* such seats a default room seats is a **16.15 composition** question
   that this measurement puts a number on for the first time. Not a T15 model change; flagged so the
   16.14R session inherits the figure rather than re-deriving it.

**A third, smaller shape defect, recorded because it is invisible in any mean:** the simulated
harvest sd within a bin is **2.1–3.7 picks against the corpus's 8.7–17.0**. Real managers vary
enormously draft to draft; simulated seats are nearly deterministic in what they take home. Even a
sim whose *means* matched every row above would still be too homogeneous to be a human room.

## T15 step 1 (2026-07-27) — the respecification, and a selection criterion that had to be thrown out

`AdpSpec` / `BandSpec` in `draft/opponent_model.py` (one owner for a modelling choice that had four
copies), `steps/t15_1_respecify.py` (the grid), `steps/t15_2_calibrate.py` (the sim-side sweep),
`steps/t15_3_verify.py` (the joint re-verify). The grid is 4 bands × 11 exponents, each refit
walk-forward on **23,934 real choice groups** (20 drafts/season), and every exponent inside a band
is refit from **one** built frame — `build_choice_frame` now keeps raw `adp`, so the transform is a
column rather than a corpus rebuild.

### ★★ THE FINDING — "gain over the baseline" is not a selection criterion, and the grid proved it

The plan said to choose by refit log-loss. Because a wider candidate set mechanically raises
log-loss (more alternatives to spread probability over), band comparison needed something else, and
the obvious candidate was **gain over the ADP-only baseline** — both terms move together, so the
mechanical penalty should cancel. It does not, and the grid shows why in a single column. Inside the
**one** band where log-loss *is* comparable (`fixed40`, identical candidate sets throughout):

| exponent | held-out log-loss | gain vs ADP-only |
|---|---|---|
| 0.30 | 3.2475 | +0.1710 |
| 0.40 | 3.2455 | +0.1715 |
| **0.45** | **3.2453** ← min | +0.1718 |
| 0.50 | 3.2457 | +0.1721 |
| 0.75 | 3.2539 | +0.1736 |
| **1.00 (shipped, linear)** | 3.2687 | **+0.1750** ← max |

**The two criteria point in opposite directions.** Log-loss picks 0.45; gain picks 1.00 — the
incumbent spec that T15 exists to replace. The reason is structural: **gain rises when the baseline
gets worse.** A linear ADP term cripples an ADP-only model far more than it cripples a model that
also has position dummies, `need` and `mgr_lean` to lean on, so the *gap* widens exactly where the
absolute fit is worst. Selecting on gain would have chosen the widest band and the flattest ADP
term — precisely the defect — and would have printed a rising headline while doing it.

**Generalizable, and it is the F.6 ablation rule's twin:** *a difference-of-two-models metric can be
improved by damaging the weaker model, so it ranks specifications only when the comparator is held
fixed.* F.6 said a leak makes a headline rise with more data; this says a bad specification can make
a headline rise by hurting its own baseline. Both present as a result.

**What replaced it: band coverage** (`opponent_model.band_coverage`) — *how often does the candidate
set fail to contain the pick a human actually made?* It is a property of the set, not of any
likelihood's normalization, so it is directly comparable across bands and has no degree of freedom
to game. It is also the Session-G choice-set contract restated as a measurable quantity: a
conditional logit evaluated on a set that excludes the realized choice is being used outside its
contract. The band is chosen as the **narrowest** one inside a stated 1 % miss tolerance; the
exponent is then chosen by held-out log-loss *within that band*, where the comparison is clean.

### ★ The exponent the likelihood picks is the one the width arithmetic derived

`fixed40`'s log-loss minimum is **interior, at p = 0.45** — not at a boundary, and not at log-ADP.
Independently, the corpus's realized reach width grows as `pick^0.5…0.6`, and the derived width law
`w_a ∝ 1/f'(a)` turns that into **p ≈ 0.4–0.5**. Two criteria with nothing in common — a held-out
choice likelihood over 24k human picks, and the shape of realized draft-slot dispersion — select the
same exponent. That is the strongest evidence in this session, and it was available only because the
grid ran down to 0.05: had it stopped at 0.3, the minimum would have looked like a boundary.

⚠ **A first, cheaper run said the opposite and was wrong.** At a 4-draft/season smoke budget the
log-loss fell monotonically toward the bottom of the grid, which reads as "the choice data want
log-ADP" — the interior optimum only resolves at a real corpus size. Recorded because the wrong
version is the more quotable one: *an optimum that sits at your grid's edge is usually a statement
about your budget, not about your data.*

### ★ The exponent and the band interact, which is why they are not chosen jointly

The log-loss-optimal exponent moves with the band: **0.45** at `fixed40`, **0.75** at `widen+5` and
`widen+10`. That is coherent — a band that reaches deeper as the draft goes on supplies some of the
depth-varying behaviour that curvature otherwise has to provide, so less curvature is needed. It
also means a joint search would need a criterion comparable across bands, which is exactly what does
not exist. Hence the sequential rule, stated before the numbers were read: **band by coverage, then
exponent by log-loss within it.**

### ★★ THE OTHER FINDING — a width metric will trade away the defect it was built to fix

The first calibration sweep minimized profile distance **averaged uniformly over all 15 rounds**, and
it selected `p = 0.60`. That spec:

| | round-1 mean | elite p95 | moderate share | full-round distance |
|---|---|---|---|---|
| corpus | **2.87** | **17.5** | **54.3 %** | — |
| p = 0.60 (selected) | 8.87 | **24.0 — gate FAIL** | 22.9 % | **0.3293 ← min** |
| p = 0.25 | 5.58 | **17.0 — gate PASS** | 61.6 % | 0.5689 |

**It bought late-round width by wrecking the top of the board**, and shipped a configuration that
fails the judgement-free elite-fall gate — the bar standing closest to the only defect a human ever
complained about. The metric was not wrong arithmetically; it was the wrong objective, and it was
one I introduced. The pre-registered bars are explicitly top-of-board ("esp. round 1: mean ≈3,
p90 ≈7"; "no top-12 player past ~pick 17"), so an unweighted average over rounds was never what T15
asked for.

**Two corrections followed, and the second is the general one:**

1. The objective is now profile distance over **rounds 1–6**, the range where the two populations
   are commensurable.
2. **The gate is a constraint, not a term.** A judgement-free bar stated against realized human
   behaviour is not something a fitted objective may trade against; the feasible set is defined
   first and the width objective is minimized *inside* it. A gate that can be out-voted by a metric
   is not a gate.

★ **And the reason the late rounds cannot be reached is structural, not parametric.** Realized
round-15 mean |drift| is **27.1 picks**; no exponent gets the simulator past ~13. At pick 150 about
thirty boarded players remain and the room takes near-best-available from them. A realized round-15
pick often lands 40 picks off consensus because *that room's managers held genuinely different
boards* — injuries, league-specific values, plain disagreement. That is **board heterogeneity
between managers**, and this simulator hands all ten seats the identical board by construction. No
`adp_s` respecification can manufacture it, and tuning curvature until the number matches would be
buying a late-round statistic with early-round realism. **Bar #1's late half is therefore reported
as an open structural limitation of the room, not closed.** The natural fix is per-seat board
perturbation, which belongs with 16.14R's `signal_weights` (direction) rather than with T15 (width).

## T15 steps 3–4 (2026-07-27) — the joint re-verify caught a trade, and forced a second parameter

### ★★ THE FINDING — one knob cannot set both ends, and the joint gate is what revealed it

Step 2 shipped `p = 0.15` on `widen+5` (the flattest exponent the elite-fall gate admitted). The
full-scale re-verify — 900 seeded drafts against 1,144 realized FFC drafts — showed it had **traded
one defect for another**:

| bar | pre-T15 | after step 2 | verdict |
|---|---|---|---|
| #2 elite fall, p95 / past pick 10 | 30.0 / 57.9 % | **16.0 / 28.5 %** | PASS (corpus 17.5 / 18.9 %) |
| #4 availability Brier (11.2) | +0.0708 | **+0.0890** | PASS — improved |
| #1 reach profile, distance | **0.388** | **0.791** | **worse than before the fix** |
| #5 dispersion (16.9) | 1.976 vs 1.816 (+8.8 %) | 0.784 vs 1.690 (**−53.6 %**) | **FAIL** |

The user-visible defect was genuinely fixed — round-1 reach **12.15 → 4.36 picks**, elites falling
past pick 10 **57.9 % → 28.5 %** — but the room became **uniformly too narrow** from round 2 on
(0.94 → 0.26× the corpus width), and Session G's validated dispersion match broke.

**This is exactly the failure the register named in advance** ("a change that improves one of those
and quietly degrades another is the failure mode to guard against") and it still caught us. Two
things made it visible: **(a)** the bars were re-measured *together in one run*, so no metric could
be checked by the person who cared about it; **(b)** a metric that was not a bar — the full-profile
distance — was reported next to the bar that was. **A round-1-only pass criterion said PASS while
the shape it was supposed to summarize had got worse**, which is a caution about writing a scalar
gate over a curve.

### ★ Why curvature could not do both: the derivation ignores pool exhaustion

The width law `w_a ∝ a^(1-p)` predicts `p = 0.15` should give width growing as `a^0.85` — roughly
18× across a draft. Measured, the room grew **4.10 → 7.30 picks, 1.8×**. The law assumes an
unbounded local candidate pool. By round 15 about **thirty** boarded players remain, so a seat
cannot deviate 27 picks from a board with less than 27 picks of depth beneath it. **Curvature buys
far less late width than the algebra promises, while costing full price at the top** — so a single
exponent is asked to satisfy two requirements that want opposite values, and satisfies neither.

That is an **identification** problem, not a tuning problem, and `docs/BUILD_PLAN.md` §16.14R had
already specified the answer and named T15 as its owner: **`width(round) × multiplier`**. Step 1 had
built only the multiplier. `personalities.WidthCurve` is the round function — it scales `β_adp_s` by
`round^γ`, so depth-width and seat-width become separately identified.

### ★ The joint sweep: 16 configurations, both gates as hard constraints, **one** survivor

| p | γ | distance | round 1 | round 15 | elite p95 | dispersion err | both gates |
|---|---|---|---|---|---|---|---|
| 0.15 | 0.0 | 0.803 | 4.10 | 7.30 | 17.0 ✓ | **−54.4 %** ✗ | ✗ |
| 0.15 | 0.4 | 0.343 | 4.10 | 11.16 | 17.0 ✓ | −24.8 % ✗ | ✗ |
| **0.15** | **0.8** | **0.190** | **4.10** | **17.40** | **17.0 ✓** | **+15.2 % ✓** | **✓** |
| 0.15 | 1.2 | 0.394 | 4.10 | 24.23 | 17.0 ✓ | +52.9 % ✗ | ✗ |
| 0.25 | 0.4 | 0.204 | 5.58 | 13.73 | 18.0 ✗ | −3.1 % ✓ | ✗ |
| 0.45 | 0.0 | 0.369 | 7.65 | 10.17 | 24.0 ✗ | −16.2 % ✓ | ✓/✗ |

**Exactly one of sixteen clears both**, and it is also the best profile match in the grid —
**distance 0.190 against the pre-T15 baseline's 0.388**, i.e. the shape error more than halved
rather than merely moving. That the constrained optimum is also the unconstrained one is the only
reason this reads as a fit rather than as a threshold chosen to admit a survivor.

### ☐ The one thing still not human-shaped, and it was never a pre-registered bar

Seat **faithfulness distribution** — step 0's own discovery — is improved but not solved, and it
trades directly against the profile match:

| | median `pool_rank` | moderate (2–8) |
|---|---|---|
| corpus | **7.62** | **54.3 %** |
| pre-T15 | 12.27 | 2.2 % |
| p=0.15, γ=0.0 (step 2) | 3.33 | **65.9 %** |
| **p=0.15, γ=0.8 (shipped)** | **10.27** | 14.3 % |

The configuration that matches the *reach profile* does not match the *population*, and vice versa.
Reported rather than resolved: it is not one of T15's five bars, and closing it means giving seats
genuinely different boards — per-seat board perturbation, which is 16.14R's direction half, not
T15's width half. **Recorded so the next session inherits a measured trade-off instead of
rediscovering it.**

### ⚠ Scope note: the width curve is a ROOM property, not part of the fitted model

`WidthCurve` is applied in the personality pick path, so it shapes **mock-room realism (11.3)** and
does **not** enter the 11.2 availability simulation, which runs the fitted β directly. It is stored
in the model artifact for convenience — the same file already carries `adp_spec`/`band`, which *are*
estimation conditions — and that convenience is a mild category error worth naming: two of those
three keys are things β was fit under, the third is a behavioural layer applied on top. 11.2's Brier
improving to **+0.0890** is therefore a statement about the refit β and band, with no contribution
from γ.

### ★ The shipped result — all five pre-registered bars pass, measured on 900 drafts

`AdpSpec(power, p=0.15)` · `BandSpec(widening, k0=40, +5/round, cap 160)` · `WidthCurve(γ=0.8)`,
β refit under all three. Full artifact: `analysis/t15_verify.json`.

| bar | pre-T15 | shipped | corpus |
|---|---|---|---|
| **#1** reach profile distance | 0.388 | **0.222** | 0 |
| | round 1 mean | 12.15 → **4.36** | 2.87 |
| | round 15 mean | 15.55 → **17.87** | 27.10 |
| | ratio range over 15 rounds | 4.24 … 0.57 | **1.52 … 0.66** | 1.0 |
| | Spearman(round, width) | +0.646 | **+0.864** | +1.000 |
| **#2** elite p95 / past pick 10 | 30.0 / 57.9 % | **17.0 / 28.5 %** | 17.5 / 18.9 % |
| **#3** worst harvest excess | — | **+0.21 sd** | tol 1.0 |
| **#4** 11.2 availability Brier gain | +0.0708 | **+0.0890** | — |
| **#5** dispersion vs corpus | +8.8 % | **+17.0 %** | tol ±20 % |

**Bar #3 is the one worth reading closely**, because it is the rewritten one. At matched
faithfulness the simulated ADP-follower now harvests **+18.10** picks against a human ADP-follower's
**+17.59** — the two populations agree to within 0.03 of a corpus sd. `autopilot`'s raw surplus is
still large (+18.03) and *that is correct*: the bar was rewritten precisely because an ADP-follower
should do well, and the defect was only ever the **excess** over what a human ADP-follower gets.
⚠ The corpus's chalk bin rests on **19 seats**, so this comparison is thin on the side that matters;
it is the weakest of the five.

**Two things that got worse and are not hidden by the verdict:**
1. **Dispersion error grew +8.8 % → +17.0 %.** It passes a ±20 % tolerance but is *not* an
   improvement on a metric Session G had tuned. T15 bought reach-profile shape at a small cost to a
   level that was previously better.
2. **11.1's log-loss gain is not comparable across the change.** At the shipped band the gain is
   **+0.1715**; the committed +0.1738 was measured on `fixed40`. Those are different candidate sets,
   and this session's own finding is that log-loss is not comparable across bands — so bar #4's 11.1
   half is reported as "re-measured under the new contract", **not** as "unchanged". Only the 11.2
   Brier, which is scored on realized windows rather than on a choice set, supports a clean
   before/after comparison — and it improved.

**The per-seat ordering is now monotone and legible**, which it was not before: `reacher` 21.1 →
`upside_chaser` 15.4 → `homer` 13.1 → `balanced` 10.8 → `safe_floor` 7.0 → `autopilot` 1.3 mean
`pool_rank`. The width multipliers do what they say.

## The 2×5 mock room (2026-07-27, session 5) — the user's eye found three seat defects, and two of them are in the *signals*

**What was run.** A full 15-round, 10-seat mock on the live 2026 FFC board (201 players + 16.13
enrichment), **2 seats each of `autopilot` / `value_hawk` / `safe_floor` / `reacher` / `balanced`**,
seats shuffled by `make_room` (room seed 5, draft seed 20260727). Then **60 seeded drafts** with the
same mix, room reshuffled per seed so personality is never confounded with slot — because *one draft
is 10 picks per round*, which is the T15 step-0 lesson applied to its own harness. Everything went
through the shipped engine: `mock.room_board`, `mock.simulate_room_draft`, the fitted 11.1 β under
`AdpSpec(power, p=0.15)` + the widening band. DEV-only; nothing written to `analysis/`.

⚠ **`value_hawk` does not exist in the shipped library** (16.14R is spec-agreed, not built). The seat
was approximated run-locally from existing machinery — `signal_weights={"vbd": 0.70,
"overall_rank": −0.30}`, `temperature 0.85`, `width_mult 1.15`, `max_reach_picks 14`. **It failed,
and why it failed is the useful result** (below).

### ★ The T15 fix holds up on the live board — this is the clean before/after

`analysis/t15_baseline.json` §`readout_2026` is the **pre-T15 room on the same 2026 board through the
same measurement code**, so this comparison has no board-vintage or re-derived-metric confound.

| | pre-T15 (2026, 100 drafts) | this room (60 drafts) | corpus (1,144 human FFC drafts) |
|---|---|---|---|
| round-1 mean reach (ADP picks) | 12.31 | **4.58** | 2.87 |
| round-1 p90 | 28.75 | **11.41** | 5.23 |
| ratio to corpus, R1 → R15 | 4.29× → 0.60× | **1.60× → 0.61×** | 1.00 |
| `profile_trend` (Spearman) | 0.725 | **0.854** | 1.000 |
| profile distance, rounds 1–6 | 0.713 | **0.244** | 0 |
| elite-fall p95 slot | 30.0 | **17.0** | 17.5 |
| consensus top-12 past pick 10 | 58.7 % | **30.6 %** | 18.9 % |

**The late-round narrowness is unchanged (0.60× → 0.61× at round 15) and that was predicted** — every
seat drafts one board, so real round-15 deviation is board *disagreement* between managers, not
choice noise. It needs per-seat board perturbation (16.14R), not another width parameter.

### ★★ THE FINDING — the fix for a level-vs-shape defect created the next one, and it is `floor`

The user reviewed all 150 picks and objected that `safe_floor` drafted boom-or-bust players (Zay
Flowers in round 2, Malik Nabers, Carnell Tate, Quentin Johnston, Jaydon Blue). The seat's aggregate
z-means are *correct* — `floor` +0.198 and `bust_prob` −0.129 against `balanced` — which is exactly
why no gate caught it.

**`q10` is censored at exactly 0 for 42.9 % of offensive board rows** (59.0 % past ADP 100, 5.7 %
inside ADP 50). `residual_shape` regresses `q10` on `mean` within position; a linear fit through a
floored variable predicts a *negative* q10 for replacement-level players, so anything just above the
censoring point earns a large positive residual. The result is a "safety" signal that **prefers
deeper players**: `corr(floor, adp)` = **+0.179 RB / +0.124 WR**. The board's safest RBs are Jonah
Coleman (ADP 171, mean 35.2, q10 1.3) and Jaydon Blue (ADP 140, mean 38.7, q10 1.8); its safest WR is
Zachariah Branch (ADP 165). Zay Flowers carries the **4th-highest residual floor of any WR** (+19.8).

**The seat drafted precisely what the board told it was safest.** 16.14 residualized the quantiles to
stop them being a level proxy; the residualization turned them into a **depth** proxy, because
removing the level from a censored variable does not leave something orthogonal to quality — it
leaves something anti-correlated with it in the tail. Fourth member of the family (`q90`/`q10` 16.14 ·
`games_played_mean` T17 · `vbd` below), **and the first where the fix for the previous instance is the
cause of the next.** Registered as **T19**.

Same seat, second defect: **`boom_prob` is exactly 0 for 64.7 % of offensive rows and `bust_prob` for
56.0 %**, so a third of `safe_floor`'s weight budget cannot fire over half the board. *An inert thing
still passes*, fourth instance.

### ★ The `reacher` has width with no direction — literally

Its definition is `Personality("reacher", temperature=2.2, width_mult=WIDTH_REACHER)`. **No
`signal_weights` at all.** The user's phrasing — *"these reaches are nonsensical and have no basis"* —
is not a metaphor: the seat is a hot softmax over a widening band with zero opinion attached. Measured
mean `pool_rank` **20.5** against a corpus p90 of **13.1**; Caleb Williams (ADP 109) at pick 51,
Rachaad White (ADP 101) at pick 44.

The user's proposed fix — a **budget** (≤2–3 large reaches in round 5+, 3–5 medium in round 3+,
clamped in rounds 1–3) — is better specified than the per-pick quantile clip proposed from the metrics
side, with one architectural consequence: **a budget is stateful per seat and `make_opponent_pick_fn`
is a stateless softmax**. But the ordering matters more than either: *give it direction first.* A
reacher that reaches **for something** (rookies, the 16.10 hype board, the 16.9 shock — all already
assigned to it by 16.14R) is most of the fix, and a budget on top of directed reaching is a different
object from a budget on top of noise.

### ★ The value hawk's bad picks are blind spots, not mis-weights — and that reorders 16.14R

The user objected to DK Metcalf (situation moved *against* him), Dylan Sampson (handcuff behind
Judkins) and James Cook (TD-dependent, regression risk). **None of those three things is on the 16.13
board.** There is a `cos` column, but `COS_WEIGHTS` scores *how loud the story is* and is **unsigned** —
Rachaad White reads `cos` **1.0** (max, team change) and DK Metcalf **0.6**, with no direction
anywhere. Committee share and TD-regression are absent entirely.

So **no objective function over today's board can avoid those picks**, and the correct conclusion is
not "re-weight the seat" but "expand the board first" — 16.14R open decision #3, settled by evidence.

**Separately, the mechanism half:** a `signal_weights` value hawk **cannot** work, and the reason is
arithmetic. `signal_bonus` z-scores within position, and within position `corr(vbd, adp)` = **−0.955
RB / −0.924 WR / −0.859 QB / −0.907 TE**. `pos_z(vbd)` therefore destroys VBD's only non-ADP content —
the **cross-position** comparison — and what is left is ADP with extra steps. Measured: the seat
gained **+0.065** vbd-z over `balanced` (autopilot, weighting nothing, gets **+0.571** by taking best
ADP) and finished **5.5 / 10**, behind `safe_floor`. This settles 16.14R open decision #1 in favour of
**portfolio CE**: CE is roster-level and survives the machinery that flattens VBD.

### ★ Two contract defects found while checking the user's K/DST instruction

1. **Team defenses are filtered out of every board by a `gsis_id IS NOT NULL` clause.** The data is
   present and good (60 `DEF` rows for 2026 FFC PPR 10-team; SEA 94.7, DEN 100.9, LAR 106.5) and
   everything downstream already supports DST — `board_player_key` name-keys defenses *by design*,
   `canon_pos` maps `DEF→DST`, `DRAFTABLE` includes it. It is a filter, not a data gap. **T20.**
2. **K is in the simulation candidate band but not the fit's.** `build_choice_frame(skill_only=True)`
   — the default the shipped β was fit under — restricts candidates to QB/RB/WR/TE; the sim bands the
   whole board. The fitted β nominates kickers it never saw (Brandon Aubrey, pick 119). **Session-G
   choice-set violation, second home**, and it survived because *an aggregate metric cannot see an
   occasional impossible event.* **T21.**

### ★ Per-seat behaviour over 60 drafts, and the two things composition alone fixed

| seat | mean `pool_rank` | mean drift (picks) | harvest | mean finish (of 10) | win share |
|---|---|---|---|---|---|
| autopilot | 1.24 | −16.40 | **+16.40** | **1.69** | **48.3 %** |
| safe_floor | 7.28 | −1.52 | +1.52 | 4.75 | 0.0 % |
| value_hawk | 8.91 | +0.57 | −0.57 | 5.54 | 1.7 % |
| balanced | 10.33 | +3.63 | −3.63 | 6.15 | 0.0 % |
| reacher | 20.46 | +20.51 | −20.51 | 9.37 | 0.0 % |

**Autopilot still wins.** T15's bar #3 (harvest excess ≤ 1.0 sd) passes and is the right bar, but the
room *outcome* still rewards doing nothing, and 2-of-10 seats over-represents a behaviour that is
**0.2 %** of real seats. That is the 16.15 composition question, now with a win share attached.

**What composition alone already fixed, with no model change:** swapping `homer` + `upside_chaser` for
`value_hawk` + a second `safe_floor` moved T15's open faithfulness gap from median `pool_rank`
**10.40 → 8.59** (corpus 7.62) and the moderate band **13.5 % → 24.3 %** (corpus 54.3 %). *Some of
what reads as a model defect is a room-composition choice* — worth knowing before spending a session
on per-seat board perturbation.

### ⚠ Roster shape carries no personality signal at all

Every seat took **6 WR** in the headline draft, and 5.82–5.99 across the batch — the `pos_caps` WR
ceiling, binding on all ten seats. Position caps plus a WR-heavy board are doing the roster
construction; the personalities only choose *which* players. If shape is meant to be a personality
dimension, the tilt has to reach positional **demand**, not just candidate utility. Not yet
registered — it needs a decision on whether shape *should* vary before it is called a defect.

---

## 16.14R steps 1–7 (2026-07-27/28) — repairing the signals before the personalities

**Goal:** the seven-step plan of record written after the 2×5 mock (`docs/BUILD_PLAN.md` §"16.14R —
THE EXECUTION ORDER"), run straight through under a waived §3.7 gate (user instruction: *"go
through the whole 7 step process without stopping until completion"*). The re-order's premise —
**repair the signals and the board before re-specifying any personality** — held up: two of the
seven steps changed inputs, and the seats that depend on them behaved differently for free.

**Decisions taken up front (user, 8 questions):** build every floor estimator and pick by the bar ·
replace `bust_prob` with a new enrichment column, Phase 5 untouched · step-3 context weightable by
any seat, default 0.0 except the value hawk · reach budget recomputed from `DraftState` · window
swept and chosen by the bar · corpus-weighted realistic room · leave uncommitted · deliver the
batch, the T19 before/after, and a fresh mock CSV.

### Step 1 — roster legality + the K/DST guarantee (T20 ☑, T21 ☑)

`include_dst` threaded through `_ffc_board`/`resolve_board` (**default OFF**, on only in
`mock.room_board`), `DraftState.mandatory_needs`/`picks_remaining`, and `SKILL_POSITIONS` shared by
the fit and the simulator. **60/60 seats finish with ≥1 K and ≥1 DST at 15 rounds; 0/60 at 8 rounds**
(the rule is gated on `rounds >= slots.starters`). The 2026 board gains **22 DEF rows** (223 vs 201).

**T15 bars unmoved, as the register required:** round-1 mean **4.36 → 4.36**, profile distance
0.222 → **0.208**, elite-fall p95 **17.0 → 17.0** / past-10 28.5 % → **28.5 %**, dispersion +17.0 %
→ +17.3 %. All PASS.

- ★ **The rule is a *deadline*, not a preference**, and that shape matters: it fires only when a
  seat's remaining picks equal its unfilled non-flexable slots, so K/DST go in rounds 14–15 exactly
  as they do in a real league. A side effect worth knowing: **round 14 now contains no offensive
  picks at all**, so the drift panel's round-14 row is empty by construction.
- ★ A test asserting "no K/DST drafted before round 13" **failed for the right reason** — a pure-ADP
  seat legitimately takes a defense at defense ADP. *"A K/DST was drafted early" and "a K/DST was
  forced early" are different events, and only the second is a bug*; the assertion moved onto
  `draftable_pool` itself.

### Step 2 — the `floor` repair (T19 ☑), and three wrong turns worth keeping

**The framing in the T19 ticket was wrong, and following it produced three failures before the fix.**
The ticket said *OLS is the wrong likelihood for a censored variable*, which admits two repairs —
fix the likelihood, or drop the functional form. Both failed, in opposite directions:

| estimator | worst `corr(floor, adp)` | top-10 ADP>130 | `corr(upside, floor)` | verdict |
|---|---|---|---|---|
| `linear` (shipped 16.14) | **+0.179** | 50 % | −0.35 | the inversion |
| `tobit` (censored MLE) | +0.089 | **100 %** | −0.38 | still deep-loaded |
| `rank` on raw quantiles | −0.069 | 20 % | **+0.94** | 16.14's defect restored |
| `rank_delta` (double rank) | +0.290 | 90 % | +0.46 | over-controls |

★★ **THE LESSON — the problem was the SCALE, not the fit.** A variable that piles up on a boundary
of its own support has no well-behaved residual *however* it is fitted: a linear fit hands the
pile-up a large positive residual, a rank hands it a mid-rank that then inherits the sign of
whatever the level control subtracts. Rebuilding the signals as **ratios to the projected level**
(`shape_inputs`: `q10/mean`, `q90/mean`, `(q90−q10)/mean`) puts a censored player at the **bottom**
of a bounded quantity — the honest reading, since a 10th percentile of zero *is* the worst possible
floor — and only then does an estimator pass. *Before choosing an estimator, check the variable is
on a scale the estimator can be right about.*

★ **The one-sided bar would have shipped the wrong answer.** `rank` on raw quantiles passes T19
cleanly (`corr(floor, adp)` −0.10…−0.21, all negative) while flipping `corr(upside, floor)` to
**+0.94 QB**, i.e. the ceiling-chaser and the floor-seeker agreeing again. Selection therefore
requires **both** T19's bar and 16.14's own oppositions. *A bar written to catch a defect in one
direction is passed by the same defect in the other.*

★ **A neighbourhood must be a fraction of its group, never a count.** At a flat window of 25 the
"local" rank was wider than the whole QB (27) and TE (23) group, so the level control silently
switched off for those positions — `corr(tail_risk, adp)` +0.45 QB / +0.78 TE against +0.38/+0.13
for the big groups. Capped at 25 % of the group.

**Shipped:** `SHAPE_METHODS = (linear, tobit, rank, rank_delta)`, default **`rank` on ratios**;
`SHAPE_COLS` gains **`tail_risk`**; `ENRICH_VERSION` added to the board cache key.

★ **`boom_prob`/`bust_prob` are worse than inert — they are four seasons stale (T22).** They are
`weekly_volatility(max(train_seasons))`, and `train_seasons` for a live season is `DEV_SEASONS`,
which ends at **2022**. So the 2026 board's boom/bust columns are the **2022** rates (100 % exact
match on the 39 % that join) and **292 of the 306 zeros are `fillna(0.0)`** — a player absent in
2022 is recorded as *never busting*, which is a fabricated safety claim, worst exactly for the
rookies a floor-seeker should most distrust. Frozen Phase-5 contract → logged, not edited; both
seats that weighted them now weight `tail_risk`.

### Step 3 — the three blind spots, all DERIVED (`role_share`, `role_delta`, `td_regression`)

The value hawk's bad picks were **blind spots, not mis-weights**: no objective over the 16.13 board
can avoid them, because `vbd` prices *how much* and never *how contested*, *which direction the
situation moved*, or *how much was touchdown luck*. The obvious sources are a depth-chart feed, a
research table and a modelling exercise; **none was needed** — the "derived-vs-curated" test is not
*"is this hard to look up"* but *"does a table we already ingest contain it"*, and three did.

**Every spot-check landed as predicted, stated before the numbers were read:**

| player | signal | value | percentile in position |
|---|---|---|---|
| DK Metcalf | `role_delta` | **−0.113** | **1st** (worst situation change on the board) |
| Dylan Sampson | `role_share` | 0.337 | 21st (a committee back) |
| James Cook | `td_regression` | +0.393 | 80th (TD-dependent) |

Coverage 99.5 % / 89.7 % / 89.7 %. ⚠ **Two of the three are partly a level restatement** —
`corr(role_share, vbd)` +0.88 RB, `corr(td_regression, vbd)` +0.63 RB — so a flat within-position
z would pay twice for the level and make "avoid TD regression" a tilt away from good players. The
value hawk prices them through a **neighbourhood-local** z instead. Fifth instance of level-vs-shape.

### Step 4 — `safe_floor` becomes *lowest downside*, not *highest floor*

`{floor +0.45, durability +0.30, tail_risk −0.40}`, `override={"rookie": −0.35}` (the fitted β is
+0.020, so `scale` cannot reach a meaningful negative), and a **`level_floor`** threshold so
"reliably useless" cannot win a downside contest. Both bars PASS:

- **spread** — drafted-pool `tail_risk` **−0.124 vs balanced, CI[−0.160, −0.088]**, clear of zero.
  This is the bar the seat previously *could not* fail honestly: "higher floor" was satisfiable by
  the broken column, and was satisfied by it.
- **disagreement** — `safe_floor` vs `reacher` differ on **48.7 %** of picks against a
  pre-registered floor of 33.3 %.
- **every knob moves something**: rookie z +0.050 → **+0.005**; sub-floor picks 12.8 % → **12.0 %**.

★ **`level_floor` had to be board-wide, and pool-relative measured as inert.** Inside a 40-player
ADP band the worst candidate is z ≈ −1.5 whoever he is, so a band-relative floor fires on somebody
at every pick and is just a level tilt — it moved nothing because the ADP term was already declining
those players. Board-wide, "below −0.6 sd of all RBs" is a fact about the player. Even then it is a
**rail, not a force** (1.4 points of pick share), and that is reported rather than tuned up.

★ **The ablation's control had a bug of its own**: scoring the guard-off arm against *its own*
`None` threshold reported a spurious 0.0 %. *A control has to be scored on the treatment's own
yardstick.*

### Step 5 — the reacher: direction first, then a budget

It was literally `Personality("reacher", temperature=2.2, width_mult=WIDTH_REACHER)` — **no
`signal_weights` at all**. The user's "these reaches have no basis" was a description of the code.
Direction: `override={"rookie": +0.45}`, `{cos +0.35, upside +0.25, tail_risk +0.20}`,
`hype_gain=2.5` (the 16.10 board + the 16.9 shock, inherited from the retired homer). Budget:
`ReachBudget` — tiers in ADP picks, counts re-derived from the draft log each pick so a
`DraftState.clone` cannot diverge, applied as a **filter before utility**.

**All four checks PASS:** max reach **1.06×** balanced (limit 2.0), **0/13 rounds** over the corpus
p95, direction moves 5 signals, budget binds.

★ **A count budget bounds how *often*, never how *far*** — and that gap was live: with only the
count tiers the seat's third permitted swing was a **78-pick** reach, over the realized human p95 on
11 of 15 rounds. `CORPUS_REACH_P95` (frozen, 1,144 drafts) is now part of the **mechanism**.
★ **And the first ceiling I derived was wrong by 6×.** Re-deriving `round` from
`ceil(pick_no/teams)` and picks from `drift*10` gave a round-15 "corpus p95" of **8.8** against
T15's published p90 of **52.3**, and duly failed the shipped seat. The panel carries its own
`round`; `mock._picks` is the one place the scaling lives. Related: `reach_profile` pools **|drift|**,
so its round-15 p90 is mostly elite players *falling* — **a ceiling on how far a manager may jump
cannot be read off a number that is mostly about players sliding.**

### Step 6 — the value hawk is the Phase-9 greedy in an opponent seat

Open decision #1 settled **measured, not argued**: within position `corr(vbd, adp)` = −0.955 RB /
−0.933 WR / −0.907 TE / −0.859 QB, so `pos_z(vbd)` deletes VBD's only non-ADP content (the
cross-position comparison) and a `signal_weights` value hawk is ADP with a sign flip. The seat now
runs `RiskModel.effective_rank` — marginal portfolio CE — on its own roster, inside a reach window,
with the step-3 context priced neighbourhood-locally.

**The window sweep is NOT RESOLVED and the tightest window ships.** 1.00× / 1.15× / 1.25× score CE
surplus **+386.0 / +391.6 / +399.1** at se ≈ 7.5 over 30 seeds; the argmax beats the tightest
eligible window by **+13.1 against a pooled se of 10.7**, i.e. inside 2 se. *An unresolved choice
does not buy itself a wider licence to reach* → `window_mult = 1.0`. Same shape as T15's
resolution-limited title objective.

★ **Descriptive, and the trap is sharpest here:** this seat maximizes our board, so scored on our
board it wins by construction. Also worth stating — its **mean reach is negative** (−1.5 to −1.8
picks): a value hawk mostly *waits*, it does not reach.
★ `assert_room_objectives` fails loudly when a `portfolio_ce` seat has no risk model, because
without it the seat silently becomes `balanced` wearing the value hawk's name and completes a legal
draft. *An inert thing still passes*, guarded.

### Step 7 — composition, and the full re-measure

`REALISTIC_ROOM` = 1 autopilot · 4 balanced · value_hawk · safe_floor · reacher · upside_chaser ·
chalk. Results are in the closeout table below.


### Step 7 results — 60 seeded drafts x 9 seasons, on the shipped measurement path

| bar | T15 shipped | 16.14R | verdict |
|---|---|---|---|
| **1** profile distance · round-1 mean | 0.2220 · 4.36 | **0.1156 · 3.70** | PASS (corpus 2.87) |
| **2** elite-fall p95 · past pick 10 | 17.0 · 28.5 % | 19.0 · **30.07 %** | **marginal FAIL** (ceiling 30.0 %) |
| **3** worst harvest excess | +0.21 sd | **+0.06 sd** | PASS (tol 1.0) |
| **4** 11.2 availability Brier | +0.0890 | **+0.0890** CI[+0.0803,+0.0996] | PASS — unchanged |
| **5** dispersion level error | +17.0 % | **+5.6 %** | PASS (tol ±20 %) |
| — seat faithfulness | 10.40 · 13.5 % mod · 19.6 % chalk | **9.38 · 27.8 % · 10.6 %** | corpus 7.62 · 54.3 % · 0.2 % |

**Four of the five bars improved, one of them substantially** — the 16.9 dispersion error is a third
of what T15 shipped, and the reach profile is half the distance from the corpus. The seat-population
gap T15 left open closed by roughly a third on every one of its three statistics, and — the point of
step 7 — most of that came from **composition**, not from the model.

**★ Bar 2 fails, and the honest number is that it is not distinguishable from its ceiling.**
30.07 % against a 30.0 % ceiling on n = 5,700, binomial se **0.61 pp** — the miss is **+0.12 se**.
The p95 half of the same bar passes (19.0 vs a 20.0 ceiling), and on the **2026 live board — the one
a user actually drafts against — the whole bar passes at 26.3 %**. It is reported as a marginal miss
rather than tuned into a pass: the ceiling was pre-registered in T15 and moving it, or reweighting a
seat until the number crosses it, is the exact anti-pattern 16.15 recorded ("turning the shock up to
pass a face-validity check tunes a calibrated parameter to a face-validity check").

**Direction of the miss is a genuine trade, not a regression to fix blindly:** the room now has one
autopilot instead of two, and an autopilot is the seat that *absorbs* elite players before they can
fall. Dropping one buys realism (autopilot is 0.2 % of real seats), profile distance, dispersion and
faithfulness, and costs ~1.5 pp of elite-fall share. Attribution measured separately rather than
asserted — see the composition A/B in `analysis/`.

**The mock reads right by eye, which is the bar that started all of this.** Round 1 is the consensus
top ten in near-ADP order (largest deviation 6.7 picks); rounds 2–3 carry realistic reaches (+13.6
Zay Flowers, +20.2 Terry McLaurin) against realistic falls (−9.1 Jaxon Smith-Njigba, −9.3 Jonathan
Taylor); rounds 14–15 are entirely K/DST and **every one of the ten teams finishes with a legal
lineup**. Nothing resembling the 42-pick reach or the five top-12 players falling past pick 30 that
opened the ticket. `analysis/mock_16_14R_picks.csv`.

**★ The T19 before/after report contains the session's most useful correction, and it is against my
own first reading.** The tempting summary is "the repaired `floor` column demotes the players the
user objected to". It does not: Zay Flowers goes from the 76th to the **85th** floor percentile,
Carnell Tate 64th → 72nd. What actually prices those picks is **`tail_risk`** — Quentin Johnston
85th percentile, Jaydon Blue 84th, DK Metcalf 76th — because the objection was about **width**, and
width is not floor. T19 repaired the input to "highest floor"; step 4 changed the objective to
"lowest downside". Both were needed and neither substitutes for the other. And the board now answers
back on one of them: Zay Flowers (ADP 25.6, mean 199, q10 98, `tail_risk` **15th** percentile) is a
high-floor, *narrow* outcome, so `safe_floor` taking him is defensible rather than a defect —
`analysis/t19_signals.csv` puts that in front of a human, which is how the ticket was found.

**Suite: 569 tests (was 549), ruff clean.** DEV-only; the spent lockbox and the frozen value stack
are untouched — 16.13/16.14 enrichment only *reads* them, and the one frozen column this session
diagnosed (`boom_prob`/`bust_prob`) was **logged as T22, not edited**.

### T16 closed, and the one thing 16.14R did not change

**T16 ✅ — a curated hype claim now expresses in a standard 15-round league.** The 16.10 done-bar
re-run at **15** rounds on the live 2026 board: **sign agreement 1.00** against a 0.75 bar,
elasticity 0.57 picks per claimed pick, mean |shift| 2.63 picks, **14 of 20 claims resolvable**.
T15's widening candidate band dissolved it exactly as that ticket predicted — where T16's own
evidence had been a *bit-identical* 30-draft result at 15 rounds. **Honest residue: 6 of the 20
claims still cannot express** (all on deep players), so the 18-round demonstration stays as the
fuller check rather than being replaced.

**What 16.14R deliberately did not touch.** The frozen value/distribution/optimizer/VBD/cost-report
stack: 16.13 enrichment only *reads* it, and the one frozen column this session diagnosed
(`boom_prob`/`bust_prob`, T22) was **logged rather than edited** even though the fix looks easy from
here. The spent 2023+2024 lockbox is untouched; every measurement above is DEV (2017–2024) plus the
2026 live board, which has no realized outcomes to leak.

### Step 6 addendum — the value hawk's context weights are not inert

Checked because the repo's own rule says a tilt must be *asserted to move something*, and the check
was missing from the first cut of the step. Over 12 seeded drafts, with vs without
`context_weights`:

| | `role_share` | `role_delta` | `td_regression` |
|---|---|---|---|
| with context | **0.721** | **0.182** | **0.179** |
| context OFF | 0.655 | 0.110 | 0.218 |

**Roster overlap between the two arms is 29.4 %** — the weights change roughly seven of every ten
players the seat takes, and all three signals move the intended way: it owns more of its players'
rooms, buys more improving situations, and carries less touchdown luck. Now a permanent part of the
step's verdict rather than a one-off measurement.

### The bar-2 attribution, measured rather than asserted

Same code, same four seasons (2021–24), same 40 seeds, **only the room mix differing**:

| room | elite past-10 | p95 | profile distance | dispersion err | median `pool_rank` | chalk share |
|---|---|---|---|---|---|---|
| T15's (`DEFAULT_FULL_ROOM`, **2** autopilot) | 28.72 % | 18.0 | 0.1176 | +10.4 % | 9.77 | 19.9 % |
| `REALISTIC_ROOM` (**1** autopilot) | **29.47 %** | 19.0 | **0.0927** | **+6.5 %** | **9.62** | **10.7 %** |

**The elite-fall cost is the composition change, and it buys four improvements.** Dropping one
autopilot removes a seat that *absorbs* elite players before they can fall, so the share rises
**+0.75 pp** — while profile distance falls 21 %, the dispersion error falls by a third, and the
chalk share nearly halves toward the corpus's 0.2 %.

⚠ **The +0.75 pp is itself only +0.51 se** (n = 1,880 per arm), so this attribution establishes the
*direction* and the *trade*, not a precise magnitude. Stated that way deliberately: the pooled
60-seed headline (30.07 % vs a 30.0 % ceiling, +0.12 se) is equally unresolved, and two unresolved
numbers do not add up to a resolved one. What is solid is the ordering — every other bar improved,
and the one that did not is inside its own noise on both measurements.

## The 2×5 mock re-run (2026-07-28) — three more objections, and the one board column the room never reads

**What was run.** The same 2×5 shape as the 2026-07-27 mock — **2 seats each of `autopilot` /
`balanced` / `safe_floor` / `reacher` / `value_hawk`** — but now with the *shipped* `value_hawk`
(16.14R step 6) rather than the run-local approximation, on the live 2026 FFC board (223 players +
16.13 enrichment). One showcased draft (room seed 20260728, draft seed 728) for the user's eye, then
**40 seeded drafts with the room reshuffled per seed** so personality is never confounded with slot.
Everything through the shipped engine: `mock.room_board` → `mock.full_room` →
`mock.simulate_room_draft` on the fitted 11.1 β, with the Phase-9 risk model attached for the hawk
seats. DEV-only; nothing written to `analysis/`. Driver: `steps/mock_2x5_diag.py`.

The user again reviewed the picks by eye and raised **three** objections. All three are real, one is
an outright bug, and the other two share a root cause that has been sitting in plain sight since T15.

### ★★ THE FINDING — an aggregate that pools *reaches* and *falls* cannot see a one-sided defect

Round-1 width **passes its bar**: mean |reach| **2.91** simulated against a corpus **2.87**, p90 6.21
vs 5.23. On that number the room is calibrated and there is nothing to fix.

Now ask where the consensus elite actually land:

| | corpus, ADP 1–2.5 (n=2,398) | sim: Bijan (ADP 1.6) | sim: Gibbs (ADP 1.8) |
|---|---|---|---|
| median landing | 2.0 | 2.0 | **4.0** |
| mean landing | 3.41 | 2.70 | **4.03** |
| p90 | 5.0 | 5.0 | 6.0 |
| **past pick 4** | **12 %** | 18 % | **42 %** |
| past pick 6 | 7 % | 2 % | 8 % |
| past pick 10 | 3 % | 0 % | 0 % |

The consensus #2 has a **median landing spot of pick 4** and clears pick 4 **42 %** of the time,
against a realized 12 %. The mean-|reach| bar cannot see it because **a reach and a fall have the
same absolute value**: every seat that jumps a player up is paired with an elite sliding down, and
the two cancel inside the mean. This is the T15 lesson — *an aggregate metric cannot see an
impossible event* — one level down. There it was aggregation over **drafts**; here it is
aggregation over **direction**, inside a metric that already passes. **Bars over |drift| need a
signed companion, and the natural one is a landing-spot distribution for the consensus top tier.**

The user's framing was more precise than the pooled number too — *"especially the first half of the
round"*. Split round 1 in half:

| | picks 1–5 | picks 6–10 |
|---|---|---|
| corpus mean abs (n≈5,600 each) | 2.41 | 3.48 |
| sim mean abs | **2.67** | **3.14** |

The corpus **rises** across round 1 (2.41 → 3.48) and the sim is **flat** (2.67 → 3.14, slightly the
wrong way). Same shape error T15 diagnosed at round grain, now visible *inside* round 1.

### ★★ THE CAUSE — width is modelled per **round**, never per **player**, and the board already carries the missing column

The shipped model has `WidthCurve(gamma=0.8)`: width scales with round depth, so **every round-1 pick
gets identical width**. But the FFC board carries a per-player consensus dispersion, and it is not
flat inside round 1 at all:

| Bijan | Gibbs | Nacua | Chase | CMC | JSN | ARSB | Taylor | Lamb | Jeanty |
|---|---|---|---|---|---|---|---|---|---|
| 0.7 | 0.8 | 0.8 | 1.0 | 1.3 | 1.6 | 1.4 | 1.7 | 2.1 | 2.5 |

**Nothing in the pick path reads it.** Across `src/fantasy_quant/draft/`, `stdev` appears only in
`mock.py:301`, where `sim_drift_panel` copies it onto the *output* panel for reporting. It never
enters a decision. Meanwhile 16.8 already found it from the other side — `adp_stdev` **+0.35/SD**,
*"where the crowd disagrees with itself, someone jumps"*, one of the four features that survived the
ablation. **The finding exists in this repo and was never fed back into the room.**

The corpus says it is the right scale, three ways (1,144 FFC drafts, 157,349 picks):

| `adp_stdev` band | n | mean stdev | mean \|drift\| | \|drift\| / stdev |
|---|---|---|---|---|
| ≤ 1.5 | 5,225 | 0.99 | 2.55 | 2.57 |
| 1.5–3 | 17,712 | 2.35 | 5.01 | 2.13 |
| 3–5 | 26,981 | 4.09 | 8.35 | 2.04 |
| 5–8 | 52,290 | 6.59 | 13.02 | 1.98 |
| 8–12 | 34,665 | 9.65 | 18.13 | 1.88 |
| 12–20 | 17,158 | 15.11 | 21.39 | 1.42 |
| > 20 | 3,318 | 23.40 | 24.38 | 1.04 |

1. **`|drift| ≈ 2 × adp_stdev`**, near-constant through the range that matters. (The decay above
   stdev 12 is **pool exhaustion** — T15's own finding, arriving independently here, which is a
   consistency check rather than a problem.)
2. **It is nearly as strong a predictor as depth**: Spearman(`adp_stdev`, |drift|) **0.484** vs
   Spearman(round, |drift|) **0.535** — and it is not the same information, because
3. **it separates inside the top of the board, where the round curve is structurally blind.**
   Restricting to rounds 1–3 and splitting by stdev tercile: **2.11 / 3.33 / 8.91** picks of drift.
   A **4.2×** spread the current specification cannot express, because Bijan (0.7) and Lamb (2.1)
   are both just "round 1".

**The recommended fix is one mechanism: a per-seat private board, `adp_seat = adp + κ_seat ·
adp_stdev · ε`, `ε ~ N(0,1)`, drawn once per seat per draft.** One scalar to calibrate against the
measured 2× law. It is fitted rather than declared — which matters, given how much of this repo's
history is a declared judgment that later measured as a level proxy — and it is **the same object
T15 handed forward** (*"the late-round 0.61× narrowness needs per-seat board perturbation, not
another width parameter"*) and 16.14R deferred. **Three open problems, one mechanism.**

⚠ **What NOT to chase.** The corpus has a far tail the sim has none of — p99 = pick **33** for an
ADP 1–2.5 player, 3 % past pick 10 (sim: 0 %, max 7). Before treating that as behaviour to
reproduce, check `days_to_board` and keeper/dynasty leakage: a consensus #1 going in round 4 is more
likely a post-snapshot injury or a contaminated room than a manager's choice. **The body is the
target; the tail is a data question first.**

### ★ Objection 2 — the T20 legality guarantee misses TE, and it is exactly one line

**12.2 % of seats (49 / 400) finish unable to field a legal lineup, and every single failure is a
missing TE.** QB, RB, WR, K and DST are never short.

| autopilot | balanced | reacher | safe_floor | value_hawk |
|---|---|---|---|---|
| **46.2 %** | 5.0 % | 5.0 % | 5.0 % | 0 % |

`DraftState.mandatory_needs` (`draft/simulator.py:149`) drops every position in
`slots.flex_positions`, and that tuple is `("RB", "WR", "TE")`. Its docstring is right for RB/WR and
wrong for TE:

> A FLEX slot is satisfiable by any of `slots.flex_positions`, so RB/WR/TE demand is never
> *mandatory*… a team short at RB still fields a legal lineup.

Being short one RB **is** survivable — the FLEX absorbs it. Being short at TE is not, because the
**dedicated TE slot** has no substitute. **TE is in `flex_positions` because a TE may fill FLEX, not
because anything may fill TE**, and the code reads the membership in the wrong direction. So T20's
deadline filter protects QB/K/DST and silently skips the only position that actually goes unfilled.

Fix: mandatory need = the full `base_demand()`; FLEX stays the only substitutable slot. Safe, because
the filter binds only when `picks_remaining <= sum(needs)` and each forced pick decrements the sum by
exactly one — so the invariant holds and it still binds late (worst case 8 picks out, in practice 3–4).
**T23.**

★ **The lesson is about how T20 was verified.** Its done-bar was *"60/60 seats finish with ≥1 K and
≥1 DST"* — the two positions the ticket was written about. It passed, and the same mechanism was
broken for a third position nobody thought to assert. *A guarantee stated as "no unfillable starting
slot" must be tested against the whole lineup, not against the slots that motivated it.*

### ★ Objection 3 — the reacher out-reaches `balanced` overall, but **not in rounds 1–3**, and that is by spec

The user's objection came off the showcased single draft, where `reacher` posted a lower mean reach
than `balanced` (+6.74 vs +10.22). **Over 40 drafts the ordering is the expected one:**

| | mean `pool_rank` | median | mean reach | reach, skill only |
|---|---|---|---|---|
| autopilot | 1.39 | 1.0 | −15.15 | −14.74 |
| safe_floor | 8.33 | 5.0 | +0.21 | +0.59 |
| value_hawk | 9.48 | 7.0 | +1.23 | +3.24 |
| balanced | 11.74 | 8.0 | +6.31 | +6.49 |
| **reacher** | **13.40** | **10.0** | **+8.39** | **+8.75** |

**Two method errors produced the apparent inversion, and both are ours:**

1. **A behavioural ordering was read off one draft** — 30 picks per personality. The repo already
   knows this (*"one draft is 10 picks per round"*, T15 step 0); it recurred because the
   *presentation* was a 15-round mean-reach table per personality, which invites exactly that read.
2. **Mean reach over 15 rounds is the wrong statistic.** `balanced`'s advantage in the single draft
   came almost entirely from R11–13 (+12.94), where "reach" is ADP noise — Tyler Allgeier at ADP 167
   taken at pick 119 scores **+48** and means nothing, because nobody else was taking Allgeier at 119
   either. Reported reach in R14–15 is also just *when* a seat takes K/DST. **`pool_rank` is the
   repo's own answer to this and should lead the per-personality summary**, split R1–13 / R14–15.

**But the objection found a real defect one round-range earlier than it was aimed:**

| mean `pool_rank` | R1–3 | R4–6 | R7–10 | R11–13 | R14–15 |
|---|---|---|---|---|---|
| balanced | **6.44** | 11.00 | 15.61 | 16.52 | 5.88 |
| reacher | **4.99** | 19.30 | 18.82 | 13.53 | 6.17 |

**In rounds 1–3 the reacher is more chalk than the average manager.** It only switches on at round 4.

That is `ReachBudget` doing exactly what it was specified to do on 2026-07-27 — `early_rounds=3`,
`early_max_picks=8.0`, `medium_from_round=3`, `large_from_round=5`, from *"a real reacher does not
open with one"*. **The defect is not the budget, it is that only `reacher` and `value_hawk` have
one.** Eight of ten seat types — including `balanced`, which is 4 of 10 in `REALISTIC_ROOM` — are
subject to no round ceiling at all, so `CORPUS_REACH_P95[0]` = 14.6 picks binds the seats that were
given discipline and not the seat that represents the average human. **The seat asked to be
disciplined looks tamer than the one that was not asked.** **T25.**

★ Note this is the *same* root cause as the round-1 defect above: a room-wide ceiling is
recommendation 1b there and the whole fix here.

★ **Why the reacher cannot simply be turned up in round 1.** Its direction channels are structurally
dead at the top of the board: `cos` (change of situation), `rookie`, `upside`, hype. Every consensus
elite is an established veteran with compressed within-position z-scores, so the signal bonus has
nothing to bite on and only `width_mult=2.0` is left — which is precisely the *"width with no
direction"* 16.14R step 5 existed to delete. **A reacher that reaches for something in round 1 needs
a channel that exists in round 1**, and the per-seat private board above is that channel. Do not
re-open this by raising `temperature` or `width_mult`.

### Recommended order (not yet executed — gated on the user under rule 7)

| | change | scope | risk |
|---|---|---|---|
| 1 | **T23** — TE in `mandatory_needs` | ~5 lines | low; a bug against a stated contract |
| 2 | **T25** — `round_ceiling` room-wide + report `pool_rank` by bucket | small | low, but it clamps a symptom |
| 3 | **T24** — per-seat `adp_stdev`-scaled private board | a full sub-step | this is the one that changes the model |

Item 3 will move T15 bars 1, 2 and 5 and the seat-faithfulness population, so it needs its own gated
sub-step with a before/after on the shipped measurement path — not a bolt-on to items 1–2.

---

## T23 / T25 / T24 (2026-07-28, session 7) — the room's width becomes a property of the *player*

The three tickets the 2×5 re-run opened, executed in the order that entry recommended: 1 → 2 in one
pass, then 3 as its own gated sub-step with a before/after. Four labelled artifacts, all produced by
one harness (`steps/mock_room_bars.py`) so each *after* column is comparable to its *before*:
`analysis/mock_room_bars_{baseline,t23,t25,t24}.json`, plus the seating-marginalized pair
`{baseline_shuffled,t24_shuffled}` and the calibration sweep `analysis/mock_t24_sweep{,_rep}.json`.

### T23 — the legality guarantee, stated over the whole lineup

One line: `mandatory_needs` exempted `slots.flex_positions`, and TE is in that tuple because a TE may
*fill* FLEX, not because anything may fill TE. Deleting the exemption took the share of seats that
could not fill a dedicated slot from **23.2 % → 12.3 %**, and the *avoidable* half — a slot the
season's board could actually have supplied — from **12.08 % → 0.03 %**. The residual is 2017-era
FFC boards carrying fewer than ten kickers or defenses for ten seats; `roster_legality` reports
avoidable and unavoidable separately rather than asserting a bar no policy can meet.

**Nothing else moved, and that was verified rather than assumed** (T20's register entry asks for
exactly this): round-1 mean **3.5242 → 3.5242**, bar 2 identical, bar 5 −5.99 % → −5.72 %. The drift
panel is offense-only, so deadline K/DST/TE picks are dropped on the measurement side.

### T25 — the ceiling every seat inherits

`ReachBudget` was attached to `reacher` and `value_hawk` only, so the corpus p95 bound the two seats
that had been *given* discipline and nothing bound `balanced` — 4 of 10 seats. `reach_budget=None`
now means **inherit `ROOM_CEILING`**, a ceiling-only budget with no count tiers and no early clamp
(the reacher's quiet opening is a spec, not a default to spread around). `unbounded_budget()` exists
for the A/B controls that genuinely measured an unconstrained seat, so an already-run done-bar keeps
meaning what it meant.

Every population statistic moved **toward** the corpus: `balanced` R1–3 `pool_rank` 6.36 → **5.98**
(overall 10.19 → **9.32**), `upside_chaser` R1–3 10.80 → **8.76**, median `pool_rank` 9.31 → **8.85**
(corpus 7.62), moderate share 28.8 % → **32.7 %** (corpus 54.3 %), profile distance 0.1052 →
**0.0894**. Unlike T23 this moves the bars, which is expected — it constrains eight seat types that
were previously unconstrained.

**The done-bar's ordering claim is not made.** It asked for `value_hawk` between `safe_floor` and
`balanced` and `reacher` last; what ships is `autopilot 1.00 < chalk 2.05 < safe_floor 3.37 <
reacher 4.91 < balanced 5.98 < upside 8.76 < value_hawk 10.09`. Both deviations are the ticket's own
analysis contradicting its own bar — the reacher's R1–3 quiet is the user's 2026-07-27 spec, stated
two paragraphs above the bar, and a bounded value argmax is the most deviant seat in the room by
construction. *A done-bar written from a symptom can contradict the fix it is attached to.*

### T24 — the prescription was rejected and its by-product was the fix

T24 named a mechanism up front (a per-seat `adp_stdev`-scaled **private board**) and called it *one
mechanism for three problems*. It was built — including the genuine defect it identified, that
`_prepare_board` dropped `stdev` so **nothing in `draft/` could read the crowd's own disagreement** —
calibrated on a grid, and then measured on a harness that marginalizes seating. It is
**monotonically harmful on the objection it was designed to fix**:

| seating-marginalized, elite (ADP ≤ 2.5) past pick 4 | κ = 0 | κ = 1 | κ = 2 |
|---|---|---|---|
| `WidthCurve.base` 0.70 | **18.8 %** | 19.7 % | 26.6 % |
| `WidthCurve.base` 0.50 / γ 1.0 | **11.2 %** | — | 23.4 % |

**★ Why, and this is the transferable part: at the top of the board `adp_stdev` is the same size as
the gaps it perturbs.** Bijan 0.7 · Gibbs 0.8 · Chase 1.0 sit about **0.2 picks** apart. A per-seat
draw of ±κ·0.8 picks therefore does not *create* tier structure — it **destroys the ordering that
was already there**, which is the exact mechanism by which an elite falls. The corpus law that
motivated it (`|drift| ≈ 2 × adp_stdev`, Spearman 0.484) is real, but it describes **realized drift**
— an outcome of ten seats interacting — and re-injecting it as a **per-seat perception** is a
different object. *A relationship measured on outcomes is not a specification for the mechanism that
produced them.*

**What fixed it was the knob added to support it.** `WidthCurve` gained `base`, splitting the width
**level** from the width **shape** (`width(round) = base · round^gamma`). They had been one number,
which is why T15 concluded *one knob cannot set both ends*. With two, round 1 halves while the late
board keeps 86 % of its width:

| 40 seeds, seating-marginalized | before | after | corpus |
|---|---|---|---|
| `WidthCurve` | `base 1.0 · γ 0.8` | **`base 0.6 · γ 1.0`** | — |
| **elite past pick 4** | 25.8 % **FAIL** | **15.3 % PASS** | 13.1 % |
| bar 2 · p95 / past-10 | 17.0 / 28.8 % | **16.0 / 25.2 %** | ≤ 20 / ≤ 30 % |
| bar 3 harvest | 0.00 sd | 0.00 sd | ≤ 1.0 |
| bar 5 dispersion | −7.1 % | **−11.4 %** | ±20 % |
| bar 1 round-1 mean | 3.33 | **2.64** | 2.87 |
| bar 1 profile distance | 0.107 | **0.089** | — |
| median `pool_rank` | 8.69 | **8.04** | 7.62 |
| moderate share | 33.7 % | **38.2 %** | 54.3 % |

**The cost, stated:** dispersion −7.1 % → **−11.4 %** — narrowing the top takes spread out of the
whole room and only `gamma` gives it back — comfortably inside bar 5. Everything else moves *toward*
the corpus, including bar 1's profile distance (0.107 → **0.089**), which is what separates `base
0.6` from the `0.5` that shipped an hour earlier: 0.5 overshoots to **tighter than real humans**
(11.3 % past-4) and pays 0.154 distance and −17.4 % dispersion for it. The 11.2 availability Brier is **bit-identical** (+0.0890, CI [+0.0803, +0.0996]).

### ★★ Three method failures this sub-step made, in order, each caught by the next measurement

1. **Calibrated on a 4-season subsample** for speed, and shipped `base 0.7 / κ 2.0` off it. The
   8-season sweep failed that config outright (20.4 % vs an 18.1 % ceiling). *Calibrate on the
   population the acceptance bar is measured on.*
2. **Measured on one fixed seating.** Every number was 5–7 pp optimistic: `0.5/1.0/2.0` reads 16.2 %
   fixed and **23.4 %** marginalized, and the round-1 half-split inverts between two room seeds
   (1.26 vs 0.82, same code). ⚠ **More seeds do not fix this** — the seating error is a bias, not a
   variance, until the seating itself is redrawn. → `--shuffle-room`.
3. **Moved two knobs together and credited the interesting one.** Every sweep row changed `base`
   *and* κ, so the width narrowing wore the private board's credit for three runs. The isolating row
   (`base 0.7, κ 0`) existed only because the verdict looked wrong — and it is the row that decided
   the ticket. *If two changes ship together, the one you were excited about gets the credit.*

**Also wrong, and worth recording as a rejected hypothesis:** the mid-sweep theory that a large κ
made seats saturate their reach ceiling (*"a constraint that binds every pick is the policy"*). It is
a real failure mode and now has a standing diagnostic (`ceiling_saturation`), but it **did not
occur** — 1.5–2.3 % of picks sit at the ceiling at every κ tested.

**A bar that cannot resolve its own question:** the round-1 half-split reads **0.54 / 0.82 / 1.11 /
1.22** across measurement configurations of essentially the same room, because a handful of large
first-half reaches dominate a mean over ~1,600 picks. The landing **share** (n ≈ 640) is the usable
bar; the rise is demoted to a diagnostic until someone gives it a trimmed or median-based estimator.

## The mock-drafter completion audit (2026-07-29) — three open tickets closed, and two of the three had the wrong cause on file

A full audit of the mock drafter after the T23/T25/T24 session, then everything the audit found
still open. The shipped room itself needed no model change — the arc that started with the live mock
(T15 → 16.14R → T23/T25/T24) was complete and its five bars pass — so this session is about the
three register entries that were still open **behind** it, all of which reach the board a human
drafts from: **T13** (the cloud is not reproducible), **T18** (the profiles' reach is a join
artifact), **T22** (boom/bust are four seasons stale). All three are ☑. One new entry, **T26**, is
opened and deliberately not fixed.

**597 tests (was 587), ruff clean.** The frozen value stack, the spent lockbox and the fitted β are
untouched; nothing here refits anything.

### T22 — the column was not latent, it was on screen

The entry said "who is affected: nobody today", on the reasoning that no personality *weights*
`boom_prob`/`bust_prob`. That reasoning missed the simplest consumer there is: `steps/mock_draft.py`
**prints** them, in a `.2f` that reads like a measurement, every time the human is on the clock. On
the live 2026 board that meant the drafter was told **Bijan Robinson, Jahmyr Gibbs, Puka Nacua,
Jaxon Smith-Njigba and Ashton Jeanty never boom** — `boom_prob` exactly 0.000 for all five, because
none of them was in the league in 2022, which is where `max(train_seasons)` lands for any live
season.

★ **A column's consumers are not only the models that weight it.** The audit that judged this latent
looked at `signal_weights` and at nothing else; the display layer is a consumer, and on a
human-in-the-loop tool it is the *only* consumer that can be wrong at the user directly.

The fix is read-only and stays out of the frozen contract: `enrichment.live_volatility` measures the
same rates on **season − 1**, `volatility_source` picks that season **from the `weekly` table rather
than from a constant** (the defect was a constant that fell behind the data, so the repair must not
introduce another) and asserts the lag is ≤ 1, and unseen players stay **NaN** rather than becoming
a confident zero.

| 2026 offensive board | frozen (2022 rates) | live (2025) |
|---|---|---|
| `bust_prob` exactly 0 | **56.0 %** | **8.2 %** |
| `boom_prob` exactly 0 | ~65 % | **18.5 %** |
| corr(frozen, live) | — | **0.026** |

**0.026 is the number that matters.** The frozen column is not a *stale* version of the live one;
four years out, it is unrelated to it. Fifty players it calls "never busts" bust in more than a
fifth of their 2025 weeks — Breece Hall, Ladd McConkey, Malik Nabers, Rome Odunze.

**The sweep the entry asked for, completed:** exactly two instances of the pattern *"a live season
reads a **covariate** from the newest training season"* have ever existed — T17's availability and
T22's volatility. Every other `DEV_SEASONS`-defaulted `train_seasons` in `src/` is a **fit**, where
training on strictly-prior seasons is the PIT discipline working correctly. *The pattern to sweep
for was never "`max(train_seasons)`" as a string; it is "a level read where a coefficient was
intended".*

### T13 — the reproducibility bug was not in the random number generator

The register's suspect was the Iman–Conover permutation in the Phase-8 coupling, on a good piece of
evidence: marginals near-invariant while the per-player assignment moved is exactly what a reshuffle
looks like. It is also exactly what an input wobbling **below the noise floor of every aggregate you
were watching** looks like. Ruled out in order, cheapest first: row order (identical across
processes — nothing is being reordered), `PYTHONHASHSEED` (no effect), BLAS/OpenMP threads (no
effect), and then **DuckDB threads — which fixed it completely**.

A parallel `SUM`/`AVG` over floats adds its partitions in whatever order the threads finish, and
floating-point addition is not associative. The training frames therefore differed in their last
bits between processes; the QuantReg and hazard coefficients differed at ~1e-11; and the sampler,
which was innocent throughout, mapped that onto per-player draws you could see. `db.deterministic_reads`
pins the assembler's reads to one thread; three fresh interpreters now agree **bit-for-bit**
(`steps/t13_reproducibility.py`). Measured cost: **negative** — 10.2 s → 9.1 s, because these
queries are small enough that thread coordination costs more than it buys.

★★ **The durable lesson: the noisy stage is not always the stochastic one.** Every candidate
explanation on file involved randomness (a permutation, a seed, an rng); the cause was arithmetic in
a database. And the prescription in the register — *thread an explicit seed through the coupling* —
would have been implemented, tested, and would not have worked.

This changes no model. The pinned digest equals one of the three unpinned runs measured before the
fix; the dress rehearsal's 75.5 ↔ 76.5 % was always the same result twice.

### T18 — when the sign flips, it was never a behaviour

`sleeper_manager_profiles.avg_reach` reported a mean **QB reach of +91.9 picks**: each pick's ADP
minus its slot, where the ADP came from one pooled board and the picks came from drafts of every
size, scoring and format in a 7,699-draft corpus. Rebuilt against **each draft's own board** over
the redraft-eligible subset (`sleeper.redraft_reach` → `drift_panel.manager_panel`, reusing the
eligibility filter and per-draft board resolution that already exist rather than re-deriving them):

| | old (pooled board, picks) | new (own board, rounds) |
|---|---|---|
| mean \|reach\| | **35.8** | **0.776** |
| range | −532.8 … **+1411.7** | −10.8 … +10.5 |
| mean | +24.8 | +0.008 |

★ **The decisive detail is the sign.** Scored properly, quarterbacks go **later** than consensus
(−0.576 rounds), not ninety picks earlier. A quantity that reverses direction when you fix its
reference was never a noisy estimate of the thing it was named after — it was a different quantity
wearing that name. The column is therefore **deleted rather than repaired in place**
(`avg_reach_rounds` + `n_reach_picks` replace it, in stated units), because a silently redefined
column is how F.5's `scoring="ppr"` and T19's `floor` both travelled. `validate.manager_reach_gate`
(±2 rounds) now guards it in the health report — the gate the entry asked for by name, and the
reason it exists is that every individual step of the broken computation was correct.

### T26 — the sibling defect, measured and left alone on purpose

The same audit found the same contamination class one column over: `pos_share_*` is counted over
**all** formats while `build_choice_frame` fits on redraft only, and `mgr_lean` — a live Tier-B
feature of the shipped β — is share-minus-mean over that pooled table (pooled QB share 13.65 % vs a
redraft 11.22 %). It is **not** fixed here, and the reason is the repo's own rule: changing it
refits β, and β's scale is what `WidthCurve`/`AdpSpec` were calibrated against over two entire
sessions. *A coefficient is not transportable without its controls* — and that applies to the
controls' own controls. Measured first so the decision is informed rather than deferred: per manager
the two scopes differ by a mean **0.83 pp** of QB share (median 0.00, >5 pp for 3.3 %), and the
pooled baseline enters as a per-position constant that position dummies largely absorb. Logged as
**T26**, to be done with the next 11.1 refit.

### The room after all three — re-measured, not assumed

`steps/mock_room_bars.py --label verify_20260729 --shuffle-room --seeds 40`, the same harness and
the same seating-marginalized protocol as the shipped `t24_shuffled` sheet, on the rebuilt
(`v3-t22-live-vol`) boards:

| bar | shipped (`t24_shuffled`) | after | |
|---|---|---|---|
| 1 profile distance / round-1 mean | 0.0894 / 2.64 | **0.0894 / 2.64** | PASS |
| 2 elite p95 / past-10 | 16.0 / 25.24 % | **16.0 / 25.24 %** | PASS |
| 3 autopilot harvest excess | +0.00 sd | **+0.00 sd** | PASS |
| 5 dispersion vs corpus | −11.4 % | **−11.4 %** | PASS |
| landing gate (top band past pick 4) | 15.3 % vs 13.1 % | **15.3 %** | PASS |
| legality: illegal / avoidable | 12.33 % / 0.11 % | **12.31 % / 0.11 %** | — |
| median `pool_rank` (corpus 7.62) | 8.04 | **8.07** | — |

**The two numbers that moved are the tell that this was measured rather than asserted.** Median
`pool_rank` 8.04 → 8.07 and one seat's legality flipping (444 → 443 of 3600) are the T13 pin landing
on *one* draw of a cloud that used to wobble: `floor`/`upside`/`tail_risk` are built from the
quantiles, so the seats that weight them see a board that differs in its last digits. Every gated
bar is unchanged to the digit, which is the expected result — the enrichment gained columns no
personality weights, and T18 rewrote a table the fitted model does not read.

The interactive drafter was then run end to end on the live 2026 board (seat 7, `REALISTIC_NINE`,
15 rounds): a legal roster in every slot including K and DST (T23's guarantee, visible), the
elite-fall readout at mean slot 7.2 for the consensus top-12, and BOOM/BUST columns that now read
2025 rather than 2022.

## The all-personality walkthrough (2026-07-30) — the simulator is finished; the seam is not

**Method.** One full 15-round draft with a personality in **every** seat — `mock.full_room(REALISTIC_ROOM,
n_teams=10, seed=17)`, `mock.simulate_room_draft(..., seed=0)`, live 2026 FFC board (snapshot
**2026-07-24**, 223 draftable players, `include_dst` on), `value_hawk` given the Phase-9 risk model,
λ = 0.01. Seats after the shuffle: T1 balanced · T2 autopilot · T3 balanced · T4 reacher ·
T5 upside_chaser · T6 safe_floor · T7 balanced · T8 chalk · T9 value_hawk · T10 balanced. Scored
through the Phase-10 season sim (400 worlds, 14-week reg + 6-team playoff). Artifacts:
`analysis/mock_walkthrough_20260729_{picks,teams,seats}.csv`.

This is the **fully-simulated** ten-personality harness (`mock.full_room`), not the nine-plus-a-human
CLI. Different question: the CLI is the by-eye bar for *a human in the room*; this one asks whether the
room is a coherent product when nobody is holding it.

### Four suspicions that did not survive measurement — record them, they are the room's credit

Each of these started as a defect I expected to find, so they are worth more than the ones that held.

1. **The QB market is not broken.** By eye it looked wrong: 17 QBs drafted for 10 teams, seven seats
   doubling up, Lamar Jackson (proj 315) available at pick 75 while WRs projecting 173–205 went ahead of
   him. Against **333 realized 10-team/15-round complete human Sleeper drafts** the medians are
   WR 53 · RB 45 · **QB 16** · TE 15 · K 9 · DEF 10, against the sim's 55 · 42 · **17** · 16 · 10 · 10.
   Six positions in line simultaneously. *Humans also draft ~16 QBs in a 15-round 10-teamer.*
2. **The reach mechanisms are legible in a single draft.** `reacher` spent its `ReachBudget`
   **exactly** — 3 of 3 swings (>25 picks: Dobbins +37.4 R6, Goff +30.2 R7, Nailor +38.8 R10) and 5 of
   5 leans (8–25: Swift R4, Tuten R5, Kincaid R12, Kyler R13, Buffalo R14) — with a **rounds-1–3 max
   reach of −0.1** against its 8-pick clamp. `upside_chaser`, which inherits `ROOM_CEILING` (ceiling
   only: no count tiers, no early clamp), reached **+11.3 in round 2**, which the reacher's clamp
   forbids outright. Two different budget mechanisms, both visible, in one draft.
3. **Elite fall is on the shipped distribution.** All twelve consensus top-12 gone by pick 15; 3 of 12
   past pick 10 = **25.0 %** against the committed sim's 25.2 % under a 30 % ceiling; worst fall
   Jonathan Taylor ADP 7.7 → pick 15.
4. **The behavioural fit is not a stale extrapolation.** 70,614 choice groups over **9 seasons**; the
   human corpus spans 2017–2026 with the bulk in **2021–25** (1,079 human drafts in 2025 alone). The
   "2017–20 β on a 2026 board" worry was checked and is unfounded.

Internal consistency also holds: title probabilities sum to **1.000**, playoff to **6.000**; all ten
rosters legal (1 K + 1 DST each, every K and DST in rounds 14–15); and the room's mean `tail_risk`
ordering is **monotone across seven seat types** — value_hawk −0.260 · safe_floor −0.090 ·
chalk −0.078 · balanced −0.010 · autopilot +0.013 · reacher +0.052 · upside_chaser **+0.152**.

### ★★ THE FINDING — the board a human reads is not the board the seats optimize (T27)

`steps/mock_draft.py` prints `PROJ` = `proj_points` (consensus, re-scored full-PPR). Every seat's
utility, and `value_hawk`'s entire objective, run on `base_value` = `ce_vbd` = Phase-5 CE minus
positional replacement CE. On the live 2026 board:

| QB | `proj_points` | Phase-5 `mean` | haircut | `sd` | `ce_value` | `vbd` | `base_value` |
|---|---|---|---|---|---|---|---|
| Josh Allen | 360.9 | 264.8 | 0.27 | 94.9 | 174.7 | +70.0 | +55.2 |
| Drake Maye | 316.5 | 261.3 | **0.17** | 85.6 | 187.9 | +25.6 | **+68.5** |
| Jalen Hurts | 315.2 | 249.6 | 0.21 | 89.0 | 170.4 | +24.3 | +51.0 |
| Lamar Jackson | 314.8 | 221.1 | 0.30 | 93.5 | 133.8 | +23.9 | +14.3 |
| **Jayden Daniels** | **313.4** | **137.1** | **0.56** | 109.2 | 17.8 | +22.6 | **−101.6** |
| Joe Burrow | 299.3 | 162.5 | 0.46 | 99.3 | 63.8 | +8.4 | −55.6 |
| Trevor Lawrence | 290.8 | 246.0 | 0.15 | 85.5 | 172.9 | 0.0 | +53.4 |
| Kyler Murray | 261.9 | 127.3 | 0.51 | 100.0 | 27.3 | −29.0 | −92.1 |

**Maye and Daniels are 3 points apart on the screen and 170 apart in the number that decides every
pick.** A user reading that board concludes the tool is broken.

**The level is intended; the dispersion is the defect.** Per-position mean haircut
(`1 − mean/proj_points`): **QB 0.28 · RB 0.33 · WR 0.28 · TE 0.30**. That *is* Phase 4.4's measured
level optimism (bias 0.575) and the lockbox's 0.62, working exactly as designed. What is new is the
**spread** — QB 0.15–0.56 (sd 0.12), RB 0.16–0.55, WR 0.15–0.58, TE 0.17–0.46 — and the fact that
nothing on screen explains which players get cut.

**⚠ Decompose before diagnosing — I got this wrong on the first pass.** The gap reads like a variance
penalty (λ = 0.01, QB sd up to 109.2 ⇒ λ·Var ≈ 119), and it does not reconcile: Allen `vbd` +70.0 →
`base_value` +55.2 (a 15-point gap) while Daniels +22.6 → −101.6 (124 points). The arithmetic only
closes once you notice `base_value = ce_value − ce_replacement(pos)` with `ce_replacement(QB)` = 119.4
on this board, and that `ce_value` is built on the **Phase-5 mean**, not on `proj_points`. So **two**
channels move it: the T3 availability channel inside the mean (`avail_p`, `rho`, `crater_avail`, the
cohort prior) and then λ·Var. A one-channel story fits neither end.

**The mechanical half, and it bit immediately.** `proj_points` is **not** in
`simulator.PASSTHROUGH_COLS`, so `_prepare_board` drops it — `st.roster()` and `draftable_pool` never
carry it. `steps/mock_draft.py` re-attaches it by hand in `cmd_start` (correctly, with a comment saying
it is display-only). Writing a fresh driver for this walkthrough reproduced the trap on the first run:
**`-` for all 150 picks.** `optimizer.attach_value` adds only `base_value` and `value`.

**★ This is T22's lesson one level up.** T22 sat on file as "latent — no personality weights it"
while `mock_draft.py` was *printing* it. *A column's consumers are not only the models that weight it.*
`proj_points` is the same defect on a much bigger number: it is the **first** thing a human reads.

### ★ The second finding — a sum over a roster is not a forecast of a lineup (T28)

`optimizer.team_value` is `Σ base_value` over all 15 roster rows; `portfolio_value` adds the covariance
cross-term and nothing else. **`grep -n "starters" draft/optimizer.py` returns nothing** — there is no
slot logic in the value path at all. So on a 1-QB roster the second quarterback is priced at full
weight, in both directions:

| team | seat | QB2 | contributed `base_value` |
|---|---|---|---|
| T1 | balanced | Caleb Williams | **−101.6** |
| T4 | reacher | Kyler Murray | **−92.1** |
| T5 | upside_chaser | Patrick Mahomes | −55.6 |
| T3 | balanced | Jalen Hurts *(taken second)* | **+51.0** |
| T9 | value_hawk | Jaxson Dart | +33.1 |

Room total `base_value` **1,938**; the QB2 line nets **−122**. Those players sit on a bench and cost
their teams nothing real.

**Measured consequence.** Spearman against Phase-10 title probability over the ten teams:

| metric | ρ vs title | ρ vs playoff |
|---|---|---|
| starting-nine Phase-5 `mean` | **+0.915** | +0.830 |
| `portfolio_value` (CE) | +0.758 | +0.733 |
| `team_value` (VBD) | +0.685 | +0.661 |
| roster total consensus proj | +0.624 | +0.552 |
| starting-nine consensus proj | +0.455 | +0.394 |

The clean cases: **T4 reacher is 9th of 10 on VBD, 3rd of 10 on starting-lineup projection, 9th on
title** (it is charged ~92 points for Kyler Murray sitting); **T1 is 7th on VBD and 2nd on title.**

**It matters twice.** `portfolio_value` is the cost report's headline, so a preference that buys depth
is priced as though the depth plays. And `value_hawk` **optimizes** it (`objective="portfolio_ce"`), so
this steers picks — Dart as QB2 at 9.09 is the visible instance. **The metric is correct as what it was
built to be** ("value over replacement, independent players"); it acquired a second meaning by being
the only team-level number anyone printed.

### Two smaller ones

- **T29 — bare absolute probabilities.** Drivers print `playoff 0.685 title 0.140`. The lockbox
  established title Brier **0.088** with on-diagonal reliability (ordering + championship calibration
  hold) but playoff Brier **0.240** *marginal*, unconditional coverage 72–77 %, and a residual sim level
  bias of **−113 pts/team** that κ cannot remove because κ is mean-preserving. The least trustworthy
  number is printed the most confidently. Fix: provenance, and lead with **fair-share multiple**
  (`title_prob · n_teams` — T9's 0.170 reads **1.70× fair share**), which is immune to the level bias.
- **T30 — the autopilot seat's share.** 1 of 10 seats against **0.2 %** of realized seats, and it is
  the seat that manufactures the spill: mean `pool_rank` **1.77**, median **1.0** (usually *literally*
  the top of the board), harvest **+11.7 picks**, the largest in the room; highest starting-lineup
  projection (2,009) on a 3rd-place title probability. 16.14R cut it from two seats **on this exact
  argument** and stopped there, and bar 3 passes at +0.06 sd — so this is a composition question that
  has never been argued in writing, not a known defect.

### One negative result worth keeping — a seat's spec is not readable off 13 picks

`chalk` and `safe_floor` are built to differ (width-only vs a risk objective), and the room-level
ordering confirms the direction. But **the two are not separable in one draft**: mean `tail_risk`
−0.078 vs −0.090, mean `floor` 0.023 vs 0.034, and `safe_floor` took **3 rookies to chalk's 1**,
including Omarion Hampton at `floor` −0.35 / `tail_risk` +0.40 — straight against its own weights. That
is the softmax sampling, and it is consistent with what the code already documents: the durability
weight's gap to `balanced` measures as noise around zero, which is why its done-bar A/Bs the weight
against *itself-off* rather than against `balanced`. What *is* legible in one draft is the
**construction** — safe_floor took two top-12 QBs (Lamar 8.05, Herbert 7.06) and two established TEs
(Loveland 6.05, Kelce 11.06) where chalk waited (Bo Nix 13.08, Kittle 12.03).

### Verdict, and what it schedules

The room *simulation* is finished: it was re-verified to the digit on 2026-07-29 and every by-eye bar
posed to it here came back clean. It is **not a shippable product**, for two reasons of different kinds
— the seam above (T27/T28, both fixable in the engine + CLI), and the fact that Phase 14 does not exist
and Phase 17's format generalization does not either, both of which are *scheduled*, not defects.
**Session H.5 (T27→T28→T29→T30) is inserted ahead of Session I** on that basis;
`docs/BUILD_PLAN.md` §"Session H.5" holds the steps and the pre-registered bars B1–B6.

---

# Session H.5 — the mock-drafter value seam (2026-07-30)

*T27 · T28 · T29 · T30, run straight through (the §3.7 sub-step gate waived by the user for this
session). Four decisions were taken up front: switch `value_hawk` to a starter-aware objective **with
the full T24 treatment**; on a pre-registered bar failing, **record it, open a ticket, keep going, and
chase the cause**; ship a T30 composition change only if every bar holds or improves; leave the tree
uncommitted.*

**The two hard bars held and the two falsifiable bars both failed.** That is the shape of the session:
nothing that was supposed to stay still moved, and both numbers that were allowed to come back negative
did. `analysis/session_h5_seam.json` carries all six.

| bar | what it asked | result |
|---|---|---|
| **B1** | the four value-chain columns reach the drafted-range board | **PASS** 183/184 (Brandon Aiyuk has no upstream projection and prints `-`) |
| **B2** | `spearman(haircut, games_played_mean) ≤ −0.50` per position, live board | **FAIL at RB** (−0.288); QB −0.902 · WR −0.538 · TE −0.838 |
| **B3** | the room bar sheet is bit-identical | **PASS** — every field, including the 2026 readout |
| **B4** | `starter_value == team_value` on exactly the starting nine | **PASS** |
| **B5** | `spearman(starter_value, title) > spearman(portfolio_value, title)` | **FAIL** −0.0230 CI[−0.0407, −0.0055] over 200 drafts |
| **B6** | the frozen cost report is bit-identical | **PASS** — diffed against a git worktree at the session-start commit |

## T27 — the value chain is on the board, and putting it there found a live-board defect

Shipped as specified: `proj_points`/`base_value` joined `PASSTHROUGH_COLS` (`mean` was already there),
`mock.room_board` attaches `proj_points` **outside** the parquet cache boundary so no `ENRICH_VERSION`
bump and no 9-season cold rebuild was needed, the hand-rolled re-attach in `cmd_start` is deleted, the
CLI board leads with `PROJ · MEAN · AVAIL · BV`, and `mock_draft.py why "<player>"` prints the chain.
On the live board it reproduces the ticket's own headline exactly:

```
=== Drake Maye (QB, ADP 63.3) ===          === Jayden Daniels (QB, ADP 86.9) ===
  consensus projection      316.5            consensus projection      313.4
  x projected availability   14.4 of 17      x projected availability    7.7 of 17
  = Phase-5 season mean     261.3            = Phase-5 season mean     137.1
  - lambda*Var              -73.3            - lambda*Var             -119.3
  - replacement CE at QB   -119.4            - replacement CE at QB   -119.4
  = BASE_VALUE              +68.5            = BASE_VALUE             -101.6
```

**170 points apart, and the reason is 14.4 games against 7.7.** The board view carries the same
explanation without the command: Omarion Hampton reads `PROJ 264 · MEAN 140 · AVAIL 9.2 · BV −1`.

### ★ The divergence nobody had looked for: the interactive room was not the shipped room

Found while wiring the risk model in. `steps/mock_draft.py` built its nine opponents through
`personalities.make_room_pick_fn`, which had **no `risk` parameter**, while the batch harness used
`mock.full_room_pick_fn`, which does. So `value_hawk` ran the Phase-9 greedy in **every batch
measurement in the repo** and the plain behavioural softmax in **every human mock** — it was
`balanced` wearing the value hawk's name, exactly the failure `assert_room_objectives` was written to
prevent. The guard could not see it because it only ran in the other builder. Fixed by moving
`assert_room_objectives` down into `personalities.py` (re-exported from `mock`, so no caller changed)
and giving `make_room_pick_fn` the same routing; the two builders now differ only in the `team → seat`
mapping they were split over in the first place.

**The lesson generalizes T22's**: *a guard that does not run on the path a human uses is not a guard.*
T22 was "a column's consumers are not only the models that weight it"; this is the same sentence about
assertions.

### ★ B2 FAILED — and the failure is a real live-board defect, not a display artifact

Pre-registered at `ρ ≤ −0.50` per position. Measured on the drafted range (top-180 ADP):

| season | QB | RB | WR | TE |
|---|---|---|---|---|
| **2026 (live)** | −0.902 | **−0.288 FAIL** | −0.538 | −0.838 |
| 2024 | −0.898 | −0.594 | −0.681 | −0.812 |
| 2022 | −0.643 | −0.716 | −0.773 | −0.662 |

So the level correction *is* explained by projected availability — on every historical board at every
position, and on the live board at three of four. **The live board is the outlier, and off the drafted
range it is far worse than the headline suggests:** over the whole 2026 value index, **22.8 % of rows
carry a *negative* haircut** (Phase-5 `mean` **above** the consensus projection, which is structurally
impossible for a level correction) against **0.4 % on 2024**, and the per-position correlation flips
sign entirely — QB **+0.474** with **59 % negative haircuts**, RB +0.225 / 42 %, TE +0.237 / 33 %.

**Cause, diagnosed rather than guessed.** Consensus prices **role**; our level correction prices
**availability**. For a player consensus expects to start, the two coincide and the identity holds. For
a projected backup they do not: consensus says 22 points because he sits behind someone, while the
Phase-5 level — with no prior-season basis to shrink toward on a live board — hands him a starter-ish
per-game rate multiplied by ~11 expected games. The worst offenders are exactly that shape: a QB at
`proj 22.3 → mean 102.9, sd 78.2` (sd ≈ mean is the fingerprint of a distribution built on nothing).
Conditioning on "consensus thinks he starts" (`vbd ≥ 0`) repairs the failing cell outright — 2026 RB
**−0.288 → −0.599**, WR −0.538 → −0.912 — which is the confirmation: the break is at the role
boundary, not in the metric.

Two checks that ruled out the obvious alternatives: **rookies are not the cause** (non-rookie RB ρ is
−0.32, and the worst offender, Ray Davis, is not a rookie), and the deep-board rows are not a small
tail (22.8 % of the index).

**Not fixed here** — it is a modelling defect and this was a display session. Logged as **T31**, with
the gate shipped **red** rather than softened: `validate.value_scale_gate` asserts the pre-registered
−0.50 on the drafted range and reports the whole-index numbers beside it. The population choice is
stated in the gate's own docstring so the exclusion is visible; the whole-index figures are in the
artifact, not hidden by it.

## T28 — closed as a LABELLING FIX, because its own pre-registered bar said so

`optimizer.starter_value(roster, value_index, slots)` ships as a **second, labelled** metric — never
an edit to `team_value`, whose numbers are the frozen cost report's input. It reuses
`simulation.season.lineup_points_matrix` (the Phase-10 solver) rather than writing a third lineup
solver, and the pick-path fast form `starter_marginal` is regression-tested against it on 120 random
rosters. Every team-level surface now prints both, labelled **STARTABLE** vs **CAPITAL**.

**B5 failed, significantly and in the opposite direction.** Over 200 seeded drafts × 10 teams, seating
reshuffled per seed, scored against the Phase-10 title probability:

| metric | mean per-draft Spearman |
|---|---|
| `team_value` (slot-blind sum) | **+0.8382** |
| `portfolio_value` (the shipped headline) | +0.8202 |
| `starter_value` (T28) | +0.7971 |
| `starter_mean` (the walkthrough's +0.915 metric) | +0.7920 |

`starter_value − portfolio_value` = **−0.0230, CI[−0.0407, −0.0055]**. The walkthrough's **+0.915 for
starting-nine Phase-5 mean did not replicate** — it was one draw of ten teams, and the spec said so in
advance.

### ★ Why the slot-blind sum wins: in a sim with injuries, the bench is load-bearing

Chased with the collected data rather than argued. **Bench value alone predicts title probability at
+0.711 (sd 0.175), positive in 100 % of the 200 drafts.** Sweeping the blend
`starter + w·(team − starter)` — which is exactly the knob the `RiskModel` now carries — puts the
maximum at **w = 0.90 (+0.8399)** against the shipped **w = 1.0 (+0.8382)**, a difference far inside
the noise, with the curve flat from 0.7 to 1.2 and **w = 0 the worst point on it**.

The Phase-10 sim draws per-player availability, so a starter who misses games is replaced from the
bench. Pricing bench depth at zero throws away real information about a roster's title odds. **The
slot-blind sum was never wrong as a *predictor* — it is wrong as a *display*, and those are different
claims.** The per-seat table shows why the display claim still stands: the gap
(`capital − startable`) is **negative for every seat except `value_hawk`** (upside_chaser −229.5,
balanced −171.5, autopilot −144.9 … **value_hawk +152.0**), because only the seat that *maximizes* the
slot-blind sum accumulates startable-elsewhere value on its own bench. That is the Jaxson-Dart-at-9.09
objection, and it is a seat-dependent reporting distortion, not a predictive one.

**So `value_hawk` keeps `objective="portfolio_ce"` and `bench_weight` stays 1.0.** The user's chosen
option was to switch it with the full T24 treatment; the T24 treatment was run (below) and the
pre-registered bar that authorises the switch failed first, so the switch is not shipped. The knob is
in the code, default-off and nesting exactly (`bench_weight=1.0` re-runs the greedy pick-for-pick,
asserted in `test_phase9`), so re-asking the question costs one flag.

## T29 — no bare absolute probabilities

`simulation/season.py` gained `PROB_PROVENANCE`, `fair_share`/`playoff_fair_share`,
`provenance_lines` and `assert_probability_sums`. Every driver that prints a probability now leads
with the **fair-share multiple** — a 0.170 title probability in a 10-team league reads **1.70×** —
because the sim's documented −113 pts/team level bias moves all ten teams together and therefore
cancels in a ratio to the uniform while surviving in the percentage. The caption carries the *weak*
numbers, not the flattering one: lockbox title Brier 0.088 on-diagonal **and** playoff Brier 0.240
recorded as marginal, plus 72–77 % unconditional coverage. `mock_draft.py summary --odds` is the new
human surface and asserts the structural identity (titles sum to 1.000, playoff berths to 6.000) every
time it prints.

## T30 — the autopilot seat's share, argued: the swap wins on realism and loses on two reach bars

The A/B the ticket asked for: swap the single `autopilot` seat for a **near**-autopilot (`chalk`:
zero-out overrides, cooled softmax at temperature 0.6, `width_mult` 0.55 — it already sat between
`autopilot` and the room at `pool_rank` 3.38), seating-marginalized over 40 seeds × 8 seasons ×
10 seats, on the shipped measurement path. `analysis/mock_room_bars_t30_chalk_swap.json`.

**Every gate passes in both rooms.** The trade is one-sided by category:

| | baseline | chalk-swap | corpus | verdict |
|---|---|---|---|---|
| **chalk share** (`pool_rank` < 2) | 11.0 % | **2.4 %** | 0.2 % | closes **79 %** of the gap |
| **moderate share** (2–8) | 38.2 % | **48.3 %** | 54.3 % | closes **63 %** |
| **median `pool_rank`** | 8.07 | **7.92** | 7.62 | closes **33 %** |
| round-1 mean \|reach\| | 2.64 | **2.77** | 2.87 | closes **55 %** |
| bar 5 dispersion | −11.39 % | −11.26 % | — | marginally better |
| **bar 1 profile distance** | **0.0894** | 0.0914 | — | **+0.0021 worse** |
| **bar 2 elite past-10** | **25.24 %** | 26.21 % | ceiling 30 % | **+0.97 pp worse** |
| bar 3 worst excess sds | 0.00 | 0.00 | tol 1.0 | unchanged |
| landing past-pick-4 · legality | 0.1531 · 12.31 % | 0.1531 · 12.31 % | 0.131 | unchanged |

**The mechanism is visible in one number.** `autopilot`'s overall `pool_rank` is **1.23** — it takes
the literal best available almost every pick, in a corpus where 0.2 % of picks look like that. It is
single-handedly responsible for most of the sim's 11 % chalk share, and two `chalk` seats at 2.82
replace it without reproducing it.

**Decision: NOT shipped, under the rule agreed before the measurement** ("change the mix only if every
bar holds or improves"). Two bars move the wrong way. They are small — 2.3 % relative on profile
distance, 0.97 pp on elite past-10 against a 30 % ceiling — and they buy a large, unambiguous gain on
every faithfulness statistic, so **this is the closest call in the session and the one most worth
overruling deliberately.** What the rule bought is that the reversal is one flag
(`--room chalk balanced balanced balanced balanced value_hawk safe_floor reacher upside_chaser chalk`)
and the evidence for it is written down rather than remembered.

**The argument the ticket actually asked for, stated:** `autopilot`'s 1-in-10 share is **not**
defensible as a frequency claim — 0.2 % of realized seats behave that way, so the room over-represents
it ~50×. It is defensible as a **role**: it is the deterministic control that reproduces
`pick_by_adp(noise=0)` exactly, several tests depend on it, and bar 3 (the harvest bar the seat was
suspected of feeding) reads **0.00 excess sds in both rooms** — so the spill it manufactures is not
currently being harvested by anyone. The honest summary is that the seat costs realism on the
faithfulness axis and costs nothing on the axis it was suspected of corrupting.

### The T24 treatment for the objective swap, run anyway — it costs two bars and buys nothing

B5 already settled the metric, but the user's decision was to switch the objective *with the full T24
treatment*, so the treatment ran: `mock_room_bars.py --bench-weight 0.0 --shuffle-room`,
seating-marginalized, 40 seeds × 8 seasons, one knob moved.
`analysis/mock_room_bars_t28_benchw0.json`.

| bar | w=1.0 (shipped) | w=0.0 (starter-aware) | delta |
|---|---|---|---|
| bar 1 profile distance | **0.0894** | 0.1020 | **+0.0126** (14 % relative, worse) |
| bar 5 dispersion level error | **−11.39 %** | −12.48 % | **−1.09 pp** (worse) |
| bar 1 round-1 · bar 2 · bar 3 · landing | — | — | unchanged to the digit |
| legality share illegal | 12.31 % | 12.25 % | −0.06 pp (better) |

Every gate still passes, and only `value_hawk` moves — as designed, since `full_room_pick_fn` hands
the risk model to `portfolio_ce` seats alone. Its `pool_rank` goes **10.12 → 9.23** overall
(R1–3 10.30 → 9.42, R7–10 12.50 → 10.84): priced by the lineup it stops paying for bench depth and
drifts toward best-available, which is the *opposite* of the direction the room needs.

**So the swap is refused on two independent grounds** — the metric is a significantly worse predictor
of title probability (B5), and installing it as an objective costs profile distance and dispersion
while improving nothing measurable. `bench_weight` stays **1.0** and ships default-off.

## Two things found on the way out

**T31 replicates on a second board.** The Stage-0 chore was run at the close of the session, banking
the 2026-07-30 FFC boards. Re-measuring B2 against that board reproduces the finding: drafted-range
**RB −0.249 (still FAIL)**, QB −0.889 / WR −0.570 / TE −0.857 all pass, and the whole-index numbers
are unchanged (QB +0.474 with 59 % negative haircuts). So T31 is a property of live boards, not of one
snapshot.

**★ T32 — and it is the reason the above needed a special-cased measurement.** `mock.room_board`
caches the enriched board on `(season, scoring, teams, include_dst, ENRICH_VERSION)` — **nothing about
which snapshot `resolve_board` answered with**. Measured immediately after running the chore:
`resolve_board` returns **244** rows while `room_board` serves the cached **223**, so **25 players on
the fresh board are invisible to every caller** and 4 stale ones remain. `ENRICH_VERSION` was built to
force precisely this kind of rebuild and it covers the enrichment but not the enrichment's *input*.

Two consequences worth stating plainly. First, it is *why every number in this session is on the
consistent 2026-07-24 board even after the refresh* — which is the outcome I wanted, but by accident
rather than by design, and an accident that happens to help is still an accident. Second, it bites
hardest **in-season**, when the chore runs weekly and consecutive boards diverge fastest — i.e.
exactly when a user is drafting. Logged, **not fixed**: the fix invalidates all nine season caches,
and Session H.5's central claim is bit-identity against caches built before it, so rebuilding them at
the close would have made that claim unverifiable. It belongs with the next batch measurement.

---

## T31 — the live-board level correction, and a filed cause that was wrong three times running

*(2026-07-30, its own session, per the user's ordering decision T31 → Session I → Session I.5. Bars
pre-registered in `PLAN.md` §2026-07-30 (session 4) before the fix existed; results in
`analysis/t31_level_cap.json`; done-bar `steps/t31_level_cap.py`.)*

**All six bars pass.** Whole-board negative-haircut share **38.75 % → 0.00 %**; drafted-range
`spearman(haircut, games_played_mean)` **RB −0.288 → −0.666** with QB/WR/TE at −0.906/−0.904/−0.889;
full-board sign **QB +0.474 → −0.980**; max `sd/proj_points` **23.06 → 0.903**;
2022/2023/2024/**2025** bit-identical; T17 band held with the top-60 moving **0.078 %**.

### ★ The ticket's own cause line was wrong, and one line of code falsified it

`docs/TECH-DEBT.md` T31 recorded the cause as "a live season has no realized prior-season basis to
shrink the per-game level toward". **There is no such branch anywhere in the code.** `train_seasons` is
`[s for s in DEV_SEASONS if s < season]`, which for a 2024 board and a 2026 board is the *same nine
seasons*, 2014–2022. The fitted QuantReg models are **identical** between the board that fails the gate
and the board that passes it. Five minutes of reading, before any code was written, moved the whole
session off the prescription and onto the board.

**That is now three in a row.** T13's filed prescription (thread a seed through the Iman–Conover
coupling) would have been built and would not have worked — the cause was DuckDB's parallel float
aggregation. T24's filed prescription (a per-seat `adp_stdev` private board) *was* built and was
**monotonically harmful**. Now T31's. The pattern is structural, not carelessness: **a ticket's cause
line is written at the moment the symptom is found, which is the moment you know least about it.** It
should be read as a hypothesis with a decaying confidence, and re-derived before it is built. The
cheapest possible first move is the one used here — *when a defect is claimed to be about A versus B,
check whether A and B actually differ in the code before theorising about why they do.*

### ★ The measured cause: a linear fit extrapolated far below its own support

The level is `b0_tau + b1_tau · calibrated_mean`, one line per (position, τ), fit on the **conditional
cohort** `weeks ≥ 0.85 · season_games` — necessarily starters. So the intercepts are large and positive
(**QB q50 `b0` = 169.35**, RB 68.95, WR 43.70, TE 36.24), and the fitted level exceeds the projection it
is built from for any `proj_points` below **272 (QB) / 187 (WR) / 170 (RB) / 150 (TE)**.

Training support of `calibrated_mean` bottoms out at **QB 34.1 / TE 11.0 / WR 12.0 / RB 4.9**. The
**2026 board's median QB `calibrated_mean` is 11.4** — below the *minimum* of the training data.
**56.4 % of 2026 QBs sit below training support, against 2.3 % on 2024 and 6.7 % on 2022.** The defect
is **board depth, not season liveness**: the live FantasyPros scrape runs 490 players deep to
`proj_points` 1.8, while the historical proxy board only projects players with prior-season production
and stops around 10. The two boards were never the same object, and nothing in the pipeline said so.

**A second mechanism sits underneath, and it is why "just don't extrapolate" fails.** The training
cohort is conditioned on availability, so a *low-projection* player who still played 85 % of a season is
one who **won a job**. The fit's low tail is made of breakouts — it is selection-biased upward, not
merely unsupported. Interpolating the fit to the origin (the textbook answer to out-of-support
extrapolation) leaves an origin slope ~3.4× steeper than `1/correction`, so the violation survives with
its sign intact. The repair has to reach for the consensus level.

### ★ Capping at the projection was built first, and the tie mass is what rejected it

The obvious repair — scale any row whose `mean` exceeds `proj_points` back to `proj_points` — shipped
first and looked good: negative share **38.75 % → 8.1 %**, B4/B5/B6 all passing. It is wrong, and the
gate said so in the one place a bar can still speak after the headline improves: **full-board QB
spearman moved the *wrong way*, +0.474 → +0.523**, and drafted-range RB degraded −0.288 → −0.250.

The reason is a **tie mass**. Capping at the boundary leaves every capped row at `haircut == 0` — a
block of players with a *low* `games_played_mean` and *no* haircut at all, which is the availability
identity failing in the opposite direction. The property under test was never "haircut ≥ 0"; it was
"haircut **is** the availability discount". The shipped target is therefore

    target = proj_points · avail_p / g_ref

which is literally what `validate.value_scale_gate` measures (`haircut == 1 − avail_p/g_ref`, decreasing
in games played). **Cap to the identity, not to the boundary.** This is T19's lesson recurring on a
repair instead of a signal: *a one-sided fix is passed by the same defect pointing the other way.*

### ★ It is a repair, not a replacement — and the gradient is the proof

Share of rows whose level moved, by ADP band, with the median scale among those that moved:

| ADP band | n | share moved | median scale |
|---|---|---|---|
| **1–24** | 24 | **0.0 %** | — |
| 25–60 | 35 | 2.9 % | 0.988 |
| 61–120 | 59 | 11.9 % | 0.971 |
| 121–180 | 79 | 51.9 % | 0.883 |
| undrafted | 282 | 96.5 % | 0.443 |

The top of the board is *literally* untouched, and the effect ramps exactly where the fit runs out of
support. Board-wide `sum(mean)` falls 41 155 → 33 998 (−17.4 %), essentially all of it below ADP 120.
Worth stating plainly because two very different changes would have passed the six bars — a narrow
repair and a wholesale replacement of the Phase-5 level with `proj × avail` — and only one of them is
the ticket. **The bars constrain the outcome; the gradient is what identifies the mechanism.**

### ★ The 2025 holdout was authorised and then not needed

The user pre-authorised one further read of the 2025 calibration holdout to confirm the fix had not
broken coverage (75.5 % uncond / 81.5 % cond). It turned out to be unnecessary: the structural gate is
**`value_board.source`**, already in the frozen 4.2 contract, and **2025 is proxy-sourced** — so it is
bit-identical, and B5 establishes that **by hash** without reading its calibration at all. The holdout
is still unspent. *Check what a structural gate already buys you before spending a one-shot resource on
the same question.*

### ⚠ The method warning, which outlives the ticket: a control that cannot fail

B5 is a before/after against a `git worktree` at the pre-T31 commit. **It silently ran post-fix code
twice.** First: the project installs **editable**, so `uv run --project <main>` from inside a worktree
resolves `fantasy_quant` to the *main* tree's `src` — the worktree's own source is never imported.
Second, on the retry: a persistent `cd` in a chained shell command sent the *working-tree* run into the
worktree, so both halves were now "before".

Both failures produced **identical hashes across all five seasons** — which reads exactly like
"bit-identical, nothing moved", the result the bar was hoping to see. A broken control and a passing
control are the same output. It was caught only because 2026 was *expected* to move and didn't.

**The rule: assert your control can produce a known difference before you trust it to show none.** Fix
in place — `PYTHONPATH=<worktree>/src`, plus the warning in `steps/t31_level_cap.py`'s docstring and a
`live_board_changed` field carried in the bar sheet so a control that stops discriminating is visible in
the artifact rather than in someone's memory.

**A third instance, same day, different disguise.** The T31 regression check against the shipped room
bar sheet (`analysis/mock_room_bars_verify_20260729.json`) came back with **149 gate-side differences**
— on `MATCHED_SEASONS` 2017–2024, which T31 leaves bit-identical by construction. It looked like the
fix had leaked into the frozen room. It had not: the verify sheet was generated with
**`shuffle_room: true`** and the re-run had defaulted to `false`, so the two sheets describe different
seating populations — H.5's own finding that a fixed seating flatters by 5–7 pp, arriving as a false
positive instead of a false negative. Confirmed independently first: the v3 and v4 board caches are
**byte-identical for every historical season** and differ **only on 2026**.

So in one session the same class of error produced *both* a spurious "nothing changed" (twice) and a
spurious "everything changed" (once). The unifying rule is not about worktrees or flags: **a
comparison is only evidence if you know the two sides differ in exactly one thing, and the cheapest
way to know that is to check the run's own recorded config before reading its numbers.** Every one of
these three was caught by a *second, independent* measurement — the expected-to-move season, and the
cache digests — not by inspecting the harness.

*(A fourth, harmless: a `cd analysis/cache` persisted across chained shell commands and a later
relative path resolved into it. Same root cause, no analytical consequence.)*

---

## Session I — Phase 17 League-Format Fidelity (17.1–17.4)

*(2026-07-30, run straight through from T31 per the user's ordering. Four scope decisions locked
before the build: nested-eligibility flex only · 4/6/8 brackets with odd `n_teams` refused · presets
plus a bounded knob set · round-based keepers only. Done-bar `steps/phase17_formats.py`,
`analysis/phase17_formats.json` — **all five gates PASS**. 658 tests, +41; ruff clean.)*

**The whole phase is a config generalization, so it has two obligations that pull against each
other:** non-default formats must be *correct*, and the lockbox-validated default must not move by a
digit. G1 and G3 are those two obligations as gates.

### ★ 17.1 — the flex rule was written in three places, and that was the actual work

`flex`/`flex_positions` had **nine** consumers, and the fill order was independently re-derived in
three solvers: `season.lineup_points_matrix` (vectorized), `walkforward.optimal_lineup_points`
(reference) and `inseason.lineup._slot_plan`. Generalizing meant giving them one rule to share —
`RosterSlots.flex_groups()`, ordered **most-restrictive-first** — rather than editing three copies
in parallel and hoping. Same shape as 16.17's `SeatMap` and T18's "delete, don't leave beside".

**Nested eligibility is what makes greedy correct, so non-nested rosters are refused rather than
mis-solved.** With nested groups (superflex ⊇ flex ⊇ dedicated), a player the narrow slot can use is
also usable by the wide one, so committing the narrow slot first never strands a better assignment.
For genuinely non-nested sets — a WR/TE flex beside an RB/WR flex — that argument fails and the
correct solver is a per-cell assignment that does not vectorize over `(n_sims, n_weeks)`.
`assert_nested` raises, and `LeagueSettings` calls it. Supporting a format we would answer *wrongly*
is worse than not supporting it.

**The vectorization trick is a carry.** Which roster row fills a flex differs per sim and per week,
so "remove the used players" cannot be done by identity — the first implementation tried to match
used rows by value and was wrong for exactly that reason. The fix: sort a group's eligible pool
descending, take its top `n`, and **carry the unused tail forward** to the next, wider group. With
nested eligibility that carry *is* the set still available to the wider slot, per cell, with no loop
over cells.

**★ The bar is brute force, not the other greedy.** G1 checks the vectorized solver against an
exhaustive optimum over legal assignments (slots allowed to be empty) on all five shipped formats —
worst absolute error **0.0**. Checking it against `optimal_lineup_points` would have proved only
that the two agree, and they now share `flex_groups()`: *two greedies that share a bug agree
perfectly.*

### ★ 17.1 — the replacement-level line is the phase's headline, and it was quietly wrong

`replacement_ranks` allocated the flex "in proportion to dedicated demand". For an RB/WR/TE flex
that is fine. For a **superflex** it handed QB **1/6** of the slot, leaving replacement at ~QB12 in a
10-team league — a format the engine claimed to support, priced as if it were 1-QB.

The fix is a one-line reframing rather than a new model: groups are processed most-restrictive-first,
and a superflex differs from the base flex **only** by admitting QB, since RB/WR/TE depth was already
priced by the narrower group. So the marginal effect falls on quarterbacks and the slots go there.
**QB replacement moves QB10 → QB20** — from "the last starter" to "the last *second* starter", which
is where superflex scarcity actually lives. Nothing else moves (RB/WR/TE/K/DST ranks identical).

**Measured on the live 2026 board (G2), that is worth: the best QB goes from overall rank 15 to
rank 3**, QBs in the top 50 from 6 to 7. Measured on the value board rather than a simulated draft
on purpose — the board is what a draft consumes, and it isolates the replacement change from every
behavioural knob in the room.

*Stated rather than hidden:* a superflex is occasionally filled by a third RB, not a second QB.
Pricing that needs realized points, which would make `replacement_ranks` impure — it is called from
`projections/distribution.py` with no DB in scope. The residual is small next to the QB10 → QB20 move.

### ★ 17.2 — the bounded field set earned itself immediately

17.2 chose presets + a bounded knob set over an open `{stat: value}` map, on the argument that a typo
in an open map scores 0.0 silently for a whole season. **The first test of that claim failed:**
pydantic allows extra fields by default, so `OffenseRules(rec_typo=1.0)` was accepted and ignored —
the exact failure the design was chosen to prevent, present in the design itself. Fixed with a
`_Rules` base carrying `extra="forbid"`.

**A second one, cheap to have missed:** `ruleset_from_preset("full_ppr")` initially returned a
ruleset with identical scoring but the name `"full_ppr"` instead of `"full_ppr_1qb"`. `RuleSet` is
serialized into `cached_distribution`'s cache key, so a same-scoring-different-name preset would have
**split the cache and forced a silent 9-season rebuild**. The preset now returns `RuleSet()` itself.
*A field that is "only a label" is not, once something keys on it.*

TE-premium needs the row's position, which some derived frames do not carry; the bonus is skipped
there rather than mis-applied, keeping the `te_rec_bonus=0.0` default byte-identical.

### ★ 17.3 — `LeagueFormat` refused ordinary leagues, and refuses different ones now

The bracket was hard-coded to 4-or-6 playoff teams with byes fixed at 0/2, so **a 12-team league with
an 8-team playoff — entirely ordinary — could not be constructed at all.** Now byes and rounds are
*derived* (`bracket_size = next power of two`), one rule instead of a table, and 4/6/8 all work.

Two limits are now refused **at the settings layer with a reason**, where before they raised deep
inside a sim or not at all: **odd `n_teams`** (the round-robin circle method pairs every team each
week, and 9.5's win-prob objective raises on odd sizes too) and non-nested flex. `LeagueSettings` is
the platform-agnostic form contract — deliberately *not* Sleeper auto-import, because the user is on
ESPN/Yahoo and gating the product on one vendor's API is the wrong dependency.

**`lockbox_validated()` is the honesty method.** It returns True for exactly one configuration: the
10-team full-PPR 1-QB league the lockbox was spent on. Everything else is supported, correctness-
tested, and carries **no out-of-sample claim** — Phase 14 is expected to render that, not let a user
assume the calibration transfers.

### ★ 17.4 — keepers re-inflate ADP by removing supply, not by adjusting a number

The obvious implementation is a keeper flag plus an "ADP adjustment". Both would be wrong together:
ADP is a *rank on the remaining board*, so removing the kept player **is** the re-inflation, and
adding a separate adjustment on top would double-count it. `apply_keepers` seats the player, drops
him from the pool, and records `(team, round)` in `skipped_picks`, which `run_to_completion` skips.

That second half is what stops keepers being free: a team keeping three studs **drafts three fewer
times**. Verified — 147 picks made instead of 150, every roster still 15, kept players never
re-drafted, and `keepers=()` bit-identical to the pre-17 path. A keeper not on the board still costs
the pick, because the forfeit is the league's rule and not the board's.

### What is deliberately not here

Non-nested flex (refused, not approximated) · auction keepers and dynasty multi-year pricing (15.1,
still deferred) · IDP (nflverse data too thin) · Sleeper settings auto-import (a future convenience
on top of the manual form, never the primary path). `starter_marginal`'s closed form reasons about
one flex slot and now **routes multi-flex to the exact solver** rather than approximating — the
candidates ride the trailing axis `lineup_points_matrix` already vectorizes, so it stays one call.
