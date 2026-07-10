"""Phase 10 — season/playoff sim: run + validate on real DEV seasons (the calibration gate).

    uv run python steps/phase10_sim.py                       # 2017-2022, 30 leagues, 500 sims
    uv run python steps/phase10_sim.py --leagues 10 --sims 300   # faster smoke run

THE done-bar (pipeline stage 1): **calibrated championship/playoff probabilities on DEV.**
For each DEV season with ≥3 training seasons behind it (2017–2022), draft ``--leagues``
ADP+noise leagues, compute each team's preseason playoff/title probability from the Monte-Carlo
engine (Phase-5 clouds + Phase-8 Σ + weekly grain), then play the *same* rosters and schedule
against **realized** weekly points and compare:

  1. Brier vs the format baselines (playoff 6/10 -> 0.24; title 1/10 -> 0.09) + reliability bins;
  2. team regular-season points: 80%-interval coverage + sim-vs-realized league spread;
  3. seed stability: playoff/title-prob rankings under a fresh set of sim draws (Spearman) —
     NB: ADP+noise leagues are near-exchangeable by construction, so true title-prob spreads
     are small and the title ranking is resolution-limited; playoff probs carry the gate;
  4. 10.3 leverage: at realized week-8 standings, added variance must RAISE the trailing
     team's playoff probability and LOWER the leader's (the make-the-cut direction; title-prob
     effects are ~neutral between equal-strength teams in a knockout and are reported only).

PIT: distributions/Σ/volatility/K-DST constants all train strictly < season; realized points
only ever score outcomes. Lockbox (2023/24) untouched.
"""

from __future__ import annotations

import argparse
import time

import numpy as np
import pandas as pd
from scipy import stats

from fantasy_quant.backtest.walkforward import (
    build_realized,
    draft_date,
    preseason_board,
    roster_weekly_points,
)
from fantasy_quant.data import db
from fantasy_quant.draft.simulator import RosterSlots, pick_by_adp, simulate_draft
from fantasy_quant.simulation.leverage import variance_leverage
from fantasy_quant.simulation.season import (
    LeagueFormat,
    rosters_weekly,
    round_robin_schedule,
    simulate_league,
)
from fantasy_quant.simulation.weekly import build_weekly_model

DEFAULT_SEASONS = range(2017, 2023)   # DEV tail: ≥3 train seasons behind each


