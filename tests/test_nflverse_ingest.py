"""Unit tests for Phase 0.2 transforms that don't require the network."""

from __future__ import annotations

import pandas as pd

from fantasy_quant.data.sources.nflverse import map_snaps_gsis


def test_map_snaps_gsis_attaches_gsis_and_leaves_unmatched_null():
    snaps = pd.DataFrame(
        {
            "pfr_player_id": ["BurrJo00", "ChasJa00", "UnknownXX"],
            "season": [2023, 2023, 2023],
            "week": [1, 1, 1],
            "offense_snaps": [70, 55, 10],
        }
    )
    ids = pd.DataFrame(
        {
            "pfr_id": ["BurrJo00", "ChasJa00", "MahoPa00"],
            "gsis_id": ["00-0036442", "00-0036900", "00-0033873"],
            # a duplicate pfr_id should not explode the merge
        }
    )
    out = map_snaps_gsis(snaps, ids)

    assert len(out) == len(snaps)  # no row blow-up
    by_pfr = out.set_index("pfr_player_id")["gsis_id"]
    assert by_pfr["BurrJo00"] == "00-0036442"
    assert by_pfr["ChasJa00"] == "00-0036900"
    assert pd.isna(by_pfr["UnknownXX"])  # unmatched -> NULL, never dropped


def test_map_snaps_gsis_dedupes_crosswalk():
    snaps = pd.DataFrame({"pfr_player_id": ["DupeXx00"], "week": [1]})
    ids = pd.DataFrame(
        {
            "pfr_id": ["DupeXx00", "DupeXx00"],  # duplicated key in crosswalk
            "gsis_id": ["00-0000001", "00-0000001"],
        }
    )
    out = map_snaps_gsis(snaps, ids)
    assert len(out) == 1
    assert out.iloc[0]["gsis_id"] == "00-0000001"
