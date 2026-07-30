"""Phase 11.2 — the MCTS research gate: does lookahead search beat the Phase-9 greedy?

    uv run python steps/phase11_2_mcts.py                       # 2020-2022 x slots 1/6/10, k5 i100
    uv run python steps/phase11_2_mcts.py --iters 40 --slots 1  # faster smoke

The **explicit research-gate** the pipeline parks just before the lockbox (ROADMAP ★ THE PIPELINE
stage 9; CFR stays dropped). The reframe's standing hypothesis is that a snake draft is
near-perfect-information, so a covariance-aware greedy with 9.1/9.4 scarcity+lookahead already
captures the plannable value and heavy MCTS does not pay (and carries live-latency risk). This
*measures* it: from each seat we draft the same PIT board twice against the same ADP+noise room
(common random numbers) — once with the greedy (`personalized_pick_fn`), once with determinized-UCT
MCTS (`mcts_pick_fn`) whose rollouts and leaf value ARE that greedy and its portfolio-CE objective —
and compare on three lenses:

  1. **portfolio CE** of the drafted roster (the in-objective both climb — a positive Δ means the
     search found a better plan for the very thing the greedy optimises);
  2. **realized optimal-lineup season points** (the OOS ground truth — the honest keep-or-drop);
  3. predicted **playoff/title probability** from an independent Phase-10 sim (the north-star lens).

Plus **seconds/pick** — the live-latency budget an MCTS assistant would have to meet.

Keep-or-drop (as-written bar): **KEEP** iff MCTS beats the greedy on realized points OOS with a
season-block bootstrap CI clear of 0 *and* meets a plausible live budget; else **DROP** (kept in
repo like Phase 7 / props / CFR). PIT: value/Σ/distributions/sim all train strictly < season; DEV
only, lockbox untouched.
"""

from __future__ import annotations

import argparse
import time

import numpy as np

from fantasy_quant.backtest.significance import block_bootstrap_ci
from fantasy_quant.backtest.walkforward import (
    build_realized,
    draft_date,
    preseason_board,
    roster_weekly_points,
)
from fantasy_quant.config import DEV_SEASONS
from fantasy_quant.data import db
from fantasy_quant.draft.config import DraftConfig, LeagueSetup
from fantasy_quant.draft.mcts import mcts_pick_fn
from fantasy_quant.draft.optimizer import (
    assemble_correlation,
    assemble_value,
    attach_value,
    build_risk_model,
    personalized_pick_fn,
    portfolio_value,
)
from fantasy_quant.draft.simulator import RosterSlots, simulate_draft
from fantasy_quant.simulation.season import (
    LeagueFormat,
    league_probabilities,
    provenance_lines,
)
from fantasy_quant.simulation.weekly import build_weekly_model

DEFAULT_SEASONS = (2020, 2021, 2022)      # DEV tail, ≥3 training seasons behind each
DEFAULT_SLOTS = (1, 6, 10)                # early / middle / late seat


