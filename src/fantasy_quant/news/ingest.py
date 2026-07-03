"""Phase 0.6 — News / injury / depth-chart raw ingest (timestamped; no NLP yet).

Three tables, each timestamped so a given day is reconstructable later:
  - ``injuries``     — official reports (Out/Questionable/Doubtful) via nflverse
    ``import_injuries``; native ``gsis_id`` + **``date_modified``** (the PIT stamp). Historical.
  - ``depth_charts`` — weekly depth (``depth_team`` rank) via ``import_depth_charts``; native
    ``gsis_id``, grain = (season, week). Historical.
  - ``news_raw``     — beat-writer / headline RSS (ESPN/CBS/Yahoo), **forward-capture** only
    (news can't be backfilled); appended + de-duped by guid, stamped ``captured_at``.

Inactives (the 90-min pre-kickoff list) has no clean free historical importer — derivable later
from snaps==0 or forward-captured; deferred (noted in PLAN.md).
"""

from __future__ import annotations

import logging

import httpx
import pandas as pd
from bs4 import BeautifulSoup

from fantasy_quant.config import RAW_DIR
from fantasy_quant.data import cache, db

log = logging.getLogger(__name__)

DEFAULT_YEARS: list[int] = list(range(2014, 2026))
NEWS_RAW = RAW_DIR / "news"
RSS_FEEDS = {
    "espn": "https://www.espn.com/espn/rss/nfl/news",
    "cbs": "https://www.cbssports.com/rss/headlines/nfl/",
    "yahoo": "https://sports.yahoo.com/nfl/rss/",
}
HEADERS = {"User-Agent": "Mozilla/5.0 (fantasy-quant research; contact rayhan.driver@gmail.com)"}


# --------------------------------------------------------------------------------------------
# injuries + depth charts (free, historical)
# --------------------------------------------------------------------------------------------
def _pull_by_year(import_name: str, years) -> pd.DataFrame:
    import nfl_data_py as nfl

    fn = getattr(nfl, import_name)
    frames = []
    for y in years:
        try:
            frames.append(fn([y]))
        except Exception as e:  # noqa: BLE001
            log.warning("skip %s %d: %s", import_name, y, e)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def ingest_injuries(con, years=DEFAULT_YEARS, refresh: bool = False) -> int:
    df = cache.load_or_pull(
        NEWS_RAW / "injuries.parquet",
        lambda: _pull_by_year("import_injuries", years),
        refresh=refresh,
    )
    if "date_modified" in df.columns:
        df["date_modified"] = pd.to_datetime(df["date_modified"], errors="coerce")
    return db.write_df(con, "injuries", df)


def ingest_depth_charts(con, years=DEFAULT_YEARS, refresh: bool = False) -> int:
    df = cache.load_or_pull(
        NEWS_RAW / "depth_charts.parquet",
        lambda: _pull_by_year("import_depth_charts", years),
        refresh=refresh,
    )
    return db.write_df(con, "depth_charts", df)


# --------------------------------------------------------------------------------------------
# news RSS (forward-capture pipe)
# --------------------------------------------------------------------------------------------
def _rss_get(item, name: str):
    el = item.find(name) or item.find(name.lower())
    return el.get_text(strip=True) if el else None


def parse_rss(xml_text: str, source: str) -> pd.DataFrame:
    """Parse an RSS feed's ``<item>``s into title/link/summary/published rows (pure)."""
    soup = BeautifulSoup(xml_text, "xml")
    rows = []
    for it in soup.find_all("item"):
        link = _rss_get(it, "link")
        rows.append({
            "source": source,
            "guid": _rss_get(it, "guid") or link,
            "link": link,
            "title": _rss_get(it, "title"),
            "summary": _rss_get(it, "description"),
            "published_raw": _rss_get(it, "pubDate"),
        })
    return pd.DataFrame(rows)


def ingest_news_text(con, feeds=None, refresh: bool = False) -> int:
    """Fetch the RSS feeds, parse, and **append + de-dupe** into ``news_raw`` (accumulates over
    time; earliest ``captured_at`` per guid wins). ``refresh`` is unused here (always fetches)."""
    feeds = feeds or RSS_FEEDS
    captured_at = db.utc_now()
    frames = []
    for source, url in feeds.items():
        try:
            r = httpx.get(url, headers=HEADERS, timeout=20, follow_redirects=True)
            r.raise_for_status()
            frames.append(parse_rss(r.text, source))
        except Exception as e:  # noqa: BLE001
            log.warning("skip feed %s: %s", source, e)
    new = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if new.empty:
        log.warning("no RSS items fetched; news_raw unchanged")
        return db.row_count(con, "news_raw") if db.table_exists(con, "news_raw") else 0
    new["published"] = pd.to_datetime(new["published_raw"], errors="coerce", utc=True,
                                       format="mixed")
    new["captured_at"] = captured_at

    if db.table_exists(con, "news_raw"):
        existing = con.execute("SELECT * FROM news_raw").df()
        combined = pd.concat([existing, new], ignore_index=True)
    else:
        combined = new
    combined = combined.drop_duplicates(subset="guid", keep="first")
    return db.write_df(con, "news_raw", combined)


# --------------------------------------------------------------------------------------------
# PIT accessor (done-criterion demo)
# --------------------------------------------------------------------------------------------
def injuries_asof(con, as_of, season: int | None = None) -> pd.DataFrame:
    """Injury reports filed **on or before** ``as_of`` (PIT). Asserts none is future-dated."""
    as_of_ts = pd.to_datetime(as_of, utc=True)
    q = "SELECT * FROM injuries WHERE date_modified <= ?"
    params: list = [as_of_ts]
    if season is not None:
        q += " AND season = ?"
        params.append(season)
    df = con.execute(q, params).df()
    if not df.empty:
        latest = pd.to_datetime(df["date_modified"], utc=True).max()
        assert latest <= as_of_ts, "PIT violation: injuries_asof returned a future report"
    return df
