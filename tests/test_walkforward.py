"""Unit tests for Phase 1.3 — the walk-forward harness pure pieces (no DB/network)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fantasy_quant.backtest.walkforward import (
    Realized,
    optimal_lineup_points,
    rank_by_adp,
    roster_season_points,
)
from fantasy_quant.data.panel import assert_panel_pit
from fantasy_quant.draft.simulator import RosterSlots

SLOTS = RosterSlots()  # QB/2RB/2WR/TE/FLEX/K/DST


def test_optimal_lineup_picks_top_per_slot_plus_flex():
    pos = ["QB", "RB", "RB", "RB", "WR", "WR", "WR", "TE", "K", "DST"]
    pts = [20,   15,   10,   5,    12,   8,    7,    6,    9,   7]
    # QB20 + RB(15+10) + WR(12+8) + TE6 + K9 + DST7 + FLEX(best leftover RB/WR/TE = WR 7) = 94
    assert optimal_lineup_points(pts, pos, SLOTS) == 94.0


def test_optimal_lineup_missing_slots_score_zero():
    pos = ["QB", "RB", "RB", "WR", "WR", "TE"]  # no K, no DST, no flex-eligible leftover
    pts = [10,   8,    6,    7,    5,    4]
    # QB10 + RB(8+6) + WR(7+5) + TE4 + K0 + DST0 + FLEX0 = 40
    assert optimal_lineup_points(pts, pos, SLOTS) == 40.0


def test_flex_takes_best_leftover_regardless_of_position():
    # one extra RB (9) beats the leftover WR (3) for the FLEX.
    pos = ["QB", "RB", "RB", "RB", "WR", "WR", "WR", "TE", "K", "DST"]
    pts = [1,    10,   10,   9,    10,   10,   3,    1,    1,   1]
    # QB1 + RB(10+10) + WR(10+10) + TE1 + K1 + DST1 + FLEX(max leftover {RB9, WR3}=9) = 53
    assert optimal_lineup_points(pts, pos, SLOTS) == 53.0


def _toy_realized() -> Realized:
    off = pd.DataFrame([[10.0, 5.0], [20.0, 0.0]],
                       index=pd.Index(["A", "B"], name="gsis_id"), columns=[1, 2])
    kick = pd.DataFrame(index=pd.Index([], name="gsis_id"), columns=[1, 2], dtype=float)
    dst = pd.DataFrame([[7.0, 3.0]], index=pd.Index(["BUF"], name="team"), columns=[1, 2])
    return Realized(off, kick, dst, [1, 2])


def test_survivorship_missing_player_contributes_zero():
    realized = _toy_realized()
    one = pd.DataFrame({"player_key": ["A"], "pos": ["RB"]})
    with_bust = pd.DataFrame({"player_key": ["A", "C"], "pos": ["RB", "RB"]})  # C never played
    # the missing bust adds nothing (LEFT-JOIN-to-zero), it is NOT dropped-and-flattering.
    assert (roster_season_points(one, realized, SLOTS)
            == roster_season_points(with_bust, realized, SLOTS))


def test_roster_season_points_sums_weeks_and_maps_dst_by_name():
    realized = _toy_realized()
    roster = pd.DataFrame({"player_key": ["A", "Buffalo Defense"], "pos": ["RB", "DST"]})
    # A: RB slot both weeks (10+5); DST 'Buffalo Defense' -> BUF (7+3). Total 25.
    assert roster_season_points(roster, realized, SLOTS) == 25.0


def test_rank_by_adp_is_the_adp_column():
    board = pd.DataFrame({"adp": [3.0, 1.0, 2.0]})
    assert list(rank_by_adp(board)) == [3.0, 1.0, 2.0]


def test_pit_guard_trips_on_future_dated_board():
    # the harness's preseason_board runs exactly this assert; a planted future snapshot trips it.
    board = pd.DataFrame({"snapshot_date": pd.to_datetime(["2022-09-04", "2023-01-01"])})
    with pytest.raises(AssertionError, match="PIT leak"):
        assert_panel_pit(board, "2022-09-05", ["snapshot_date"])


def test_optimal_lineup_accepts_numpy_row():
    # roster_season_points feeds a numpy column per week; make sure that path works.
    pos = ["QB", "RB", "RB", "WR", "WR", "TE", "K", "DST"]
    row = np.array([10, 8, 6, 7, 5, 4, 3, 2], dtype=float)
    assert optimal_lineup_points(row, pos, SLOTS) == 10 + 8 + 6 + 7 + 5 + 4 + 3 + 2 - 0.0
