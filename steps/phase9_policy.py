"""Phase 9 completion — the draft policy: scarcity/lookahead greedy + the win-prob objective.

    uv run python steps/phase9_policy.py                 # 2022 (DEV), k=5, 200 sims/pick
    uv run python steps/phase9_policy.py --k 4 --sims 60 # faster smoke

NB the *title* objective is resolution-limited: title is a ~1-in-10 event, so
`championship_or_bust` needs a healthy ``--sims`` (≥~200) or it chases sim noise instead of
ceiling; `make_playoffs` (a 6-in-10 event) resolves at far fewer. On 2022 at 250 sims the
title-max board carries +0.09 title prob over the playoff-max board on an independent eval.

Done-bar (T8a): **switching `DraftConfig.objective` measurably changes the drafted roster**,
consuming the calibrated Phase-10 probabilities. We draft the same seat/board twice —
`make_playoffs` (maximize playoff prob) vs `championship_or_bust` (maximize title prob) — through
the opt-in win-probability policy (portfolio-CE/scarcity prefilter → top-k greedy-completion
rollout → Phase-10 mini-sim), show the rosters differ, and evaluate each with an independent sim.

Also shows 9.1/9.4: the scarcity+lookahead greedy vs the covariance-only greedy on the same board.
PIT: value/Σ/distributions/sim all train strictly < SEASON; DEV only, lockbox untouched.
"""

from __future__ import annotations

import argparse
import time

import numpy as np

from fantasy_quant.config import DEV_SEASONS
from fantasy_quant.data import db
from fantasy_quant.draft.config import DraftConfig, LeagueSetup
from fantasy_quant.draft.optimizer import assemble_value, build_risk_model, optimize_draft
from fantasy_quant.simulation.season import (
    LeagueFormat,
    fair_share,
    league_probabilities,
    playoff_fair_share,
    provenance_lines,
)
from fantasy_quant.simulation.weekly import build_weekly_model

SEASON = 2022


def _roster_keys(state) -> list[str]:
    return state.pick_log().query("is_you")["player_key"].tolist()


def _show(state, name_map) -> None:
    log = state.pick_log().query("is_you")
    for r in log.itertuples(index=False):
        print(f"    R{r.round:<2d} {name_map.get(r.player_key, r.player_name):22s} {r.pos:3s} "
              f"(adp {r.adp:.0f})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=5, help="win-prob prefilter width (candidates/pick)")
    ap.add_argument("--sims", type=int, default=200, help="mini-sim worlds per candidate")
    ap.add_argument("--eval-sims", type=int, default=600, help="independent evaluation worlds")
    args = ap.parse_args()

    assert SEASON in DEV_SEASONS, "stay out of the lockbox / holdout during development"
    con = db.connect(read_only=True)
    t0 = time.time()
    seat = LeagueSetup(draft_slot=5)
    base = DraftConfig(league=seat)
    vi = assemble_value(con, SEASON, base, seed=0)          # T6: one shared draw cloud (seed 0)
    name_map = dict(zip(vi["player_key"], vi["player_key"], strict=False))  # keys are gsis

    # ---- 9.1/9.4 — scarcity + lookahead vs the covariance-only greedy (fast, myopic) -----------
    from fantasy_quant.backtest.walkforward import draft_date, preseason_board
    from fantasy_quant.draft.optimizer import (
        assemble_correlation,
        attach_value,
        personalized_pick_fn,
    )
    from fantasy_quant.draft.simulator import simulate_draft
    as_of = draft_date(con, SEASON)
    board = attach_value(preseason_board(con, SEASON, as_of), vi)
    corr = assemble_correlation(con, SEASON, seat.ruleset)
    plain = build_risk_model(board, vi, corr, base.risk_lambda, scarcity_w=0.0)
    scar = build_risk_model(board, vi, corr, base.risk_lambda)   # default scarcity on
    kw = dict(n_teams=seat.n_teams, rounds=seat.rounds, slots=seat.slots,
              your_team=seat.your_team, noise=5.0, seed=0)
    r_plain = _roster_keys(simulate_draft(board, personalized_pick_fn(base, 5.0, plain), **kw))
    r_scar = _roster_keys(simulate_draft(board, personalized_pick_fn(base, 5.0, scar), **kw))
    n_scar_diff = sum(a != b for a, b in zip(r_plain, r_scar, strict=False))
    print(f"[{SEASON}] 9.1/9.4 scarcity+lookahead vs covariance-only greedy: "
          f"{n_scar_diff}/{len(r_plain)} picks differ  ({time.time() - t0:.0f}s)")

    # ---- 9.5 — the win-probability objective (opt-in) ------------------------------------------
    drafts = {}
    for obj in ("make_playoffs", "championship_or_bust"):
        cfg = DraftConfig(league=seat, objective=obj)
        st = optimize_draft(con, SEASON, cfg, value_index=vi, seed=0, winprob=True,
                            winprob_k=args.k, winprob_sims=args.sims)
        drafts[obj] = st
        print(f"\n[{SEASON}] objective={obj}  ({time.time() - t0:.0f}s)")
        _show(st, name_map)

    r_pl = _roster_keys(drafts["make_playoffs"])
    r_ti = _roster_keys(drafts["championship_or_bust"])
    n_obj_diff = len(set(r_pl) ^ set(r_ti)) // 2 + abs(len(set(r_pl)) - len(set(r_ti)))
    print(f"\nobjective swing: {n_obj_diff} roster slots differ between make_playoffs and "
          "championship_or_bust")

    # ---- independent evaluation: each drafted league scored on a fresh, larger sim --------------
    wm = build_weekly_model(con, SEASON, seat.ruleset, seed=0)   # same seed → shared draws (T6)
    fmt = LeagueFormat(n_teams=seat.n_teams)
    print("\n".join(provenance_lines(args.eval_sims, fmt)))
    for obj, st in drafts.items():
        rosters = [st.roster(t) for t in range(seat.n_teams)]
        pp, tp = league_probabilities(rosters, wm, fmt, seat.slots, np.random.default_rng(99),
                                      sims=args.eval_sims)
        me = seat.your_team
        # T29: lead with the fair-share multiple — the sim's level bias moves all ten teams
        # together, so it cancels in a ratio to the uniform and survives in the percentage.
        print(f"  {obj:22s} your seat: playoff {playoff_fair_share(pp, fmt)[me]:.2f}x "
              f"({pp[me]:.3f})  title {fair_share(tp, fmt.n_teams)[me]:.2f}x ({tp[me]:.3f})")

    # ---- gates --------------------------------------------------------------------------------
    gates = {
        "scarcity_changes_the_board": n_scar_diff >= 1,
        "objective_changes_the_roster": n_obj_diff >= 1,
        "rosters_are_full": all(len(_roster_keys(st)) == seat.rounds for st in drafts.values()),
    }
    print("\n=== gates ===")
    for g, ok in gates.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {g}")
    print(f"\n=== phase9_policy: {'PASS' if all(gates.values()) else 'REVIEW'} "
          f"({time.time() - t0:.0f}s) ===")
    con.close()


if __name__ == "__main__":
    main()
