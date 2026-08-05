"""Phase 0.12.8 — the **table registry**: PIT class, backtestability, floor, expected seasons.

One declaration per table, and the single thing both the gates (0.12.8) and the generated
inventory (0.12.2) read. It exists because the store had grown to 27 tables with none of these
facts written down anywhere, so every one of them had to be re-derived by reading code — which is
how ``ngs`` sat ingested and unread for a year (T45) and how byes ended up coming out of a
rankings feed (T44).

★ **The PIT class is the load-bearing field, and it is what keeps an ingest session from
poisoning the modelling.** Every table declares one of:

``preseason``
    Known before a draft. Safe as a draft feature as-is.
``in_season_weekly``
    Known only after week *w* is played. Native and safe for the Phase-13 in-season co-pilot and
    the M-5 variance work; usable in a **draft** feature only through the season-*t−1* lag that
    ``features/exposures.py`` already applies.
``retrospective``
    Complete only once the season is over. **Never a feature** — using it to predict anything
    inside that season is the classic leak, and the one this repo's discipline §3.1 exists to
    prevent structurally rather than by memory.

⚠ **A prose warning is not a guard** (UI-1's lesson 4), so this is not documentation: 0.12.8 turns
each class into an assertion, and B7 proves the assertion can fail by making it fail.
"""

from __future__ import annotations

from dataclasses import dataclass

PIT_CLASSES = ("preseason", "in_season_weekly", "retrospective")


@dataclass(frozen=True)
class TableSpec:
    """What we declare about one table in the store."""

    table: str
    grain: str
    pit_class: str
    source: str
    backtestable: bool = True
    floor: int | None = None          # upstream first season; None = no season dimension / no floor
    expected_seasons: tuple[int, ...] | None = None
    note: str = ""


def _seasons(a: int, b: int) -> tuple[int, ...]:
    return tuple(range(a, b + 1))


