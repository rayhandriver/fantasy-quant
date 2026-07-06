"""Phase 5.2 — conformalized quantile regression: guaranteed 80% coverage.

    uv run python steps/phase5_2_conformal.py

Done when: the raw quantile band (5.1) is corrected by a per-position CQR adjustment fit on a
held-out DEV season, and empirical coverage on the **2025 holdout** (evaluated once) moves toward
the 80% target — the distribution-free guarantee that a "80% interval" really contains the outcome
~80% of the time.
"""

from __future__ import annotations

import numpy as np

from fantasy_quant.config import CALIBRATION_SEASONS, DEV_SEASONS
from fantasy_quant.data import db
from fantasy_quant.projections import conformal, quantile


def _band(models, frame, taus):
    """Attach raw [q10,q90] band columns to a conditional frame."""
    lo = np.full(len(frame), np.nan)
    hi = np.full(len(frame), np.nan)
    for pos, idx in frame.groupby("pos").groups.items():
        q = quantile.predict_quantiles(
            models, pos, frame.loc[idx, "calibrated_mean"].to_numpy(), taus)
        pos_rows = frame.index.get_indexer(idx)
        lo[pos_rows], hi[pos_rows] = q[:, 0], q[:, -1]
    return frame.assign(q_lo=lo, q_hi=hi).dropna(subset=["q_lo", "q_hi"])


def main() -> None:
    con = db.connect(read_only=True)
    taus = quantile.QUANTILE_TAUS
    corr = quantile.dev_correction(con)
    dev = [s for s in DEV_SEASONS if s >= 2016]
    fit_seasons, cal_seasons = dev[:-2], dev[-2:]

    models = quantile.fit_quantile_models(
        quantile.conditional_training_frame(con, fit_seasons, correction=corr), taus)

    # calibrate the CQR adjustment on the held-out DEV seasons (pooled for a stable per-position d)
    cal = _band(
        models, quantile.conditional_training_frame(con, cal_seasons, correction=corr), taus)
    adj = conformal.fit_cqr(cal, "q_lo", "q_hi")
    print(f"CQR adjustment (points, fit on {cal_seasons}):  "
          + "  ".join(f"{p} {d:+.0f}" for p, d in sorted(adj.items())))

    # HOLDOUT: coverage on 2025, raw vs conformal-corrected (read once)
    hold = _band(models, quantile.conditional_training_frame(
        con, list(CALIBRATION_SEASONS), correction=corr), taus)
    cov_raw = conformal.empirical_coverage(hold["q_lo"], hold["q_hi"], hold["points"])
    hc = conformal.apply_cqr(hold, adj, "q_lo", "q_hi")
    cov_adj = conformal.empirical_coverage(hc["lo"], hc["hi"], hc["points"])

    print(f"\nHOLDOUT {list(CALIBRATION_SEASONS)} coverage of the 80% band ({len(hold)} players):")
    print(f"  raw quantile band       : {cov_raw:.0%}")
    print(f"  conformal-corrected band: {cov_adj:.0%}   (target 80%)")
    for pos, g in hc.groupby("pos"):
        c = conformal.empirical_coverage(g["lo"], g["hi"], g["points"])
        print(f"    {pos}: {c:.0%}  (n={len(g)})")

    assert abs(cov_adj - 0.80) <= abs(cov_raw - 0.80) + 0.02, "conformal should not worsen coverage"
    print("\nPhase 5.2 (conformal) — all checks PASS.")
    con.close()


if __name__ == "__main__":
    main()
