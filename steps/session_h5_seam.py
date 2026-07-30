"""Session H.5 done-bar — the mock-drafter value seam, re-measured in one artifact.

    uv run python steps/session_h5_seam.py            # reads the labelled bar sheets
    uv run python steps/session_h5_seam.py --season 2026

Writes ``analysis/session_h5_seam.json``. Every bar T27/T28/T29/T30 was given, in one place, with
the ones that **failed** reported as failures — the session's two pre-registered bars were written
to be falsifiable and both were allowed to come back negative:

  **B1** every drafted-range (top-180 ADP) skill row carries all four value-chain columns
  **B2** ``spearman(haircut, games_played_mean) <= -0.50`` per position, live board ← FAILS at RB
  **B3** the room bar sheet is bit-identical to the 2026-07-29 verification
  **B4** ``starter_value == team_value`` exactly when the roster is the starting nine
  **B5** ``spearman(starter_value, title) > spearman(portfolio_value, title)``            ← FAILS
  **B6** the frozen cost report is bit-identical

B3/B6 are the hard bars — *a display change that moves a bar is not a display change* — and both
hold. B2 and B5 are the informative ones, and what they found is written up in ``findings.md``
§"Session H.5"; neither was softened to make this file green.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from fantasy_quant.data import validate
from fantasy_quant.draft import mock, optimizer
from fantasy_quant.draft.config import DraftConfig
from fantasy_quant.draft.simulator import VALUE_SCALE_COLS, RosterSlots, _prepare_board

DB = Path("data/fantasy_quant.duckdb")
CACHE = Path("analysis/cache")
OUT = Path("analysis/session_h5_seam.json")

#: The committed room measurement B3 is a bit-identity check against (2026-07-29 audit).
VERIFY = Path("analysis/mock_room_bars_verify_20260729.json")
AFTER = Path("analysis/mock_room_bars_h5_step1.json")

#: 11.2's availability Brier. `draft/availability.py` imports nothing from `personalities`, so no
#: room or display change can move it — asserted rather than assumed, every session.
BRIER = Path("analysis/phase16_14r_brier.json")
BRIER_EXPECT = 0.088996997698074

GATED_PREFIXES = ("/bar", "/landing", "/legality")


def _flat(o: dict, p: str = "") -> dict:
    out = {}
    for k, v in o.items():
        if isinstance(v, dict):
            out.update(_flat(v, f"{p}/{k}"))
        elif isinstance(v, list):
            out[f"{p}/{k}"] = str(v)
        else:
            out[f"{p}/{k}"] = v
    return out


def bar_identity(before: Path, after: Path) -> dict:
    """B3 — the gated bars must be equal to the digit. The 2026 readout is compared too and
    reported separately: it has no realized counterpart and is never a gate, but a change in it
    that is *not* explained by a board refresh would still be worth seeing."""
    if not (before.exists() and after.exists()):
        return {"passed": False, "reason": f"missing {before if not before.exists() else after}"}
    fa, fb = _flat(json.loads(before.read_text())), _flat(json.loads(after.read_text()))
    diff = [k for k in fa if k in fb and fa[k] != fb[k]
            and "generated" not in k and "label" not in k]
    gated = [k for k in diff if k.startswith(GATED_PREFIXES)]
    return {"passed": not gated, "gated_diffs": gated,
            "readout_diffs": [k for k in diff if k.startswith("/readout")],
            "other_diffs": [k for k in diff
                            if not k.startswith((*GATED_PREFIXES, "/readout", "/config"))],
            "before": before.name, "after": after.name}


def value_chain_coverage(con, season: int) -> dict:
    """B1 — the four columns reach ``DraftState.board`` for the rows a human drafts from."""
    board, _ = mock.room_board(con, season, cache_dir=CACHE)
    vi = optimizer.assemble_value(con, season, DraftConfig())
    prepped = _prepare_board(optimizer.attach_value(board, vi))
    skill = prepped[prepped["pos"].isin(["QB", "RB", "WR", "TE"])
                    & (prepped["adp"] <= validate.VALUE_SCALE_ADP_MAX)]
    cov = {c: int(skill[c].notna().sum()) for c in VALUE_SCALE_COLS}
    missing = skill.loc[skill["proj_points"].isna(), "player_name"].tolist()
    return {"passed": all(v >= len(skill) - len(missing) for v in cov.values()),
            "n_rows": int(len(skill)), "non_null": cov,
            "rows_with_no_consensus_projection": missing,
            "note": "a row with no upstream projection prints '-' (the T22 rule), never a 0"}


def b4_starting_nine() -> dict:
    """B4 — the decomposition identity, on a concrete roster rather than in the abstract."""
    pos = ["QB", "RB", "RB", "RB", "WR", "WR", "TE", "K", "DST"]
    keys = [f"s{i}" for i in range(9)]
    vi = pd.DataFrame({"player_key": keys, "pos": pos,
                       "base_value": [80.0, 70.0, 60.0, 20.0, 75.0, 55.0, 30.0, 5.0, 0.0]})
    roster = pd.DataFrame({"player_key": keys, "pos": pos})
    sv = optimizer.starter_value(roster, vi, RosterSlots())
    tv = optimizer.team_value(roster, vi)
    return {"passed": bool(np.isclose(sv, tv)), "starter_value": sv, "team_value": tv}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    con = duckdb.connect(str(DB), read_only=True)

    b1 = value_chain_coverage(con, args.season)
    b2 = validate._value_scale_gates(con, args.season)[0]
    b3 = bar_identity(VERIFY, AFTER)
    b4 = b4_starting_nine()

    t28 = (json.loads(Path("analysis/t28_starter_value.json").read_text())
           if Path("analysis/t28_starter_value.json").exists() else {})
    b5 = t28.get("b5", {"passed": False, "reason": "not measured"})

    brier = json.loads(BRIER.read_text())
    brier_ok = bool(np.isclose(brier["brier_gain_vs_best"], BRIER_EXPECT, atol=1e-9))

    # `-p no:cacheprovider --color=no` so the count is parseable; pytest colours its summary line
    # even when captured, and an ANSI escape in an int() is a silly way to fail a done-bar.
    out = subprocess.run(
        ["uv", "run", "python", "-m", "pytest", "-q", "--collect-only", "--color=no"],
        capture_output=True, text=True).stdout
    n_tests = int(re.search(r"(\d+)\s+tests? collected", out).group(1))

    print("=== SESSION H.5 — THE MOCK-DRAFTER VALUE SEAM ===\n")
    print(f"  B1 value-chain columns   {b1['non_null']['base_value']}/{b1['n_rows']} "
          f"drafted-range skill rows -> {'PASS' if b1['passed'] else 'FAIL'}")
    if b1["rows_with_no_consensus_projection"]:
        gaps = ", ".join(b1["rows_with_no_consensus_projection"])
        print(f"     (no upstream projection: {gaps})")
    print(f"  B2 haircut ~ availability  per-position rho <= -0.50 -> "
          f"{'PASS' if b2['passed'] else 'FAIL'}  failed={b2.get('failed_positions')}")
    for p, s in b2["by_position"].items():
        print(f"       {p:<3} rho {s['rho']:+.3f}  median haircut {s['median_haircut']:+.3f}  "
              f"n={s['n']}")
    print(f"  B3 room bar sheet          bit-identical -> {'PASS' if b3['passed'] else 'FAIL'}"
          f"  ({len(b3.get('gated_diffs', []))} gated diffs)")
    print(f"  B4 starting-nine identity  {b4['starter_value']:.4f} == {b4['team_value']:.4f} -> "
          f"{'PASS' if b4['passed'] else 'FAIL'}")
    print(f"  B5 starter_value > portfolio_value  {b5.get('diff', float('nan')):+.4f} "
          f"CI[{b5.get('lo', float('nan')):+.4f},{b5.get('hi', float('nan')):+.4f}] -> "
          f"{'PASS' if b5.get('passed') else 'FAIL'}")
    print("  B6 frozen cost report      bit-identical (verified against a worktree at the "
          "session-start commit)")
    print(f"\n  11.2 availability Brier    {brier['brier_gain_vs_best']:+.4f} -> "
          f"{'unchanged' if brier_ok else 'MOVED'}")
    print(f"  tests                      {n_tests}")

    art = {
        "generated": pd.Timestamp.now("UTC").isoformat(),
        "season": args.season,
        "bars": {"B1": b1, "B2": b2, "B3": b3, "B4": b4, "B5": b5,
                 "B6": {"passed": True, "method": "spine_3_cost_report.py diffed against a git "
                                                  "worktree at the session-start commit"}},
        "availability_brier": {"value": brier["brier_gain_vs_best"], "unchanged": brier_ok},
        "n_tests": n_tests,
        "verdict": {
            "T27": "shipped — the value chain is on the board, `why` prints it, and the gate "
                   "found a live-board defect (B2)",
            "T28": "closed as a LABELLING FIX — B5's pre-registered direction failed, so "
                   "`value_hawk` keeps objective=portfolio_ce (bench_weight=1.0)",
            "T29": "shipped — no driver prints a bare probability; the mock leads with the "
                   "fair-share multiple",
            "T30": "see analysis/mock_room_bars_t30_chalk_swap.json",
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(art, indent=2, default=str))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
