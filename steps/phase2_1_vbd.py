"""Phase 2.1 — VBD baseline, run + verify (projected points -> draftable cross-position value).

    uv run python steps/phase2_1_vbd.py

Done when (BUILD_PLAN.md 2.1): the VBD board is monotonic in points within a position, and the
cross-position ordering is sane.
"""

from __future__ import annotations

from fantasy_quant.data import db
from fantasy_quant.projections.baseline import baseline_projection
from fantasy_quant.valuation.vbd import replacement_baseline, vbd

SEASON = 2023


def main() -> None:
    con = db.connect(read_only=True)
    proj = baseline_projection(con, SEASON)
    repl = replacement_baseline(con, SEASON)
    board = vbd(proj, repl).sort_values("vbd", ascending=False)

    print(f"=== replacement levels {SEASON} ===")
    for pos in ("QB", "RB", "WR", "TE", "K"):
        print(f"  {pos}: {repl.level(pos):.1f}")

    # -- monotonic in points within each position --------------------------------------------
    for pos in ("QB", "RB", "WR", "TE"):
        sub = board[board["pos"] == pos]
        pts = sub.sort_values("proj_points")["vbd"].to_numpy()
        assert (pts[1:] >= pts[:-1] - 1e-9).all(), f"VBD not monotonic in points for {pos}"
    print("\n  [PASS] VBD is monotonic in projected points within every position.")

    # -- cross-position board is a sane mix --------------------------------------------------
    names = con.execute("SELECT DISTINCT gsis_id, name FROM player_ids "
                        "WHERE gsis_id IS NOT NULL").df().drop_duplicates("gsis_id")
    top = (board.merge(names, left_on="player_key", right_on="gsis_id", how="left").head(15))
    print("\n=== top-15 VBD board (cross-position) ===")
    for _, r in top.iterrows():
        nm = str(r["name"])[:20]
        print(f"  {r['pos']:<3} {nm:<20}  proj {r['proj_points']:>6.1f}  VBD {r['vbd']:>6.1f}")
    positions = set(top["pos"])
    assert {"RB", "WR"} <= positions, "top board should include both RB and WR (not one position)"
    assert (board["vbd"] > 0).sum() >= 60, "expected a deep pool of above-replacement players"
    print("\n  [PASS] cross-position VBD board is a sane multi-position mix.")
    print("  (Note: naive VBD ranks elite QBs high — a known 1-QB artifact the ensemble corrects.)")

    print("\nPhase 2.1 (VBD baseline) — all criteria PASS.")
    con.close()


if __name__ == "__main__":
    main()
