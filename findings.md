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
