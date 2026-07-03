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


def ensure_dirs() -> None:
    """Create the data directory tree if missing (idempotent)."""
    for d in (DATA_DIR, RAW_DIR, INTERIM_DIR, PROCESSED_DIR):
        d.mkdir(parents=True, exist_ok=True)
