"""Phase 15 — multi-format + auction: pure unit tests (no project DB).

Load-bearing behaviours: (15.4 auction) auction values floor at $1 and sum to the total budget, the
$1
endgame cap always leaves min-bids for the other slots, and a bid respects both cap and budget;
(15.2
best-ball) the season total sums each week's optimal lineup and the ceiling value is a positive
weekly-volatility tilt; (15.3 DFS) synthetic salaries are monotone in projection, leverage fades
owned
players, the cap optimizer returns a legal lineup, and prize-splitting punishes a duplicated
lineup. The
DB-backed done-bars (auction_skill / bestball_skill / gpp_skill) are exercised by the step runners.
"""

from __future__ import annotations

import numpy as np
import pytest

from fantasy_quant.draft.auction import (
    DEFAULT_BUDGET,
    auction_bid,
    auction_values,
    endgame_cap,
    nominate,
)
from fantasy_quant.draft.simulator import RosterSlots
from fantasy_quant.formats.bestball import bestball_season_points, ceiling_value
from fantasy_quant.formats.dfs import (
    DFS_SLOTS,
    _entry_payout,
    _payout_curve,
    leverage_score,
    modeled_ownership,
    optimize_lineup,
    synthetic_salaries,
)


# ------------------------------------------------------------------------------------------------
# 15.4 — auction kernels
# ------------------------------------------------------------------------------------------------
def test_auction_values_floor_and_budget():
    vor = np.array([100.0, 60.0, 30.0, 10.0, 2.0, -5.0])
    av = auction_values(vor, n_teams=2, budget=100.0, roster_size=3)
    # 2 teams × 3 slots = 6 rosterable; total spend ≈ full budget; each rosterable ≥ $1; ordering
    # holds.
    assert av.sum() == pytest.approx(200.0, abs=1.0)
    assert (av[:5] >= 1.0).all()
    assert av[0] > av[1] > av[2]                      # value-monotone


def test_endgame_cap():
    assert endgame_cap(200.0, 15) == pytest.approx(186.0)   # keep $1 for 14 other slots
    assert endgame_cap(10.0, 1) == pytest.approx(10.0)       # last slot: spend it all
    assert endgame_cap(5.0, 0) == 0.0


def test_auction_bid_caps():
    assert auction_bid(50.0, 200.0, 15) == pytest.approx(0.95 * 50.0)   # shaded value; cap idle
    assert auction_bid(50.0, 5.0, 4) == pytest.approx(2.0)              # endgame-capped ($5 − $3)
    assert auction_bid(0.5, 200.0, 15) == 0.0                          # below min bid ⇒ don't bid
    assert auction_bid(50.0, 200.0, 0) == 0.0                          # roster full


def test_nominate():
    val = {"a": 50.0, "b": 40.0, "c": 10.0}
    pos = {"a": "RB", "b": "WR", "c": "TE"}
    # I still need WR/TE but not RB → nominate the priciest player I don't need (a, an RB).
    assert nominate(val, {"WR", "TE"}, pos) == "a"
    # I need everything → nominate the cheapest (preserve cash).
    assert nominate(val, {"RB", "WR", "TE"}, pos) == "c"


# ------------------------------------------------------------------------------------------------
# 15.2 — best-ball kernels
# ------------------------------------------------------------------------------------------------
def test_ceiling_value_is_upside_tilt():
    # at equal mean, the streakier (higher wk_cov) player is valued higher.
    steady = ceiling_value(12.0, 0.4)
    streaky = ceiling_value(12.0, 1.2)
    assert streaky > steady > 12.0


def test_bestball_sums_weekly_optimal():
    # 2 players, 1 sim, 2 weeks; a 1-QB/0-flex slot picks the best QB each week.
    slots = RosterSlots(qb=1, rb=0, wr=0, te=0, flex=0, k=0, dst=0, bench=1)
    weekly = np.array([[[20.0, 2.0]], [[3.0, 25.0]]])   # (2 players, 1 sim, 2 weeks)
    pos = ["QB", "QB"]
    tot = bestball_season_points(weekly, pos, slots)
    # best-ball keeps the weekly max: 20 (wk1) + 25 (wk2) = 45, not either player's own total.
    assert tot[0] == pytest.approx(45.0)


# ------------------------------------------------------------------------------------------------
# 15.3 — DFS kernels
# ------------------------------------------------------------------------------------------------
def test_synthetic_salaries_monotone():
    sal = synthetic_salaries(np.array([5.0, 10.0, 20.0, 30.0]))
    assert (np.diff(sal) > 0).all()                  # higher projection ⇒ higher salary
    assert (sal >= 3000.0).all()


def test_leverage_fades_owned():
    proj = np.array([20.0, 20.0])
    own = np.array([0.5, 0.05])                      # same projection, very different ownership
    lev = leverage_score(proj, own, lam=0.8)
    assert lev[1] > lev[0]                            # the low-owned play scores higher


def test_optimize_lineup_is_legal():
    rng = np.random.default_rng(0)
    n = 40
    proj = rng.uniform(3, 25, n)
    pos = np.array(["QB"] * 6 + ["RB"] * 12 + ["WR"] * 16 + ["TE"] * 6)
    sal = synthetic_salaries(proj)
    lu = optimize_lineup(proj, sal, pos, DFS_SLOTS)
    assert len(lu) == DFS_SLOTS.total                # a full 8-man lineup
    assert sal[lu].sum() <= 50000.0                  # under the cap
    assert (pos[lu] == "QB").sum() == 1              # exactly one QB


def test_entry_payout_splits_duplicates():
    # one world; our entry and 3 field copies all top the field → first place split 4 ways.
    pay = _payout_curve(10)                           # pay[1] = 100
    entry = [0, 1]
    field = [[0, 1], [0, 1], [0, 1], [2, 3]]          # 3 exact duplicates of the entry, 1 other
    entry_scores = np.array([50.0])
    field_scores = np.array([[50.0], [50.0], [50.0], [10.0]])
    out = _entry_payout(entry_scores, entry, field_scores, field, pay)
    # rank 1 (nobody strictly higher), duplicity 4 (entry + 3 copies) → 100 / 4 = 25.
    assert out[0] == pytest.approx(25.0)


def test_modeled_ownership_bounded():
    proj = np.array([25.0, 15.0, 8.0, 20.0])
    pos = ["QB", "RB", "WR", "RB"]
    own = modeled_ownership(proj, synthetic_salaries(proj), pos)
    assert (own >= 0).all() and (own <= 0.6).all()
    assert DEFAULT_BUDGET == 200.0                    # sanity: module constant intact
