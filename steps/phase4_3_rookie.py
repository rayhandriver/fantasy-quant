"""Phase 4.3 — the rookie value model, run + verify.

    uv run python steps/phase4_3_rookie.py

Done when (reframed BUILD_PLAN 4.3): rookies get a real projection from draft capital + landing spot
(not a punt to ADP), the model is PIT/walk-forward (fit only on strictly-prior seasons), its
predictions rank-correlate with realized rookie points OOS, and it plugs into the 4.2 value board so
the historical proxy board stops being blind to rookies.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fantasy_quant.config import DEV_SEASONS
from fantasy_quant.data import db
from fantasy_quant.projections.rookie import rookie_frame, rookie_projection
from fantasy_quant.valuation.value_board import value_board


def spearman(a, b) -> float:
    return float(pd.Series(np.asarray(a)).corr(pd.Series(np.asarray(b)), method="spearman"))


def main() -> None:
    con = db.connect(read_only=True)

    # -- walk-forward OOS: predict each DEV season's rookies from strictly-prior seasons -----------
    rows = []
    for s in [yr for yr in DEV_SEASONS if yr >= 2018]:  # need a few prior seasons to train
        pred = rookie_projection(con, s)
        real = rookie_frame(con, s, with_target=True)[["player_key", "points"]]
        m = pred.merge(real, on="player_key", how="inner")
        m["season"] = s
        rows.append(m)
    allm = pd.concat(rows, ignore_index=True)
    rho = spearman(allm["proj_points"], allm["points"])
    # naive baseline (predict every rookie the pooled mean) -> Spearman 0; we beat it.
    mae = float(np.abs(allm["proj_points"] - allm["points"]).mean())
    print(f"=== rookie model, walk-forward on {allm['season'].nunique()} DEV seasons "
          f"({len(allm)} rookies) ===")
    print(f"  Spearman(predicted, realized rookie points) = {rho:+.2f}   MAE {mae:.1f} pts")
    assert rho > 0.25, f"rookie predictions should rank-correlate with realized (got {rho:+.2f})"

    # -- the dominant signal is draft capital: earlier pick -> more realized points (pooled) -------
    pool = pd.concat([rookie_frame(con, s, with_target=True)
                      for s in DEV_SEASONS if s >= 2015], ignore_index=True)
    dc = spearman(pool["draft_ovr"], pool["points"])
    print(f"  (sanity) corr(draft_ovr, realized rookie points), {len(pool)} pooled rookies "
          f"= {dc:+.2f} (negative = earlier picks score more)")
    assert dc < -0.3, "draft capital should predict rookie points (earlier = more)"

    # -- top projected rookies for a season, with names --------------------------------------------
    s = 2021
    pred = rookie_projection(con, s).sort_values("proj_points", ascending=False).head(10)
    names = con.execute(
        "SELECT gsis_id, MAX(player_display_name) nm FROM weekly GROUP BY gsis_id").df()
    pred = pred.merge(names, left_on="player_key", right_on="gsis_id", how="left")
    print(f"\n  top-10 projected {s} rookies (fit on {[y for y in DEV_SEASONS if y < s]}):")
    print(pred[["nm", "pos", "proj_points"]].round(1).to_string(index=False))

    # -- integration: the value board now fills rookies the proxy misses ---------------------------
    base = value_board(con, s)
    withr = value_board(con, s, rookie_fn=rookie_projection)
    n_rookies = int((withr["source"] == "rookie").sum())
    print(f"\n  [PASS] value board {s}: proxy alone {len(base)} players -> +{n_rookies} rookies "
          f"filled by the model ({len(withr)} total).")
    assert n_rookies > 10, "rookie model should add a meaningful class to the proxy board"

    print("\nPhase 4.3 (rookie model) — all checks PASS.")
    con.close()


if __name__ == "__main__":
    main()
