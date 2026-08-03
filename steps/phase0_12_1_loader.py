"""Session DATA-1 / 0.12.1 — the release-asset loader's done-bar (**B1**).

    uv run python steps/phase0_12_1_loader.py

★ **The bar is a CONTROL, not a smoke test.** "The download worked" is worth nothing: the claim
that matters is that the new path reads *the same data* the wrapper reads, so that everything
already in the store keeps its provenance while new tables arrive through the direct reader.

So B1 has two arms, and T31's method warning is why:

    **assert the control can produce a known difference before trusting it to show none.**

    * **positive** — ``combine``, already ingested through ``nfl_data_py``, is re-read through
      ``nflverse_release`` and must match the stored table **bit-identically** (values *and*
      dtypes, restricted to the ingested seasons and excluding our own ``pulled_at`` stamp).
    * **negative** — the same comparison pointed at a deliberately wrong asset must **fail**. An
      equality check that cannot report inequality is a check that passes on an empty room.

Writes ``analysis/phase0_12_1_loader.json``.
"""

from __future__ import annotations

import json

import pandas as pd

from fantasy_quant.config import PROJECT_ROOT
from fantasy_quant.data import db
from fantasy_quant.data.sources import nflverse_release as nr

OUT_JSON = PROJECT_ROOT / "analysis" / "phase0_12_1_loader.json"


def _identical(release: pd.DataFrame, stored: pd.DataFrame) -> dict:
    """Compare a release frame against a stored table, ignoring row order and our own stamp."""
    stored = stored.drop(columns=[c for c in ("pulled_at",) if c in stored.columns])
    if set(release.columns) != set(stored.columns):
        return {
            "equal": False,
            "reason": "column sets differ",
            "only_release": sorted(set(release.columns) - set(stored.columns)),
            "only_stored": sorted(set(stored.columns) - set(release.columns)),
        }
    cols = list(stored.columns)
    if len(release) != len(stored):
        return {"equal": False, "reason": "row counts differ",
                "n_release": len(release), "n_stored": len(stored)}
    a = release[cols].sort_values(cols).reset_index(drop=True)
    b = stored[cols].sort_values(cols).reset_index(drop=True)
    dtype_mismatch = sorted(c for c in cols if a[c].dtype != b[c].dtype)
    return {
        "equal": bool(a.equals(b)) and not dtype_mismatch,
        "n_rows": len(a),
        "n_cols": len(cols),
        "dtype_mismatch": dtype_mismatch,
    }


def main() -> dict:
    con = db.connect(read_only=True)
    stored = con.execute("select * from combine").df()
    seasons = sorted(int(s) for s in stored["season"].dropna().unique())

    # --- positive control: the same table, through the new path ------------------------------
    rel = nr.read_release("combine", "combine.parquet")
    # the wrapper ingested a season window out of a full-history asset; match that window
    pos = _identical(rel[rel["season"].isin(seasons)].reset_index(drop=True), stored)

    # --- negative controls: REQUIRE a mismatch, at both grains --------------------------------
    # ⚠ Two arms, because the obvious one is weaker than it looks. Pointing at the wrong *asset*
    # makes the column sets differ, so it only proves the comparison can detect a **schema**
    # difference — it would still pass if `_identical` compared nothing but headers. The arm that
    # licenses the positive claim is the second: one cell of an otherwise-identical frame moved,
    # which is the failure a silently-corrected upstream asset would actually produce.
    wrong = nr.read_release("draft_picks", "draft_picks.parquet")
    neg_schema = _identical(wrong, stored)

    perturbed = rel[rel["season"].isin(seasons)].reset_index(drop=True).copy()
    perturbed.loc[0, "forty"] = float(perturbed.loc[0, "forty"] or 0) + 0.01
    neg_value = _identical(perturbed, stored)

    # --- the index and the floors are live, not remembered ------------------------------------
    index = nr.list_releases()
    floors = {
        tag: {"declared": floor, "published": nr.available_seasons(tag)[:1]}
        for tag, floor in nr.SEASON_FLOORS.items()
        if tag in index and nr.available_seasons(tag)
    }
    floors_agree = all(v["published"] and v["published"][0] == v["declared"]
                       for v in floors.values())

    try:  # B6 in miniature — the floor assertion must raise, not return empty
        nr.assert_season_floor("ftn_charting", [2019])
        floor_raises = False
    except ValueError:
        floor_raises = True

    passed = (
        bool(pos["equal"])
        and not neg_schema["equal"]
        and not neg_value["equal"]
        and floors_agree
        and floor_raises
    )
    result = {
        "bar": "B1 — the loader control",
        "passed": passed,
        "positive_control_combine": pos,
        "negative_control_wrong_asset": {**neg_schema, "must_be_unequal": True},
        "negative_control_perturbed_cell": {**neg_value, "must_be_unequal": True},
        "seasons_matched": [seasons[0], seasons[-1]],
        "n_release_tags": len(index),
        "floors_declared_match_published": floors_agree,
        "floors": floors,
        "floor_assertion_raises": floor_raises,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True))
    print(json.dumps(result, indent=2, sort_keys=True))
    print(f"\nB1 {'PASS' if passed else 'FAIL'}")
    return result


if __name__ == "__main__":
    raise SystemExit(0 if main()["passed"] else 1)
