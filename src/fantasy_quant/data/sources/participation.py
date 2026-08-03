"""Phase 0.12.3-0.12.4 — **nflverse participation**, at play grain and per player-week.

Ten seasons (2016-2025) of one row per play carrying what no public site publishes together:
``defenders_in_box`` · ``offense_personnel``/``defense_personnel`` · ``offense_formation`` ·
``defense_man_zone_type``/``defense_coverage_type`` · ``route`` · ``was_pressure`` ·
``time_to_throw`` · ``number_of_pass_rushers`` — **and the gsis ids of all 22 men on the field**,
which is what turns every one of those from a team-level fact into a per-player one *conditional on
personnel grouping*.

It has no ``nfl_data_py`` wrapper function, which is the only reason it was not already here
(0.12.1's docstring; T46).

★ **The grain decision, and why it is not the obvious one.** The exploded player-play form —
``offense_players`` split on ``;`` — is ~46k plays x 22 players x 10 seasons ≈ **100M rows**,
larger than every other table in this store combined. So:

* :func:`ingest_participation` lands **play grain** (~470k rows). Cheap, and it means a question
  nobody anticipated never needs a re-ingest, which was the explicit ask.
* :func:`build_participation_player_week` materializes the **player-week** aggregate, which is the
  grain every downstream question is actually asked at (~5k rows/week).
* :func:`player_play_view` creates the exploded form as a **VIEW** — computed on demand, never
  stored. DuckDB's ``unnest(str_split(...))`` does the explode at query time.

⚠ **Fill rates only mean something against the right denominator.** ``route``,
``defense_man_zone_type`` and ``was_pressure`` sit near 0.38 of *all* rows, and the next person to
look will read that as 62 % missing. It is not: it is the **pass-play share of the row count**.
Personnel and box are ~0.76 for 2016-2022 and 1.00 from 2023. The genuine holes are
``defense_coverage_type`` (~0.50 throughout) and ``ngs_air_yards``, which **stopped being
populated in 2023** — a silent vendor degradation, and the reason 0.12.8 has a fill-rate gate.
"""

from __future__ import annotations

import logging

import pandas as pd

from fantasy_quant.adp.panel import _canon_team
from fantasy_quant.data import db
from fantasy_quant.data.sources import nflverse_release as nr

log = logging.getLogger(__name__)

TAG = "pbp_participation"
STEM = "pbp_participation"
TABLE = "participation"
WEEK_TABLE = "participation_player_week"
PLAYER_PLAY_VIEW = "participation_player_play"

PARTICIPATION_SEASONS = list(range(2016, 2026))

# The six columns that appear only from 2023 (20-col files -> 26-col files). Named, not inferred,
# so a *seventh* one appearing upstream shows up as an unexpected column rather than as silence.
DRIFT_COLS_2023 = [
    "offense_names", "defense_names",
    "offense_positions", "defense_positions",
    "offense_numbers", "defense_numbers",
]

# Columns whose natural denominator is pass plays, not all plays (the B5 rule).
PASS_PLAY_COLS = ["route", "was_pressure", "time_to_throw", "number_of_pass_rushers",
                  "defense_man_zone_type", "defense_coverage_type", "ngs_air_yards"]


