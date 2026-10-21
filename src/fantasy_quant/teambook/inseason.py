"""The team book for a season **still being played**, read straight from the nflverse releases.

No project store is needed: :func:`release_store` downloads one season of ``pbp``,
``ftn_charting``, ``stats_player``, ``snap_counts`` and the schedule into an **in-memory DuckDB**
whose tables carry the store's names and columns, so :mod:`~fantasy_quant.teambook.pbp_family`
runs on it unchanged. That is what lets a scheduled CI job rebuild the live books every week.

★ **What a live season cannot have yet.** nflverse publishes ``pbp_participation`` after the season
(2025's file landed 2026-02-10), so personnel groupings, defensive fronts, coverage shells, man/zone
and pressure are absent until then. :func:`participation_published` asks the release index, and the
books say *which* family is missing and why — never a zero in its place. When the file lands, the
full build (from the project store) is the one to run; this module only knows the pbp/FTN half.

⚠ **Refresh is the default here, and it has to be.** :func:`nflverse_release.read_release` caches
an asset **forever** on first pull — correct for a closed season, wrong for one that gains a week
every Monday night. A cached 2026 ``games.parquet`` from earlier in this session reported no scores
at all.
"""

from __future__ import annotations

import logging

import duckdb
import pandas as pd

from fantasy_quant.data.sources import nflverse_release as nr
from fantasy_quant.data.sources.nflverse import _STATS_RENAME, map_snaps_gsis
from fantasy_quant.teambook import build as B

log = logging.getLogger(__name__)

#: The columns ``pbp_family`` reads from ``weekly``, in the store's (legacy) names.
WEEKLY_COLS = ("gsis_id", "player_display_name", "position", "recent_team", "season", "week",
               "season_type", "attempts", "passing_yards", "passing_tds", "interceptions",
               "carries", "rushing_yards", "rushing_tds", "targets", "receptions",
               "receiving_yards", "receiving_tds", "receiving_air_yards", "fantasy_points_ppr")


def participation_published(season: int, refresh: bool = True) -> bool:
    """Has nflverse published the participation file for ``season``?"""
    try:
        return season in nr.available_seasons("pbp_participation", refresh=refresh)
    except Exception as exc:  # noqa: BLE001 — an index outage must not read as "published"
        log.warning("could not list pbp_participation releases: %s", exc)
        return False


# --- conforming release frames to the store's shape (pure, offline-testable) -------------------
def conform_ftn(ftn: pd.DataFrame) -> pd.DataFrame:
    """FTN's release keys plays by ``nflverse_*_id``; the store renamed them on ingest."""
    return ftn.rename(columns={"nflverse_game_id": "game_id", "nflverse_play_id": "play_id"})


def conform_weekly(stats: pd.DataFrame) -> pd.DataFrame:
    """``stats_player`` → the store's legacy ``weekly`` names (Phase 0.9's rename, reused)."""
    return stats.rename(columns=_STATS_RENAME).reindex(columns=list(WEEKLY_COLS))


def conform_snaps(snaps: pd.DataFrame, players: pd.DataFrame) -> pd.DataFrame:
    """Snap counts carry PFR ids only; attach ``gsis_id`` through the nflverse players table."""
    return map_snaps_gsis(snaps, players[["pfr_id", "gsis_id"]])


def release_frames(season: int, refresh: bool = True) -> dict[str, pd.DataFrame]:
    s = int(season)
    games = nr.read_release("schedules", "games.parquet", refresh=refresh)
    return {
        "pbp": nr.read_release("pbp", f"play_by_play_{s}.parquet", refresh=refresh),
        "ftn_charting": conform_ftn(
            nr.read_release("ftn_charting", f"ftn_charting_{s}.parquet", refresh=refresh)),
        "weekly": conform_weekly(
            nr.read_release("stats_player", f"stats_player_week_{s}.parquet", refresh=refresh)),
        "snaps": conform_snaps(
            nr.read_release("snap_counts", f"snap_counts_{s}.parquet", refresh=refresh),
            nr.read_release("players", "players.parquet", refresh=refresh)),
        "schedules": games[games["season"] == s],
    }


def frames_store(frames: dict[str, pd.DataFrame]) -> duckdb.DuckDBPyConnection:
    """An in-memory DuckDB with one table per frame, named as the project store names them."""
    con = duckdb.connect()
    for name, df in frames.items():
        con.register(f"_{name}", df)
        con.execute(f"create table {name} as select * from _{name}")
        con.unregister(f"_{name}")
    return con


def release_store(season: int, refresh: bool = True) -> duckdb.DuckDBPyConnection:
    """An in-memory DuckDB holding one season straight from the releases."""
    return frames_store(release_frames(season, refresh=refresh))


def store_frames(con, season: int) -> dict[str, pd.DataFrame]:
    """The same five tables, read from the project store — the code-parity control."""
    s = int(season)
    return {
        "pbp": con.execute(f"select * from pbp where season = {s}").df(),
        "ftn_charting": con.execute(f"select * from ftn_charting where season = {s}").df(),
        "weekly": con.execute(
            f"select {', '.join(WEEKLY_COLS)} from weekly where season = {s}").df(),
        "snaps": con.execute(f"select * from snaps where season = {s}").df(),
        "schedules": con.execute(f"select * from schedules where season = {s}").df(),
    }


def build_live_season(season: int, *, con: duckdb.DuckDBPyConnection | None = None,
                      construction: pd.DataFrame | None = None,
                      meta: dict[str, dict] | None = None, refresh: bool = True) -> dict:
    """Every team's book for a live season: the pbp/FTN family, with participation marked absent.

    ``con`` overrides the release download (tests and the 2025 parity check pass a store).
    ``construction`` and ``meta`` are carried in from the last full export, since neither is in
    the releases this module reads.
    """
    con = con if con is not None else release_store(season, refresh=refresh)
    return B.build_season_books(con, season, participation=False,
                                construction=construction if construction is not None else None,
                                meta=meta or {})
