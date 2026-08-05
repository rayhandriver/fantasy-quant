# DATA-SOURCES — what is in the store, and what is not

> ⚠ **GENERATED FILE — do not hand-edit.** Regenerate with
> `uv run python steps/phase0_12_inventory.py` (Session DATA-1 / 0.12.2).
> Every row below is derived from the store and from a scan of `src/`, `steps/`, `app/`
> and `tests/`. Hand-editing it makes it a curated file that pretends to be a derived
> one, which is worse than either.

## Why this file exists

So that *"do we have X?"* is answered by reading one table instead of running another
investigation. Three defects motivated it, and each is the same defect wearing a
different hat — **nothing recorded what we had**:

- **T46** — `nfl_data_py` is a *wrapper* over the nflverse release assets, and its
  surface was being read as the data's surface. Ten seasons of play-level participation
  data were invisible, not unavailable.
- **T45** — `ngs` was ingested and effectively unread for a year. See the **consumers**
  column: *a table nobody reads and a table that does not exist look identical from the
  outside.*
- **T44** — there was no `schedules` table, so bye weeks were being inferred from a
  third-party *rankings* feed.

## How to read the columns

- **PIT class** — `preseason` (known before a draft, safe as a draft feature) ·
  `in_season_weekly` (known only after week *w*; draft-legal **only** through the
  season-*t−1* lag in `features/exposures.py`) · `retrospective` (complete only after the
  season; **never** a feature). Enforced in `data/registry.py`, not merely documented.
- **Backtestable** — `False` means the table must never be a backtest input. It is an
  assertion (`registry.assert_backtestable`), not a label.
- **Floor** — the earliest season that exists **upstream**. A floor is a fact about the
  world, not a gap in our ingest. ⚠ **Do not go looking for data below a floor.**
- **Readers** — files that *query* the table, excluding the module that writes it and
  excluding `tests/`. A producer mentions its own table more than anyone, so counting
  mentions would report every freshly-ingested table as well-read — which is how a
  register goes blind to the T45 it was written to catch. **0 readers is a finding.**

## ★ Upstream floors — permanent; stop re-investigating these

| source | first season | consequence |
|---|---|---|
| participation | **2016** | 7 DEV seasons (2016-2022) — workable |
| NGS | **2016** | 7 DEV seasons — workable |
| PFR advanced | **2018** | 5 DEV seasons |
| **FTN charting** | **2022** | **ONE DEV season** — descriptive/live use only, never a backtest input |

`DEV_SEASONS` is 2014-2022 and the lockbox is 2023+2024, so a source starting in 2022
contributes exactly one usable development season. *The user's instinct that "pre-2022
is missing" is **right for FTN and wrong for everything else**, and that distinction is
the most useful thing in this file.*

## The store

**63 tables · 0 undeclared · 26 with no consumer.**

