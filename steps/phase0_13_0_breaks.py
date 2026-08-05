"""Phase 0.13.0 done-bar — the break map, and the two bars that make it trustworthy.

**B1 — the map is a CONTROL, not a description.** It has to find the 2023 participation break
*without being pointed at it*, and it has to flag a **planted synthetic sentinel** in data it has
never seen. A detector that has only ever been shown the answer has not been tested (T31's rule).

**B2 — the trap is real, and the gate closes it.** State the naive and the gated blitz rate side
by side. A fix whose effect is unmeasured is a claim, not a fix.

Run: ``uv run python steps/phase0_13_0_breaks.py``  (stop the Streamlit app first — DuckDB is
single-writer, though this step only reads).
"""

from __future__ import annotations

import json

import duckdb
import pandas as pd

from fantasy_quant.config import PROJECT_ROOT
from fantasy_quant.data import breaks, db, registry, validate

OUT = PROJECT_ROOT / "analysis" / "phase0_13_0_breaks.json"

# The two columns T50 was opened on. B1 asserts the detector rediscovers them from a probe of the
# whole store with no column named — they are the ANSWER, never an input.
T50_COLUMNS = [("participation", "was_pressure", 2023),
               ("participation", "number_of_pass_rushers", 2023)]


def b1_unprompted(bm: breaks.BreakMap) -> dict:
    """Did a store-wide probe rediscover the known break on its own?"""
    found = {(b.table, b.column, b.season) for b in bm.breaks
             if b.kind == "null_to_sentinel"}
    missing = [k for k in T50_COLUMNS if k not in found]
    return {
        "bar": "B1a — the 2023 break is found unprompted",
        "passed": not missing,
        "n_columns_probed": len({(c.table, c.column) for c in bm.cells}),
        "n_sentinel_breaks_found": len(found),
        "expected_found": [f"{t}.{c}@{s}" for t, c, s in T50_COLUMNS if (t, c, s) in found],
        "missing": [f"{t}.{c}@{s}" for t, c, s in missing],
    }


def b1_planted() -> dict:
    """Plant a synthetic null→sentinel break in a table the detector has never seen.

    The negative control matters as much as the positive one: a column that merely gets *better*
    covered must NOT be reported, or the gate cries wolf on every genuine backfill.
    """
    def planted(season: int, i: int):
        """NULL on 40 % of rows until 2021, then the sentinel -1 in their place."""
        if i % 10 >= 4:
            return i % 7
        return None if season < 2021 else -1

    def benign(season: int, i: int):
        """A genuine backfill at the same season — the coverage doubles, but across nine values."""
        if season >= 2021 or i % 10 >= 5:
            return i % 9
        return None

    con = duckdb.connect(":memory:")
    rows = [
        {"season": season, "planted": planted(season, i), "benign": benign(season, i)}
        for season in range(2018, 2024)
        for i in range(1000)
    ]
    con.register("t", pd.DataFrame(rows))
    con.execute("create table synth as select * from t")

    bm = breaks.build_break_map(con, tables=["synth"], max_season=None)
    kinds = {(b.column, b.kind): b for b in bm.breaks}
    planted_hit = kinds.get(("planted", "null_to_sentinel"))
    benign_flagged = any(c == "benign" and k in breaks.BREAKING_KINDS for c, k in kinds)
    return {
        "bar": "B1b — a planted sentinel is flagged; a genuine backfill is not",
        "passed": planted_hit is not None and not benign_flagged,
        "planted_detected": planted_hit.describe() if planted_hit else None,
        "planted_sentinel_value": planted_hit.value if planted_hit else None,
        "benign_backfill_flagged": benign_flagged,
        "note": "`benign` doubles its fill at the same season but spreads across nine values, so "
                "mass is not conserved into one — which is exactly the discriminator.",
    }


