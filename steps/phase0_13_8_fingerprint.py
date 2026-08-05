"""Phase 0.13.8 done-bar — the defensive fingerprint and the widened offensive one.

T48 closes here: the apparatus that had no defensive counterpart to run on now runs on one. The
bars are structural, not predictive — this is **descriptive only**, so there is no FDR gate and no
edge claim, and ``assert_not_wired_into_the_optimizer`` is what makes that a fact rather than a
sentence.
"""

from __future__ import annotations

import json
from pathlib import Path

from fantasy_quant.data import db
from fantasy_quant.situation import defense_fingerprint as dfp
from fantasy_quant.situation import fingerprint

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis" / "phase0_13_8_fingerprint.json"


def main() -> None:
    con = db.connect()

    d_fp, d_rp, d_k = dfp.build_defense_fingerprints(con)
    o_fp, o_rp, o_k = dfp.build_offense_scheme_fingerprints(con)

    panel_floor = int(con.execute(
        f"select min(season) from {dfp.PANEL_TABLE}").fetchone()[0])
    dfp.assert_regime_coverage(d_rp, panel_floor)
    dfp.assert_regime_coverage(o_rp, panel_floor)
    fingerprint.assert_fingerprints_sane(d_fp, dfp.DEFENSE_METRICS)
    fingerprint.assert_fingerprints_sane(o_fp, dfp.OFFENSE_SCHEME_METRICS)
    dfp.assert_not_wired_into_the_optimizer()

    cov = dfp.coverage_report(d_rp)

    # ★ the shrinkage weights ARE the honesty of the table: a one-season coordinator should sit
    # near the league mean, and a long tenure should be nearly raw. Reported per metric so the
    # 2018-floor coverage metrics can be seen shrinking harder than the 2016-floor front metrics.
    shrink = {
        "defense": {m: round(float(d_k[m]), 3) for m in dfp.DEFENSE_METRICS},
        "offense_scheme": {m: round(float(o_k[m]), 3) for m in dfp.OFFENSE_SCHEME_METRICS},
    }
    weight_at_n = {
        m: {f"n={n}": round(n / (n + d_k[m]), 3) for n in (1, 3, 6)}
        for m in ("blitz_rate", "man_share", "share_nickel", "proxy_two_high_share")
    }

    # the most and least distinctive defensive play-callers on the shrunk vector
    d_fp = d_fp.copy()
    d_fp["distinctiveness"] = d_fp[list(dfp.DEFENSE_METRICS)].abs().mean(axis=1)
    top = d_fp.nlargest(8, "distinctiveness")[
        ["play_caller", "n_seasons", "teams", "distinctiveness",
         "blitz_rate", "man_share", "share_nickel", "box_mean"]]

    out = {
        "step": "0.13.8 — the fingerprint, extended to defense",
        "defense": {
            "n_play_callers": int(len(d_fp)),
            "n_regime_seasons": int((~d_rp["dropped"]).sum()),
            "dropped": int(d_rp["dropped"].sum()),
            "drop_reasons": sorted(set(d_rp.loc[d_rp["dropped"], "drop_reason"])),
            "panel_floor": panel_floor,
            "n_metrics": len(dfp.DEFENSE_METRICS),
        },
        "offense_scheme": {
            "n_play_callers": int(len(o_fp)),
            "n_regime_seasons": int((~o_rp["dropped"]).sum()),
            "dropped": int(o_rp["dropped"].sum()),
            "n_metrics": len(dfp.OFFENSE_SCHEME_METRICS),
            "note": "additive to fingerprint.METRICS' 14, which stay exactly as they were",
        },
        "shrinkage_k": shrink,
        "weight_by_regime_length": weight_at_n,
        "coverage": cov.head(40).to_dict("records"),
        "coordinators_with_one_season": cov[cov["n_seasons"] == 1]["play_caller"].tolist(),
        "most_distinctive": top.round(3).to_dict("records"),
        "descriptive_only": (
            "no FDR gate, no backtested-edge claim, not imported by draft/optimizer.py, "
            "valuation/value_board.py or valuation/cost_report.py — asserted, not stated"
        ),
    }
    ANALYSIS.write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(json.dumps({k: out[k] for k in
                      ("defense", "offense_scheme", "weight_by_regime_length",
                       "coordinators_with_one_season", "most_distinctive")},
                     indent=2, default=str))


if __name__ == "__main__":
    main()