| table | grain | PIT class | backtest | rows | cols | seasons | floor | readers |
|---|---|---|---|---:|---:|---|---:|---:|
| `adp_snapshots` | player-board-date | preseason | yes | 37,029 | 21 | 2010-2026 | — | 19 |
| `combine` | player | preseason | yes | 4,080 | 19 | 2014-2025 | — | 3 |
| `consensus_projections` | player-season | preseason | yes | 529 | 20 | 2026-2026 | — | 2 |
| `contract_season` | player-season | preseason | yes | 40,798 | 10 | 2014-2026 | 2014 | 0 |
| `contracts` | contract | preseason | yes | 51,793 | 26 | — | — | 1 |
| `defense_coverage_week` | team-week | in_season_weekly | yes | 5,522 | 25 | 2016-2025 | 2016 | 1 |
| `defense_personnel_map` | personnel-string | preseason | yes | 7,637 | 8 | — | — | 0 |
| `defense_player_week` | player-week | in_season_weekly | yes | 106,760 | 17 | 2016-2025 | 2016 | 1 |
| `defense_team_week` | team-week | in_season_weekly | yes | 5,522 | 28 | 2016-2025 | 2016 | 2 |
| `depth_charts` | MIXED — see depth_charts_all | in_season_weekly | yes | 955,989 | 27 | 2014-2024 | 2014 | 4 |
| `depth_charts_all` | team-player-slot (grain column: weekly | snapshot) | in_season_weekly | yes | 955,989 | 19 | 2014-2025 | 2014 | 0 |
| `depth_charts_ts` | team-player-snapshot | in_season_weekly | yes | 554,215 | 14 | — | — | 2 |
| `draft_picks` | pick | preseason | yes | 3,077 | 37 | 2014-2025 | — | 4 |
| `draft_values` | pick | preseason | yes | 262 | 7 | — | — | 2 |
| `ecr_snapshots` | player-board-date | preseason | yes | 17,264 | 21 | 2017-2026 | — | 5 |
| `ftn_charting` | play | in_season_weekly | **NO** | 185,215 | 30 | 2022-2025 | 2022 | 1 |
| `game_lines` | game | preseason | yes | 3,295 | 27 | 2014-2025 | 2014 | 8 |
| `injuries` | player-week | in_season_weekly | yes | 65,866 | 18 | 2014-2025 | 2014 | 4 |
| `kicking_env_week` | team-week | in_season_weekly | yes | 6,590 | 15 | 2014-2025 | 2014 | 0 |
| `news_raw` | item | in_season_weekly | **NO** | 109 | 9 | — | — | 3 |
| `ngs` | player-week | in_season_weekly | yes | 26,723 | 53 | 2016-2025 | 2016 | 1 |
| `offense_personnel_map` | personnel-string | preseason | yes | 4,001 | 11 | — | — | 0 |
| `offense_player_week` | player-week | in_season_weekly | yes | 102,368 | 52 | 2016-2025 | 2016 | 1 |
| `offense_team_week` | team-week | in_season_weekly | yes | 5,522 | 42 | 2016-2025 | 2016 | 1 |
| `officials` | game-official | retrospective | yes | 21,900 | 10 | 2015-2025 | 2015 | 0 |
| `otc_player_ids` | player | preseason | yes | 13,782 | 7 | — | — | 0 |
| `participation` | play | in_season_weekly | yes | 478,989 | 30 | 2016-2025 | 2016 | 5 |
| `participation_defense_player_play` | play-defender | in_season_weekly | yes | 4,945,496 | 13 | 2016-2025 | 2016 | 1 |
| `participation_offense_player_play` | play-player | in_season_weekly | yes | 4,947,841 | 10 | 2016-2025 | 2016 | 0 |
| `participation_player_play` | player-play (VIEW, never materialized) | in_season_weekly | yes | 9,893,337 | 16 | 2016-2025 | 2016 | 0 |
| `participation_player_week` | player-week | in_season_weekly | yes | 182,303 | 24 | 2016-2025 | 2016 | 1 |
| `pbp` | play | in_season_weekly | yes | 580,005 | 373 | 2014-2025 | 2014 | 17 |
| `pfr_pass` | player-season | retrospective | yes | 848 | 39 | 2018-2025 | 2018 | 0 |
| `pfr_rec` | player-season | retrospective | yes | 4,130 | 27 | 2018-2025 | 2018 | 0 |
| `pfr_rush` | player-season | retrospective | yes | 2,820 | 21 | 2018-2025 | 2018 | 0 |
| `player_distributions` | player | preseason | yes | 673 | 16 | 2025-2025 | — | 0 |
| `player_ids` | player | preseason | yes | 12,465 | 36 | — | — | 20 |
| `players_master` | player | preseason | yes | 24,509 | 40 | — | — | 2 |
| `qbr_season` | player-season-type | retrospective | yes | 1,523 | 24 | 2006-2025 | 2006 | 0 |
| `qbr_week` | player-week | in_season_weekly | yes | 10,709 | 31 | 2006-2025 | 2006 | 0 |
| `sc_lines` | game-side-line | preseason | yes | 4,092 | 8 | 2013-2020 | — | 0 |
| `schedules` | game | preseason | yes | 7,548 | 47 | 1999-2026 | 1999 | 1 |
| `seasonal` | player-season | retrospective | yes | 8,702 | 59 | 2014-2025 | 2014 | 1 |
| `sleeper_crawl_leagues` | league | preseason | yes | 8,207 | 2 | — | — | 0 |
| `sleeper_crawl_queue` | queue entry | preseason | yes | 11,149 | 3 | — | — | 0 |
| `sleeper_crawl_users` | user | preseason | yes | 370 | 2 | — | — | 0 |
| `sleeper_draft_picks` | pick | preseason | yes | 1,207,687 | 17 | 2017-2026 | — | 9 |
| `sleeper_drafts` | draft | preseason | yes | 8,521 | 16 | 2017-2026 | — | 8 |
| `sleeper_manager_profiles` | manager | preseason | yes | 24,696 | 11 | — | — | 3 |
| `sleeper_tendencies` | manager-slot | preseason | yes | 122,162 | 7 | — | — | 0 |
| `snaps` | player-game | in_season_weekly | yes | 300,812 | 19 | 2014-2025 | 2014 | 6 |
| `st_team_season` | team-season | in_season_weekly | yes | 384 | 31 | 2014-2025 | 2014 | 1 |
| `team_construction_season` | team-season | preseason | yes | 416 | 59 | 2014-2026 | 2014 | 2 |
| `team_scheme_columns` | table-column | preseason | yes | 190 | 14 | — | — | 0 |
| `team_scheme_season` | team-season | in_season_weekly | yes | 320 | 109 | 2016-2025 | 2016 | 1 |
| `team_scheme_season_z` | team-season | in_season_weekly | yes | 320 | 186 | 2016-2025 | 2016 | 0 |
| `team_scheme_week` | team-week | in_season_weekly | yes | 5,522 | 89 | 2016-2025 | 2016 | 0 |
| `team_scheme_week_z` | team-week | in_season_weekly | yes | 5,522 | 145 | 2016-2025 | 2016 | 0 |
| `teams_meta` | team | preseason | yes | 36 | 17 | — | — | 1 |
| `trades` | trade-asset | preseason | yes | 4,975 | 12 | 2002-2026 | 2002 | 0 |
| `weekly` | player-week | in_season_weekly | yes | 79,250 | 54 | 2014-2025 | 2014 | 24 |
| `weekly_rosters` | player-week-status | in_season_weekly | yes | 533,275 | 37 | 2014-2026 | 2014 | 3 |
| `win_totals` | game-market-book | preseason | **NO** | 470,217 | 10 | 2006-2021 | — | 0 |

