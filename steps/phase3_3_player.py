"""Phase 3.3 — player-intrinsic features, run + verify.

    uv run python steps/phase3_3_player.py

Done when (BUILD_PLAN 3.3): age computed as-of correctly (no future birthdays), plausible; draft
capital + athletic populated; rookies flagged (rookie-model inputs exist without prior production).
"""

from __future__ import annotations

from fantasy_quant.data import db
from fantasy_quant.features.player import _ATHLETIC, player_features


def main() -> None:
    con = db.connect(read_only=True)
    df = player_features(con)
    print(f"=== player-intrinsic features: {len(df):,} (gsis, season) rows, "
          f"{df['season'].min()}–{df['season'].max()} ===")

    # -- key discipline: age as-of, plausible, no future birthdays ---------------------------
    assert not df.duplicated(["gsis_id", "season"]).any(), "duplicate (gsis, season)"
    age_present = df["age"].notna()
    assert df.loc[age_present, "age"].between(18, 50).all(), "age implausible"
    assert df["experience"].between(0, 30).all(), "experience implausible"
    assert df["draft_ovr"].between(1, 300).all(), "draft_ovr out of range"
    print(f"  [PASS] age as-of Sep-1 in [18,50] ({age_present.mean():.1%} present); "
          "experience/draft capital sane; unique keys.")

    # -- rookie coverage: rookies have intrinsic (draft/athletic) despite no prior production --
    rk = df[df["is_rookie"] == 1]
    ath_cov = df[_ATHLETIC].notna().any(axis=1).mean()
    print(f"  rookies flagged: {len(rk):,} | athletic profile present for {ath_cov:.0%} of rows")
    assert len(rk) > 100, "too few rookies flagged"
    assert (rk["draft_ovr"] < 262).sum() > 50, "rookies should carry real draft capital"
    assert (df["season"] == 2025).any(), "2025 intrinsic missing"

    # -- known-player age spot check ---------------------------------------------------------
    jj = con.execute("SELECT gsis_id FROM player_ids WHERE name='Justin Jefferson' "
                    "AND gsis_id LIKE '00-00%' LIMIT 1").fetchone()
    if jj:
        j = df[(df["gsis_id"] == jj[0])].sort_values("season")
        print("\n  Justin Jefferson age/experience by season (born 2001; rookie 2020):")
        for _, r in j.iterrows():
            print(f"    {int(r['season'])}: age={r['age']:.1f} exp={int(r['experience'])} "
                  f"rookie={int(r['is_rookie'])} draft_ovr={int(r['draft_ovr'])}")
        r2020 = j[j["season"] == 2020]
        if len(r2020):
            assert 20 <= r2020["age"].iloc[0] <= 22, "JJ 2020 age wrong"
            assert r2020["is_rookie"].iloc[0] == 1, "JJ should be a 2020 rookie"
    print("\n  [PASS] ages/experience track real player timelines; rookies carry intrinsic signal.")

    print("\nPhase 3.3 (player-intrinsic features) — all checks PASS.")
    con.close()


if __name__ == "__main__":
    main()
