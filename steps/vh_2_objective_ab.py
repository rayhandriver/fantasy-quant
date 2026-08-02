"""VH.2 — the interventional objective experiment (**T42**). Outcome and shape, reported apart.

    uv run python steps/vh_2_objective_ab.py --seeds 50 --seasons 2019 2020 2021 2022

Writes ``analysis/vh_objective_ab.json`` (+ ``.csv``, one row per team-season-arm).

★ **The question T28 answered was correlational; this one is interventional.** T28's bar B5 asked
*which roster-value definition best **correlates** with title probability* — ``team_value`` +0.8382
> ``portfolio_ce`` +0.8202 > ``starter_value`` +0.7971 — and used the ranking to decide what the
seat should **maximize**. *A relationship measured on outcomes is not a specification for the
mechanism that produced them.* Here the seat is actually **run** on each objective and the rosters
it builds are measured. A second reason B5 was blind to this: it pools ten seats, **nine of which
do not maximize the quantity at all**.

**The knob** is ``RiskModel.bench_weight`` (T28), and ``1.0`` nests the shipped greedy pick-for-pick
— so arm A is not a re-implementation of the shipped seat, it *is* the shipped seat. Only
``value_hawk`` reads ``risk``; every other seat is behavioural, so one knob moves one seat.

**Pre-registered — B3.** Outcome and shape are different claims and are never combined into one
score. Ship starter-awareness only if **shape improves AND outcome does not degrade beyond its
CI**. ⚠ If shape improves and outcome degrades, that is a **finding about the sim**, not a tuning
target: it draws injuries, and T28 measured **bench value alone predicting title +0.711**. Report
it; do not reweight.

  outcome   realized optimal-lineup points · starter_value · title / playoff **fair-share
            multiple** (T29: 10 teams, so 0.10 is par and every driver leads with the multiple,
            which is immune to the sim's −113 pts/team level bias)
  shape     QB2/TE2 taken before round 12 · ``capital − startable`` · the round RB1 arrives ·
            mean reach

Seating is **reshuffled per seed** (T24: a fixed arrangement measures *where the reachy seats sit*,
and more seeds do not fix it — it is a bias, not variance).
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from fantasy_quant.backtest.walkforward import build_realized, roster_season_points
from fantasy_quant.config import DEV_SEASONS
from fantasy_quant.draft import mock, optimizer
from fantasy_quant.draft.config import DraftConfig
from fantasy_quant.draft.personalities import REALISTIC_ROOM
from fantasy_quant.simulation.season import LeagueFormat, league_probabilities
from fantasy_quant.simulation.weekly import build_weekly_model

DB = Path("data/fantasy_quant.duckdb")
CACHE = Path("analysis/cache")
OUT = Path("analysis/vh_objective_ab.json")

#: DEV seasons with an FFC board — the same set T28 measured on, so the two are comparable.
DEV_MATCHED: tuple[int, ...] = (2019, 2020, 2021, 2022)
#: The arms. ``1.0`` is the shipped seat, exactly (T28's algebra collapses term-for-term).
ARMS: dict[str, float] = {"portfolio_ce": 1.0, "starter_aware": 0.0, "blend_50": 0.5}
#: "Early" for the shape metric — a backup taken before this round is the behaviour under test.
BACKUP_BEFORE_ROUND = 12
SINGLE_SLOT = ("QB", "TE")


def _shape(log: pd.DataFrame, team: int) -> dict:
    """The roster-shape metrics, from one seat's picks in draft order."""
    mine = log[log["team"] == team].sort_values("overall_pick")
    seen: dict[str, int] = {}
    backups_early = 0
    rb1_round = np.nan
    for _, r in mine.iterrows():
        pos, rnd = str(r["pos"]), int(r["round"])
        if pos in SINGLE_SLOT and seen.get(pos, 0) >= 1 and rnd < BACKUP_BEFORE_ROUND:
            backups_early += 1
        if pos == "RB" and np.isnan(rb1_round):
            rb1_round = rnd
        seen[pos] = seen.get(pos, 0) + 1
    return {"backups_early": int(backups_early),
            "rb1_round": float(rb1_round),
            "mean_reach": float((mine["adp"] - mine["overall_pick"]).mean())}


