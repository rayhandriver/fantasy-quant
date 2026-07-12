"""Offline tests for Phase 7 (causal/) — opportunity-adjusted projection.

Synthetic panels only (no DB), so these run fast. They check the mechanics, not the DROP verdict:
the decomposition recovers a planted situation signal, the situation-swap is a pure delta on the
prior rate (identity for non-movers), and rookie intervals are ordered/roughly calibrated.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fantasy_quant.causal.counterfactual import project_season
from fantasy_quant.causal.decompose import TwoWayDecomposition, decompose
from fantasy_quant.causal.rookie_transport import RookieTransport


def _synth_panel(n_players=120, seasons=(2015, 2016, 2017, 2018), seed=0):
    """log(ppg) = pos_base + skill[player] + situation[team] + noise; ~15% of players move."""
    rng = np.random.default_rng(seed)
    teams = [f"T{i}" for i in range(12)]
    true_sit = {t: rng.normal(0, 0.3) for t in teams}
    skill = {f"p{i}": rng.normal(0, 0.4) for i in range(n_players)}
    home = {p: rng.choice(teams) for p in skill}
    rows = []
    for s in seasons:
        for p in skill:
            team = rng.choice(teams) if rng.random() < 0.15 else home[p]
            logppg = 2.4 + skill[p] + true_sit[team] + rng.normal(0, 0.15)
            ppg = np.exp(logppg)
            rows.append({"gsis_id": p, "season": s, "pos": "RB", "team": team,
                         "points": ppg * 15, "weeks": 15, "ppg": ppg})
    return pd.DataFrame(rows), true_sit, skill


def test_decompose_recovers_situation_ranking():
    panel, true_sit, skill = _synth_panel()
    dec = decompose(panel, alpha=5.0)
    est = pd.Series(dec.situation_)
    tru = pd.Series(true_sit).reindex(est.index)
    # estimated situation ranking correlates strongly with the planted truth
    assert est.corr(tru) > 0.6
    # a high-skill player scores above a low-skill one
    hi = max(skill, key=skill.get)
    lo = min(skill, key=skill.get)
    assert dec.skill(hi) > dec.skill(lo)


def test_situation_swap_is_delta_on_prior_rate():
    dec = TwoWayDecomposition(situation_={"A": 0.5, "B": 0.0})
    panel = pd.DataFrame([
        # a mover A->B and a stayer A->A across seasons 2016->2017
        {"gsis_id": "m", "season": 2016, "pos": "RB", "team": "A", "ppg": 10.0, "weeks": 15},
        {"gsis_id": "m", "season": 2017, "pos": "RB", "team": "B", "ppg": 12.0, "weeks": 15},
        {"gsis_id": "s", "season": 2016, "pos": "WR", "team": "A", "ppg": 8.0, "weeks": 15},
        {"gsis_id": "s", "season": 2017, "pos": "WR", "team": "A", "ppg": 9.0, "weeks": 15},
    ])
    out = project_season(dec, panel, 2017).set_index("gsis_id")
    # stayer: opp_rate identical to naive (zero situation delta)
    assert np.isclose(out.loc["s", "opp_rate"], out.loc["s", "naive_rate"])
    assert out.loc["s", "is_mover"] == 0
    # mover A(0.5)->B(0.0): opp = prior(10) * exp(0.0 - 0.5)
    assert np.isclose(out.loc["m", "opp_rate"], 10.0 * np.exp(-0.5))
    assert out.loc["m", "is_mover"] == 1


def test_rookie_transport_intervals_ordered():
    rng = np.random.default_rng(1)
    n = 200
    df = pd.DataFrame({
        "gsis_id": [f"r{i}" for i in range(n)],
        "pos": rng.choice(["RB", "WR", "TE", "QB"], n),
        "draft_year": 2018, "draft_ovr": rng.integers(1, 260, n).astype(float),
        "situation": rng.normal(0, 0.3, n), "forty": rng.normal(4.5, 0.2, n),
        "weeks": 14,
    })
    df["log_ovr"] = np.log(df["draft_ovr"])
    df["ppg"] = np.exp(2.6 - 0.4 * (df["log_ovr"] - df["log_ovr"].mean()) + rng.normal(0, 0.3, n))
    rt = RookieTransport(alpha=5.0).fit(df)
    pr = rt.project(df, z=1.0)
    assert (pr["ppg_lo"] < pr["proj_ppg"]).all() and (pr["proj_ppg"] < pr["ppg_hi"]).all()
    # higher draft capital (lower ovr) -> higher projection on average
    top = pr[df["draft_ovr"] <= 40]["proj_ppg"].mean()
    late = pr[df["draft_ovr"] >= 200]["proj_ppg"].mean()
    assert top > late
