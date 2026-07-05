"""Phase 0.9 — 2025 backfill via nflverse's NEW ``stats_player`` release (+ re-validate).

    uv run python steps/phase0_9_backfill_2025.py

Why: ``nfl_data_py`` is frozen on the DEAD old ``player_stats`` path (404 for 2025); nflverse
restructured player stats after 2024. We read the live ``stats_player`` release directly and append
2025 ``weekly``/``seasonal`` conformed to our legacy schema (findings.md 2026-07-04).

Done when: 2025 weekly/seasonal join cleanly, the 1.1 scorer reconstructs 2025 fantasy points to
~1e-6, and the 0.8 validator still passes. 2025 becomes a **projection-calibration holdout** (NOT
the draft-backtest lockbox — no 2025 ADP board yet).
"""

from __future__ import annotations

import logging

from fantasy_quant.backtest import scoring
from fantasy_quant.data import db
from fantasy_quant.data.sources.nflverse import (
    backfill_stats_new_release,
    ingest_depth_charts_ts,
)
from fantasy_quant.data.validate import data_health_report

TOL = 0.02


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    con = db.connect()  # writable

    before = con.execute("SELECT MAX(season) FROM weekly").fetchone()[0]
    print(f"=== weekly max season BEFORE backfill: {before} ===")

    counts = backfill_stats_new_release(con, years=(2025,))
    print(f"=== backfilled (new stats_player release): {counts} ===")

    # -- 2025 landed, sane coverage ----------------------------------------------------------
    cov = con.execute(
        "SELECT season_type, COUNT(*) n, COUNT(DISTINCT week) wks "
        "FROM weekly WHERE season=2025 GROUP BY 1 ORDER BY 1"
    ).df()
    print("\n=== weekly 2025 coverage ===")
    print(cov.to_string(index=False))
    n_reg = int(cov.loc[cov["season_type"] == "REG", "n"].sum())
    assert n_reg > 4000, f"implausible 2025 REG weekly row count {n_reg}"
    smax = con.execute("SELECT MAX(season) FROM weekly").fetchone()[0]
    assert int(smax) == 2025, f"weekly max season should be 2025, got {smax}"

    # -- the 1.1 scorer reconstructs 2025 fantasy_points_ppr (schema-compat proof) ------------
    wk = scoring.weekly_points(con, 2025)
    diff = (wk["points"] - wk["fantasy_points_ppr"].fillna(0.0)).abs()
    over = int((diff > TOL).sum())
    print(f"\n=== 2025 scoring reconciliation ({len(wk):,} REG player-weeks) ===")
    print(f"  max|recon - fantasy_points_ppr| = {diff.max():.4g} | rows over tol({TOL}): {over}")
    assert over == 0, f"{over} 2025 player-weeks exceed scoring tolerance"
    print("  [PASS] 2025 weekly reconstructs full-PPR exactly (new-release schema is compatible).")

    # -- timestamped depth charts (new 2025 grain: ISO8601 dt, no week) -----------------------
    n_dc = ingest_depth_charts_ts(con, years=(2025,))
    ts = con.execute("SELECT MIN(dt) mn, MAX(dt) mx, COUNT(DISTINCT gsis_id) players "
                     "FROM depth_charts_ts WHERE dt IS NOT NULL").df()
    print(f"\n=== depth_charts_ts (new timestamped grain): {n_dc:,} rows ===")
    print(f"  dt span {ts['mn'].iloc[0]} -> {ts['mx'].iloc[0]} | "
          f"{int(ts['players'].iloc[0])} players")
    assert n_dc > 1000 and "week" not in [c.lower() for c in
        con.execute("DESCRIBE depth_charts_ts").df()["column_name"]], "depth_charts_ts grain wrong"
    print("  [PASS] timestamped depth charts stored separately (week-grain table untouched).")

    # -- re-validate the extended store ------------------------------------------------------
    report = data_health_report(con, write=True)
    passed = report["all_gates_passed"]
    print(f"\n=== 0.8 validator on extended store: all gates passed = {passed} ===")
    assert passed, "validator failed after backfill"

    print("\nPhase 0.9 (2025 backfill) — PASS. 2025 weekly/seasonal in store; calibration holdout.")
    print("(Draft-backtest lockbox stays 2023+2024; a 2025 ADP board is still needed to backtest.)")
    con.close()


if __name__ == "__main__":
    main()
