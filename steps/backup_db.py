"""T2 — back up the irreplaceable data off the WSL disk.

    uv run python steps/backup_db.py                  # snapshots + backfill + timestamped DB dump
    uv run python steps/backup_db.py --no-db          # skip the DB dump (snapshots + backfill only)
    uv run python steps/backup_db.py --dest /some/dir  # override the backup root

Two assets in this repo are **not reproducible** and live single-copy on the gitignored WSL disk
(TECH-DEBT T2): the live **2026 FFC ADP snapshot series** (Stage 0's whole point — unrecoverable
after the season) and the **2025 nflverse `stats_player` backfill** (the old frozen `nfl_data_py`
path is dead — a 404). This copies both — plus a timestamped full DuckDB dump — to the Windows
side so a WSL/ext4 loss can't wipe them.

Hang this off the weekly Stage-0 chore (CLAUDE.md §2): after each ADP snapshot pull, run this.
Idempotent — snapshots/backfill are overwritten in place (source of truth), the DB dump is
date-stamped so history accrues.

Done when: the 2026 snapshot parquets + 2025 backfill + a recent `.duckdb` exist under the backup
root, byte-for-byte identical to source.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DEST = Path("/mnt/c/Users/rayha/fantasy-quant-backup")

# (source glob-or-file, backup subdir) — the crown jewels, cheapest first.
SNAPSHOTS = REPO / "data/raw/adp/snapshots"
BACKFILL = [
    REPO / "data/raw/nflverse/weekly_statsplayer_2025.parquet",
    REPO / "data/raw/nflverse/seasonal_statsplayer_2025.parquet",
    REPO / "data/raw/nflverse/depth_charts_ts_2025.parquet",
]
DUCKDB = REPO / "data/fantasy_quant.duckdb"


def _md5(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _copy_verify(src: Path, dst: Path) -> bool:
    """Copy src→dst and confirm byte-identity via md5. Returns True on match."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    ok = _md5(src) == _md5(dst)
    flag = "✅" if ok else "❌ CHECKSUM MISMATCH"
    print(f"  {flag} {src.name} -> {dst}")
    return ok


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", type=Path, default=DEFAULT_DEST, help="backup root (Windows side)")
    ap.add_argument("--no-db", action="store_true", help="skip the ~295 MB DuckDB dump")
    args = ap.parse_args()
    dest: Path = args.dest
    stamp = dt.date.today().isoformat()
    all_ok = True

    print(f"=== backing up to {dest} ===")
    if not dest.parent.exists():
        raise SystemExit(f"backup root parent {dest.parent} not accessible — mount missing?")

    print("\n1. ADP snapshots (source of truth — self-heals the ingest):")
    snaps = sorted(SNAPSHOTS.glob("*.parquet"))
    if not snaps:
        print("  (none found — has Stage 0 run?)")
    for p in snaps:
        all_ok &= _copy_verify(p, dest / "adp-snapshots" / p.name)

    print("\n2. 2025 nflverse stats_player backfill (dead old path — unreproducible):")
    for p in BACKFILL:
        if p.exists():
            all_ok &= _copy_verify(p, dest / "nflverse-2025-backfill" / p.name)
        else:
            print(f"  ⚠ missing (skipped): {p.name}")

    if not args.no_db:
        print(f"\n3. DuckDB dump (timestamped {stamp}):")
        if DUCKDB.exists():
            all_ok &= _copy_verify(DUCKDB, dest / "duckdb" / f"fantasy_quant_{stamp}.duckdb")
        else:
            print(f"  ⚠ missing (skipped): {DUCKDB.name}")

    msg = "✅ backup complete, checksums verified" if all_ok else "❌ backup had mismatches"
    print(f"\n=== {msg} ===")
    if not all_ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
