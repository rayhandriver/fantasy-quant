"""Phase 0.2 — nflverse / nfl_data_py ingest into the DuckDB PIT store.

Lands the core NFL signal for **2014 -> latest** and normalizes player identity onto
``gsis_id`` (the join key everything downstream hangs off):

    table         source                         gsis key
    -----------   ----------------------------   --------------------------------
    player_ids    import_ids (crosswalk)         gsis_id (+ pfr_id, sleeper_id, ...)
    weekly        import_weekly_data             player_id  -> gsis_id
    seasonal      import_seasonal_data           player_id  -> gsis_id
    snaps         import_snap_counts             pfr_player_id -> gsis_id (via player_ids)
    ngs           import_ngs_data (3 stat types) player_gsis_id -> gsis_id
    draft_picks   import_draft_picks             gsis_id (native)
    combine       import_combine_data            (no gsis; pfr/cfb keys)
    pbp           import_pbp_data                play-level; *_player_id cols are gsis

Raw pulls are cached to ``data/raw/nflverse/`` (parquet) so we never re-hit the network
mid-dev; pass ``refresh=True`` to force a re-pull. Every table is stamped with ``pulled_at``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import nfl_data_py as nfl
import pandas as pd

from fantasy_quant.config import RAW_DIR
from fantasy_quant.data import db

log = logging.getLogger(__name__)

# 2014 is the practical floor for snap-count coverage; NGS begins 2016 (earlier years just skip).
DEFAULT_YEARS: list[int] = list(range(2014, 2026))  # 2014..2025 inclusive
NFLVERSE_RAW = RAW_DIR / "nflverse"


# --------------------------------------------------------------------------------------------
# pull + cache helpers
# --------------------------------------------------------------------------------------------
def _cache_path(name: str):
    NFLVERSE_RAW.mkdir(parents=True, exist_ok=True)
    return NFLVERSE_RAW / f"{name}.parquet"


def _load_or_pull(name: str, pull_fn: Callable[[], pd.DataFrame],
                  refresh: bool = False) -> pd.DataFrame:
    """Return a dataframe, reading the cached parquet unless ``refresh`` is set."""
    cp = _cache_path(name)
    if cp.exists() and not refresh:
        log.info("cache hit: %s", cp.name)
        return pd.read_parquet(cp)
    df = pull_fn()
    df.to_parquet(cp, index=False)
    log.info("pulled + cached %s (rows=%d)", name, len(df))
    return df


def _pull_by_year(import_fn: Callable[..., pd.DataFrame], years, **kwargs) -> pd.DataFrame:
    """Call a per-year nfl_data_py importer year-by-year, skipping (logging) years that fail.

    Robust to "the latest season isn't published yet" without aborting the whole pull.
    """
    frames = []
    for y in years:
        try:
            frames.append(import_fn([y], **kwargs))
        except Exception as e:  # noqa: BLE001 - upstream raises bare Exceptions for missing years
            log.warning("skip %s year %d: %s", import_fn.__name__, y, e)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# --------------------------------------------------------------------------------------------
# pure transforms (unit-testable without the network)
# --------------------------------------------------------------------------------------------
def map_snaps_gsis(snaps: pd.DataFrame, ids: pd.DataFrame) -> pd.DataFrame:
    """Attach ``gsis_id`` to a snap-counts frame via the ``pfr_id`` crosswalk in ``player_ids``."""
    xwalk = (
        ids.dropna(subset=["pfr_id", "gsis_id"])
        .drop_duplicates("pfr_id")[["pfr_id", "gsis_id"]]
    )
    return snaps.merge(xwalk, left_on="pfr_player_id", right_on="pfr_id", how="left")


# --------------------------------------------------------------------------------------------
# 0.9 — nflverse "stats_player" NEW-release path (post-2024 restructure)
# --------------------------------------------------------------------------------------------
# nflverse restructured player stats after the 2024 season; the frozen ``nfl_data_py`` hardcodes
# the DEAD old path (``player_stats/player_stats_{yr}.parquet``) -> clean 404 for 2025. The live
# data is in the ``stats_player`` release. We read it directly and conform the renamed columns
# back to our legacy ``weekly``/``seasonal`` schema so a new season appends without a migration.
STATS_PLAYER_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "stats_player/stats_player_{kind}_{year}.parquet"
)
# new-release column name -> our legacy schema name
_STATS_RENAME = {
    "player_id": "gsis_id",
    "passing_interceptions": "interceptions",
    "team": "recent_team",
    "sacks_suffered": "sacks",
    "sack_yards_lost": "sack_yards",
}


def conform_stats_player(df: pd.DataFrame, target_cols) -> pd.DataFrame:
    """Rename new-release ``stats_player`` columns to our legacy schema and reindex to
    ``target_cols`` (NA-filling any legacy column the new release dropped, e.g. ``dakota`` and
    the seasonal share/dominator columns). Pure — the unit-test target."""
    return df.rename(columns=_STATS_RENAME).reindex(columns=list(target_cols))


def ingest_depth_charts_ts(con, years=(2025,), refresh: bool = False) -> int:
    """Ingest the **new timestamped** depth charts (2025+) into ``depth_charts_ts``.

    From 2025 on nflverse stopped week-assigning depth charts: each update is appended with an
    ISO8601 ``dt`` timestamp (assign to a point in the season yourself). That grain is incompatible
    with the week-based ``depth_charts`` table (2014–24), so it lands in its own table. A
    ``source_year`` column records which release file each row came from (the file has no season).
    PIT use: latest snapshot with ``dt <= as_of`` per player.
    """
    frames = []
    for year in years:
        d = _load_or_pull(f"depth_charts_ts_{year}",
                          lambda y=year: nfl.import_depth_charts([y]), refresh=refresh)
        d = d.copy()
        d["source_year"] = year
        frames.append(d)
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return db.write_df(con, "depth_charts_ts", df)


def backfill_stats_new_release(con, years=(2025,), refresh: bool = False) -> dict:
    """Append the given ``years`` of ``weekly`` + ``seasonal`` from the NEW ``stats_player``
    release, conformed to the existing table schema. Idempotent (deletes those seasons first).

    weekly  <- ``stats_player_week_{yr}`` (REG + POST) ; seasonal <- ``stats_player_reg_{yr}``.
    Requires a writable connection. Returns ``{table: new_row_count}``.
    """
    counts: dict[str, int] = {}
    for table, kind in (("weekly", "week"), ("seasonal", "reg")):
        target = [c for c in con.execute(f'DESCRIBE "{table}"').df()["column_name"]
                  if c != "pulled_at"]
        for year in years:
            raw = _load_or_pull(
                f"{table}_statsplayer_{year}",
                lambda k=kind, y=year: pd.read_parquet(STATS_PLAYER_URL.format(kind=k, year=y)),
                refresh=refresh,
            )
            new = conform_stats_player(raw, target)
            new = new[new["season"] == year]
            con.execute(f'DELETE FROM "{table}" WHERE season = {int(year)}')
            counts[table] = db.append_df(con, table, new)
            log.info("backfilled %s %d: +%d rows", table, year, len(new))
    return counts


# --------------------------------------------------------------------------------------------
# per-source ingest functions  (each returns the written row count)
# --------------------------------------------------------------------------------------------
def ingest_ids(con, refresh: bool = False) -> int:
    df = _load_or_pull("player_ids", nfl.import_ids, refresh=refresh)
    return db.write_df(con, "player_ids", df)


def ingest_weekly(con, years=DEFAULT_YEARS, refresh: bool = False) -> int:
    df = _load_or_pull("weekly", lambda: _pull_by_year(nfl.import_weekly_data, years), refresh)
    df = df.rename(columns={"player_id": "gsis_id"})
    return db.write_df(con, "weekly", df)


def ingest_seasonal(con, years=DEFAULT_YEARS, refresh: bool = False) -> int:
    df = _load_or_pull("seasonal", lambda: _pull_by_year(nfl.import_seasonal_data, years), refresh)
    df = df.rename(columns={"player_id": "gsis_id"})
    return db.write_df(con, "seasonal", df)


def ingest_snaps(con, years=DEFAULT_YEARS, refresh: bool = False) -> int:
    """Requires ``player_ids`` to already be in the store (run :func:`ingest_ids` first)."""
    df = _load_or_pull("snaps", lambda: _pull_by_year(nfl.import_snap_counts, years), refresh)
    ids = con.execute("SELECT pfr_id, gsis_id FROM player_ids").df()
    df = map_snaps_gsis(df, ids)
    return db.write_df(con, "snaps", df)


def ingest_ngs(con, years=DEFAULT_YEARS, refresh: bool = False) -> int:
    def pull() -> pd.DataFrame:
        frames = []
        for stat_type in ("passing", "rushing", "receiving"):
            try:
                d = nfl.import_ngs_data(stat_type, years)
                d["stat_type"] = stat_type
                frames.append(d)
            except Exception as e:  # noqa: BLE001
                log.warning("skip ngs %s: %s", stat_type, e)
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    df = _load_or_pull("ngs", pull, refresh=refresh)
    if "player_gsis_id" in df.columns:
        df = df.rename(columns={"player_gsis_id": "gsis_id"})
    return db.write_df(con, "ngs", df)


def ingest_draft_picks(con, years=DEFAULT_YEARS, refresh: bool = False) -> int:
    df = _load_or_pull("draft_picks", lambda: nfl.import_draft_picks(years), refresh=refresh)
    return db.write_df(con, "draft_picks", df)


def ingest_combine(con, years=DEFAULT_YEARS, refresh: bool = False) -> int:
    df = _load_or_pull("combine", lambda: nfl.import_combine_data(years), refresh=refresh)
    return db.write_df(con, "combine", df)


def ingest_pbp(con, years=DEFAULT_YEARS, refresh: bool = False, columns=None) -> int:
    """Pull play-by-play **one season at a time** (each cached as its own parquet), then load
    the lot via a ``union_by_name`` glob so per-season schema drift doesn't break the table.
    """
    pbp_dir = NFLVERSE_RAW / "pbp"
    pbp_dir.mkdir(parents=True, exist_ok=True)
    for y in years:
        fp = pbp_dir / f"pbp_{y}.parquet"
        if fp.exists() and not refresh:
            continue
        try:
            d = nfl.import_pbp_data([y], columns=columns, include_participation=False,
                                    downcast=True)
            d.to_parquet(fp, index=False)
            log.info("pbp %d cached (rows=%d)", y, len(d))
        except Exception as e:  # noqa: BLE001
            log.warning("skip pbp %d: %s", y, e)
    return db.write_parquet_glob(con, "pbp", str(pbp_dir / "pbp_*.parquet"))


# --------------------------------------------------------------------------------------------
# verification: the 0.2 done-criterion (weekly <-> snaps gsis join health)
# --------------------------------------------------------------------------------------------
def weekly_snaps_match_rate(con) -> dict:
    """Fraction of regular-season skill-player weeks in ``weekly`` that find a matching ``snaps``
    row by ``(gsis_id, season, week)``. The 0.2 acceptance gate is <1% unmatched.
    """
    row = con.execute(
        """
        WITH wk AS (
            SELECT DISTINCT gsis_id, season, week
            FROM weekly
            WHERE season_type = 'REG'
              AND position IN ('QB', 'RB', 'WR', 'TE')
              AND gsis_id IS NOT NULL
        ),
        sn AS (
            SELECT DISTINCT gsis_id, season, week
            FROM snaps
            WHERE game_type = 'REG' AND gsis_id IS NOT NULL
        )
        SELECT
            COUNT(*)                                            AS weekly_rows,
            COUNT(*) - COUNT(sn.gsis_id)                        AS unmatched
        FROM wk
        LEFT JOIN sn USING (gsis_id, season, week)
        """
    ).fetchone()
    weekly_rows, unmatched = int(row[0]), int(row[1])
    rate = unmatched / weekly_rows if weekly_rows else float("nan")
    return {"weekly_rows": weekly_rows, "unmatched": unmatched, "unmatched_rate": rate}


def per_season_counts(con, table: str = "weekly") -> pd.DataFrame:
    """Row counts per season for a sanity check on coverage."""
    return con.execute(
        f'SELECT season, COUNT(*) AS rows FROM "{table}" GROUP BY season ORDER BY season'
    ).df()


# --------------------------------------------------------------------------------------------
# orchestration
# --------------------------------------------------------------------------------------------
def run_all(con, years=DEFAULT_YEARS, refresh: bool = False, skip_pbp: bool = False) -> dict:
    """Ingest every nflverse source (ids FIRST — snaps mapping depends on it). Returns counts."""
    counts: dict[str, int] = {}
    counts["player_ids"] = ingest_ids(con, refresh=refresh)
    counts["weekly"] = ingest_weekly(con, years=years, refresh=refresh)
    counts["seasonal"] = ingest_seasonal(con, years=years, refresh=refresh)
    counts["snaps"] = ingest_snaps(con, years=years, refresh=refresh)
    counts["ngs"] = ingest_ngs(con, years=years, refresh=refresh)
    counts["draft_picks"] = ingest_draft_picks(con, years=years, refresh=refresh)
    counts["combine"] = ingest_combine(con, years=years, refresh=refresh)
    if not skip_pbp:
        counts["pbp"] = ingest_pbp(con, years=years, refresh=refresh)
    return counts
