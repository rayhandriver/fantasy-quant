"""Phase 7 runner — opportunity-adjusted projection: fit, validate, keep-or-drop.

    uv run python steps/phase7_opportunity.py

Fits the skill÷opportunity decomposition (7.1) walk-forward, re-projects role-changers (7.2),
transports rookies (7.3), and evaluates everything strictly out-of-sample on DEV seasons (7.4),
ending in the KEEP/DROP verdict against the as-written bar. Writes a scorecard to analysis/.
"""

from __future__ import annotations

import json
from pathlib import Path

from fantasy_quant.causal.validate import walk_forward_validation
from fantasy_quant.data.db import connect

OUT = Path("analysis/phase7_opportunity.json")


def main() -> None:
    con = connect(read_only=True)
    print("Walk-forward validation on DEV seasons (fit<S, score S) ...")
    res = walk_forward_validation(con, n_boot=1000, seed=0)
    con.close()

    ov, mv, st, rk, vd = (res[k] for k in
                          ("overall", "movers", "skill_travels", "rookie", "verdict"))
    print("\n[7.1] Does skill travel across moves?")
    print(f"  movers={st['n_movers']}  corr(skill, realized)={st['corr_skill_vs_realized']:+.3f}  "
          f"vs corr(prior-rate, realized)={st['corr_priorrate_vs_realized']:+.3f}  "
          f"-> skill more stable: {st['skill_more_stable']}")

    print("\n[7.2/7.4] Re-projection error on ROLE-CHANGERS (ppg MAE, lower better):")
    print(f"  movers n={mv['n']}  opp={mv['opp_mae']:.3f}  naive={mv['naive_mae']:.3f}  "
          f"market={mv['market_mae']:.3f}")
    print(f"  opp vs naive gain {mv['opp_vs_naive_gain']:+.3f}  "
          f"CI[{mv['opp_vs_naive_ci'][0]:+.3f},{mv['opp_vs_naive_ci'][1]:+.3f}]")
    if "opp_vs_market_gain" in mv:
        print(f"  opp vs market gain {mv['opp_vs_market_gain']:+.3f}  "
              f"CI[{mv['opp_vs_market_ci'][0]:+.3f},{mv['opp_vs_market_ci'][1]:+.3f}]")

    print("\n[overall calibration] all returning players (ppg MAE):")
    print(f"  n={ov['n']}  opp={ov['opp_mae']:.3f}  naive={ov['naive_mae']:.3f}  "
          f"market={ov['market_mae']:.3f}")
    print(f"  opp vs market gain {ov['opp_minus_market_gain']:+.3f}  "
          f"CI[{ov['opp_minus_market_ci'][0]:+.3f},{ov['opp_minus_market_ci'][1]:+.3f}]")

    print("\n[7.3] Rookie transport (held-out classes):")
    print(f"  n={rk['n']}  1σ coverage={rk['interval_coverage_1sigma']:.3f} (target ≈0.68)  "
          f"Spearman(pred,real)={rk['spearman_pred_vs_real']:+.3f}")

    print("\n==== KEEP-OR-DROP VERDICT ====")
    print(f"  overall not worse than market: {vd['overall_not_worse_than_market']}")
    print(f"  movers strictly beat naive:    {vd['movers_strictly_beat_naive']}")
    print(f"  >>> {'KEEP' if vd['KEEP'] else 'DROP'} <<<")
    print(f"  {vd['rationale']}")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2, default=float))
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
