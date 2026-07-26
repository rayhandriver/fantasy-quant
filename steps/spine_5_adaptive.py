"""Personalization spine · step 6 — the adaptive archetype's done-bar, in sim.

    uv run python steps/spine_5_adaptive.py

Done when (ROADMAP): the adaptive wrapper **beats its static parent when the board diverges from
ADP, and does no harm when it doesn't**. We draft the same seat with the static parent (e.g.
``zero_rb``) and with ``adaptive``/<parent>, PIT on the DEV validation seasons, against two rooms:

  · an **ADP room** (the strict ADP+noise opponents) — the board honors ADP, so adaptive should
    reproduce its parent (gain ≈ 0, the do-no-harm control); and
  · a **behavioral room** (Phase-11 behavioral RB-faders + reachers) — the fitted opponent model
    drafts off its own behavioral utility, not ADP, so elite RBs slide past their ADP: a static
    Zero-RB keeps fading the value that fell to it while adaptive melts the fade and banks it. (That
    behavioral boards diverge sharply from ADP is itself the Phase-11 finding — this is the
    realistic room, and exactly the "board breaks" case adaptive is built for.)

Both rosters are scored by **team value** (Σ risk-adjusted VBD on one shared PIT value index — the
S3 cost yardstick), the gain (adaptive − parent) is block-bootstrapped over seasons, then split by
how far each draft's board diverged from ADP. Isolation: both seats run the *static* value path
(risk model off) so the only moving part is the archetype. Lockbox untouched (DEV window only).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fantasy_quant.backtest.walkforward import draft_date, preseason_board
from fantasy_quant.config import LOCKBOX_SEASONS
from fantasy_quant.data import db
from fantasy_quant.draft.config import DraftConfig, LeagueSetup
from fantasy_quant.draft.opponent_model import ALL_FEATURES, OpponentModel, build_choice_frame
from fantasy_quant.draft.optimizer import (
    DEFAULT_NOISE,
    assemble_value,
    attach_value,
    personalized_pick_fn,
    team_value,
)
from fantasy_quant.draft.personalities import make_opponent_pick_fn, personalities
from fantasy_quant.draft.simulator import simulate_draft
from fantasy_quant.valuation.cost_validation import VALIDATION_SEASONS

PARENTS = ("zero_rb", "hero_rb")   # the fade archetypes an adaptive wrapper can rescue value for
SEEDS = 6                          # matched-opponent draft replications per (season, room)
DIVERGENT_CYCLE = ("zero_rb", "reacher", "zero_rb", "reacher", "balanced")  # board-breaking room


def room_opponents(model: OpponentModel, my_seat: int, n_teams: int, kind: str):
    """One ``opponent_pick_fn(state, team)`` staffing every non-your seat — or ``None`` for the
    strict ADP room (the simulator then falls back to ADP+noise, which honors the board).

    ``behavioral`` = a mix of RB-faders and reachers off the fitted model (elite RBs slide) — the
    realistic, board-breaking room adaptive is built for. The sub-fns take no explicit rng, so they
    draw from the seeded draft state → matched across the static-vs-adaptive pair at a given seed
    (common random numbers)."""
    if kind == "adp":
        return None
    pers = personalities()
    others = [t for t in range(n_teams) if t != my_seat]
    assign = {t: pers[DIVERGENT_CYCLE[i % len(DIVERGENT_CYCLE)]] for i, t in enumerate(others)}
    fns = {t: make_opponent_pick_fn(model, p) for t, p in assign.items()}
    return lambda state, team: fns[team](state, team)


def draft_and_score(board: pd.DataFrame, value_index: pd.DataFrame, cfg: DraftConfig,
                    opp, my_seat: int, seed: int) -> tuple[float, float]:
    """Draft ``cfg``'s seat against room ``opp`` and return (team value, realized board divergence).

    Divergence = mean |overall_pick − ADP| over the whole draft, in rounds — how far the room
    drifted from a strict-ADP board (near 0 = ADP-tracking, large = the board broke)."""
    st = simulate_draft(board, your_pick_fn=personalized_pick_fn(cfg, DEFAULT_NOISE, None),
                        n_teams=cfg.league.n_teams, rounds=cfg.league.rounds,
                        slots=cfg.league.slots, your_team=my_seat, noise=DEFAULT_NOISE,
                        seed=seed, opponent_pick_fn=opp)
    log = st.pick_log()
    div = float((log["overall_pick"] - log["adp"]).abs().mean() / cfg.league.n_teams)
    return team_value(st.roster(my_seat), value_index), div


def _bootstrap_ci(vals, n_boot: int = 10000, seed: int = 0, alpha: float = 0.05):
    """Percentile CI of the mean by resampling the per-season block (spine_4 convention)."""
    v = np.asarray(vals, float)
    rng = np.random.default_rng(seed)
    means = v[rng.integers(0, len(v), (n_boot, len(v)))].mean(axis=1)
    return float(np.quantile(means, alpha / 2)), float(np.quantile(means, 1 - alpha / 2))


def main() -> None:
    assert not (set(VALIDATION_SEASONS) & set(LOCKBOX_SEASONS)), "lockbox must stay untouched"
    con = db.connect(read_only=True)

    print("Fitting the Phase-11 behavioral opponent model (human corpus) ...")
    # Same sampling budget and seed as steps/phase11_opponent_model.py, so the room S6 is validated
    # against is the room 11.1 reported — and so the frame fits in memory on the F.5 corpus.
    frame, _ = build_choice_frame(con, top_k=40, max_drafts_per_season=60, seed=11)
    model = OpponentModel(list(ALL_FEATURES), l2=1.0).fit(frame)

    lg = LeagueSetup(n_teams=10, draft_slot=5)          # a mid seat: slides have room to develop
    my_seat = lg.your_team

    # one PIT value index + value-attached board per season (archetype-independent → shared).
    print(f"Assembling PIT value boards for {list(VALIDATION_SEASONS)} ...")
    boards: dict[int, tuple] = {}
    for season in VALIDATION_SEASONS:
        as_of = draft_date(con, season)
        vi = assemble_value(con, season, DraftConfig(league=lg), as_of, seed=0)
        boards[season] = (attach_value(preseason_board(con, season, as_of), vi), vi)

    verdicts = []
    for parent in PARENTS:
        static = DraftConfig(league=lg, archetype=parent)
        adaptive = DraftConfig(league=lg, archetype="adaptive", adaptive_parent=parent)
        print(f"\n=== adaptive({parent})  vs  static {parent} "
              f"— {SEEDS} seeds × {len(VALIDATION_SEASONS)} seasons ===")
        rows = []
        for room in ("adp", "behavioral"):
            opp = room_opponents(model, my_seat, lg.n_teams, room)
            season_gain, season_div = [], []
            for season in VALIDATION_SEASONS:
                board, vi = boards[season]
                gains, divs = [], []
                for seed in range(SEEDS):
                    v_s, d_s = draft_and_score(board, vi, static, opp, my_seat, seed)
                    v_a, d_a = draft_and_score(board, vi, adaptive, opp, my_seat, seed)
                    gains.append(v_a - v_s)
                    divs.append(0.5 * (d_s + d_a))
                season_gain.append(float(np.mean(gains)))
                season_div.append(float(np.mean(divs)))
            lo, hi = _bootstrap_ci(season_gain)
            mean_gain = float(np.mean(season_gain))
            rows.append({"room": room, "mean_divergence_rounds": float(np.mean(season_div)),
                         "adaptive_minus_parent": mean_gain, "ci_lo": lo, "ci_hi": hi})
            print(f"  {room:10s}  board-divergence {np.mean(season_div):.2f} rd  |  "
                  f"Δteam-value (adaptive−{parent}) {mean_gain:+7.1f}  CI[{lo:+.1f},{hi:+.1f}]")

        adp = next(r for r in rows if r["room"] == "adp")
        beh = next(r for r in rows if r["room"] == "behavioral")
        no_harm = adp["ci_lo"] <= 0.0 <= adp["ci_hi"] or adp["adaptive_minus_parent"] >= 0
        wins_break = (beh["adaptive_minus_parent"] > adp["adaptive_minus_parent"]
                      and beh["ci_lo"] >= 0)
        board_broke = beh["mean_divergence_rounds"] > adp["mean_divergence_rounds"]
        ok = no_harm and wins_break and board_broke
        verdicts.append((parent, ok, beh["adaptive_minus_parent"], beh["ci_lo"]))
        phrase = ("does no harm on an ADP board and BANKS value when it breaks" if ok
                  else "did not clear the done-bar for this parent")
        print(f"  reading: adaptive {phrase} "
              f"(+{beh['adaptive_minus_parent']:.1f} team-value in the behavioral room).")

    # structural gates (not 'the gain is huge' — a modest nudge is the design).
    assert all(v[1] for v in verdicts), f"a parent failed the adaptive done-bar: {verdicts}"
    print("\nSpine step 6 (adaptive archetype) — done-bar PASS for:",
          ", ".join(f"adaptive({v[0]})" for v in verdicts))
    con.close()


if __name__ == "__main__":
    main()
