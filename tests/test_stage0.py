"""Stage 0 — snapshot-series idempotency (pure parts of adp.snapshot_adp)."""

from __future__ import annotations

import datetime as dt

import pandas as pd

from fantasy_quant.data.sources.adp import dedupe_gsis_within_snapshot, new_snapshot_rows


def _frame(dates, scoring="ppr", teams=10):
    rows = []
    for d in dates:
        rows.append({"season": 2026, "source": "ffc", "format": "redraft", "scoring": scoring,
                     "teams": teams, "snapshot_date": d, "name": "A Player", "adp": 1.0})
    return pd.DataFrame(rows)


def test_new_snapshot_rows_filters_existing_dates():
    df = _frame([dt.date(2026, 7, 9), dt.date(2026, 7, 16)])
    existing = {(2026, "ffc", "redraft", "ppr", 10, dt.date(2026, 7, 9))}
    out = new_snapshot_rows(df, existing)
    assert len(out) == 1
    assert pd.to_datetime(out["snapshot_date"].iloc[0]).date() == dt.date(2026, 7, 16)


def test_new_snapshot_rows_keeps_all_when_store_empty():
    df = _frame([dt.date(2026, 7, 9), dt.date(2026, 7, 16)])
    assert len(new_snapshot_rows(df, set())) == 2


def test_new_snapshot_rows_distinguishes_configs_on_same_date():
    d = dt.date(2026, 7, 9)
    df = pd.concat([_frame([d], scoring="ppr"), _frame([d], scoring="standard")],
                   ignore_index=True)
    existing = {(2026, "ffc", "redraft", "ppr", 10, d)}
    out = new_snapshot_rows(df, existing)
    assert out["scoring"].tolist() == ["standard"]


def test_snapshot_dedupe_key_includes_snapshot_date():
    # the same gsis on two different snapshot dates must BOTH survive (a series, not a dupe);
    # within one date, the higher-ADP row is nulled (the 0.4 homonym rule).
    d1, d2 = dt.date(2026, 7, 9), dt.date(2026, 7, 16)
    df = pd.DataFrame({
        "season": [2026] * 3, "source": ["ffc"] * 3, "format": ["redraft"] * 3,
        "scoring": ["ppr"] * 3, "teams": [10] * 3,
        "snapshot_date": [d1, d2, d2],
        "gsis_id": ["00-1", "00-1", "00-1"],
        "adp": [5.0, 6.0, 9.0],
    })
    key = ["season", "source", "format", "scoring", "teams", "snapshot_date"]
    out, n_nulled = dedupe_gsis_within_snapshot(df, key)
    assert n_nulled == 1
    assert out.loc[out["snapshot_date"] == d1, "gsis_id"].notna().all()
    kept = out[out["snapshot_date"] == d2]
    assert kept["gsis_id"].notna().sum() == 1
    assert kept.loc[kept["gsis_id"].notna(), "adp"].iloc[0] == 6.0
