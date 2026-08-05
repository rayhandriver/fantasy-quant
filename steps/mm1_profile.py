"""MM-1 — build a :class:`ManagerProfile` from a filled belief workbook, and CALIBRATE its scale.

    uv run --extra reports python steps/mm1_profile.py [--write]

★ **The one number this step exists to decide.** A workbook records *direction and confidence*
("Very undervalued", confidence 4). It does not record **magnitude in picks**, and on this subject's
sheet the optional ``Personal ADP`` column — the only place a magnitude could have been written —
is empty for all 150 rows. So the scale has to come from somewhere, and the honest somewhere is his
own realized behaviour: **the scale that best reproduces the picks he actually made.**

★★ **And the reason it is leave-one-DRAFT-out and not a plain fit.** The same 45 picks are the only
held-out set this subject has (bar **B4**: *beat the corpus-fit ``balanced`` on picks never used in
fitting*). Choosing a scale on all three drafts and then scoring it on all three drafts is the
**grader-is-the-subject trap** with an extra step — the model would be scored on data it selected
itself against. Under LOO the scale that scores draft *i* has never seen draft *i*, so the reported
number is a genuine out-of-fold one and the data is not spent.

⚠ **What this step does NOT do.** It fits no **policy**. The tradeoff coefficients — how this
manager weighs value against risk against need against scarcity — are a *decision rule*, they are
identified by choices in the region where he is torn, and they wait for the elicitation session
(16.18a–c). ``profile.policy`` therefore ships **empty**, with ``policy_source='corpus'`` saying so,
and the seat runs the fitted average manager's tradeoffs over his own board. That is a complete
object, not a half-built one, and calling it anything else would report an unfitted seat as a
fitted one.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from fantasy_quant.draft import mock
from fantasy_quant.draft.manager_profile import (
    PROFILE_DIR,
    ManagerProfile,
    avoid_mask,
    build_profile,
    name_key,
    personal_adp,
    read_belief_workbook,
)
from fantasy_quant.draft.opponent_model import SKILL_POSITIONS

DB = Path("data/fantasy_quant.duckdb")
OUT = Path("analysis/mm1_profile.json")
WORKBOOK = Path("reference/mm1_belief_board_2026_20260802.xlsx")

SEASON = 2026
TEAMS = 10
PROFILE_ID = "mm1_2026"

#: The subject's Sleeper identity — the only thing here that names a person, and it names him as a
#: **key into a public table**, not as a hardcoded behaviour. Everything else in the pipeline reads
#: a profile file and does not know whose it is.
SUBJECT_SLEEPER_ID = "1381536159267573760"

#: Stated allegiance rule, taken from the workbook's own prose and confirmed by the subject:
#: no Green Bay, with exactly one named exception. Recorded here (a step, reviewable) rather than
#: in the library, because it is a fact about one person and not about drafting.
AVOID_TEAMS = ("GB",)
TEAM_EXCEPTIONS = ("Tucker Kraft",)

#: Picks per unit of stated value score at confidence 3. The grid the LOO sweep searches.
SCALE_GRID = (0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0)


# ------------------------------------------------------------------------------------------------
# scoring a profile against realized picks
# ------------------------------------------------------------------------------------------------
def subject_picks(con, sleeper_id: str = SUBJECT_SLEEPER_ID) -> pd.DataFrame:
    """Every pick this manager personally made, plus the full pick log of those drafts.

    The mocks were solo-vs-bots, so ``picked_by`` is populated for the human's own picks **only**
    (the 2026-07-11 finding). That is enough: his picks are the choices, and the other seats' picks
    are needed only to know what was still on the board when his turn came.
    """
    df = con.execute("""
        with mine as (select distinct draft_id from sleeper_draft_picks where picked_by = ?)
        select p.draft_id, p.pick_no, p.round, p.player_name, p.position, p.nfl_team, p.gsis_id,
               coalesce(p.picked_by = ?, false) as is_mine
        from sleeper_draft_picks p join mine m using (draft_id)
        order by p.draft_id, p.pick_no
    """, [sleeper_id, sleeper_id]).fetchdf()
    # `picked_by` is NULL for every bot seat, so the comparison is NULL there too — a pandas
    # nullable boolean whose truth value raises rather than reading False. Pin it in the type.
    df["is_mine"] = df["is_mine"].fillna(False).astype(bool)
    return df


def _pool_at(board: pd.DataFrame, taken: set[str]) -> pd.DataFrame:
    return board[~board["_k"].isin(taken)]


def score_profile(profile: ManagerProfile, picks: pd.DataFrame, board: pd.DataFrame, *,
                  top_k: int = 40) -> dict:
    """How well this profile's board explains the manager's realized picks.

    Deliberately a **rank** statistic over his own candidate set, not a log-likelihood: a
    likelihood would need the policy β, and the whole point of this step is that the policy is not
    fitted yet. ``mean_rank`` is where his actual pick sat on the personal board among everything
    still available at that pick, and ``top1``/``top5`` are how often it was the personal board's
    own first / top-five choice. A pure consensus board (``scale=0``) is the null this is measured
    against, which is exactly bar B4's shape one signal short.
    """
    board = board.copy()
    board["_k"] = [name_key(n, p) for n, p in zip(board["name"], board["position"], strict=True)]
    padp = personal_adp(board, profile, key="gsis_id")
    avoid = avoid_mask(board, profile, key="gsis_id")
    board["_padp"] = padp
    board["_avoid"] = avoid

    ranks: list[float] = []
    hit1 = hit5 = n = avoided_picks = offboard = 0
    for _, g in picks.groupby("draft_id"):
        taken: set[str] = set()
        for _, row in g.iterrows():
            k = name_key(row["player_name"], row["position"])
            if bool(row["is_mine"]):
                pool = _pool_at(board, taken)
                pool = pool[pool["position"].isin(SKILL_POSITIONS)]
                if k not in set(pool["_k"]):
                    offboard += 1              # a kicker, a DST, or someone off the top-N board
                else:
                    live = pool[~pool["_avoid"]]
                    live = live if not live.empty else pool
                    if k not in set(live["_k"]):
                        avoided_picks += 1     # he drafted someone his own rule says he would not
                        live = pool
                    cand = live.nsmallest(min(top_k, len(live)), "_padp")
                    if k in set(cand["_k"]):
                        order = cand.sort_values("_padp", kind="stable")["_k"].tolist()
                        r = order.index(k) + 1
                    else:
                        r = float(top_k + 1)   # outside his own consideration set entirely
                    ranks.append(float(r))
                    n += 1
                    hit1 += int(r == 1)
                    hit5 += int(r <= 5)
            taken.add(k)
    return {
        "n_scored": int(n), "mean_rank": float(np.mean(ranks)) if ranks else float("nan"),
        "median_rank": float(np.median(ranks)) if ranks else float("nan"),
        "top1": hit1 / n if n else float("nan"), "top5": hit5 / n if n else float("nan"),
        "picks_off_board": int(offboard), "picks_against_own_avoid": int(avoided_picks),
        "ranks": ranks,
    }


def paired_bootstrap(a: list[float], b: list[float], *, n_boot: int = 4000,
                     seed: int = 7) -> dict:
    """Paired bootstrap CI on ``mean(a) − mean(b)`` over the **same** picks.

    Paired because both arms score the identical 40 choices: the between-pick variance is enormous
    (a rank runs 1 to 41) and would swamp a difference of one rank if the arms were resampled
    independently. This is the same block-bootstrap discipline ``backtest/significance.py`` applies
    to seasons, at the only grain this data has.
    """
    x = np.asarray(a, float) - np.asarray(b, float)
    if x.size == 0:
        return {"delta": float("nan"), "lo": float("nan"), "hi": float("nan"), "se": float("nan")}
    rng = np.random.default_rng(seed)
    draws = x[rng.integers(0, x.size, size=(n_boot, x.size))].mean(axis=1)
    return {"delta": float(x.mean()), "se": float(draws.std()),
            "lo": float(np.percentile(draws, 2.5)), "hi": float(np.percentile(draws, 97.5))}


def calibrate_scale(workbook: pd.DataFrame, board: pd.DataFrame, picks: pd.DataFrame, *,
                    grid=SCALE_GRID, **build_kw) -> dict:
    """Leave-one-**draft**-out sweep over ``grid`` → the scale, and its honest out-of-fold score.

    ⚠ The fold is a **draft**, not a pick. Picks inside one draft share a board, a seat and a
    running roster, so leaving out single picks would leave most of the information about a draft
    in the training set — the sibling-derived-feature failure 16.8 was written up for, arriving on
    a cross-validation split.
    """
    drafts = sorted(picks.loc[picks["is_mine"], "draft_id"].unique().tolist())
    prof = {s: build_profile(workbook, profile_id="_sweep", season=SEASON, board=board,
                             belief_scale=s, **build_kw) for s in grid}
    in_sample = {s: score_profile(prof[s], picks, board) for s in grid}

    folds = []
    for held in drafts:
        train = picks[picks["draft_id"] != held]
        test = picks[picks["draft_id"] == held]
        # choose on the OTHER drafts...
        best = min(grid, key=lambda s: score_profile(prof[s], train, board)["mean_rank"])
        # ...and report on the one it never saw
        folds.append({"held_out_draft": str(held), "chosen_scale": float(best),
                      **score_profile(prof[best], test, board)})

    oof_rank = float(np.mean([f["mean_rank"] for f in folds]))
    oof_top1 = float(np.mean([f["top1"] for f in folds]))
    null = in_sample[0.0]

    # ★ Resolution before argmin. `mean_rank` falls monotonically to scale 10 while `top1` and
    # `median_rank` both peak around 3-6 — three statistics, three winners, on n=40. VH.3's
    # lesson applies verbatim: *if the sweep is unresolved at achievable n, say so and keep the
    # conservative default rather than reading an argmax off noise.* So the shipped scale is the
    # SMALLEST one whose mean rank is within one paired-bootstrap se of the best, which is a
    # deliberate tie-break toward deviating less from a room that has already been validated.
    best = min(grid, key=lambda s: in_sample[s]["mean_rank"])
    se = paired_bootstrap(in_sample[best]["ranks"], null["ranks"])["se"]
    tol = in_sample[best]["mean_rank"] + se
    shipped = min(s for s in grid if in_sample[s]["mean_rank"] <= tol)
    vs_null = paired_bootstrap(in_sample[shipped]["ranks"], null["ranks"])
    resolved = bool(in_sample[best]["mean_rank"] < in_sample[0.0]["mean_rank"] - 2 * se)
    return {
        "grid": [float(s) for s in grid],
        "in_sample": {str(s): {k: v for k, v in in_sample[s].items() if k != "ranks"}
                      for s in grid},
        "folds": [{k: v for k, v in f.items() if k != "ranks"} for f in folds],
        "argmin_scale": float(best), "shipped_scale": float(shipped),
        "shipped_rule": "smallest scale within 1 paired-bootstrap se of the argmin",
        "oof_mean_rank": oof_rank, "oof_top1": oof_top1,
        "null_scale0_mean_rank": null["mean_rank"], "null_scale0_top1": null["top1"],
        "delta_vs_null": vs_null,
        "sweep_resolved": resolved,
        "beats_consensus_null": bool(oof_rank < null["mean_rank"]),
        # ⚠ What each number is a claim ABOUT, because they are not claims about the same thing.
        "oof_note": ("oof_* scores the PROCEDURE (choose a scale on two drafts, score the third), "
                     "which is the falsifiable number. delta_vs_null scores the SHIPPED scale "
                     "in-sample; the shipped scale is a conservative tie-break inside the "
                     "procedure's own noise and has no clean out-of-fold of its own."),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workbook", type=Path, default=WORKBOOK)
    ap.add_argument("--write", action="store_true", help="save the profile to reference/")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    wb = read_belief_workbook(args.workbook)
    con = duckdb.connect(str(DB), read_only=True)
    board, src = mock.room_board(con, SEASON, teams=TEAMS)
    picks = subject_picks(con)
    con.close()

    build_kw = dict(blank_note_means_avoid=True, avoid_teams=AVOID_TEAMS,
                    team_exceptions=TEAM_EXCEPTIONS)
    calib = calibrate_scale(wb, board, picks, **build_kw)

    profile = build_profile(
        wb, profile_id=PROFILE_ID, season=SEASON, board=board,
        belief_scale=calib["shipped_scale"], source=str(args.workbook),
        asof=str(board["snapshot_date"].max()), **build_kw)

    report = {
        "profile": profile.summary(),
        "board": {"source": src, "rows": int(len(board)),
                  "asof": str(board["snapshot_date"].max())},
        "workbook": {"path": str(args.workbook), "rows": int(len(wb))},
        "calibration": calib,
        "held_out_picks": {
            "n_drafts": int(picks.loc[picks["is_mine"], "draft_id"].nunique()),
            "n_picks": int(picks["is_mine"].sum())},
        "policy": "NOT FITTED — waits on the 16.18a-c elicitation session; the seat runs the "
                  "corpus-average manager's tradeoffs over this manager's own board",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["profile"], indent=2))
    print(json.dumps({k: v for k, v in calib.items() if k not in ("in_sample", "folds")}, indent=2))
    for f in calib["folds"]:
        print(f"  fold {f['held_out_draft']} scale {f['chosen_scale']} "
              f"mean_rank {f['mean_rank']:.2f} top1 {f['top1']:.2f}")
    if args.write:
        p = profile.save(PROFILE_DIR / f"{PROFILE_ID}.json")
        print(f"wrote {p}")
    else:
        print(f"(dry run — pass --write to save to {PROFILE_DIR}/{PROFILE_ID}.json)")


if __name__ == "__main__":
    main()
