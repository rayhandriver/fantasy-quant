"""Unit tests for Phase 5 pure pieces — quantile fit/predict, conformal (CQR) coverage, boom/bust
rates, injury dispersion + games sampler, the distribution samplers, and the mean-variance utility
(no DB). Two of these are explicit regression guards for bugs found wiring the phase together:
``test_predict_quantiles_*`` (crossing/floor) and, most importantly,
``test_sample_player_season_is_on_the_H_scale`` (the games-count / availability-fraction units bug
that inflated season means ~17x)."""

from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd
import pytest

from fantasy_quant.data import db
from fantasy_quant.projections import conformal, distribution, injury, quantile, variance
from fantasy_quant.valuation import utility


# --------------------------------------------------------------------------------------------
# 5.1 quantile regression — fit recovers the level, predict is monotone/floored
# --------------------------------------------------------------------------------------------
def test_fit_quantile_models_recovers_unit_slope():
    rng = np.random.default_rng(0)
    x = rng.uniform(20, 200, size=400)
    y = x + rng.normal(0, 10, size=400)                      # points ≈ calibrated_mean
    train = pd.DataFrame({"pos": "RB", "calibrated_mean": x, "points": y})
    models = quantile.fit_quantile_models(train)
    b0, b1 = models["RB"][0.5]
    assert 0.85 < b1 < 1.15                                   # median line recovers the mean


def test_fit_quantile_models_skips_thin_positions():
    train = pd.DataFrame({"pos": "TE", "calibrated_mean": np.arange(10.0),
                          "points": np.arange(10.0)})
    assert quantile.fit_quantile_models(train) == {}          # < 30 rows -> skipped


def test_predict_quantiles_is_monotone_and_floored():
    # deliberately crossing lines (tau .1 steeper than .9) + a negative intercept
    models = {"WR": {0.1: (-20.0, 1.2), 0.5: (0.0, 1.0), 0.9: (5.0, 0.9)}}
    q = quantile.predict_quantiles(models, "WR", np.array([5.0, 100.0]), taus=(0.1, 0.5, 0.9))
    assert q.shape == (2, 3)
    assert np.all(np.diff(q, axis=1) >= 0)                    # non-crossing after the sort repair
    assert np.all(q >= 0.0)                                   # floored at 0 (the 5-pt row)


def test_predict_quantiles_unknown_position_is_nan():
    q = quantile.predict_quantiles({}, "QB", np.array([100.0]), taus=(0.1, 0.5, 0.9))
    assert q.shape == (1, 3) and np.isnan(q).all()


# --------------------------------------------------------------------------------------------
# 5.2 conformal (CQR) — widen when too tight, shrink when too loose; coverage counts
# --------------------------------------------------------------------------------------------
def test_cqr_widens_a_too_tight_band():
    lo, hi, y = np.full(50, 40.0), np.full(50, 60.0), np.full(50, 80.0)   # all 20 above the band
    d = conformal.cqr_adjustment(lo, hi, y, alpha=0.2)
    assert 18.0 <= d <= 22.0                                  # ~+20 to reach the outcomes


def test_cqr_shrinks_a_too_loose_band():
    lo, hi, y = np.full(50, 40.0), np.full(50, 60.0), np.full(50, 50.0)   # comfortably inside
    assert conformal.cqr_adjustment(lo, hi, y, alpha=0.2) < 0.0           # negative -> tighten


def test_cqr_adjustment_empty_is_zero():
    assert conformal.cqr_adjustment(np.array([]), np.array([]), np.array([])) == 0.0


def test_empirical_coverage_counts_inside_inclusive():
    assert conformal.empirical_coverage([0, 0], [10, 10], [5, 15]) == 0.5   # 1 of 2 inside
    assert conformal.empirical_coverage([0], [10], [10]) == 1.0             # boundary is inside
    assert np.isnan(conformal.empirical_coverage([], [], []))


