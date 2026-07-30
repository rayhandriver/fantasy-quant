"""T28 (Session H.5 step 2) — is a **starter-aware** team metric a better read than the slot-blind
sum, and should the value hawk optimize it?

    uv run python steps/t28_starter_value.py --seeds 40 --seasons 2019 2020 2021 2022

Two questions, deliberately kept apart because only the first is a measurement:

**B5 — the reporting question.** ``team_value``/``portfolio_value`` sum ``base_value`` over all
fifteen roster rows, so a bench QB2 is priced as if he starts. The 2026 walkthrough put
Spearman(portfolio CE, title) at **+0.758** and Spearman(starting-nine Phase-5 mean, title) at
**+0.915** over ten teams — one draw, and one draw is a hypothesis. This scores four metrics against
the Phase-10 title probability over ``seeds x seasons`` *seated-reshuffled* drafts and reports the
**paired** difference with a bootstrap CI:

    portfolio_value   the shipped headline (team_value − 2λ·cross-covariance)
    team_value        the slot-blind sum itself
    starter_value     T28: the best legal starting lineup's base_value
    starter_mean      the same lineup selection scored on the raw Phase-5 `mean`

⚠ **B5's direction is pre-registered**: ``spearman(starter_value, title) > spearman(portfolio_value,
title)``. If it fails, T28 closes as a labelling fix and the value hawk's objective does not move —
a ten-team walkthrough is not licence to ship a new headline metric.

**The objective question** is a *behaviour* change (it moves the room's picks, so it moves T15 bars
1/2/5) and is therefore measured the way T24 was — seating-marginalized, one knob, the full bar
sheet — by ``steps/mock_room_bars.py --bench-weight``. This script only decides whether that
question is worth asking.

★ **The scoring trap, restated** (glossary: "the scoring trap"): every metric here is computed on
*our* board, and the seats that drafted these rosters were also optimizing our board. What keeps
this honest is that the **target** is not our board — it is the Phase-10 title probability, a
different object with its own calibration (lockbox title Brier 0.088). Read this as "which summary
of a roster best predicts the sim's own verdict", never as "which drafter is better".
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from fantasy_quant.draft import mock, optimizer
from fantasy_quant.draft.config import DraftConfig
from fantasy_quant.draft.personalities import REALISTIC_ROOM
from fantasy_quant.simulation.season import (
    LeagueFormat,
    league_probabilities,
    lineup_points_matrix,
)
from fantasy_quant.simulation.weekly import build_weekly_model

DB = Path("data/fantasy_quant.duckdb")
CACHE = Path("analysis/cache")
OUT = Path("analysis/t28_starter_value.json")

#: DEV seasons only — the lockbox is spent and this is a *reporting* question, but the rule that
#: nothing is tuned on 2023/2024 does not lapse because the eval is over.
DEV_MATCHED: tuple[int, ...] = (2017, 2018, 2019, 2020, 2021, 2022)

METRICS = ("portfolio_value", "team_value", "starter_value", "starter_mean")


def _starter_mean(roster: pd.DataFrame, mean_by_key: pd.Series, slots) -> float:
    """The same lineup selection as :func:`~fantasy_quant.draft.optimizer.starter_value`, scored on
    the raw Phase-5 ``mean`` — the walkthrough's +0.915 metric, included because if *it* is the one
    that wins then the lesson is about the level, not about slot-awareness."""
    if roster.empty:
        return 0.0
    vals = roster["player_key"].map(mean_by_key).fillna(0.0).to_numpy(float)
    return float(np.ravel(lineup_points_matrix(vals[:, None], roster["pos"].tolist(), slots))[0])


def _boot_diff(a: np.ndarray, b: np.ndarray, n: int = 4000, seed: int = 0) -> dict:
    """Paired bootstrap over drafts of ``mean(a) − mean(b)`` (a and b are per-draft Spearmans)."""
    rng = np.random.default_rng(seed)
    d = np.asarray(a, float) - np.asarray(b, float)
    idx = rng.integers(0, len(d), (n, len(d)))
    draws = d[idx].mean(axis=1)
    return {"diff": float(d.mean()), "lo": float(np.quantile(draws, 0.025)),
            "hi": float(np.quantile(draws, 0.975)),
            "share_positive": float((draws > 0).mean())}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", type=int, default=40)
    ap.add_argument("--seasons", type=int, nargs="*", default=None)
    ap.add_argument("--rounds", type=int, default=15)
    ap.add_argument("--room-seed", type=int, default=17)
    ap.add_argument("--sims", type=int, default=300)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    seasons = tuple(args.seasons) if args.seasons else DEV_MATCHED
    con = duckdb.connect(str(DB), read_only=True)
    model = mock.load_opponent_model()
    config = DraftConfig()
    slots = config.league.slots
    fmt = LeagueFormat(n_teams=10)

    rows: list[dict] = []
    for season in seasons:
        board, src = mock.room_board(con, season, cache_dir=CACHE)
        if board.empty:
            print(f"  {season}: no board, skipped")
            continue
        vi = optimizer.assemble_value(con, season, config)
        attached = optimizer.attach_value(board, vi)
        risk = optimizer.build_risk_model(attached, vi, optimizer.assemble_correlation(con, season),
                                          lam=config.risk_lambda)
        corr = optimizer.assemble_correlation(con, season)
        mean_by_key = (vi.dropna(subset=["mean"]).drop_duplicates("player_key")
                       .set_index("player_key")["mean"])
        # one WeeklyModel per season on the shared T6 draws — the same cloud the value came from
        wm = build_weekly_model(con, season, config.league.ruleset, seed=0)
        print(f"  {season} ({src}): {args.seeds} drafts", flush=True)

        for s in range(args.seeds):
            # seating reshuffled per seed: T24's lesson — a fixed arrangement measures *where the
            # reachy seats sit*, and more seeds do not fix it because it is a bias, not variance.
            room = mock.full_room(REALISTIC_ROOM, n_teams=10, seed=args.room_seed + 1000 * s)
            st = mock.simulate_room_draft(attached, room, model, n_teams=10, rounds=args.rounds,
                                          seed=s, risk=risk, slots=slots)
            rosters = [st.roster(t) for t in range(st.n_teams)]
            rng = np.random.default_rng(10_000 + s)
            pp, tp = league_probabilities(rosters, wm, fmt, slots, rng, sims=args.sims)
            for t, roster in enumerate(rosters):
                rows.append({
                    "season": season, "seed": s, "team": t,
                    "seat": room[t].name,
                    "portfolio_value": optimizer.portfolio_value(roster, vi, corr,
                                                                 config.risk_lambda),
                    "team_value": optimizer.team_value(roster, vi),
                    "starter_value": optimizer.starter_value(roster, vi, slots),
                    "starter_mean": _starter_mean(roster, mean_by_key, slots),
                    "title_prob": float(tp[t]), "playoff_prob": float(pp[t]),
                })

    df = pd.DataFrame(rows)
    if df.empty:
        raise SystemExit("no drafts scored")

    # per-draft Spearman across the ten teams, then aggregate. Pooling raw values across drafts
    # would mix seasons with different value scales and let a level shift masquerade as ordering.
    per_draft = (df.groupby(["season", "seed"])
                 .apply(lambda g: pd.Series({m: spearmanr(g[m], g["title_prob"]).statistic
                                             for m in METRICS}), include_groups=False)
                 .dropna())
    summary = {m: {"mean_spearman": float(per_draft[m].mean()),
                   "sd": float(per_draft[m].std())} for m in METRICS}

    print(f"\n=== B5 — Spearman(metric, title_prob), {len(per_draft)} drafts "
          f"x 10 teams, seating reshuffled ===")
    for m in METRICS:
        print(f"  {m:<18} {summary[m]['mean_spearman']:+.4f}  (sd {summary[m]['sd']:.3f})")

    b5 = _boot_diff(per_draft["starter_value"].to_numpy(), per_draft["portfolio_value"].to_numpy())
    extra = {
        "starter_value_vs_team_value": _boot_diff(per_draft["starter_value"].to_numpy(),
                                                  per_draft["team_value"].to_numpy()),
        "starter_mean_vs_starter_value": _boot_diff(per_draft["starter_mean"].to_numpy(),
                                                    per_draft["starter_value"].to_numpy()),
    }
    passed = bool(b5["diff"] > 0 and b5["lo"] > 0)
    print(f"\n  B5  starter_value − portfolio_value = {b5['diff']:+.4f} "
          f"CI[{b5['lo']:+.4f},{b5['hi']:+.4f}] -> {'PASS' if passed else 'FAIL'}")
    print("      (pre-registered direction: > 0. A fail closes T28 as a labelling fix.)")
    for k, v in extra.items():
        print(f"  ..  {k:<32} {v['diff']:+.4f} CI[{v['lo']:+.4f},{v['hi']:+.4f}]")

    art = {"generated": pd.Timestamp.now("UTC").isoformat(),
           "config": {"seeds": args.seeds, "seasons": list(seasons), "rounds": args.rounds,
                      "sims": args.sims, "room_seed": args.room_seed,
                      "room": list(REALISTIC_ROOM), "shuffled_seating": True},
           "n_drafts": int(len(per_draft)), "n_team_seasons": int(len(df)),
           "spearman": summary, "b5": {**b5, "passed": passed}, "also": extra}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(art, indent=2))
    df.to_csv(args.out.with_suffix(".csv"), index=False)
    print(f"\nwrote {args.out} (+ .csv, {len(df)} team-rows)")


if __name__ == "__main__":
    main()
