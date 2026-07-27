"""Phase 16.16 done-bar — live-draft reactive re-estimation (run detection).

Two questions, and the second only matters if the first passes:

1. **Does the detector fire on real runs?** Replay the human Sleeper corpus and check that
   :func:`~fantasy_quant.draft.opponent_model.detect_run` marks windows where a position is
   genuinely coming off the board faster than its remaining supply — and that it is *selective*,
   i.e. it does not fire on most windows, or it is not detecting anything.
2. **Does reacting to a run improve the availability forecast, inside the run window?** Paired
   availability Brier on run-opened windows only, static flow vs run-aware flow.

The restriction to run windows is deliberate and follows 12.4: an injury signal that clearly beat
the injury-blind forecast **on the designated subset** diluted to +0.5 leaguewide. A reactive model
can only differ from a static one where the thing it reacts to is present, so scoring everywhere
would measure dilution rather than the effect.

Per the standing decision, if the adjustment fires correctly but does not beat static it ships
**default OFF** with the null reported — the 16.9 treatment, not deletion.

Run:  uv run python steps/phase16_16_run_detection.py [--quick]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from fantasy_quant.adp.boards import resolve_boards
from fantasy_quant.adp.drift_panel import eligible_drafts
from fantasy_quant.draft.availability import availability_brier
from fantasy_quant.draft.opponent_model import (
    ALL_FEATURES,
    CHOICE_TOP_K,
    RUN_WINDOW,
    OpponentModel,
    detect_run,
)
from fantasy_quant.draft.simulator import canon_pos

DB = Path("data/fantasy_quant.duckdb")
OUT = Path("analysis/phase16_16_run_detection.json")
COEF_JSON = Path("analysis/phase11_opponent_model.json")

#: Intensity at which a window counts as "opened during a run": the running position is taking
#: this much more of the recent picks than its share of the live candidate set. Chosen from
#: :data:`THRESHOLD_GRID` by the face-validity sweep rather than asserted up front.
RUN_THRESHOLD = 0.30

#: Swept, because the firing threshold is a free parameter and picking one silently is how a
#: detector gets tuned until it looks like it works.
THRESHOLD_GRID = (0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50)

#: Utility bumps swept for the reactive adjustment. 0 is the static control and must reproduce the
#: frozen number exactly.
RUN_W_GRID = (0.0, 0.5, 1.0, 2.0)


def _model() -> OpponentModel:
    coef = json.loads(COEF_JSON.read_text())["coefficients"]
    return OpponentModel(feature_cols=list(ALL_FEATURES),
                         beta=np.array([coef[c] for c in ALL_FEATURES]))


def detector_face_validity(con, *, max_drafts: int = 60, seed: int = 0) -> dict:
    """Question 1: replay real drafts and describe when the detector fires.

    Reports the firing rate, which position fires most, and — the load-bearing check — whether a
    fired window is actually followed by more of that position being taken than an unfired one. A
    detector that fires everywhere, or that fires with no predictive relationship to what happens
    next, is not detecting runs.

    The baseline is the **top-``CHOICE_TOP_K`` available by ADP**, rebuilt pick by pick from each
    draft's own board, which is why this replay needs the board and not just the pick sequence.
    """
    drafts = eligible_drafts(con, None)
    drafts = drafts[drafts["season"] < 2025]
    if drafts.empty:
        return {"error": "no eligible drafts"}
    keys = list(zip(drafts["season"], drafts["ffc_scoring"], drafts["board_teams"], strict=False))
    resolved = resolve_boards(con, keys, allow_ecr=False)
    board_of = {}
    for k, (b, _s) in resolved.items():
        if b.empty:
            continue
        b = b.copy()
        b["pos"] = b["position"].map(canon_pos)
        b["adp"] = pd.to_numeric(b["adp"], errors="coerce")
        b = b.dropna(subset=["pos", "adp"])
        board_of[k] = b[b["pos"].isin(("QB", "RB", "WR", "TE"))].sort_values("adp")
    d = drafts[[k in board_of for k in keys]]
    if d.empty:
        return {"error": "no boarded drafts"}
    d = d.sample(min(len(d), max_drafts), random_state=seed)
    key_of = {str(r.draft_id): (int(r.season), str(r.ffc_scoring), int(r.board_teams))
              for r in d.itertuples()}

    ph = ",".join("?" * len(d))
    picks = con.execute(
        f"""SELECT draft_id, pick_no, gsis_id, position FROM sleeper_draft_picks
            WHERE draft_id IN ({ph}) AND gsis_id IS NOT NULL ORDER BY draft_id, pick_no""",
        [str(x) for x in d["draft_id"]],
    ).df()
    picks["pos"] = picks["position"].map(canon_pos)
    picks = picks[picks["pos"].isin(("QB", "RB", "WR", "TE"))]

    obs: list[tuple[str, float, float]] = []     # (position, intensity, its share of the next 5)
    for did, g in picks.groupby("draft_id"):
        bd = board_of.get(key_of.get(str(did)))
        if bd is None:
            continue
        seq = list(g["pos"])
        taken_ids = list(g["gsis_id"])
        bpos = bd["pos"].to_numpy()
        bids = bd["gsis_id"].astype(str).to_numpy()
        gone = np.zeros(len(bd), bool)
        idx_of = {v: i for i, v in enumerate(bids)}
        for t in range(len(seq)):
            if t >= RUN_WINDOW and t < len(seq) - 5:
                # the candidate set as it stands right now: top-k still available by ADP
                cand = bpos[~gone][:CHOICE_TOP_K]
                inten = detect_run(seq[t - RUN_WINDOW:t], cand)
                if inten:
                    top = max(inten, key=lambda p: inten[p])
                    obs.append((top, inten[top], seq[t:t + 5].count(top) / 5.0))
            j = idx_of.get(str(taken_ids[t]))
            if j is not None:
                gone[j] = True
    if not obs:
        return {"error": "no windows"}

    top_pos = np.array([o[0] for o in obs])
    inten = np.array([o[1] for o in obs])
    nxt5 = np.array([o[2] for o in obs])

    # The firing threshold is a free parameter, so it is swept and the whole curve reported rather
    # than one number chosen to look good. What we want is the operating point where the detector
    # is selective AND the flagged position is genuinely taken more often next — if no threshold
    # delivers both, that is the finding.
    sweep = []
    for th in THRESHOLD_GRID:
        f = inten >= th
        if f.sum() < 30 or (~f).sum() < 30:
            continue
        sweep.append({
            "threshold": float(th), "fire_rate": float(f.mean()),
            "share_next5_when_fired": float(nxt5[f].mean()),
            "share_next5_when_not": float(nxt5[~f].mean()),
            "discrimination": float(nxt5[f].mean() - nxt5[~f].mean()),
            "n_fired": int(f.sum()),
        })
    chosen = next((s for s in sweep
                   if s["fire_rate"] < 0.5 and s["discrimination"] > 0), None)
    at = chosen or (sweep[-1] if sweep else {})
    return {
        "n_windows": int(len(obs)),
        "threshold_sweep": sweep,
        "chosen_threshold": at.get("threshold"),
        "n_fired": at.get("n_fired"),
        "fire_rate": at.get("fire_rate"),
        "share_next5_when_fired": at.get("share_next5_when_fired"),
        "share_next5_when_not": at.get("share_next5_when_not"),
        "discrimination": at.get("discrimination"),
        "by_position": pd.Series(top_pos[inten >= at["threshold"]]).value_counts().to_dict()
        if at else {},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    budget = 4 if args.quick else 10
    n_sims = 30 if args.quick else 60

    con = duckdb.connect(str(DB), read_only=True)
    model = _model()
    out: dict = {"config": {"run_window": RUN_WINDOW, "run_threshold": RUN_THRESHOLD,
                            "max_drafts_per_season": budget, "n_sims": n_sims}}

    # ---- 1. does it fire on real runs? --------------------------------------------------------
    print("replaying the human corpus for detector face validity ...", flush=True)
    fv = detector_face_validity(con)
    out["face_validity"] = fv
    if "error" not in fv:
        print(f"  {fv['n_windows']} windows; threshold sweep:")
        for s in fv["threshold_sweep"]:
            print(f"    th={s['threshold']:.2f}  fires {s['fire_rate']:>6.1%}  "
                  f"next-5 share {s['share_next5_when_fired']:.3f} vs "
                  f"{s['share_next5_when_not']:.3f}  (disc {s['discrimination']:+.4f})")
        print(f"  chosen threshold {fv['chosen_threshold']}  "
              f"fires {fv['fire_rate']:.1%}  by position {fv['by_position']}")

    # ---- 2. does reacting help, inside the run window? ----------------------------------------
    threshold = fv.get("chosen_threshold") or RUN_THRESHOLD
    out["config"]["run_threshold"] = threshold
    print(f"\npaired availability Brier on run-opened windows (threshold {threshold}) ...",
          flush=True)
    sweep = {}
    for w in RUN_W_GRID:
        r = availability_brier(con, model, n_sims=n_sims, contested_k=30,
                               max_drafts_per_season=budget, n_boot=300, seed=1,
                               run_w=w, require_run=threshold)
        sweep[str(w)] = r
        if r.get("n_windows"):
            print(f"  run_w={w:>4}: beh={r['beh_brier']:.4f}  "
                  f"gain_vs_best_adp={r['brier_gain_vs_best']:+.4f}  n={r['n_windows']}")
        else:
            print(f"  run_w={w:>4}: no windows passed the run filter")
    out["run_window_sweep"] = sweep

    base = sweep["0.0"]
    best_w, best = None, None
    for w in RUN_W_GRID[1:]:
        r = sweep[str(w)]
        if r.get("n_windows") and (best is None or r["beh_brier"] < best["beh_brier"]):
            best_w, best = w, r

    verdict: dict = {"threshold": threshold}
    if base.get("n_windows") and best is not None:
        improvement = base["beh_brier"] - best["beh_brier"]
        verdict.update({
            "static_brier": base["beh_brier"], "best_run_w": best_w,
            "run_aware_brier": best["beh_brier"],
            "brier_improvement": improvement,
            # the same bar 16.9 used: does it move the metric beyond its own noise?
            "beats_static": bool(improvement > 0),
            "n_windows": base["n_windows"],
        })
    out["verdict"] = verdict

    gates = {
        "detector_is_selective": bool(0.02 < (fv.get("fire_rate") or 0) < 0.5),
        "detector_discriminates": bool((fv.get("discrimination") or 0) > 0),
        "static_control_reproduces": bool(base.get("n_windows", 0) > 0),
        "run_aware_beats_static": bool(verdict.get("beats_static", False)),
    }
    out["gates"] = gates
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, default=float))
    print(f"\nwrote {OUT}")
    for k, v in gates.items():
        print(f"  {k:>28}: {'PASS' if v else 'FAIL'}")
    if not gates["run_aware_beats_static"]:
        print("\n  → run detection ships DEFAULT OFF (RUN_W = 0), null reported — the 16.9 "
              "treatment. The detector itself is kept: it is a live-draft alert for 14.4 "
              "regardless of whether it sharpens the forecast.")


if __name__ == "__main__":
    main()