# --------------------------------------------------------------------------------------------
# 5.3 boom/bust weekly volatility
# --------------------------------------------------------------------------------------------
def test_boom_bust_rates_thresholds_and_moments():
    wk = pd.DataFrame({"player_key": ["a"] * 4, "pos": ["RB"] * 4,
                       "points": [25.0, 25.0, 25.0, 0.0]})
    out = variance.boom_bust_rates(wk).iloc[0]
    assert out["weeks"] == 4 and out["pos"] == "RB"
    assert out["boom_prob"] == 0.75                           # 3/4 weeks >= RB boom line (20)
    assert out["bust_prob"] == 0.25                           # 1/4 weeks <= RB bust line (6)
    assert out["wk_cov"] > 0                                  # sd/mean defined (mean>0)


# --------------------------------------------------------------------------------------------
# 5.4 injury — Beta-Binomial dispersion + games sampler
# --------------------------------------------------------------------------------------------
def test_estimate_dispersion_zero_when_binomial_consistent():
    g, G, p = np.full(200, 8.0), np.full(200, 10.0), np.full(200, 0.8)   # games == p*G exactly
    assert injury.estimate_dispersion(g, G, p) == 0.0        # no over-dispersion -> clipped to 0


def test_estimate_dispersion_saturates_on_lumpy_outcomes():
    # all-or-nothing seasons at p=0.5 are maximally over-dispersed -> clip ceiling 0.5
    g, G, p = np.tile([0.0, 10.0], 100), np.full(200, 10.0), np.full(200, 0.5)
    assert injury.estimate_dispersion(g, G, p) == 0.5


def test_sample_games_binomial_mean_and_support():
    rng = np.random.default_rng(1)
    s = injury.sample_games(0.5, 16, rho=0.0, rng=rng, n=20000)
    assert abs(s.mean() - 8.0) < 0.3                          # Binomial(16, .5) mean = 8
    assert s.min() >= 0 and s.max() <= 16


# --------------------------------------------------------------------------------------------
# assembler samplers — inverse-CDF draw + the H-scale regression guard
# --------------------------------------------------------------------------------------------
def test_sample_from_quantiles_inverts_the_grid():
    taus, qvals = (0.1, 0.5, 0.9), (50.0, 100.0, 150.0)
    assert distribution.sample_from_quantiles(taus, qvals, [0.5])[0] == 100.0
    assert distribution.sample_from_quantiles(taus, qvals, [0.1])[0] == 50.0
    s = distribution.sample_from_quantiles(taus, qvals, np.linspace(0.01, 0.99, 50))
    assert np.all(np.diff(s) >= 0) and np.all(s >= 0.0)       # monotone in u, floored at 0


def test_sample_player_season_is_on_the_H_scale():
    """Regression: Y = H * (availability_fraction / G_ref) must stay on H's scale. The original code
    divided a games *count* (~16) by a *fraction* G_ref (~0.9), inflating every mean ~17x."""
    rng = np.random.default_rng(2)
    taus, qvals = (0.1, 0.5, 0.9), (100.0, 100.0, 100.0)    # H is a constant 100
    y = distribution.sample_player_season(taus, qvals, avail_p=0.9, team_games=17,
                                          rho=0.0, g_ref=0.9, rng=rng, n=20000)
    assert 90.0 < y.mean() < 110.0                           # ≈ H, NOT ~1700


def test_sample_player_season_full_health_slightly_exceeds_H():
    rng = np.random.default_rng(3)
    taus, qvals = (0.1, 0.5, 0.9), (100.0, 100.0, 100.0)
    y = distribution.sample_player_season(taus, qvals, avail_p=0.999, team_games=17,
                                          rho=0.0, g_ref=0.9, rng=rng, n=20000)
    assert 105.0 < y.mean() < 118.0                          # ≈ H / G_ref = 100 / 0.9 ≈ 111


# --------------------------------------------------------------------------------------------
# T3 — cohort availability prior (A) + role-loss washout mixture (B)
# --------------------------------------------------------------------------------------------
def test_capital_tier_boundary_and_vectorized():
    assert injury.capital_tier(50) == "hi"                    # premium pick
    assert injury.capital_tier(200) == "lo"                   # late/undrafted
    assert injury.capital_tier(None) == "lo"                  # missing -> lo
    out = injury.capital_tier(pd.Series([10.0, 150.0]))
    assert list(out) == ["hi", "lo"]


def test_role_tier_bands():
    assert injury.role_tier(5, 24) == "elite"                # top half of startable
    assert injury.role_tier(18, 24) == "starter"             # rest of startable
    assert injury.role_tier(40, 24) == "deep"                # beyond startable


