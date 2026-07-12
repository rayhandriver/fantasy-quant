"""Phase 13.1 + 13.2 — the in-season co-pilot: pure unit tests (no DB).

The load-bearing behaviours: (13.1) the scalar Kalman re-projection shrinks the preseason level
toward realized results, is strictly PIT (future weeks never leak), the prior strength and process
variance move the level the documented direction, and the reserved news slot shifts the mean and
floors at zero; (13.2) the start/sit fill is legal and mean-maximising with no opponent, and the
win-probability leverage tilt adds variance as the underdog / cuts it when favored, always under a
do-no-harm guard.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fantasy_quant.draft.simulator import RosterSlots
from fantasy_quant.inseason.lineup import optimal_lineup
from fantasy_quant.inseason.reproject import (
    preseason_prior,
    reproject_week,
)
from fantasy_quant.simulation.weekly import WeeklyModel


# ------------------------------------------------------------------------------------------------
# 13.1 — weekly re-projection
# ------------------------------------------------------------------------------------------------
def _tiny_model(n_weeks: int = 17) -> WeeklyModel:
    """A 4-player model: an RB on a bye team, a WR on a bye-free team, a QB, and a K (excluded)."""
    summary = pd.DataFrame({
        "player_key": ["a", "b", "q", "k"], "pos": ["RB", "WR", "QB", "K"],
        "team": ["AAA", "BBB", "AAA", "CCC"], "role_rank": [1, 1, 1, 1],
        "mean": [200.0, 170.0, 300.0, 120.0], "sd": [50.0, 45.0, 60.0, 20.0],
        "wk_cov": [0.5, 0.9, 0.4, 0.3],
    })
    samples = np.full((4, 8), 200.0)
    games = np.full((4, 8), 17)
    return WeeklyModel(summary=summary, samples=samples, games=games,
                       byes={"AAA": 7}, kdst={"K": 7.5, "DST": 6.0},
                       repl_weekly={"QB": 12.0, "RB": 6.5, "WR": 7.0, "TE": 4.5}, n_weeks=n_weeks)


def test_preseason_prior_excludes_kdst_and_prices_the_bye():
    prior = preseason_prior(_tiny_model(), prior_weeks=5.0)
    assert set(prior["player_key"]) == {"a", "b", "q"}          # K/DST are not re-projected
    row = prior.set_index("player_key")
    assert int(row.loc["a", "active_weeks"]) == 16              # AAA has a bye -> 16 active weeks
    assert int(row.loc["b", "active_weeks"]) == 17              # BBB bye-free
    assert row.loc["a", "m0"] == pytest.approx(200.0 / 16)      # per-active-week level
    assert row.loc["b", "m0"] == pytest.approx(170.0 / 17)
    # r = (wk_cov * m0)^2 ; p0 = r / prior_weeks
    assert row.loc["a", "r"] == pytest.approx((0.5 * 200.0 / 16) ** 2)
    assert row.loc["a", "p0"] == pytest.approx(row.loc["a", "r"] / 5.0)


def test_preseason_prior_strength_scales_prior_variance():
    weak = preseason_prior(_tiny_model(), prior_weeks=1.0).set_index("player_key")
    strong = preseason_prior(_tiny_model(), prior_weeks=50.0).set_index("player_key")
    assert weak.loc["a", "m0"] == pytest.approx(strong.loc["a", "m0"])    # same level
    assert weak.loc["a", "p0"] > strong.loc["a", "p0"]                    # weaker prior = looser


def _realized(rows: list[tuple[str, int, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["player_key", "week", "points"])


def test_reproject_shrinks_toward_realized_but_not_all_the_way():
    prior = preseason_prior(_tiny_model())
    m0_a = float(prior.set_index("player_key").loc["a", "m0"])            # ~12.5
    hot = _realized([("a", w, 25.0) for w in range(1, 5)])               # 4 weeks well above m0
    ros = reproject_week(prior, hot, through_week=4)
    fc = ros.forecast.set_index("player_key")
    assert m0_a < fc.loc["a", "level"] < 25.0                            # partial credit to reality
    assert int(fc.loc["a", "n_played"]) == 4
    # a player with no evidence stays exactly at his preseason level
    assert fc.loc["b", "level"] == pytest.approx(prior.set_index("player_key").loc["b", "m0"])
    assert fc.loc["b", "mean_week"] == pytest.approx(fc.loc["b", "level"])


def test_reproject_is_point_in_time():
    """A week-4 re-projection must be identical whether or not future weeks are in the frame."""
    prior = preseason_prior(_tiny_model())
    past = _realized([("a", w, 25.0) for w in range(1, 5)])
    future = pd.concat([past, _realized([("a", 8, 40.0), ("a", 10, 2.0)])], ignore_index=True)
    lvl_past = reproject_week(prior, past, 4).week_mean()["a"]
    lvl_future = reproject_week(prior, future, 4).week_mean()["a"]        # weeks >4 must not leak
    assert lvl_past == pytest.approx(lvl_future)


def test_reproject_prior_strength_controls_update_speed():
    weak = preseason_prior(_tiny_model(), prior_weeks=1.0)               # trusts data
    strong = preseason_prior(_tiny_model(), prior_weeks=50.0)            # trusts preseason
    m0_a = float(weak.set_index("player_key").loc["a", "m0"])
    hot = _realized([("a", w, 25.0) for w in range(1, 5)])
    lvl_weak = reproject_week(weak, hot, 4).week_mean()["a"]
    lvl_strong = reproject_week(strong, hot, 4).week_mean()["a"]
    # both move up toward 25, but the weak prior moves further from the preseason level
    assert (lvl_weak - m0_a) > (lvl_strong - m0_a) > 0


def test_reproject_process_var_weights_recent_form():
    prior = preseason_prior(_tiny_model())
    seq = zip(range(1, 5), (8.0, 14.0, 20.0, 26.0), strict=False)
    rising = _realized([("a", w, v) for w, v in seq])
    flat_lvl = reproject_week(prior, rising, 4, process_var=0.0).week_mean()["a"]
    walk_lvl = reproject_week(prior, rising, 4, process_var=8.0).week_mean()["a"]
    assert walk_lvl > flat_lvl                                           # recent form weighted up


def test_reproject_news_slot_shifts_mean_and_floors_at_zero():
    prior = preseason_prior(_tiny_model())
    base = reproject_week(prior, _realized([]), 4)                       # no games at all
    lvl_b = base.forecast.set_index("player_key").loc["b", "mean_week"]
    up = reproject_week(prior, _realized([]), 4, news={"b": 5.0})
    assert up.week_mean()["b"] == pytest.approx(lvl_b + 5.0)             # additive level shift
    # level (pre-news) is untouched, only the predictive mean moves
    assert up.forecast.set_index("player_key").loc["b", "level"] == pytest.approx(lvl_b)
    # a catastrophic note cannot push the mean negative
    down = reproject_week(prior, _realized([]), 4, news={"b": -1000.0})
    assert down.week_mean()["b"] == pytest.approx(0.0)
    # default is a no-op
    assert base.week_mean()["b"] == pytest.approx(lvl_b)


# ------------------------------------------------------------------------------------------------
# 13.2 — start/sit under the win-probability objective
# ------------------------------------------------------------------------------------------------
def _one_flex(positions=("RB",)) -> RosterSlots:
    """A single FLEX slot over ``positions`` and nothing else — start exactly one player."""
    return RosterSlots(qb=0, rb=0, wr=0, te=0, flex=1, k=0, dst=0, bench=0,
                       flex_positions=tuple(positions))


def test_mean_max_fills_a_legal_lineup_and_flex_takes_the_best_leftover():
    slots = RosterSlots(qb=1, rb=1, wr=1, te=0, flex=1, k=0, dst=0, bench=0,
                        flex_positions=("RB", "WR"))
    # QB, two RBs (12, 9), two WRs (11, 7); mean-max => QB, RB=12, WR=11, FLEX=best leftover=RB(9)
    mu = np.array([20.0, 12.0, 9.0, 11.0, 7.0])
    weekly = np.tile(mu[:, None], (1, 200))
    pos = ["QB", "RB", "RB", "WR", "WR"]
    choice = optimal_lineup(weekly, pos, slots, objective="mean")
    assert choice.slots["QB"] == 0
    assert choice.slots["RB"] == 1 and choice.slots["WR"] == 3      # the higher of each pair
    assert choice.slots["FLEX"] == 2                                # leftover RB (9) beats WR (7)
    assert set(choice.indices()) == {0, 1, 2, 3}
    assert choice.exp_points == pytest.approx(20 + 12 + 11 + 9)
    assert np.isnan(choice.win_prob)                               # no opponent supplied


def test_no_opponent_is_mean_max():
    slots = _one_flex()
    weekly = np.stack([np.full(500, 15.0), np.full(500, 14.0)])
    both = optimal_lineup(weekly, ["RB", "RB"], slots, objective="win")   # opp=None -> mean-max
    assert both.indices() == [0]


def test_underdog_starts_the_boom_bust_player():
    rng = np.random.default_rng(0)
    n = 40000
    safe = rng.normal(15.0, 1.0, n).clip(0)      # higher mean, tiny variance
    boom = rng.normal(14.0, 12.0, n).clip(0)     # lower mean, big ceiling
    weekly = np.stack([safe, boom])
    opp = rng.normal(30.0, 5.0, n).clip(0)       # a heavy favorite across the table
    slots = _one_flex()
    mean_c = optimal_lineup(weekly, ["RB", "RB"], slots, opp, objective="mean")
    win_c = optimal_lineup(weekly, ["RB", "RB"], slots, opp, objective="win")
    assert mean_c.indices() == [0]               # mean-max starts the safe floor
    assert win_c.indices() == [1]                # trailing badly -> take the tail shot
    assert win_c.win_prob >= mean_c.win_prob     # and it does not lower the win chance


def test_favorite_cuts_variance():
    rng = np.random.default_rng(1)
    n = 40000
    safe = rng.normal(14.0, 1.0, n).clip(0)      # lower mean, tiny variance
    hero = rng.normal(15.0, 12.0, n).clip(0)     # higher mean, big variance
    weekly = np.stack([safe, hero])
    opp = rng.normal(6.0, 3.0, n).clip(0)        # a heavy underdog across the table
    slots = _one_flex()
    mean_c = optimal_lineup(weekly, ["RB", "RB"], slots, opp, objective="mean")
    win_c = optimal_lineup(weekly, ["RB", "RB"], slots, opp, objective="win")
    assert mean_c.indices() == [1]               # mean-max starts the higher-mean hero
    assert win_c.indices() == [0]                # protecting a lead -> start the safe floor
    assert win_c.win_prob >= mean_c.win_prob


def test_coin_flip_does_no_harm():
    rng = np.random.default_rng(2)
    n = 40000
    safe = rng.normal(15.0, 1.0, n).clip(0)
    boom = rng.normal(14.0, 12.0, n).clip(0)
    weekly = np.stack([safe, boom])
    opp = rng.normal(14.7, 8.0, n).clip(0)       # ~50/50 -> the tilt should be negligible
    slots = _one_flex()
    win_c = optimal_lineup(weekly, ["RB", "RB"], slots, opp, objective="win")
    mean_c = optimal_lineup(weekly, ["RB", "RB"], slots, opp, objective="mean")
    assert win_c.win_prob >= mean_c.win_prob     # guard holds regardless of which lineup it keeps