## Notes and known holes

**`adp_snapshots`** — ⚠ The `team` column is an end-of-season crosswalk and leaks RETROSPECTIVELY (the 16.1 PIT catch) — but only backwards: a snapshot of a season not yet played cannot encode a trade not yet made, so the current season's board team is safe and only there (16.5).

**`consensus_projections`** — 2026-only and dated 2026-07-05; the re-pull is its own step, not DATA-1's.

**`contract_season`** — The contract in force per player-season, deduplicated. ⚠ OTC nominal window [year_signed, +years) — NOT a cap sheet: no per-season cap hits, dead money or restructures.

**`contracts`** — The role-security hypothesis for T3's open hole. ⚠ No unique row key — OTC emits byte-identical duplicate rows (3,339 of them); aggregate deliberately.

**`defense_coverage_week`** — THREE TIERS, never blended: charted shell (2018+, ~49%), derived safety count (a PERSONNEL proxy, never alignment), and not-obtainable-free alignment depth/rotation.

**`defense_personnel_map`** — Distinct defense_personnel string -> unit counts. Both encodings.

**`defense_player_week`** — The defensive half participation deliberately never materialized (T48).

**`defense_team_week`** — Fronts, blitz, box, man/zone, pressure. Rates route their denominators through the 0.13.0 break map; man/zone columns are 2018+, NOT 2016+.

**`depth_charts`** — ⚠ Holds TWO grains: 401,774 weekly rows 2014-2024 plus 554,215 rows of the 2025 snapshot series appended with a NULL season. Kept for provenance; read depth_charts_all instead, where the grain is a column.

**`depth_charts_all`** — 0.12.7 — season-complete 2014-2025, grain explicit.

**`depth_charts_ts`** — Duplicated inside depth_charts; superseded by depth_charts_all.

**`ftn_charting`** — ★ backtestable=False AS AN ASSERTION, not a label. DEV_SEASONS is 2014-2022 and the floor is 2022, so it contributes exactly ONE development season; any bar built on it is a bar built on n=1 (cf. T24, T40). Descriptive / live-2026 use only.

**`game_lines`** — The validated market spine — 'don't fight the sharp market'.

**`kicking_env_week`** — temp/wind are NULL inside a dome and that null is information — verified NOT zero-filled, the opposite of the T50 failure.

