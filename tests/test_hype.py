"""Offline tests for Phase 16.10 (curated hype board) and 16.11 (live ADP momentum).

No DB: synthetic snapshot series and synthetic boards. What these pin down is the machinery that
is easy to get silently wrong — the **sign convention** (positive = drafted earlier, carried
identically from 16.7 through to the utility offset), the **review gate** (an unsigned board is
inert), and the two **mechanical corrections** without which the nomination ranks players by board
depth and by position rather than by narrative. The empirical content — who is actually hyped in
2026 — lives in `reference/hype_board.csv` and `analysis/phase16_1{0,1}_*.json`, not here.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fantasy_quant.adp.hype_board import (
    HYPE_COLS,
    MAX_PICK_DELTA,
    _z_resid,
    apply_hype,
    assert_hype_schema,
    hype_deltas,
    hyped_adp,
    load_hype_board,
    summarize,
)
from fantasy_quant.adp.momentum import (
    MIN_SNAPSHOTS,
    _slope_and_se,
    adp_velocity,
    momentum_summary,
    movers,
)
from fantasy_quant.draft.opponent_model import _ADP_SCALE


# =================================================================================================
# 16.11 — momentum
# =================================================================================================
class _FakeCon:
    """Stands in for the DuckDB connection: `adp_velocity` issues exactly one query."""

    def __init__(self, df: pd.DataFrame):
        self._df = df

    def execute(self, _sql, _params=None):
        return self

    def df(self):
        return self._df.copy()


def _series(moves: dict[str, list[float]], dates=("2026-07-09", "2026-07-18", "2026-07-24")):
    rows = []
    for gid, adps in moves.items():
        for d, a in zip(dates, adps, strict=False):
            rows.append({"snapshot_date": d, "gsis_id": gid, "name": gid,
                         "position": "WR", "team": "SF", "adp": a, "stdev": 5.0})
    return pd.DataFrame(rows)


def test_velocity_sign_positive_means_drafted_earlier():
    """The single most expensive thing to get backwards in this phase. A FALLING ADP number means
    the room takes him EARLIER, which is `velocity > 0` — matching 16.7's `drift`."""
    df = _series({"riser": [100.0, 90.0, 80.0], "faller": [100.0, 110.0, 120.0],
                  "flat": [100.0, 100.0, 100.0]})
    v = adp_velocity(_FakeCon(df), 2026).set_index("gsis_id")
    assert v.loc["riser", "velocity"] > 0
    assert v.loc["faller", "velocity"] < 0
    assert abs(v.loc["flat", "velocity"]) < 1e-9


def test_velocity_centers_out_board_wide_drift():
    """The pool deepens through a preseason, so every ADP creeps later together. That common
    component belongs to the board, not to a player: if everyone moves identically, nobody moved."""
    df = _series({f"p{i}": [100.0 + i, 105.0 + i, 110.0 + i] for i in range(9)})
    v = adp_velocity(_FakeCon(df), 2026)
    assert np.allclose(v["velocity"], 0.0, atol=1e-9)
    assert v["board_median_slope"].iloc[0] < 0        # the board itself drifted later


def test_velocity_median_is_zero_by_construction():
    df = _series({f"p{i}": [50.0 + 3 * i, 50.0 + 2 * i, 50.0 + i] for i in range(11)})
    v = adp_velocity(_FakeCon(df), 2026)
    assert abs(momentum_summary(v)["velocity_median"]) < 1e-9


def test_two_snapshot_player_shrinks_to_zero():
    """Two points give a slope with no residual df. It is reported, but an infinite standard error
    must crush it — otherwise a player who appeared on exactly two boards outranks the whole
    file."""
    df = _series({"thin": [100.0, 80.0], "a": [50.0, 51.0, 52.0], "b": [60.0, 59.0, 58.0],
                  "c": [70.0, 72.0, 74.0], "d": [80.0, 79.0, 77.0]},
                 dates=("2026-07-09", "2026-07-18", "2026-07-24"))
    v = adp_velocity(_FakeCon(df), 2026).set_index("gsis_id")
    assert v.loc["thin", "n_snapshots"] == 2
    assert not np.isfinite(v.loc["thin", "se"])
    assert v.loc["thin", "velocity_shrunk"] == 0.0
    assert v.loc["thin", "velocity"] != 0.0           # the raw slope is still reported


def test_single_snapshot_player_is_dropped():
    df = _series({"solo": [100.0], "a": [50.0, 51.0, 52.0]})
    v = adp_velocity(_FakeCon(df), 2026)
    assert "solo" not in set(v["gsis_id"])
    assert MIN_SNAPSHOTS == 2


def test_slope_and_se_degenerate_design():
    slope, se = _slope_and_se(np.array([1.0]), np.array([5.0]))
    assert np.isnan(slope) and not np.isfinite(se)
    slope, se = _slope_and_se(np.array([0.0, 0.0]), np.array([5.0, 9.0]))
    assert np.isnan(slope)                            # no spread in x -> no slope