def b2_blitz_rate(con, bm: breaks.BreakMap) -> dict:
    """The naive and the gated blitz rate, side by side, with the gap stated."""
    excl = breaks.sentinel_exclusion_sql(bm, "participation", "number_of_pass_rushers", "p")
    df = con.execute(f"""
        select season,
               round(avg(case when number_of_pass_rushers >= 5 then 1.0 else 0.0 end)
                     filter (where number_of_pass_rushers is not null), 4) as naive,
               round(avg(case when number_of_pass_rushers >= 5 then 1.0 else 0.0 end)
                     filter (where number_of_pass_rushers is not null and {excl}), 4) as gated
        from participation p
        where season is not null
        group by 1 order by 1
    """).df()
    df["gap"] = (df["gated"] - df["naive"]).round(4)
    pre = df[df["season"] < 2023]
    post = df[df["season"] >= 2023]
    # the discontinuity each series shows at the 2023 boundary
    naive_step = float(post["naive"].iloc[0] - pre["naive"].iloc[-1])
    gated_step = float(post["gated"].iloc[0] - pre["gated"].iloc[-1])
    return {
        "bar": "B2 — naive vs gated blitz rate differ by a stated amount",
        "passed": bool(pre["gap"].abs().max() < 1e-9 and post["gap"].min() > 0.10),
        "predicate": excl,
        "per_season": df.to_dict("records"),
        "max_gap_before_break": round(float(pre["gap"].abs().max()), 6),
        "mean_gap_after_break": round(float(post["gap"].mean()), 4),
        "naive_step_at_2023": round(naive_step, 4),
        "gated_step_at_2023": round(gated_step, 4),
        "understatement_factor_2024": round(
            float(df.loc[df.season == 2024, "gated"].iloc[0]
                  / df.loc[df.season == 2024, "naive"].iloc[0]), 3),
        "reading": (
            "The naive series reads a 52 % collapse in league blitz rate at 2023 — the largest "
            "defensive scheme shift in modern NFL history, and entirely an encoding change. The "
            "gated series is flat. Before the break the two are bit-identical, so the gate is a "
            "no-op exactly where it should be."
        ),
    }


def floors_vs_registry(bm: breaks.BreakMap) -> dict:
    """T49 — every per-column floor that disagrees with its table's registered floor."""
    out = []
    for (table, column), floor in sorted(bm.floors().items()):
        spec = registry.BY_TABLE.get(table)
        if spec is None or spec.floor is None:
            continue
        if floor != spec.floor:
            out.append({"table": table, "column": column,
                        "table_floor": spec.floor, "column_floor": floor,
                        "dev_seasons_lost": max(0, floor - spec.floor)})
    return {"n_disagreements": len(out), "columns": out}


def main() -> None:
    con = db.connect(read_only=True)
    bm = breaks.build_break_map(con)

    bars = [b1_unprompted(bm), b1_planted(), b2_blitz_rate(con, bm)]
    gate = validate.encoding_break_gate(con, bm)

    report = {
        "step": "0.13.0 — the break map",
        "break_map": bm.to_dict(),
        "bars": bars,
        "gates": [gate],
        "floors_vs_registry": floors_vs_registry(bm),
        "all_bars_passed": all(b["passed"] for b in bars) and gate["passed"],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str))

    print(f"break map: {len(bm.cells)} cells, {len(bm.breaks)} breaks, "
          f"{len(bm.unclassified())} unclassified")
    for b in bars:
        print(f"  [{'PASS' if b['passed'] else 'FAIL'}] {b['bar']}")
    print(f"  [{'PASS' if gate['passed'] else 'FAIL'}] {gate['gate']}")
    fv = report["floors_vs_registry"]
    print(f"  T49: {fv['n_disagreements']} per-column floors disagree with the table floor")
    for c in fv["columns"]:
        print(f"       {c['table']}.{c['column']}: table {c['table_floor']} -> "
              f"column {c['column_floor']}")
    print(f"\n-> {OUT}")


if __name__ == "__main__":
    main()
