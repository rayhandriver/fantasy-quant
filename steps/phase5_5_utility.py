"""Phase 5.5 — assemble the distribution, apply the mean-variance risk dial, validate, persist.

    uv run python steps/phase5_5_utility.py

Done when: the four factors (quantile 5.1 · conformal 5.2 · variance 5.3 · availability 5.4) are
composed into a per-player Monte-Carlo season distribution; the mean-variance certainty equivalent
ranks players under the λ risk dial; the assembled 80% interval's coverage is validated **once** on
the 2025 holdout; and the frozen contract is written to ``player_distributions``. This is the
object the personalization optimizer (Phase 9) and the copula/roster layer (Phase 8) consume.
"""

from __future__ import annotations

from fantasy_quant.backtest.scoring import season_points
from fantasy_quant.config import CALIBRATION_SEASONS
from fantasy_quant.data import db
from fantasy_quant.projections import conformal, distribution, quantile
from fantasy_quant.valuation import utility


def main() -> None:
    # 2025 holdout: the one season with realized outcomes to validate the assembled interval on.
    season = CALIBRATION_SEASONS[0]
    con = db.connect()      # writable — persists the contract table (gitignored store)

    print(f"assembling per-player season distributions for {season} (holdout) …")
    dist, samples = distribution.assemble_distribution(con, season, n_draws=distribution.N_DRAWS)
    board = utility.risk_adjusted_board(dist, lam=utility.DEFAULT_LAMBDA)
    print(f"  {len(board)} players · {samples.shape[1]} draws each · "
          f"contract cols {[c for c in distribution.DIST_CONTRACT]}")

    # -- the risk dial in action: top of the board by certainty equivalent -------------------------
    print(f"\ntop 10 by certainty equivalent (λ={utility.DEFAULT_LAMBDA}):")
    print("  player_key      pos   mean    sd   q10   q90  boom  bust  E[g]  risk_prem   CE")
    for _, r in board.head(10).iterrows():
        print(f"  {r['player_key']:12s}  {r['pos']:3s}  {r['mean']:5.0f} {r['sd']:5.0f} "
              f"{r['q10']:5.0f} {r['q90']:5.0f}  {r['boom_prob']:.0%}  {r['bust_prob']:.0%}  "
              f"{r['games_played_mean']:4.1f}  {r['risk_premium']:7.1f}  {r['ce_value']:5.0f}")

    # -- λ dial: a volatile player is penalized more than a steady one as risk aversion rises ----
    hi_var = board.sort_values("sd", ascending=False).iloc[0]
    lo_var = board[board["mean"] > board["mean"].median()].sort_values("sd").iloc[0]
    print("\nλ dial (certainty equivalent as risk aversion rises):")
    for name, r in (("most volatile", hi_var), ("steadiest starter", lo_var)):
        ces = [utility.certainty_equivalent(r["mean"], r["sd"] ** 2, lam)[()]
               for lam in (0.0, 0.01, 0.03)]
        print(f"  {name:17s} ({r['pos']}, mean {r['mean']:.0f}, sd {r['sd']:.0f}):  "
              f"λ0 {ces[0]:.0f} → λ.01 {ces[1]:.0f} → λ.03 {ces[2]:.0f}")
    drop_hi = hi_var["mean"] - utility.certainty_equivalent(
        hi_var["mean"], hi_var["sd"] ** 2, 0.03)[()]
    drop_lo = lo_var["mean"] - utility.certainty_equivalent(
        lo_var["mean"], lo_var["sd"] ** 2, 0.03)[()]
    assert drop_hi > drop_lo, "the risk dial must penalize the volatile player more"
    print(f"  [PASS] the dial docks the volatile player more "
          f"({drop_hi:.0f} vs {drop_lo:.0f} pts at λ.03).")

    # -- VALIDATE (once): does the assembled 80% interval cover realized 2025 outcomes? ---------
    # Two reads. CONDITIONAL (the interval's calibration target — the same available cohort the
    # healthy spread H is fit on, weeks >= 0.85*season_games): coverage should sit near the 80%
    # conformal target. UNCONDITIONAL (the full projected board, realized 0 for anyone who never
    # played): a much harsher number, dragged down by role/depth attrition — projected bodies who
    # never earn a snap — which the injury-only availability model (5.4) deliberately does NOT
    # capture. That gap is a documented Phase-5 limitation (findings.md; future work = a role/depth
    # survival haircut beyond injury), not a coverage the distribution promises.
    real = (season_points(con, season)[["gsis_id", "points", "weeks"]]
            .rename(columns={"gsis_id": "player_key"}))
    ev = board.merge(real, on="player_key", how="left")
    ev["points"] = ev["points"].fillna(0.0)
    ev["weeks"] = ev["weeks"].fillna(0)
    cov_uncond = conformal.empirical_coverage(ev["q10"], ev["q90"], ev["points"])
    cohort = ev[ev["weeks"] >= 0.85 * quantile.season_games(season)]   # the available (H) cohort
    cov_cond = conformal.empirical_coverage(cohort["q10"], cohort["q90"], cohort["points"])
    med_ae = (cohort["q50"] - cohort["points"]).abs().median()
    print(f"\nHOLDOUT {season} interval validation:")
    print(f"  conditional  (available cohort, n={len(cohort)}): coverage {cov_cond:.0%}  "
          f"(target 80%)   median |q50−realized| = {med_ae:.0f} pts")
    print(f"  unconditional (full board n={len(ev)}, 0-filled): coverage {cov_uncond:.0%}   "
          f"— role/depth attrition beyond injury (documented limitation)")
    assert 0.65 <= cov_cond <= 0.90, "the conditional interval should cover near its 80% target"

    # -- PERSIST the frozen contract ---------------------------------------------------------------
    keep = [*distribution.DIST_CONTRACT, "risk_premium", "ce_rank", "ce_pos_rank"]
    n = db.write_df(con, "player_distributions", board[keep].assign(season=season))
    print(f"\nwrote player_distributions: {n} rows (season {season}).")
    print("\nPhase 5.5 (utility) + distribution assembler — all checks PASS.")
    con.close()


if __name__ == "__main__":
    main()
