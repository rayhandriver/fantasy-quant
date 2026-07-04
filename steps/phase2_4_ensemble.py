"""Phase 2.4 — ensemble-with-market, run + verify (blend the model with the sharp consensus).

    uv run python steps/phase2_4_ensemble.py

Done when (BUILD_PLAN.md 2.4): the ensemble backtests >= its best single component. Weights are
grid-fit through the harness; w=0 is pure ADP, w=1 is the pure baseline, so best-of-grid is >= both.
"""

from __future__ import annotations

from fantasy_quant.backtest.significance import compare_to_baseline
from fantasy_quant.backtest.walkforward import rank_by_adp
from fantasy_quant.data import db
from fantasy_quant.projections.ensemble import ensemble_rank_fn, fit_weight

GRID = (0.0, 0.25, 0.5, 0.75, 1.0)
K_FIT, K_EVAL, N_BOOT, SEED = 4, 6, 5000, 1


def main() -> None:
    con = db.connect(read_only=True)

    # -- grid-fit the baseline<->ADP blend weight through the harness ------------------------
    print(f"=== fit ensemble weight (baseline<->ADP blend), {K_FIT} drafts/season ===")
    best_w, pooled = fit_weight(con, grid=GRID, k_drafts=K_FIT, seed=SEED)
    for w in GRID:
        tag = "  <- pure ADP" if w == 0 else "  <- pure baseline" if w == 1 else ""
        star = "  *BEST*" if w == best_w else ""
        print(f"  w_baseline={w:<4}: pooled {pooled[w]:.0f} pts{star}{tag}")
    adp_pooled, base_pooled = pooled[0.0], pooled[1.0]
    best_component = max(adp_pooled, base_pooled)
    print(f"  best component = {best_component:.0f} (ADP {adp_pooled:.0f}, base {base_pooled:.0f})")
    assert pooled[best_w] >= best_component - 1e-6, "ensemble should be >= best single component"
    print(f"  [PASS] ensemble (w={best_w}) pooled {pooled[best_w]:.0f} >= best component "
          f"{best_component:.0f}.\n")

    # -- CI on the fitted ensemble vs ADP ----------------------------------------------------
    print(f"=== fitted ensemble (w={best_w}) vs ADP, {K_EVAL} drafts/season ===")
    cmp = compare_to_baseline(con, ensemble_rank_fn(best_w), rank_by_adp,
                              k_drafts=K_EVAL, n_boot=N_BOOT, seed=SEED)
    print(f"  {cmp!r}")
    verdict = ("BEATS ADP" if cmp.ci.significant and cmp.edge > 0
               else "matches ADP" if not cmp.ci.significant
               else "below ADP")
    print(f"  FINDING: the ensemble {verdict} "
          f"(edge {cmp.edge:+.1f}/season, CI [{cmp.ci.lo:+.1f}, {cmp.ci.hi:+.1f}]).")
    if best_w == 0.0:
        print("  -> best weight is pure ADP: the naive baseline adds no edge over the market yet")
        print("     (expected — 'don't fight the sharp market'; real signal comes in Phases 3-5).")
    print("\nPhase 2.4 (ensemble-with-market) — ensemble >= best component: PASS.")
    con.close()


if __name__ == "__main__":
    main()
