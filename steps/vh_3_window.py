"""VH.3 — the reach window: the sweep 16.14R never resolved, re-asked at the repaired scale.

    uv run python steps/vh_3_window.py --seeds 50 --seasons 2019 2020 2021 2022

Writes ``analysis/vh_window.json`` (+ ``.csv``).

**Where this stood.** ``analysis/phase16_14r_value_hawk.json`` records ``sweep_resolved: false``:
over ``{1.00, 1.15, 1.25}`` the CE surplus rose +13.1 against a pooled se of **10.7**, so the
shipped ``window_mult = 1.0`` went out as a **default, not a result**.

**Why it is no longer a tail item.** VH.0 attributed the user's objection and the window came out
the **dominant** channel on both board vintages — closing it changes 6 of 7–8 objected picks, more
than any other knob — and it is the channel that speaks to his stated criterion directly: he
labelled reaches bad and falls good (``corr(reach, labelled-bad) = +0.767``), and the window is the
mechanism that produces reaches.

★ **Two things 16.14R's sweep could not have settled, both fixed here.**

1. **The grid was unbracketed on the side that matters.** ``{1.00, 1.15, 1.25}`` only ever asked
   *how much further should it be allowed to reach*. The winner sat at the bottom edge, and this
   repo has already shipped twice off the edge of an unbracketed grid (T15's width curve, twice —
   the un-sampled midpoint beat both). So the grid now runs **below** 1.0.
2. **It was scored on CE, which this seat maximizes.** That is the evaluation trap stated in
   ``make_value_hawk_pick_fn``'s own docstring: a seat optimizing our board, scored on our board,
   wins by construction — and a *wider* window can only raise the CE it is maximizing, so the
   sweep's own metric was monotone in the knob by construction. CE is still reported, labelled
   **descriptive**; the evaluative columns are **realized points** and the title multiple.

**Pre-registered — B4.** The window is resolved, **or is reported as still unresolved with its se**
and the default is kept. An argmax is not read off a difference inside its own noise (16.14R's dead
end, and 9.5's before it). The realism constraint is a **gate, not a tiebreak**: a window whose
realized ``p95`` reach exceeds the corpus ceiling is out regardless of what it scores.
"""

from __future__ import annotations

import argparse
import importlib.util
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
from fantasy_quant.draft.personalities import (
    CORPUS_REACH_P95,
    REALISTIC_ROOM,
    personalities,
    value_hawk_budget,
)
from fantasy_quant.simulation.season import LeagueFormat, league_probabilities
from fantasy_quant.simulation.weekly import build_weekly_model

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data/fantasy_quant.duckdb"
CACHE = ROOT / "analysis/cache"
OUT = ROOT / "analysis/vh_window.json"

DEV_MATCHED: tuple[int, ...] = (2019, 2020, 2021, 2022)
#: ★ bracketed on BOTH sides of the shipped 1.0 — see the docstring.
WINDOWS: tuple[float, ...] = (0.50, 0.75, 1.00, 1.15, 1.25)
SHIPPED_WINDOW = 1.00


