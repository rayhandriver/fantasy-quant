"""Shared raw-pull caching.

Pull a source once to parquet under ``data/raw/<source>/`` and reuse it on subsequent runs so
we never re-hit the network mid-dev. ``refresh=True`` forces a re-pull. Used by every data
source (nflverse uses its own local copy; 0.3+ share this).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)


def load_or_pull(cache_path: Path, pull_fn: Callable[[], pd.DataFrame],
                 refresh: bool = False) -> pd.DataFrame:
    """Return the cached parquet at ``cache_path`` unless ``refresh``; otherwise call ``pull_fn``,
    cache the result, and return it."""
    cache_path = Path(cache_path)
    if cache_path.exists() and not refresh:
        log.info("cache hit: %s", cache_path.name)
        return pd.read_parquet(cache_path)
    df = pull_fn()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache_path, index=False)
    log.info("pulled + cached %s (rows=%d)", cache_path.name, len(df))
    return df
