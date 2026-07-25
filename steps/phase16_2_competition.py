"""Phase 16.2 — competition-change ADP-alpha, dual-sourced.

    uv run python steps/phase16_2_competition.py

Does the crowd misprice a player whose **same-position competition changed** — a startable-caliber
teammate arrived or departed? Built **two independent ways** and mined side by side, to test whether
a roster-turnover source avoids the null the depth-chart source hit in Phase 12.3, or whether both
wash out:
  * ``competition_change_roster`` — weekly usage + ``draft_picks`` (a startable vet or a top-2-round
    rookie joined/left the position room; the player himself excluded).
  * ``competition_change_depth``  — ``depth_charts``: a genuinely new competitor cracked the season-
    opening starting depth (top-2, absent from the team's prior-year depth chart).

Same discipline as Phase 6 / 16.1: season-block-bootstrap CI + BH-FDR-adjusted p + walk-forward
sign stability; survive or honestly drop. Walled off from the frozen cost report (mines
``PHASE16_FEATURES``, never the pinned ``FEATURES``). Runs on ``DEV_SEASONS``; lockbox never read.
"""

from __future__ import annotations

import json
from pathlib import Path

from fantasy_quant.adp.panel import PHASE16_FEATURES, build_alpha_panel
from fantasy_quant.adp.scorecard import bias_scorecard
from fantasy_quant.config import DEV_SEASONS, LOCKBOX_SEASONS
from fantasy_quant.data import db

COMPETITION = ("competition_change_roster", "competition_change_depth")
OUT = Path(__file__).resolve().parents[1] / "analysis" / "phase16_2_competition.json"


def main() -> None:
    con = db.connect(read_only=True)

    panel = build_alpha_panel(con, seasons=DEV_SEASONS)
    assert not (set(panel["season"]) & set(LOCKBOX_SEASONS)), "lockbox leaked into the panel"
    for f in COMPETITION:
        print(f"panel: {f:28s} rate = {panel[f].mean():5.1%}  ({int(panel[f].sum())}/{len(panel)})")

    sc = bias_scorecard(panel, features=PHASE16_FEATURES, n_boot=5000)
    print("\n" + sc.render())

    assert len(sc.table) == len(PHASE16_FEATURES), "scorecard must judge every trait"
    tbl = sc.table.set_index("term")
    for f in COMPETITION:
        assert f in tbl.index, f"{f} not judged"
        assert tbl.loc[f, "n_seasons"] >= 5, f"{f} not identifiable across the DEV window"
        assert tbl.loc[f, "stability"] == tbl.loc[f, "stability"], f"{f} stability is NaN"

    # the deliverable: do the two sources agree, and does either survive?
    print("\n  Dual-source verdict (does roster-turnover avoid Phase 12.3's depth-chart null?):")
    for f in COMPETITION:
        r = tbl.loc[f]
        reading = ("SURVIVES" if r["significant"] else "ruled out")
        print(f"    {f:28s} coef {r['coef']:+6.1f} VOR/SD  "
              f"CI[{r['ci_lo']:+6.1f},{r['ci_hi']:+6.1f}]  p_fdr={r['p_fdr']:.3f}  "
              f"stability {r['stability']:.0%}  → {reading}")
    survived = [f for f in COMPETITION if tbl.loc[f, "significant"]]
    print(f"\n  Reading: {len(survived)} of 2 competition sources survive FDR + stability"
          f"{': ' + str(survived) if survived else ' — both wash out (echoes Phase 12.3)'}.")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "seasons": sorted(int(s) for s in panel["season"].unique()),
        "n_players": int(len(panel)),
        "competition_features": list(COMPETITION),
        "rates": {f: float(panel[f].mean()) for f in COMPETITION},
        "scorecard": sc.table.to_dict(orient="records"),
    }, indent=2, default=float))
    print(f"\n  wrote {OUT.relative_to(OUT.parents[1])}")
    print("\nPhase 16.2 (competition-change ADP-alpha) — all checks PASS.")
    con.close()


if __name__ == "__main__":
    main()
