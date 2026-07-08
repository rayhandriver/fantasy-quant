"""Phase 6 — ADP-bias mining (where the market is soft), on real DEV data.

    uv run python steps/phase6_adp_bias.py

Done when (PROJECT.md §5): stable, significant ADP biases are identified with CIs — or honestly
ruled out. The reframe (2026-07-04) reads the answer as *how cheaply a personalization preference
can be indulged*: a trait with positive ADP-alpha is under-drafted (cheap/free to prefer), negative
is over-drafted (costly to chase). Pipeline: 6.1 build the leave-one-season-out ADP-alpha panel →
6.2 cross-sectional regression with season-block-bootstrap CIs → 6.3 scorecard (Benjamini-Hochberg
FDR + walk-forward sign stability). Runs on ``DEV_SEASONS``; the 2023/24 lockbox is never read.

This is *analysis* — it does not yet wire into the cost report. How the surviving softness signal
would price a preference cheaper is left for a follow-on (documented in findings.md).
"""

from __future__ import annotations

from fantasy_quant.adp.panel import FEATURES, build_alpha_panel
from fantasy_quant.adp.regression import fit_alpha_regression
from fantasy_quant.adp.scorecard import bias_scorecard
from fantasy_quant.config import DEV_SEASONS, LOCKBOX_SEASONS
from fantasy_quant.data import db


def main() -> None:
    con = db.connect(read_only=True)

    # 6.1 — the panel
    panel = build_alpha_panel(con, seasons=DEV_SEASONS)
    assert not (set(panel["season"]) & set(LOCKBOX_SEASONS)), "lockbox leaked into the panel"
    pos_mean = panel.groupby("pos")["alpha"].mean().abs().max()
    print(f"6.1 panel: {len(panel)} drafted players, seasons {sorted(panel['season'].unique())}, "
          f"max |per-position mean alpha| = {pos_mean:.1f} (LOSO baseline → ~0)")

    # 6.2 — the regression
    reg = fit_alpha_regression(panel, n_boot=5000)
    print(f"6.2 regression: R²={reg.r2:.3f} over {reg.n} players / {reg.n_seasons} seasons "
          f"({reg.n_boot} season-block bootstraps)")

    # 6.3 — the scorecard
    sc = bias_scorecard(panel, reg=reg)
    print("\n" + sc.render())

    # sanity gates — the pipeline is sound; we do not force a particular bias to appear.
    assert len(panel) > 1000, "panel unexpectedly thin"
    assert pos_mean < 8.0, "LOSO baseline not centering alpha within position"
    assert len(sc.table) == len(FEATURES), "scorecard must judge every trait"
    assert sc.table["stability"].notna().all(), "stability not computed for some trait"

    survivors = sc.significant["label"].tolist()
    print(f"\n  Done-when satisfied: {len(survivors)} stable, FDR-significant ADP bias(es) "
          f"identified {survivors or '— the rest honestly ruled out'}.")
    print("\nPhase 6 (ADP-bias mining) — all checks PASS.")
    con.close()


if __name__ == "__main__":
    main()
