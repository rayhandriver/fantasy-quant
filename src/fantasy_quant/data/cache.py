"""Shared raw-pull caching.

Pull a source once to parquet under ``data/raw/<source>/`` and reuse it on subsequent runs so
we never re-hit the network mid-dev. ``refresh=True`` forces a re-pull. Used by every data
source (nflverse uses its own local copy; 0.3+ share this).
"""

from __future__ import annotations

import datetime as dt
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


def archive_text(dir_path: Path, stem: str, text: str, ext: str = "html") -> Path | None:
    """Archive a scrape's **raw payload** (HTML/JSON) date-stamped under ``dir_path`` (T7).

    The parsed parquet is what we ingest; this keeps the raw response next to it so a *broken*
    scrape (site markup change, truncated shell) can be diffed against the last-good shape. One
    file per day (``<stem>_<YYYY-MM-DD>.<ext>``, overwritten within a day) bounds growth while
    preserving history. Best-effort: never let an archiving failure break a pull — returns ``None``.
    """
    if not text:
        return None
    try:
        dir_path = Path(dir_path)
        dir_path.mkdir(parents=True, exist_ok=True)
        path = dir_path / f"{stem}_{dt.date.today().isoformat()}.{ext}"
        path.write_text(text, encoding="utf-8")
        return path
    except OSError as e:  # a full disk / permissions issue must not sink the ingest
        log.warning("could not archive raw payload %s: %s", stem, e)
        return None
