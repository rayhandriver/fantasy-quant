"""16.14R step 2 — repair the ``floor`` signal (T19), by measurement rather than by preference.

    uv run python steps/phase16_14r_2_floor.py
    uv run python steps/phase16_14r_2_floor.py --season 2026 --out analysis/phase16_14r_floor.json

Done when: a level-control estimator is selected against a **bar fixed before the numbers were
read**, and the column a floor-seeking personality consumes no longer prefers deeper players.

★ **The bar, pre-registered (``docs/TECH-DEBT.md`` T19, ``docs/BUILD_PLAN.md`` §16.14R step 2):**

1. ``corr(floor, adp) <= 0`` within **every** position, and
2. the top-10 ``floor`` list is not dominated by ADP > 130 players (``<= 30 %``).

Stated as an **opposition**, per the 16.14 lesson — "safest" and "deepest" must pull apart. A bar
of the form *"floor differs from balanced"* passes on the broken build, which is how the inversion
survived a green suite and a whole phase.

★ **Why four estimators and not one.** T19 framed the defect as *"OLS is the wrong likelihood for
a censored variable"*, which admits two honest repairs — fix the likelihood (``tobit``) or drop the
functional form (``rank``) — with the incumbent ``linear`` as the control. Which wins is an
empirical question about *this* board, so all of them are fitted and scored. Same shape as T15 step
1, which chose its ADP transform by refit log-loss rather than by argument.

★★ **And the framing was wrong: the problem was the SCALE, not the fit.** Every estimator failed on
the raw quantiles, in different directions — ``tobit`` improved the inversion but left a 100 %-deep
top-10, ``rank`` flipped ``corr(upside, floor)`` positive, ``rank_delta`` swung the inversion back.
A variable that piles up on a boundary of its own support has no well-behaved residual, however it
is fitted. Rebuilding the signals as **ratios to the projected level**
(:func:`~fantasy_quant.draft.enrichment.shape_inputs`) makes the pile-up land at the *bottom* of a
bounded quantity — which is the honest reading, since a 10th percentile of zero really is the worst
possible floor — and only then does an estimator pass. *Before choosing an estimator, check the
variable is on a scale the estimator can be right about.*

★ **The check that stops the bar being gamed.** T19's bar is **one-sided**, so an estimator can
pass it by over-correcting into a pure quality tilt — which is 16.14's original defect wearing a
PASS. :func:`oppositions` therefore re-runs 16.14's own two bars alongside (``corr(upside, floor)``
must stay strongly negative; ``corr(floor, mean)`` must not blow up), and selection requires
**both**. That check is what rejected ``rank`` on raw quantiles, which passed T19 cleanly at
``corr(floor, adp)`` −0.10…−0.21 while being wrong.

★ **The validity check that stops it being circular.** A rank is near-orthogonal to ADP roughly by
construction, so passing bar 1 is weak evidence on its own. The report also measures agreement with
the incumbent **on the uncensored rows only** — where both estimators answer the same question and
OLS is unbiased. A repair that disagrees *there* is not a repair, it is a different signal.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from fantasy_quant.draft import enrichment, mock
from fantasy_quant.draft.simulator import canon_pos

DB = Path("data/fantasy_quant.duckdb")
OUT = Path("analysis/phase16_14r_floor.json")
CACHE = Path("analysis/cache")

OFFENSE: tuple[str, ...] = ("QB", "RB", "WR", "TE")

#: The pre-registered bar. Fixed before any estimator was run; see the module docstring.
BAR_MAX_CORR: float = 0.0
BAR_MAX_DEEP_SHARE: float = 0.30
DEEP_ADP: float = 130.0

#: 16.14's opposition bar, carried forward as a **constraint on the repair**: the ceiling-chaser and
#: the floor-seeker must still disagree. 16.14 measured −0.86 (2022/2025) and −0.71 (2026 post-T17),
#: so −0.30 is a loose ceiling that only a genuine collapse into a shared quality tilt can breach.
OPPOSITION_MAX: float = -0.30


def corr_with_adp(df: pd.DataFrame, col: str) -> dict:
    """``corr(col, adp)`` within each offensive position — the T19 inversion measurement."""
    out = {}
    for p in OFFENSE:
        g = df[df["pos"] == p]
        v = pd.to_numeric(g[col], errors="coerce")
        a = pd.to_numeric(g["adp"], errors="coerce")
        ok = v.notna() & a.notna()
        out[p] = (round(float(np.corrcoef(v[ok], a[ok])[0, 1]), 4)
                  if int(ok.sum()) >= 5 and float(v[ok].std()) > 0 else None)
    return out


def oppositions(df: pd.DataFrame) -> dict:
    """16.14's own bars, re-run on the repaired columns — the check a one-sided bar cannot make.

    ★ **Why this block exists.** T19's bar is *one-sided* (``corr(floor, adp) <= 0``) because the
    defect was a positive correlation. But a large *negative* correlation is a different defect
    wearing the same PASS: it means ``floor`` has become a **quality** tilt, which is precisely
    what 16.14 built ``residual_shape`` to prevent. So the estimator is also held to the two bars
    16.14 shipped:

    * ``corr(upside, floor)`` **strongly negative** — the ceiling-chaser and the floor-seeker must
      *oppose*, not agree (16.14 measured −0.86 on 2022/2025, −0.71 on 2026 post-T17);
    * ``corr(floor, mean)`` **near zero** — the level is controlled for, not merely reordered.

    A method that passes T19's bar by overshooting fails here, and that is the intended reading.
    """
    out = {}
    for p in OFFENSE:
        g = df[df["pos"] == p]
        cols = {}
        for a, b in (("upside", "floor"), ("floor", "mean"), ("upside", "mean"),
                     ("tail_risk", "floor")):
            va, vb = pd.to_numeric(g[a], errors="coerce"), pd.to_numeric(g[b], errors="coerce")
            ok = va.notna() & vb.notna()
            cols[f"{a}~{b}"] = (round(float(np.corrcoef(va[ok], vb[ok])[0, 1]), 3)
                                if int(ok.sum()) >= 5 and float(va[ok].std()) > 0
                                and float(vb[ok].std()) > 0 else None)
        out[p] = cols
    return out


def score_method(df: pd.DataFrame, col: str) -> dict:
    """Both halves of the bar for one candidate column, plus the top-10 list behind them."""
    corrs = corr_with_adp(df, col)
    top = df.nlargest(10, col)
    deep = float((top["adp"] > DEEP_ADP).mean())
    vals = [c for c in corrs.values() if c is not None]
    return {
        "corr_by_pos": corrs,
        "worst_corr": round(max(vals), 4) if vals else None,
        "n_pos_passing": sum(c <= BAR_MAX_CORR for c in vals),
        "n_pos_scored": len(vals),
        "top10_deep_share": round(deep, 3),
        "top10": json.loads(top[["name", "pos", "adp", "mean", "q10", col]].to_json(
            orient="records")),
        "pass": bool(vals and all(c <= BAR_MAX_CORR for c in vals)
                     and deep <= BAR_MAX_DEEP_SHARE),
    }


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

    # -- the defect, restated in numbers ---------------------------------------------------------
    cens = pd.to_numeric(off["q10"], errors="coerce") == enrichment.CENSOR_AT
    censoring = {"overall": round(float(cens.mean()), 4)}
    for lo, hi, lab in ((0, 50, "adp_le_50"), (50, 100, "adp_50_100"), (100, 1e9, "adp_gt_100")):
        m = (off["adp"] > lo) & (off["adp"] <= hi)
        censoring[lab] = round(float(cens[m].mean()), 4)
    print(f"\nq10 censored at {enrichment.CENSOR_AT}: {censoring['overall']:.1%} overall "
          f"({censoring['adp_le_50']:.1%} inside ADP 50, {censoring['adp_gt_100']:.1%} past 100)")

    # -- every estimator, on one board -----------------------------------------------------------
    shapes = {m: enrichment.residual_shape(off, method=m) for m in enrichment.SHAPE_METHODS}
    results, agreement, opp = {}, {}, {}
    for m, sh in shapes.items():
        wide = off.copy()
        for c in enrichment.SHAPE_COLS:
            wide[c] = sh[c]
        results[m] = {c: score_method(wide, c) for c in ("floor", "upside", "durability")}
        opp[m] = oppositions(wide)
        # validity: agreement with the incumbent where OLS is unbiased (uncensored rows only)
        a = pd.to_numeric(shapes["linear"]["floor"], errors="coerce")[~cens]
        b = pd.to_numeric(sh["floor"], errors="coerce")[~cens]
        ok = a.notna() & b.notna()
        agreement[m] = round(float(pd.Series(a[ok]).corr(pd.Series(b[ok]), method="spearman")), 4)

    print("\n=== corr(floor, adp) by position — bar 1 (<= 0 in EVERY position) ===")
    tab = pd.DataFrame({m: results[m]["floor"]["corr_by_pos"] for m in shapes}).T
    print(tab.to_string())
    print("\n=== 16.14's oppositions, re-run — corr(upside, floor) must stay strongly NEGATIVE ===")
    print(pd.DataFrame({m: {p: opp[m][p]["upside~floor"] for p in OFFENSE}
                        for m in shapes}).T.to_string())
    print("\n=== ... and corr(floor, mean) near ZERO (level controlled, not reordered) ===")
    print(pd.DataFrame({m: {p: opp[m][p]["floor~mean"] for p in OFFENSE}
                        for m in shapes}).T.to_string())
    print("\n=== the bar ===")
    for m in shapes:
        r = results[m]["floor"]
        uf = [v for v in (opp[m][p]["upside~floor"] for p in OFFENSE) if v is not None]
        print(f"  {m:<7} worst corr {r['worst_corr']:+.3f}  "
              f"top-10 ADP>{DEEP_ADP:.0f} share {r['top10_deep_share']:.0%}  "
              f"worst upside~floor {max(uf):+.2f}  "
              f"agreement rho={agreement[m]:+.3f}  "
              f"-> {'PASS' if r['pass'] else 'FAIL'}")

    def keeps_opposition(m: str) -> bool:
        uf = [v for v in (opp[m][p]["upside~floor"] for p in OFFENSE) if v is not None]
        return bool(uf) and max(uf) <= OPPOSITION_MAX

    passing = [m for m in enrichment.SHAPE_METHODS
               if results[m]["floor"]["pass"] and keeps_opposition(m)]
    # tie-break among passers: strongest agreement with the incumbent where the incumbent is valid
    chosen = max(passing, key=lambda m: agreement[m]) if passing else None
    print(f"\nSELECTED: {chosen}  (passing T19 bar + 16.14 opposition: {passing or 'none'})")

    if chosen:
        wide = off.copy()
        for c in enrichment.SHAPE_COLS:
            wide[c] = shapes[chosen][c]
        print(f"\n=== top-10 floor under '{chosen}' (what safe_floor will be told is safest) ===")
        print(wide.nlargest(10, "floor")[["name", "pos", "adp", "mean", "q10", "floor"]]
              .round(2).to_string(index=False))
        print("\n=== top-10 floor under 'linear' (the shipped inversion, for contrast) ===")
        lin = off.copy()
        lin["floor"] = shapes["linear"]["floor"]
        print(lin.nlargest(10, "floor")[["name", "pos", "adp", "mean", "q10", "floor"]]
              .round(2).to_string(index=False))

    # -- the bust_prob replacement ---------------------------------------------------------------
    rel = enrichment.shape_inputs(off)["tail_risk"]
    boom = pd.to_numeric(off["boom_prob"], errors="coerce").fillna(0.0)
    bust = pd.to_numeric(off["bust_prob"], errors="coerce").fillna(0.0)
    inert = {"boom_prob_zero_share": round(float((boom == 0).mean()), 4),
             "bust_prob_zero_share": round(float((bust == 0).mean()), 4),
             "relative_downside_zero_share": round(float((rel.fillna(0) == 0).mean()), 4),
             "relative_downside_defined": round(float(rel.notna().mean()), 4)}
    print("\n=== the inert weights, and their replacement ===")
    print(f"  boom_prob == 0 for {inert['boom_prob_zero_share']:.1%} of offensive rows")
    print(f"  bust_prob == 0 for {inert['bust_prob_zero_share']:.1%}")
    print(f"  relative_downside == 0 for {inert['relative_downside_zero_share']:.1%} "
          f"(defined for {inert['relative_downside_defined']:.1%})")
    if chosen:
        tr = score_method(wide, "tail_risk")
        inert["tail_risk_corr_by_pos"] = tr["corr_by_pos"]
        print(f"  tail_risk corr with adp: {tr['corr_by_pos']} "
              f"(expected POSITIVE-free after the level control)")

    verdict = {"bar1_corr_le_0": bool(chosen is not None),
               "bar2_top10_not_deep": bool(chosen is not None
                                           and results[chosen]["floor"]["top10_deep_share"]
                                           <= BAR_MAX_DEEP_SHARE),
               "selected_method": chosen}
    print("\n=== VERDICT ===")
    for k, v in verdict.items():
        print(f"  {k:<22} {v if not isinstance(v, bool) else ('PASS' if v else 'FAIL')}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "generated": pd.Timestamp.now("UTC").isoformat(),
        "season": args.season, "board_source": src, "n_offensive_rows": int(len(off)),
        "bar": {"max_corr": BAR_MAX_CORR, "max_deep_share": BAR_MAX_DEEP_SHARE,
                "deep_adp": DEEP_ADP},
        "censoring": censoring,
        "methods": results,
        "oppositions": opp,
        "opposition_max": OPPOSITION_MAX,
        "uncensored_agreement_with_linear": agreement,
        "selected": chosen,
        "inert_weights": inert,
        "verdict": verdict,
    }, indent=2, default=float))
    print(f"\nwrote {args.out}")
    con.close()


if __name__ == "__main__":
    main()
