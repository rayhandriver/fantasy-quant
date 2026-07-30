"""T31 bar **B5** — hash ``assemble_distribution`` per season, so historical bit-identity is a
measured before/after rather than a claim about the diff.

Run it in a ``git worktree`` at the pre-T31 commit and again in the working tree; the hashes for
every **proxy-sourced** season (2022/2023/2024/**2025**) must match exactly. 2025 is the calibration
holdout: hashing it verifies nothing moved **without reading its calibration**, so the holdout stays
unspent.

    uv run python steps/t31_hash_distributions.py --out analysis/t31_hashes_after.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from fantasy_quant.data.db import connect
from fantasy_quant.projections import distribution

SEASONS = (2022, 2023, 2024, 2025, 2026)


def hash_season(con, season: int) -> dict:
    """Digest of the assembled cloud. ``samples`` is hashed at full float64 precision — the point is
    to catch a last-bit change, so nothing here is rounded."""
    summary, samples, games = distribution.assemble_distribution(
        con, season, n_draws=distribution.N_DRAWS, seed=0, return_games=True)
    if len(summary) == 0:
        return {"n": 0, "samples_md5": None, "summary_md5": None}
    order = np.argsort(summary["player_key"].astype(str).to_numpy(), kind="stable")
    s = np.ascontiguousarray(np.asarray(samples, dtype=np.float64)[order])
    g = np.ascontiguousarray(np.asarray(games, dtype=np.float64)[order])
    num = summary[["mean", "sd", "q10", "q50", "q90", "games_played_mean"]].to_numpy(float)[order]
    return {
        "n": int(len(summary)),
        "samples_md5": hashlib.md5(s.tobytes()).hexdigest(),
        "games_md5": hashlib.md5(g.tobytes()).hexdigest(),
        "summary_md5": hashlib.md5(np.ascontiguousarray(num).tobytes()).hexdigest(),
        "sum_mean": float(summary["mean"].sum()),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seasons", default=",".join(str(s) for s in SEASONS))
    args = ap.parse_args()

    con = connect()
    out = {}
    for season in [int(s) for s in args.seasons.split(",")]:
        try:
            out[str(season)] = hash_season(con, season)
        except Exception as exc:                                  # noqa: BLE001 — record, never stop
            out[str(season)] = {"error": str(exc)[:300]}
        print(f"{season}: {out[str(season)]}", flush=True)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