def _vh2():
    """VH.2's metric helpers, imported rather than re-typed.

    *If the two sides of a comparison are computed by different code, the comparison measures the
    code* — 16.14R step 7's rule. The window sweep and the objective A/B are meant to be read
    against each other, so ``_shape`` and ``_boot`` must be the identical functions.
    """
    spec = importlib.util.spec_from_file_location("_vh2", ROOT / "steps" / "vh_2_objective_ab.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", type=int, default=50)
    ap.add_argument("--seasons", type=int, nargs="*", default=None)
    ap.add_argument("--rounds", type=int, default=15)
    ap.add_argument("--room-seed", type=int, default=17)
    ap.add_argument("--sims", type=int, default=300)
    ap.add_argument("--windows", type=float, nargs="*", default=None)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    seasons = tuple(args.seasons) if args.seasons else DEV_MATCHED
    bad = [s for s in seasons if s not in set(DEV_SEASONS)]
    if bad:
        raise SystemExit(f"{bad} are not DEV seasons — the lockbox stays shut (config.DEV_SEASONS)")
    windows = tuple(args.windows) if args.windows else WINDOWS
    vh2 = _vh2()

    con = duckdb.connect(str(DB), read_only=True)
    model = mock.load_opponent_model()
    config = DraftConfig()
    slots = config.league.slots
    fmt = LeagueFormat(n_teams=10)
    vh_base = personalities()["value_hawk"]
    print(f"=== VH.3 — the reach window · {list(windows)} (shipped {SHIPPED_WINDOW}) ===")
    print(f"    {args.seeds} seeds x {len(seasons)} seasons = "
          f"{args.seeds * len(seasons)} drafts per window, seating reshuffled per seed\n")

    rows: list[dict] = []
    for season in seasons:
        board, src = mock.room_board(con, season, cache_dir=CACHE)
        if board.empty:
            print(f"  {season}: no board, skipped")
            continue
        vi = optimizer.assemble_value(con, season, config)
        attached = optimizer.attach_value(board, vi)
        corr = optimizer.assemble_correlation(con, season)
        risk = optimizer.build_risk_model(attached, vi, corr, lam=config.risk_lambda)
        wm = build_weekly_model(con, season, config.league.ruleset, seed=0)
        realized = build_realized(con, season, config.league.ruleset)
        print(f"  {season} ({src}) ...", flush=True)

        for s in range(args.seeds):
            base_room = mock.full_room(REALISTIC_ROOM, n_teams=10, seed=args.room_seed + 1000 * s)
            for w in windows:
                # one knob: the value hawk's budget. Every other seat is the same object.
                room = tuple(replace(p, reach_budget=value_hawk_budget(w))
                             if p.name == vh_base.name else p for p in base_room)
                st = mock.simulate_room_draft(attached, room, model, n_teams=10,
                                              rounds=args.rounds, seed=s, risk=risk, slots=slots)
                log = st.pick_log()
                rosters = [st.roster(t) for t in range(st.n_teams)]
                rng = np.random.default_rng(10_000 + s)
                pp, tp = league_probabilities(rosters, wm, fmt, slots, rng, sims=args.sims)
                for t, roster in enumerate(rosters):
                    if room[t].name != vh_base.name:
                        continue
                    mine = log[log["team"] == t]
                    reach = (mine["adp"] - mine["overall_pick"]).to_numpy(float)
                    # 16.14R step 6's definition exactly: the p95 of reaches CONDITIONAL on
                    # reaching. Pooling the falls in would let a patient seat buy headroom for a
                    # wild one, and the constraint it feeds was calibrated on this quantity.
                    pos_reach = reach[reach > 0]
                    cap = optimizer.team_value(roster, vi)
                    rows.append({
                        "season": season, "seed": s, "window_mult": w, "team": t,
                        "realized_points": roster_season_points(roster, realized, slots),
                        "starter_value": optimizer.starter_value(roster, vi, slots),
                        "portfolio_ce": optimizer.portfolio_value(roster, vi, corr,
                                                                  config.risk_lambda),
                        "team_value": cap,
                        "title_multiple": float(tp[t]) * fmt.n_teams,
                        "playoff_multiple": float(pp[t]) * fmt.n_teams / 6.0,
                        "p95_reach": (float(np.quantile(pos_reach, 0.95))
                                      if len(pos_reach) else 0.0),
                        **vh2._shape(log, t),
                    })

    df = pd.DataFrame(rows)
    if df.empty:
        raise SystemExit("no drafts scored")
    df.to_csv(args.out.with_suffix(".csv"), index=False)

    METRICS = ["realized_points", "title_multiple", "playoff_multiple", "starter_value",
               "portfolio_ce", "mean_reach", "p95_reach", "backups_early"]
    piv = df.pivot_table(index=["season", "seed"], columns="window_mult", values=METRICS,
                         aggfunc="mean")

    # 16.14R step 6's ceiling: the round-pooled mean of the per-round corpus p95, not the round-1
    # value. Using a different ceiling here would make the gate incomparable to the shipped one.
    ceiling = float(np.mean(CORPUS_REACH_P95[: args.rounds]))
    print(f"\n=== per window (n = {len(piv)} drafts each) ===")
    hdr = (f"{'w':>5} {'realized':>10} {'title x':>8} {'CE (desc)':>11} "
           f"{'mean rch':>9} {'p95 rch':>8} {'legal':>6}")
    print(hdr)
    per_w = {}
    for w in windows:
        m = {k: float(df.loc[df["window_mult"] == w, k].mean()) for k in METRICS}
        legal = m["p95_reach"] <= ceiling
        per_w[w] = {**m, "within_corpus_p95": bool(legal)}
        print(f"{w:>5.2f} {m['realized_points']:>10.1f} {m['title_multiple']:>8.3f} "
              f"{m['portfolio_ce']:>11.1f} {m['mean_reach']:>9.2f} {m['p95_reach']:>8.2f} "
              f"{'yes' if legal else 'NO':>6}")
    print(f"      (realism gate: realized p95 reach <= round-pooled corpus p95 = {ceiling:.2f})")

    # ===== B4 — is the sweep resolved? ============================================================
    base_col = SHIPPED_WINDOW
    contrasts = {}
    for w in windows:
        if w == base_col:
            continue
        contrasts[str(w)] = {
            k: vh2._boot(piv[(k, w)].to_numpy(), piv[(k, base_col)].to_numpy())
            for k in ("realized_points", "title_multiple", "mean_reach", "portfolio_ce")
        }

    print(f"\n=== each window − the shipped {base_col}, paired over {len(piv)} drafts ===")
    for w, c in contrasts.items():
        r, t = c["realized_points"], c["title_multiple"]
        print(f"  w={w}:  realized {r['diff']:+8.1f} CI[{r['lo']:+.1f},{r['hi']:+.1f}]"
              f"   title x {t['diff']:+.3f} CI[{t['lo']:+.3f},{t['hi']:+.3f}]"
              f"   reach {c['mean_reach']['diff']:+.2f}")

    # "Resolved" = some window beats the shipped default on realized points with a CI clear of 0,
    # among windows that pass the realism gate. Anything else is reported as unresolved.
    legal_w = [w for w in windows if per_w[w]["within_corpus_p95"]]
    winners = [w for w in legal_w if w != base_col
               and contrasts[str(w)]["realized_points"]["lo"] > 0]
    resolved = bool(winners)
    best = max(winners, key=lambda w: contrasts[str(w)]["realized_points"]["diff"]) if winners \
        else base_col
    ses = {w: (contrasts[str(w)]["realized_points"]["hi"]
               - contrasts[str(w)]["realized_points"]["lo"]) / 3.92
           for w in windows if w != base_col}
    print(f"\nB4: sweep_resolved = {resolved}"
          f"{f' -> {best}' if resolved else f' — keeping the default {base_col}'}")
    if not resolved:
        print(f"    realized-points se across the grid: "
              f"{', '.join(f'w={w}: {s:.1f}' for w, s in ses.items())}")
        print("    (16.14R shipped this knob as a default, not a result; so does VH.3.)")

    art = {"generated": pd.Timestamp.now("UTC").isoformat(),
           "config": {"seeds": args.seeds, "seasons": list(seasons), "rounds": args.rounds,
                      "sims": args.sims, "room_seed": args.room_seed, "windows": list(windows),
                      "shipped_window": SHIPPED_WINDOW, "shuffled_seating": True,
                      "corpus_p95_round1": ceiling},
           "n_drafts_per_window": int(len(piv)), "per_window": {str(k): v
                                                                for k, v in per_w.items()},
           "contrasts_vs_shipped": contrasts,
           "bars": {"B4": {"resolved": resolved, "selected": best,
                           "legal_windows": legal_w, "winners": winners,
                           "realized_se": {str(k): v for k, v in ses.items()},
                           "pass": True}}}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(art, indent=2, default=str))
    print(f"\nwrote {args.out} (+ .csv, {len(df)} rows)")


if __name__ == "__main__":
    main()
