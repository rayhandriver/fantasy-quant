"""T31 done-bar — the consensus level cap, measured against the bars pre-registered in
``PLAN.md`` §2026-07-30 (session 4) **before** the fix existed.

    uv run python steps/t31_level_cap.py \
        --before analysis/t31_hashes_before.json --after analysis/t31_hashes_after.json

B5 (historical bit-identity) is read from the two hash files produced by
``steps/t31_hash_distributions.py`` — one run in a ``git worktree`` at the pre-T31 commit, one
in the working tree. ⚠ Run the worktree copy with ``PYTHONPATH=<worktree>/src``: the project
installs **editable**, so ``uv run --project <main>`` from a worktree silently loads the *main*
tree's source and both "runs" return the same digest. That mistake was made twice and caught twice
here on 2026-07-30 (the second time a persistent ``cd`` sent the *working-tree* run into the
worktree) — a before/after harness that cannot fail is worse than none.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from fantasy_quant.data import validate
from fantasy_quant.data.db import connect
from fantasy_quant.projections import distribution

SEASON = 2026
PROXY_SEASONS = ("2022", "2023", "2024", "2025")

# ── the pre-registered bars (PLAN.md 2026-07-30 s4). Do not soften. ──────────────────────────
B1_MAX_NEG_SHARE = 0.020        # whole board, `mean > proj_points` is structurally impossible
B2_MAX_RHO = validate.VALUE_HAIRCUT_RHO_MAX      # -0.50, T27's shipped bar, unchanged
B3_MAX_RHO_FULL = 0.0           # off the drafted range: sign only, no magnitude demanded
B4_MAX_MEDIAN_SD_RATIO = 1.0    # per position, median sd / proj_points
B4_MAX_SD_RATIO = 3.0           # whole board, max sd / proj_points
B6_MAX_TOP_DRIFT = 0.005        # top-60 aggregate mean must not move 0.5 %
B6_TOP_SUM_MEAN_BEFORE = 12176.44


def _bar(name: str, ok: bool, **detail) -> dict:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}  {detail}")
    return {"bar": name, "pass": bool(ok), **detail}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", default="analysis/t31_hashes_before.json")
    ap.add_argument("--after", default="analysis/t31_hashes_after.json")
    ap.add_argument("--out", default="analysis/t31_level_cap.json")
    args = ap.parse_args()

    con = connect()
    df = validate.value_scale_frame(con, SEASON)
    stats = validate.value_scale_stats(df)
    dist = distribution.cached_distribution(con, SEASON)[0]

    sd = (dist[["player_key", "sd"]].drop_duplicates("player_key")
          .rename(columns={"sd": "sd_dist"}))
    m = df.merge(sd, on="player_key", how="left").dropna(subset=["sd_dist", "proj_points"])
    m = m[m["proj_points"] > 0]
    m["sd_ratio"] = m["sd_dist"] / m["proj_points"]

    bars = []
    print("T31 — pre-registered bars\n")

    neg = float((df["haircut"] < 0).mean())
    bars.append(_bar("B1 whole-board negative-haircut share", neg <= B1_MAX_NEG_SHARE,
                     share=round(neg, 5), n_neg=int((df["haircut"] < 0).sum()),
                     n=int(len(df)), bar=B1_MAX_NEG_SHARE))

    drafted = {p: s["rho"] for p, s in stats["drafted_range"].items()}
    ok2 = all(r is not None and r <= B2_MAX_RHO for r in drafted.values())
    bars.append(_bar("B2 drafted-range spearman(haircut, games)", ok2,
                     by_pos={p: (round(r, 4) if r is not None else None)
                             for p, r in drafted.items()}, bar=B2_MAX_RHO))

    full = {p: s["rho"] for p, s in stats["full_board"].items()}
    ok3 = all(r is not None and r <= B3_MAX_RHO_FULL for r in full.values())
    bars.append(_bar("B3 full-board spearman sign", ok3,
                     by_pos={p: (round(r, 4) if r is not None else None)
                             for p, r in full.items()}, bar=B3_MAX_RHO_FULL))

    med = m.groupby("pos")["sd_ratio"].median().to_dict()
    mx = float(m["sd_ratio"].max())
    ok4 = all(v <= B4_MAX_MEDIAN_SD_RATIO for v in med.values()) and mx <= B4_MAX_SD_RATIO
    bars.append(_bar("B4 sd / proj_points", ok4,
                     median_by_pos={k: round(float(v), 4) for k, v in med.items()},
                     max_ratio=round(mx, 4),
                     bar_median=B4_MAX_MEDIAN_SD_RATIO, bar_max=B4_MAX_SD_RATIO))

    before, after = (json.loads(Path(p).read_text()) for p in (args.before, args.after))
    same = {s: (before.get(s, {}).get("samples_md5") == after.get(s, {}).get("samples_md5")
                and before.get(s, {}).get("summary_md5") == after.get(s, {}).get("summary_md5")
                and before.get(s, {}).get("samples_md5") is not None)
            for s in PROXY_SEASONS}
    live_moved = (before.get(str(SEASON), {}).get("samples_md5")
                  != after.get(str(SEASON), {}).get("samples_md5"))
    bars.append(_bar("B5 historical bit-identity (proxy boards)", all(same.values()),
                     by_season=same, live_board_changed=bool(live_moved)))

    top = df.nlargest(distribution.LEVEL_TOP_N, "proj_points")
    ratio = float(top["mean"].sum() / top["proj_points"].sum())
    drift = abs(float(top["mean"].sum()) - B6_TOP_SUM_MEAN_BEFORE) / B6_TOP_SUM_MEAN_BEFORE
    lo, hi = distribution.LEVEL_BAND
    ok6 = (lo <= ratio <= hi) and drift < B6_MAX_TOP_DRIFT
    bars.append(_bar("B6 top-of-board untouched (T17 band + drift)", ok6,
                     level_ratio=round(ratio, 4), band=list(distribution.LEVEL_BAND),
                     top_sum_mean=round(float(top["mean"].sum()), 2),
                     drift=round(drift, 6), bar_drift=B6_MAX_TOP_DRIFT))

    n_capped = int((m["mean"] < m["proj_points"] * 0.999999).sum())
    out = {"season": SEASON, "bars": bars, "all_pass": all(b["pass"] for b in bars),
           "value_scale_stats": stats,
           "n_rows": int(len(df)), "n_below_consensus": n_capped}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2, default=float))
    print(f"\nALL PASS: {out['all_pass']}   -> {args.out}")


if __name__ == "__main__":
    main()
