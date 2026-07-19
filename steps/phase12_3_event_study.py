"""Phase 12.3 runner — event study (the documented impact/lag per news type).

    uv run python steps/phase12_3_event_study.py

Measures, on the historical structured feeds, how much a news event moves the production it
predicts:
the per-status injury impact + the exploitable lag a stale set-and-forget lineup loses, and the
depth-chart promotion/demotion production change. Verdict per sub-signal (the 12.4 gate then
confirms):
the **injury signal is large and directional** (keep); the **depth-chart signal does not separate**
(drop).
Writes a scorecard to analysis/.
"""

from __future__ import annotations

import json
from pathlib import Path

from fantasy_quant.data.db import connect
from fantasy_quant.news import event_study
from fantasy_quant.valuation.cost_validation import VALIDATION_SEASONS

OUT = Path("analysis/phase12_event_study.json")


def main() -> None:
    seasons = list(VALIDATION_SEASONS)
    con = connect(read_only=True)

    print(f"=== Phase 12.3 injury event study ({seasons}) ===")
    inj = event_study.injury_impact(con, seasons, n_boot=2000)
    print(f"  {inj['n_events']} designations")
    print(f"  {'status':14} {'n':>5} {'play%':>6} {'mean_pts':>8} {'baseline':>8} "
          f"{'exp_loss (CI)':>20}")
    for st, d in sorted(inj["per_status"].items(), key=lambda kv: -kv[1]["expected_loss"]):
        lo, hi = d["expected_loss_ci"]
        print(f"  {st:14} {d['n']:>5} {d['play_rate']:>6.2f} {d['mean_points']:>8.2f} "
              f"{d['baseline_points']:>8.2f} {d['expected_loss']:>+6.2f} [{lo:>+5.2f},{hi:>+5.2f}]")
    elo, ehi = inj["exploitable_loss_ci"]
    print(f"  → exploitable lag (Out/Doubtful/Q) = {inj['exploitable_loss']:+.2f} pts/start "
          f"CI[{elo:+.2f},{ehi:+.2f}]  significant={inj['exploitable_significant']}")

    print(f"\n=== Phase 12.3 depth-chart event study ({seasons}) ===")
    dep = event_study.depth_impact(con, seasons, n_boot=2000)
    for status in ("promotion", "demotion"):
        d = dep[status]
        lo, hi = d["change_ci"]
        print(f"  {status:10} n={d['n']:>5} before→after Δ = {d['mean_change']:+.2f} "
              f"CI[{lo:+.2f},{hi:+.2f}]")
    print(f"  → separation = {dep['separation']:+.2f}  directional={dep['directional']}")
    con.close()

    inj_keep = bool(inj["exploitable_significant"])
    dep_keep = bool(dep["directional"] and dep["separation"] > 0.5)
    print("\n==== 12.3 VERDICT ====")
    print(f"  injury signal: {'KEEP' if inj_keep else 'drop'} "
          f"(large, significant exploitable lag → 12.4 gates the decision use)")
    print(f"  depth signal : {'keep' if dep_keep else 'DROP'} "
          f"(no directional separation — noisy nflverse depth ranks; the gate doing its job)")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"seasons": seasons, "injury": inj, "depth": dep,
                               "injury_keep": inj_keep, "depth_keep": dep_keep},
                              indent=2, default=float))
    print(f"\nWrote {OUT}")
    assert inj_keep, "injury event study should show a significant exploitable lag"


if __name__ == "__main__":
    main()
