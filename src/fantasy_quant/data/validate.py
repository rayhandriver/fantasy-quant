"""Phase 0.8 — data validation & sanity gates (the hard-gate analog).

Ports the intern repo's ``_validate_cov_hard_gate`` philosophy to the data layer: outputs that
fail sanity never flow downstream. Two entry points:
  - :func:`validate_panel` — hard gates on a built panel (dupes, impossible values, PIT); **raises**
    with the offending detail so a bad panel fails loudly.
  - :func:`data_health_report` — store-wide coverage / join-rate / range / survivorship report,
    written to ``analysis/results/data_health.json`` (committed).

Value-range note: **counting** stats (targets/receptions/carries/attempts/snaps) can't be negative
and are gated; **yardage** is *not* gated to ≥0 (rushing/sack yardage is legitimately negative).
"""

from __future__ import annotations

import datetime as dt
import json

import pandas as pd

from fantasy_quant.config import PROJECT_ROOT
from fantasy_quant.data import db
from fantasy_quant.data.panel import assert_panel_pit

HEALTH_JSON = PROJECT_ROOT / "analysis" / "results" / "data_health.json"

_COUNTING_STATS = ["targets", "receptions", "carries", "attempts", "offense_snaps"]


# --------------------------------------------------------------------------------------------
# small query helpers
# --------------------------------------------------------------------------------------------
def _count(con, sql: str) -> int:
    return int(con.execute(sql).fetchone()[0])


def _pct_nonnull(con, table: str, col: str) -> float | None:
    r = con.execute(
        f'SELECT AVG(CASE WHEN "{col}" IS NOT NULL THEN 1.0 ELSE 0 END) FROM "{table}"'
    ).fetchone()[0]
    return round(float(r), 4) if r is not None else None


def _gate(name: str, passed: bool, **detail) -> dict:
    return {"gate": name, "passed": bool(passed), **detail}


# --------------------------------------------------------------------------------------------
# panel hard gate
# --------------------------------------------------------------------------------------------
def validate_panel(df: pd.DataFrame, as_of) -> bool:
    """Hard-gate a built panel; raise (loudly) with the offending detail on any failure."""
    problems: list[str] = []

    dups = int(df.duplicated(subset=["gsis_id", "season", "week"]).sum()) if "week" in df else \
        int(df.duplicated(subset=["gsis_id", "season"]).sum())
    if dups:
        problems.append(f"{dups} duplicate identity rows")

    for c in _COUNTING_STATS:
        if c in df.columns:
            n = int((df[c] < 0).sum())
            if n:
                problems.append(f"{n} negative {c}")

    if "offense_pct" in df.columns:
        n = int(((df["offense_pct"] < 0) | (df["offense_pct"] > 1.01)).sum())
        if n:
            problems.append(f"{n} offense_pct outside [0, 1.01]")

    if "fantasy_points_ppr" in df.columns:
        n = int(((df["fantasy_points_ppr"] < -15) | (df["fantasy_points_ppr"] > 100)).sum())
        if n:
            problems.append(f"{n} fantasy_points_ppr outside [-15, 100]")

    # PIT — raises on its own with the leaking column(s)
    assert_panel_pit(df, as_of, ["week_end_date", "adp_snapshot_date", "injury_date_modified"])

    assert not problems, f"panel validation FAILED (as_of {as_of}): {problems}"
    return True


# --------------------------------------------------------------------------------------------
# store-wide gates + report
# --------------------------------------------------------------------------------------------
def _range_gates(con) -> list[dict]:
    gates = []
    neg = _count(
        con,
        "SELECT COUNT(*) FROM weekly WHERE targets < 0 OR receptions < 0 "
        "OR carries < 0 OR attempts < 0",
    )
    gates.append(_gate("weekly: no negative counting stats", neg == 0, offending_rows=neg))

    snap_pct = _count(
        con, "SELECT COUNT(*) FROM snaps WHERE offense_pct < 0 OR offense_pct > 1.01"
    )
    gates.append(_gate("snaps: offense_pct in [0,1.01]", snap_pct == 0, offending_rows=snap_pct))

    tot = _count(
        con,
        "SELECT COUNT(*) FROM game_lines WHERE total_line IS NOT NULL "
        "AND (total_line < 20 OR total_line > 80)",
    )
    gates.append(_gate("game_lines: total_line in [20,80]", tot == 0, offending_rows=tot))

    itt = _count(
        con,
        "SELECT COUNT(*) FROM game_lines WHERE home_implied_total IS NOT NULL "
        "AND (home_implied_total < 0 OR home_implied_total > 45)",
    )
    gates.append(_gate("game_lines: implied team totals in [0,45]", itt == 0, offending_rows=itt))
    return gates


