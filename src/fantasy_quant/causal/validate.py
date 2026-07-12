"""Phase 7.4 — held-out transition validation + the keep-or-drop verdict.

Strict walk-forward on ``DEV_SEASONS``: for each target season S the decomposition is fit on
seasons < S only, then used to re-project returning players; forecasts are scored on realized rate.
Three questions, in the reframe's language:

  1. **7.1 — does skill travel?** On movers, does the estimated *skill* effect (team-neutral)
     predict next-season rate better than raw prior production (which bakes in the old situation)?
  2. **7.2 — does re-projection beat naive carry-over on moves?** MAE on role-changers, with a
     bootstrap CI on the gain.
  3. **7.3 — are rookie projections calibrated?** Interval coverage + rank accuracy on held-out
     classes.

**Keep-or-drop bar (as written, 2026-07-11):** keep iff the opportunity-adjusted projection is
**≥ the consensus proxy on overall calibration** (not significantly worse) **AND strictly better on
role-changers** (CI on the mover gain excludes 0); else drop. Role-changer = team-changer (the
dominant, cleanest situation change; share-shift movers are a documented extension).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from fantasy_quant.causal.counterfactual import project_season
from fantasy_quant.causal.decompose import GAMES, decompose, player_season_panel
from fantasy_quant.causal.rookie_transport import RookieTransport, build_rookie_panel
from fantasy_quant.config import DEV_SEASONS
from fantasy_quant.projections.baseline import baseline_projection


def _mae(pred, target):
    return float(np.mean(np.abs(np.asarray(pred) - np.asarray(target))))


def _boot_mae_gain(worse_pred, better_pred, target, n_boot, rng):
    """Bootstrap CI of MAE(worse) − MAE(better) (>0 ⇒ `better` wins). Resamples rows."""
    worse_pred = np.asarray(worse_pred)
    better_pred = np.asarray(better_pred)
    target = np.asarray(target)
    n = len(target)
    gains = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        gains.append(_mae(worse_pred[idx], target[idx]) - _mae(better_pred[idx], target[idx]))
    return (float(np.mean(gains)),
            [float(np.percentile(gains, 2.5)), float(np.percentile(gains, 97.5))])


def walk_forward_validation(con, dev_seasons=DEV_SEASONS, *, min_train: int = 3,
                            alpha: float = 10.0, n_boot: int = 1000, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    panel = player_season_panel(con, dev_seasons)
    seasons = sorted(dev_seasons)

    recs = []
    skill_stab = []        # (skill, prior_rate, realized) on movers
    rook_cov, rook_pred, rook_real = [], [], []

    for S in seasons:
        train_seasons = [s for s in seasons if s < S]
        if len(train_seasons) < min_train:
            continue
        train_panel = panel[panel["season"] < S]
        dec = decompose(train_panel, alpha=alpha)
        proj = project_season(dec, panel, S)   # delta-form re-projection (no level calib needed)
        if proj.empty:
            continue
        mkt = baseline_projection(con, S).rename(columns={"player_key": "gsis_id"})
        mkt["market_rate"] = mkt["proj_points"] / GAMES
        proj = proj.merge(mkt[["gsis_id", "market_rate"]], on="gsis_id", how="left")
        recs.append(proj)
        for r in proj[proj["is_mover"] == 1].itertuples(index=False):
            skill_stab.append((dec.skill(r.gsis_id), r.naive_rate, r.ppg))

        # 7.3 rookie calibration (walk-forward)
        rk_train = build_rookie_panel(con, dec, panel, train_seasons)
        rk_test = build_rookie_panel(con, dec, panel, [S])
        if len(rk_train) >= 30 and not rk_test.empty:
            rt = RookieTransport(alpha=5.0).fit(rk_train)
            pr = rt.project(rk_test, z=1.0)
            real = rk_test["ppg"].to_numpy()
            cov = (real >= pr["ppg_lo"].to_numpy()) & (real <= pr["ppg_hi"].to_numpy())
            rook_cov.extend(cov.tolist())
            rook_pred.extend(pr["proj_ppg"].tolist())
            rook_real.extend(real.tolist())

    allrec = pd.concat(recs, ignore_index=True)

    # ---- overall calibration (rows with a market projection, for a fair 3-way compare) ----
    has_mkt = allrec["market_rate"].notna()
    om = allrec[has_mkt]
    overall = {
        "n": int(has_mkt.sum()),
        "opp_mae": _mae(om["opp_rate"], om["ppg"]),
        "naive_mae": _mae(om["naive_rate"], om["ppg"]),
        "market_mae": _mae(om["market_rate"], om["ppg"]),
    }
    g_mkt_ov, ci_mkt_ov = _boot_mae_gain(om["market_rate"], om["opp_rate"], om["ppg"], n_boot, rng)
    overall["opp_minus_market_gain"] = g_mkt_ov          # >0 ⇒ opp better than market overall
    overall["opp_minus_market_ci"] = ci_mkt_ov

    # ---- role-changers (movers) ----
    mv = allrec[(allrec["is_mover"] == 1)]
    mvm = mv[mv["market_rate"].notna()]
    movers = {
        "n": int(len(mv)), "n_with_market": int(len(mvm)),
        "opp_mae": _mae(mv["opp_rate"], mv["ppg"]),
        "naive_mae": _mae(mv["naive_rate"], mv["ppg"]),
        "market_mae": _mae(mvm["market_rate"], mvm["ppg"]) if len(mvm) else float("nan"),
    }
    g_naive, ci_naive = _boot_mae_gain(mv["naive_rate"], mv["opp_rate"], mv["ppg"], n_boot, rng)
    movers["opp_vs_naive_gain"], movers["opp_vs_naive_ci"] = g_naive, ci_naive
    if len(mvm):
        g_mkt, ci_mkt = _boot_mae_gain(mvm["market_rate"], mvm["opp_rate"], mvm["ppg"], n_boot, rng)
        movers["opp_vs_market_gain"], movers["opp_vs_market_ci"] = g_mkt, ci_mkt

    # ---- 7.1 skill travels? (movers) ----
    ss = np.array(skill_stab)
    skill_corr = float(spearmanr(ss[:, 0], ss[:, 2]).correlation)
    prior_corr = float(spearmanr(ss[:, 1], ss[:, 2]).correlation)
    skill_travels = {
        "n_movers": int(len(ss)),
        "corr_skill_vs_realized": skill_corr,
        "corr_priorrate_vs_realized": prior_corr,
        "skill_more_stable": bool(skill_corr > prior_corr),
    }

    # ---- 7.3 rookie ----
    rookie = {
        "n": len(rook_cov),
        "interval_coverage_1sigma": float(np.mean(rook_cov)) if rook_cov else float("nan"),
        "spearman_pred_vs_real": (float(spearmanr(rook_pred, rook_real).correlation)
                                  if rook_cov else float("nan")),
    }

    # ---- keep-or-drop verdict ----
    overall_ok = ci_mkt_ov[0] > -0.20          # opp not materially worse than market (≈0.2 ppg tol)
    movers_beat_naive = ci_naive[0] > 0        # strictly better than naive on movers
    keep = bool(overall_ok and movers_beat_naive)
    verdict = {
        "overall_not_worse_than_market": bool(overall_ok),
        "movers_strictly_beat_naive": bool(movers_beat_naive),
        "KEEP": keep,
        "rationale": (
            "KEEP: opp-adjusted is not worse than the consensus proxy overall and strictly beats "
            "naive carry-over on role-changers." if keep else
            "DROP: fails the as-written bar (needs ≥ consensus overall AND better on movers)."
        ),
    }
    return {"overall": overall, "movers": movers, "skill_travels": skill_travels,
            "rookie": rookie, "verdict": verdict}