REGISTRY: tuple[TableSpec, ...] = (
    # --- the ingest spine (pre-existing; provenance is data/sources/nflverse.py) ---------------
    TableSpec("weekly", "player-week", "in_season_weekly", "nflverse/stats_player",
              floor=2014, expected_seasons=_seasons(2014, 2025),
              note="Realized weekly stats — the scoring spine."),
    TableSpec("seasonal", "player-season", "retrospective", "nflverse/stats_player",
              floor=2014, expected_seasons=_seasons(2014, 2025)),
    TableSpec("pbp", "play", "in_season_weekly", "nflverse/pbp",
              floor=2014, expected_seasons=_seasons(2014, 2025)),
    TableSpec("snaps", "player-game", "in_season_weekly", "nflverse/snap_counts",
              floor=2014, expected_seasons=_seasons(2014, 2025)),
    TableSpec("ngs", "player-week", "in_season_weekly", "nflverse/nextgen_stats",
              floor=2016, expected_seasons=_seasons(2016, 2025),
              note=(
                  "T45 — ingested and effectively unread: one consumer (data/panel.py:93, "
                  "receiving only), NO features/ module reads it. Wiring it in is M-1, "
                  "deliberately not DATA-1, because it changes a matrix downstream models read."
              )),
    TableSpec("pfr_pass", "player-season", "retrospective", "pfr/advanced", floor=2018),
    TableSpec("pfr_rec", "player-season", "retrospective", "pfr/advanced", floor=2018),
    TableSpec("pfr_rush", "player-season", "retrospective", "pfr/advanced", floor=2018),
    TableSpec("combine", "player", "preseason", "nflverse/combine"),
    TableSpec("draft_picks", "pick", "preseason", "nflverse/draft_picks"),
    TableSpec("player_ids", "player", "preseason", "nflverse/import_ids",
              note="The gsis crosswalk every existing join hangs off."),
    TableSpec("injuries", "player-week", "in_season_weekly", "nflverse/injuries", floor=2014),
    TableSpec("depth_charts", "MIXED — see depth_charts_all", "in_season_weekly",
              "nflverse/depth_charts", floor=2014,
              note=(
                  "⚠ Holds TWO grains: 401,774 weekly rows 2014-2024 plus 554,215 rows of the "
                  "2025 snapshot series appended with a NULL season. Kept for provenance; read "
                  "depth_charts_all instead, where the grain is a column."
              )),
    TableSpec("depth_charts_ts", "team-player-snapshot", "in_season_weekly",
              "nflverse/depth_charts (2025 release)",
              note="Duplicated inside depth_charts; superseded by depth_charts_all."),
    TableSpec("depth_charts_all", "team-player-slot (grain column: weekly | snapshot)",
              "in_season_weekly", "DATA-1 0.12.7 union", floor=2014,
              expected_seasons=_seasons(2014, 2025),
              note="0.12.7 — season-complete 2014-2025, grain explicit."),
    TableSpec("game_lines", "game", "preseason", "vegas/game_lines", floor=2014,
              note="The validated market spine — 'don't fight the sharp market'."),
    TableSpec("adp_snapshots", "player-board-date", "preseason", "FFC + Sleeper derived",
              note=(
                  "⚠ The `team` column is an end-of-season crosswalk and leaks RETROSPECTIVELY "
                  "(the 16.1 PIT catch) — but only backwards: a snapshot of a season not yet "
                  "played cannot encode a trade not yet made, so the current season's board team "
                  "is safe and only there (16.5)."
              )),
    TableSpec("ecr_snapshots", "player-board-date", "preseason", "FantasyPros ECR"),
    TableSpec("consensus_projections", "player-season", "preseason", "FantasyPros scrape",
              note="2026-only and dated 2026-07-05; the re-pull is its own step, not DATA-1's."),
    TableSpec("player_distributions", "player", "preseason", "Phase-5 assembler (derived)"),
    TableSpec("news_raw", "item", "in_season_weekly", "RSS", backtestable=False,
              note="Free-text RSS is forward-only and cannot be backfilled (Phase 12)."),
    TableSpec("sleeper_drafts", "draft", "preseason", "Sleeper public API"),
    TableSpec("sleeper_draft_picks", "pick", "preseason", "Sleeper public API"),
    TableSpec("sleeper_tendencies", "manager-slot", "preseason", "derived from Sleeper"),
    TableSpec("sleeper_manager_profiles", "manager", "preseason", "derived from Sleeper"),
    TableSpec("sleeper_crawl_users", "user", "preseason", "crawler bookkeeping"),
    TableSpec("sleeper_crawl_leagues", "league", "preseason", "crawler bookkeeping"),
    TableSpec("sleeper_crawl_queue", "queue entry", "preseason", "crawler bookkeeping"),

    # --- DATA-1 additions ---------------------------------------------------------------------
    TableSpec("participation", "play", "in_season_weekly", "nflverse/pbp_participation",
              floor=2016, expected_seasons=_seasons(2016, 2025),
              note=(
                  "0.12.3 — box counts, personnel, coverage scheme, routes, pressure, and the "
                  "gsis ids of all 22 men on every play. The motivating source of DATA-1."
              )),
    TableSpec("participation_player_week", "player-week", "in_season_weekly",
              "derived from participation", floor=2016, expected_seasons=_seasons(2016, 2025),
              note="0.12.4 — the grain the downstream questions are actually asked at."),
    TableSpec("participation_player_play", "player-play (VIEW, never materialized)",
              "in_season_weekly", "view over participation", floor=2016,
              note=(
                  "0.12.4 — the exploded 22-men-on-the-field form. A VIEW on purpose: stored it "
                  "is ~100M rows, larger than the rest of the store combined. Declared here "
                  "because a view is a queryable surface and needs a PIT class exactly as much "
                  "as a table does — it was the one thing the registry gate caught on its first "
                  "run, which is the gate working."
              )),
    TableSpec("ftn_charting", "play", "in_season_weekly", "nflverse/ftn_charting",
              backtestable=False, floor=2022, expected_seasons=_seasons(2022, 2025),
              note=(
                  "★ backtestable=False AS AN ASSERTION, not a label. DEV_SEASONS is 2014-2022 "
                  "and the floor is 2022, so it contributes exactly ONE development season; any "
                  "bar built on it is a bar built on n=1 (cf. T24, T40). Descriptive / live-2026 "
                  "use only."
              )),
    TableSpec("schedules", "game", "preseason", "nflverse/schedules", floor=1999,
              note="0.12.6 — closes T44; byes now derive from the fixture list, not from ECR."),
    TableSpec("qbr_week", "player-week", "in_season_weekly", "nflverse/espn_data", floor=2006),
    TableSpec("qbr_season", "player-season-type", "retrospective", "nflverse/espn_data",
              floor=2006),
    TableSpec("contracts", "contract", "preseason", "nflverse/contracts (OTC)",
              note=(
                  "The role-security hypothesis for T3's open hole. ⚠ No unique row key — OTC "
                  "emits byte-identical duplicate rows (3,339 of them); aggregate deliberately."
              )),
    TableSpec("otc_player_ids", "player", "preseason", "nflverse/players_components"),
    TableSpec("players_master", "player", "preseason", "nflverse/players_components",
              note="nflverse's own player master; beside player_ids, not merged into it."),
    TableSpec("officials", "game-official", "retrospective", "nflverse/officials", floor=2015),
    TableSpec("trades", "trade-asset", "preseason", "nflverse/trades", floor=2002,
              note="One row per asset moved; trade_id is a GROUP key, not a row key."),
    TableSpec("weekly_rosters", "player-week-status", "in_season_weekly",
              "nflverse/weekly_rosters", floor=2014, expected_seasons=_seasons(2014, 2026),
              note=(
                  "Distinguishes 'did not play' from 'was not rostered' — the distinction T3's "
                  "cohort availability prior is built around. Grain includes STATUS."
              )),
    TableSpec("teams_meta", "team", "preseason", "nflverse/teams"),
    TableSpec("draft_values", "pick", "preseason", "nfl_data_py/import_draft_values"),
    TableSpec("sc_lines", "game-side-line", "preseason", "nfl_data_py/import_sc_lines"),
    TableSpec("win_totals", "game-market-book", "preseason", "nfl_data_py/import_win_totals",
              backtestable=False,
              note=(
                  "⚠ nfl_data_py warns this source 'is currently in flux and may be out of "
                  "date'. Landed for completeness; game_lines remains the market spine."
              )),

    # ---- Session DATA-2 (Phase 0.13) — derived facts, all in_season_weekly ------------------
    # ⚠ Every one of these is DERIVED from participation/pbp/rosters, so its PIT class is
    # inherited from its sources, and its floor is the floor of the WEAKEST column it carries
    # (T49). The per-column detail lives in `team_scheme_columns`, which 0.13.7 generates —
    # a table-level floor here would repeat exactly the mistake T49 opened.
    TableSpec("defense_team_week", "team-week", "in_season_weekly",
              "DATA-2 0.13.2 over participation", floor=2016,
              expected_seasons=_seasons(2016, 2025),
              note=("Fronts, blitz, box, man/zone, pressure. Rates route their denominators "
                    "through the 0.13.0 break map; man/zone columns are 2018+, NOT 2016+.")),
    TableSpec("defense_player_week", "player-week", "in_season_weekly",
              "DATA-2 0.13.2 over participation", floor=2016,
              expected_seasons=_seasons(2016, 2025),
              note="The defensive half participation deliberately never materialized (T48)."),
    TableSpec("defense_personnel_map", "personnel-string", "preseason",
              "DATA-2 0.13.2 lookup",
              note="Distinct defense_personnel string -> unit counts. Both encodings."),
    TableSpec("defense_coverage_week", "team-week", "in_season_weekly",
              "DATA-2 0.13.3 over participation", floor=2016,
              expected_seasons=_seasons(2016, 2025),
              note=("THREE TIERS, never blended: charted shell (2018+, ~49%), derived safety "
                    "count (a PERSONNEL proxy, never alignment), and not-obtainable-free "
                    "alignment depth/rotation.")),
    TableSpec("offense_team_week", "team-week", "in_season_weekly",
              "DATA-2 0.13.4 over participation + ftn_charting", floor=2016,
              expected_seasons=_seasons(2016, 2025),
              note=("Formation/personnel/tempo 2016+; motion/PA/RPO/screen are FTN 2022+ and "
                    "backtestable:false — see offense_scheme.assert_ftn_backtestable.")),
    TableSpec("offense_player_week", "player-week", "in_season_weekly",
              "DATA-2 0.13.4 over participation", floor=2016,
              expected_seasons=_seasons(2016, 2025),
              note=("Route tree (19 charted routes, targeted receiver only) + usage within "
                    "personnel grouping.")),
    TableSpec("offense_personnel_map", "personnel-string", "preseason",
              "DATA-2 0.13.4 lookup",
              note="Distinct offense_personnel string -> skill counts. Both encodings."),
    TableSpec("contract_season", "player-season", "preseason",
              "DATA-2 0.13.5 over contracts", floor=2014,
              note=("The contract in force per player-season, deduplicated. ⚠ OTC nominal "
                    "window [year_signed, +years) — NOT a cap sheet: no per-season cap hits, "
                    "dead money or restructures.")),
    TableSpec("team_construction_season", "team-season", "preseason",
              "DATA-2 0.13.5 over contracts/draft_picks/weekly_rosters/snaps", floor=2014,
              note=("Cap allocation, draft capital, age, continuity. Read cap_share_* (a "
                    "distribution) not cap_pct_* (accounted APY, which sums past 1.0). "
                    "preseason because roster/cap/draft state is known before week 1.")),
    TableSpec("st_team_season", "team-season", "in_season_weekly",
              "DATA-2 0.13.6 over pbp", floor=2014,
              expected_seasons=_seasons(2014, 2025),
              note=("4th-down and 2-point aggression attributed to the HEAD COACH, conditioned "
                    "on the opportunity that offered the choice. No ST-coordinator table.")),
    TableSpec("kicking_env_week", "team-week", "in_season_weekly",
              "DATA-2 0.13.6 over pbp", floor=2014,
              expected_seasons=_seasons(2014, 2025),
              note=("temp/wind are NULL inside a dome and that null is information — verified "
                    "NOT zero-filled, the opposite of the T50 failure.")),
    TableSpec("team_scheme_week", "team-week", "in_season_weekly",
              "DATA-2 0.13.7 panel", floor=2016,
              expected_seasons=_seasons(2016, 2025),
              note="The unified panel. Per-column floors in team_scheme_columns (T49)."),
    TableSpec("team_scheme_season", "team-season", "in_season_weekly",
              "DATA-2 0.13.7 panel", floor=2016,
              expected_seasons=_seasons(2016, 2025),
              note=("Rates are ratios of sums, never means of weekly ratios. Per-column floors "
                    "in team_scheme_columns.")),
    TableSpec("team_scheme_week_z", "team-week", "in_season_weekly",
              "DATA-2 0.13.7 z-scored within season", floor=2016,
              note="A NULL z means never measured; it is never filled with 0 (= league average)."),
    TableSpec("team_scheme_season_z", "team-season", "in_season_weekly",
              "DATA-2 0.13.7 z-scored within season", floor=2016,
              note="A NULL z means never measured; it is never filled with 0 (= league average)."),
    TableSpec("participation_defense_player_play", "play-defender", "in_season_weekly",
              "DATA-2 0.13.2 view over participation", floor=2016,
              note=("Zips defense_players with defense_positions by PARALLEL unnest. "
                    "⚠ defense_positions is 2023+, so 2016-2022 rows carry a null position "
                    "rather than vanishing — requiring it truncated the view to three seasons, "
                    "all outside DEV.")),
    TableSpec("participation_offense_player_play", "play-player", "in_season_weekly",
              "DATA-2 0.13.4 view over participation", floor=2016,
              note=("The offensive twin. `route` is ONE route per play, so it is play context "
                    "and is attributed only to the targeted receiver.")),
    TableSpec("team_scheme_columns", "table-column", "preseason",
              "DATA-2 0.13.7 generated register",
              note=("★ T49's answer: per-COLUMN floor, PIT class, break provenance and "
                    "per-season fill for every panel column.")),
)

