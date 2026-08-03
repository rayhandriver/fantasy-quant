"""Session DATA-1 / bar **B0** — bank (and later re-check) the store's pre-session fingerprint.

Run ``--bank`` *before* any DATA-1 ingest, ``--check`` after. B0 is the usual bar-sheet rule
inverted for an additive session: ingest cannot move a model number, so the interesting claim is
not "the gates still pass" but **"nothing that already existed moved a byte."**

    uv run python steps/phase0_12_0_baseline.py --bank
    uv run python steps/phase0_12_0_baseline.py --check

The baseline lands in ``analysis/data1_baseline.json`` and is committed — a fingerprint you can
only regenerate is not a control.
"""

from __future__ import annotations

import argparse
import json
import sys

from fantasy_quant.config import PROJECT_ROOT
from fantasy_quant.data import db
from fantasy_quant.data.validate import compare_fingerprints, fingerprint_store

BASELINE_JSON = PROJECT_ROOT / "analysis" / "data1_baseline.json"


def bank() -> dict:
    con = db.connect(read_only=True)
    fp = fingerprint_store(con)
    BASELINE_JSON.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_JSON.write_text(json.dumps(fp, indent=2, sort_keys=True))
    print(f"banked {len(fp)} tables -> {BASELINE_JSON.relative_to(PROJECT_ROOT)}")
    for t, d in sorted(fp.items()):
        print(f"  {t:32s} {d['n_rows']:>10,}  {len(d['schema']):>3} cols")
    return fp


def check() -> dict:
    if not BASELINE_JSON.exists():
        sys.exit(f"no baseline at {BASELINE_JSON} — run --bank first")
    before = json.loads(BASELINE_JSON.read_text())
    con = db.connect(read_only=True)
    gate = compare_fingerprints(before, fingerprint_store(con))
    print(json.dumps(gate, indent=2)[:4000])
    print(f"\nB0 {'PASS' if gate['passed'] else 'FAIL'} — "
          f"{gate['n_baseline']} baseline tables unchanged, "
          f"{gate['n_new']} new: {gate['new_tables']}")
    return gate


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.bank:
        bank()
    if a.check:
        g = check()
        sys.exit(0 if g["passed"] else 1)
    if not (a.bank or a.check):
        ap.error("pass --bank or --check")
