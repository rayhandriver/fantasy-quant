"""Phase 2.2 — naive baseline projection, run + verify (the dumb model to beat).

    uv run python steps/phase2_2_baseline.py

Done when (BUILD_PLAN.md 2.2): the baseline produces a full board and backtests through the Phase-1
harness; logged as the baseline to beat. (Beating ADP is NOT required — expect it to lose; that's
a finding, per CLAUDE.md §3.3.)
"""

from __future__ import annotations

from fantasy_quant.backtest.significance import compare_to_baseline
from fantasy_quant.backtest.walkforward import draft_date, preseason_board, rank_by_adp
from fantasy_quant.data import db
from fantasy_quant.projections.baseline import baseline_projection
from fantasy_quant.valuation.vbd import vbd_rank_fn

K_DRAFTS, N_BOOT, SEED = 6, 5000, 1


def main() -> None:
    con = db.connect(read_only=True)

    # -- the projection produces a full, sane board ------------------------------------------
    proj = baseline_projection(con, 2023)
    print("=== baseline projection (2023, from 2022 production) ===")
    print(f"  projected {len(proj)} players: {proj['pos'].value_counts().to_dict()}")
    assert (proj["proj_points"] > 0).all(), "projections must be positive"
    as_of = draft_date(con, 2023)
    board = preseason_board(con, 2023, as_of)
    covered = vbd_rank_fn(baseline_projection)(board, con, 2023, as_of).notna().sum()
    print(f"  covers {covered}/{len(board)} of the draftable board (rest -> ADP fallback)")
    assert covered > 0.6 * len(board), "baseline should cover most veterans on the board"
    print("  [PASS] full board produced (offense + K), PIT from prior season.\n")

    # -- backtest the VBD-ranked baseline vs ADP through the harness --------------------------
    print(f"=== backtest: baseline-VBD vs ADP (2014-2024, {K_DRAFTS} drafts/season) ===")
    method = vbd_rank_fn(baseline_projection)
    cmp = compare_to_baseline(con, method, rank_by_adp, k_drafts=K_DRAFTS, n_boot=N_BOOT, seed=SEED)
    for season, d in cmp.per_season.items():
        print(f"    {int(season)}: {d:+7.1f}")
    print(f"  baseline pooled {cmp.method_mean:.0f} pts | ADP pooled {cmp.baseline_mean:.0f} pts")
    print(f"  {cmp!r}")
    verdict = ("BEATS ADP" if cmp.ci.significant and cmp.edge > 0
               else "LOSES to ADP" if cmp.ci.significant and cmp.edge < 0
               else "on par with ADP (CI spans 0)")
    print(f"  FINDING: naive baseline is {verdict}.")
    print("  (Naive VBD overrates QBs in 1-QB leagues; the ADP blend in 2.4 corrects it.)")
    print("\nPhase 2.2 (naive baseline) — board + harness backtest PASS (edge is a finding).")
    con.close()


if __name__ == "__main__":
    main()
