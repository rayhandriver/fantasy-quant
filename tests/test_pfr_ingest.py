"""Unit tests for Phase 0.3 transforms that don't require the network."""

from __future__ import annotations

import pandas as pd

from fantasy_quant.data.sources.pfr import map_pfr_ids


def _ids():
    return pd.DataFrame(
        {
            "pfr_id": ["JeffJu00", "ChasJa00", "MahoPa00"],
            "gsis_id": ["00-0036322", "00-0036900", "00-0033873"],
        }
    )


def test_map_pfr_ids_crosswalk_and_unmatched_null():
    df = pd.DataFrame(
        {
            "pfr_id": ["JeffJu00", "ChasJa00", "NobodyXx00"],
            "player": ["Justin Jefferson", "Ja'Marr Chase", "Nobody"],
            "season": [2023, 2023, 2023],
            "yds": [1074, 1216, 0],
        }
    )
    out = map_pfr_ids(df, _ids())
    assert len(out) == 3  # no row blow-up
    g = out.set_index("pfr_id")["gsis_id"]
    assert g["JeffJu00"] == "00-0036322"
    assert pd.isna(g["NobodyXx00"])  # unmatched -> NULL, not dropped


def test_map_pfr_ids_applies_overrides():
    df = pd.DataFrame({"pfr_id": ["NobodyXx00"], "player": ["Nobody"], "season": [2023]})
    overrides = pd.DataFrame({"pfr_id": ["NobodyXx00"], "gsis_id": ["00-0099999"]})
    out = map_pfr_ids(df, _ids(), overrides)
    assert out.iloc[0]["gsis_id"] == "00-0099999"  # override fills the crosswalk miss
