"""Unit tests for Phase 6 — ADP-bias mining. Pure: synthetic panels, no DB/network.

Covers the three guards that make the result trustworthy: the leave-one-season-out baseline does not
leak a season's own outcome into its own alpha; the regression recovers a planted effect with a
season-block-bootstrap CI; and the scorecard flags a stable planted bias while ruling out noise.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fantasy_quant.adp.panel import FEATURES, _loso_isotonic_baseline
from fantasy_quant.adp.regression import fit_alpha_regression, prepare
from fantasy_quant.adp.scorecard import _season_stability, bias_scorecard


def _panel(n_seasons: int = 9, depth: int = 40, planted_rookie: float = 0.0,
           noise: float = 15.0, seed: int = 0, independent: bool = False) -> pd.DataFrame:
    """A synthetic alpha panel. ``alpha`` = a planted rookie effect + season-clustered noise. With
    ``independent`` the traits are fully decoupled and ``alpha`` is pure noise (a clean null)."""
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(2014, 2014 + n_seasons):
        season_shock = rng.normal(0, 5)   # a whole-season common shock (clustering)
        for pos in ("QB", "RB", "WR", "TE"):
            for r in range(1, depth + 1):
                rookie = int(rng.random() < 0.15)
                # in the null, prior stats don't zero out for rookies → no structural collinearity.
                exp = float(rng.integers(0, 12)) if independent else (0 if rookie else
                                                                      float(rng.integers(1, 12)))
                pg = float(rng.integers(0, 18)) if independent else (0.0 if rookie else
                                                                     float(rng.integers(0, 18)))
                ppg = float(rng.uniform(0, 20)) if independent else (0.0 if rookie else
                                                                     float(rng.uniform(0, 20)))
                alpha = ((0.0 if independent else season_shock)
                         + planted_rookie * rookie + rng.normal(0, noise))
                rows.append({
                    "season": s, "gsis_id": f"{s}_{pos}_{r}", "name": f"{pos}{r}", "pos": pos,
                    "adp": float(r), "pos_rank": r, "adp_stdev": float(rng.uniform(1, 15)),
                    "realized_vor": 200.0 - 3 * r + alpha, "alpha": float(alpha),
                    "rookie": rookie, "experience": float(exp),
                    "prior_games": pg, "prior_ppg": ppg,
                })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------------
# 6.1 — the leave-one-season-out baseline is monotone AND leak-free
# --------------------------------------------------------------------------------------------
def test_loso_baseline_centers_alpha_when_seasons_agree():
    """8 identical seasons: realized_vor = 100 - pos_rank → LOSO baseline recovers it, alpha ~ 0."""
    rows = []
    for s in range(2014, 2022):
        for pos in ("QB", "RB", "WR", "TE"):
            for r in range(1, 31):
                rows.append({"season": s, "pos": pos, "pos_rank": r,
                             "realized_vor": 100.0 - r})
    panel = pd.DataFrame(rows)
    implied = _loso_isotonic_baseline(panel)
    alpha = panel["realized_vor"] - implied
    assert alpha.abs().mean() < 1.0        # baseline ≈ the shared curve


def test_loso_baseline_does_not_leak_own_season():
    """One season is shifted +200. If the baseline leaked its own data, its alpha would be ~0;
    because it is fit on the *other* seasons only, its alpha must reflect the full +200 shift."""
    rows = []
    for s in range(2014, 2023):
        shift = 200.0 if s == 2022 else 0.0
        for pos in ("QB", "RB", "WR", "TE"):
            for r in range(1, 31):
                rows.append({"season": s, "pos": pos, "pos_rank": r,
                             "realized_vor": 100.0 - r + shift})
    panel = pd.DataFrame(rows)
    alpha = panel["realized_vor"] - _loso_isotonic_baseline(panel)
    shock = alpha[panel["season"] == 2022]
    calm = alpha[panel["season"] != 2022]
    # If the baseline leaked its own season, the shocked season's alpha would collapse to ~0.
    # It doesn't: the +200 shift is fully reflected (baseline is fit on the other seasons only).
    assert shock.mean() > 150.0
    # The calm seasons are pulled only mildly (their baseline legitimately trains on 2022), and the
    # shocked season stands clearly apart — the hallmark of leave-one-season-out.
    assert shock.mean() - calm.mean() > 180.0


# --------------------------------------------------------------------------------------------
# 6.2 — the design matrix + recovering a planted effect
# --------------------------------------------------------------------------------------------
def test_prepare_zscroes_continuous_and_dummifies_position():
    aug, cols = prepare(_panel())
    assert "z_experience" in cols and "rookie" in cols
    assert {"pos_RB", "pos_WR", "pos_TE"}.issubset(cols) and "pos_QB" not in cols
    assert abs(aug["z_adp_stdev"].mean()) < 1e-9 and abs(aug["z_adp_stdev"].std(ddof=0) - 1) < 1e-9


def test_regression_recovers_planted_rookie_effect():
    reg = fit_alpha_regression(_panel(planted_rookie=25.0, seed=1), n_boot=800)
    i = reg.terms.index("rookie")
    assert reg.coef[i] > 12.0               # recovers the +25 planted effect (attenuated by noise)
    assert reg.ci_lo[i] > 0                 # and is distinguishable from zero


def test_regression_finds_no_effect_in_pure_noise():
    reg = fit_alpha_regression(_panel(planted_rookie=0.0, seed=2), n_boot=800)
    i = reg.terms.index("rookie")
    assert reg.ci_lo[i] < 0 < reg.ci_hi[i]  # CI straddles 0 when nothing is planted


# --------------------------------------------------------------------------------------------
# 6.3 — the scorecard flags stable planted bias, rules out noise, handles constant seasons
# --------------------------------------------------------------------------------------------
def test_scorecard_flags_stable_planted_bias():
    sc = bias_scorecard(_panel(planted_rookie=30.0, seed=3), n_boot=800)
    row = sc.table[sc.table["term"] == "rookie"].iloc[0]
    assert row["significant"] and row["p_fdr"] < 0.05 and row["stability"] >= 0.6
    assert "rookie" in sc.significant["label"].tolist()


def test_scorecard_rules_out_noise_traits():
    # a clean null: traits decoupled, alpha pure noise → nothing survives FDR + stability.
    sc = bias_scorecard(_panel(planted_rookie=0.0, seed=4, independent=True), n_boot=800)
    assert sc.significant.empty


def test_stability_skips_constant_in_season_column():
    """A trait constant within a season (rookies all 0 one year) must not crash stability and is
    simply not counted for that season."""
    panel = _panel(seed=5)
    panel.loc[panel["season"] == 2016, "prior_games"] = 0.0   # constant that season
    aug, cols = prepare(panel)
    reg = fit_alpha_regression(panel, n_boot=200)
    stab = _season_stability(aug, cols, reg.terms, reg.coef)
    n_seasons, frac = stab["z_prior_games"]
    assert n_seasons <= panel["season"].nunique()
    assert 0.0 <= frac <= 1.0


def test_features_all_present_in_scorecard():
    sc = bias_scorecard(_panel(seed=6), n_boot=200)
    assert len(sc.table) == len(FEATURES)
    assert set(sc.table["term"]) == {"rookie", "z_experience", "z_adp_stdev",
                                     "z_prior_games", "z_prior_ppg"}
