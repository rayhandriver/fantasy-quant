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

from fantasy_quant.config import FANTASY_SEASONS, PROJECT_ROOT
from fantasy_quant.data import db
from fantasy_quant.data.panel import assert_panel_pit

HEALTH_JSON = PROJECT_ROOT / "analysis" / "results" / "data_health.json"

_COUNTING_STATS = ["targets", "receptions", "carries", "attempts", "offense_snaps"]

# --- T7 scrape freshness / schema guard thresholds ------------------------------------------
# The external scrapes (FFC ADP, FantasyPros consensus) are the value/availability spine and rot
# silently when a site's markup changes or the recurring pull lapses. These turn the CLAUDE.md §2
# Stage-0 chore + "sane board" expectations into hard, test-visible gates that fail loudly.
ADP_MAX_AGE_DAYS = 6            # live-season FFC snapshot must be at most this stale (the §2 chore)
FP_BOARD_ROW_BAND = (400, 700)  # a full FantasyPros consensus board sits here (2026 = 528)
GSIS_MATCH_FLOOR = 0.95         # consensus-board identity match floor (2026 ran ~0.99)
MANAGER_REACH_MAX_ROUNDS = 2.0  # T18: a profile reach past this is a join defect, not a manager


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
# T7 — scrape freshness / schema guards (pure, injectable; the DB wrapper is `_scrape_gates`)
# --------------------------------------------------------------------------------------------
def adp_freshness_gate(latest_snapshot_date, today, *, live_season, newest_completed_season,
                       max_age_days: int = ADP_MAX_AGE_DAYS) -> dict:
    """Gate: the *live-season* FFC ADP snapshot series is fresh (≤ ``max_age_days`` old).

    This promotes the CLAUDE.md §2 Stage-0 chore to a hard, test-visible assertion. It only fires
    for an **in-progress** draft cycle (``live_season > newest_completed_season``) — the board we
    actively re-snapshot. A dev store holding only historical single snapshots has nothing to keep
    fresh, so the gate passes as not-applicable. Pure: pass real dates in from the DB wrapper.
    """
    if live_season is None or live_season <= newest_completed_season:
        return _gate("adp: live-season snapshot fresh", True, applicable=False)
    if latest_snapshot_date is None:
        return _gate("adp: live-season snapshot fresh", False, live_season=live_season,
                     reason="no snapshot for live season")
    age = (today - latest_snapshot_date).days
    return _gate("adp: live-season snapshot fresh", age <= max_age_days,
                 live_season=live_season, latest=str(latest_snapshot_date), age_days=age,
                 max_age_days=max_age_days)


def board_size_gate(name: str, n_rows: int, band: tuple[int, int] = FP_BOARD_ROW_BAND) -> dict:
    """Gate: a scraped board's row count sits in a sane band — a truncated/empty page (markup
    change, shell) falls below the floor and trips the gate instead of ingesting silently."""
    lo, hi = band
    return _gate(name, lo <= n_rows <= hi, n_rows=n_rows, band=[lo, hi])


def match_rate_gate(name: str, rate, floor: float = GSIS_MATCH_FLOOR) -> dict:
    """Gate: identity (gsis) match rate is at or above ``floor``; a markup/name-format break shows
    up here as a coverage drop. ``None`` (no rows) fails loudly rather than passing vacuously."""
    ok = rate is not None and rate >= floor
    return _gate(name, ok, match_rate=None if rate is None else round(float(rate), 4), floor=floor)


# --- step 0.10 Sleeper ingest guards (pure; DB wrapper is `_sleeper_gates`) ------------------
def sleeper_picks_gate(name: str, *, n_picks: int, expected_picks: int, min_pick: int,
                       max_pick: int, n_distinct: int) -> dict:
    """Gate: a draft's picks are complete + well-formed — exactly ``teams*rounds`` picks, numbered
    contiguously ``1..n`` with no gap or duplicate. A truncated/garbled pick pull trips this."""
    ok = (n_picks == expected_picks and min_pick == 1 and max_pick == n_picks
          and n_distinct == n_picks)
    return _gate(name, ok, n_picks=n_picks, expected=expected_picks, min_pick=min_pick,
                 max_pick=max_pick, n_distinct=n_distinct)


