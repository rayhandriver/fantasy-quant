"""Phase 1.3 — walk-forward harness, run + verify (the engine that ties 1.1 + 1.2 together).

    uv run python steps/phase1_3_walkforward.py

Done when (BUILD_PLAN.md 1.3): a ranking method is scored end-to-end on historical drafts,
PIT-clean, in one call; swapping rank_fn is a one-arg change; a planted future feature trips assert.
"""

from __future__ import annotations

import pandas as pd

from fantasy_quant.backtest.walkforward import preseason_board, rank_by_adp, walk_forward
from fantasy_quant.data import db
from fantasy_quant.data.panel import assert_panel_pit
from fantasy_quant.data.sources.adp import adp_asof

K_DRAFTS, SEED = 6, 1


def rank_reverse(board: pd.DataFrame, con=None, season=None, as_of=None) -> pd.Series:
    """A deliberately terrible rank_fn: draft the *worst* (highest-ADP) available player first."""
    return -pd.to_numeric(board["adp"], errors="coerce")


def main() -> None:
    con = db.connect(read_only=True)

    # -- baseline: score the ADP ranking end-to-end, PIT, in one call -------------------------
    print(f"=== walk-forward: ADP baseline (2014-2024, {K_DRAFTS} drafts/season) ===")
    base = walk_forward(con, rank_by_adp, k_drafts=K_DRAFTS, seed=SEED)
    for _, r in base.per_season.iterrows():
        print(f"  {int(r['season'])}: mean starter-pts {r['mean_points']:>7.1f} "
              f"± {r['std_points']:>5.1f}  (n={int(r['n_drafts'])})")
    print(f"  POOLED: {base.pooled['mean']:.1f} ± {base.pooled['std']:.1f} "
          f"over {base.pooled['n']} drafts")
    assert len(base.per_season) == 11, "expected 11 seasons (2014-2024)"
    assert 1500 < base.pooled["mean"] < 3000, f"implausible pooled mean {base.pooled['mean']}"
    print("  [PASS] every season scored end-to-end, PIT-clean, in one call.\n")

    # -- swapping rank_fn is a one-arg change, and the harness discriminates quality ----------
    print("=== rank_fn swap (one-arg change): worst-ADP-first ===")
    rev = walk_forward(con, rank_reverse, k_drafts=K_DRAFTS, seed=SEED)
    print(f"  ADP baseline pooled : {base.pooled['mean']:.1f}")
    print(f"  worst-first pooled  : {rev.pooled['mean']:.1f}")
    gap = base.pooled["mean"] - rev.pooled["mean"]
    assert gap > 0, "harness failed to rank the ADP method above a deliberately bad one"
    print(f"  [PASS] ADP beats worst-first by {gap:.1f} pts — the harness discriminates.\n")

    # -- reproducibility ---------------------------------------------------------------------
    again = walk_forward(con, rank_by_adp, k_drafts=K_DRAFTS, seed=SEED)
    assert base.per_draft.equals(again.per_draft), "same seed produced different results"
    print("=== reproducibility ===\n  [PASS] same seed -> identical walk-forward.\n")

    # -- PIT guard: a planted future-dated feature trips the assert ---------------------------
    print("=== PIT guard (intern Step 5.1 analog) ===")
    board = adp_asof(con, 2022, "2022-09-05")
    preseason_board(con, 2022, "2022-09-05")  # real board passes the guard
    leaked = board.copy()
    leaked.loc[leaked.index[0], "snapshot_date"] = pd.Timestamp("2022-12-01")  # future leak
    try:
        assert_panel_pit(leaked, "2022-09-05", ["snapshot_date"])
        raise SystemExit("FAIL: PIT guard did not catch the planted future feature")
    except AssertionError as e:
        print(f"  [PASS] planted future ADP snapshot tripped the guard: {e}")

    print("\nPhase 1.3 (walk-forward harness) — all criteria PASS.")
    con.close()


if __name__ == "__main__":
    main()
