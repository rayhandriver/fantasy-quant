"""Phase 1.1 — league scoring engine, run + verify (first brick of the backtest harness).

    uv run python steps/phase1_1_scoring.py

Done when (BUILD_PLAN.md 1.1): reconstructed full-PPR points match nflverse ``fantasy_points_ppr``
within rounding across a broad player-week sample (hard assert); K/DST weekly points — derived from
pbp/game_lines for the 9-starter lineup — pass sanity checks; K/DST identity resolvers work.
"""

from __future__ import annotations

from fantasy_quant.backtest import scoring
from fantasy_quant.data import db

SEASONS = range(2014, 2025)  # fantasy-point history (weekly) spans 2014-2024
TOL = 0.02  # nflverse stores points as float32; recon is float64 -> epsilon-level diffs


def main() -> None:
    con = db.connect(read_only=True)

    # -- offense: the hard done-criterion (reconstruct == nflverse fantasy_points_ppr) --------
    print("=== offense: reconstructed PPR vs nflverse fantasy_points_ppr ===")
    worst = 0.0
    total = 0
    over_tol = 0
    for yr in SEASONS:
        wk = scoring.weekly_points(con, yr)
        diff = (wk["points"] - wk["fantasy_points_ppr"].fillna(0.0)).abs()
        total += len(wk)
        over_tol += int((diff > TOL).sum())
        worst = max(worst, float(diff.max()))
        print(f"  {yr}: {len(wk):>6,} player-weeks | max|diff|={diff.max():.4g}")
    print(f"  TOTAL {total:,} player-weeks | over tol({TOL}): {over_tol} | worst|diff|={worst:.4g}")
    assert over_tol == 0, f"{over_tol} player-weeks exceed scoring tolerance {TOL}"
    print("  [PASS] offensive scoring reproduces nflverse full-PPR exactly.\n")

    # -- kickers: derived from pbp; sanity-check ranges + a known kicker ----------------------
    print("=== kickers (pbp-derived), 2022 ===")
    kw = scoring.kicker_weekly_points(con, 2022)
    kseason = (kw.groupby(["gsis_id", "player_name"], as_index=False)
                 .agg(pts=("points", "sum"), wks=("week", "nunique"))
                 .sort_values("pts", ascending=False))
    print("  top-5 kicker season totals:")
    for _, r in kseason.head(5).iterrows():
        print(f"    {r['player_name']:<20} {r['pts']:>6.1f} pts over {int(r['wks'])} wks")
    top_k = kseason.iloc[0]
    assert 80 <= top_k["pts"] <= 220, f"implausible top kicker total {top_k['pts']}"
    assert kw["points"].min() >= -5 and kw["points"].max() <= 30, "implausible kicker week"
    print(f"  [PASS] kicker weekly points in plausible range "
          f"(week min={kw['points'].min():.0f}, max={kw['points'].max():.0f}).\n")

    # -- team defense: derived from pbp events + game_lines PA --------------------------------
    print("=== team defense (pbp+PA-derived), 2022 ===")
    dw = scoring.dst_weekly_points(con, 2022)
    dseason = (dw.groupby("team", as_index=False)
                 .agg(pts=("points", "sum"), wks=("week", "nunique"))
                 .sort_values("pts", ascending=False))
    print("  top-5 DST season totals:")
    for _, r in dseason.head(5).iterrows():
        print(f"    {r['team']:<5} {r['pts']:>6.1f} pts over {int(r['wks'])} wks")
    top_d = float(dseason.iloc[0]["pts"])
    assert 60 <= top_d <= 260, f"implausible top DST total {top_d}"
    assert dw["pa"].notna().all(), "some DST team-weeks missing points-allowed"
    print(f"  [PASS] DST weekly points sane (week min={dw['points'].min():.0f}, "
          f"max={dw['points'].max():.0f}; all PA joined).\n")

    # -- identity: connect ADP K/DST rows (null gsis) to a scoreable key ----------------------
    print("=== K/DST identity resolvers ===")
    tucker = scoring.resolve_kicker_gsis(con, "Justin Tucker", season=2022)
    phi = scoring.dst_team_from_adp_name("Philadelphia Defense")
    print(f"  resolve_kicker_gsis('Justin Tucker') -> {tucker}")
    print(f"  dst_team_from_adp_name('Philadelphia Defense') -> {phi}")
    assert tucker == "00-0029597", f"Tucker gsis mismatch: {tucker}"
    assert phi == "PHI", f"PHI mapping wrong: {phi}"

    # resolve every K/DST on a real ADP board and report coverage
    board = con.execute(
        "SELECT DISTINCT name, position FROM adp_snapshots "
        "WHERE season=2022 AND source='ffc' AND scoring='ppr' AND teams=10 "
        "AND position IN ('PK','K','DEF') AND adp <= 180"
    ).df()
    kick_names = board[board["position"].isin(["PK", "K"])]["name"]
    def_names = board[board["position"] == "DEF"]["name"]
    k_res = sum(scoring.resolve_kicker_gsis(con, n, 2022) is not None for n in kick_names)
    d_res = sum(dst_ok(scoring.dst_team_from_adp_name(n)) for n in def_names)
    print(f"  2022 draftable board: kickers resolved {k_res}/{len(kick_names)}, "
          f"defenses resolved {d_res}/{len(def_names)}")
    assert k_res == len(kick_names), "unresolved kicker(s) on the draftable board"
    assert d_res == len(def_names), "unresolved defense(s) on the draftable board"
    print("  [PASS] all draftable K/DST resolve to a scoreable key.\n")

    print("Phase 1.1 (scoring engine) — all criteria PASS.")
    con.close()


def dst_ok(abbr: str | None) -> bool:
    return abbr is not None


if __name__ == "__main__":
    main()
