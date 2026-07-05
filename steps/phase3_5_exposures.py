"""Phase 3.5 — the exposure matrix X, run + verify (the capstone; sets up Phases 4-7).

    uv run python steps/phase3_5_exposures.py

Done when (BUILD_PLAN 3.5): finite, mean-centered per position, columns documented, PIT (two target
seasons differ; a planted-future feature trips the guard). Plus **readiness checks**: rookies carry
intrinsic signal without prior production, X aligns with the draftable ADP board, and lagged
features carry real predictive signal for next-season points (so Phase 4/5 have something to model).
"""

from __future__ import annotations

import numpy as np

from fantasy_quant.backtest import scoring
from fantasy_quant.config import DEV_SEASONS
from fantasy_quant.data import db
from fantasy_quant.features.exposures import (
    FEATURE_MANIFEST,
    assert_exposures_pit,
    build_exposures,
)


def main() -> None:
    con = db.connect(read_only=True)

    X = build_exposures(con, 2023)
    print(f"=== exposure matrix X (target 2023): {len(X)} players x "
          f"{len(FEATURE_MANIFEST)} features ===")
    print(f"  positions: {X['position'].value_counts().to_dict()}")

    # -- finite, unique, mean-centered per position (z-scores) --------------------------------
    feat = X[FEATURE_MANIFEST].to_numpy(float)
    assert np.isfinite(feat).all(), "non-finite in X"
    assert not X.duplicated("gsis_id").any(), "duplicate players"
    zcols = [c for c in FEATURE_MANIFEST if c.endswith("_z")]
    means = X.groupby("position")[zcols].mean().abs().to_numpy()
    assert (means < 0.05).all(), f"z-scores not mean-centered (max |mean| {means.max():.3f})"
    print(f"  [PASS] finite, unique gsis, {len(zcols)} z-features mean-centered within position.")

    # -- PIT: two target seasons differ; the guard rejects a same/future production season ----
    X22 = build_exposures(con, 2022)
    same = set(X["gsis_id"]) == set(X22["gsis_id"])
    assert not same, "2022 and 2023 universes identical (suspicious)"
    tripped = False
    try:
        assert_exposures_pit(2023, 2023, 2023)  # production season == target -> must trip
    except AssertionError:
        tripped = True
    assert tripped, "PIT guard failed to reject a non-lagged production season"
    print("  [PASS] target seasons differ; PIT guard rejects production/env dated >= target.")

    # -- rookie readiness: rookies present, flagged no_prior, carrying intrinsic signal -------
    rk = X[(X["is_rookie"] == 1)]
    assert len(rk) > 20, "too few rookies in the 2023 matrix"
    assert (rk["no_prior"] == 1).mean() > 0.8, "rookies should mostly have no prior production"
    # rookies must have non-trivial intrinsic (draft capital) exposure, not all-zero
    assert rk["draft_ovr_z"].abs().sum() > 0, "rookie draft-capital signal is flat"
    print(f"  [PASS] {len(rk)} rookies flagged (no_prior) with live intrinsic signal.")

    # -- alignment: X covers the draftable ADP board (Phase 9 optimizer / Phase 6 will join it) --
    board = con.execute(
        "SELECT DISTINCT gsis_id FROM adp_snapshots WHERE season=2023 AND source='ffc' "
        "AND scoring='ppr' AND teams=10 AND adp<=150 AND gsis_id IS NOT NULL "
        "AND position IN ('QB','RB','WR','TE')"
    ).df()
    covered = board["gsis_id"].isin(set(X["gsis_id"])).mean()
    print(f"\n  draftable ADP board (top-150 skill) covered by X: {covered:.0%}")
    assert covered > 0.85, f"X misses too much of the draft board ({covered:.0%})"

    # -- SIGNAL readiness: lagged features predict next-season points (Phase 4/5 have signal) --
    rows = []
    for s in [yr for yr in DEV_SEASONS if yr >= 2016]:
        Xs = build_exposures(con, s)
        pts = scoring.season_points(con, s)[["gsis_id", "points"]]
        m = Xs.merge(pts, on="gsis_id", how="inner")
        rows.append(m)
    import pandas as pd
    allm = pd.concat(rows, ignore_index=True)
    c_wopr = float(np.corrcoef(allm["wopr_z"], allm["points"])[0, 1])
    c_ay = float(np.corrcoef(allm["air_yards_share_z"], allm["points"])[0, 1])
    print(f"  corr(lagged WOPR_z, next-season points) = {c_wopr:+.2f}  "
          f"(pooled {len(allm):,} DEV player-seasons)")
    print(f"  corr(lagged air-yards-share_z, next-season points) = {c_ay:+.2f}")
    assert c_wopr > 0.3, f"lagged opportunity should predict next-year points (got {c_wopr:+.2f})"
    print("  [PASS] lagged exposures carry real predictive signal for Phase 4/5.")

    # -- 2025 calibration holdout builds too --------------------------------------------------
    X25 = build_exposures(con, 2025)
    assert len(X25) > 200 and np.isfinite(X25[FEATURE_MANIFEST].to_numpy(float)).all()
    print(f"\n  2025 (calibration holdout) matrix builds: {len(X25)} players, finite.")

    print("\nPhase 3.5 (exposure matrix X) — all checks PASS. Phase 3 COMPLETE; X ready.")
    con.close()


if __name__ == "__main__":
    main()
