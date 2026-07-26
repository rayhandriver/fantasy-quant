"""Unit tests for spine step 4 — realized-PAR cost validation. Pure: constructed cost series and
config objects, no DB/network (the DB-backed sweep is exercised by steps/spine_4_validate.py)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from fantasy_quant.config import DEV_SEASONS, LOCKBOX_SEASONS
from fantasy_quant.draft.config import DraftConfig, LeagueSetup
from fantasy_quant.valuation.cost_validation import (
    VALIDATION_SEASONS,
    _seat_config,
    crosscheck,
    summarize,
)


def _long(realized_by_season, projected_by_season, subject="zero_rb", bench=2000.0):
    """A synthetic per-draft ``long`` frame (one draft per season) with prescribed costs."""
    rows = []
    for s, (rc, pc) in enumerate(zip(realized_by_season, projected_by_season, strict=True)):
        rows.append({"subject": subject, "season": 2017 + s, "draft": 0, "seat": 0,
                     "bench_points": bench, "pers_points": bench - rc,
                     "realized_cost": rc, "projected_cost": pc})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------------
# season selection respects the lockbox + thin-history rule
# --------------------------------------------------------------------------------------------
def test_validation_seasons_are_dev_only_and_have_history():
    assert set(VALIDATION_SEASONS).issubset(set(DEV_SEASONS))
    assert not (set(VALIDATION_SEASONS) & set(LOCKBOX_SEASONS))
    # each validated season has >= 3 prior DEV seasons behind it (the conformal minimum).
    for s in VALIDATION_SEASONS:
        assert sum(t < s for t in DEV_SEASONS) >= 3
    assert min(VALIDATION_SEASONS) == 2017


# --------------------------------------------------------------------------------------------
# seat re-seating (rotating draft position)
# --------------------------------------------------------------------------------------------
def test_seat_config_reseats_without_touching_preferences():
    base = DraftConfig(league=LeagueSetup(draft_slot=1), archetype="zero_rb")
    moved = _seat_config(base, 6)
    assert moved.league.draft_slot == 7 and moved.league.your_team == 6
    assert moved.archetype == "zero_rb"                 # preferences preserved
    assert base.league.draft_slot == 1                  # original untouched (frozen replace)


# --------------------------------------------------------------------------------------------
# summarize: mean, CI, and the verdict logic
# --------------------------------------------------------------------------------------------
def test_summarize_flags_consistent_positive_cost_as_real():
    long = _long([10, 12, 11, 9, 10, 13], [8, 9, 7, 8, 9, 8])
    v = summarize(long, "zero_rb", n_boot=2000, seed=0)
    assert v.n_seasons == 6
    assert abs(v.realized_cost - np.mean([10, 12, 11, 9, 10, 13])) < 1e-9
    assert v.ci.lo > 0 and v.verdict.startswith("REAL COST")


def test_summarize_calls_noisy_series_indistinguishable():
    long = _long([-30, 40, -10, 20, -25, 35], [0, 0, 0, 0, 0, 0])
    v = summarize(long, "zero_rb", n_boot=2000, seed=0)
    assert v.ci.lo < 0 < v.ci.hi
    assert v.verdict == "not distinguishable from 0"


def test_summarize_flags_consistent_gain():
    long = _long([-20, -18, -25, -22, -19, -21], [1, 1, 1, 1, 1, 1])
    v = summarize(long, "zero_rb", n_boot=2000, seed=0)
    assert v.ci.hi < 0 and v.verdict.startswith("REAL GAIN")


# --------------------------------------------------------------------------------------------
# crosscheck: does projected cost track realized cost?
# --------------------------------------------------------------------------------------------
def test_crosscheck_perfect_sign_agreement():
    # projected and realized move together across subject-seasons.
    long = _long([10, -8, 12, -6, 9, -7], [5, -4, 6, -3, 4, -2])
    cc = crosscheck(long)
    assert cc.n == 6
    assert cc.sign_agreement == 1.0
    assert cc.spearman > 0.5


def test_crosscheck_no_relationship_low_agreement():
    # projected constant-positive, realized alternating → weak/absent agreement.
    long = _long([10, -10, 10, -10, 10, -10], [5, 5, 5, 5, 5, 5])
    cc = crosscheck(long)
    assert cc.sign_agreement <= 0.6


def test_empty_sweep_raises_a_diagnostic_error_not_a_keyerror(monkeypatch):
    """A season with no draftable board must say so, not die inside pandas.

    Regression for the 2025 dress rehearsal: `validate_archetypes` returned an empty frame and
    surfaced `KeyError: 'subject'`, which reads like a schema bug and hides the real cause (the
    board's `teams` label did not match what the harness asked for).
    """
    import pytest

    from fantasy_quant.valuation import cost_validation as cv

    monkeypatch.setattr(cv, "paired_costs",
                        lambda *a, **k: pd.DataFrame())
    with pytest.raises(ValueError, match="no drafts"):
        cv.validate_archetypes(None, archetypes=["zero_rb"], seasons=(2025,))