def test_lookup_cohort_backoff():
    prior = {("*", "*"): {"avail_p": 0.5, "rho": 0.3},
             ("RB", "*"): {"avail_p": 0.48, "rho": 0.35},
             ("RB", "hi"): {"avail_p": 0.67, "rho": 0.39}}
    assert injury.lookup_cohort(prior, "RB", "hi") == (0.67, 0.39)     # exact cell
    assert injury.lookup_cohort(prior, "RB", "lo") == (0.48, 0.35)     # -> (pos, *)
    assert injury.lookup_cohort(prior, "QB", "hi") == (0.5, 0.3)       # -> (*, *)


def test_lookup_role_backoff_returns_triple():
    ret = {("*", "*"): {"p_crater": 0.1, "crater_avail": 0.2, "keep_frac": 0.7},
           ("WR", "deep"): {"p_crater": 0.3, "crater_avail": 0.1, "keep_frac": 0.6}}
    assert injury.lookup_role(ret, "WR", "deep") == (0.3, 0.1, 0.6)
    assert injury.lookup_role(ret, "WR", "elite") == (0.1, 0.2, 0.7)   # backoff to (*, *)


def test_washout_mixture_fattens_left_tail_preserves_upper():
    """T3-B: the washout branch must lower q10 (and the mean) while leaving q90 ~unchanged — a
    left-tail-only widening, so conditional (healthy) coverage isn't dragged down by q90."""
    taus, qvals = (0.1, 0.5, 0.9), (120.0, 120.0, 120.0)     # H constant 120
    kw = dict(avail_p=0.95, team_games=17, rho=0.05, g_ref=0.9, n=40000)
    base = distribution.sample_player_season(taus, qvals, rng=np.random.default_rng(4),
                                             p_crater=0.0, **kw)
    wash = distribution.sample_player_season(taus, qvals, rng=np.random.default_rng(4),
                                             p_crater=0.3, crater_avail=0.12, keep_frac=0.7, **kw)
    b10, b90 = np.percentile(base, [10, 90])
    w10, w90 = np.percentile(wash, [10, 90])
    assert w10 < b10 - 20                                     # left tail markedly fatter
    assert wash.mean() < base.mean()                         # mean pulled down by the bad branch
    assert abs(w90 - b90) < 0.10 * b90                        # upper tail ~preserved


# --------------------------------------------------------------------------------------------
# 5.5 mean-variance utility / risk dial
# --------------------------------------------------------------------------------------------
def test_certainty_equivalent_penalizes_variance_and_floors():
    assert utility.certainty_equivalent(100.0, 1600.0, lam=0.01)[()] == 84.0   # 100 - .01*1600
    assert utility.certainty_equivalent(10.0, 2000.0, lam=0.01)[()] == 0.0     # floored at 0


def test_cvar_is_the_lower_tail_mean():
    samples = np.vstack([np.arange(100.0), np.arange(100.0, 200.0)])
    c = utility.cvar(samples, alpha=0.1)
    assert c[0] == np.arange(10).mean() and c[1] == np.arange(100, 110).mean()


def test_risk_adjusted_board_ranks_safe_over_volatile_at_equal_mean():
    dist = pd.DataFrame({"player_key": ["safe", "volatile"], "pos": ["RB", "RB"],
                         "mean": [150.0, 150.0], "sd": [20.0, 60.0]})
    out = utility.risk_adjusted_board(dist, lam=0.01)
    top = out.iloc[0]
    assert top["player_key"] == "safe" and top["ce_rank"] == 1           # lower variance wins
    assert (out.set_index("player_key").loc["volatile", "risk_premium"]
            > out.set_index("player_key").loc["safe", "risk_premium"])     # pays more for its risk


