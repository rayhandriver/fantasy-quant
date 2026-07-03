"""Phase 0.8 — data validation & sanity gates, run + verify (last step of Phase 0).

    uv run python steps/phase0_8_validate.py

Done when: the store passes all hard gates (or fails loudly), the panel validates, and a
committed data_health.json is written (BUILD_PLAN.md 0.8).
"""

from __future__ import annotations

import logging

from fantasy_quant.data import db
from fantasy_quant.data.panel import weekly_panel
from fantasy_quant.data.validate import HEALTH_JSON, data_health_report, validate_panel


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    con = db.connect()

    report = data_health_report(con, write=True)

    print("=== store-wide gates ===")
    for g in report["gates"]:
        flag = "PASS" if g["passed"] else "FAIL"
        detail = {k: v for k, v in g.items() if k not in ("gate", "passed")}
        print(f"  [{flag}] {g['gate']:<45} {detail}")
    print(f"\n  all gates passed: {report['all_gates_passed']}")

    print("\n=== coverage (% non-null) ===")
    for table, cols in report["coverage"].items():
        print(f"  {table}: {cols}")

    print("\n=== survivorship (documented limitation) ===")
    sv = report["survivorship"]
    print(f"  {season_line(sv)}")
    print(f"  weekly gsis not in player_ids: {sv['weekly_gsis_not_in_player_ids']}")
    print(f"  e.g. drafted-but-DNP {sv['season_examined']}: "
          f"{[e['name'] for e in sv['examples'][:5]]}")

    print("\n=== panel hard-gate (2022 weekly, full season) ===")
    panel = weekly_panel(con, 2022, "2023-02-15")
    validate_panel(panel, "2023-02-15")
    print(f"  validated {len(panel):,} rows -> PASS")

    rel = HEALTH_JSON.relative_to(HEALTH_JSON.parents[2])
    print(f"\n=== data_health.json written -> {rel} ===")
    print("Phase 0 (data foundation) COMPLETE." if report["all_gates_passed"]
          else "GATES FAILED — see report.")
    con.close()


def season_line(sv: dict) -> str:
    return (f"season {sv['season_examined']}: {sv['drafted_top150_no_weekly_appearance']} "
            f"top-150 ADP players had no weekly appearance (injury/cut/bust)")


if __name__ == "__main__":
    main()
