"""The 2x5 mock room, and the three measurements the user's eye opened on 2026-07-28.

    uv run python steps/mock_2x5_diag.py                       # 40 drafts, all three diagnostics
    uv run python steps/mock_2x5_diag.py --seeds 100
    uv run python steps/mock_2x5_diag.py --picks-csv out.csv   # also emit one draft, for the eye

A **2 seats each** room — `autopilot` / `balanced` / `safe_floor` / `reacher` / `value_hawk` — as
opposed to :data:`~fantasy_quant.draft.personalities.REALISTIC_ROOM`, which is corpus-weighted. The
2x5 shape is deliberately *not* realistic: it puts two of every character in the room so a seat's
behaviour is legible by eye, which is what it is for. Use `REALISTIC_ROOM` (via
`steps/phase16_14r_7_room.py`) for anything that measures the room against the corpus.

Thin over the shipped engine — `mock.room_board`, `mock.full_room`, `mock.simulate_room_draft` on
the fitted 11.1 beta, with the Phase-9 risk model attached because `value_hawk` runs `portfolio_ce`.
The room is **reshuffled per seed** so a personality is never confounded with a draft slot.

★ **Why this lives in `steps/` rather than being rewritten each session.** It is the harness for
three open tickets, and each one was found by a human reading picks that every automated gate had
passed (`findings.md` §"The 2x5 mock re-run (2026-07-28)"):

  T23  roster legality   `mandatory_needs` drops TE -> 12.2 % of seats cannot field a lineup
  T24  round-1 realism   width is per-round, never per-player; the consensus #2 lands at pick 4
  T25  seat discipline   the reach ceiling binds 2 of 10 seat types, so `balanced` out-reaches
                         `reacher` in rounds 1-3

Each diagnostic prints its corpus counterpart alongside the simulated number, on the same code path
over both sides — *if the two sides of a comparison are computed by different code, the comparison
measures the code.*
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from fantasy_quant.adp import boards
from fantasy_quant.adp.drift_panel import build_drift_panel
from fantasy_quant.draft import mock, optimizer
from fantasy_quant.draft.config import DraftConfig

DB = Path("data/fantasy_quant.duckdb")
CACHE = Path("analysis/cache")

#: Two of each of the five characters. Not corpus-weighted — see the module docstring.
MIX_2X5: tuple[str, ...] = (
    "autopilot", "autopilot",
    "balanced", "balanced",
    "safe_floor", "safe_floor",
    "reacher", "reacher",
    "value_hawk", "value_hawk",
)

#: The full starting lineup a seat must be able to field. T23's bar is stated over **all** of it,
#: not over the K/DST that motivated T20 — that is the whole lesson of the ticket.
STARTER_MIN = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DST": 1}


def build(con, season: int, teams: int):
    """The enriched board with value + risk attached — `value_hawk` needs the Phase-9 machinery."""
    board, src = mock.room_board(con, season, teams=teams, cache_dir=CACHE)
    if board.empty:
        raise SystemExit(f"no {season} board at teams={teams}")
    config = DraftConfig()
    vi = optimizer.assemble_value(con, season, config)
    attached = optimizer.attach_value(board, vi)
    risk = optimizer.build_risk_model(attached, vi, optimizer.assemble_correlation(con, season),
                                      lam=config.risk_lambda)
    return attached, risk, src


def run_batch(board, risk, model, *, seeds: int, teams: int, rounds: int) -> pd.DataFrame:
    """``seeds`` drafts, room reshuffled per seed, concatenated into one pick log."""
    frames = []
    for s in range(seeds):
        room = mock.full_room(MIX_2X5, n_teams=teams, seed=1000 + s)
        st = mock.simulate_room_draft(board, room, model, n_teams=teams, rounds=rounds,
                                      seed=s, risk=risk)
        log = st.pick_log().copy()
        log["seat_personality"] = log["team"].map({i: p.name for i, p in enumerate(room)})
        log["draft_id"] = f"d{s}"
        log["reach_picks"] = log["adp"] - log["overall_pick"]
        frames.append(log)
    return pd.concat(frames, ignore_index=True)


def corpus_panel(con) -> pd.DataFrame:
    """The realized FFC-boarded human drafts, in the same frame the sim is measured in."""
    c = build_drift_panel(con)
    c = c[c["board_source"] == boards.FFC].dropna(subset=["adp", "pick_no"]).copy()
    c["abs_drift"] = (c["adp"] - c["pick_no"]).abs()
    c["rd"] = np.ceil(c["pick_no"] / 10).clip(upper=15)
    return c


# ------------------------------------------------------------------------------------------------
# T24 — where the consensus elite land, and the |reach| bar that cannot see it
# ------------------------------------------------------------------------------------------------
def diag_elite(panel: pd.DataFrame, board: pd.DataFrame, corpus: pd.DataFrame, *, n: int = 8):
    print("\n=== T24(a) — ELITE LANDING SPOTS ===")
    print("corpus, by ADP band:")
    rows = []
    for lo, hi, lbl in [(0, 2.5, "ADP 1-2.5 (consensus top 2)"), (2.5, 4.5, "ADP 2.5-4.5"),
                        (4.5, 6.5, "ADP 4.5-6.5"), (6.5, 10.5, "ADP 6.5-10.5")]:
        g = corpus[(corpus["adp"] > lo) & (corpus["adp"] <= hi)]["pick_no"]
        if g.empty:
            continue
        rows.append({"band": lbl, "n": len(g), "mean": g.mean(), "median": g.median(),
                     "p90": g.quantile(.90), "p99": g.quantile(.99),
                     "past_4": (g > 4).mean(), "past_6": (g > 6).mean(),
                     "past_10": (g > 10).mean()})
    print(pd.DataFrame(rows).round(2).to_string(index=False))

    print("\nsimulated, per player:")
    top = board.nsmallest(n, "adp")[["name", "adp"]]
    rows = []
    for _, p in top.iterrows():
        g = panel.loc[panel["player_name"] == p["name"], "overall_pick"]
        if g.empty:
            continue
        rows.append({"player": p["name"], "adp": round(float(p["adp"]), 1), "mean": g.mean(),
                     "median": g.median(), "p90": g.quantile(.90), "max": g.max(),
                     "past_4": (g > 4).mean(), "past_6": (g > 6).mean(),
                     "past_10": (g > 10).mean()})
    print(pd.DataFrame(rows).round(2).to_string(index=False))

    # ★ the bar that passes while the above fails — the reason T24 exists
    r1, c1 = panel[panel["round"] == 1], corpus[corpus["rd"] == 1]
    print(f"\n  round-1 mean |reach|: sim {r1.reach_picks.abs().mean():.2f} vs "
          f"corpus {c1.abs_drift.mean():.2f}  <- PASSES, and pools reaches with falls")
    print("  the same number split across the round (corpus RISES, sim is FLAT):")
    for lbl, s, c in (("picks 1-5", r1[r1.pick_in_round <= 5], c1[c1.pick_no <= 5]),
                      ("picks 6-10", r1[r1.pick_in_round > 5], c1[c1.pick_no > 5])):
        print(f"    {lbl:11s} sim {s.reach_picks.abs().mean():.2f}   "
              f"corpus {c.abs_drift.mean():.2f}")


def diag_stdev_scale(corpus: pd.DataFrame):
    """T24's proposed width scale, measured: is `adp_stdev` the right per-player unit?"""
    print("\n=== T24(b) — is `adp_stdev` the right width scale? (corpus) ===")
    c = corpus.dropna(subset=["adp_stdev"])
    bands = pd.cut(c["adp_stdev"], [0, 1.5, 3, 5, 8, 12, 20, 999])
    t = c.groupby(bands, observed=True).agg(n=("abs_drift", "size"),
                                            mean_stdev=("adp_stdev", "mean"),
                                            mean_abs_drift=("abs_drift", "mean"))
    t["ratio"] = t["mean_abs_drift"] / t["mean_stdev"]
    print(t.round(2).to_string())
    sp_sd = c.adp_stdev.corr(c.abs_drift, method="spearman")
    sp_rd = c.rd.corr(c.abs_drift, method="spearman")
    print(f"\n  Spearman(adp_stdev, |drift|) = {sp_sd:.3f}")
    print(f"  Spearman(round,     |drift|) = {sp_rd:.3f}")
    # ★ the decisive one: does it separate INSIDE the top of the board, where WidthCurve cannot?
    e = c[c["rd"] <= 3].copy()
    e["tercile"] = pd.qcut(e["adp_stdev"], 3, labels=["low", "mid", "high"])
    print("\n  within rounds 1-3, |drift| by stdev tercile (the round curve is blind to this):")
    print(e.groupby("tercile", observed=True)["abs_drift"].agg(["size", "mean"])
          .round(2).to_string())


