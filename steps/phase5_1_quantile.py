"""Phase 5.1 — quantile regression of realized points on the calibrated mean.

    uv run python steps/phase5_1_quantile.py

Done when: per-position quantile lines fit walk-forward on the conditional (available) DEV cohort,
the median line recovers the calibrated mean (slope≈1), and the outer τ lines fan out with level
(spread grows with projection) — the heteroscedastic if-healthy spread the sampler draws from.
"""

from __future__ import annotations

from fantasy_quant.config import DEV_SEASONS
from fantasy_quant.data import db
from fantasy_quant.projections import quantile


def main() -> None:
    con = db.connect(read_only=True)
    dev = [s for s in DEV_SEASONS if s >= 2016]
    corr = quantile.dev_correction(con)
    train = quantile.conditional_training_frame(con, dev, correction=corr)
    print(f"conditional training cohort: {len(train)} player-seasons "
          f"({sorted(train['pos'].unique())})")

    models = quantile.fit_quantile_models(train)

    # median line should track the calibrated mean (slope near 1, not systematically biased)
    med_slopes = [models[p][0.5][1] for p in models]
    avg_med = sum(med_slopes) / len(med_slopes)
    print(f"\nmean τ.50 slope across positions = {avg_med:.2f} (≈1 ⇒ median tracks the mean)")
    assert 0.6 < avg_med < 1.4, "median quantile should roughly recover the mean"

    # the heteroscedastic fan: the 80% band width should GROW from a low to a high projected mean
    # (measured on the fitted band, not raw slopes — QB fans out via the intercept, not the slope).
    print("\n80% band width at each position's p25 vs p75 calibrated mean:")
    grows = []
    for pos in ("QB", "RB", "WR", "TE"):
        if pos not in models:
            continue
        g = train[train["pos"] == pos]["calibrated_mean"]
        lo_m, hi_m = float(g.quantile(0.25)), float(g.quantile(0.75))
        q_lo = quantile.predict_quantiles(models, pos, [lo_m])[0]
        q_hi = quantile.predict_quantiles(models, pos, [hi_m])[0]
        w_lo, w_hi = q_lo[-1] - q_lo[0], q_hi[-1] - q_hi[0]
        grows.append(w_hi >= w_lo)
        print(f"  {pos}:  mean {lo_m:5.0f}→width {w_lo:4.0f}   mean {hi_m:5.0f}→width {w_hi:4.0f}  "
              f"τ.50 slope {models[pos][0.5][1]:+.2f}")
    assert sum(grows) >= len(grows) - 1, "band width should widen with level for ≥3/4 positions"
    print(f"  [PASS] band widens with projection for {sum(grows)}/{len(grows)} positions.")

    print("\nPhase 5.1 (quantile regression) — all checks PASS.")
    con.close()


if __name__ == "__main__":
    main()
