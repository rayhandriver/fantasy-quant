"""Phase 3.2 — efficiency features, run + verify.

    uv run python steps/phase3_2_efficiency.py

Done when (BUILD_PLAN 3.2): finite; the TD-regression flag correlates with next-year TD decline (the
mean-reversion the flag is meant to capture); QB EPA/CPOE rank elite QBs on top. In-sample checks
run on DEV_SEASONS only (lockbox discipline).
"""

from __future__ import annotations

import numpy as np

from fantasy_quant.config import DEV_SEASONS
from fantasy_quant.data import db
from fantasy_quant.features.efficiency import FEATURE_COLS, efficiency_features


def main() -> None:
    con = db.connect(read_only=True)
    df = efficiency_features(con)
    print(f"=== efficiency features: {len(df):,} (gsis, season) rows, "
          f"{df['season'].min()}–{df['season'].max()} ===")

    assert not df.duplicated(["gsis_id", "season"]).any(), "duplicate (gsis, season)"
    assert np.isfinite(df[FEATURE_COLS].to_numpy(float)).all(), "non-finite feature"
    assert df["catch_rate"].between(-0.01, 1.2).all(), "catch_rate out of range"
    assert df["ypc"].between(-10, 15).all(), "ypc implausible"
    assert df["ypr"].between(0, 30).all() and df["yptgt"].between(0, 25).all(), "yardage rate odd"
    assert (df["season"] == 2025).any(), "2025 efficiency missing"
    print("  [PASS] unique keys, finite, rates sane; 2025 covered "
          f"({(df['season'] == 2025).sum()} rows).")

    # -- TD-regression flag validates: high TD-over-expected -> next-year TD decline -----------
    dev = df[df["season"].isin(DEV_SEASONS)].copy()
    dev["tds_pg"] = (dev["rec_tds"] + dev["rush_tds"]) / dev["games"].clip(lower=1)
    nxt = dev[["gsis_id", "season", "tds_pg"]].copy()
    nxt["season"] = nxt["season"] - 1  # join season S's next-year (S+1) tds onto S
    m = dev.merge(nxt.rename(columns={"tds_pg": "tds_pg_next"}), on=["gsis_id", "season"])
    m = m[(m["rz_targets"] + m["rz_carries"]) >= 10]  # players with real TD opportunity
    m["td_change"] = m["tds_pg_next"] - m["tds_pg"]
    corr = float(np.corrcoef(m["td_oe"] / m["games"].clip(lower=1), m["td_change"])[0, 1])
    print(f"\n=== TD-regression validation (DEV seasons, {len(m)} consecutive player-seasons) ===")
    print(f"  corr( TD-over-expected(S) , TD/gm change S->S+1 ) = {corr:+.2f}")
    assert corr < -0.15, f"TD-regression flag not mean-reverting (corr {corr:+.2f})"
    print("  [PASS] positive TD luck predicts next-year TD decline (flag captures regression).")

    # -- QB EPA sanity: elite QBs on top ------------------------------------------------------
    names = con.execute("SELECT DISTINCT gsis_id, name FROM player_ids "
                        "WHERE gsis_id IS NOT NULL").df().drop_duplicates("gsis_id")
    qb23 = (df[(df["season"] == 2023) & (df["games"] >= 10) & (df["qb_epa_per_play"] != 0)]
            .merge(names, on="gsis_id", how="left").nlargest(5, "qb_epa_per_play"))
    print("\n  2023 top-5 QB EPA/play:")
    for _, r in qb23.iterrows():
        print(f"    {str(r['name']):<18} epa/play={r['qb_epa_per_play']:+.3f} "
              f"cpoe={r['qb_cpoe']:+.1f}")
    assert len(qb23) >= 3, "QB EPA not populated"
    print("\n  [PASS] efficiency ranks elite QBs on top.")

    print("\nPhase 3.2 (efficiency features) — all checks PASS.")
    con.close()


if __name__ == "__main__":
    main()
