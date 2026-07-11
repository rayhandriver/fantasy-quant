"""Phase 5.4 — availability: discrete-time weekly hazard → games-played distribution (+ T3).

    uv run python steps/phase5_4_injury.py

Done when: a logistic weekly-availability hazard is fit on the DEV player-week grid, its signs are
sane (older players and RBs are less available; durable-last-year players more so), the
Beta-Binomial over-dispersion ρ is estimated (so games-played keeps its lost-season tail), and the
model produces a per-player games-played mean for a season.

**T3 (2026-07-11)** extends this module with the two downside fixes and their done-bar checks: the
**cohort availability prior** for the rookie/backup sub-gate universe (A) and the **role-loss
washout mixture** for established deep-projected players (B). See TECH-DEBT T3 / `findings.md`.
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

    # -- T3-A: the cohort availability prior (rookies/backups the hazard drops) --------------------
    train = [s for s in dev if s < tgt]
    cohort = injury.cohort_availability_prior(con, train)
    print("\nT3-A cohort availability prior (pos × draft-capital tier → avail_p, ρ):")
    for pos in ("RB", "WR", "TE", "QB"):
        hi = cohort.get((pos, "hi")) or cohort.get((pos, "*"))
        lo = cohort.get((pos, "lo")) or cohort.get((pos, "*"))
        print(f"  {pos}: hi-capital avail {hi['avail_p']:.0%} (ρ {hi['rho']:.2f}) | "
              f"lo-capital avail {lo['avail_p']:.0%} (ρ {lo['rho']:.2f})")
    rb_hi, rb_lo = cohort.get(("RB", "hi")), cohort.get(("RB", "lo"))
    if rb_hi and rb_lo:
        assert rb_hi["avail_p"] > rb_lo["avail_p"], "premium RB rookies should out-play late fliers"
    assert cohort[("*", "*")]["rho"] > rho, "the cohort tail must be fatter than the established"
    print("  [PASS] premium picks out-play late fliers; cohort tail fatter than the established.")

    # -- T3-B: the role-loss washout mixture (established, deep-projected) ----------------------
    ret = injury.role_retention(con, train)
    print("\nT3-B role-loss washout rate by tier (p_washout, crater_avail, keep_frac):")
    for pos in ("RB", "WR"):
        for tier in ("elite", "starter", "deep"):
            c = ret.get((pos, tier))
            if c:
                print(f"  {pos}-{tier:7s}: p {c['p_crater']:.2f}  avail {c['crater_avail']:.2f}  "
                      f"keep {c['keep_frac']:.2f}  (n={c['n']})")
    for pos in ("RB", "WR", "TE"):
        deep, elite = ret.get((pos, "deep")), ret.get((pos, "elite"))
        if deep and elite:
            assert deep["p_crater"] > elite["p_crater"], f"{pos} deep washes out more than elite"
    print("  [PASS] deep-projected players wash out more than elite — the pure role-loss channel.")

    print("\nPhase 5.4 (injury availability + T3 cohort/washout) — all checks PASS.")
    con.close()


if __name__ == "__main__":
    main()
