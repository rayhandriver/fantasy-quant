"""Unit tests for Phase 1.4 — the PAR metric (no DB/network)."""

from __future__ import annotations

import pandas as pd

from fantasy_quant.backtest.metrics import (
    ReplacementLevels,
    expected_wins,
    final_standings,
    par,
    replacement_ranks,
)
from fantasy_quant.backtest.walkforward import Realized, roster_season_points
from fantasy_quant.draft.simulator import RosterSlots

SLOTS = RosterSlots()


def test_replacement_ranks_10team_flex_split():
    # QB/K/DST = teams; RB/WR = 2*teams + flex share (2/5); TE = teams + flex share (1/5).
    assert replacement_ranks(SLOTS, n_teams=10) == {
        "QB": 10, "RB": 24, "WR": 24, "TE": 12, "K": 10, "DST": 10}


def test_replacement_ranks_scale_with_teams():
    r = replacement_ranks(SLOTS, n_teams=12)
    assert r["QB"] == 12 and r["RB"] == 29 and r["TE"] == 14  # 12*2+4.8->29 ; 12+2.4->14


def _toy_realized() -> Realized:
    off = pd.DataFrame([[30.0, 30.0], [3.0, 3.0]],
                       index=pd.Index(["STAR", "SCRUB"], name="gsis_id"), columns=[1, 2])
    empty = pd.DataFrame(index=pd.Index([], name="gsis_id"), columns=[1, 2], dtype=float)
    dst = pd.DataFrame(index=pd.Index([], name="team"), columns=[1, 2], dtype=float)
    return Realized(off, empty, dst, [1, 2])


def test_par_subtracts_replacement_and_ranks_good_above_bad():
    realized = _toy_realized()
    repl = ReplacementLevels(by_pos={}, roster_total=50.0, n_teams=10)
    good = pd.DataFrame({"player_key": ["STAR"], "pos": ["RB"]})
    bad = pd.DataFrame({"player_key": ["SCRUB"], "pos": ["RB"]})
    par_good = par(good, realized, repl, SLOTS)
    par_bad = par(bad, realized, repl, SLOTS)
    # exact: STAR scores 30/wk -> 60 season; PAR = 60 - 50 = 10.
    assert par_good == roster_season_points(good, realized, SLOTS) - 50.0 == 10.0
    assert par_good > par_bad
    assert par_bad < 0  # a scrub roster is below replacement


def test_expected_wins_all_play():
    m = [[10, 10], [5, 5], [1, 1]]  # team0 always top, team2 always bottom
    ew = expected_wins(m)
    assert list(ew) == [2.0, 1.0, 0.0]  # per week: 1 / 0.5 / 0, x2 weeks


def test_expected_wins_ties_count_half():
    ew = expected_wins([[5], [5], [5]])  # all tied one week
    assert list(ew) == [0.5, 0.5, 0.5]


def test_final_standings_orders_by_wins():
    m = [[10, 10], [5, 5], [1, 1]]
    assert list(final_standings(m)) == [1, 2, 3]


def test_final_standings_single_team():
    assert list(final_standings([[10, 20]])) == [1]