# --------------------------------------------------------------------------------------------
# 0.12.3 — play grain
# --------------------------------------------------------------------------------------------
def normalize_participation(df: pd.DataFrame) -> pd.DataFrame:
    """Conform a raw participation frame so it joins ``pbp`` and carries a canonical team code.

    Three things, each of which has burned this repo before:

    1. ``play_id`` is ``int32`` here and ``FLOAT`` in ``pbp``. Joining across that works in DuckDB
       but only by implicit cast; we make it explicit so the join key has one type.
    2. ``possession_team`` carries the **era-accurate** codes ``LA``/``OAK``/``SD``. Routing them
       through ``_canon_team`` is not tidying — 16.4's first run silently deleted Sean McVay's
       entire Rams tenure on exactly this, and *a missing entity and a failed join look identical*.
       The raw code is kept beside it, because the era-accurate code is the truth about that season.
    3. Empty strings are not missing values. ``possession_team`` and the player lists use ``''``
       for absent; left alone, ``count(col)`` reports them as present and every fill rate lies.
    """
    df = df.copy()
    df = df.rename(columns={"nflverse_game_id": "game_id"})
    df["play_id"] = df["play_id"].astype("int64")

    for c in ("possession_team", "offense_personnel", "defense_personnel", "offense_formation",
              "route", "defense_man_zone_type", "defense_coverage_type",
              "players_on_play", "offense_players", "defense_players"):
        if c in df.columns:
            s = df[c].astype("string").str.strip()
            df[c] = s.mask(s.eq(""), pd.NA)

    df["possession_team_raw"] = df["possession_team"]
    df["possession_team"] = _canon_team(df["possession_team"])

    if "was_pressure" in df.columns:  # object-dtype bool with NA; make it a real nullable bool
        df["was_pressure"] = df["was_pressure"].astype("boolean")

    # season/week come from the game id (`2016_01_CAR_DEN`), so the table stands on its own
    # without requiring the pbp join for something as basic as "which week is this".
    gid = df["game_id"].astype("string")
    df["season"] = pd.to_numeric(gid.str.slice(0, 4), errors="coerce").astype("Int64")
    df["week"] = pd.to_numeric(gid.str.slice(5, 7), errors="coerce").astype("Int64")

    for c in DRIFT_COLS_2023:  # explicit NULLs for the pre-2023 seasons, never a dropped column
        if c not in df.columns:
            df[c] = pd.Series(pd.NA, index=df.index, dtype="string")
    return df


def ingest_participation(con, seasons=PARTICIPATION_SEASONS, refresh: bool = False) -> dict:
    """Land ``participation`` at play grain for ``seasons``. Returns an ingest report."""
    raw = nr.read_seasons(TAG, STEM, seasons, refresh=refresh)
    n_raw = len(raw)
    df = normalize_participation(raw)

    # B2: zero rows dropped silently. A row with no (game_id, play_id) cannot join or be counted,
    # so it is dropped — but it is *counted and reasoned*, per the assert_regime_coverage rule.
    bad_key = df["game_id"].isna() | df["play_id"].isna()
    dropped = int(bad_key.sum())
    df = df.loc[~bad_key].reset_index(drop=True)

    df = df.drop(columns=[c for c in ("_source_season",) if c in df.columns])
    db.write_df(con, TABLE, df)
    per_season = (
        df.groupby("season", dropna=False).size().rename("n_rows").reset_index()
        .astype({"n_rows": int}).to_dict("records")
    )
    log.info("participation: %d rows, %d seasons", len(df), df["season"].nunique())
    return {
        "table": TABLE,
        "n_rows": len(df),
        "n_raw": n_raw,
        "n_dropped": dropped,
        "drop_reason": "missing (game_id, play_id) — cannot join or be attributed",
        "seasons": sorted(int(s) for s in df["season"].dropna().unique()),
        "n_cols": df.shape[1],
        "per_season": per_season,
    }


# --------------------------------------------------------------------------------------------
# fill rates — with their denominators (B5)
# --------------------------------------------------------------------------------------------
def fill_rates(con, table: str = TABLE) -> pd.DataFrame:
    """Per column, per season: the unconditional fill rate **and** the conditional one.

    Every rate in the register is stated against its correct denominator, with the unconditional
    rate shown beside it — because the unconditional number is the one a reader will otherwise
    quote, and for the charting columns it is wrong by a factor of the pass rate.
    """
    cols = [
        c for (c,) in con.execute(
            "select column_name from information_schema.columns "
            "where table_name = ? order by ordinal_position", [table]
        ).fetchall()
    ]
    skip = {"season", "week", "game_id", "play_id", "pulled_at"}
    cols = [c for c in cols if c not in skip]
    # one pass over the join, not one per column — 26 columns x 470k rows is a scan we only want
    # to pay for once
    aggs = ", ".join(
        f'count(p."{c}") as "f_{c}", '
        f'count(p."{c}") filter (where b.play_type = \'pass\') as "fp_{c}"'
        for c in cols
    )
    q = f"""
        select p.season,
               count(*) as n_rows,
               count(*) filter (where b.play_type = 'pass') as n_pass,
               {aggs}
        from "{table}" p
        left join pbp b using (game_id, play_id)
        group by 1 order by 1
    """
    raw = con.execute(q).df()
    rows = []
    for _, r in raw.iterrows():
        n_rows, n_pass = int(r["n_rows"]), int(r["n_pass"])
        for c in cols:
            conditional = c in PASS_PLAY_COLS
            rows.append({
                "column": c,
                "season": int(r["season"]),
                "n_rows": n_rows,
                "fill_unconditional": round(r[f"f_{c}"] / n_rows, 4) if n_rows else None,
                "denominator": "pass_plays" if conditional else "all_plays",
                "fill_conditional": (
                    round(r[f"fp_{c}"] / n_pass, 4) if conditional and n_pass else None
                ),
                "n_pass": n_pass,
            })
    return pd.DataFrame(rows)


