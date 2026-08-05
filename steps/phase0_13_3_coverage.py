"""Phase 0.13.3 done-bar — coverage shells, the secondary proxy, and the floor that must raise."""

from __future__ import annotations

import json
from pathlib import Path

from fantasy_quant.data import breaks, db
from fantasy_quant.situation import coverage as cov

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis" / "phase0_13_3_coverage.json"


def main() -> None:
    con = db.connect()
    bm = breaks.build_break_map(con, tables=["participation"])
    built = cov.build_coverage_week(con, bm)

    per_season = con.execute(f"""
        select season,
               round(avg(charted_share), 4)            as charted_share,
               round(avg(share_cover_1), 4)            as cover1,
               round(avg(share_cover_3), 4)            as cover3,
               round(avg(share_cover_2), 4)            as cover2,
               round(avg(proxy_safeties_mean), 3)      as safeties_mean,
               round(avg(proxy_single_high_share), 4)  as single_high,
               round(avg(proxy_two_high_share), 4)     as two_high,
               round(avg(proxy_unresolved_share), 4)   as unresolved,
               mode(safety_provenance)                 as provenance
        from {cov.COVERAGE_WEEK_TABLE} group by 1 order by 1
    """).df()

    # B6 — the floor is asserted, not documented: a 2016 request must RAISE and name 2018.
    floor_raises = False
    try:
        cov.assert_shell_floor(2016, bm)
    except ValueError as exc:
        floor_raises = "2018" in str(exc)
    floor_allows_2018 = True
    try:
        cov.assert_shell_floor(2018, bm)
    except ValueError:
        floor_allows_2018 = False

    shells_before_floor = int(con.execute(f"""
        select count(*) from {cov.COVERAGE_WEEK_TABLE}
        where season < 2018 and charted_snaps > 0""").fetchone()[0])

    out = {
        "step": "0.13.3 — coverage shells and the secondary",
        "table": built,
        "tier1_charted": {
            "floor": built["charted_floor"],
            "rows_with_shells_before_floor": shells_before_floor,
            "B6_floor_raises_naming_2018": floor_raises,
            "B6_floor_allows_its_own_floor_season": floor_allows_2018,
        },
        "tier2_proxy": {
            "provenance_by_era": con.execute(f"""
                select safety_provenance, min(season) lo, max(season) hi, count(*) team_weeks
                from {cov.COVERAGE_WEEK_TABLE} group by 1 order by 3
            """).df().to_dict("records"),
            "note": "a PERSONNEL proxy: who was on the field, never where he lined up",
            "validated_against_charted": cov.validate_proxy_against_charted(con)
                                            .to_dict("records"),
        },
        "tier3_not_obtainable_free": list(cov.NOT_OBTAINABLE_FREE),
        "per_season": per_season.to_dict("records"),
    }
    ANALYSIS.write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(json.dumps({k: out[k] for k in
                      ("table", "tier1_charted", "tier2_proxy", "tier3_not_obtainable_free")},
                     indent=2, default=str))
    print(per_season.to_string())


if __name__ == "__main__":
    main()
