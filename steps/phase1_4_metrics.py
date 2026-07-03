"""Phase 1.4 — PAR metric scorer, run + verify (the harness's headline number).

    uv run python steps/phase1_4_metrics.py

Done when (BUILD_PLAN.md 1.4): PAR ranks an obviously-good roster above an obviously-bad one;
replacement levels are documented. Secondary metrics (expected wins, final standing) demonstrated.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fantasy_quant.backtest import scoring
from fantasy_quant.backtest.metrics import (
    expected_wins,
    final_standings,
    par,
    replacement_levels,
)
from fantasy_quant.backtest.walkforward import (
    build_realized,
    draft_date,
    preseason_board,
    roster_season_points,
    roster_weekly_points,
)
from fantasy_quant.data import db
from fantasy_quant.data.sources.adp import adp_asof
from fantasy_quant.draft.simulator import RosterSlots, simulate_draft, value_pick_fn

SEASON = 2023
_OFF = {"QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE", "FB": "RB", "HB": "RB"}


def main() -> None:
    con = db.connect(read_only=True)
    slots = RosterSlots()
    realized = build_realized(con, SEASON)

    # -- replacement levels (resolves the PLAN.md open question) ------------------------------
    repl = replacement_levels(con, SEASON, slots)
    print(f"=== replacement levels — 10-team 9-starter, {SEASON} (season points) ===")
    for pos in ("QB", "RB", "WR", "TE", "K", "DST"):
        b = repl.by_pos[pos]
        print(f"  {pos:<4} rank {b['rank']:>2}  ->  {b['level']:>6.1f} pts")
    print(f"  replacement roster total: {repl.roster_total:.1f} pts")
    assert all(repl.by_pos[p]["level"] > 0 for p in repl.by_pos), "a replacement level is <= 0"
    assert 800 < repl.roster_total < 2000, f"implausible replacement total {repl.roster_total}"
    print()

    # -- PAR ranks an obviously-good roster above an obviously-bad one (the done-criterion) ----
    off = scoring.weekly_points(con, SEASON).copy()
    off["cpos"] = off["position"].map(_OFF)
    tot = off.dropna(subset=["cpos"]).groupby(["gsis_id", "cpos"], as_index=False)["points"].sum()
    ktot = (scoring.kicker_weekly_points(con, SEASON)
            .groupby("gsis_id", as_index=False)["points"].sum())

    def pick(pos: str, n: int, skip: int = 0) -> list[tuple[str, str]]:
        d = tot[tot["cpos"] == pos].sort_values("points", ascending=False).iloc[skip:skip + n]
        return [(g, pos) for g in d["gsis_id"]]

    def top_k() -> list[tuple[str, str]]:
        g = ktot.sort_values("points", ascending=False).iloc[0]["gsis_id"]
        return [(g, "K")]

    def roster(rows: list[tuple[str, str]]) -> pd.DataFrame:
        return pd.DataFrame(rows, columns=["player_key", "pos"])

    # good = elite starters + flex + top K; bad = ~40th-ranked scrubs (no K).
    good = roster(pick("QB", 1) + pick("RB", 2) + pick("WR", 2) + pick("TE", 1)
                  + pick("RB", 1, skip=2) + top_k())
    bad = roster(pick("QB", 1, 39) + pick("RB", 2, 39) + pick("WR", 2, 39)
                 + pick("TE", 1, 39) + pick("RB", 1, 45))
    par_good = par(good, realized, repl, slots)
    par_bad = par(bad, realized, repl, slots)
    print("=== PAR: obviously-good vs obviously-bad roster ===")
    print(f"  good (elite starters): {roster_season_points(good, realized, slots):.1f} pts "
          f"-> PAR {par_good:+.1f}")
    print(f"  bad  (~40th at each) : {roster_season_points(bad, realized, slots):.1f} pts "
          f"-> PAR {par_bad:+.1f}")
    assert par_good > par_bad, "PAR failed to rank the good roster above the bad one"
    assert par_good > 0 > par_bad, "expected good PAR > 0 > bad PAR"
    print(f"  [PASS] PAR ranks good above bad by {par_good - par_bad:.1f} pts.\n")

    # -- secondary metrics: PAR vs expected wins across a real 10-team draft ------------------
    as_of = draft_date(con, SEASON)
    board = adp_asof(con, SEASON, as_of).assign(value=lambda b: b["adp"])
    preseason_board(con, SEASON, as_of)  # PIT-assert the board
    res = simulate_draft(board, your_pick_fn=value_pick_fn, n_teams=10, rounds=15,
                         slots=slots, your_team=0, noise=5.0, seed=SEASON)
    weekly = np.vstack([roster_weekly_points(res.roster(t), realized, slots) for t in range(10)])
    pars = np.array([roster_season_points(res.roster(t), realized, slots)
                     for t in range(10)]) - repl.roster_total
    ew = expected_wins(weekly)
    fin = final_standings(weekly)
    tbl = (pd.DataFrame({"team": range(10), "PAR": pars, "exp_wins": ew, "finish": fin})
           .sort_values("finish"))
    print(f"=== one {SEASON} draft: PAR vs expected wins (all-play) ===")
    for _, r in tbl.iterrows():
        print(f"  finish {int(r['finish']):>2}  team {int(r['team'])}  "
              f"PAR {r['PAR']:>+7.1f}  exp_wins {r['exp_wins']:>4.1f}")
    corr = float(np.corrcoef(pars, ew)[0, 1])
    assert corr > 0.7, f"PAR and expected wins should correlate strongly (got {corr:.2f})"
    assert fin[int(np.argmax(pars))] <= 3, "highest-PAR team should finish top-3"
    print(f"  [PASS] PAR ↔ expected-wins corr = {corr:.2f}; top-PAR team finishes "
          f"{fin[int(np.argmax(pars))]}.\n")

    print("Phase 1.4 (PAR metric) — all criteria PASS.")
    con.close()


if __name__ == "__main__":
    main()