# --------------------------------------------------------------------------------------------
# T17 — the live season's rolled-forward availability frame (and the level guard)
# --------------------------------------------------------------------------------------------
def _t17_con(seasons=(2022, 2023, 2024), n_players: int = 12):
    """A minimal DB for the availability path: `weekly` + `player_ids` + an empty `combine`.

    Player ``i`` misses every 5th week on an offset, so the grid carries both classes (a logistic
    hazard needs them) and games-played varies; players 10 and 11 play only 3 games so they sit
    below the ``min_prior_games`` gate.
    """
    import duckdb
    pos_cycle = ["QB", "RB", "WR", "TE"]
    rows = []
    for s in seasons:
        for i in range(n_players):
            weeks = range(1, 4) if i >= 10 else [w for w in range(1, 18) if (w + i) % 5]
            for w in weeks:
                rows.append({"season": s, "gsis_id": f"00-{i:07d}", "week": w,
                             "recent_team": f"T{i % 4}", "position": pos_cycle[i % 4],
                             "season_type": "REG"})
    ids = [{"gsis_id": f"00-{i:07d}", "name": f"P{i}", "position": pos_cycle[i % 4],
            "birthdate": f"{1995 + i % 6}-03-01", "draft_year": 2018, "draft_round": 1,
            "draft_ovr": 10 if i % 3 == 0 else 200, "height": 72, "weight": 200,
            "pfr_id": None, "db_season": 2024} for i in range(n_players)]
    con = duckdb.connect()
    con.register("_w", pd.DataFrame(rows))
    con.register("_i", pd.DataFrame(ids))
    con.execute("CREATE TABLE weekly AS SELECT * FROM _w")
    con.execute("CREATE TABLE player_ids AS SELECT * FROM _i")
    con.execute("CREATE TABLE combine (pfr_id VARCHAR, forty DOUBLE, vertical DOUBLE, "
                "broad_jump DOUBLE, cone DOUBLE, shuttle DOUBLE, bench DOUBLE)")
    return con


def test_projected_frame_is_built_at_the_target_seasons_width():
    con = _t17_con()
    f = injury.projected_availability_frame(con, 2025)
    assert set(f["season"]) == {2025}
    assert f["week"].min() == 1 and f["week"].max() == 17            # the TARGET season's schedule
    # exactly the established universe (>=8 prior games) x 17 weeks -- players 10/11 are excluded
    assert f["player_key"].nunique() == 10
    assert len(f) == 10 * 17
    assert f.groupby("player_key")["week"].nunique().eq(17).all()


def test_projected_frame_uses_no_target_season_data():
    """PIT: the frame for an unplayed season is built strictly from ``season - 1``."""
    con = _t17_con(seasons=(2022, 2023, 2024))
    only_2024 = injury.projected_availability_frame(con, 2025)["player_key"].unique()
    # a player who appears ONLY in the target season cannot leak in (there is no such data yet)
    con.execute("INSERT INTO weekly VALUES (2025, '00-0009999', 1, 'T9', 'RB', 'REG')")
    assert set(injury.projected_availability_frame(con, 2025)["player_key"]) == set(only_2024)


def test_projected_frame_carries_prior_season_availability_and_target_season_age():
    con = _t17_con()
    f = injury.projected_availability_frame(con, 2025)
    row = f[f["player_key"] == "00-0000000"].iloc[0]
    assert row["prior_avail"] == pytest.approx(14 / 17, abs=1e-6)     # 2024 games / team games
    # age is as-of Sep-1 of the TARGET season, not one year stale
    born = pd.Timestamp("1995-03-01")
    assert row["age"] == pytest.approx((pd.Timestamp("2025-09-01") - born).days / 365.25, abs=0.01)


def test_projected_frame_has_no_outcome_column_populated():
    """It is a prediction frame; feeding it to the fit would train on nothing."""
    f = injury.projected_availability_frame(_t17_con(), 2025)
    assert f["available"].isna().all()


def test_projected_frame_empty_without_a_prior_season():
    f = injury.projected_availability_frame(_t17_con(seasons=(2022,)), 2025)
    assert f.empty and list(f.columns)[:3] == ["season", "player_key", "pos"]


def test_availability_projection_stamps_observed_vs_rolled_forward():
    con = _t17_con()
    obs = injury.availability_projection(con, 2024, train_seasons=[2022, 2023])
    fwd = injury.availability_projection(con, 2025, train_seasons=[2022, 2023])
    assert (obs["covariate_source"] == "observed").all()              # a played season is untouched
    assert (fwd["covariate_source"] == "rolled_forward").all()
    assert len(fwd) and (fwd["team_games"] == 17).all()               # the target season's schedule
    assert fwd["games_played_mean"].between(0, 17).all()


