"""T13 done-bar — the Phase-5 cloud is reproducible **across processes**.

    uv run python steps/t13_reproducibility.py
    uv run python steps/t13_reproducibility.py --season 2026 --runs 3

Done when: two fresh interpreters, same ``(season, ruleset, seed)``, produce a **bit-identical**
per-player ``q10``/``q90``. That has to be checked out-of-process by construction — the defect was
invisible inside one interpreter, which is why it survived from Session F.6 to now — so this step
shells out to itself and compares digests.

★ **The register's stated cause was wrong, and the wrong cause was the plausible one.** T13 named
the Iman–Conover permutation in the Phase-8 coupling as the prime suspect: the fingerprint was
"marginals invariant, per-player assignment moves", which is exactly what a reshuffle looks like.
It is not a reshuffle. Ruled out by measurement, in this order:

  row order          identical across processes (same 673 keys, same sequence) — nothing is shuffled
  ``PYTHONHASHSEED`` pinned: no effect — no set/dict ordering leaks into a number
  BLAS threads       pinned to 1: no effect — the fits are not the source of the noise
  **DuckDB threads** pinned to 1: ``quantile_projection`` and ``availability_projection`` become
                     **bit-identical**, and with them the entire cloud

The cause is float aggregation *inside the database*: a parallel ``SUM``/``AVG`` adds its partitions
in whatever order the threads finish and floating-point addition is not associative, so the training
frames differ in their last bits from run to run. Those last bits move the fitted quantile and
hazard coefficients, and the sampler turns a 1e-8 coefficient difference into a *visible* per-player
draw difference. **A reproducibility bug does not have to live in the random number generator** —
and "the marginals are stable but the assignment moves" is equally the fingerprint of an input that
wobbles below the noise floor of every aggregate you were watching.

The fix is :func:`~fantasy_quant.data.db.deterministic_reads`, wrapping the assembler's reads.
Measured cost: **none** (10.2 s → 9.1 s on the 2025/2026 clouds — these queries are small enough
that thread coordination costs more than it buys).

★ **This does not change the model.** The pin selects one of the runs the old code was already
alternating between (the dress rehearsal's 75.5 ↔ 76.5 % coverage was the same result twice, as
T13 always said); it re-specifies nothing. What it buys is that a published per-player number, or a
mock board rebuilt from a seed, is the same number tomorrow.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

DB = Path("data/fantasy_quant.duckdb")
OUT = Path("analysis/t13_reproducibility.json")


def _digest(season: int, seed: int) -> dict:
    """One run's fingerprint — computed in a *fresh* interpreter by ``--child``."""
    import duckdb

    from fantasy_quant.projections import distribution

    con = duckdb.connect(str(DB), read_only=True)
    summ, samples, _ = distribution.cached_distribution(con, season, None, seed=seed)
    keys = summ["player_key"].astype(str).tolist()
    con.close()
    return {
        "n": int(len(summ)),
        "keys": hashlib.md5("|".join(keys).encode()).hexdigest(),
        "q10": hashlib.md5(summ["q10"].to_numpy(float).tobytes()).hexdigest(),
        "q90": hashlib.md5(summ["q90"].to_numpy(float).tobytes()).hexdigest(),
        "samples": hashlib.md5(samples[:, :16].copy(order="C").tobytes()).hexdigest(),
        # sums are reported as well as hashed: a hash says "different", a sum says "how much"
        "q10_sum": float(np.sum(summ["q10"].to_numpy(float))),
        "mean_sum": float(np.sum(summ["mean"].to_numpy(float))),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=2025)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--runs", type=int, default=2, help="fresh interpreters to compare")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args()

    if a.child:                                     # one fresh process: print and exit
        print(json.dumps(_digest(a.season, a.seed)))
        return

    runs = []
    for i in range(a.runs):
        proc = subprocess.run(
            [sys.executable, __file__, "--child", "--season", str(a.season),
             "--seed", str(a.seed)],
            capture_output=True, text=True, check=True)
        runs.append(json.loads(proc.stdout.strip().splitlines()[-1]))
        print(f"  run {i + 1}/{a.runs}: q10={runs[-1]['q10'][:12]}  "
              f"q90={runs[-1]['q90'][:12]}  n={runs[-1]['n']}")

    first = runs[0]
    agree = {k: all(r[k] == first[k] for r in runs) for k in ("n", "keys", "q10", "q90", "samples")}
    spread = {k: (max(r[k] for r in runs) - min(r[k] for r in runs))
              for k in ("q10_sum", "mean_sum")}
    ok = all(agree.values())

    print(f"\nT13 — {a.runs} fresh processes, season {a.season}, seed {a.seed}")
    for k, v in agree.items():
        print(f"  {k:<9} {'IDENTICAL' if v else 'DIFFERS'}")
    for k, v in spread.items():
        print(f"  {k:<9} spread {v:.6g}")
    print(f"\n  {'PASS' if ok else 'FAIL'} — the cloud is "
          f"{'reproducible' if ok else 'NOT reproducible'} across processes")

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(
        {"season": a.season, "seed": a.seed, "runs": runs, "agree": agree, "spread": spread,
         "pass": ok}, indent=1))
    print(f"  -> {a.out}")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
