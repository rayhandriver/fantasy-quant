"""Session DATA-1 / 0.12.8 — gates, PIT classes, backup (**B6 · B7**).

    uv run python steps/phase0_12_8_gates.py
    uv run python steps/phase0_12_8_gates.py --rebaseline   # re-record the fill-rate baseline

* **B6 — the floors are asserted, not documented.** A request for FTN 2019 or participation 2014
  **raises, naming the floor**. Proven by making it raise, and by proving it does *not* raise on a
  legal request — a guard that always throws is not a guard.
* **B7 — PIT classes hold.** A ``retrospective`` table, or an unlagged ``in_season_weekly`` one,
  routed at a draft feature **fails**. Written as a check that *can* fail and verified by making
  it fail; the legal cases are checked too, for the same reason as B6.

Plus: the per-table coverage gate, the registry completeness gate, and the fill-rate gate — the
last of which is the one that would have caught ``ngs_air_yards`` silently going to zero in 2023.

Writes ``analysis/phase0_12_8_gates.json`` and ``analysis/fill_rate_baseline.json``.
"""

from __future__ import annotations

import argparse
import json

from fantasy_quant.config import PROJECT_ROOT
from fantasy_quant.data import db, registry, validate
from fantasy_quant.data.sources import nflverse_release as nr

OUT_JSON = PROJECT_ROOT / "analysis" / "phase0_12_8_gates.json"


def b6_floors() -> dict:
    """Floor assertions raise below the floor and stay quiet above it."""
    cases = []
    for tag, season, should_raise in [
        ("ftn_charting", 2019, True),
        ("ftn_charting", 2022, False),
        ("pbp_participation", 2014, True),
        ("pbp_participation", 2016, False),
        ("pfr_advstats", 2017, True),
        ("pfr_advstats", 2018, False),
    ]:
        try:
            nr.assert_season_floor(tag, [season])
            raised, msg = False, None
        except ValueError as e:
            raised, msg = True, str(e)
        cases.append({
            "tag": tag, "season": season, "expected_raise": should_raise,
            "raised": raised, "ok": raised == should_raise,
            "names_the_floor": bool(msg and str(nr.SEASON_FLOORS[tag]) in msg),
        })
    return {
        "bar": "B6 — the floors are asserted, not documented",
        "passed": all(c["ok"] for c in cases)
        and all(c["names_the_floor"] for c in cases if c["raised"]),
        "cases": cases,
    }


def b7_pit_classes() -> dict:
    """A retrospective or unlagged in-season table cannot feed a draft feature."""
    cases = []
    for table, lagged, should_raise in [
        ("qbr_season", True, True),        # retrospective — illegal even lagged
        ("seasonal", False, True),         # retrospective
        ("participation", False, True),    # in_season_weekly, unlagged — leaks
        ("participation", True, False),    # in_season_weekly through the t-1 lag — legal
        ("schedules", False, False),       # preseason — legal
        ("combine", False, False),         # preseason — legal
    ]:
        try:
            registry.assert_pit_class_for_draft_feature(table, lagged=lagged)
            raised = False
        except ValueError:
            raised = True
        cases.append({
            "table": table, "pit_class": registry.spec(table).pit_class, "lagged": lagged,
            "expected_raise": should_raise, "raised": raised, "ok": raised == should_raise,
        })

    # backtestable=False is an assertion too, not a label (FTN's one DEV season)
    try:
        registry.assert_backtestable("ftn_charting")
        ftn_raised = False
    except ValueError:
        ftn_raised = True
    try:
        registry.assert_backtestable("weekly")
        weekly_raised = False
    except ValueError:
        weekly_raised = True

    # an undeclared table must raise rather than default to something permissive
    try:
        registry.spec("a_table_that_does_not_exist")
        undeclared_raised = False
    except KeyError:
        undeclared_raised = True

    return {
        "bar": "B7 — PIT classes hold",
        "passed": (
            all(c["ok"] for c in cases)
            and ftn_raised and not weekly_raised and undeclared_raised
        ),
        "cases": cases,
        "backtestable_assertion": {
            "ftn_charting_raises": ftn_raised,
            "weekly_does_not_raise": not weekly_raised,
        },
        "undeclared_table_raises": undeclared_raised,
    }


def main(rebaseline: bool = False) -> dict:
    con = db.connect()

    coverage = [
        validate.coverage_gate(con, s.table, s.expected_seasons)
        for s in registry.REGISTRY if s.expected_seasons
    ]
    reg_gate = validate.registry_gate(con)

    current = validate.store_fill_rates(con)
    baseline_path = validate.FILL_RATE_BASELINE
    baseline = (
        json.loads(baseline_path.read_text())
        if baseline_path.exists() and not rebaseline else None
    )
    fr_gate = validate.fill_rate_gate(con, current, baseline)
    if rebaseline or not baseline_path.exists():
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(json.dumps(current, indent=2, sort_keys=True))

    b6, b7 = b6_floors(), b7_pit_classes()

    # the store roughly doubled; T2's discipline says the irreplaceable half gets backed up
    sizes = con.execute(
        "select sum(estimated_size) from duckdb_tables()"
    ).fetchone()[0]

    result = {
        "substep": "0.12.8",
        "B6": b6,
        "B7": b7,
        "coverage_gates": coverage,
        "coverage_all_pass": all(g["passed"] for g in coverage),
        "registry_gate": reg_gate,
        "fill_rate_gate": fr_gate,
        "fill_rate_baseline_written": rebaseline or baseline is None,
        "estimated_store_rows": int(sizes or 0),
        "passed": bool(
            b6["passed"] and b7["passed"]
            and all(g["passed"] for g in coverage)
            and reg_gate["passed"] and fr_gate["passed"]
        ),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True, default=str))

    print(f"B6 {'PASS' if b6['passed'] else 'FAIL'}  floors asserted")
    print(f"B7 {'PASS' if b7['passed'] else 'FAIL'}  PIT classes hold")
    print(f"   coverage gates: {sum(g['passed'] for g in coverage)}/{len(coverage)} pass")
    for g in coverage:
        if not g["passed"]:
            print("     FAIL", json.dumps(g))
    print("   registry:", json.dumps(reg_gate))
    print("   fill rate:", json.dumps(fr_gate)[:600])
    print(f"\n0.12.8 {'PASS' if result['passed'] else 'FAIL'}")
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebaseline", action="store_true")
    a = ap.parse_args()
    raise SystemExit(0 if main(rebaseline=a.rebaseline)["passed"] else 1)
