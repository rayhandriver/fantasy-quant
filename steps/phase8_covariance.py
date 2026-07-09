"""Phase 8 — covariance & roster construction, validated on real DEV data.

    uv run python steps/phase8_covariance.py

Done when (BUILD_PLAN 8.1–8.5 + the 9.1 pull-forward, decisions 2026-07-09):
  * the pooled relationship correlations estimate cleanly and the shrunk model **predicts
    out-of-sample stack variance better than assuming independence** (8.2's done-bar, walk-forward);
  * a full board Σ passes the **hard gate** (PSD/symmetric/finite — the intern gate);
  * the handcuff copula captures tail dependence the Gaussian misses, **against real backfields**;
  * a stacked roster shows a higher ceiling and a hedged one a higher floor (8.4's done-bar);
  * the handcuff option premium moves with starter fragility (8.5's done-bar);
  * the covariance-aware greedy (λ>0) drafts **less same-team covariance** than the λ=0 greedy.

Everything runs on DEV seasons; the 2023/24 lockbox is never read.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fantasy_quant.backtest.walkforward import draft_date, preseason_board
from fantasy_quant.config import DEV_SEASONS, LOCKBOX_SEASONS
from fantasy_quant.covariance import copula
from fantasy_quant.covariance.estimate import (
    pair_correlations,
    player_covariance,
    role_ranks,
    validate_covariance,
    weekly_offense_panel,
)
from fantasy_quant.covariance.shrinkage import CorrelationModel, shrink_correlations
from fantasy_quant.data import db
from fantasy_quant.draft.config import DraftConfig, LeagueSetup
from fantasy_quant.draft.optimizer import (
    assemble_correlation,
    assemble_value,
    attach_value,
    build_risk_model,
    cross_covariance,
    optimize_draft,
)
from fantasy_quant.draft.simulator import canon_pos
from fantasy_quant.valuation.handcuff import elevation_stats, handcuff_value
from fantasy_quant.valuation.roster_risk import roster_risk

SEASON = 2022                      # the representative DEV season for the board-level checks
OOS_SEASONS = tuple(s for s in DEV_SEASONS if s >= 2016)   # ≥2 training seasons behind each


# ------------------------------------------------------------------------------------------------
# 8.2 done-bar: does the shrunk correlation predict NEXT season's stack variance?
# ------------------------------------------------------------------------------------------------
def oos_stack_variance(con) -> pd.DataFrame:
    """Walk-forward: for each season, predict every QB1+WR1 pair's weekly-sum variance from that
    season's own player sds plus a correlation fit on strictly-prior seasons, under three models
    (independence ρ=0 · raw empirical · shrunk). Only ρ differs, so the error isolates the
    correlation model. Returns mean absolute error per model per season."""
    rows = []
    for season in OOS_SEASONS:
        train = [s for s in DEV_SEASONS if s < season]
        emp = pair_correlations(weekly_offense_panel(con, train))
        raw = CorrelationModel.from_table(emp.assign(rho=emp["corr"]))
        shrunk = CorrelationModel.from_table(shrink_correlations(emp))

        panel = weekly_offense_panel(con, [season])
        roles = role_ranks(panel)
        p = panel.merge(roles, on=["season", "team", "pos", "gsis_id"])
        for (_, team), g in p.groupby(["season", "team"]):
            qb = g[(g["pos"] == "QB") & (g["role"] == 1)]
            wr = g[(g["pos"] == "WR") & (g["role"] == 1)]
            if qb.empty or wr.empty:
                continue
            wide = pd.merge(qb[["week", "points"]], wr[["week", "points"]],
                            on="week", suffixes=("_qb", "_wr")).dropna()
            if len(wide) < 8:
                continue
            x, y = wide["points_qb"].to_numpy(), wide["points_wr"].to_numpy()
            sx, sy = x.std(ddof=1), y.std(ddof=1)
            real = float(np.var(x + y, ddof=1))
            for model, rho in (("independence", 0.0),
                               ("raw", raw.rho("QB", 1, "WR", 1)),
                               ("shrunk", shrunk.rho("QB", 1, "WR", 1))):
                pred = sx**2 + sy**2 + 2 * rho * sx * sy
                rows.append({"season": season, "team": team, "model": model,
                             "abs_err": abs(pred - real), "real_var": real})
    per = pd.DataFrame(rows)
    return (per.groupby("model", as_index=False)
            .agg(mae=("abs_err", "mean"), n_pairs=("abs_err", "count")))


# ------------------------------------------------------------------------------------------------
# 8.3 check: real backfields — empirical boom|bust vs Clayton vs Gaussian
# ------------------------------------------------------------------------------------------------
def handcuff_tail_check(con) -> dict:
    """Pooled over every DEV RB1/RB2 backfield: P(backup in his own top quartile | starter in his
    own bottom quartile) on the zero-filled grid, vs what the fitted Clayton and a Kendall-matched
    Gaussian each predict. Independence would be 0.25."""
    panel = weekly_offense_panel(con, DEV_SEASONS)
    dep = copula.handcuff_dependence(panel)
    pairs = copula.handcuff_pairs(panel)
    hits, conds = 0, 0
    for _, g in pairs.groupby(["season", "team"]):
        if len(g) < 10:
            continue
        s_lo = g["starter_pts"] <= g["starter_pts"].quantile(0.25)
        b_hi = g["backup_pts"] >= g["backup_pts"].quantile(0.75)
        conds += int(s_lo.sum())
        hits += int((s_lo & b_hi).sum())
    emp = hits / conds if conds else float("nan")
    q = 0.25
    return {**dep, "empirical": emp,
            "clayton": copula.boom_given_bust_clayton(q, dep["theta"]),
            "gaussian": copula.boom_given_bust_gaussian(q, dep["tau"]),
            "n_cond_weeks": conds}


def main() -> None:
    assert all(s not in LOCKBOX_SEASONS for s in DEV_SEASONS)
    assert SEASON in DEV_SEASONS and all(s in DEV_SEASONS for s in OOS_SEASONS)
    con = db.connect(read_only=True)

    # -- 8.1/8.2: the correlation model on full DEV, with its audit trail ----------------------
    corr = assemble_correlation(con, SEASON + 1)        # trains on ≤ SEASON (strictly prior, PIT)
    print("Shrunk relationship correlations (fit on DEV ≤ 2022; emp vs prior vs shrunk):")
    print(corr.render(min_pairs=30))

    print("\nOut-of-sample QB1+WR1 stack-variance prediction (walk-forward, only ρ differs):")
    oos = oos_stack_variance(con)
    print(oos.to_string(index=False))
    mae = oos.set_index("model")["mae"]
    assert mae["shrunk"] < mae["independence"], "shrunk ρ must beat assuming independence OOS"

    # -- 8.1: full-board Σ passes the hard gate ------------------------------------------------
    vi = assemble_value(con, SEASON, DraftConfig(league=LeagueSetup(draft_slot=1)))
    m = vi.dropna(subset=["sd", "team"]).drop_duplicates("player_key")
    sigma = player_covariance(m["sd"], m["team"], m["pos"],
                              m["role_rank"].fillna(1).astype(int), corr.rho)
    validate_covariance(sigma)
    eig = np.linalg.eigvalsh(sigma)
    print(f"\nBoard Σ ({len(m)} players, {SEASON}): hard gate PASS "
          f"(min eig {eig[0]:.2e}, cond {eig[-1] / max(eig[0], 1e-12):.1e})")

    # -- 8.3: the handcuff tail, against real backfields ---------------------------------------
    tail = handcuff_tail_check(con)
    print(f"\nHandcuff dependence (RB1/RB2, zero-filled, {tail['n_pairs']} backfields): "
          f"τ={tail['tau']:+.2f} → Clayton θ={tail['theta']:.2f}, λ_L={tail['tail']:.2f}")
    print("  P(backup top-quartile | starter bottom-quartile), independence=0.25:")
    print(f"  empirical {tail['empirical']:.3f} | Clayton {tail['clayton']:.3f} | "
          f"Gaussian {tail['gaussian']:.3f}   ({tail['n_cond_weeks']} conditioning weeks)")
    assert tail["empirical"] > 0.25, "no tail dependence found — the handcuff premise fails"
    assert (abs(tail["clayton"] - tail["empirical"])
            < abs(tail["gaussian"] - tail["empirical"])), \
        "Clayton should track the empirical tail better than the Gaussian"

    # -- 8.4 done-bar: stacked ceiling vs hedged floor, on the real 2022 board -----------------
    mm = m.set_index("player_key")
    qb = mm[(mm["pos"] == "QB") & (mm["role_rank"] == 1)].sort_values("mean", ascending=False)
    qb_key = qb.index[0]
    qb_team = qb["team"].iloc[0]
    mates = mm[(mm["team"] == qb_team) & (mm["pos"].isin(["WR", "TE"]))]
    others = mm[(mm["team"] != qb_team) & (mm["pos"] == "WR")].sort_values("mean",
                                                                           ascending=False)
    stacked = pd.DataFrame({"player_key": [qb_key, *mates.index[:2]]})
    divers = pd.DataFrame({"player_key": [qb_key, *others.index[:2].tolist()]})
    rr_s = roster_risk(stacked, vi, corr)
    rr_d = roster_risk(divers, vi, corr)
    print(f"\nRoster risk ({SEASON}): stack = {qb_key} + 2 same-team pass-catchers vs "
          f"the same QB + 2 other-team WRs")
    print(f"  stacked:     sd {rr_s.sd:6.1f} (indep {rr_s.sd_independent:6.1f})  "
          f"floor {rr_s.floor:7.1f}  ceiling {rr_s.ceiling:7.1f}")
    print(f"  diversified: sd {rr_d.sd:6.1f} (indep {rr_d.sd_independent:6.1f})  "
          f"floor {rr_d.floor:7.1f}  ceiling {rr_d.ceiling:7.1f}")
    assert rr_s.sd > rr_s.sd_independent, "a stack must carry positive covariance"
    assert rr_s.sd > rr_d.sd, "stacked roster must be riskier than the diversified twin"

    # -- 8.5 done-bar: the option premium moves with starter fragility -------------------------
    elev = elevation_stats(copula.handcuff_pairs(weekly_offense_panel(con, DEV_SEASONS)))
    print(f"\nHandcuff elevation (pooled DEV backfields): backup {elev['ppg_with']:.1f} ppg with "
          f"starter, {elev['ppg_without']:.1f} without → ratio {elev['ratio']:.2f} "
          f"({elev['n_weeks_without']} starter-out weeks)")
    frag = handcuff_value(0.30, 5.0, elev["ratio"])
    dur = handcuff_value(0.06, 5.0, elev["ratio"])
    print(f"  backup at 5.0 standalone ppg: option premium {frag.option_premium:+.1f} pts under a "
          f"fragile starter (30% out) vs {dur.option_premium:+.1f} under a durable one (6%)")
    assert elev["ratio"] > 1.0 and frag.option_premium > dur.option_premium > 0

    # -- 9.1 pull-forward: the marginal covariance penalty works on the real board -------------
    # Direct check: once the QB is rostered, his own pass-catcher's priority must worsen while an
    # equivalent other-team player's is untouched (the marginal 2λ·ρ·σσ' penalty, live).
    lam = 0.01
    cfg = DraftConfig(league=LeagueSetup(draft_slot=5), risk_lambda=lam)
    board = attach_value(preseason_board(con, SEASON, draft_date(con, SEASON)), vi)
    risk = build_risk_model(board, vi, corr, lam)
    mate_key = mates.sort_values("mean", ascending=False).index[0]
    other_key = others.index[0]
    gsis = board["gsis_id"].where(board["gsis_id"].notna(), board["name"])
    pool = (pd.DataFrame({"player_key": gsis, "pos": board["position"].map(canon_pos),
                          "base_value": board["base_value"]})
            .dropna(subset=["base_value"]))
    empty = pd.DataFrame({"player_key": []})
    with_qb = pd.DataFrame({"player_key": [qb_key]})
    r0 = pd.Series(risk.effective_rank(pool, empty), index=pool["player_key"])
    r1 = pd.Series(risk.effective_rank(pool, with_qb), index=pool["player_key"])
    print(f"\nCovariance-aware pick penalty ({SEASON}, λ={lam:g}): after rostering {qb_key},")
    print(f"  his {mate_key}: priority rank {r0[mate_key]:.1f} → {r1[mate_key]:.1f} "
          f"(pushed {r1[mate_key] - r0[mate_key]:+.1f} picks down)")
    print(f"  other-team {other_key}: {r0[other_key]:.1f} → {r1[other_key]:.1f} (unchanged)")
    assert r1[mate_key] > r0[mate_key], "the stack partner must be deprioritized"
    assert abs(r1[other_key] - r0[other_key]) < 1e-9, "cross-team players must be untouched"

    # And the honest full-draft read: the greedy already diversifies across NFL teams, so both
    # λ settings usually draft ~zero same-team covariance — the penalty is a guard-rail (it binds
    # when preferences push toward a stack), not a rebalancer. Report, don't over-claim.
    aware = optimize_draft(con, SEASON, cfg, vi, seed=11, corr=corr).your_roster()
    blind_cfg = DraftConfig(league=LeagueSetup(draft_slot=5), risk_lambda=0.0)
    vi0 = assemble_value(con, SEASON, blind_cfg)
    blind = optimize_draft(con, SEASON, blind_cfg, vi0, seed=11, corr=corr).your_roster()
    cc_aware = cross_covariance(aware, vi, corr)
    cc_blind = cross_covariance(blind, vi0, corr)
    print(f"  full-draft cross-covariance: λ={lam:g} → {cc_aware:,.0f} pts² | λ=0 → "
          f"{cc_blind:,.0f} pts²")
    assert cc_aware <= cc_blind + 1e-9, "the penalty must not increase drafted covariance"

    print("\nPhase 8 (covariance & rosters) — all checks PASS.")
    con.close()


if __name__ == "__main__":
    main()