def _realized_points(roster, realized, slots) -> float:
    """A drafted roster's realized optimal-lineup **season total** — the OOS ground truth."""
    return float(np.asarray(roster_weekly_points(roster, realized, slots)).sum())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", type=int, nargs="*", default=list(DEFAULT_SEASONS))
    ap.add_argument("--slots", type=int, nargs="*", default=list(DEFAULT_SLOTS))
    ap.add_argument("--iters", type=int, default=100, help="MCTS iterations per pick")
    ap.add_argument("--k", type=int, default=5, help="top-K branching width")
    ap.add_argument("--eval-sims", type=int, default=600, help="independent sim worlds for lens 3")
    args = ap.parse_args()

    assert not (set(args.seasons) & {2023, 2024}), "lockbox (2023/24) stays untouched"
    con = db.connect(read_only=True)
    slots_cfg = RosterSlots()
    fmt = LeagueFormat()
    t0 = time.time()
    rows, pick_secs = [], []

    for season in args.seasons:
        assert season in DEV_SEASONS, f"{season} not a DEV season"
        base = DraftConfig(league=LeagueSetup(draft_slot=1))
        vi = assemble_value(con, season, base, seed=0)          # T6 shared cloud
        corr = assemble_correlation(con, season, base.league.ruleset)
        board = attach_value(preseason_board(con, season, draft_date(con, season)), vi)
        realized = build_realized(con, season)
        wm = build_weekly_model(con, season, base.league.ruleset, seed=0)
        lam = base.risk_lambda

        def value_fn(roster, _vi=vi, _corr=corr, _lam=lam):
            return portfolio_value(roster, _vi, _corr, _lam)

        for slot in args.slots:
            seat = LeagueSetup(draft_slot=slot)
            cfg = DraftConfig(league=seat)
            risk = build_risk_model(board, vi, corr, cfg.risk_lambda, noise=5.0)
            kw = dict(n_teams=seat.n_teams, rounds=seat.rounds, slots=slots_cfg,
                      your_team=seat.your_team, noise=5.0, seed=season * 100 + slot)

            g_state = simulate_draft(board, your_pick_fn=personalized_pick_fn(cfg, 5.0, risk), **kw)

            tp0 = time.time()
            m_pick = mcts_pick_fn(cfg, risk, value_fn, n_iter=args.iters, k=args.k,
                                  noise=5.0, seed=kw["seed"])
            m_state = simulate_draft(board, your_pick_fn=m_pick, **kw)
            pick_secs.append((time.time() - tp0) / seat.rounds)

            me = seat.your_team
            g_ros = [g_state.roster(t) for t in range(seat.n_teams)]
            m_ros = [m_state.roster(t) for t in range(seat.n_teams)]
            g_pp, g_tp = league_probabilities(g_ros, wm, fmt, slots_cfg,
                                              np.random.default_rng(99), sims=args.eval_sims)
            m_pp, m_tp = league_probabilities(m_ros, wm, fmt, slots_cfg,
                                              np.random.default_rng(99), sims=args.eval_sims)
            rows.append({
                "season": season, "slot": slot,
                "ce_g": portfolio_value(g_state.your_roster(), vi, corr, lam),
                "ce_m": portfolio_value(m_state.your_roster(), vi, corr, lam),
                "real_g": _realized_points(g_state.your_roster(), realized, slots_cfg),
                "real_m": _realized_points(m_state.your_roster(), realized, slots_cfg),
                "pp_g": float(g_pp[me]), "pp_m": float(m_pp[me]),
                "tp_g": float(g_tp[me]), "tp_m": float(m_tp[me]),
            })
            r = rows[-1]
            print(f"[{season} slot {slot:2d}]  CE {r['ce_g']:7.1f}->{r['ce_m']:7.1f}  "
                  f"realized {r['real_g']:6.0f}->{r['real_m']:6.0f}  "
                  f"playoff {r['pp_g']:.3f}->{r['pp_m']:.3f}  ({time.time() - t0:.0f}s)")

    con.close()
    import pandas as pd
    df = pd.DataFrame(rows)
    d_ce = (df["ce_m"] - df["ce_g"]).to_numpy()
    d_real = (df["real_m"] - df["real_g"]).to_numpy()
    d_pp = (df["pp_m"] - df["pp_g"]).to_numpy()
    d_tp = (df["tp_m"] - df["tp_g"]).to_numpy()
    ci_real = block_bootstrap_ci(d_real, expected_block=1)
    ci_ce = block_bootstrap_ci(d_ce, expected_block=1)

    n = len(df)
    print(f"\n=== MCTS vs greedy over {n} seat-seasons "
          f"({df['season'].nunique()} seasons x {len(args.slots)} slots; "
          f"k={args.k}, iters={args.iters}; {time.time() - t0:.0f}s) ===")
    print(f"  Δ portfolio CE   (in-objective): mean {d_ce.mean():+7.2f}  "
          f"CI[{ci_ce.lo:+.2f},{ci_ce.hi:+.2f}]  win-rate {np.mean(d_ce >= -1e-9):.0%}")
    print(f"  Δ realized pts   (OOS truth)   : mean {d_real.mean():+7.1f}  "
          f"CI[{ci_real.lo:+.1f},{ci_real.hi:+.1f}]  win-rate {np.mean(d_real > 0):.0%}")
    print("\n".join(provenance_lines(args.sims if hasattr(args, "sims") else 0)))
    print(f"  Δ playoff prob   (north-star)  : mean {d_pp.mean():+.4f}  "
          f"win-rate {np.mean(d_pp > 0):.0%}")
    print(f"  Δ title prob                   : mean {d_tp.mean():+.4f}")
    print(f"  live budget: {np.mean(pick_secs):.2f}s/pick (max {np.max(pick_secs):.2f}s)")

    beats_oos = ci_real.lo > 0
    verdict = "KEEP" if beats_oos else "DROP"
    print("\n=== gate (as-written bar) ===")
    print(f"  MCTS beats greedy on realized pts OOS (CI clear of 0): {beats_oos}")
    tag = "search pays" if beats_oos else "near-perfect-info thesis holds — greedy is enough"
    print(f"\n=== phase11_2_mcts VERDICT: {verdict} ({tag}) ===")

    import json
    from pathlib import Path
    out = {
        "seasons": list(args.seasons), "slots": list(args.slots), "k": args.k, "iters": args.iters,
        "n_seat_seasons": n,
        "delta_ce_mean": float(d_ce.mean()), "delta_ce_ci": [ci_ce.lo, ci_ce.hi],
        "delta_realized_mean": float(d_real.mean()), "delta_realized_ci": [ci_real.lo, ci_real.hi],
        "delta_realized_winrate": float(np.mean(d_real > 0)),
        "delta_playoff_mean": float(d_pp.mean()), "delta_title_mean": float(d_tp.mean()),
        "sec_per_pick_mean": float(np.mean(pick_secs)),
        "verdict": verdict,
    }
    Path("analysis/phase11_mcts.json").write_text(json.dumps(out, indent=2))
    print("wrote analysis/phase11_mcts.json")


if __name__ == "__main__":
    main()
