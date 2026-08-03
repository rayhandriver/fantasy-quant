"""Phase 0.12.1 — a **direct reader for the nflverse-data release assets**.

★ Why this module exists, stated plainly, because it is the finding of Session DATA-1:

    ``nfl_data_py`` is a *wrapper* over the GitHub release assets of `nflverse/nflverse-data`,
    and this repo has been reading the wrapper's surface as if it were the data's surface.
    Anything the wrapper does not expose has been invisible to us — **not unavailable,
    invisible.**

The repo had already been bitten by this once and wrote it off as a one-off (Phase 0.9: *"nflverse
restructured stats releases post-2024; the frozen ``nfl_data_py`` hits the dead old path"*). It was
the general case. The proof is ``pbp_participation``: ten seasons at play grain, carrying
``defenders_in_box``, ``offense_personnel``/``defense_personnel``, ``defense_man_zone_type``,
``route``, ``was_pressure`` and the gsis ids of all 22 men on every play — with **no wrapper
function**, and therefore absent from a store that had ingested sixteen tables.

This module sits **beside** ``data/sources/nflverse.py``, it does not replace it: that module is
the provenance of sixteen tables and migrating them is not a goal of this session. What this buys
is that every future nflverse release is reachable the day it ships, without waiting on a wrapper.

Layout of a release: one *tag* per dataset (``pbp_participation``, ``schedules``, ``ftn_charting``,
…), each holding assets in four serializations (``.parquet``/``.csv``/``.qs``/``.rds``) and, for
per-season datasets, one set per season. We always take **parquet** — it carries dtypes, so a
season boundary cannot silently retype a column the way a CSV round-trip can.

⚠ **Two rate limits, and only one of them is the download.** The GitHub *API* (asset listings) is
60 requests/hour unauthenticated; the *asset downloads* are plain CDN fetches and are not limited.
So the release index is cached to disk with a TTL and the payloads are cached forever. Anything
that calls :func:`list_releases` in a loop will exhaust the API budget and see empty listings, so
it is cached at the one place that fetches it.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import logging
import re
from pathlib import Path

import pandas as pd
import requests

from fantasy_quant.config import RAW_DIR
from fantasy_quant.data import cache

log = logging.getLogger(__name__)

REPO = "nflverse/nflverse-data"
API_RELEASES = f"https://api.github.com/repos/{REPO}/releases?per_page=100"
ASSET_URL = "https://github.com/" + REPO + "/releases/download/{tag}/{asset}"

RELEASE_RAW = RAW_DIR / "nflverse" / "releases"
INDEX_JSON = RELEASE_RAW / "_release_index.json"
INDEX_TTL_HOURS = 24
TIMEOUT = 120

# ★ Upstream hard floors — measured 2026-08-02 against the release API, and **permanent facts about
# the world, not gaps we can close**. They live here (not only in prose) so 0.12.8 can assert them:
# a request below a floor must *raise, naming the floor*, rather than return an empty frame that
# reads downstream as "this player had no routes". A prose warning is not a guard.
#
# ⚠ The DEV arithmetic is the point. ``DEV_SEASONS`` is 2014-2022, so FTN's 2022 floor contributes
# exactly **one** development season — any bar built on FTN is a bar built on n=1, which this repo
# has already learned twice (T24, T40) not to trust. FTN therefore ships ``backtestable: False``.
SEASON_FLOORS: dict[str, int] = {
    "pbp_participation": 2016,
    "nextgen_stats": 2016,
    "pfr_advstats": 2018,
    "ftn_charting": 2022,
    "weekly_rosters": 2002,
    "pbp": 1999,
}


# --------------------------------------------------------------------------------------------
# the release index
# --------------------------------------------------------------------------------------------
def list_releases(refresh: bool = False) -> dict[str, list[str]]:
    """``{tag: [asset names]}`` for every release, from a TTL'd on-disk cache of the GitHub API."""
    if not refresh and INDEX_JSON.exists():
        age = dt.datetime.now(dt.UTC) - dt.datetime.fromtimestamp(
            INDEX_JSON.stat().st_mtime, dt.UTC
        )
        if age < dt.timedelta(hours=INDEX_TTL_HOURS):
            return json.loads(INDEX_JSON.read_text())
    resp = requests.get(API_RELEASES, timeout=TIMEOUT)
    resp.raise_for_status()
    index = {r["tag_name"]: sorted(a["name"] for a in r["assets"]) for r in resp.json()}
    INDEX_JSON.parent.mkdir(parents=True, exist_ok=True)
    INDEX_JSON.write_text(json.dumps(index, indent=2, sort_keys=True))
    log.info("release index refreshed: %d tags", len(index))
    return index


