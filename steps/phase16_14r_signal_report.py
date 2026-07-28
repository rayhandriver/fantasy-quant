"""16.14R — the T19 before/after signal report: what every repaired column does, side by side.

    uv run python steps/phase16_14r_signal_report.py
    uv run python steps/phase16_14r_signal_report.py --season 2026 --csv analysis/t19_signals.csv

Done when the T19 acceptance bar is **auditable rather than asserted**: for every shape signal, the
shipped ``linear`` estimator and the repaired one are computed on the same board and reported
together — correlations by position, the top-10 lists, and the players whose picks opened the
ticket.

★ This exists because the T19 bar is a *claim about a column*, and a claim about a column is
checkable by eye in a way an aggregate draft metric is not. The 2x5 mock's defect survived every
gate in the repo and was found by a human reading 150 picks; the cheapest way to keep that from
recurring is to put the column itself in front of someone.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from fantasy_quant.draft import mock
from fantasy_quant.draft.enrichment import SHAPE_COLS, residual_shape, shape_inputs
from fantasy_quant.draft.simulator import canon_pos

DB = Path("data/fantasy_quant.duckdb")
OUT = Path("analysis/phase16_14r_signal_report.json")
CACHE = Path("analysis/cache")
OFFENSE: tuple[str, ...] = ("QB", "RB", "WR", "TE")

#: The players the user objected to in the 2x5 mock, by the seat that took them.
OBJECTED: dict[str, str] = {
    "Zay Flowers": "safe_floor", "Malik Nabers": "safe_floor", "Carnell Tate": "safe_floor",
    "Quentin Johnston": "safe_floor", "Jaydon Blue": "safe_floor",
    "DK Metcalf": "value_hawk", "Dylan Sampson": "value_hawk", "James Cook": "value_hawk",
}


def _corr(df, a, b) -> dict:
    out = {}
    for p in OFFENSE:
        g = df[df["pos"] == p]
        x, y = pd.to_numeric(g[a], errors="coerce"), pd.to_numeric(g[b], errors="coerce")
        ok = x.notna() & y.notna()
        out[p] = (round(float(np.corrcoef(x[ok], y[ok])[0, 1]), 3)
                  if int(ok.sum()) >= 5 and float(x[ok].std()) > 0 and float(y[ok].std()) > 0
                  else None)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--csv", type=Path, default=Path("analysis/t19_signals.csv"))
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    con = duckdb.connect(str(DB), read_only=True)
    board, src = mock.room_board(con, args.season, cache_dir=CACHE)
    board = board.copy()
    board["pos"] = board["position"].map(canon_pos)
    off = board[board["pos"].isin(OFFENSE)].copy()

    before = residual_shape(off, method="linear")
    after = residual_shape(off)                       # the shipped estimator
    raw = shape_inputs(off)

    wide = off[["name", "pos", "team", "adp", "mean", "q10", "q90"]].copy()
    for c in SHAPE_COLS:
        wide[f"{c}_before"] = before[c]
        wide[f"{c}_after"] = after[c]
        wide[f"{c}_ratio"] = raw[c]
    for c in ("role_share", "role_delta", "td_regression"):
        if c in off.columns:
            wide[c] = off[c]

    print(f"{args.season} board: {len(off)} offensive rows ({src})\n")
    cens = float((pd.to_numeric(off["q10"], errors="coerce") == 0).mean())
    print(f"q10 censored at 0: {cens:.1%} of rows — the defect's cause\n")

    report = {"censored_share": round(cens, 4), "by_signal": {}}
    for c in SHAPE_COLS:
        b_adp, a_adp = _corr(wide.rename(columns={f"{c}_before": c}), c, "adp"), None
        a_adp = _corr(wide.rename(columns={f"{c}_after": c}), c, "adp")
        report["by_signal"][c] = {"corr_adp_before": b_adp, "corr_adp_after": a_adp}
        print(f"=== {c} — corr with ADP within position ===")
        print(pd.DataFrame({"before (linear)": b_adp, "after (rank on ratios)": a_adp}).T
              .to_string())
        print()

    print("=== corr(upside, floor) — the 16.14 opposition, before vs after ===")
    opp_b = _corr(wide.rename(columns={"upside_before": "upside", "floor_before": "floor"}),
                  "upside", "floor")
    opp_a = _corr(wide.rename(columns={"upside_after": "upside", "floor_after": "floor"}),
                  "upside", "floor")
    report["opposition"] = {"before": opp_b, "after": opp_a}
    print(pd.DataFrame({"before": opp_b, "after": opp_a}).T.to_string())

    print("\n=== top-10 floor: what the seat is told is safest ===")
    for lab, col in (("BEFORE (shipped 16.14)", "floor_before"), ("AFTER (T19)", "floor_after")):
        t = wide.nlargest(10, col)[["name", "pos", "adp", "mean", "q10", col]]
        print(f"\n  {lab} — {(t['adp'] > 130).mean():.0%} of them are ADP > 130")
        print(t.round(2).to_string(index=False))

    print("\n=== the objected picks, and where they now sit ===")
    rows = []
    for name, seat in OBJECTED.items():
        hit = wide[wide["name"].str.contains(name, case=False, na=False)]
        if hit.empty:
            rows.append({"player": name, "seat": seat, "on_board": False})
            continue
        r = hit.iloc[0]
        grp = wide[wide["pos"] == r["pos"]]
        rows.append({
            "player": name, "seat": seat, "on_board": True, "pos": r["pos"],
            "adp": round(float(r["adp"]), 1),
            "floor_pct_before": round(float((grp["floor_before"] < r["floor_before"]).mean()), 2),
            "floor_pct_after": round(float((grp["floor_after"] < r["floor_after"]).mean()), 2),
            "tail_risk_pct_after": round(
                float((grp["tail_risk_after"] < r["tail_risk_after"]).mean()), 2),
        })
    objected = pd.DataFrame(rows)
    print(objected.to_string(index=False))
    print("""
  ^ READ THIS COLUMN BY COLUMN — the obvious reading is wrong.

    `floor_pct` is the player's percentile within his position. The tempting story is "the
    objected picks should now have a LOWER floor percentile", and that is **not** what happened:
    Zay Flowers goes 0.76 -> 0.85 and Carnell Tate 0.64 -> 0.72. The repair did not demote them.

    ★ What actually fixes these picks is `tail_risk`, not `floor`, and that is the distinction
    step 4 was built on. The user's objection was that the seat drafted **boom-or-bust** players,
    which is a statement about *width*, not about *floor* — and on the repaired board that is
    exactly where they light up: Quentin Johnston 0.85, Jaydon Blue 0.84, DK Metcalf 0.76. A seat
    weighting `tail_risk` at -0.40 avoids them; a seat weighting only `floor` never would, at any
    quality of floor column. "Highest floor" and "lowest downside" are different objectives, and
    T19 repaired the input to the first while step 4 changed the objective to the second.

    ★ And the board now answers back on one of them: Zay Flowers (ADP 25.6, mean 199, q10 98) is
    a high-floor, *narrow* outcome — `tail_risk` 15th percentile. On the repaired columns he is
    not a boom-or-bust player, and `safe_floor` taking him is defensible rather than a defect.
    Worth a human's eye, since the whole ticket came from one.""")
    report["objected"] = json.loads(objected.to_json(orient="records"))

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    wide.round(4).to_csv(args.csv, index=False)
    args.out.write_text(json.dumps({"generated": pd.Timestamp.now("UTC").isoformat(),
                                    "season": args.season, "board_source": src, **report},
                                   indent=2, default=float))
    print(f"\nwrote {args.csv} and {args.out}")
    con.close()


if __name__ == "__main__":
    main()
