"""Phase 10 — season/playoff simulation: pure unit tests (no DB).

The two load-bearing equivalences: (1) the Iman–Conover *permutation* reproduces the validated
``correlate_samples`` exactly, so games-played companions ride along with their draws; (2) the
vectorized lineup evaluator equals the Phase-1.3 reference per week. Everything else checks the
structural mechanics: week splits reconcile to season draws, schedules are legal, seeding and
brackets follow the house rules, and variance leverage points the right way for underdogs.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fantasy_quant.draft.simulator import RosterSlots
from fantasy_quant.simulation.leverage import leverage_advice, scale_team_spread
from fantasy_quant.simulation.playoffs import bracket_champion, playoff_seeds
from fantasy_quant.simulation.season import (
    LeagueFormat,
    lineup_points_matrix,
    round_robin_schedule,
    simulate_league,
)
from fantasy_quant.simulation.weekly import WeeklyModel, correlation_permutation, split_weeks
from fantasy_quant.valuation.roster_risk import correlate_samples


# ------------------------------------------------------------------------------------------------
# weekly grain
# ------------------------------------------------------------------------------------------------
def test_correlation_permutation_reproduces_correlate_samples():
    rng = np.random.default_rng(7)
    samples = rng.gamma(2.0, 50.0, (4, 300))
    corr = np.eye(4)
    corr[0, 1] = corr[1, 0] = 0.7
    corr[2, 3] = corr[3, 2] = -0.4
    ref = correlate_samples(samples, corr, np.random.default_rng(11))
    idx = correlation_permutation(samples, corr, np.random.default_rng(11))
    np.testing.assert_array_equal(np.take_along_axis(samples, idx, axis=1), ref)


def test_split_weeks_sums_to_season_draw_and_respects_byes():
    rng = np.random.default_rng(0)
    y = np.array([100.0, 250.0, 0.0, 40.0])
    g = np.array([10, 17, 0, 3])
    eligible = np.array([w for w in range(17) if w != 6])   # bye = week 7 (index 6)
    out = split_weeks(y, g, wk_cov=0.8, eligible=eligible, n_weeks=17, rng=rng)
    assert out.shape == (4, 17)
    np.testing.assert_allclose(out.sum(axis=1), y, rtol=1e-12)
    assert (out[:, 6] == 0).all()                            # nobody scores on the bye
    assert (out[3] > 0).sum() == 3                           # g=3 -> exactly 3 active weeks
    assert (out[2] == 0).all()                               # lost season -> zero row


def test_split_weeks_cov_controls_weekly_spread():
    rng1, rng2 = np.random.default_rng(1), np.random.default_rng(1)
    y = np.full(400, 170.0)
    g = np.full(400, 17)
    eligible = np.arange(17)
    flat = split_weeks(y, g, 0.2, eligible, 17, rng1)
    spiky = split_weeks(y, g, 2.0, eligible, 17, rng2)
    assert spiky.std(axis=1).mean() > 2 * flat.std(axis=1).mean()


def _tiny_model() -> WeeklyModel:
    summary = pd.DataFrame({
        "player_key": ["a", "b"], "pos": ["RB", "WR"], "team": ["AAA", "BBB"],
        "role_rank": [1, 1], "mean": [150.0, 120.0], "sd": [40.0, 35.0],
        "wk_cov": [0.5, 0.9],
    })
    rng = np.random.default_rng(3)
    samples = rng.gamma(3.0, 50.0, (2, 50))
    games = np.full((2, 50), 17)
    return WeeklyModel(summary=summary, samples=samples, games=games,
                       byes={"AAA": 7}, kdst={"K": 7.5, "DST": 6.0},
                       repl_weekly={"QB": 12.0, "RB": 6.5, "WR": 7.0, "TE": 4.5}, n_weeks=17)


def test_weekly_model_routes_players_correctly():
    m = _tiny_model()
    cols = np.arange(20)
    rng = np.random.default_rng(5)
    k = m.player_weekly("anyone", "K", cols, rng)
    assert k.shape == (20, 17) and (k == 7.5).all()          # K/DST -> constant
    ghost = m.player_weekly("not-on-board", "WR", cols, rng)
    assert (ghost == 7.0).all()                              # cloudless offense -> replacement
    a = m.player_weekly("a", "RB", cols, rng)
    np.testing.assert_allclose(a.sum(axis=1), m.samples[0, cols])   # weeks == season draw
    assert (a[:, 6] == 0).all()                              # AAA bye week 7


# ------------------------------------------------------------------------------------------------
# schedule + lineups + standings
# ------------------------------------------------------------------------------------------------
def test_round_robin_schedule_is_legal_and_complete():
    rng = np.random.default_rng(2)
    sched = round_robin_schedule(10, 14, rng)
    assert sched.shape == (14, 10)
    for w in range(14):
        opp = sched[w]
        assert (opp[opp] == np.arange(10)).all()             # symmetric pairing
        assert (opp != np.arange(10)).all()                  # no self-play
    for i in range(10):
        assert set(sched[:9, i]) == set(range(10)) - {i}     # first 9 weeks: everyone once


def test_lineup_points_matrix_matches_reference():
    from fantasy_quant.backtest.walkforward import optimal_lineup_points
    slots = RosterSlots()
    rng = np.random.default_rng(4)
    positions = ["QB", "QB", "RB", "RB", "RB", "WR", "WR", "WR", "TE", "TE",
                 "K", "DST", "RB", "WR", "QB"]
    pts = rng.gamma(2.0, 6.0, (len(positions), 3, 4))
    fast = lineup_points_matrix(pts, positions, slots)
    for s in range(3):
        for w in range(4):
            ref = optimal_lineup_points(pts[:, s, w], positions, slots)
            assert fast[s, w] == pytest.approx(ref)


def test_lineup_points_matrix_handles_missing_positions():
    from fantasy_quant.backtest.walkforward import optimal_lineup_points
    slots = RosterSlots()
    positions = ["RB", "RB", "WR"]                            # no QB/TE/K/DST at all
    pts = np.array([[10.0], [8.0], [5.0]])[:, :, None]
    fast = lineup_points_matrix(pts, positions, slots)
    assert fast[0, 0] == pytest.approx(optimal_lineup_points(pts[:, 0, 0], positions, slots))


def test_league_format_validation():
    with pytest.raises(ValueError):
        LeagueFormat(playoff_teams=8, playoff_weeks=(15, 16, 17))
    with pytest.raises(ValueError):
        LeagueFormat(playoff_teams=6, playoff_weeks=(15, 16))
    with pytest.raises(ValueError):
        LeagueFormat(reg_weeks=13, playoff_weeks=(15, 16, 17))
    fmt = LeagueFormat(reg_weeks=14, playoff_teams=4, playoff_weeks=(15, 16),
                       first_round_byes=0)
    assert fmt.n_weeks == 16


def test_playoff_seeds_tiebreak_on_points():
    wins = np.array([[3.0], [3.0], [1.0], [0.0]])
    pf = np.array([[100.0], [120.0], [90.0], [80.0]])
    seeds = playoff_seeds(wins, pf, 4)
    assert seeds[:, 0].tolist() == [1, 0, 2, 3]              # pf breaks the 3-win tie


def test_bracket_champion_six_team_deterministic():
    # seeds = teams 0..5; round scores rigged so 6-seed upsets, then loses the semi to the 1;
    # the 2 beats the 4-5 winner; final goes to the 2 on points.
    seeds = np.array([[0], [1], [2], [3], [4], [5]])
    scores = np.zeros((6, 1, 3))
    scores[[2, 5], 0, 0] = [80, 95]      # 3v6: the 6-seed (team 5) advances
    scores[[3, 4], 0, 0] = [90, 85]      # 4v5: team 3 advances
    scores[[0, 5], 0, 1] = [70, 60]      # reseeded semi: 1-seed hosts the worst survivor
    scores[[1, 3], 0, 1] = [88, 70]
    scores[[0, 1], 0, 2] = [90, 91]      # final: team 1 wins
    champ = bracket_champion(seeds, scores, first_round_byes=2)
    assert champ.tolist() == [1]


def test_bracket_tie_advances_better_seed():
    seeds = np.array([[0], [1], [2], [3]])
    scores = np.zeros((4, 1, 2))          # every game 0-0 -> better seed advances throughout
    champ = bracket_champion(seeds, scores, first_round_byes=0)
    assert champ.tolist() == [0]


def test_simulate_league_deterministic_standings():
    fmt = LeagueFormat(reg_weeks=14, playoff_teams=4, playoff_weeks=(15, 16),
                       first_round_byes=0)
    sched = round_robin_schedule(4, 14, np.random.default_rng(6))
    # team strength strictly ordered and constant -> the strongest team never loses
    weekly = np.tile(np.array([100.0, 90.0, 80.0, 70.0])[:, None, None], (1, 1, 16))
    sim = simulate_league(weekly, fmt, sched)
    assert sim.wins[0, 0] == 14.0 and sim.wins[3, 0] == 0.0
    assert sim.made_playoffs[:, 0].tolist() == [True, True, True, True]
    assert sim.champion.tolist() == [0]
    assert sim.title_prob.sum() == pytest.approx(1.0)


def test_simulate_league_resumes_from_state():
    fmt = LeagueFormat(reg_weeks=14, playoff_teams=4, playoff_weeks=(15, 16),
                       first_round_byes=0)
    sched = round_robin_schedule(4, 14, np.random.default_rng(8))
    weekly = np.tile(np.array([100.0, 90.0, 80.0, 70.0])[:, None, None], (1, 1, 16))
    # hand team 3 an insurmountable 12-0 start from week 12 on: it must make the playoffs
    wins0 = np.array([2.0, 4.0, 6.0, 12.0])
    pf0 = np.zeros(4)
    sim = simulate_league(weekly, fmt, sched, start_week=12, wins0=wins0, pf0=pf0)
    assert bool(sim.made_playoffs[3, 0])
    assert sim.wins[3, 0] >= 12.0


# ------------------------------------------------------------------------------------------------
# leverage
# ------------------------------------------------------------------------------------------------
def _stochastic_league(seed: int = 9, n_sims: int = 4000):
    fmt = LeagueFormat()
    rng = np.random.default_rng(seed)
    sched = round_robin_schedule(10, 14, rng)
    means = np.linspace(115.0, 85.0, 10)                     # team 0 favorite ... team 9 trailing
    weekly = rng.normal(means[:, None, None], 18.0, (10, n_sims, 17)).clip(min=0)
    return fmt, sched, weekly


def test_scale_team_spread_preserves_mean():
    _, _, weekly = _stochastic_league(n_sims=500)
    out = scale_team_spread(weekly, team=2, scale=1.4)
    np.testing.assert_allclose(out[2].mean(axis=0), weekly[2].mean(axis=0), rtol=1e-2)
    np.testing.assert_array_equal(out[5], weekly[5])         # other teams untouched
    assert out[2].std() > weekly[2].std()


def test_leverage_underdog_gains_from_variance_favorite_loses():
    fmt, sched, weekly = _stochastic_league()
    dog = leverage_advice(weekly, fmt, sched, team=9, scales=(0.6, 1.0, 1.6))
    fav = leverage_advice(weekly, fmt, sched, team=0, scales=(0.6, 1.0, 1.6))
    dog_curve = dog["curve"].set_index("scale")["title_prob"]
    fav_curve = fav["curve"].set_index("scale")["title_prob"]
    assert dog_curve[1.6] > dog_curve[0.6]                   # trailing team: add variance
    assert fav_curve[1.6] < fav_curve[0.6]                   # favorite: protect the lead
    assert dog["verdict"] in ("add variance", "hold")