def join_rate(con, table: str = TABLE) -> pd.DataFrame:
    """B3 — per season, the share of participation plays that find a ``pbp`` row.

    ★ **A join rate needs its denominator just as much as a fill rate does** — B5's lesson, one
    level up, and it cost this bar a false failure before it was noticed. The raw rate is ~0.984
    for 2016-2022 and exactly 1.000 from 2023, which looks like a decaying-backwards data problem
    and is not one. The vendor emits an **empty placeholder row** (``n_offense = n_defense = 0``,
    no team, no personnel, no player lists) for plays ``pbp`` does not carry at all — roughly 780
    a season — and stopped doing it in 2023. Those rows contain nothing to join *with*.

    Measured on rows that carry participation content, the rate is **1.00000** in every season
    (four exceptions in 344k rows). So both are reported: ``match_rate`` for fidelity to what is
    in the table, ``match_rate_content`` for the claim the bar is actually making, which is that
    participation is joinable to ``pbp``.
    """
    q = f"""
        select p.season,
               count(*) as n_participation,
               count(b.play_id) as n_matched,
               round(count(b.play_id) / count(*), 5) as match_rate,
               count(*) filter (where p.n_offense = 0 and p.n_defense = 0) as n_empty_rows,
               count(*) filter (where not (p.n_offense = 0 and p.n_defense = 0))
                                                                        as n_content_rows,
               round(
                 count(b.play_id) filter (where not (p.n_offense = 0 and p.n_defense = 0))
                 / nullif(count(*) filter (where not (p.n_offense = 0 and p.n_defense = 0)), 0),
                 5
               ) as match_rate_content
        from "{table}" p
        left join pbp b using (game_id, play_id)
        group by 1 order by 1
    """
    return con.execute(q).df()


# --------------------------------------------------------------------------------------------
# 0.12.4 — the player-play view (NEVER materialized) and the player-week aggregate
# --------------------------------------------------------------------------------------------
def player_play_view(con, table: str = TABLE) -> None:
    """Create the exploded 22-men-on-the-field form as a **view**.

    This is the shape that answers a question nobody has asked yet, and it is ~100M rows if
    stored. As a view it costs nothing until queried and cannot go stale relative to the play
    table. ``side`` distinguishes the offensive from the defensive participation record.
    """
    con.execute(f"""
        create or replace view {PLAYER_PLAY_VIEW} as
        select season, week, game_id, play_id, possession_team,
               offense_formation, offense_personnel, defense_personnel,
               defenders_in_box, number_of_pass_rushers,
               defense_man_zone_type, defense_coverage_type, was_pressure, route,
               'offense' as side,
               unnest(str_split(offense_players, ';')) as gsis_id
        from "{table}" where offense_players is not null
        union all
        select season, week, game_id, play_id, possession_team,
               offense_formation, offense_personnel, defense_personnel,
               defenders_in_box, number_of_pass_rushers,
               defense_man_zone_type, defense_coverage_type, was_pressure, route,
               'defense' as side,
               unnest(str_split(defense_players, ';')) as gsis_id
        from "{table}" where defense_players is not null
    """)


