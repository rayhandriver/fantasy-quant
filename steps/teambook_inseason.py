"""Team book step 2 done-bar — the live-season path, checked three ways.

    uv run python steps/teambook_inseason.py            # → analysis/teambook_inseason.json

1. **Code parity (must be exact).** The in-season path, run on the project store's own 2025 tables,
   reproduces the store path's books with participation switched off — every metric, player row,
   weekly row, trait and record. This is what proves the in-memory store is the same shape.
2. **Vintage (reported, bounded).** The same season built from *today's* nflverse releases. The two
   differ, and the difference is upstream: since the store's 2026-06-30 pull nflverse re-ran its EPA
   model (tens of thousands of plays) and reclassified a few dozen play types. The bar is that no
   rate moves by more than ``VINTAGE_TOL`` — a restatement, not a different number.
3. **The live season itself.** 32 sane books, ``through_week`` from the schedule, the participation
   family marked unavailable with its reason, and whether nflverse has published it yet.
"""

from __future__ import annotations

import json
import time

import numpy as np

from fantasy_quant.config import PROJECT_ROOT
from fantasy_quant.data import db
from fantasy_quant.teambook import build as B
from fantasy_quant.teambook import inseason as I
from fantasy_quant.teambook import metrics as M
from fantasy_quant.teambook import schema as S

PARITY_SEASON = 2025
LIVE_SEASON = 2026
VINTAGE_TOL = 0.01      # rates; per-game counts are bounded separately
VINTAGE_COUNT_TOL = 0.2


def max_metric_diff(a: dict, b: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    for team, book in a["books"].items():
        other = b["books"][team]["metrics"]
        for key, cell in book["metrics"].items():
            d = abs(cell["v"] - other[key]["v"]) if key in other else np.inf
            out[key] = max(out.get(key, 0.0), float(d))
    return out


def main() -> None:
    con = db.connect(read_only=True)
    report: dict = {"step": "teambook 2 — the in-season path"}

    ref = B.build_season_books(con, PARITY_SEASON, participation=False, construction=None,
                               meta={})
    own = I.build_live_season(PARITY_SEASON,
                              con=I.frames_store(I.store_frames(con, PARITY_SEASON)))
    diffs = max_metric_diff(ref, own)
    sections_equal = all(ref["books"][t][sec] == own["books"][t][sec]
                         for t in ref["books"]
                         for sec in ("players", "weekly", "meta", "traits", "coaching"))
    report["code_parity"] = {"season": PARITY_SEASON, "metrics": len(diffs),
                             "max_abs_diff": max(diffs.values()),
                             "sections_equal": sections_equal,
                             "PASS": max(diffs.values()) == 0.0 and sections_equal}

    t0 = time.time()
    rel = I.build_live_season(PARITY_SEASON, refresh=False)
    vint = max_metric_diff(ref, rel)
    counts = {k for k in vint if M.BY_KEY[k].fmt in ("num1", "num2", "signed1")}
    worst_rate = max(v for k, v in vint.items() if k not in counts)
    worst_count = max(vint[k] for k in counts)
    report["vintage"] = {
        "season": PARITY_SEASON, "seconds": round(time.time() - t0, 1),
        "worst_rate_diff": worst_rate, "worst_count_diff": worst_count,
        "by_metric": dict(sorted(vint.items(), key=lambda kv: -kv[1])),
        "PASS": worst_rate <= VINTAGE_TOL and worst_count <= VINTAGE_COUNT_TOL,
        "note": "store pulled 2026-06-30; nflverse has since re-run EPA and reclassified "
                "play types, so the difference is upstream, not code",
    }

    t0 = time.time()
    live = I.build_live_season(LIVE_SEASON)
    S.assert_season_sane(live["books"])
    any_book = next(iter(live["books"].values()))
    report["live"] = {
        "season": LIVE_SEASON, "seconds": round(time.time() - t0, 1),
        "teams": len(live["books"]), "through_week": any_book["status"]["through_week"],
        "complete": any_book["status"]["complete"],
        "metrics_per_book": int(np.median([len(b["metrics"]) for b in live["books"].values()])),
        "unavailable": sorted(any_book["status"]["unavailable"]),
        "participation_published": I.participation_published(LIVE_SEASON),
        "PASS": len(live["books"]) == 32 and M.PARTICIPATION in any_book["status"]["unavailable"],
    }
    report["all_pass"] = all(report[k]["PASS"] for k in ("code_parity", "vintage", "live"))

    out = PROJECT_ROOT / "analysis" / "teambook_inseason.json"
    out.write_text(json.dumps(report, indent=2, default=float))
    print(json.dumps({k: v for k, v in report.items() if k != "vintage"}, indent=2,
                     default=float))
    print("vintage:", {k: report["vintage"][k] for k in
                       ("worst_rate_diff", "worst_count_diff", "PASS")})
    print("wrote", out)


if __name__ == "__main__":
    main()