BY_TABLE: dict[str, TableSpec] = {s.table: s for s in REGISTRY}


# ------------------------------------------------------------------------------------------------
# T49 — floors are a property of the COLUMN, not of the table
# ------------------------------------------------------------------------------------------------
#: ★ Columns whose first usable season is **later than their table's**. The register listed
#: participation at 2016, which is right for personnel, box counts and formation and **wrong for
#: coverage**: ``defense_man_zone_type`` and ``defense_coverage_type`` are 0.000 in 2016 and 2017.
#: With ``DEV_SEASONS`` = 2014-2022 that is **five** development seasons of man/zone, not seven.
#:
#: *A floor recorded one level too coarse is worse than no floor: it is confidently wrong at the
#: grain a query is actually written at.* These are measured by ``breaks.BreakMap.floor``, not
#: asserted by hand — this table is the declaration the gate checks the measurement against.
COLUMN_FLOORS: dict[tuple[str, str], int] = {
    ("participation", "defense_man_zone_type"): 2018,
    ("participation", "defense_coverage_type"): 2018,
    ("participation", "defense_positions"): 2016,
    ("participation", "offense_positions"): 2016,
    ("ftn_charting", "is_motion"): 2022,
    ("ftn_charting", "is_play_action"): 2022,
    ("ftn_charting", "is_rpo"): 2022,
    ("ftn_charting", "is_screen_pass"): 2022,
    ("ftn_charting", "n_blitzers"): 2022,
}


