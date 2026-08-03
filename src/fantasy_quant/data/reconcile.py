"""Phase 0.12.7 — **reconciliation**: one depth-chart table, one season type, one team canon.

Cleaning that had been deferred because each piece was individually survivable. Together they are
the difference between a store you can ask a new question of and one you have to remember the
quirks of, which is the whole point of DATA-1.

★ **The finding this substep turned up, and it is worse than the one it went looking for.**
The scoped defect was "``depth_charts`` stops at 2024 and 2025 lives separately in
``depth_charts_ts``". That is not what is on disk. ``depth_charts`` has **955,989 rows, and
554,215 of them — 58 % — ARE the ts series**, appended during the Phase-0.9 backfill with a
**NULL ``season``**. So:

* the table holds **two different grains** (2014-2024 weekly depth charts keyed by
  ``season``/``week``/``depth_team``; a 2025 timestamped snapshot series keyed by ``dt``), and the
  only thing distinguishing them is *which columns happen to be null*;
* any ``group by season`` over it **silently drops 58 % of the table**, and reports a season range
  ending in 2024 — which is exactly what the scoping saw and read as "the data stops at 2024";
* ``depth_charts_ts`` is not a *separate* 2025 store, it is a **duplicate** of those rows.

*A table that silently answers a different question depending on which rows you land on is not a
table with a missing season; it is two tables sharing a name.* The fix is to make the grain a
**column** instead of an inference, so a reader cannot fail to notice which one they have.

⚠ **This substep is the one place in DATA-1 that is not purely additive**, so it is declared: it
rewrites ``depth_charts.season``/``week`` and ``injuries.season`` from DOUBLE to INT. Those are
**value-preserving** casts (``2014.0`` -> ``2014``) and 0.12.7's bar proves the values round-trip.
B0 carries them as **named allowances** and still fails on any unclassified change.
"""

from __future__ import annotations

import logging

import pandas as pd

from fantasy_quant.adp.panel import _canon_team
from fantasy_quant.data import db

log = logging.getLogger(__name__)

UNIFIED_TABLE = "depth_charts_all"

# The DOUBLE-typed season/week columns. Named, not discovered at runtime, so B0's allowance list
# and the thing that does the work cannot drift apart.
DOUBLE_SEASON_COLS: dict[str, tuple[str, ...]] = {
    "depth_charts": ("season", "week"),
    "injuries": ("season",),
}


def double_to_int_seasons(con, spec: dict = DOUBLE_SEASON_COLS) -> list[dict]:
    """Cast DOUBLE ``season``/``week`` columns to INT **in place**, proving values are preserved.

    A season stored as ``2014.0`` joins a season stored as ``2014`` only by implicit cast, and
    every such cast is a place a future join can silently return nothing. The cast is safe here
    precisely because it is checked: a value with a fractional part would be *destroyed* by it, so
    the count of such values is asserted to be zero before the rewrite rather than after.
    """
    out = []
    for table, cols in spec.items():
        types = dict(con.execute(
            "select column_name, data_type from information_schema.columns where table_name = ?",
            [table],
        ).fetchall())
        for col in cols:
            if types.get(col) not in ("DOUBLE", "FLOAT", "REAL"):
                out.append({"table": table, "column": col, "action": "skipped",
                            "reason": f"already {types.get(col)}"})
                continue
            n_frac = con.execute(
                f'select count(*) from "{table}" '
                f'where "{col}" is not null and "{col}" <> floor("{col}")'
            ).fetchone()[0]
            if n_frac:
                raise ValueError(
                    f"{table}.{col} has {n_frac} non-integral values — the cast would destroy "
                    f"them; investigate before converting"
                )
            before = con.execute(
                f'select count("{col}"), sum("{col}") from "{table}"'
            ).fetchone()
            con.execute(f'alter table "{table}" alter "{col}" type INTEGER')
            after = con.execute(
                f'select count("{col}"), sum("{col}") from "{table}"'
            ).fetchone()
            out.append({
                "table": table, "column": col, "action": "cast DOUBLE->INTEGER",
                "n_nonnull_before": int(before[0]), "n_nonnull_after": int(after[0]),
                "sum_before": float(before[1] or 0), "sum_after": float(after[1] or 0),
                "values_preserved": bool(before[0] == after[0]
                                         and float(before[1] or 0) == float(after[1] or 0)),
            })
    return out


