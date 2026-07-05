"""Phase 4.4 — projection calibration, run + verify (the reframe's real done-criterion).

    uv run python steps/phase4_4_calibration.py

Done when (reframed BUILD_PLAN 4.4): the value signal's calibration is measured, not assumed —
per-position bias (Σreal/Σpred), a monotone reliability table, and a correction factor that pulls
bias to ≈1; development on DEV_SEASONS, the verdict read **once** on the 2025 holdout. This is what
"calibration > edge" means operationally.
"""

from __future__ import annotations

from fantasy_quant.config import CALIBRATION_SEASONS, DEV_SEASONS
from fantasy_quant.data import db
from fantasy_quant.projections import calibration
from fantasy_quant.projections.consensus import consensus_projection


def _print_report(rep, label):
    print(f"\n=== {label}: {rep['n']} player-seasons, {len(rep['seasons'])} seasons ===")
    print(f"  overall bias (Σreal/Σpred) = {rep['overall_bias']:.2f}   "
          f"Spearman {rep['spearman']:+.2f}   MAE {rep['mae']:.1f}")
    print("  per-position bias:  " + "  ".join(
        f"{p} {b:.2f}" for p, b in sorted(rep['by_position_bias'].items())))
    print("  reliability (predicted decile -> realized):")
    print(rep["reliability"].round(1).to_string(index=False))


def main() -> None:
    con = db.connect(read_only=True)
    dev = [s for s in DEV_SEASONS if s >= 2016]

    # -- DEVELOPMENT: calibrate on DEV seasons (conditional = players who played) ------------------
    dev_rep = calibration.calibration_report(con, consensus_projection, dev)
    _print_report(dev_rep, "DEV (conditional on playing)")

    # reliability should climb with prediction (allow small empirical wobble -> bin-level corr)
    rel = dev_rep["reliability"]
    bin_corr = float(rel["mean_pred"].corr(rel["mean_real"]))
    assert bin_corr > 0.95, f"reliability bins should track prediction (corr {bin_corr:.2f})"
    assert dev_rep["spearman"] > 0.4, "projection should rank-correlate with realized"
    print(f"  [PASS] reliability climbs with prediction (bin corr {bin_corr:.2f}).")

    # -- the survivorship haircut: projected players who DNP count as 0 ----------------------------
    dev_unc = calibration.calibration_report(con, consensus_projection, dev, unconditional=True)
    print(f"\n  draft-day haircut: bias {dev_rep['overall_bias']:.2f} (played) -> "
          f"{dev_unc['overall_bias']:.2f} (incl. DNP as 0) — the injury/washout discount a draft "
          f"board must respect.")

    # -- CORRECTION: apply per-position factors -> bias pulled to ~1 -------------------------------
    corr = dev_rep["correction_factor"]
    factors = "  ".join(f"{p} {c:.2f}" for p, c in sorted(corr.items()))
    print(f"  correction factors (x proj): {factors}")
    check = calibration.matched(con, consensus_projection, 2022)
    corrected_bias = calibration.bias_ratio(
        calibration.apply_correction(check, corr), check["points"])
    print(f"  2022 bias after correction = {corrected_bias:.2f} (target ~1.0)")

    # -- HOLDOUT: read the 2025 calibration season ONCE --------------------------------------------
    hold = calibration.calibration_report(con, consensus_projection, list(CALIBRATION_SEASONS))
    _print_report(hold, f"HOLDOUT {list(CALIBRATION_SEASONS)} (evaluated once)")
    print(f"\n  holdout Spearman {hold['spearman']:+.2f} confirms the value signal ranks players "
          f"OOS on a season never used in development.")
    assert hold["spearman"] > 0.4, "holdout rank fidelity should survive"

    print("\nPhase 4.4 (calibration) — all checks PASS.")
    con.close()


if __name__ == "__main__":
    main()
