"""Unit tests for Phase 0.4 — name normalization, identity matching, and the adp_asof PIT guard."""

from __future__ import annotations

import datetime as dt

import duckdb
import pandas as pd

from fantasy_quant.data.sources.adp import (
    adp_asof,
    dedupe_gsis_within_snapshot,
    match_adp_to_gsis,
    normalize_name,
)


def test_normalize_name_strips_punct_and_suffix():
    assert normalize_name("D.J. Moore") == "dj moore"
    assert normalize_name("Michael Pittman Jr.") == "michael pittman"
    assert normalize_name("Ja'Marr Chase") == "jamarr chase"
    assert normalize_name("Patrick Mahomes II") == "patrick mahomes"
    assert normalize_name(None) == ""


def _ids():
    # two same-name WRs in different eras to exercise draft-year disambiguation
    return pd.DataFrame(
        {
            "name": ["Mike Williams", "Mike Williams", "Justin Jefferson"],
            "position": ["WR", "WR", "WR"],
            "team": ["TB", "LAC", "MIN"],
            "gsis_id": ["00-0027702", "00-0033536", "00-0036322"],
            "draft_year": [2010, 2017, 2020],
        }
    )


def test_match_prefers_draft_year_appropriate_homonym():
    adp = pd.DataFrame(
        {
            "name": ["Mike Williams", "Mike Williams", "Justin Jefferson"],
            "position": ["WR", "WR", "WR"],
            "team": ["XXX", "XXX", "XXX"],  # force name+pos tier (no team match)
            "season": [2011, 2019, 2022],
        }
    )
    out = match_adp_to_gsis(adp, _ids())
    g = out["gsis_id"].tolist()
    assert g[0] == "00-0027702"  # 2011 -> the 2010-draft Mike Williams
    assert g[1] == "00-0033536"  # 2019 -> the 2017-draft Mike Williams
    assert g[2] == "00-0036322"


def test_match_uses_team_when_available():
    adp = pd.DataFrame({"name": ["Mike Williams"], "position": ["WR"],
                        "team": ["LAC"], "season": [2019]})
    out = match_adp_to_gsis(adp, _ids())
    assert out.iloc[0]["gsis_id"] == "00-0033536"


def test_dedupe_gsis_within_snapshot_nulls_homonym_loser():
    # two real "Mike Williams" WRs in one 2010 board both resolved to the same gsis; keep the
    # lower-ADP (more prominent) row, null the other so joins stay 1:1.
    df = pd.DataFrame(
        {
            "season": [2010, 2010, 2010],
            "source": ["ffc", "ffc", "ffc"],
            "format": ["redraft", "redraft", "redraft"],
            "scoring": ["ppr", "ppr", "ppr"],
            "teams": [12, 12, 12],
            "name": ["Mike Williams", "Mike Williams", "Adrian Peterson"],
            "adp": [55.0, 130.0, 1.8],
            "gsis_id": ["00-0027702", "00-0027702", "00-0009999"],
        }
    )
    out, n = dedupe_gsis_within_snapshot(
        df, ["season", "source", "format", "scoring", "teams"]
    )
    assert n == 1
    # the lower-ADP Mike Williams keeps the gsis; the higher-ADP one is nulled
    assert out.loc[out["adp"] == 55.0, "gsis_id"].iloc[0] == "00-0027702"
    assert pd.isna(out.loc[out["adp"] == 130.0, "gsis_id"].iloc[0])
    assert out.loc[out["name"] == "Adrian Peterson", "gsis_id"].iloc[0] == "00-0009999"


def test_name_override_resolves_nickname():
    adp = pd.DataFrame({"name": ["Hollywood Brown"], "position": ["WR"],
                        "team": ["BAL"], "season": [2022]})
    overrides = pd.DataFrame({"name": ["Hollywood Brown"], "position": ["WR"],
                              "gsis_id": ["00-0035662"]})
    out = match_adp_to_gsis(adp, _ids(), overrides=overrides)
    assert out.iloc[0]["gsis_id"] == "00-0035662"  # tiers 1-3 miss the nickname; override fixes it


def test_adp_asof_is_point_in_time():
    con = duckdb.connect(":memory:")
    con.execute(
        """
        CREATE TABLE adp_snapshots AS
        SELECT * FROM (VALUES
            (2020, DATE '2020-09-01', 'ffc', 'redraft', 'ppr', 10, '00-0001', 5.0),
            (2020, DATE '2020-09-01', 'ffc', 'redraft', 'ppr', 10, '00-0002', 8.0)
        ) AS t(season, snapshot_date, source, format, scoring, teams, gsis_id, adp)
        """
    )
    assert len(adp_asof(con, 2020, dt.date(2020, 8, 31))) == 0   # day before -> nothing leaks
    assert len(adp_asof(con, 2020, dt.date(2020, 9, 2))) == 2    # day after  -> full board
    # exactly on the snapshot date counts as known (<=), and no returned row is ever future-dated
    on_day = adp_asof(con, 2020, dt.date(2020, 9, 1))
    assert len(on_day) == 2
    assert pd.to_datetime(on_day["snapshot_date"]).max() <= pd.Timestamp("2020-09-01")
