"""Phase 0.12.6 — the **small sources**, ingested declaratively.

Nine sources that are individually tiny and were individually never worth a session — which is
exactly how a store ends up with a first-class fact about the season being inferred from a
third-party rankings feed (T44). The point of doing them together is to stop revisiting the
question.

The list is a **declaration**, not nine hand-written functions: each entry names where the data
comes from and what its grain is, and one loop lands them. That is the 16.5 *derived-vs-curated*
rule applied to code — anything a table can answer should not be hand-maintained.

★ **``schedules`` goes first and is the one that pays immediately.** Session K2 needed bye weeks,
found no schedule table, and read byes out of ``ecr_snapshots`` — a *rankings* feed with no
obligation to carry them. That workaround is still shipping, so byes are unknown for any player
without an ECR row. ``schedules`` closes it, and it is also the cheapest real proof of the 0.12.1
loader on a genuinely new table.

★ **``contracts`` is the one small source with a live hypothesis attached.** Guaranteed money and
contract year are a plausible **role-security** signal, and role security is precisely the hole
T3 left open (unconditional coverage, role attrition — the *barely-plays* failure mode, which the
T3 diagnosis found was an availability phenomenon rather than a plays-worse one). It carries a
native ``gsis_id``, so it joins without a crosswalk. **Ingesting it is not testing it** — that is
M-series work with its own bars.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

from fantasy_quant.data import db
from fantasy_quant.data.sources import nflverse_release as nr

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SmallSource:
    """One small source: where it comes from, what grain it is, and how it is keyed."""

    table: str
    grain: str
    tag: str | None = None            # nflverse release tag
    asset: str | None = None          # asset stem within the tag
    stem: str | None = None           # per-season assets use `<stem>_<season>.parquet`
    seasons: tuple[int, ...] | None = None
    importer: str | None = None       # or an `nfl_data_py` function name
    key: tuple[str, ...] = ()
    # ★ Whether `key` is a ROW key or only a GROUP key. Declared, because the first run of 0.12.6
    # declared five keys that turned out not to be unique, and *a declared grain that does not
    # hold is worse than no declared grain* — it invites a downstream join that silently fans out.
    # Where a source genuinely has no unique row key (trades, contracts) that is recorded as a
    # fact about the source rather than papered over with a synthetic id.
    key_unique: bool = True
    note: str = ""
    pit_class: str = "retrospective"
    backtestable: bool = True
    rename: dict = field(default_factory=dict)


SMALL_SOURCES: tuple[SmallSource, ...] = (
    SmallSource(
        table="schedules", grain="game", tag="schedules", asset="games",
        key=("game_id",), pit_class="preseason",
        rename={},
        note=(
            "The season's fixture list: kickoff, teams, result, and — the reason it is first — "
            "the structure byes are derived from. Closes T44, which had 14.F reading byes out of "
            "ecr_snapshots. Available before a draft, hence pit_class=preseason."
        ),
    ),
    SmallSource(
        table="qbr_week", grain="player-week", tag="espn_data", asset="qbr_week_level",
        key=("season", "game_id", "player_id"), pit_class="in_season_weekly",
        note="ESPN QBR at week grain, 2006-. A QB quality read independent of our own scoring.",
    ),
    SmallSource(
        table="qbr_season", grain="player-season-type", tag="espn_data",
        asset="qbr_season_level",
        key=("season", "season_type", "player_id"), pit_class="retrospective",
        note=(
            "ESPN QBR at season grain. Retrospective: complete only once the season is over. "
            "`season_type` is part of the grain — regular season and postseason are separate "
            "rows, which is what made (season, player_id) non-unique on the first run."
        ),
    ),
    SmallSource(
        table="contracts", grain="contract", tag="contracts",
        asset="historical_contracts", key=("otc_id", "year_signed"), key_unique=False,
        pit_class="preseason",
        note=(
            "OverTheCap contract history, native gsis_id. The role-security hypothesis (T3's "
            "open hole) lives here: guaranteed money and contract year as a proxy for how safe a "
            "starter's job is. Ingested, NOT tested — that is M-series work.\n"
            "⚠ NO UNIQUE ROW KEY, and this is a property of the source, not of our load: a "
            "practice-squad churner signs many small deals in one year and OTC emits some of "
            "them as byte-identical rows (3,339 fully-duplicate rows overall; one 2022 WR has "
            "eleven). Any per-player aggregate here must aggregate deliberately — a naive join "
            "on otc_id fans out."
        ),
    ),
    SmallSource(
        table="otc_player_ids", grain="player", tag="players_components", asset="otc_players",
        key=("otc_id",), pit_class="preseason",
        note="OTC id -> gsis crosswalk, so contracts join the rest of the store.",
    ),
    SmallSource(
        table="players_master", grain="player", tag="players_components", asset="players",
        key=("gsis_id",), pit_class="preseason",
        note=(
            "nflverse's own player master (24.5k rows, every id system + birth_date + position "
            "group). Wider than our player_ids crosswalk; kept beside it, not merged — "
            "player_ids is the provenance of every existing join."
        ),
    ),
    SmallSource(
        table="officials", grain="game-official", tag="officials", asset="officials",
        key=("game_id", "official_id"), pit_class="retrospective",
        note="Officiating crews, 2015-. Crew-level penalty tendency is the standing hypothesis.",
    ),
    SmallSource(
        table="trades", grain="trade-asset", tag="trades", asset="trades",
        key=("trade_id",), key_unique=False, pit_class="preseason",
        note=(
            "Trade transactions, 2002-. ONE ROW PER ASSET MOVED, not per trade — `trade_id` is "
            "a group key (up to 10 rows share one). Relevant to 16.5, whose `mechanism` is the "
            "one irreducibly-human field on a table that is otherwise derived (111 rows still "
            "`unknown`) — this is the feed that could answer trade-vs-free-agent."
        ),
    ),
    SmallSource(
        table="weekly_rosters", grain="player-week-status", tag="weekly_rosters",
        stem="roster_weekly", seasons=tuple(range(2014, 2027)),
        key=("season", "week", "gsis_id", "team", "status", "position"), key_unique=False,
        pit_class="in_season_weekly",
        note=(
            "Roster status per player-week (active/inactive/IR), 2014-2026. The honest "
            "availability record: distinguishes 'did not play' from 'was not on the roster', "
            "which is the distinction T3's cohort availability prior is built around.\n"
            "⚠ The grain is player-week-STATUS, not player-week: one player-week carries a row "
            "per roster transaction (ACT/TRC/TRT/TRD), so a player-week join must pick a status "
            "or it fans out. Five residual duplicates remain even on the full key, and six 2026 "
            "week-1 rows have a null gsis_id (unsigned players)."
        ),
    ),
    SmallSource(
        table="teams_meta", grain="team", tag="teams", asset="teams_colors_logos",
        key=("team_abbr",), pit_class="preseason",
        note=("Team codes, conference/division, colours. Division structure feeds the "
              "playoff-SOS readout (14.H)."),
    ),
    SmallSource(
        table="draft_values", grain="pick", importer="import_draft_values",
        key=("pick",), pit_class="preseason",
        note=(
            "Draft-pick trade-value charts (Stuart/Johnson/Hill/OTC/PFF). Not an NFL-draft table "
            "— it is the pick-value curve, and the natural prior for a FANTASY pick's value in "
            "the 13.5 trade evaluator."
        ),
    ),
    SmallSource(
        table="sc_lines", grain="game-side-line", importer="import_sc_lines",
        key=("game_id", "side", "line"), pit_class="preseason",
        note="Scoring-market lines by side. Beside game_lines, which stays the spine.",
    ),
    SmallSource(
        table="win_totals", grain="game-market-book", importer="import_win_totals",
        key=("game_id", "market_type", "abbr", "book"), pit_class="preseason",
        note=(
            "⚠ nfl_data_py itself warns this source 'is currently in flux and may be out of "
            "date'. Landed for completeness and registered with that warning; it is NOT a "
            "substitute for game_lines, which is the validated market spine."
        ),
    ),
)


def ingest_small(con, src: SmallSource, refresh: bool = False) -> dict:
    """Land one small source. Returns a per-source report."""
    if src.importer:
        import nfl_data_py as nfl

        df = getattr(nfl, src.importer)()
    elif src.stem:
        published = set(nr.available_seasons(src.tag, src.stem))
        want = sorted(set(src.seasons or ()) & published)
        df = nr.read_seasons(src.tag, src.stem, want, refresh=refresh)
        df = df.drop(columns=[c for c in ("_source_season",) if c in df.columns])
    else:
        df = nr.read_release(src.tag, f"{src.asset}.parquet", refresh=refresh)

    if src.rename:
        df = df.rename(columns=src.rename)
    # pandas nullable/extension dtypes that DuckDB cannot infer are cast to string rather than
    # silently dropped — a column we cannot type is still a column we want registered.
    for c in df.columns:
        if df[c].dtype == "object":
            df[c] = df[c].astype("string")
    db.write_df(con, src.table, df)

    missing_key = [k for k in src.key if k not in df.columns]
    n_dup = 0
    if not missing_key and src.key:
        n_dup = int(len(df) - len(df.drop_duplicates(list(src.key))))
    seasons = (
        sorted(int(s) for s in pd.to_numeric(df["season"], errors="coerce").dropna().unique())
        if "season" in df.columns else []
    )
    return {
        "table": src.table,
        "grain": src.grain,
        "source": src.importer or f"{src.tag}/{src.asset or src.stem}",
        "n_rows": len(df),
        "n_cols": df.shape[1],
        "seasons": [seasons[0], seasons[-1]] if seasons else None,
        "n_seasons": len(seasons),
        "key": list(src.key),
        "key_columns_missing": missing_key,
        "n_duplicate_keys": n_dup,
        "key_declared_unique": src.key_unique,
        # the bar is that the DECLARATION is true, in both directions — a key declared unique that
        # is not is a trap, and a key declared non-unique that turns out unique is a stale note
        "key_declaration_holds": (
            (n_dup == 0) if src.key_unique else (n_dup > 0)
        ) and not missing_key,
        "pit_class": src.pit_class,
        "backtestable": src.backtestable,
        "note": src.note,
    }


def ingest_all_small(con, refresh: bool = False) -> list[dict]:
    out = []
    for src in SMALL_SOURCES:
        try:
            out.append(ingest_small(con, src, refresh=refresh))
        except Exception as e:  # one flaky vendor must not sink the other twelve
            log.warning("small source %s failed: %s", src.table, e)
            out.append({"table": src.table, "error": f"{type(e).__name__}: {e}"})
    return out


# --------------------------------------------------------------------------------------------
# T44 — byes from the schedule, instead of from a rankings feed
# --------------------------------------------------------------------------------------------
def bye_weeks(con, season: int) -> pd.DataFrame:
    """``team, bye_week`` for a season, derived from ``schedules``.

    ★ This is T44's fix. The shipped workaround reads byes out of ``ecr_snapshots``, so a player
    with no ECR row has an unknown bye — rendered honestly on screen, but inferred from a feed
    with no obligation to carry it. A bye is a fact about the fixture list, and here it is derived
    from the fixture list: the weeks in the regular-season range in which a team does not appear.
    """
    q = """
        with games as (
            select season, week, home_team as team from schedules
            where season = ? and game_type = 'REG'
            union all
            select season, week, away_team as team from schedules
            where season = ? and game_type = 'REG'
        ),
        weeks as (select distinct week from games),
        teams as (select distinct team from games)
        select t.team, w.week as bye_week
        from teams t cross join weeks w
        where not exists (
            select 1 from games g where g.team = t.team and g.week = w.week
        )
        order by t.team, w.week
    """
    return con.execute(q, [season, season]).df()