def sleeper_no_dup_picks_gate(name: str, n_drafts_with_dup: int, *, n_incomplete: int = 0,
                              n_total: int = 0) -> dict:
    """Gate: no draft has two picks sharing a ``pick_no`` — the true corruption check on the crawled
    corpus (which legitimately contains *incomplete* drafts, so completeness is NOT gated, only
    reported). A duplicate pick_no means a parse/ingest bug."""
    return _gate(name, n_drafts_with_dup == 0, drafts_with_dup=n_drafts_with_dup,
                 incomplete_drafts=n_incomplete, total_drafts=n_total)


def manager_reach_gate(name: str, mean_abs_reach_rounds, n_managers: int,
                       max_rounds: float = MANAGER_REACH_MAX_ROUNDS) -> dict:
    """Gate: the manager profiles' mean |reach| is inside a couple of rounds (T18).

    The gate the register asked for by name, and it exists because the failure it catches does not
    look like a bug from the inside — the pooled-board table reported a **+91.9-pick** mean QB reach
    and every individual step of the computation was correct. *A mean reach outside roughly ±2
    rounds is a join defect, not a manager.* Pure: pass the aggregate in from the DB wrapper.
    """
    ok = mean_abs_reach_rounds is not None and abs(float(mean_abs_reach_rounds)) <= max_rounds
    return _gate(name, ok, n_managers=int(n_managers), max_rounds=max_rounds,
                 mean_abs_reach_rounds=(None if mean_abs_reach_rounds is None
                                        else round(float(mean_abs_reach_rounds), 3)))