**`news_raw`** — Free-text RSS is forward-only and cannot be backfilled (Phase 12).

**`ngs`** — T45 — ingested and effectively unread: one consumer (data/panel.py:93, receiving only), NO features/ module reads it. Wiring it in is M-1, deliberately not DATA-1, because it changes a matrix downstream models read.

**`offense_personnel_map`** — Distinct offense_personnel string -> skill counts. Both encodings.

**`offense_player_week`** — Route tree (19 charted routes, targeted receiver only) + usage within personnel grouping.

**`offense_team_week`** — Formation/personnel/tempo 2016+; motion/PA/RPO/screen are FTN 2022+ and backtestable:false — see offense_scheme.assert_ftn_backtestable.

**`participation`** — 0.12.3 — box counts, personnel, coverage scheme, routes, pressure, and the gsis ids of all 22 men on every play. The motivating source of DATA-1.

**`participation_defense_player_play`** — Zips defense_players with defense_positions by PARALLEL unnest. ⚠ defense_positions is 2023+, so 2016-2022 rows carry a null position rather than vanishing — requiring it truncated the view to three seasons, all outside DEV.

**`participation_offense_player_play`** — The offensive twin. `route` is ONE route per play, so it is play context and is attributed only to the targeted receiver.

**`participation_player_play`** — 0.12.4 — the exploded 22-men-on-the-field form. A VIEW on purpose: stored it is ~100M rows, larger than the rest of the store combined. Declared here because a view is a queryable surface and needs a PIT class exactly as much as a table does — it was the one thing the registry gate caught on its first run, which is the gate working.

**`participation_player_week`** — 0.12.4 — the grain the downstream questions are actually asked at.

**`player_ids`** — The gsis crosswalk every existing join hangs off.

**`players_master`** — nflverse's own player master; beside player_ids, not merged into it.

**`schedules`** — 0.12.6 — closes T44; byes now derive from the fixture list, not from ECR.

**`st_team_season`** — 4th-down and 2-point aggression attributed to the HEAD COACH, conditioned on the opportunity that offered the choice. No ST-coordinator table.

**`team_construction_season`** — Cap allocation, draft capital, age, continuity. Read cap_share_* (a distribution) not cap_pct_* (accounted APY, which sums past 1.0). preseason because roster/cap/draft state is known before week 1.

**`team_scheme_columns`** — ★ T49's answer: per-COLUMN floor, PIT class, break provenance and per-season fill for every panel column.

**`team_scheme_season`** — Rates are ratios of sums, never means of weekly ratios. Per-column floors in team_scheme_columns.

**`team_scheme_season_z`** — A NULL z means never measured; it is never filled with 0 (= league average).

**`team_scheme_week`** — The unified panel. Per-column floors in team_scheme_columns (T49).

**`team_scheme_week_z`** — A NULL z means never measured; it is never filled with 0 (= league average).

**`trades`** — One row per asset moved; trade_id is a GROUP key, not a row key.

**`weekly`** — Realized weekly stats — the scoring spine.

**`weekly_rosters`** — Distinguishes 'did not play' from 'was not rostered' — the distinction T3's cohort availability prior is built around. Grain includes STATUS.

**`win_totals`** — ⚠ nfl_data_py warns this source 'is currently in flux and may be out of date'. Landed for completeness; game_lines remains the market spine.

## ⚠ Tables with no consumer

Ingested and referenced nowhere in `src/`, `steps/`, `app/` or `tests/`. Either a
source waiting on the work that motivated it, or a T45 in the making.

- `contract_season`
- `defense_personnel_map`
- `depth_charts_all`
- `kicking_env_week`
- `offense_personnel_map`
- `officials`
- `otc_player_ids`
- `participation_offense_player_play`
- `participation_player_play`
- `pfr_pass`
- `pfr_rec`
- `pfr_rush`
- `player_distributions`
- `qbr_season`
- `qbr_week`
- `sc_lines`
- `sleeper_crawl_leagues`
- `sleeper_crawl_queue`
- `sleeper_crawl_users`
- `sleeper_tendencies`
- `team_scheme_columns`
- `team_scheme_season_z`
- `team_scheme_week`
- `team_scheme_week_z`
- `trades`
- `win_totals`