def test_noisier_player_shrinks_further_than_a_clean_one():
    """Shrinkage must key on the standard error, not on the raw slope size.

    The filler players carry genuinely *different* slopes on purpose: if they all moved alike the
    cross-player signal variance would be zero, every velocity would shrink to zero, and the test
    would pass or fail for a reason unrelated to what it claims to check.
    """
    days = np.array([0.0, 9.0, 15.0])                 # the real 2026 snapshot cadence
    clean = list(100.0 - 0.5 * days)                   # perfectly linear -> se == 0
    noisy = [100.0, 88.0, 92.5]                        # similar net move, real residual
    # a spread of genuine, cleanly-measured slopes, so the cross-player signal variance is large
    # enough for shrinkage to have something to keep
    filler = {f"p{i}": list(60.0 + i + (i - 6) * 0.4 * days) for i in range(13)}
    v = adp_velocity(_FakeCon(_series({"clean": clean, "noisy": noisy, **filler})),
                     2026).set_index("gsis_id")
    assert v.loc["noisy", "se"] > v.loc["clean", "se"]
    keep = lambda g: v.loc[g, "velocity_shrunk"] / v.loc[g, "velocity"]   # noqa: E731
    assert keep("noisy") < keep("clean")
    assert 0 < keep("clean") <= 1.0


def test_movers_filters_kickers():
    """A raw sort is dominated by kickers, whose ADP swings 15+ picks between boards for no
    narrative reason. A hype readout that shows them is reporting noise with names on it."""
    df = _series({f"p{i}": [50.0 + i, 55.0 + i, 60.0 + i] for i in range(6)})
    df.loc[df["gsis_id"] == "p0", "position"] = "K"
    df.loc[df["gsis_id"] == "p0", "adp"] = [100.0, 60.0, 20.0]
    v = adp_velocity(_FakeCon(df), 2026)
    assert v.iloc[0]["gsis_id"] == "p0"                       # the kicker tops the raw table
    m = movers(v, k=5)
    assert "p0" not in set(m["risers"]["gsis_id"])            # and is absent from the readout


def test_momentum_summary_leads_with_not_backtestable():
    v = adp_velocity(_FakeCon(_series({f"p{i}": [50.0 + i, 52.0 + i, 54.0 + i]
                                       for i in range(5)})), 2026)
    s = momentum_summary(v)
    assert s["backtestable"] is False
    assert "not backtestable" in s["forward_only"]


def test_empty_series_is_not_an_error():
    v = adp_velocity(_FakeCon(pd.DataFrame(columns=["snapshot_date", "gsis_id", "name",
                                                    "position", "team", "adp", "stdev"])), 2026)
    assert v.empty
    assert momentum_summary(v)["n_players"] == 0


# =================================================================================================
# 16.10 — the hype board
# =================================================================================================
def _hype(rows):
    base = dict(season=2026, player="X", position="WR", team="SF", adp=50.0, note="n",
                source="s", evidence="derived+web", confidence="med", reviewed=True)
    return pd.DataFrame([{**base, **r} for r in rows], columns=HYPE_COLS)


def test_z_resid_removes_the_depth_confound():
    """ADP standard deviation grows mechanically with ADP, so an unconditional z-score ranks
    players by how deep they are. `ABLATION_SURVIVOR_W` holds *partial* coefficients (16.8 fit them
    with `adp_rounds` in the model), so the carrier has to be residualized to match."""
    adp = pd.Series(np.linspace(1, 200, 60))
    plain = None
    # both shapes must be absorbed: the control nests log(adp) and adp precisely so the answer does
    # not depend on which one the real carrier happens to follow.
    for stdev in (pd.Series(0.15 * adp), pd.Series(4.0 * np.log(adp))):
        z = _z_resid(stdev, adp)
        assert np.abs(z).max() < 1e-6                 # nothing survives -> nobody is "disputed"
        plain = (stdev - stdev.mean()) / stdev.std()
        assert plain.abs().max() > 1.0                # the naive version would have ranked them


def test_z_resid_keeps_a_genuine_outlier():
    adp = pd.Series(np.linspace(1, 200, 60))
    stdev = pd.Series(0.15 * adp)
    stdev.iloc[3] += 20.0                             # an early player nobody agrees on
    z = _z_resid(stdev, adp)
    assert z[3] == pytest.approx(np.abs(z).max())
    assert z[3] > 3


