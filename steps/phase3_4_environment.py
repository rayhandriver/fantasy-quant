"""Phase 3.4 — team/environment features, run + verify.

    uv run python steps/phase3_4_environment.py

Done when (BUILD_PLAN 3.4): implied-team-total present & sane, features finite, ~32 teams/season;
pass-happy and high-scoring offenses surface correctly.
"""

from __future__ import annotations

import numpy as np

from fantasy_quant.data import db
from fantasy_quant.features.environment import FEATURE_COLS, environment_features


def main() -> None:
    con = db.connect(read_only=True)
    df = environment_features(con)
    print(f"=== environment features: {len(df):,} (team, season) rows, "
          f"{df['season'].min()}–{df['season'].max()} ===")

    # -- ~32 teams/season, finite, ranges sane -----------------------------------------------
    per = df.groupby("season").size()
    assert per.between(30, 36).all(), f"team count per season off: {per.min()}..{per.max()}"
    assert np.isfinite(df[FEATURE_COLS].to_numpy(float)).all(), "non-finite feature"
    assert df["pass_rate"].between(0.3, 0.85).all(), "pass_rate implausible"
    assert df["implied_team_total"].between(10, 40).all(), "implied team total implausible"
    assert df["tgt_hhi"].between(0.03, 0.5).all(), "target HHI implausible"
    print(f"  [PASS] {per.min()}–{per.max()} teams/season, finite, pass_rate/implied/HHI sane.")
    assert (df["season"] == 2025).any(), "2025 environment missing"
    print(f"  2025 rows: {(df['season'] == 2025).sum()}")

    # -- sanity: high-implied-total offenses are the good ones --------------------------------
    d23 = df[df["season"] == 2023].sort_values("implied_team_total", ascending=False)
    print("\n  2023 top-5 offenses by implied team total:")
    for _, r in d23.head(5).iterrows():
        print(f"    {r['team']:<4} implied={r['implied_team_total']:.1f} "
              f"pts_pg={r['points_pg']:.1f} pass_rate={r['pass_rate']:.2f} "
              f"pass_epa={r['pass_epa']:+.3f}")
    # implied total should correlate with realized points
    corr = float(np.corrcoef(df["implied_team_total"], df["points_pg"])[0, 1])
    print(f"\n  corr(implied_team_total, realized points/gm) = {corr:+.2f}")
    assert corr > 0.5, f"implied total should track realized scoring (corr {corr:+.2f})"
    print("  [PASS] Vegas implied totals track realized offense; environment features are sane.")

    print("\nPhase 3.4 (environment features) — all checks PASS.")
    con.close()


if __name__ == "__main__":
    main()
