"""Phase 4.1 — consensus-projections ingest (the VALUE signal), run + verify.

    uv run python steps/phase4_1_consensus.py

Done when (reframed BUILD_PLAN 4.1): a free consensus board is ingested for the live season, its
points re-scored to our full-PPR RuleSet (cross-checks vs FantasyPros' own FPTS), name-matched to
gsis, PIT-stamped; and the two-track `consensus_projection` dispatch returns the scraped board for
the live season and the baseline proxy for a historical season — same shape either way.
"""

from __future__ import annotations

import datetime as dt

import numpy as np

from fantasy_quant.data import db
from fantasy_quant.projections import consensus

LIVE_SEASON = 2026  # the upcoming draft FantasyPros currently serves (as-of 2026-07-05)


def main() -> None:
    con = db.connect()

    n = consensus.ingest_consensus(con, LIVE_SEASON)
    print(f"=== consensus_projections ingested: {n} rows (season {LIVE_SEASON}) ===")
    if n == 0:
        print("  [SKIP] FantasyPros returned nothing — live track is a no-op until a source lands.")
        return

    board = con.execute(
        f"SELECT position, COUNT(*) n, COUNT(gsis_id) n_matched, ROUND(AVG(proj_points),1) avg_pts "
        f"FROM {consensus.CONSENSUS_TABLE} GROUP BY position ORDER BY n DESC").df()
    print(board.to_string(index=False))
    tot = con.execute(
        f"SELECT COUNT(*), COUNT(gsis_id) FROM {consensus.CONSENSUS_TABLE}").fetchone()
    print(f"  gsis match rate: {tot[1]}/{tot[0]} = {tot[1]/tot[0]:.0%} "
          f"(unmatched = new rookies / name gaps, expected)")

    # -- coverage sanity: guard against a transient truncated page slipping through ----------------
    by_pos = dict(con.execute(
        f"SELECT position, COUNT(*) FROM {consensus.CONSENSUS_TABLE} GROUP BY position").fetchall())
    assert by_pos.get("RB", 0) >= 40 and by_pos.get("WR", 0) >= 50, \
        f"consensus coverage looks truncated: {by_pos}"

    # -- our full-PPR reconstruction should track FantasyPros' own FPTS closely for offense --------
    off = con.execute(
        f"SELECT proj_points, fp_fpts FROM {consensus.CONSENSUS_TABLE} "
        f"WHERE position IN ('QB','RB','WR','TE') AND fp_fpts > 0").df()
    c = float(np.corrcoef(off["proj_points"], off["fp_fpts"])[0, 1])
    mad = float((off["proj_points"] - off["fp_fpts"]).abs().mean())
    print(f"\n  corr(our full-PPR, FP FPTS) = {c:.3f}; mean abs diff {mad:.1f} pts "
          f"(small gap = 2pt/return-TD not projected). ")
    assert c > 0.98, f"reconstructed points should track FP FPTS (got {c:.3f})"

    print("\n  top-12 by our full-PPR consensus:")
    top = con.execute(
        f"SELECT name, position, team, ROUND(proj_points,1) pts FROM {consensus.CONSENSUS_TABLE} "
        f"ORDER BY proj_points DESC LIMIT 12").df()
    print(top.to_string(index=False))

    # -- PIT: a board dated today is invisible to an earlier as-of, visible to a later one ---------
    snap = con.execute(f"SELECT MAX(snapshot_date) FROM {consensus.CONSENSUS_TABLE}").fetchone()[0]
    day_before = snap - dt.timedelta(days=1)
    before = consensus.consensus_asof(con, LIVE_SEASON, as_of=str(day_before))
    after = consensus.consensus_asof(con, LIVE_SEASON, as_of=str(snap))
    assert before.empty and not after.empty, "PIT: consensus_asof must hide a future snapshot"
    print(f"\n  [PASS] PIT: as-of {day_before} -> empty, as-of {snap} -> {len(after)} players.")

    # -- two-track dispatch: live -> scraped board; historical -> baseline proxy -------------------
    live = consensus.consensus_projection(con, LIVE_SEASON)
    hist = consensus.consensus_projection(con, 2023)
    assert set(live.columns) == set(hist.columns) == {"player_key", "pos", "proj_points"}
    assert not consensus.has_consensus(con, 2023), "2023 should have no scraped board"
    print(f"\n  [PASS] dispatch: {LIVE_SEASON} -> scraped consensus ({len(live)} players); "
          f"2023 -> baseline proxy ({len(hist)} players); identical shape.")

    print("\nPhase 4.1 (consensus ingest) — all checks PASS.")
    con.close()


if __name__ == "__main__":
    main()
