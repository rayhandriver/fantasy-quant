"""Session DATA-1 / 0.12.5 — **FTN charting**, 2022-2025, shipped ``backtestable: false``.

    uv run python steps/phase0_12_5_ftn.py

Play-level manual charting: ``is_play_action`` · ``is_motion`` · ``is_rpo`` · ``is_screen_pass`` ·
``is_no_huddle`` · ``n_blitzers`` · ``n_offense_backfield`` · ``n_defense_box`` · ``qb_location`` ·
``read_thrown``. It answers *"what is this offense doing in 2026"* better than anything else free.

★ **And it must never quietly become a backtest input.** ``DEV_SEASONS`` is 2014-2022 and FTN's
upstream floor is 2022, so it contributes **exactly one development season**. Any bar built on it
is a bar built on n=1 — a mistake this repo has already made twice (T24's four-season subsample,
T40's n=1 control) and does not need to make a third time. So the label is not a docstring: the
table is registered ``backtestable: false`` and 0.12.8 asserts it, because *a prose warning is not
a guard* (UI-1's lesson 4).

Writes ``analysis/phase0_12_5_ftn.json``.
"""

from __future__ import annotations

import json

import pandas as pd

from fantasy_quant.config import DEV_SEASONS, PROJECT_ROOT
from fantasy_quant.data import db
from fantasy_quant.data.sources import nflverse_release as nr

OUT_JSON = PROJECT_ROOT / "analysis" / "phase0_12_5_ftn.json"
TAG = STEM = "ftn_charting"
TABLE = "ftn_charting"
FTN_SEASONS = [2022, 2023, 2024, 2025]


def ingest_ftn(con, seasons=FTN_SEASONS, refresh: bool = False) -> dict:
    df = nr.read_seasons(TAG, STEM, seasons, refresh=refresh)
    df = df.rename(columns={"nflverse_game_id": "game_id", "nflverse_play_id": "play_id"})
    df["play_id"] = pd.to_numeric(df["play_id"], errors="coerce").astype("Int64")
    df = df.drop(columns=[c for c in ("_source_season",) if c in df.columns])
    db.write_df(con, TABLE, df)
    return {"table": TABLE, "n_rows": len(df), "n_cols": df.shape[1],
            "seasons": sorted(int(s) for s in df["season"].unique())}


def main() -> dict:
    con = db.connect()
    ing = ingest_ftn(con)

    join = con.execute(f"""
        select f.season, count(*) as n, count(b.play_id) as n_matched,
               round(count(b.play_id) / count(*), 5) as match_rate
        from "{TABLE}" f left join pbp b using (game_id, play_id)
        group by 1 order by 1
    """).df()

    dev_overlap = sorted(set(ing["seasons"]) & set(DEV_SEASONS))
    result = {
        "substep": "0.12.5",
        "ingest": ing,
        "join_to_pbp": join.to_dict("records"),
        "backtestable": False,
        "upstream_floor": nr.SEASON_FLOORS[TAG],
        "dev_seasons_covered": dev_overlap,
        "n_dev_seasons_covered": len(dev_overlap),
        "why_not_backtestable": (
            f"DEV_SEASONS is {min(DEV_SEASONS)}-{max(DEV_SEASONS)} and FTN's upstream floor is "
            f"{nr.SEASON_FLOORS[TAG]}, so the overlap is {dev_overlap} — n={len(dev_overlap)} "
            "development season(s). Descriptive and live-2026 use only; never a backtest feature. "
            "0.12.8 asserts this rather than trusting the label."
        ),
        # the bar for this substep: it landed, it joins, and the label is *correct* (not merely
        # written) — a single DEV season is the fact that makes the flag true
        "passed": bool((join["match_rate"] >= 0.99).all()) and len(dev_overlap) <= 1,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True, default=str))
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return result


if __name__ == "__main__":
    raise SystemExit(0 if main()["passed"] else 1)
