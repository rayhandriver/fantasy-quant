"""Phase 16.7/16.8 — unit tests for the draft-slot drift panel and its model (no network).

Built on small synthetic panels rather than the DB so each property is checked in isolation. The
tests that carry the most weight are the ones guarding the two ways this phase could have produced
a **fake** result:

* :func:`test_heldout_board_excludes_the_rows_own_draft` — the ``source_divergence`` circularity.
  The stored ``sleeper_human`` ADP is the mean pick over the very drafts being explained, so the
  naive feature is the target's own negative.
* :func:`test_planted_signal_is_recovered` / :func:`test_pure_noise_scores_no_skill` — the
  walk-forward scorer must find a signal that is really there and must *not* find one that is not.
  A scorer that always reports skill would have turned this phase's null into a false positive.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fantasy_quant.adp import drift_model as dm
from fantasy_quant.adp import drift_panel as dp


# --- panel mechanics -----------------------------------------------------------------------------
def test_in_window_keeps_preseason_and_drops_the_rest():
    """The corpus runs February→November; only drafts inside the preseason window measure drift
    against a September board. This filter cuts 117 human drafts to 38, so it must be exact."""
    ts = pd.to_datetime(pd.Series([
        "2020-08-15", "2020-09-01", "2020-09-15", "2020-02-14", "2020-11-04", "2020-07-31",
    ]), utc=True)
    season = pd.Series([2020] * 6)
    keep = dp._in_window(ts, season)
    assert list(keep) == [True, True, True, False, False, False]


def test_in_window_is_keyed_to_the_rows_own_season():
    """A draft held in August 2019 for the 2020 season (an offseason startup) is out of window."""
    ts = pd.to_datetime(pd.Series(["2019-08-15", "2020-08-15"]), utc=True)
    keep = dp._in_window(ts, pd.Series([2020, 2020]))
    assert list(keep) == [False, True]


def _panel(n_drafts=3, teams=10, seed=0, jitter=True) -> pd.DataFrame:
    """A synthetic pick-grain panel: ``n_drafts`` drafts of the same 20 players.

    ``jitter=False`` makes every room draft exactly at ADP order, which is what the sign and
    centering tests need in order to assert on known numbers.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for d in range(n_drafts):
        for i in range(20):
            pick = i + 1 + (rng.integers(-2, 3) if jitter else 0)
            rows.append({
                "season": 2020, "draft_id": f"d{d}", "teams": teams, "scoring": "ppr",
                "start_ts": pd.Timestamp("2020-08-20", tz="UTC"), "days_to_board": 5.0,
                "pick_no": max(1, int(pick)), "round": 1, "draft_slot": 1,
                "gsis_id": f"p{i}", "name": f"P{i}", "pos": "WR",
                "adp": float(i + 1), "board_teams": 10, "adp_stdev": 3.0,
            })
    df = pd.DataFrame(rows)
    df["slot_rounds"] = df["pick_no"] / df["teams"]
    df["adp_rounds"] = df["adp"] / df["board_teams"]
    df["drift"] = df["adp_rounds"] - df["slot_rounds"]
    df["drift_centered"] = df["drift"] - df.groupby("draft_id")["drift"].transform("mean")
    return df


def test_drift_sign_positive_means_drafted_early():
    """The repo-wide convention (mirroring ``sleeper.build_tendencies``' ``reach``): a player taken
    ahead of his board position gets a POSITIVE drift. Getting this backwards would invert every
    downstream 16.9/16.10 conclusion, so it is asserted on explicit numbers rather than on the
    jittered fixture."""
    p = _panel(n_drafts=1, jitter=False)   # every room drafts exactly at ADP order
    assert np.allclose(p["drift"], 0.0), "drafting at ADP must produce zero drift"

    # now move one player two full rounds earlier than the board and re-derive.
    moved = p.copy()
    moved.loc[moved["gsis_id"] == "p9", "pick_no"] -= 20      # 20 picks = 2 rounds in a 10-teamer
    moved["slot_rounds"] = moved["pick_no"] / moved["teams"]
    moved["drift"] = moved["adp_rounds"] - moved["slot_rounds"]
    row = moved[moved["gsis_id"] == "p9"].iloc[0]
    assert row["drift"] == pytest.approx(2.0), "taken 2 rounds early => drift +2"
    assert row["drift"] > 0, "a reach must read as POSITIVE drift"
    assert moved[moved["gsis_id"] == "p8"].iloc[0]["drift"] == pytest.approx(0.0)


def test_rounds_normalization_makes_league_sizes_comparable():
    """Pick 12 means round 1.2 in a 10-team and round 1.0 in a 12-team room; the panel must express
    both in rounds so an 8- or 16-team draft can join a 10/12-team board."""
    a = _panel(n_drafts=1, teams=10)
    b = _panel(n_drafts=1, teams=12)
    assert a["slot_rounds"].iloc[5] == pytest.approx(a["pick_no"].iloc[5] / 10)
    assert b["slot_rounds"].iloc[5] == pytest.approx(b["pick_no"].iloc[5] / 12)


