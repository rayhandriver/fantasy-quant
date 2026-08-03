"""Session DATA-1 / 0.12.7 — reconciliation done-bar.

    uv run python steps/phase0_12_7_reconcile.py

Three claims:

1. ``depth_charts_all`` is **season-complete 2014-2025** and its grain is a *column*, not an
   inference from which fields are null. (The scoped defect was "2025 lives in a separate table";
   what was actually on disk was two grains inside one table, 58 % of it invisible to any
   ``group by season``.)
2. The DOUBLE ``season``/``week`` columns are INT and the cast **preserved every value** — checked
   before the rewrite, not asserted after it.
3. gsis match rates are reported for every new table **with the unmatched population named**, not
   as a bare percentage.

Writes ``analysis/phase0_12_7_reconcile.json``.
"""

from __future__ import annotations

import json

from fantasy_quant.config import PROJECT_ROOT
from fantasy_quant.data import db, reconcile

OUT_JSON = PROJECT_ROOT / "analysis" / "phase0_12_7_reconcile.json"

CROSSWALK_TABLES = {
    "participation_player_week": "gsis_id",
    "weekly_rosters": "gsis_id",
    "contracts": "gsis_id",
    "depth_charts_all": "gsis_id",
    "players_master": "gsis_id",
}


def main() -> dict:
    con = db.connect()

    casts = reconcile.double_to_int_seasons(con)
    unified = reconcile.build_depth_charts_all(con)
    rates = reconcile.crosswalk_match_rates(con, CROSSWALK_TABLES)

    casts_ok = all(c["action"] == "skipped" or c["values_preserved"] for c in casts)
    result = {
        "substep": "0.12.7",
        "double_to_int": casts,
        "casts_value_preserving": casts_ok,
        "depth_charts_all": unified,
        "crosswalk_match_rates": rates,
        "finding": (
            "depth_charts held TWO grains: 401,774 legacy weekly rows (2014-2024) and 554,215 "
            "rows of the 2025 timestamped snapshot series appended with a NULL season — the "
            "latter a duplicate of depth_charts_ts. `group by season` over it silently dropped "
            "58% of the table and reported the data as ending in 2024, which is how the scoping "
            "read it as a missing season. depth_charts_all makes the grain an explicit column."
        ),
        "passed": bool(
            unified["season_complete_2014_2025"]
            and casts_ok
            and all(r["match_rate"] is not None for r in rates)
        ),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True, default=str))
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    print(f"\n0.12.7 {'PASS' if result['passed'] else 'FAIL'}")
    return result


if __name__ == "__main__":
    raise SystemExit(0 if main()["passed"] else 1)
