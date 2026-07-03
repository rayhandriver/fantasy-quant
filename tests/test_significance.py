"""Unit tests for Phase 1.5 — the block-bootstrap significance machinery (no DB/network)."""

from __future__ import annotations

import numpy as np
import pytest

from fantasy_quant.backtest.significance import block_bootstrap_ci


def test_point_estimate_is_the_observed_statistic():
    x = [1.0, 2.0, 3.0, 4.0, 5.0]
    ci = block_bootstrap_ci(x, n_boot=2000, seed=0)
    assert ci.point == np.mean(x)
    assert ci.lo <= ci.point <= ci.hi


def test_recovers_sample_mean_and_iid_se():
    rng = np.random.default_rng(1)
    x = rng.normal(10.0, 2.0, size=400)  # true mean 10
    ci = block_bootstrap_ci(x, n_boot=3000, expected_block=1, seed=2)  # iid bootstrap
    assert abs(ci.mean - x.mean()) < 0.02              # bootstrap mean ~ the sample mean
    assert ci.lo <= x.mean() <= ci.hi                  # CI brackets the observed statistic
    assert abs(ci.point - 10.0) < 0.5                  # sample mean is near the truth
    assert abs(ci.se - x.std(ddof=0) / np.sqrt(400)) < 0.02  # iid SE ~ sigma/sqrt(n)


def test_block_bootstrap_respects_autocorrelation():
    # AR(1), phi=0.85: strong positive autocorrelation -> the mean's true variance exceeds the iid
    # estimate. The block bootstrap (L>1) should report a LARGER SE than the iid bootstrap (L=1).
    rng = np.random.default_rng(3)
    n = 400
    x = np.empty(n)
    x[0] = rng.normal()
    for t in range(1, n):
        x[t] = 0.85 * x[t - 1] + rng.normal()
    iid = block_bootstrap_ci(x, n_boot=2000, expected_block=1, seed=4)
    block = block_bootstrap_ci(x, n_boot=2000, expected_block=20, seed=4)
    assert block.se > 1.5 * iid.se, f"block SE {block.se:.3f} should exceed iid SE {iid.se:.3f}"


def test_significant_flag():
    # a clearly-positive low-variance series -> CI excludes 0 -> significant.
    pos = block_bootstrap_ci([8.0, 9.0, 10.0, 11.0, 12.0], n_boot=2000, seed=5)
    assert pos.significant and pos.lo > 0
    # a symmetric zero-mean series -> CI straddles 0 -> not significant.
    null = block_bootstrap_ci([-5.0, 5.0, -5.0, 5.0, -5.0, 5.0], n_boot=2000, seed=6)
    assert not null.significant


def test_constant_series_has_zero_width_ci():
    ci = block_bootstrap_ci([5.0, 5.0, 5.0, 5.0], n_boot=500, seed=7)
    assert ci.lo == ci.hi == ci.point == 5.0
    assert ci.se == 0.0
    assert ci.significant  # 5 > 0 with no uncertainty


def test_default_block_length_is_cube_root():
    ci = block_bootstrap_ci(list(range(27)), n_boot=200, seed=8)
    assert ci.block == 3  # round(27 ** (1/3))


def test_empty_series_raises():
    with pytest.raises(ValueError, match="empty"):
        block_bootstrap_ci([], n_boot=10)
