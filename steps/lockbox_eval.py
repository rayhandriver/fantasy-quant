"""steps/lockbox_eval.py — the ONE-SHOT lockbox evaluation (and the 2025 dress rehearsal).

    uv run python steps/lockbox_eval.py --which dress                 # 2025 dress rehearsal (safe)
    uv run python steps/lockbox_eval.py --which lockbox               # 2023+2024 — RUN EXACTLY ONCE

╔══════════════════════════════════════════════════════════════════════════════════════════════╗
║  THE LOCKBOX (2023 + 2024) IS EVALUATED EXACTLY ONCE. The stack is FROZEN by the T5            ║
║  pre-registration (PLAN.md) before this runs — projection, distributions (incl. T3), Σ, the    ║
║  covariance-aware greedy (+S6/scarcity), the season sim (incl. T4 κ), the opponent model. No   ║
║  tuning, no re-runs, no "one more tweak" after this. Whatever it prints is reported as-is, with ║
║  the DEV-decision-count caveat (findings.md). PIT-clean ≠ out-of-sample-clean — this is the one ║
║  measurement of true external validity, so spending it twice destroys the claim it certifies.  ║
╚══════════════════════════════════════════════════════════════════════════════════════════════╝

Reports the whole reframe thesis on the held-out seasons (CLAUDE.md §1, the "honest value"):
  (1) **season/playoff sim** — the north-star: calibrated championship/playoff probabilities
      (title & playoff Brier vs the format baselines + reliability, points coverage, level bias,
      league-spread ratio, seed stability, wk-8 leverage direction). A faithful port of the frozen
      `steps/phase10_sim.py` loop, parameterised by the ADP board source (validated to reproduce it
      on a DEV season — see the module test / findings);
  (2) **projection calibration** — value = consensus→VBD: pooled bias, rank Spearman, MAE;
  (3) **cost-of-personalization** — realized-PAR archetype sweep + projected→realized cross-check
      (the personalization deliverable).

The **dress rehearsal** (`--which dress`) runs the identical harness on 2025 (the calibration
holdout) so the lockbox isn't the assembled system's first contact with unseen data. 2025 has no
FFC board, so its draft-dependent parts (sim, cost) run off the crawled ``sleeper_human`` board
(smaller — a rehearsal, not a verdict); projection calibration is board-free. T5 done-bar.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from fantasy_quant.backtest.walkforward import (
    build_realized,
    draft_date,
    preseason_board,
    roster_weekly_points,
)
from fantasy_quant.config import CALIBRATION_SEASONS, LOCKBOX_SEASONS
from fantasy_quant.data import db
from fantasy_quant.data.sources.adp import adp_asof
from fantasy_quant.draft.simulator import RosterSlots, pick_by_adp, simulate_draft
from fantasy_quant.projections.calibration import calibration_report
from fantasy_quant.projections.consensus import consensus_projection
from fantasy_quant.simulation.leverage import variance_leverage
from fantasy_quant.simulation.season import (
    LeagueFormat,
    rosters_weekly,
    round_robin_schedule,
    simulate_league,
)
from fantasy_quant.simulation.weekly import build_weekly_model
from fantasy_quant.valuation.cost_validation import validate_archetypes


def _noisy_adp_pick(state):
    """Every seat drafts ADP+noise — calibration wants exchangeable teams (as phase10_sim)."""
    return pick_by_adp(state, state.your_team, noise=5.0)


def _board_ffc(con, season):
    as_of = draft_date(con, season)
    return (preseason_board(con, season, as_of), as_of) if as_of is not None else (None, None)


def _board_source(con, season, source):
    """PIT board off a non-FFC ADP source (e.g. the crawled ``sleeper_human`` 2025 board)."""
    as_of = draft_date(con, season, source=source)
    if as_of is None:
        return None, None
    return adp_asof(con, season, as_of, source=source), as_of


# ------------------------------------------------------------------------------------------------
# (1) season/playoff sim — a faithful port of steps/phase10_sim.py, board source parameterised
# ------------------------------------------------------------------------------------------------
def season_sim_gate(con, seasons, board_fn, leagues: int = 30, sims: int = 500) -> dict:
    fmt = LeagueFormat()
    slots = RosterSlots()
    rows, stab, lev_dog, lev_fav = [], [], [], []
    for season in seasons:
        board, as_of = board_fn(con, season)
        if board is None:
            print(f"[{season}] no ADP board — skipping season sim")
            continue
        wm = build_weekly_model(con, season, n_weeks=fmt.n_weeks)
        realized = build_realized(con, season)
        print(f"[{season}] board {len(board)} rows @ {as_of.date()}, "
              f"weekly model {sum(1 for _ in wm.index)} clouds")
        for lg in range(leagues):
            seed = season * 10_000 + lg
            rng = np.random.default_rng(seed)
            state = simulate_draft(board, your_pick_fn=_noisy_adp_pick, n_teams=fmt.n_teams,
                                   rounds=slots.total, slots=slots, your_team=lg % fmt.n_teams,
                                   noise=5.0, seed=seed)
            rosters = [state.roster(t) for t in range(fmt.n_teams)]
            schedule = round_robin_schedule(fmt.n_teams, fmt.reg_weeks, rng)
            sim_cols = rng.choice(wm.n_draws, sims, replace=False)
            tw = rosters_weekly(rosters, wm, sim_cols, slots, rng)
            sim = simulate_league(tw, fmt, schedule)
            rw = np.stack([roster_weekly_points(r, realized, slots)[:fmt.n_weeks]
                           for r in rosters])[:, None, :]
            real = simulate_league(rw, fmt, schedule)
            q10, q90 = np.percentile(sim.points_for, [10, 90], axis=1)
            for t in range(fmt.n_teams):
                rows.append({
                    "season": season, "league": lg, "team": t,
                    "pred_playoff": float(sim.playoff_prob[t]),
                    "pred_title": float(sim.title_prob[t]),
                    "real_playoff": float(real.made_playoffs[t, 0]),
                    "real_title": float(real.champion[0] == t),
                    "pred_pf_mean": float(sim.points_for[t].mean()),
                    "pred_pf_sd": float(sim.points_for[t].std()),
                    "pf_lo": float(q10[t]), "pf_hi": float(q90[t]),
                    "real_pf": float(real.points_for[t, 0]),
                })
            if lg == 0:
                n_stab = min(3 * sims, wm.n_draws)
                s2 = []
                for salt in (777, 888):
                    rng2 = np.random.default_rng(seed + salt)
                    cols2 = rng2.choice(wm.n_draws, n_stab, replace=False)
                    tw2 = rosters_weekly(rosters, wm, cols2, slots, rng2)
                    s2.append(simulate_league(tw2, fmt, schedule))
                stab.append({
                    "playoff": stats.spearmanr(s2[0].playoff_prob, s2[1].playoff_prob).statistic,
                    "title": stats.spearmanr(s2[0].title_prob, s2[1].title_prob).statistic})
            if lg < 3:
                wk = 8
                wins8, pf8 = np.zeros(fmt.n_teams), np.zeros(fmt.n_teams)
                for w in range(wk):
                    mine = rw[:, 0, w]
                    theirs = mine[schedule[w]]
                    wins8 += np.where(mine > theirs, 1.0, np.where(mine == theirs, 0.5, 0.0))
                    pf8 += mine
                dog = int(np.argmin(wins8 * 1e9 + pf8))
                fav = int(np.argmax(wins8 * 1e9 + pf8))
                for team, sink in ((dog, lev_dog), (fav, lev_fav)):
                    curve = variance_leverage(tw, fmt, schedule, team, scales=(0.6, 1.0, 1.6),
                                              start_week=wk, wins0=wins8, pf0=pf8)
                    pp = curve.set_index("scale")["playoff_prob"]
                    sink.append({"playoff": float(pp[1.6] - pp[0.6])})

    df = pd.DataFrame(rows)
    if df.empty:
        return {"n": 0}
    briers = {}
    for name, pred, real, base_p in (("playoff", "pred_playoff", "real_playoff", 0.6),
                                     ("title", "pred_title", "real_title", 0.1)):
        brier = float(((df[pred] - df[real]) ** 2).mean())
        base = float(((base_p - df[real]) ** 2).mean())
        briers[name] = {"brier": brier, "baseline": base, "beats": brier < base}
    cover = float(((df["real_pf"] >= df["pf_lo"]) & (df["real_pf"] <= df["pf_hi"])).mean())
    spread_ratio = float(df["pred_pf_sd"].mean()
                         / df.groupby(["season", "league"])["real_pf"].std().mean())
    bias = float((df["pred_pf_mean"] - df["real_pf"]).mean())
    stab_po = float(np.mean([s["playoff"] for s in stab])) if stab else float("nan")
    dog_po = float(np.mean([d["playoff"] for d in lev_dog])) if lev_dog else float("nan")
    fav_po = float(np.mean([d["playoff"] for d in lev_fav])) if lev_fav else float("nan")
    return {
        "n_team_seasons": int(len(df)), "seasons": sorted(df["season"].unique().tolist()),
        "playoff_brier": briers["playoff"], "title_brier": briers["title"],
        "points_coverage": cover, "spread_ratio": spread_ratio, "level_bias": bias,
        "stability_playoff": stab_po, "leverage_dog_playoff": dog_po,
        "leverage_fav_playoff": fav_po,
    }


# ------------------------------------------------------------------------------------------------
# (2) projection calibration  &  (3) cost-of-personalization
# ------------------------------------------------------------------------------------------------
def projection_calibration(con, seasons) -> dict:
    rep = calibration_report(con, consensus_projection, list(seasons))
    return {"n": rep["n"], "overall_bias": float(rep["overall_bias"]),
            "spearman": float(rep["spearman"]), "mae": float(rep["mae"]),
            "by_position_bias": {k: float(v) for k, v in rep["by_position_bias"].items()}}


def distribution_coverage(con, seasons, ruleset=None) -> dict:
    """The assembled Phase-5 (+T3) distribution's realized 80%-interval coverage on ``seasons`` —
    board-free (the risk layer, "not just projections"). Unconditional counts a projected body who
    never plays (realized 0) as a miss (the attrition axis T3 targets); conditional restricts to
    players who actually played. Skill positions only (K/DST realized come from separate paths)."""
    from fantasy_quant.backtest import scoring
    from fantasy_quant.projections.distribution import cached_distribution
    covu, covc, n_u, n_c = [], [], 0, 0
    for s in seasons:
        dist = cached_distribution(con, s, ruleset)[0]
        dist = dist[dist["pos"].isin(["QB", "RB", "WR", "TE"])]
        real = scoring.season_points(con, s)[["gsis_id", "points", "weeks"]]
        m = dist.merge(real, left_on="player_key", right_on="gsis_id", how="left")
        m["points"] = m["points"].fillna(0.0)
        m["weeks"] = m["weeks"].fillna(0)
        inside = (m["points"] >= m["q10"]) & (m["points"] <= m["q90"])
        played = m["weeks"] > 0
        covu.append(float(inside.mean()))
        covc.append(float(inside[played].mean()) if played.any() else float("nan"))
        n_u += int(len(m))
        n_c += int(played.sum())
    return {"unconditional_coverage": float(np.mean(covu)),
            "conditional_coverage": float(np.nanmean(covc)),
            "n": n_u, "n_played": n_c}


def cost_report_par(con, seasons, k_drafts: int = 10) -> dict:
    # Sweep the static *preference* archetypes only: `bpa` is the value-optimal benchmark and
    # `adaptive` (S6) is a meta-wrapper needing an `adaptive_parent` — neither a standalone
    # preference to price (a harness scoping choice; the frozen stack is untouched).
    from fantasy_quant.draft.config import ADAPTIVE_PARENTS
    res = validate_archetypes(con, archetypes=list(ADAPTIVE_PARENTS), seasons=tuple(seasons),
                              k_drafts=k_drafts, n_boot=10000)
    per = [{"archetype": v.subject, "realized_cost": float(v.realized_cost),
            "ci": [float(v.ci.lo), float(v.ci.hi)]} for v in res.per_archetype]
    return {"n_drafts_each": res.per_archetype[0].n_drafts if res.per_archetype else 0,
            "per_archetype": per,
            "cross_spearman": float(res.cross.spearman),
            "cross_sign_agreement": float(res.cross.sign_agreement),
            "cross_n": int(res.cross.n)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--which", choices=["dress", "lockbox"], required=True)
    ap.add_argument("--leagues", type=int, default=30)
    ap.add_argument("--sims", type=int, default=500)
    ap.add_argument("--cost-drafts", type=int, default=10)
    ap.add_argument("--skip-cost", action="store_true", help="skip the (slow) cost-report sweep")
    args = ap.parse_args()

    if args.which == "lockbox":
        seasons, source = list(LOCKBOX_SEASONS), "ffc"
        board_fn = _board_ffc
        banner = ("LOCKBOX EVALUATION — 2023+2024 — EXACTLY ONCE. Stack frozen by the T5 "
                  "pre-registration; report as-is.")
        out_path = Path("analysis/lockbox_eval.json")
    else:
        seasons, source = list(CALIBRATION_SEASONS), "sleeper_human"
        board_fn = lambda c, s: _board_source(c, s, source)  # noqa: E731
        banner = ("2025 DRESS REHEARSAL (calibration holdout) — board-dependent parts off the "
                  "crawled sleeper_human board; a rehearsal, not a verdict.")
        out_path = Path("analysis/lockbox_dress_2025.json")

    print("=" * 96)
    print(f"  {banner}")
    print(f"  seasons={seasons}  board_source={source}  leagues={args.leagues}  sims={args.sims}")
    print("=" * 96)
    con = db.connect(read_only=True)
    t0 = time.time()

    print("\n--- (1) season/playoff sim (north-star) ---")
    sim_metrics = season_sim_gate(con, seasons, board_fn, leagues=args.leagues, sims=args.sims)
    print(f"    {json.dumps(sim_metrics, indent=2)}  ({time.time() - t0:.0f}s)")

    print("\n--- (2) projection calibration (value = consensus→VBD) ---")
    proj_metrics = projection_calibration(con, seasons)
    print(f"    n={proj_metrics['n']}  bias={proj_metrics['overall_bias']:.3f}  "
          f"Spearman={proj_metrics['spearman']:.3f}  MAE={proj_metrics['mae']:.2f}  "
          f"({time.time() - t0:.0f}s)")

    print("\n--- (2b) distribution 80%-interval coverage (Phase-5 + T3 risk layer) ---")
    dist_metrics = distribution_coverage(con, seasons)
    print(f"    unconditional {dist_metrics['unconditional_coverage']:.1%} "
          f"(n={dist_metrics['n']}) | conditional {dist_metrics['conditional_coverage']:.1%} "
          f"(n_played={dist_metrics['n_played']})  ({time.time() - t0:.0f}s)")

    cost_metrics = None
    if not args.skip_cost:
        print("\n--- (3) cost-of-personalization (realized-PAR archetype sweep) ---")
        cost_metrics = cost_report_par(con, seasons, k_drafts=args.cost_drafts)
        for p in cost_metrics["per_archetype"]:
            print(f"    {p['archetype']:14s} realized cost {p['realized_cost']:+7.1f} "
                  f"CI[{p['ci'][0]:+.0f},{p['ci'][1]:+.0f}]")
        print(f"    projected→realized: Spearman {cost_metrics['cross_spearman']:+.2f}, "
              f"sign agreement {cost_metrics['cross_sign_agreement']:.0%} "
              f"over {cost_metrics['cross_n']} subject-seasons  ({time.time() - t0:.0f}s)")

    con.close()
    report = {"which": args.which, "seasons": seasons, "board_source": source,
              "leagues": args.leagues, "sims": args.sims,
              "season_sim": sim_metrics, "projection_calibration": proj_metrics,
              "distribution_coverage": dist_metrics, "cost_report": cost_metrics}
    out_path.write_text(json.dumps(report, indent=2))
    print(f"\nwrote {out_path}  ({time.time() - t0:.0f}s)")
    if args.which == "lockbox":
        print("\n*** LOCKBOX SPENT. Do not modify the modeling stack or re-run. Report as-is. ***")


if __name__ == "__main__":
    main()