def test_z_resid_removes_a_positional_level():
    """Our value board likes TEs more than ADP does across the board. That is a real *value* claim
    about a position and not evidence that any individual TE has a narrative — without the position
    control the nomination came back TE-flooded."""
    n = 80
    pos = pd.Series(["WR", "TE"] * (n // 2))
    adp = pd.Series(np.linspace(1, 200, n))
    gap = pd.Series(np.where(pos == "TE", 5.0, 0.0))  # entirely a positional offset
    assert np.abs(_z_resid(gap, adp, pos)).max() < 1e-6


def test_schema_rejects_an_oversized_delta():
    with pytest.raises(ValueError, match="beyond"):
        assert_hype_schema(_hype([{"gsis_id": "g1", "pick_delta": MAX_PICK_DELTA + 1}]))


def test_schema_rejects_duplicates_and_missing_ids():
    with pytest.raises(ValueError, match="duplicate"):
        assert_hype_schema(_hype([{"gsis_id": "g1", "pick_delta": 1.0},
                                  {"gsis_id": "g1", "pick_delta": 2.0}]))
    with pytest.raises(ValueError, match="gsis_id"):
        assert_hype_schema(_hype([{"gsis_id": "", "pick_delta": 1.0}]))


def test_review_gate_refuses_unreviewed_rows(tmp_path):
    """The load-bearing safety property: a Claude-drafted board cannot reach a simulation until a
    human signs it. Structural, not advisory."""
    p = tmp_path / "hype.csv"
    df = _hype([{"gsis_id": "g1", "pick_delta": 6.0, "reviewed": False},
                {"gsis_id": "g2", "pick_delta": 4.0, "reviewed": True}])
    p.write_text(df.to_csv(index=False))
    assert set(load_hype_board(p, 2026)["gsis_id"]) == {"g2"}
    assert len(load_hype_board(p, 2026, require_reviewed=False)) == 2


def test_load_tolerates_a_comment_header_and_a_missing_file(tmp_path):
    p = tmp_path / "hype.csv"
    p.write_text("# a header the generator writes\n"
                 + _hype([{"gsis_id": "g1", "pick_delta": 3.0}]).to_csv(index=False))
    assert len(load_hype_board(p, 2026)) == 1
    assert load_hype_board(tmp_path / "nope.csv").empty


def test_deltas_align_to_board_rows_not_to_hype_rows():
    """The alignment contract every consumer depends on: the returned vector is indexed like the
    board, zero where a player has no hype row. Getting this wrong lands offsets on the wrong
    players silently — the exact failure `simulate_drift_panel` guards against for the 16.9
    shock."""
    board = pd.DataFrame({"player_key": ["a", "b", "c", "d"], "adp": [10.0, 20.0, 30.0, 40.0]})
    h = _hype([{"gsis_id": "c", "pick_delta": 7.0}, {"gsis_id": "a", "pick_delta": -2.0}])
    assert list(hype_deltas(board, h)) == [-2.0, 0.0, 7.0, 0.0]


def test_apply_hype_matches_an_equivalent_adp_shift():
    """The conversion runs through the model's own ADP coefficient, so "6 picks early" means
    exactly what it would have meant had his ADP been 6 picks lower."""
    board = pd.DataFrame({"player_key": ["a", "b"], "adp": [50.0, 60.0]})
    h = _hype([{"gsis_id": "a", "pick_delta": 6.0}])
    beta = -1.68
    u = apply_hype(board, h, beta_adp_s=beta)
    assert u[0] == pytest.approx(-beta * 6.0 / _ADP_SCALE)
    assert u[0] > 0                                   # beta is negative -> hype is a positive bump
    assert u[1] == 0.0


def test_hyped_adp_moves_a_hyped_player_earlier():
    board = pd.DataFrame({"player_key": ["a", "b"], "adp": [50.0, 60.0]})
    h = _hype([{"gsis_id": "a", "pick_delta": 8.0}, {"gsis_id": "b", "pick_delta": -5.0}])
    assert list(hyped_adp(board, h)) == [42.0, 65.0]


def test_empty_board_is_inert():
    board = pd.DataFrame({"player_key": ["a", "b"], "adp": [50.0, 60.0]})
    empty = pd.DataFrame(columns=HYPE_COLS)
    assert np.allclose(hype_deltas(board, empty), 0.0)
    assert np.allclose(apply_hype(board, empty, beta_adp_s=-1.68), 0.0)
    assert summarize(empty)["n_rows"] == 0


def test_summarize_always_flags_the_claim_as_uncurated_by_evidence():
    s = summarize(_hype([{"gsis_id": "g1", "pick_delta": 5.0},
                         {"gsis_id": "g2", "pick_delta": -3.0}]))
    assert s["curated_not_backtested"] is True
    assert s["n_positive"] == 1 and s["n_negative"] == 1


def test_shipped_board_is_wellformed_and_unsigned():
    """The board committed in this repo must parse, and must still be inert — if this fails because
    rows were signed, that is the review gate opening deliberately and the test should be updated
    with intent rather than silently."""
    board = load_hype_board(season=2026, require_reviewed=False)
    if board.empty:
        pytest.skip("no hype board shipped yet")
    assert_hype_schema(board)
    assert board["pick_delta"].abs().max() <= MAX_PICK_DELTA
    assert not load_hype_board(season=2026)["reviewed"].any() if len(
        load_hype_board(season=2026)) else True
