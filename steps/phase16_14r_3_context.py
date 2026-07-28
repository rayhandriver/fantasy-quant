"""16.14R step 3 — the structural context a value objective is blind to.

    uv run python steps/phase16_14r_3_context.py
    uv run python steps/phase16_14r_3_context.py --season 2026

Done when: the three columns exist on the live board, their coverage is **reported rather than
assumed**, and the players whose picks motivated the step carry the signals they were missing.

★ **The finding this step encodes: the value hawk's bad picks were blind spots, not mis-weights.**
The 2x5 mock's objections — DK Metcalf, Dylan Sampson, James Cook — are not fixable by reweighting,
because *no* objective over the 16.13 board can see what is wrong with them. ``vbd`` prices **how
much**; it cannot price **how contested**, **which direction the situation moved**, or **how much
of last year was touchdown luck**. Reweighting a board that lacks a column is how a session spends
itself tuning around a missing input, so board scope moves before any personality does.

★★ **All three are DERIVED, and that was a deliberate re-do of the obvious plan.** The natural
sources are a depth-chart feed (committee), a curated research table (signed situation) and a
modelling exercise (TD regression). The repo's "derived-vs-curated" rule says hand-curate only what
has no free source, and the test is not *"is this hard to look up"* but *"does a table we already
ingest contain it"*. Three do:

* ``role_share``    the board's own projections, grouped by (team, position) — a bell-cow owns ~1.0
                    of his team's positional projection, half a committee owns ~0.5.
* ``role_delta``    that share minus the share he **realized** last season, from ``weekly``. Signed,
                    with no annotation in it anywhere. This is what ``cos`` could never be: 16.5's
                    event board scores how *loud* a story is (Rachaad White 1.0, DK Metcalf 0.6),
                    never whether it is good news.
* ``td_regression`` Phase 3.2's ``td_regression_flag`` on the prior season — TDs over what red-zone
                    opportunity implies, whose measured next-year correlation is **−0.50**.

Ships **labelled, read-only and default-OFF**: every seat's weight is 0.0 unless it opts in, per the
"level, not the residual" rule (ADP has already absorbed the story, so these are not deviation
drivers). Step 6's value hawk is the one consumer.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from fantasy_quant.draft import mock
from fantasy_quant.draft.enrichment import CONTEXT_COLS
from fantasy_quant.draft.simulator import canon_pos

DB = Path("data/fantasy_quant.duckdb")
OUT = Path("analysis/phase16_14r_context.json")
CACHE = Path("analysis/cache")

OFFENSE: tuple[str, ...] = ("QB", "RB", "WR", "TE")

#: The three picks the user objected to in the 2x5 mock, and what each was meant to expose. Named
#: here so the spot-check is a **stated prediction** rather than a story told after the numbers.
SPOT_CHECK: dict[str, str] = {
    "DK Metcalf": "role_delta",        # changed team — is the new room better or worse?
    "Dylan Sampson": "role_share",     # behind Judkins in a committee backfield
    "James Cook": "td_regression",     # touchdown-dependent production
}

#: Minimum fill rate for a column to be usable by a personality at all. Below this the seat is
#: tilting on a handful of rows and the rest of the board reads as neutral.
MIN_COVERAGE: float = 0.50


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    con = duckdb.connect(str(DB), read_only=True)
    board, src = mock.room_board(con, args.season, cache_dir=CACHE)
    board = board.copy()
    board["pos"] = board["position"].map(canon_pos)
    off = board[board["pos"].isin(OFFENSE)].copy()
    print(f"{args.season} board: {len(board)} rows ({src}), offensive {len(off)}")

    # -- coverage, reported not assumed ----------------------------------------------------------
    coverage = {}
    print("\n=== coverage ===")
    for c in CONTEXT_COLS:
        v = pd.to_numeric(off.get(c), errors="coerce")
        filled = float(v.notna().mean()) if v is not None else 0.0
        coverage[c] = round(filled, 4)
        desc = (f"mean {v[v.notna()].mean():+.3f}  sd {v[v.notna()].std():.3f}"
                if filled else "absent")
        print(f"  {c:<14} {filled:6.1%}   {desc}")

    # -- what they are NOT: a restatement of the level -------------------------------------------
    print("\n=== these must not be `vbd` in disguise (corr within position) ===")
    rows = []
    for c in CONTEXT_COLS:
        r = {"signal": c}
        for p in OFFENSE:
            g = off[off["pos"] == p]
            v, b = pd.to_numeric(g[c], errors="coerce"), pd.to_numeric(g["vbd"], errors="coerce")
            ok = v.notna() & b.notna()
            r[p] = (round(float(np.corrcoef(v[ok], b[ok])[0, 1]), 3)
                    if int(ok.sum()) >= 5 and float(v[ok].std()) > 0 else None)
        rows.append(r)
    vbd_corr = pd.DataFrame(rows)
    print(vbd_corr.to_string(index=False))

    # -- the spot-check: a stated prediction, then the numbers -----------------------------------
    print("\n=== spot-check — the three picks that motivated the step ===")
    spot = {}
    for name, expect in SPOT_CHECK.items():
        hit = off[off["name"].str.contains(name, case=False, na=False)]
        if hit.empty:
            print(f"  {name:<16} NOT ON BOARD")
            spot[name] = {"on_board": False, "expected_signal": expect}
            continue
        r = hit.iloc[0]
        vals = {c: (None if pd.isna(r.get(c)) else round(float(r[c]), 3)) for c in CONTEXT_COLS}
        pos_rows = off[off["pos"] == r["pos"]]
        pct = {c: (None if pd.isna(r.get(c)) else
                   round(float((pd.to_numeric(pos_rows[c], errors="coerce") < r[c]).mean()), 3))
               for c in CONTEXT_COLS}
        spot[name] = {"on_board": True, "expected_signal": expect, "pos": r["pos"],
                      "adp": round(float(r["adp"]), 1), "values": vals, "pos_percentile": pct}
        flag = "" if vals.get(expect) is None else f"  [{expect} = {vals[expect]:+.3f}, "\
                                                   f"pos pct {pct[expect]:.0%}]"
        print(f"  {name:<16} {r['pos']} ADP {float(r['adp']):5.1f}  "
              f"{ {k: v for k, v in vals.items()} }{flag}")

    # -- the extremes, so the columns are legible by eye ------------------------------------------
    print("\n=== most contested backfields/rooms (lowest role_share, RB/WR) ===")
    cont = off[off["pos"].isin(("RB", "WR")) & off["role_share"].notna()]
    print(cont.nsmallest(8, "role_share")[["name", "pos", "team", "adp", "role_share"]]
          .round(3).to_string(index=False))
    print("\n=== biggest role gains vs last season (role_delta) ===")
    rd = off[off["role_delta"].notna()]
    print(rd.nlargest(6, "role_delta")[["name", "pos", "team", "adp", "role_delta"]]
          .round(3).to_string(index=False))
    print("\n=== biggest TD-regression candidates ===")
    tr = off[off["td_regression"].notna()]
    print(tr.nlargest(6, "td_regression")[["name", "pos", "adp", "td_regression"]]
          .round(3).to_string(index=False))

    verdict = {
        "all_columns_present": bool(all(c in off.columns for c in CONTEXT_COLS)),
        "coverage_usable": bool(all(coverage[c] >= MIN_COVERAGE for c in CONTEXT_COLS)),
        "spot_checks_carry_their_signal": bool(all(
            v.get("on_board") and v["values"].get(v["expected_signal"]) is not None
            for v in spot.values())),
    }
    print("\n=== VERDICT ===")
    for k, v in verdict.items():
        print(f"  {k:<34} {'PASS' if v else 'FAIL'}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "generated": pd.Timestamp.now("UTC").isoformat(),
        "season": args.season, "board_source": src, "n_offensive_rows": int(len(off)),
        "coverage": coverage, "min_coverage": MIN_COVERAGE,
        "corr_with_vbd": json.loads(vbd_corr.to_json(orient="records")),
        "spot_check": spot,
        "verdict": verdict,
    }, indent=2, default=float))
    print(f"\nwrote {args.out}")
    con.close()


if __name__ == "__main__":
    main()
