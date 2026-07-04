"""Unit tests for Phase 2 pure pieces — VBD, baseline helpers, props, ensemble blend (no DB)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from fantasy_quant.backtest.metrics import ReplacementLevels
from fantasy_quant.markets.props_projection import props_projection
from fantasy_quant.projections.baseline import _age_factor, _shrink_ppg
from fantasy_quant.projections.ensemble import blend_rank_fn
from fantasy_quant.valuation.vbd import board_key, vbd


def _repl() -> ReplacementLevels:
    by_pos = {p: {"rank": 1, "level": lvl} for p, lvl in
              {"QB": 270.0, "RB": 190.0, "WR": 220.0, "TE": 140.0, "K": 150.0, "DST": 140}.items()}
    return ReplacementLevels(by_pos=by_pos, roster_total=0.0, n_teams=10)


def test_vbd_subtracts_positional_replacement():
    proj = pd.DataFrame({"player_key": ["a", "b", "c"], "pos": ["QB", "RB", "TE"],
                         "proj_points": [350.0, 250.0, 160.0]})
    out = vbd(proj, _repl())
    assert list(out["vbd"]) == [80.0, 60.0, 20.0]  # 350-270, 250-190, 160-140


def test_vbd_handles_ffc_position_aliases():
    proj = pd.DataFrame({"player_key": ["d"], "pos": ["PK"], "proj_points": [170.0]})
    assert vbd(proj, _repl())["vbd"].iloc[0] == 20.0  # PK -> K, 170-150


def test_board_key_prefers_gsis_then_name():
    board = pd.DataFrame({"gsis_id": ["00-1", None], "name": ["Player A", "Buffalo Defense"]})
    assert list(board_key(board)) == ["00-1", "Buffalo Defense"]


def test_shrink_ppg_weights_by_sample_size():
    # 6 games -> weight 0.5 -> midpoint of player (20) and mean (10) = 15.
    assert _shrink_ppg(20.0, 6.0, 10.0) == 15.0
    # a full season barely shrinks; a tiny sample leans on the mean.
    assert _shrink_ppg(20.0, 17.0, 10.0) > _shrink_ppg(20.0, 2.0, 10.0)


def test_age_factor_penalizes_the_old():
    assert _age_factor("RB", 31) == 0.85
    assert _age_factor("RB", 24) == 1.0
    assert _age_factor("WR", 33) == 0.90
    assert _age_factor("QB", 40) == 0.90
    assert _age_factor("RB", None) == 1.0


def test_props_projection_maps_market_to_points():
    props = pd.DataFrame({"player_key": ["wr1"], "pos": ["WR"],
                          "rec_yds": [1200.0], "receptions": [90.0], "rec_tds": [9.0]})
    # 1200*0.1 + 90*1 + 9*6 = 120 + 90 + 54 = 264
    assert props_projection(props)["proj_points"].iloc[0] == 264.0


def test_props_projection_empty_is_empty():
    out = props_projection(pd.DataFrame(columns=["player_key", "pos"]))
    assert out.empty and list(out.columns) == ["player_key", "pos", "proj_points"]


def test_blend_rank_fn_weighted_average():
    board = pd.DataFrame({"adp": [10.0, 20.0, 30.0]})

    def a(b, con=None, season=None, as_of=None):
        return pd.Series([1.0, 2.0, 3.0], index=b.index)

    def z(b, con=None, season=None, as_of=None):
        return pd.Series([3.0, 2.0, 1.0], index=b.index)

    out = blend_rank_fn([a, z], [1, 1])(board)  # normalized 0.5/0.5
    assert list(out) == [2.0, 2.0, 2.0]


def test_blend_rank_fn_nan_component_falls_back_to_adp():
    board = pd.DataFrame({"adp": [10.0, 20.0, 30.0]})

    def partial(b, con=None, season=None, as_of=None):
        return pd.Series([1.0, np.nan, 3.0], index=b.index)

    out = blend_rank_fn([partial], [1.0])(board)  # single component -> its ADP-filled values
    assert list(out) == [1.0, 20.0, 3.0]