def _noisy_adp_pick(state):
    """Your seat drafts like everyone else (ADP + noise) — league calibration wants 10
    exchangeable teams, not a hero seat."""
    return pick_by_adp(state, state.your_team, noise=5.0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--leagues", type=int, default=30)
    ap.add_argument("--sims", type=int, default=500)
    ap.add_argument("--seasons", type=int, nargs="*", default=list(DEFAULT_SEASONS))
    args = ap.parse_args()

    con = db.connect(read_only=True)
    fmt = LeagueFormat()
    slots = RosterSlots()
    rows, stab, lev_dog, lev_fav = [], [], [], []
    t0 = time.time()

    for season in args.seasons:
        wm = build_weekly_model(con, season, n_weeks=fmt.n_weeks)
        realized = build_realized(con, season)
        as_of = draft_date(con, season)
        board = preseason_board(con, season, as_of)
        n_cloud = sum(1 for k in wm.index)
        print(f"[{season}] weekly model: {n_cloud} clouds, byes={len(wm.byes)} teams, "
              f"K/DST wk = {wm.kdst['K']:.1f}/{wm.kdst['DST']:.1f}  "
              f"({time.time() - t0:.0f}s)")

        for lg in range(args.leagues):
            seed = season * 10_000 + lg
            rng = np.random.default_rng(seed)
            state = simulate_draft(board, your_pick_fn=_noisy_adp_pick, n_teams=fmt.n_teams,
                                   rounds=slots.total, slots=slots, your_team=lg % fmt.n_teams,
                                   noise=5.0, seed=seed)
            rosters = [state.roster(t) for t in range(fmt.n_teams)]
            schedule = round_robin_schedule(fmt.n_teams, fmt.reg_weeks, rng)
            sim_cols = rng.choice(wm.n_draws, args.sims, replace=False)
            tw = rosters_weekly(rosters, wm, sim_cols, slots, rng)
            sim = simulate_league(tw, fmt, schedule)

            # the same league, realized (survivorship-safe; n_sims = 1)
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
                # (3) seed stability: two independent estimates at 3x sims (resolution-fair)
                n_stab = min(3 * args.sims, wm.n_draws)
                sims2 = []
                for salt in (777, 888):
                    rng2 = np.random.default_rng(seed + salt)
                    cols2 = rng2.choice(wm.n_draws, n_stab, replace=False)
                    tw2 = rosters_weekly(rosters, wm, cols2, slots, rng2)
                    sims2.append(simulate_league(tw2, fmt, schedule))
                stab.append({
                    "playoff": stats.spearmanr(sims2[0].playoff_prob,
                                               sims2[1].playoff_prob).statistic,
                    "title": stats.spearmanr(sims2[0].title_prob,
                                             sims2[1].title_prob).statistic,
                })

            if lg < 3:
                # (4) leverage at realized week-8 standings, predicted futures
                wk = 8
                wins8 = np.zeros(fmt.n_teams)
                pf8 = np.zeros(fmt.n_teams)
                for w in range(wk):
                    mine = rw[:, 0, w]
                    theirs = mine[schedule[w]]
                    wins8 += np.where(mine > theirs, 1.0,
                                      np.where(mine == theirs, 0.5, 0.0))
                    pf8 += mine
                dog = int(np.argmin(wins8 * 1e9 + pf8))
                fav = int(np.argmax(wins8 * 1e9 + pf8))
                for team, sink in ((dog, lev_dog), (fav, lev_fav)):
                    curve = variance_leverage(tw, fmt, schedule, team, scales=(0.6, 1.0, 1.6),
                                              start_week=wk, wins0=wins8, pf0=pf8)
                    pp = curve.set_index("scale")["playoff_prob"]
                    tp = curve.set_index("scale")["title_prob"]
                    sink.append({"playoff": float(pp[1.6] - pp[0.6]),
                                 "title": float(tp[1.6] - tp[0.6])})

    con.close()
    df = pd.DataFrame(rows)
    n = len(df)
    print(f"\n=== calibration panel: {n} team-seasons "
          f"({df['season'].nunique()} seasons x {args.leagues} leagues x {fmt.n_teams} teams; "
          f"{time.time() - t0:.0f}s) ===")

    # (1) Brier + reliability
    briers = {}
    for name, pred, real, base_p in (("playoff", "pred_playoff", "real_playoff", 0.6),
                                     ("title", "pred_title", "real_title", 0.1)):
        brier = float(((df[pred] - df[real]) ** 2).mean())
        base = float(((base_p - df[real]) ** 2).mean())
        briers[name] = (brier, base)
        print(f"\n--- {name}: Brier {brier:.4f} vs constant-{base_p} baseline {base:.4f} "
              f"({'BEATS' if brier < base else 'DOES NOT BEAT'}) ---")
        edges = [0, .2, .4, .6, .8, 1.0001] if name == "playoff" else [0, .05, .1, .15, .25, 1.0001]
        binned = df.groupby(pd.cut(df[pred], edges), observed=True).agg(
            n=(real, "size"), predicted=(pred, "mean"), realized=(real, "mean"))
        print(binned.round(3).to_string())

    # (2) points coverage + league spread
    cover = float(((df["real_pf"] >= df["pf_lo"]) & (df["real_pf"] <= df["pf_hi"])).mean())
    spread_ratio = float(df["pred_pf_sd"].mean()
                         / df.groupby(["season", "league"])["real_pf"].std().mean())
    bias = float((df["pred_pf_mean"] - df["real_pf"]).mean())
    print(f"\n--- team reg-season points: 80%-interval coverage {cover:.1%} | "
          f"sim-sd / realized-cross-team-sd {spread_ratio:.2f} | mean bias {bias:+.0f} pts ---")

    # (3) stability, (4) leverage
    stab_po = float(np.mean([s["playoff"] for s in stab]))
    stab_ti = float(np.mean([s["title"] for s in stab]))
    print(f"--- ranking stability across fresh draws: playoff Spearman {stab_po:.3f}, "
          f"title {stab_ti:.3f} (title is resolution-limited between near-equal ADP teams) ---")
    dog_po = float(np.mean([d["playoff"] for d in lev_dog]))
    fav_po = float(np.mean([d["playoff"] for d in lev_fav]))
    dog_ti = float(np.mean([d["title"] for d in lev_dog]))
    fav_ti = float(np.mean([d["title"] for d in lev_fav]))
    print(f"--- leverage @ wk8, Δ(1.6x vs 0.6x) over {len(lev_dog)} leagues: trailing team "
          f"playoff {dog_po:+.4f} (title {dog_ti:+.4f}) | leader playoff {fav_po:+.4f} "
          f"(title {fav_ti:+.4f}) ---")

    gates = {
        "playoff_brier_beats_baseline": briers["playoff"][0] < briers["playoff"][1],
        "title_brier_beats_baseline": briers["title"][0] < briers["title"][1],
        "playoff_stability_spearman>=0.9": stab_po >= 0.9,
        "leverage_dog_playoff_gains": dog_po > 0,
        "leverage_fav_playoff_loses": fav_po < 0,
    }
    print("\n=== gates ===")
    for g, ok in gates.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {g}")
    print(f"  INFO  points coverage {cover:.1%} (Phase-5 unconditional-attrition limitation "
          f"applies; report, not a hard gate)")
    print(f"\n=== phase10_sim: {'PASS' if all(gates.values()) else 'REVIEW'} ===")


if __name__ == "__main__":
    main()
