"""Unit tests for Phase 8 — covariance & roster construction. Pure: synthetic data, no DB/network.

Covers the guards that make the layer trustworthy: the covariance hard gate (and its
diagonal-preserving repair), planted-correlation recovery through the pooled estimator, the
shrinkage limits (data-rich → empirical, data-poor → prior), the copula's tail dependence vs the
Gaussian, Iman–Conover marginal preservation, the roster floor/ceiling directions the BUILD_PLAN
names as the 8.4 done-bar, the handcuff option monotonicity (8.5), and the covariance-aware greedy
actually diversifying away from a priced stack (the 9.1 pull-forward).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from fantasy_quant.covariance import copula
from fantasy_quant.covariance.estimate import (
    CovarianceGateError,
    generic_key,
    nearest_psd,
    pair_correlations,
    player_covariance,
    relationship_key,
    validate_covariance,
)
from fantasy_quant.covariance.shrinkage import (
    STRUCTURED_PRIOR,
    CorrelationModel,
    neutral_model,
    shrink_correlations,
)
from fantasy_quant.draft.config import DraftConfig, LeagueSetup
from fantasy_quant.draft.optimizer import (
    attach_value,
    build_risk_model,
    cross_covariance,
    personalized_pick_fn,
    portfolio_value,
    team_value,
)
from fantasy_quant.draft.simulator import DRAFTABLE, RosterSlots, simulate_draft
from fantasy_quant.valuation.handcuff import elevation_stats, handcuff_value
from fantasy_quant.valuation.roster_risk import (
    correlate_samples,
    floor_ceiling,
    portfolio_moments,
    roster_risk,
)

UNCAPPED = RosterSlots(pos_caps=dict.fromkeys(DRAFTABLE, 99))


# --------------------------------------------------------------------------------------------
# 8.1 — hard gate, repair, planted-correlation recovery
# --------------------------------------------------------------------------------------------
def test_gate_accepts_valid_and_rejects_broken_covariances():
    validate_covariance(np.array([[4.0, 1.0], [1.0, 2.0]]))
    with pytest.raises(CovarianceGateError, match="not PSD"):
        validate_covariance(np.array([[1.0, 2.0], [2.0, 1.0]]))
    with pytest.raises(CovarianceGateError, match="symmetric"):
        validate_covariance(np.array([[1.0, 0.5], [0.1, 1.0]]))
    with pytest.raises(CovarianceGateError, match="finite"):
        validate_covariance(np.array([[1.0, np.nan], [np.nan, 1.0]]))
    with pytest.raises(CovarianceGateError, match="diagonal"):
        validate_covariance(np.array([[0.0, 0.0], [0.0, 1.0]]))


def test_nearest_psd_repairs_and_preserves_the_diagonal():
    bad = np.array([[1.0, 0.9, -0.9], [0.9, 1.0, 0.9], [-0.9, 0.9, 1.0]])  # not PSD
    fixed = nearest_psd(bad)
    validate_covariance(fixed)
    assert np.allclose(np.diag(fixed), np.diag(bad))     # own variances are Phase-5 truth


def _weekly_panel(rho: float = 0.5, n_seasons: int = 6, weeks: int = 14,
                  seed: int = 0) -> pd.DataFrame:
    """8 teams × n seasons; each team a QB and WR correlated at ``rho`` + an independent RB."""
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(2015, 2015 + n_seasons):
        for t in range(8):
            team = f"T{t}"
            z = rng.standard_normal(weeks)
            qb = 15 + 5 * (np.sqrt(rho) * z + np.sqrt(1 - rho) * rng.standard_normal(weeks))
            wr = 12 + 5 * (np.sqrt(rho) * z + np.sqrt(1 - rho) * rng.standard_normal(weeks))
            rb = 10 + 5 * rng.standard_normal(weeks)
            for w in range(weeks):
                for pid, pos, pts in ((f"{s}{team}QB", "QB", qb[w]),
                                      (f"{s}{team}WR", "WR", wr[w]),
                                      (f"{s}{team}RB", "RB", rb[w])):
                    rows.append({"season": s, "week": w + 1, "gsis_id": pid, "pos": pos,
                                 "team": team, "points": float(pts)})
    return pd.DataFrame(rows)


def test_pair_correlations_recover_a_planted_stack():
    emp = pair_correlations(_weekly_panel(rho=0.5))
    stack = emp[emp["rel"] == "QB1-WR1"].iloc[0]
    indep = emp[emp["rel"] == "QB1-RB1"].iloc[0]
    assert stack["n_pairs"] == 48                       # 8 teams × 6 seasons
    assert abs(stack["corr"] - 0.5) < 0.10              # recovers the planted ρ
    assert abs(indep["corr"]) < 0.10                    # and finds nothing where there is nothing


def test_player_covariance_assembles_and_gates():
    model = neutral_model()
    cov = player_covariance(
        sd=[50.0, 40.0, 45.0], teams=["A", "A", "B"], positions=["QB", "WR", "RB"],
        roles=[1, 1, 1], rho_fn=model.rho)
    validate_covariance(cov)
    assert cov[0, 1] == pytest.approx(0.40 * 50 * 40)   # QB1-WR1 prior stack
    assert cov[0, 2] == 0.0                             # cross-team pairs are 0


# --------------------------------------------------------------------------------------------
# 8.2 — shrinkage limits + lookup fallback
# --------------------------------------------------------------------------------------------
def test_shrinkage_data_rich_goes_empirical_data_poor_goes_prior():
    emp = pd.DataFrame({
        "rel": ["QB1-WR1", "TE2-TE3"], "generic": ["QB-WR", "TE-TE"],
        "corr": [0.10, 0.90], "n_pairs": [10000, 1], "n_weeks": [100000, 10]})
    shrunk = shrink_correlations(emp, kappa=25.0)
    rich = shrunk[shrunk["rel"] == "QB1-WR1"].iloc[0]
    poor = shrunk[shrunk["rel"] == "TE2-TE3"].iloc[0]
    assert abs(rich["rho"] - 0.10) < 0.01               # data wins with 10k pairs
    assert abs(poor["rho"] - STRUCTURED_PRIOR["TE-TE"]) < 0.06   # prior wins with 1 pair


def test_correlation_model_fallback_chain():
    m = CorrelationModel.from_table(pd.DataFrame({
        "rel": ["QB1-WR1", "QB-WR"], "generic": ["QB-WR", "QB-WR"],
        "corr": [0.5, 0.3], "n_pairs": [100, 400], "n_weeks": [0, 0],
        "prior": [0.4, 0.35], "weight": [0.8, 0.94], "rho": [0.48, 0.31]}))
    assert m.rho("QB", 1, "WR", 1) == 0.48              # exact role relationship
    assert m.rho("WR", 1, "QB", 1) == 0.48              # order-free
    assert m.rho("QB", 1, "WR", 3) == 0.31              # generic pair fallback
    assert m.rho("RB", 1, "RB", 2) == STRUCTURED_PRIOR["RB1-RB2"]   # prior fallback
    assert relationship_key("WR", 5, "QB", 1) == "QB1-WR3"          # rank cap
    assert generic_key("WR", "QB") == "QB-WR"


# --------------------------------------------------------------------------------------------
# 8.3 — copula tail dependence (what the Gaussian misses)
# --------------------------------------------------------------------------------------------
def test_clayton_tau_and_tail_dependence_roundtrip():
    rng = np.random.default_rng(1)
    theta = copula.clayton_theta(0.4)                   # = 2·0.4/0.6
    uv = copula.clayton_sample(theta, 30000, rng)
    tau_hat, _ = stats.kendalltau(uv[:, 0], uv[:, 1])
    assert abs(tau_hat - 0.4) < 0.03                    # sampler hits the target dependence
    q = 0.05
    emp_tail = float(np.mean(uv[uv[:, 0] <= q, 1] <= q))
    assert abs(emp_tail - copula.boom_given_bust_clayton(q, theta)) < 0.05


def test_rotated_clayton_beats_gaussian_in_the_handcuff_tail():
    tau = 0.35
    theta = copula.clayton_theta(tau)
    q = 0.05
    clayton = copula.boom_given_bust_clayton(q, theta)
    gauss = copula.boom_given_bust_gaussian(q, tau)
    assert clayton > gauss * 1.5                        # the tail the linear ρ cannot see
    rng = np.random.default_rng(2)
    uv = copula.rotated_clayton_sample(theta, 20000, rng)
    assert np.corrcoef(uv[:, 0], uv[:, 1])[0, 1] < -0.2   # handcuff direction: u low ↔ v high


def test_handcuff_dependence_found_in_a_synthetic_backfield():
    rows = []
    for s in (2018, 2019):
        for t in range(6):
            team = f"T{t}"
            for w in range(1, 15):
                active = w <= 10
                if active:                              # starter plays weeks 1–10 only
                    rows.append({"season": s, "week": w, "gsis_id": f"{s}{team}A", "pos": "RB",
                                 "team": team, "points": 15.0 + (w % 3)})
                rows.append({"season": s, "week": w, "gsis_id": f"{s}{team}B", "pos": "RB",
                             "team": team, "points": (3.0 if active else 16.0) + (w % 2)})
    dep = copula.handcuff_dependence(pd.DataFrame(rows))
    assert dep["n_pairs"] == 12
    assert dep["tau"] < -0.3                            # backup booms exactly when starter is out
    assert dep["tail"] > 0.2                            # which the Clayton θ turns into tail mass


# --------------------------------------------------------------------------------------------
# 8.4 — Iman–Conover + floor/ceiling directions (the BUILD_PLAN done-bar)
# --------------------------------------------------------------------------------------------
def test_iman_conover_imposes_correlation_without_touching_marginals():
    rng = np.random.default_rng(3)
    samples = np.vstack([rng.lognormal(3, 0.6, 4000), rng.exponential(50, 4000),
                         rng.uniform(0, 300, 4000)])
    target = np.array([[1.0, 0.6, 0.0], [0.6, 1.0, 0.0], [0.0, 0.0, 1.0]])
    out = correlate_samples(samples, target, rng)
    for i in range(3):                                  # marginals are pure permutations
        assert np.allclose(np.sort(out[i]), np.sort(samples[i]))
    rho01, _ = stats.spearmanr(out[0], out[1])
    rho02, _ = stats.spearmanr(out[0], out[2])
    assert abs(rho01 - 0.6) < 0.05 and abs(rho02) < 0.05


def test_stack_raises_ceiling_hedge_raises_floor():
    mean, sd = [100.0, 100.0], 40.0
    stacked = np.array([[sd**2, 0.5 * sd**2], [0.5 * sd**2, sd**2]])
    hedged = np.array([[sd**2, -0.5 * sd**2], [-0.5 * sd**2, sd**2]])
    mu_s, sd_s = portfolio_moments(mean, stacked)
    mu_h, sd_h = portfolio_moments(mean, hedged)
    lo_s, hi_s = floor_ceiling(mu_s, sd_s)
    lo_h, hi_h = floor_ceiling(mu_h, sd_h)
    assert mu_s == mu_h == 200.0
    assert hi_s > hi_h and lo_h > lo_s                  # stack = ceiling, hedge = floor


def _synthetic_value_index() -> pd.DataFrame:
    return pd.DataFrame({
        "player_key": ["qb_a", "wr_a", "rb1_a", "rb2_a", "wr_b"],
        "pos": ["QB", "WR", "RB", "RB", "WR"],
        "team": ["AAA", "AAA", "AAA", "AAA", "BBB"],
        "role_rank": [1, 1, 1, 2, 1],
        "mean": [300.0, 250.0, 240.0, 120.0, 245.0],
        "sd": [50.0, 45.0, 48.0, 40.0, 44.0],
        "base_value": [120.0, 110.0, 100.0, 20.0, 105.0],
    })


def test_roster_risk_names_the_stack_and_the_hedge():
    vi = _synthetic_value_index()
    roster = pd.DataFrame({"player_key": ["qb_a", "wr_a", "rb1_a", "rb2_a", "wr_b"]})
    rr = roster_risk(roster, vi, neutral_model())
    assert rr.n_valued == 5 and rr.sd > 0
    pairs = {(r.player_a, r.player_b): r.rel_rho for r in rr.pairs.itertuples(index=False)}
    assert pairs[("qb_a", "wr_a")] == pytest.approx(0.40)      # stack detected
    assert pairs[("rb1_a", "rb2_a")] == pytest.approx(-0.30)   # hedge detected
    assert ("qb_a", "wr_b") not in pairs                       # cross-team pair is not a pair


# --------------------------------------------------------------------------------------------
# portfolio CE + the covariance-aware greedy (9.1 pulled forward)
# --------------------------------------------------------------------------------------------
def test_portfolio_value_charges_the_cross_terms():
    vi = _synthetic_value_index()
    roster = pd.DataFrame({"player_key": ["qb_a", "wr_a"]})
    lam, corr = 0.01, neutral_model()
    cross = 0.40 * 50.0 * 45.0                          # QB1-WR1 prior stack
    assert cross_covariance(roster, vi, corr) == pytest.approx(cross)
    assert portfolio_value(roster, vi, corr, lam) == pytest.approx(230.0 - 2 * lam * cross)
    assert portfolio_value(roster, vi, corr, 0.0) == pytest.approx(team_value(roster, vi))
    legacy = vi.drop(columns=["sd", "team"])            # pre-Phase-8 index: no covariance info
    assert cross_covariance(roster, legacy, corr) == 0.0


def _stack_board():
    """A board where the two best values are a same-team QB+WR stack and the third-best is an
    equivalent WR on another team, all deep enough in ADP that opponents leave them alone."""
    rows = [{"name": f"F{i}", "position": "RB", "adp": float(i + 2), "pos_rank": i + 1,
             "gsis_id": f"filler_{i}"} for i in range(28)]           # opponents eat these
    rows += [
        {"name": "QB A", "position": "QB", "adp": 30.0, "pos_rank": 1, "gsis_id": "qb_a"},
        {"name": "WR A", "position": "WR", "adp": 31.0, "pos_rank": 1, "gsis_id": "wr_a"},
        {"name": "WR B", "position": "WR", "adp": 32.0, "pos_rank": 2, "gsis_id": "wr_b"},
    ]
    rows += [{"name": f"D{i}", "position": "WR", "adp": float(40 + i), "pos_rank": 3 + i,
              "gsis_id": f"deep_{i}"} for i in range(120)]
    board = pd.DataFrame(rows)
    vi = pd.DataFrame({
        "player_key": ["qb_a", "wr_a", "wr_b"] + [f"deep_{i}" for i in range(120)],
        "pos": ["QB", "WR", "WR"] + ["WR"] * 120,
        "team": ["AAA", "AAA", "BBB"] + ["CCC"] * 120,
        "role_rank": [1, 1, 1] + [1] * 120,
        "mean": [300.0, 299.0, 298.0] + [100.0] * 120,
        "sd": [60.0, 60.0, 60.0] + [10.0] * 120,
        "base_value": [200.0, 199.0, 198.0] + list(np.linspace(150, 30, 120)),
    })
    return board, vi


def _my_first_two(vi, board, lam):
    corr = neutral_model()                               # QB1-WR1 prior ρ = +0.40
    cfg = DraftConfig(league=LeagueSetup(draft_slot=1, slots=UNCAPPED), risk_lambda=lam)
    b = attach_value(board, vi)
    risk = build_risk_model(b, vi, corr, lam, scarcity_w=0.0)   # isolate the covariance mechanic
    res = simulate_draft(b, your_pick_fn=personalized_pick_fn(cfg, 0.0, risk),
                         n_teams=10, rounds=15, slots=UNCAPPED, your_team=0, noise=0.0, seed=7)
    return res.pick_log().query("is_you")["player_key"].tolist()[:2]


def test_covariance_aware_greedy_diversifies_away_from_the_stack():
    board, vi = _stack_board()
    # λ=0: covariance-blind — takes the two best raw values, the same-offense stack.
    assert _my_first_two(vi, board, lam=0.0) == ["qb_a", "wr_a"]
    # λ>0: the marginal penalty 2λ·ρ·σ² ≈ 29 pts ≫ the 1-pt value gap — takes the other-team WR.
    assert _my_first_two(vi, board, lam=0.01) == ["qb_a", "wr_b"]


# --------------------------------------------------------------------------------------------
# 8.5 — the handcuff option
# --------------------------------------------------------------------------------------------
def test_handcuff_value_moves_with_fragility_and_elevation():
    durable = handcuff_value(0.05, 6.0, 2.0, 17)
    fragile = handcuff_value(0.30, 6.0, 2.0, 17)
    assert fragile.option_premium > durable.option_premium > 0
    assert handcuff_value(0.30, 6.0, 1.0, 17).option_premium == pytest.approx(0.0)
    assert fragile.contingent_ev == pytest.approx(17 * (0.7 * 6.0 + 0.3 * 12.0))


def test_elevation_stats_pools_the_two_regimes():
    pairs = pd.DataFrame({
        "season": [2020] * 100, "team": ["T"] * 100, "week": list(range(100)),
        "starter_pts": [10.0] * 60 + [0.0] * 40,
        "backup_pts": [4.0] * 60 + [12.0] * 40,
        "starter_active": [True] * 60 + [False] * 40,
    })
    es = elevation_stats(pairs)
    assert es["ppg_with"] == pytest.approx(4.0) and es["ppg_without"] == pytest.approx(12.0)
    assert es["ratio"] == pytest.approx(3.0)
    thin = elevation_stats(pairs.head(62), min_out_weeks=30)   # only 2 starter-out weeks
    assert thin["ratio"] == 1.0                                # too thin to claim anything