def release_assets(tag: str, ext: str | None = "parquet", refresh: bool = False) -> list[str]:
    """Asset names under ``tag``, optionally filtered to one extension."""
    index = list_releases(refresh=refresh)
    if tag not in index:
        raise KeyError(f"no nflverse release tagged {tag!r}; have {sorted(index)[:10]}...")
    names = index[tag]
    return [n for n in names if n.endswith("." + ext)] if ext else list(names)


def available_seasons(tag: str, stem: str | None = None, refresh: bool = False) -> list[int]:
    """Seasons actually published under ``tag`` (parsed from the asset names, not assumed)."""
    out = set()
    for name in release_assets(tag, "parquet", refresh=refresh):
        if stem and not name.startswith(stem):
            continue
        m = re.search(r"(\d{4})\.parquet$", name)
        if m:
            out.add(int(m.group(1)))
    return sorted(out)


# --------------------------------------------------------------------------------------------
# reading assets
# --------------------------------------------------------------------------------------------
def _cache_path(tag: str, asset: str) -> Path:
    return RELEASE_RAW / tag / asset


def read_release(tag: str, asset: str, *, refresh: bool = False) -> pd.DataFrame:
    """Read one release asset (parquet) into a DataFrame, caching the raw bytes on first pull."""
    if not asset.endswith(".parquet"):
        asset = f"{asset}.parquet"
    path = _cache_path(tag, asset)
    if path.exists() and not refresh:
        return pd.read_parquet(path)
    url = ASSET_URL.format(tag=tag, asset=asset)
    log.info("downloading %s", url)
    resp = requests.get(url, timeout=TIMEOUT)
    if resp.status_code == 404:
        raise FileNotFoundError(f"no such release asset: {tag}/{asset} ({url})")
    resp.raise_for_status()
    df = pd.read_parquet(io.BytesIO(resp.content))
    cache.archive_bytes(path.parent, path.name, resp.content)
    return df


def read_seasons(
    tag: str,
    stem: str,
    seasons,
    *,
    refresh: bool = False,
    assert_floor: bool = True,
) -> pd.DataFrame:
    """Read ``stem_<season>.parquet`` for each season and union them **on the column superset**.

    ⚠ Schema drift across seasons is real, not hypothetical: participation's 2016-2022 files carry
    20 columns and 2023-2025 carry 26. Concatenating on the intersection would silently drop the
    six new columns for every season; concatenating on the union with explicit NULLs keeps the
    drift *visible*, which is the only version a fill-rate register can describe honestly. A
    ``season`` column is added if the asset does not carry one.
    """
    seasons = sorted(int(s) for s in seasons)
    if assert_floor:
        assert_season_floor(tag, seasons)
    frames = []
    for s in seasons:
        df = read_release(tag, f"{stem}_{s}.parquet", refresh=refresh)
        if "season" not in df.columns:
            df["season"] = s
        df["_source_season"] = s
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True, sort=False)  # pandas unions columns, NaN-filling
    log.info("%s: %d rows over %d seasons, %d cols", tag, len(out), len(frames), out.shape[1])
    return out


def assert_season_floor(tag: str, seasons) -> None:
    """Raise, **naming the floor**, if any requested season predates what the source publishes.

    B6. The failure this prevents is not a crash but a silence: asking for FTN 2019 returns an
    empty frame, which every downstream aggregate reads as "this happened zero times" rather than
    "this was never recorded". The register documents the floors; this makes them a guard.
    """
    floor = SEASON_FLOORS.get(tag)
    if floor is None:
        return
    bad = sorted(s for s in seasons if int(s) < floor)
    if bad:
        raise ValueError(
            f"{tag} does not exist before {floor} (requested {bad}). This is an upstream floor, "
            f"not a gap in our ingest — do not go looking for it."
        )