def build_depth_charts_all(con) -> dict:
    """Unify the two depth-chart grains into ``depth_charts_all`` with an explicit ``grain``.

    Kept as a **new** table rather than a rewrite of ``depth_charts``: that table is the
    provenance of existing readers, and the loader-beside-the-wrapper principle applies here too.
    What changes is that a reader now has a table where the grain is a column they must look at.

    ``season`` is filled for the snapshot rows from ``depth_charts_ts.source_year`` (2025), so the
    table genuinely covers 2014-2025 and ``group by season`` stops lying.
    """
    con.execute(f"""
        create or replace table {UNIFIED_TABLE} as
        -- (a) the legacy weekly grain, 2014-2024
        select
            cast(season as integer)      as season,
            cast(week as integer)        as week,
            'weekly'                     as grain,
            club_code                    as team_raw,
            depth_team                   as depth_order,
            game_type, formation, gsis_id, position, depth_position,
            coalesce(full_name, player_name)  as player_name,
            cast(null as varchar)        as asof_dt,
            pos_grp, pos_abb, pos_name,
            cast(pos_slot as integer)    as pos_slot,
            cast(pos_rank as integer)    as pos_rank,
            pulled_at
        from depth_charts
        where season is not null
        union all
        -- (b) the 2025 timestamped snapshot series, whose season lives in source_year
        select
            cast(t.source_year as integer) as season,
            cast(null as integer)          as week,
            'snapshot'                     as grain,
            t.team                         as team_raw,
            cast(null as varchar)          as depth_order,
            cast(null as varchar)          as game_type,
            cast(null as varchar)          as formation,
            t.gsis_id,
            t.pos_abb                      as position,
            t.pos_name                     as depth_position,
            t.player_name,
            t.dt                           as asof_dt,
            t.pos_grp, t.pos_abb, t.pos_name,
            cast(t.pos_slot as integer)    as pos_slot,
            cast(t.pos_rank as integer)    as pos_rank,
            t.pulled_at
        from depth_charts_ts t
    """)
    # one team canon across both halves — the LA/LAR lesson, applied at the point of unification
    df = con.execute(f"select team_raw from {UNIFIED_TABLE}").df()
    canon = _canon_team(df["team_raw"]).astype("string")
    con.register("_canon", pd.DataFrame({"team": canon}))
    con.execute(f"""
        create or replace table {UNIFIED_TABLE} as
        select u.* replace (u.team_raw as team_raw), c.team
        from (select *, row_number() over () as _rn from {UNIFIED_TABLE}) u
        join (select *, row_number() over () as _rn from _canon) c using (_rn)
    """)
    con.execute(f"alter table {UNIFIED_TABLE} drop column _rn")
    con.unregister("_canon")

    rows = con.execute(f"""
        select grain, min(season) as s0, max(season) as s1, count(*) as n,
               count(distinct season) as n_seasons
        from {UNIFIED_TABLE} group by 1 order by 1
    """).df()
    total, n_seasons = con.execute(
        f"select count(*), count(distinct season) from {UNIFIED_TABLE}"
    ).fetchone()
    seasons = [
        int(s) for (s,) in con.execute(
            f"select distinct season from {UNIFIED_TABLE} order by 1"
        ).fetchall()
    ]
    return {
        "table": UNIFIED_TABLE,
        "n_rows": int(total),
        "n_seasons": int(n_seasons),
        "seasons": seasons,
        "by_grain": rows.to_dict("records"),
        "season_complete_2014_2025": seasons == list(range(2014, 2026)),
    }


def crosswalk_match_rates(con, tables: dict[str, str]) -> list[dict]:
    """gsis match rate against ``player_ids``, per table and per position where known.

    Reported, not gated — because the honest number is not 100 % and should not be forced to be.
    ``participation`` carries **all eleven** offensive players, so its misses are dominated by
    offensive linemen, who have never been in this store's crosswalk and are not wanted in it.
    A match rate is only interpretable next to *who* is missing.
    """
    out = []
    for table, col in tables.items():
        if not db.table_exists(con, table):
            continue
        total, matched = con.execute(f"""
            select count(*), count(i.gsis_id)
            from "{table}" t left join player_ids i on i.gsis_id = t."{col}"
            where t."{col}" is not null and t."{col}" <> ''
        """).fetchone()
        # who is missing, by position — from nflverse's own player master where we have it
        by_pos = []
        if db.table_exists(con, "players_master"):
            by_pos = con.execute(f"""
                select coalesce(p.position, '(unknown)') as position, count(*) as n
                from "{table}" t
                left join player_ids i on i.gsis_id = t."{col}"
                left join players_master p on p.gsis_id = t."{col}"
                where i.gsis_id is null and t."{col}" is not null and t."{col}" <> ''
                group by 1 order by n desc limit 8
            """).df().to_dict("records")
        out.append({
            "table": table,
            "id_column": col,
            "n_rows_with_id": int(total),
            "n_matched": int(matched),
            "match_rate": round(matched / total, 4) if total else None,
            "top_unmatched_positions": by_pos,
        })
    return out
