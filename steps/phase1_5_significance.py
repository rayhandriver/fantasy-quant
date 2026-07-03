"""Phase 1.5 — significance, run + verify (the final brick of the backtest harness).

    uv run python steps/phase1_5_significance.py

Done when (BUILD_PLAN.md 1.5): the CI machinery reproduces a known result on synthetic data and uses
block (not iid) resampling; and a real method-vs-ADP comparison returns an effect size + 95% CI so a
winner is never declared on noise. Completes Phase 1 — the backtest harness.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fantasy_quant.backtest.significance import block_bootstrap_ci, compare_to_baseline
from fantasy_quant.backtest.walkforward import rank_by_adp
from fantasy_quant.data import db

K_DRAFTS, N_BOOT, SEED = 6, 5000, 1


def rank_reverse(board: pd.DataFrame, con=None, season=None, as_of=None) -> pd.Series:
    """A deliberately terrible method: draft the worst (highest-ADP) player first."""
    return -pd.to_numeric(board["adp"], errors="coerce")


def main() -> None:
    # -- synthetic sanity: block bootstrap respects autocorrelation --------------------------
    print("=== block bootstrap on synthetic AR(1) (respects autocorrelation) ===")
    rng = np.random.default_rng(0)
    n = 400
    ar = np.empty(n)
    ar[0] = rng.normal()
    for t in range(1, n):
        ar[t] = 0.85 * ar[t - 1] + rng.normal()
    iid = block_bootstrap_ci(ar, n_boot=N_BOOT, expected_block=1, seed=SEED)
    blk = block_bootstrap_ci(ar, n_boot=N_BOOT, expected_block=20, seed=SEED)
    print(f"  iid   SE {iid.se:.3f}  |  block SE {blk.se:.3f}")
    assert blk.se > 1.5 * iid.se, "block bootstrap should widen SE under autocorrelation"
    print("  [PASS] block SE > iid SE — autocorrelation is respected (not iid).\n")

    con = db.connect(read_only=True)

    # -- null: ADP vs itself -> no edge, not significant (no false positive) ------------------
    print(f"=== null check: ADP vs ADP ({K_DRAFTS} drafts/season) ===")
    null = compare_to_baseline(con, rank_by_adp, rank_by_adp, k_drafts=K_DRAFTS,
                               n_boot=N_BOOT, seed=SEED)
    print(f"  {null!r}")
    assert null.ci.point == 0.0 and not null.ci.significant, "identical methods: not significant"
    print("  [PASS] identical method vs baseline -> edge 0, not significant.\n")

    # -- signal: a genuinely worse method is flagged significant-negative ---------------------
    print("=== signal check: worst-ADP-first vs ADP ===")
    sig = compare_to_baseline(con, rank_reverse, rank_by_adp, k_drafts=K_DRAFTS,
                              n_boot=N_BOOT, seed=SEED)
    print("  per-season PAR difference (method - ADP):")
    for season, d in sig.per_season.items():
        print(f"    {int(season)}: {d:+7.1f}")
    print(f"  {sig!r}")
    assert sig.ci.significant and sig.edge < 0, "a clearly-worse method should read significant-neg"
    assert sig.ci.hi < 0, "the whole 95% CI should sit below 0"
    print(f"  [PASS] worst-first is significantly below ADP "
          f"(edge {sig.edge:+.1f}, CI [{sig.ci.lo:+.1f}, {sig.ci.hi:+.1f}]).\n")

    print("Phase 1.5 (significance) — all criteria PASS. Phase 1 (backtest harness) COMPLETE.")
    con.close()


if __name__ == "__main__":
    main()