def sleeper_human_slot_gate(name: str, n_mocks: int, n_with_human_slot: int) -> dict:
    """Gate: every *mock* draft resolved a ``human_slot`` from ``draft_order`` (a mock has one
    entry — the user). Not applicable (passes) when there are no mocks."""
    if n_mocks == 0:
        return _gate(name, True, applicable=False)
    return _gate(name, n_mocks == n_with_human_slot, n_mocks=n_mocks,
                 with_human_slot=n_with_human_slot)


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

    # T12: `snapshot_date` belongs in this key. The gate predates Stage 0, when each season had
    # exactly one FFC board; since 2026-07-09 we deliberately bank a weekly 2026 snapshot *series*,
    # so one row per player per board per season is no longer the invariant — one row per player
    # per board per **snapshot** is. Without the date the report was red on every run (1,028 benign
    # 2026 groups, 0 genuine dups), and a validator that is always red cannot warn anyone.
    adp = _count(
        con,
        "SELECT COUNT(*) FROM (SELECT gsis_id, season, source, scoring, teams, snapshot_date, "
        "COUNT(*) c FROM adp_snapshots WHERE gsis_id IS NOT NULL "
        "GROUP BY 1,2,3,4,5,6 HAVING c > 1)",
    )
    gates.append(_gate("adp: unique (gsis,season,source,scoring,teams,snapshot_date)", adp == 0,
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


def _scrape_gates(con, today=None) -> list[dict]:
    """T7 — freshness + schema guards on the external scrapes (FFC ADP, FantasyPros consensus), so a
    lapsed chore or a site-markup change trips a red gate instead of ingesting garbage silently.

    Each guard only fires when the relevant *live* board is present, so historical-only dev stores
    stay green. ``today`` is injectable for testing; defaults to the wall clock at report time."""
    today = today or dt.date.today()
    newest_completed = max(FANTASY_SEASONS)
    gates: list[dict] = []

    # ADP freshness — the Stage-0 §2 chore as an assertion (live season = the max banked season).
    live_season, latest = None, None
    if db.table_exists(con, "adp_snapshots"):
        row = con.execute("SELECT MAX(season) FROM adp_snapshots").fetchone()
        live_season = int(row[0]) if row and row[0] is not None else None
        if live_season is not None:
            d = con.execute("SELECT MAX(snapshot_date) FROM adp_snapshots WHERE season = ?",
                            [live_season]).fetchone()[0]
            latest = pd.to_datetime(d).date() if d is not None else None
    gates.append(adp_freshness_gate(latest, today, live_season=live_season,
                                    newest_completed_season=newest_completed))

    # FantasyPros consensus board — sane size + gsis-match (only once a live board's been scraped).
    if db.table_exists(con, "consensus_projections"):
        s = con.execute("SELECT MAX(season) FROM consensus_projections").fetchone()[0]
        if s is not None:
            n = _count(con,
                       f"SELECT COUNT(*) FROM consensus_projections WHERE season = {int(s)}")
            gates.append(board_size_gate("consensus: FantasyPros board size sane", n))
            gates.append(match_rate_gate("consensus: gsis-match rate",
                                         _pct_nonnull(con, "consensus_projections", "gsis_id")))
    return gates


def _sleeper_gates(con) -> list[dict]:
    """Step 0.10 — guards on the ingested Sleeper draft corpus. Only fire when the tables exist, so
    stores without any Sleeper drafts stay green."""
    if not db.table_exists(con, "sleeper_draft_picks"):
        return []
    gates: list[dict] = []

    # true integrity: no draft repeats a pick_no. Completeness is NOT gated — a crawled corpus
    # legitimately contains abandoned drafts (people quit mid-draft) — but it is reported.
    n_dup = _count(
        con,
        "SELECT COUNT(DISTINCT draft_id) FROM (SELECT draft_id FROM sleeper_draft_picks "
        "GROUP BY draft_id, pick_no HAVING COUNT(*) > 1)",
    )
    n_total = _count(con, "SELECT COUNT(*) FROM sleeper_drafts")
    n_incomplete = _count(
        con,
        "SELECT COUNT(*) FROM (SELECT d.draft_id FROM sleeper_drafts d "
        "JOIN sleeper_draft_picks p USING (draft_id) "
        "WHERE d.draft_type IN ('snake', 'linear') AND d.status = 'complete' "
        "GROUP BY d.draft_id, d.teams, d.rounds HAVING COUNT(*) <> d.teams * d.rounds)",
    )
    gates.append(sleeper_no_dup_picks_gate("sleeper: no draft repeats a pick_no", n_dup,
                                           n_incomplete=n_incomplete, n_total=n_total))

    tot, matched = con.execute(
        "SELECT COUNT(*), COUNT(gsis_id) FROM sleeper_draft_picks "
        "WHERE UPPER(position) IN ('QB', 'RB', 'WR', 'TE')"
    ).fetchone()
    gates.append(match_rate_gate("sleeper: skill (QB/RB/WR/TE) gsis-match rate",
                                 (matched / tot) if tot else None))

    n_mocks, n_slot = con.execute(
        "SELECT COUNT(*), COUNT(human_slot) FROM sleeper_drafts WHERE source = 'mock'"
    ).fetchone()
    gates.append(sleeper_human_slot_gate("sleeper: human slot resolved per mock",
                                         int(n_mocks), int(n_slot)))

    # T18 — the profiles' reach column, in the units it is now stored in (rounds, own board)
    if db.table_exists(con, "sleeper_manager_profiles"):
        cols = [r[0] for r in con.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'sleeper_manager_profiles'").fetchall()]
        if "avg_reach_rounds" in cols:
            mean_abs, n_mgr = con.execute(
                "SELECT AVG(ABS(avg_reach_rounds)), COUNT(avg_reach_rounds) "
                "FROM sleeper_manager_profiles").fetchone()
            gates.append(manager_reach_gate("sleeper: manager reach is a behaviour, not a join",
                                            mean_abs, int(n_mgr or 0)))
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
    gates = (_range_gates(con) + _dup_gates(con) + _join_rate_gates(con)
             + _scrape_gates(con) + _sleeper_gates(con))
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