def build_participation_player_week(con, table: str = TABLE) -> dict:
    """Materialize ``participation_player_week`` — offensive participation per player-week.

    One row per (season, week, gsis_id, team). Carries snap counts overall and **by personnel
    grouping** (11/12/13/21/...), route participation, and the defensive context the player's
    offense faced while he was on the field: mean ``defenders_in_box``, man/zone share, pressure
    rate. That last group is the point — a box count is a team-level fact until you condition it
    on who was actually out there, and this is the only free source that lets you.

    Restricted to the **offensive** side: the defensive record is available through the view, but
    the fantasy questions are all offensive and materializing both doubles the table for nothing.
    """
    player_play_view(con, table)
    con.execute(f"""
        create or replace table {WEEK_TABLE} as
        with pp as (
            select v.season, v.week, v.game_id, v.play_id, v.gsis_id,
                   v.possession_team as team,
                   v.offense_personnel, v.defenders_in_box, v.was_pressure,
                   v.route, v.defense_man_zone_type,
                   b.play_type,
                   -- "11 personnel" is the conventional shorthand for the RB/TE counts; derive it
                   -- rather than storing the prose string, so a grouping can be compared across
                   -- seasons where the vendor's spacing/ordering differs.
                   coalesce(
                     regexp_extract(v.offense_personnel, '(\\d+) RB', 1), ''
                   ) || coalesce(
                     regexp_extract(v.offense_personnel, '(\\d+) TE', 1), ''
                   ) as personnel_code
            from {PLAYER_PLAY_VIEW} v
            left join pbp b using (game_id, play_id)
            where v.side = 'offense' and v.gsis_id is not null and v.gsis_id <> ''
        )
        select
            season, week, gsis_id, team,
            count(*)                                              as snaps,
            count(*) filter (where play_type = 'pass')            as pass_snaps,
            count(*) filter (where play_type = 'run')             as run_snaps,
            count(*) filter (where personnel_code = '11')         as snaps_p11,
            count(*) filter (where personnel_code = '12')         as snaps_p12,
            count(*) filter (where personnel_code = '13')         as snaps_p13,
            count(*) filter (where personnel_code = '21')         as snaps_p21,
            count(*) filter (where personnel_code not in ('11','12','13','21')
                             and personnel_code <> '')            as snaps_p_other,
            count(route)                                          as routes,
            count(route) filter (where play_type = 'pass')        as routes_on_pass,
            avg(defenders_in_box)                                 as box_faced_mean,
            avg(defenders_in_box) filter (where play_type = 'run') as box_faced_mean_run,
            count(*) filter (where defenders_in_box >= 8)          as snaps_box_8plus,
            count(*) filter (where defense_man_zone_type = 'MAN_COVERAGE')  as snaps_vs_man,
            count(*) filter (where defense_man_zone_type = 'ZONE_COVERAGE') as snaps_vs_zone,
            count(*) filter (where was_pressure)                   as snaps_pressure,
            current_localtimestamp()                               as pulled_at
        from pp
        group by 1, 2, 3, 4
    """)
    # snap *share* needs the team-week denominator, which is only known after the group-by
    con.execute(f"""
        create or replace table {WEEK_TABLE} as
        select w.*,
               round(w.snaps / t.team_plays, 4)  as snap_share,
               round(w.routes / nullif(t.team_pass_plays, 0), 4) as route_share,
               round(w.snaps_vs_man / nullif(w.snaps_vs_man + w.snaps_vs_zone, 0), 4)
                                                 as man_share_faced
        from {WEEK_TABLE} w
        join (
            select p.season, p.week, p.possession_team as team,
                   count(*) as team_plays,
                   count(*) filter (where b.play_type = 'pass') as team_pass_plays
            from "{table}" p left join pbp b using (game_id, play_id)
            where p.possession_team is not null
            group by 1, 2, 3
        ) t using (season, week, team)
    """)
    n, npl, seasons = con.execute(
        f"select count(*), count(distinct gsis_id), count(distinct season) from {WEEK_TABLE}"
    ).fetchone()
    return {"table": WEEK_TABLE, "n_rows": int(n), "n_players": int(npl),
            "n_seasons": int(seasons), "view": PLAYER_PLAY_VIEW}