# ------------------------------------------------------------------------------------------------
# T23 — roster legality, stated over the WHOLE lineup
# ------------------------------------------------------------------------------------------------
def diag_legality(panel: pd.DataFrame):
    print("\n=== T23 — ROSTER LEGALITY (1QB/2RB/2WR/1TE/1FLEX/1K/1DST) ===")
    cnt = panel.groupby(["draft_id", "team", "seat_personality"])["pos"].value_counts().unstack(
        fill_value=0)
    for p in STARTER_MIN:
        if p not in cnt:
            cnt[p] = 0
    short = pd.DataFrame({f"no_{p}" if n == 1 else f"lt{n}_{p}": cnt[p] < n
                          for p, n in STARTER_MIN.items()})
    bad = short.any(axis=1)
    print(f"  illegal rosters: {bad.sum()} / {len(cnt)} ({bad.mean():.1%})")
    print("  which slot goes unfilled (% of seats):")
    print(short.mean().mul(100).round(1).to_string())
    print("\n  by personality (% of that seat's rosters that are illegal):")
    print(bad.groupby(level="seat_personality").mean().mul(100).round(1).to_string())


# ------------------------------------------------------------------------------------------------
# T25 — seat discipline, on `pool_rank` rather than a 15-round mean reach
# ------------------------------------------------------------------------------------------------
def diag_seats(panel: pd.DataFrame):
    print("\n=== T25 — SEAT BEHAVIOUR: `pool_rank` (1 = best available, scale-free) ===")
    panel = panel.copy()
    panel["pool_rank"] = mock.pool_rank(panel.rename(columns={"overall_pick": "pick_no"}))
    panel["bucket"] = pd.cut(panel["round"], [0, 3, 6, 10, 13, 15],
                             labels=["R1-3", "R4-6", "R7-10", "R11-13", "R14-15"])
    print("\n-- mean pool_rank by round bucket (the R1-3 column is the inversion) --")
    print(panel.pivot_table(index="seat_personality", columns="bucket", values="pool_rank",
                            aggfunc="mean", observed=True).round(2).to_string())
    print("\n-- mean reach in ADP picks, same buckets "
          "(R11-15 is ADP noise, do not lead with it) --")
    print(panel.pivot_table(index="seat_personality", columns="bucket", values="reach_picks",
                            aggfunc="mean", observed=True).round(2).to_string())
    skill = ~panel["pos"].isin(["K", "DST"])
    print("\n-- overall --")
    print(panel.groupby("seat_personality").agg(
        mean_pool_rank=("pool_rank", "mean"),
        median_pool_rank=("pool_rank", "median"),
        mean_reach=("reach_picks", "mean"),
        mean_reach_skill=("reach_picks", lambda s: s[skill.loc[s.index]].mean()),
    ).round(2).to_string())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--seeds", type=int, default=40)
    ap.add_argument("--teams", type=int, default=10)
    ap.add_argument("--rounds", type=int, default=15)
    ap.add_argument("--picks-csv", type=Path, default=None,
                    help="also emit one full draft (room seed 20260728, seed 728) for the eye")
    args = ap.parse_args()

    con = duckdb.connect(str(DB), read_only=True)
    model = mock.load_opponent_model()
    board, risk, src = build(con, args.season, args.teams)
    print(f"board: {len(board)} players ({src} ADP + 16.13 enrichment) · "
          f"width curve {model.width_curve} · {args.seeds} drafts x {args.teams} seats")

    if args.picks_csv:
        room = mock.full_room(MIX_2X5, n_teams=args.teams, seed=20260728)
        st = mock.simulate_room_draft(board, room, model, n_teams=args.teams,
                                      rounds=args.rounds, seed=728, risk=risk)
        log = st.pick_log().copy()
        log["seat_personality"] = log["team"].map({i: p.name for i, p in enumerate(room)})
        log["reach_picks"] = (log["adp"] - log["overall_pick"]).round(1)
        args.picks_csv.parent.mkdir(parents=True, exist_ok=True)
        log.to_csv(args.picks_csv, index=False)
        print(f"  wrote one {args.rounds}-round mock to {args.picks_csv}")

    panel = run_batch(board, risk, model, seeds=args.seeds, teams=args.teams, rounds=args.rounds)
    corpus = corpus_panel(con)
    print(f"corpus: {corpus.draft_id.nunique():,} FFC drafts / {len(corpus):,} boarded picks")

    diag_elite(panel, board, corpus)
    diag_stdev_scale(corpus)
    diag_legality(panel)
    diag_seats(panel)
    con.close()


if __name__ == "__main__":
    main()