def test_rolled_forward_availability_is_not_a_four_value_constant():
    """The T17 symptom: everyone on the cohort prior collapses to a per-(pos, tier) constant."""
    fwd = injury.availability_projection(_t17_con(), 2025, train_seasons=[2022, 2023])
    assert fwd["avail_p"].round(6).nunique() > 4


def test_player_tiers_falls_back_to_the_crosswalk_for_an_unplayed_season():
    con = _t17_con()
    t = injury.player_tiers(con, [2025])
    assert len(t) == 12                                    # the crosswalk universe, not zero rows
    assert set(t["capital_tier"]) == {"hi", "lo"}          # the split the cohort prior routes on
    assert t.loc[t["player_key"] == "00-0000000", "capital_tier"].iloc[0] == "hi"


# -- the level guard ---------------------------------------------------------------------------
def _level_frames(mean_scale: float):
    dist = pd.DataFrame({"player_key": [f"p{i}" for i in range(10)], "pos": ["RB"] * 10,
                         "mean": np.arange(10, 0, -1) * 10.0 * mean_scale})
    proj = pd.DataFrame({"player_key": [f"p{i}" for i in range(10)],
                         "proj_points": np.arange(10, 0, -1) * 10.0})
    return dist, proj


def test_level_ratio_is_the_top_of_board_haircut():
    dist, proj = _level_frames(0.7)
    assert distribution.level_ratio(dist, proj, top_n=5) == pytest.approx(0.7)
    assert distribution.level_ratio(dist, proj, top_n=100) == pytest.approx(0.7)   # clips to n


def test_assert_level_band_passes_inside_and_raises_below():
    dist, proj = _level_frames(0.65)
    assert distribution.assert_level_band(dist, proj, 2025, top_n=5) == pytest.approx(0.65)
    collapsed, proj = _level_frames(0.37)          # the live-2026 board before T17 was fixed
    with pytest.raises(AssertionError, match="level ratio"):
        distribution.assert_level_band(collapsed, proj, 2026, top_n=5)


def test_assert_level_band_raises_when_the_hazard_is_inert():
    dist, proj = _level_frames(1.0)                # availability barely applied at all
    with pytest.raises(AssertionError, match="level ratio"):
        distribution.assert_level_band(dist, proj, 2026, top_n=5)


def test_level_ratio_raises_on_a_disjoint_board():
    dist, proj = _level_frames(0.7)
    with pytest.raises(ValueError, match="share no players"):
        distribution.level_ratio(dist, proj.assign(player_key="other"))


# --------------------------------------------------------------------------------------------
# T13 — the cloud is reproducible across processes (the determinism pin)
# --------------------------------------------------------------------------------------------
def test_deterministic_reads_pins_one_thread_and_restores_the_setting():
    """The mechanism, asserted rather than assumed.

    T13's actual cause was DuckDB's *parallel float aggregation* — partitions summed in whatever
    order the threads finished, so the training frames (and with them the fitted quantile/hazard
    coefficients, and with them every per-player draw) differed in the last bits between processes.
    Restoring the previous value matters as much as setting it: this wraps one assembler, not the
    caller's whole session.
    """
    con = duckdb.connect(":memory:")
    con.execute("SET threads TO 4")
    with db.deterministic_reads(con) as c:
        assert int(c.execute("SELECT current_setting('threads')").fetchone()[0]) == 1
    assert int(con.execute("SELECT current_setting('threads')").fetchone()[0]) == 4


def test_deterministic_reads_restores_the_setting_after_a_failed_block():
    con = duckdb.connect(":memory:")
    con.execute("SET threads TO 3")
    with pytest.raises(RuntimeError), db.deterministic_reads(con):
        raise RuntimeError("boom")
    assert int(con.execute("SELECT current_setting('threads')").fetchone()[0]) == 3


def test_deterministic_reads_leaves_a_non_duckdb_connection_alone():
    """A determinism guarantee where DuckDB is real — never a hard dependency on it being real."""
    class _Stub:
        def execute(self, *a, **k):
            raise AssertionError("not a DuckDB connection")

    stub = _Stub()
    with db.deterministic_reads(stub) as c:
        assert c is stub