def column_floor(table: str, column: str) -> int | None:
    """First usable season for ``table.column`` — the column's own floor, else its table's."""
    if (table, column) in COLUMN_FLOORS:
        return COLUMN_FLOORS[(table, column)]
    return BY_TABLE[table].floor if table in BY_TABLE else None


def assert_column_floor(table: str, column: str, season: int) -> None:
    """Raise if ``season`` is below ``table.column``'s floor, **naming the column** (T49).

    The error names the column and says how it differs from the table, because the whole failure
    mode is a query written against the table's floor getting empty seasons that look like quiet
    ones — a 2016 man/zone request returning zeros rather than raising.
    """
    floor = column_floor(table, column)
    if floor is not None and season < floor:
        table_floor = BY_TABLE[table].floor if table in BY_TABLE else None
        extra = ("" if table_floor == floor else
                 f" (the TABLE's floor is {table_floor} — this is a per-COLUMN floor, T49)")
        raise ValueError(
            f"{table}.{column} has no data before {floor}; requested {season}{extra}."
        )


def spec(table: str) -> TableSpec:
    """Registry entry for ``table``; raises if it is not declared."""
    try:
        return BY_TABLE[table]
    except KeyError:
        raise KeyError(
            f"{table!r} is not in the DATA-1 registry. Every table declares a PIT class and a "
            f"backtestable flag — add it to data/registry.py rather than reading it undeclared."
        ) from None


