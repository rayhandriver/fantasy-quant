"""Phase 16.7 — build and characterise the draft-slot **drift** panel.

    uv run python steps/phase16_7_drift_panel.py

The availability twin of the 16.1 value panel. 16.1 asked "does a changed situation make a player
out-earn his ADP?" (answer: an honest null). This asks "does it make him get **drafted earlier**?"
— the signal that fixes the sniped-target UX failure. This step only *builds and describes* the
target; 16.8 is where it survives or is dropped.

``drift > 0`` = drafted EARLIER than the consensus board, in **rounds** (see the module docstring
for the sign flip vs BUILD_PLAN and the rounds normalization). ``drift_centered`` removes each
room's own level offset and is the headline target.

Reports the corpus honestly — this is a **thin** panel and the report says so rather than burying
it: the crawled Sleeper corpus is 117 human complete drafts, but only those inside the preseason
window, snake, in a redraft scoring format, in a season with an FFC board survive.
"""

from __future__ import annotations

import json
from pathlib import Path

from fantasy_quant.adp import drift_panel as dp
from fantasy_quant.config import LOCKBOX_SEASONS
from fantasy_quant.data import db

OUT = Path(__file__).resolve().parents[1] / "analysis" / "phase16_7_drift_panel.json"

MIN_DRAFTS_FOR_PLAYER_VIEW = 4   # below this a player-season mean is not worth reading


def main() -> None:
    con = db.connect(read_only=True)

    drafts = dp.eligible_drafts(con)
    panel = dp.build_drift_panel(con)
    dp.assert_drift_panel_pit(panel, drafts)
    s = dp.summarize(panel)

    print("=== corpus funnel ===")
    total = con.execute("SELECT COUNT(*) FROM sleeper_drafts WHERE is_human "
                        "AND status = 'complete'").fetchone()[0]
    print(f"  human complete drafts in the corpus : {total}")
    print(f"  ... snake + redraft scoring + preseason window : {len(drafts)}")
    print(f"  ... with a consensus board for that season     : {s['n_drafts']}")
    by_src = panel.groupby("board_source")["draft_id"].nunique().to_dict()
    print(f"  ... by board source                            : {by_src}")
    lost = sorted(set(drafts["season"]) - set(panel["season"]))
    if lost:
        print(f"  seasons dropped for want of a board            : {lost}")

    print("\n=== panel ===")
    for k, v in s.items():
        print(f"  {k:22s} {v:,.3f}" if isinstance(v, float) else f"  {k:22s} {v:,}")
    print(f"  drift_centered sd      {panel['drift_centered'].std(ddof=0):.3f}")

    print("\n  per season:")
    by = panel.groupby("season").agg(drafts=("draft_id", "nunique"), picks=("drift", "size"),
                                     sd=("drift_centered", "std"))
    print(by.to_string())

    # ---- face validity: the tails should be recognisable, not noise ----------------------------
    agg = dp.aggregate_player_season(panel)
    solid = agg[agg["n_drafts"] >= MIN_DRAFTS_FOR_PLAYER_VIEW].copy()
    ranked = solid.sort_values("mean_drift_centered", ascending=False)
    cols = ["season", "name", "pos", "n_drafts", "mean_drift_centered", "sd_drift"]
    print(f"\n=== biggest REACHES (≥{MIN_DRAFTS_FOR_PLAYER_VIEW} drafts) ===")
    print(ranked.head(10)[cols].to_string(index=False))
    print("\n=== biggest FALLERS ===")
    print(ranked.tail(10)[cols].to_string(index=False))

    pos_bias = panel.groupby("pos")["drift_centered"].mean().sort_values()
    print("\n=== mean centered drift by position (rounds; −ve = slides) ===")
    print(pos_bias.to_string())

    # ---- structural gates ----------------------------------------------------------------------
    assert s["n_rows"] > 0, "empty drift panel"
    assert s["n_seasons"] >= 5, "too few seasons to walk forward"
    assert abs(float(panel["drift_centered"].mean())) < 1e-9, "centering is not mean-zero"
    assert panel["drift"].std(ddof=0) > 0, "degenerate target"
    # the lockbox seasons are *expected* here — drift is an availability signal, outside the frozen
    # value stack (user decision 2026-07-25). Assert only that we know which rows they are.
    n_lock = int(panel["season"].isin(LOCKBOX_SEASONS).sum())
    print(f"\n  lockbox-season rows (availability track — outside the frozen "
          f"value stack): {n_lock}")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "funnel": {"human_complete": int(total), "eligible": int(len(drafts)),
                   "with_board": int(s["n_drafts"]), "seasons_without_board": lost,
                   "by_board_source": {k: int(v) for k, v in by_src.items()}},
        "summary": s,
        "drift_centered_sd": float(panel["drift_centered"].std(ddof=0)),
        "drift_centered_sd_by_source": {
            str(k): float(v) for k, v in
            panel.groupby("board_source")["drift_centered"].std(ddof=0).items()},
        "per_season": by.reset_index().to_dict(orient="records"),
        "pos_bias": pos_bias.to_dict(),
        "lockbox_rows": n_lock,
        "top_reaches": ranked.head(15)[cols].to_dict(orient="records"),
        "top_fallers": ranked.tail(15)[cols].to_dict(orient="records"),
        "n_player_seasons": int(len(agg)),
        "n_player_seasons_solid": int(len(solid)),
    }, indent=2, default=float))
    print(f"\n  wrote {OUT.relative_to(OUT.parents[1])}")
    print("\nPhase 16.7 (drift panel) — all checks PASS.")
    con.close()


if __name__ == "__main__":
    main()
