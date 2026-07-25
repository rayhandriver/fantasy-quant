"""Phase 16.1 — situation-change ADP-alpha extension (team change · new starting QB).

    uv run python steps/phase16_1_situation_alpha.py

The Situation-Change Beta Lab, value side. Extends the Phase-6 ADP-alpha mining with two PIT
situation features and asks: does the crowd misprice a player who (a) **changed teams** in the
offseason, or (b) enters the season with a **new starting QB**? Same discipline as the DURABILITY
survivor: a season-block-bootstrap CI + a BH-FDR-adjusted p-value + walk-forward sign stability.
Each feature **survives or is honestly dropped** — no threshold is moved after seeing the result.

Walled off from the frozen cost report: this mines ``PHASE16_FEATURES`` (the pinned 5-trait
``FEATURES`` + the situation flags), never the ``FEATURES`` default the softness credit is frozen
on, so nothing here perturbs the cost report's DURABILITY constant. Runs on ``DEV_SEASONS``; the
2023 and 2024 lockbox is never read.

**PIT note (2026-07-24):** team-of-record comes from ``weekly`` (Week-1 team), NOT the ADP board's
``team`` column — that field is contaminated with an end-of-season crosswalk (it lists mid-season
2022 trades McCaffrey→SF, Toney→KC as if known at draft day). See ``adp/panel.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

from fantasy_quant.adp.panel import PHASE16_FEATURES, SITUATION_FEATURES, build_alpha_panel
from fantasy_quant.adp.scorecard import bias_scorecard
from fantasy_quant.config import DEV_SEASONS, LOCKBOX_SEASONS
from fantasy_quant.data import db

OUT = Path(__file__).resolve().parents[1] / "analysis" / "phase16_1_situation_alpha.json"


def main() -> None:
    con = db.connect(read_only=True)

    # 16.1 — the panel (now carries the two PIT situation flags as 0/1 columns)
    panel = build_alpha_panel(con, seasons=DEV_SEASONS)
    assert not (set(panel["season"]) & set(LOCKBOX_SEASONS)), "lockbox leaked into the panel"
    for f in SITUATION_FEATURES:
        print(f"panel: {f:16s} rate = {panel[f].mean():5.1%}  "
              f"({int(panel[f].sum())}/{len(panel)} drafted players)")

    # mine the enlarged feature set (frozen 5 + situation), same FDR + stability guards as Phase 6
    sc = bias_scorecard(panel, features=PHASE16_FEATURES, n_boot=5000)
    print("\n" + sc.render())

    # structural gates — the pipeline is sound; we never force a signal to appear.
    assert len(sc.table) == len(PHASE16_FEATURES), "scorecard must judge every trait"
    tbl = sc.table.set_index("term")
    for f in SITUATION_FEATURES:
        assert f in tbl.index, f"{f} not judged by the scorecard"
        assert tbl.loc[f, "n_seasons"] >= 5, f"{f} not identifiable across the DEV window"
        assert tbl.loc[f, "stability"] == tbl.loc[f, "stability"], f"{f} stability is NaN"

    # the honest per-feature verdict (survive-or-drop), in the reframe's terms
    print("\n  Situation-change verdicts:")
    for f in SITUATION_FEATURES:
        r = tbl.loc[f]
        reading = ("UNDER-drafted → cheap to prefer" if r["coef"] > 0
                   else "OVER-drafted → costly to chase") if r["significant"] else \
            "no stable ADP bias (honestly ruled out)"
        print(f"    {f:16s} coef {r['coef']:+6.1f} VOR/SD  "
              f"CI[{r['ci_lo']:+6.1f},{r['ci_hi']:+6.1f}]  p_fdr={r['p_fdr']:.3f}  "
              f"stability {r['stability']:.0%}  → {reading}")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "seasons": sorted(int(s) for s in panel["season"].unique()),
        "n_players": int(len(panel)),
        "features": list(PHASE16_FEATURES),
        "situation_features": list(SITUATION_FEATURES),
        "rates": {f: float(panel[f].mean()) for f in SITUATION_FEATURES},
        "scorecard": sc.table.to_dict(orient="records"),
    }, indent=2, default=float))
    print(f"\n  wrote {OUT.relative_to(OUT.parents[1])}")
    print("\nPhase 16.1 (situation-change ADP-alpha) — all checks PASS.")
    con.close()


if __name__ == "__main__":
    main()
