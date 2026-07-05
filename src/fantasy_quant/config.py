"""Central configuration & path resolution for fantasy_quant.

Loads ``.env`` once (via python-dotenv) and exposes the canonical data paths and league
settings so every module agrees on where the DuckDB store and data dirs live. Relative env
paths are resolved against the **repo root**, not the current working directory, so scripts
behave the same regardless of where they're launched from.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# src/fantasy_quant/config.py -> repo root is two parents up from the package directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolve(env_key: str, default: Path) -> Path:
    raw = os.getenv(env_key)
    if not raw:
        return default
    p = Path(raw).expanduser()
    return p if p.is_absolute() else (PROJECT_ROOT / p)


DATA_DIR = _resolve("DATA_DIR", PROJECT_ROOT / "data")
DUCKDB_PATH = _resolve("DUCKDB_PATH", DATA_DIR / "fantasy_quant.duckdb")
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"

# League format the backtest scores against (stated baseline: 10-team full-PPR, 1-QB).
LEAGUE_TEAMS = int(os.getenv("LEAGUE_TEAMS", "10"))
LEAGUE_SCORING = os.getenv("LEAGUE_SCORING", "ppr")
LEAGUE_QB = int(os.getenv("LEAGUE_QB", "1"))

# --- Lockbox discipline (reframe 2026-07-04; CLAUDE.md §4) -----------------------------------
# Seasons with realized weekly fantasy points in the store (2025 backfilled 2026-07-05 via the new
# nflverse `stats_player` release — step 0.9). Usable for feature/projection/CALIBRATION work.
STATS_SEASONS: tuple[int, ...] = tuple(range(2014, 2026))  # 2014..2025

# The DRAFT-BACKTEST universe: seasons with BOTH a preseason ADP board AND realized weekly points.
# 2025 is excluded here — it has weekly stats now, but there's no 2025 ADP board (FFC empty; source
# via Sleeper later). Add 2025 once an ADP board lands. (see findings.md 2026-07-04/07-05).
FANTASY_SEASONS: tuple[int, ...] = tuple(range(2014, 2025))  # 2014..2024 (11 seasons)

# The LOCKBOX: frozen, never touched during development / feature+model selection. Evaluate the
# final chosen stack here exactly once. DEV_SEASONS is everything else (all development happens
# here). Enforce by defaulting walk-forward/selection to DEV_SEASONS; only the final eval reads
# LOCKBOX_SEASONS. (reframe caution #1: PIT-clean != out-of-sample-clean.)
LOCKBOX_SEASONS: tuple[int, ...] = (2023, 2024)
DEV_SEASONS: tuple[int, ...] = tuple(s for s in FANTASY_SEASONS if s not in LOCKBOX_SEASONS)

# 2025 has realized outcomes but no ADP board -> a projection/calibration HOLDOUT (the reframe's
# core bar is calibration, which needs no draft board). Upgrades to a full backtest season when a
# 2025 ADP board is sourced. Keep it out of DEV_SEASONS and the lockbox.
CALIBRATION_SEASONS: tuple[int, ...] = (2025,)


def ensure_dirs() -> None:
    """Create the data directory tree if missing (idempotent)."""
    for d in (DATA_DIR, RAW_DIR, INTERIM_DIR, PROCESSED_DIR):
        d.mkdir(parents=True, exist_ok=True)
