"""Phase 4.2 — the VBD value board (value signal + frozen contract), run + verify.

    uv run python steps/phase4_2_value_board.py

Done when (reframed BUILD_PLAN 4.2): the consensus mean becomes a draftable cross-position value
board — proj_points → VBD (positional replacement subtracted) → within-position + overall ranks — in
the frozen contract shape Phase 5 wraps; VBD visibly demotes 1-QB quarterbacks vs a raw-points sort;
and the same board builds off the historical baseline proxy for a backtest season.
"""

from __future__ import annotations

from fantasy_quant.data import db
from fantasy_quant.valuation.value_board import CONTRACT_COLS, value_board


def _check_board(board, label):
    assert list(board.columns) == CONTRACT_COLS, f"{label}: contract drift {list(board.columns)}"
    assert board["proj_points"].notna().all() and (board["proj_points"] > 0).all()
    assert board["overall_rank"].is_monotonic_increasing, f"{label}: not sorted by overall_rank"
    assert list(board["overall_rank"]) == list(range(1, len(board) + 1)), f"{label}: rank gaps"
    # within each position, pos_rank must order by descending VBD
    for pos, g in board.groupby("pos"):
        gg = g.sort_values("pos_rank")
        assert gg["vbd"].is_monotonic_decreasing, f"{label}: {pos} pos_rank not by VBD"


def main() -> None:
    con = db.connect(read_only=True)

    live = value_board(con, 2026)
    _check_board(live, "2026 consensus")
    print(f"=== value board 2026 (source={live['source'].iloc[0]}): {len(live)} players ===")
    print(live.head(15).to_string(index=False))

    # VBD's whole point: quarterbacks that top a RAW-points sort get demoted in a 1-QB league.
    top_by_points = live.sort_values("proj_points", ascending=False).head(15)
    qb_raw = int((top_by_points["pos"] == "QB").sum())
    qb_vbd = int((live.head(15)["pos"] == "QB").sum())
    print(f"\n  QBs in top-15 by raw points: {qb_raw}  ->  by VBD: {qb_vbd}  "
          f"(VBD moves scarcity to RB/WR in 1-QB)")
    assert qb_vbd <= qb_raw, "VBD should not promote QBs vs a raw-points sort in 1-QB"

    # historical season -> the baseline proxy behind the same contract
    hist = value_board(con, 2023)
    _check_board(hist, "2023 proxy")
    assert hist["source"].iloc[0] == "proxy", "2023 should be the baseline proxy"
    print(f"\n  [PASS] historical 2023 board builds off the proxy: {len(hist)} players, "
          f"same contract; top-3 {list(hist.head(3)['player_key'])}.")

    print(f"\n  contract frozen: {CONTRACT_COLS}")
    print("\nPhase 4.2 (VBD value board) — all checks PASS.")
    con.close()


if __name__ == "__main__":
    main()
