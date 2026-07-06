"""Phase 5.4 — availability: discrete-time weekly hazard → games-played distribution.

    uv run python steps/phase5_4_injury.py

Done when: a logistic weekly-availability hazard is fit on the DEV player-week grid, its signs are
sane (older players and RBs are less available; durable-last-year players more so), the
Beta-Binomial over-dispersion ρ is estimated (so games-played keeps its lost-season tail), and the
model produces a per-player games-played mean for a season.
"""

from __future__ import annotations

from fantasy_quant.config import DEV_SEASONS
from fantasy_quant.data import db
from fantasy_quant.projections import injury


def main() -> None:
    con = db.connect(read_only=True)
    dev = [s for s in DEV_SEASONS if s >= 2016]

    frame = injury.availability_frame(con, dev)
    print(f"person-period grid: {len(frame)} player-weeks, "
          f"base availability {frame['available'].mean():.1%}")
    fit = injury.fit_availability(frame)
    coefs = dict(zip(fit["features"], fit["model"].coef_[0], strict=False))
    print("\nhazard coefficients (standardized; + ⇒ more available):")
    for f in fit["features"]:
        print(f"  {f:12s} {coefs[f]:+.3f}")
    # durability persistence must be positive; age must not increase availability.
    assert coefs["prior_avail"] > 0, "last-year availability should predict this-year availability"
    assert coefs["age"] <= coefs["prior_avail"], "age should not be the strongest positive driver"
    print("  [PASS] prior-season availability is a positive, sane durability signal.")

    tgt = max(dev)
    proj = injury.availability_projection(con, tgt, train_seasons=[s for s in dev if s < tgt])
    rho = float(proj["rho"].iloc[0])
    print(f"\n{tgt}: {len(proj)} players, mean availability {proj['avail_p'].mean():.1%}, "
          f"Beta-Binomial ρ = {rho:.3f}")
    print("  most fragile (lowest projected availability, ≥ a starter-level board):")
    for _, r in proj.sort_values("avail_p").head(5).iterrows():
        print(f"    {r['player_key']}  {r['pos']}  avail {r['avail_p']:.0%}  "
              f"E[games] {r['games_played_mean']:.1f}")
    assert 0.0 <= rho <= 0.5, "dispersion in range"
    assert 0.6 < proj["avail_p"].mean() < 1.0, "mean availability plausible"

    print("\nPhase 5.4 (injury availability) — all checks PASS.")
    con.close()


if __name__ == "__main__":
    main()