def _boot(a: np.ndarray, b: np.ndarray, n: int = 4000, seed: int = 0) -> dict:
    """Paired bootstrap of ``mean(a) - mean(b)`` over drafts (the pairing unit)."""
    rng = np.random.default_rng(seed)
    d = np.asarray(a, float) - np.asarray(b, float)
    d = d[np.isfinite(d)]
    if len(d) == 0:
        return {"diff": float("nan"), "lo": float("nan"), "hi": float("nan"), "n": 0}
    idx = rng.integers(0, len(d), size=(n, len(d)))
    boot = d[idx].mean(axis=1)
    return {"diff": float(d.mean()), "lo": float(np.percentile(boot, 2.5)),
            "hi": float(np.percentile(boot, 97.5)), "n": int(len(d))}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", type=int, default=50)
    ap.add_argument("--seasons", type=int, nargs="*", default=None)
    ap.add_argument("--rounds", type=int, default=15)
    ap.add_argument("--room-seed", type=int, default=17)
    ap.add_argument("--sims", type=int, default=300)
    ap.add_argument("--arms", type=str, nargs="*", default=None)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    seasons = tuple(args.seasons) if args.seasons else DEV_MATCHED
    bad = [s for s in seasons if s not in set(DEV_SEASONS)]
    if bad:
        raise SystemExit(f"{bad} are not DEV seasons — the lockbox stays shut (config.DEV_SEASONS)")
    arms = {k: ARMS[k] for k in (args.arms or list(ARMS))}

    con = duckdb.connect(str(DB), read_only=True)
    model = mock.load_opponent_model()
    config = DraftConfig()
    slots = config.league.slots
    fmt = LeagueFormat(n_teams=10)
    print(f"=== VH.2 — the interventional objective A/B · arms {list(arms)} ===")
    print(f"    {args.seeds} seeds x {len(seasons)} seasons = "
          f"{args.seeds * len(seasons)} drafts per arm, seating reshuffled per seed\n")

    rows: list[dict] = []
    for season in seasons:
        board, src = mock.room_board(con, season, cache_dir=CACHE)
        if board.empty:
            print(f"  {season}: no board, skipped")
            continue
        vi = optimizer.assemble_value(con, season, config)
        attached = optimizer.attach_value(board, vi)
        corr = optimizer.assemble_correlation(con, season)
        base_risk = optimizer.build_risk_model(attached, vi, corr, lam=config.risk_lambda)
        wm = build_weekly_model(con, season, config.league.ruleset, seed=0)
        realized = build_realized(con, season, config.league.ruleset)
        print(f"  {season} ({src}) ...", flush=True)

        for s in range(args.seeds):
            room = mock.full_room(REALISTIC_ROOM, n_teams=10, seed=args.room_seed + 1000 * s)
            for arm, bw in arms.items():
                risk = replace(base_risk, bench_weight=bw, slots=slots)
                st = mock.simulate_room_draft(attached, room, model, n_teams=10,
                                              rounds=args.rounds, seed=s, risk=risk, slots=slots)
                log = st.pick_log()
                rosters = [st.roster(t) for t in range(st.n_teams)]
                rng = np.random.default_rng(10_000 + s)
                pp, tp = league_probabilities(rosters, wm, fmt, slots, rng, sims=args.sims)
                for t, roster in enumerate(rosters):
                    cap = optimizer.team_value(roster, vi)
                    sv = optimizer.starter_value(roster, vi, slots)
                    rows.append({
                        "season": season, "seed": s, "arm": arm, "bench_weight": bw,
                        "team": t, "seat": room[t].name,
                        "realized_points": roster_season_points(roster, realized, slots),
                        "starter_value": sv, "team_value": cap,
                        "capital_minus_startable": cap - sv,
                        "title_multiple": float(tp[t]) * fmt.n_teams,
                        "playoff_multiple": float(pp[t]) * fmt.n_teams / 6.0,
                        **_shape(log, t),
                    })
        print(f"    -> {len([r for r in rows if r['season'] == season])} team-rows")

    df = pd.DataFrame(rows)
    if df.empty:
        raise SystemExit("no drafts scored")
    vh = df[df["seat"] == "value_hawk"].copy()

    # ===== the report — outcome and shape are printed apart, never combined ====================
    OUTCOME = ["realized_points", "starter_value", "title_multiple", "playoff_multiple"]
    SHAPE = ["backups_early", "capital_minus_startable", "rb1_round", "mean_reach"]
    base = "portfolio_ce"
    piv = vh.pivot_table(index=["season", "seed"], columns="arm",
                         values=OUTCOME + SHAPE, aggfunc="mean")

    result_arms: dict[str, dict] = {}
    for arm in arms:
        if arm == base:
            continue
        block = {"outcome": {}, "shape": {}}
        for m in OUTCOME:
            block["outcome"][m] = _boot(piv[(m, arm)].to_numpy(), piv[(m, base)].to_numpy())
        for m in SHAPE:
            block["shape"][m] = _boot(piv[(m, arm)].to_numpy(), piv[(m, base)].to_numpy())
        result_arms[arm] = block

    means = {arm: {m: float(vh.loc[vh["arm"] == arm, m].mean()) for m in OUTCOME + SHAPE}
             for arm in arms}
    for arm in arms:
        print(f"\n=== value_hawk on `{arm}` (bench_weight {arms[arm]}) ===")
        print("  OUTCOME  " + "  ".join(f"{m}={means[arm][m]:.3f}" for m in OUTCOME))
        print("  SHAPE    " + "  ".join(f"{m}={means[arm][m]:.3f}" for m in SHAPE))

    b3 = {}
    for arm, block in result_arms.items():
        print(f"\n=== {arm} − {base}, paired over {block['outcome'][OUTCOME[0]]['n']} drafts ===")
        print("  --- OUTCOME (a degradation beyond its CI blocks the ship) ---")
        for m, v in block["outcome"].items():
            flag = "" if (v["lo"] <= 0 <= v["hi"]) else ("  ** better" if v["diff"] > 0
                                                         else "  ** WORSE")
            print(f"    {m:<26} {v['diff']:+9.3f}  CI[{v['lo']:+.3f},{v['hi']:+.3f}]{flag}")
        print("  --- SHAPE (improvement is the reason to ship) ---")
        for m, v in block["shape"].items():
            flag = "" if (v["lo"] <= 0 <= v["hi"]) else "  **"
            print(f"    {m:<26} {v['diff']:+9.3f}  CI[{v['lo']:+.3f},{v['hi']:+.3f}]{flag}")

        # pre-registered: shape improves = fewer early backups + a smaller capital-startable gap
        shape_better = (block["shape"]["backups_early"]["hi"] < 0
                        or block["shape"]["capital_minus_startable"]["hi"] < 0)
        outcome_degraded = any(v["hi"] < 0 for v in block["outcome"].values())
        ship = bool(shape_better and not outcome_degraded)
        b3[arm] = {"shape_improved": shape_better, "outcome_degraded": outcome_degraded,
                   "ship": ship}
        print(f"  -> shape improved {shape_better} · outcome degraded {outcome_degraded} "
              f"· SHIP {ship}")

    art = {"generated": pd.Timestamp.now("UTC").isoformat(),
           "config": {"seeds": args.seeds, "seasons": list(seasons), "rounds": args.rounds,
                      "sims": args.sims, "room_seed": args.room_seed, "arms": arms,
                      "shuffled_seating": True, "backup_before_round": BACKUP_BEFORE_ROUND},
           "n_drafts_per_arm": int(len(piv)), "means": means, "contrasts": result_arms,
           "bars": {"B3": b3}}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(art, indent=2, default=str))
    df.to_csv(args.out.with_suffix(".csv"), index=False)
    print(f"\nwrote {args.out} (+ .csv, {len(df)} team-rows)")


if __name__ == "__main__":
    main()
