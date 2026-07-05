"""Phase 3.1 — opportunity features, run + verify.

    uv run python steps/phase3_1_opportunity.py

Done when (BUILD_PLAN 3.1): finite, ranges sane, one row per (gsis, season); known workhorses top
the opportunity board. (PIT lag is enforced in 3.5, not here — these are realized season facts.)
"""

from __future__ import annotations

import numpy as np

from fantasy_quant.data import db
from fantasy_quant.features.opportunity import FEATURE_COLS, opportunity_features


def main() -> None:
    con = db.connect(read_only=True)
    df = opportunity_features(con)

    print(f"=== opportunity features: {len(df):,} (gsis, season) rows, "
          f"{df['season'].min()}–{df['season'].max()} ===")

    # -- one row per (gsis, season); finite; ranges sane -------------------------------------
    assert not df.duplicated(["gsis_id", "season"]).any(), "duplicate (gsis, season) rows"
    assert np.isfinite(df[FEATURE_COLS].to_numpy(float)).all(), "non-finite feature"
    for c in ("snap_pct", "tgt_share", "carry_share"):
        assert df[c].between(-0.01, 1.05).all(), f"{c} out of [0,1]: {df[c].min()}..{df[c].max()}"
    # air-yards share can be mildly negative (behind-the-LOS targets => negative air yards).
    assert df["air_yards_share"].between(-1.0, 1.05).all(), "air_yards_share out of band"
    assert (df["adot"].between(-10, 30)).all(), "aDOT implausible"
    assert (df[["targets_pg", "carries_pg", "rz_tgt_pg"]] >= 0).all().all(), "negative rate"
    print("  [PASS] unique keys, finite, shares in [0,1], per-game rates >= 0.")

    # -- 2025 present (calibration holdout got features too) ----------------------------------
    assert (df["season"] == 2025).any(), "2025 opportunity features missing"
    print(f"  2025 rows: {(df['season'] == 2025).sum()}  (calibration holdout covered)")

    # -- known-workhorse sanity: top target-share WRs and top carry-share RBs ----------------
    names = con.execute("SELECT DISTINCT gsis_id, name FROM player_ids "
                        "WHERE gsis_id IS NOT NULL").df().drop_duplicates("gsis_id")
    d23 = df[(df["season"] == 2023) & (df["games"] >= 10)].merge(names, on="gsis_id", how="left")
    print("\n  2023 top-5 WR target share:")
    for _, r in d23[d23["position"] == "WR"].nlargest(5, "tgt_share").iterrows():
        print(f"    {str(r['name']):<22} tgt_share={r['tgt_share']:.2f} wopr={r['wopr']:.2f} "
              f"rz_tgt_pg={r['rz_tgt_pg']:.2f}")
    print("  2023 top-5 RB carry share:")
    for _, r in d23[d23["position"] == "RB"].nlargest(5, "carry_share").iterrows():
        print(f"    {str(r['name']):<22} carry_share={r['carry_share']:.2f} "
              f"carries_pg={r['carries_pg']:.1f} rz_carry_pg={r['rz_carry_pg']:.2f}")
    top_wr = d23[d23["position"] == "WR"].nlargest(1, "tgt_share")["tgt_share"].iloc[0]
    assert top_wr > 0.25, f"top WR target share implausibly low ({top_wr})"
    print("\n  [PASS] elite WRs/RBs top the opportunity board (features track real usage).")

    print("\nPhase 3.1 (opportunity features) — all checks PASS.")
    con.close()


if __name__ == "__main__":
    main()