def test_drift_centered_is_mean_zero_within_every_draft():
    """Each room carries its own level offset (board depth vs draft depth, K/DST slots the
    offense-only panel never sees). Centering removes that draft fixed effect."""
    p = _panel(n_drafts=4)
    per_draft = p.groupby("draft_id")["drift_centered"].mean()
    assert np.allclose(per_draft.to_numpy(), 0.0, atol=1e-12)


def test_aggregate_player_season_reports_dispersion_and_depth():
    p = _panel(n_drafts=5)
    agg = dp.aggregate_player_season(p)
    assert len(agg) == 20
    assert (agg["n_drafts"] == 5).all()
    assert (agg["sd_drift"] >= 0).all()          # 16.9's variance-match target
    assert "mean_drift_centered" in agg.columns


# --- the leakage guard ----------------------------------------------------------------------------
def test_heldout_board_excludes_the_rows_own_draft():
    """``source_divergence`` must be built leave-one-draft-out. Checked numerically: for a player
    drafted in 3 drafts, the held-out board for draft 0 is the mean of drafts 1 and 2 only."""
    p = _panel(n_drafts=3, seed=7)
    held = dp.heldout_sleeper_board(p)
    one = p[p["gsis_id"] == "p3"]
    for idx in one.index:
        others = one.drop(index=idx)["slot_rounds"].mean()
        assert held.loc[idx] == pytest.approx(others)
        assert held.loc[idx] != pytest.approx(one["slot_rounds"].mean())


def test_heldout_board_is_nan_for_a_single_draft_season():
    """With one draft there is nothing to hold out — the feature must be missing, not silently
    equal to the row itself (which would be perfect self-prediction)."""
    p = _panel(n_drafts=1)
    held = dp.heldout_sleeper_board(p)
    assert held.isna().all()


def test_naive_divergence_would_have_been_the_target_itself():
    """Documents *why* the held-out form exists: the naive feature (FFC minus the board built from
    ALL drafts, including this one) is, up to sign, this panel's own aggregate target."""
    p = _panel(n_drafts=4, seed=3)
    naive_board = p.groupby("gsis_id")["slot_rounds"].transform("mean")
    naive_divergence = p["adp_rounds"] - naive_board
    player_mean_drift = p.groupby("gsis_id")["drift"].transform("mean")
    assert np.corrcoef(naive_divergence, player_mean_drift)[0, 1] > 0.99


# --- the model scorer -----------------------------------------------------------------------------
def _model_panel(effect: float, n_seasons=4, seed=0) -> pd.DataFrame:
    """Panel with a planted linear relationship of size ``effect`` between ``rookie`` and drift."""
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(2018, 2018 + n_seasons):
        for _i in range(150):
            rookie = int(rng.random() < 0.3)
            rows.append({
                "season": s, "pos": "WR", "rookie": rookie,
                "vbd_gap": rng.normal(), "source_divergence": rng.normal(),
                "team_changed": 0, "new_starting_qb": 0,
                "competition_change_roster": 0, "competition_change_depth": 0,
                "adp_rounds": rng.uniform(1, 15), "adp_stdev": rng.uniform(1, 10),
                "days_to_board": rng.uniform(-5, 20),
                "drift_centered": effect * rookie + rng.normal(0, 1.0),
            })
    return pd.DataFrame(rows)


def test_planted_signal_is_recovered():
    """A real effect must show up as positive skill — otherwise the phase's null means nothing."""
    v = dm.walk_forward_drift(_model_panel(effect=3.0), dm.ABLATION_FEATURES, n_boot=200)
    assert v.skill > 0.10
    assert v.skill_ci[0] > 0
    assert v.spearman > 0.3


def test_pure_noise_scores_no_skill():
    """With no relationship, the scorer must not manufacture one."""
    v = dm.walk_forward_drift(_model_panel(effect=0.0, seed=11), dm.ABLATION_FEATURES, n_boot=200)
    assert v.skill < 0.05
    assert v.skill_ci[0] <= 0


def test_baseline_is_drift_equals_zero():
    """The comparison is against 'everyone goes at ADP', i.e. mean |drift|, not against a fitted
    intercept — a fitted baseline would flatter the model."""
    p = _model_panel(effect=0.0, seed=5)
    v = dm.walk_forward_drift(p, dm.ABLATION_FEATURES, n_boot=50)
    expected = p.groupby("season")["drift_centered"].apply(lambda s: s.abs().mean())
    assert v.mae_baseline == pytest.approx(
        float(np.average(expected, weights=p.groupby("season").size())), rel=1e-6)


def test_sign_stability_is_reported_per_term():
    p = _model_panel(effect=2.0, seed=2)
    stab = dm.sign_stability(p, dm.ABLATION_FEATURES)
    assert "stability" in stab.columns
    assert set(stab["stability"].dropna()) <= set(np.linspace(0, 1, 5))
    rookie = stab[stab["term"] == "rookie"].iloc[0]
    assert rookie["stability"] == pytest.approx(1.0)   # a real effect never flips sign


def test_empty_panel_returns_a_null_verdict_not_a_crash():
    v = dm.walk_forward_drift(pd.DataFrame(columns=[*dm.DRIFT_FEATURES, "drift_centered",
                                                    "season", "pos"]))
    assert v.n == 0
    assert np.isnan(v.skill)