def assert_backtestable(table: str) -> None:
    """Raise if ``table`` is used where a backtest input is expected (B6's sibling)."""
    s = spec(table)
    if not s.backtestable:
        raise ValueError(
            f"{table} is registered backtestable=False and must not be used as a backtest "
            f"input. Reason: {s.note or 'see data/registry.py'}"
        )


def assert_pit_class_for_draft_feature(table: str, *, lagged: bool) -> None:
    """Raise if ``table`` cannot legally feed a **draft-time** feature.

    B7. ``retrospective`` is never legal. ``in_season_weekly`` is legal only through the
    season-*t−1* lag that ``features/exposures.py`` applies — so the caller must say which it is,
    and saying ``lagged=True`` when it is not is the one failure this cannot catch, which is why
    ``build_exposures`` applies the lag structurally rather than trusting a flag.
    """
    s = spec(table)
    if s.pit_class == "retrospective":
        raise ValueError(
            f"{table} is pit_class=retrospective — complete only after the season ends, so it can "
            f"never be a feature for that season. This is a leak, not a warning."
        )
    if s.pit_class == "in_season_weekly" and not lagged:
        raise ValueError(
            f"{table} is pit_class=in_season_weekly and is only draft-legal through the "
            f"season-(t-1) lag applied in features/exposures.py. Unlagged use leaks."
        )