def _dup_gates(con) -> list[dict]:
    gates = []
    wk = _count(
        con,
        "SELECT COUNT(*) FROM (SELECT gsis_id, season, week, season_type, COUNT(*) c "
        "FROM weekly GROUP BY 1,2,3,4 HAVING c > 1)",
    )
    gates.append(_gate("weekly: unique (gsis,season,week,type)", wk == 0, offending_groups=wk))

    gl = _count(
        con,
        "SELECT COUNT(*) FROM (SELECT game_id, COUNT(*) c FROM game_lines GROUP BY 1 HAVING c > 1)",
    )
    gates.append(_gate("game_lines: unique game_id", gl == 0, offending_groups=gl))

    adp = _count(
        con,
        "SELECT COUNT(*) FROM (SELECT gsis_id, season, source, scoring, teams, COUNT(*) c "
        "FROM adp_snapshots WHERE gsis_id IS NOT NULL GROUP BY 1,2,3,4,5 HAVING c > 1)",
    )
    gates.append(_gate("adp: unique (gsis,season,source,scoring,teams)", adp == 0,
                       offending_groups=adp))
    return gates


def _join_rate_gates(con) -> list[dict]:
    from fantasy_quant.data.sources.adp import match_rate as adp_match
    from fantasy_quant.data.sources.nflverse import weekly_snaps_match_rate

    gates = []
    ws = weekly_snaps_match_rate(con)
    gates.append(_gate("weekly<->snaps gsis match <1%", ws["unmatched_rate"] < 0.01,
                       unmatched_rate=round(ws["unmatched_rate"], 5)))
    am = adp_match(con)
    gates.append(_gate("ADP top-150 gsis match <1%", am["top150_unmatched_rate"] < 0.01,
                       unmatched_rate=round(am["top150_unmatched_rate"], 5)))
    return gates


def _coverage(con) -> dict:
    return {
        "weekly": {c: _pct_nonnull(con, "weekly", c)
                   for c in ["gsis_id", "position", "fantasy_points_ppr", "target_share"]},
        "game_lines": {c: _pct_nonnull(con, "game_lines", c)
                       for c in ["spread_line", "total_line", "home_implied_total"]},
        "injuries": {c: _pct_nonnull(con, "injuries", c)
                     for c in ["gsis_id", "report_status", "date_modified"]},
        "adp_snapshots": {"gsis_id": _pct_nonnull(con, "adp_snapshots", "gsis_id")},
    }


def _survivorship(con, season: int = 2022) -> dict:
    """Document the survivorship limitation: drafted (ADP) players with **no** weekly appearance
    that season (injured/cut/bust) are absent from the weekly panel unless joined from ADP."""
    drafted_no_play = con.execute(
        """
        WITH board AS (
            SELECT DISTINCT gsis_id, name, adp FROM adp_snapshots
            WHERE season = ? AND scoring='ppr' AND teams=10 AND gsis_id IS NOT NULL AND adp <= 150
              AND position IN ('QB', 'RB', 'WR', 'TE')  -- K/DST aren't in offensive `weekly`
        ),
        played AS (SELECT DISTINCT gsis_id FROM weekly WHERE season = ? AND season_type='REG')
        SELECT board.name, board.adp FROM board
        LEFT JOIN played USING (gsis_id) WHERE played.gsis_id IS NULL ORDER BY board.adp
        """,
        [season, season],
    ).df()
    weekly_orphans = _count(
        con,
        "SELECT COUNT(*) FROM (SELECT DISTINCT w.gsis_id FROM weekly w "
        "LEFT JOIN player_ids p USING (gsis_id) WHERE p.gsis_id IS NULL AND w.gsis_id IS NOT NULL)",
    )
    return {
        "season_examined": season,
        "drafted_top150_no_weekly_appearance": int(len(drafted_no_play)),
        "examples": drafted_no_play.head(8).to_dict("records"),
        "weekly_gsis_not_in_player_ids": weekly_orphans,
        "note": ("Weekly panels contain only players who recorded stats; drafted-but-DNP players "
                 "must be pulled from ADP to avoid survivorship-flattered backtests."),
    }


def data_health_report(con, write: bool = True) -> dict:
    """Assemble the store-wide health report; write ``analysis/results/data_health.json``."""
    gates = _range_gates(con) + _dup_gates(con) + _join_rate_gates(con)
    tables = {t: db.row_count(con, t) for t in db.list_tables(con)}
    report = {
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "tables": tables,
        "coverage": _coverage(con),
        "gates": gates,
        "all_gates_passed": all(g["passed"] for g in gates),
        "survivorship": _survivorship(con),
    }
    if write:
        HEALTH_JSON.parent.mkdir(parents=True, exist_ok=True)
        HEALTH_JSON.write_text(json.dumps(report, indent=2, default=str))
    return report
