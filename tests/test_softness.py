"""Unit tests for the Phase-6 → cost-report softness wiring. Pure: no DB/network.

The credit's honesty rests on three properties: exposure is computed on the regression's own
frozen scale (so exposure × coef is unit-honest), the credit is exactly the exposure *gap* times
the coefficient (zero for identical rosters, positive when preferences tilt durable), and the
report's net line never moves the raw headline — it is derived, printed beside it, and labeled.
"""

from __future__ import annotations

import pandas as pd
import pytest

from fantasy_quant.adp.softness import (
    DURABILITY,
    SoftnessSignal,
    roster_exposure,
    softness_credit,
)
from fantasy_quant.valuation.cost_report import CostReport

SIG = SoftnessSignal(term="prior_games", label="durability (prior-yr games)", coef=10.0,
                     ci_lo=5.0, ci_hi=15.0, p_fdr=0.001, stability=1.0, mu=10.0, sd=5.0,
                     fitted_on="synthetic")


def _roster(keys, pos=None):
    return pd.DataFrame({"player_key": keys, "pos": pos or ["RB"] * len(keys)})


def test_roster_exposure_is_z_scored_on_the_frozen_panel_scale():
    traits = {"durable": 15.0, "average": 10.0, "fragile": 5.0}
    r = _roster(["durable", "average", "fragile"])
    # z = (+1) + 0 + (−1) = 0 on the frozen μ=10, σ=5 scale
    assert roster_exposure(r, traits, SIG) == pytest.approx(0.0)
    assert roster_exposure(_roster(["durable"]), traits, SIG) == pytest.approx(1.0)
    # a player with no prior line takes the panel convention: raw trait 0 → z = −2
    assert roster_exposure(_roster(["rookie"]), traits, SIG) == pytest.approx(-2.0)


def test_exposure_counts_offense_only():
    traits = {"rb": 15.0, "dst": 15.0}
    r = _roster(["rb", "dst"], pos=["RB", "DST"])
    assert roster_exposure(r, traits, SIG) == pytest.approx(1.0)   # the DST never enters


def test_credit_is_zero_for_identical_rosters_and_signed_for_tilted_ones():
    traits = {"durable": 15.0, "fragile": 5.0, "avg": 10.0}
    same = softness_credit([_roster(["avg"])], [_roster(["avg"])], traits, (SIG,))
    assert same["credit_points"].iloc[0] == pytest.approx(0.0)

    tilted = softness_credit([_roster(["durable"])], [_roster(["fragile"])], traits, (SIG,))
    row = tilted.iloc[0]
    assert row["delta_sd"] == pytest.approx(2.0)                   # +1 SD vs −1 SD
    assert row["credit_points"] == pytest.approx(20.0)             # 2 SD × 10 VOR/SD
    assert row["credit_lo"] == pytest.approx(10.0)                 # 2 × ci_lo
    assert row["credit_hi"] == pytest.approx(30.0)

    inverse = softness_credit([_roster(["fragile"])], [_roster(["durable"])], traits, (SIG,))
    assert inverse["credit_points"].iloc[0] == pytest.approx(-20.0)
    # negative delta: the CI bounds swap so lo ≤ hi still holds
    assert inverse["credit_lo"].iloc[0] <= inverse["credit_hi"].iloc[0]


def test_credit_averages_over_the_paired_drafts():
    traits = {"durable": 15.0, "avg": 10.0}
    pers = [_roster(["durable"]), _roster(["avg"])]                # mean exposure +0.5
    bench = [_roster(["avg"]), _roster(["avg"])]                   # mean exposure 0
    out = softness_credit(pers, bench, traits, (SIG,))
    assert out["credit_points"].iloc[0] == pytest.approx(5.0)      # 0.5 SD × 10


def test_frozen_durability_signal_is_the_scorecard_survivor():
    assert DURABILITY.term == "prior_games" and DURABILITY.coef > 0
    assert DURABILITY.p_fdr <= 0.05 and DURABILITY.stability >= 0.6
    assert DURABILITY.ci_lo > 0 < DURABILITY.ci_hi and DURABILITY.sd > 0


def test_report_renders_credit_and_net_line_without_moving_the_headline():
    soft = pd.DataFrame([{"label": "durability (prior-yr games)", "exposure_yours": 1.0,
                          "exposure_bench": 0.0, "delta_sd": 1.0, "credit_points": 10.0,
                          "credit_lo": 5.0, "credit_hi": 15.0}])
    empty = pd.DataFrame()
    rep = CostReport(
        season=2022, seat=0, n_drafts=2, archetype="bpa", risk_lambda=0.01,
        benchmark_value=200.0, personalized_value=188.0, cost_points=12.0, cost_pct=0.06,
        per_constraint=empty, secured=empty, personalized_roster=empty, benchmark_roster=empty,
        softness=soft, softness_points=10.0, net_cost_points=2.0,
    )
    text = rep.render()
    assert "personalization cost :     12.0 pts" in text           # the raw headline, untouched
    assert "market-softness credit" in text and "net effective cost" in text
    assert "historical-bias estimate" in text
    assert rep.net_cost_points == pytest.approx(rep.cost_points - rep.softness_points)
