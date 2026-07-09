"""Phase 6 — ADP-bias mining (where the market is soft), on real DEV data.

    uv run python steps/phase6_adp_bias.py

Done when (PROJECT.md §5): stable, significant ADP biases are identified with CIs — or honestly
ruled out. The reframe (2026-07-04) reads the answer as *how cheaply a personalization preference
can be indulged*: a trait with positive ADP-alpha is under-drafted (cheap/free to prefer), negative
is over-drafted (costly to chase). Pipeline: 6.1 build the leave-one-season-out ADP-alpha panel →
6.2 cross-sectional regression with season-block-bootstrap CIs → 6.3 scorecard (Benjamini-Hochberg
FDR + walk-forward sign stability). Runs on ``DEV_SEASONS``; the 2023/24 lockbox is never read.

Since 2026-07-09 the surviving signal is **wired into the cost report** as a frozen
:data:`~fantasy_quant.adp.softness.DURABILITY` constant (credit + net-effective-cost lines); this
script doubles as the **drift check** — it recomputes the scorecard and asserts the frozen numbers
still match the data.
"""

from __future__ import annotations

from fantasy_quant.adp.panel import FEATURES, build_alpha_panel
from fantasy_quant.adp.regression import fit_alpha_regression
from fantasy_quant.adp.scorecard import bias_scorecard
from fantasy_quant.adp.softness import DURABILITY, signals_from_scorecard
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

    # drift check — the frozen softness constant the cost report prices with must still match a
    # fresh recompute (regeneration uses the same n_boot=5000 seed=0 fit as the freeze).
    fresh = {s.term: s for s in signals_from_scorecard(sc, panel)}
    assert "prior_games" in fresh, "durability no longer survives the scorecard — refreeze needed"
    f = fresh["prior_games"]
    for attr in ("coef", "mu", "sd"):
        frozen, now = getattr(DURABILITY, attr), getattr(f, attr)
        assert abs(frozen - now) <= 0.05 * max(abs(frozen), 1.0), \
            f"softness drift: {attr} frozen {frozen:.3f} vs recomputed {now:.3f} — refreeze"
    print(f"  Drift check: frozen DURABILITY (coef {DURABILITY.coef:+.1f}, μ {DURABILITY.mu:.1f}, "
          f"σ {DURABILITY.sd:.1f}) matches the recompute.")
    print("\nPhase 6 (ADP-bias mining) — all checks PASS.")
    con.close()


if __name__ == "__main__":
    main()
