"""Phase 0.4 — ADP ingest (the "market price"), point-in-time.

**Source:** Fantasy Football Calculator's public JSON API
(``/api/v1/adp/{scoring}?teams=&year=``). For each season it returns the **late-preseason**
aggregate (e.g. 2024 drafts span Aug 31–Sep 1), so ``meta.end_date`` is a clean PIT snapshot
date for a draft-day as-of. Coverage ≈ **2010–2024** (earlier/later years return empty).

**Underdog best-ball is deferred (documented gap):** the public Underdog endpoints require
auth (404/301 unauthenticated), so free *historical* best-ball ADP isn't available. The schema
is format-aware (``source``/``format`` columns; FFC = redraft) so best-ball slots in later
without a migration. See ``PLAN.md`` open questions.

**Identity:** FFC has no ``gsis_id`` (only its own ``player_id``), so we name-match to the
``player_ids`` crosswalk via :func:`match_adp_to_gsis` (team + position + normalized name, with
draft-year disambiguation for same-name players across eras). Unmatched are logged, not dropped.
"""

from __future__ import annotations

import logging
import re
import time

import httpx
import pandas as pd

from fantasy_quant.config import PROJECT_ROOT, RAW_DIR
from fantasy_quant.data import cache, db

log = logging.getLogger(__name__)

FFC_BASE = "https://fantasyfootballcalculator.com/api/v1/adp"
NAME_OVERRIDES_CSV = PROJECT_ROOT / "reference" / "adp_name_overrides.csv"
HEADERS = {"User-Agent": "Mozilla/5.0 (fantasy-quant research; contact rayhan.driver@gmail.com)"}
ADP_RAW = RAW_DIR / "adp"
DEFAULT_YEARS: list[int] = list(range(2010, 2026))
DEFAULT_SCORINGS = ("standard", "ppr", "half-ppr")
DEFAULT_TEAMS = (10, 12)
_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}
_NON_GSIS_POS = ("DEF", "PK", "K")  # team D/ST and kickers have no gsis_id


# --------------------------------------------------------------------------------------------
# name normalization + identity matching (pure, unit-tested)
# --------------------------------------------------------------------------------------------
def normalize_name(name: str | float) -> str:
    """Lowercase, strip punctuation and generational suffixes, collapse whitespace.

    Applied identically to both FFC names and ``player_ids`` names so they join consistently
    (e.g. "D.J. Moore" -> "dj moore", "Michael Pittman Jr." -> "michael pittman").
    """
    if not isinstance(name, str):
        return ""
    s = name.lower().replace(".", "").replace("'", "").replace("`", "")
    s = re.sub(r"[^a-z\s-]", " ", s)
    tokens = [t for t in s.replace("-", " ").split() if t and t not in _SUFFIXES]
    return " ".join(tokens)


def _load_name_overrides() -> pd.DataFrame:
    """Manual name->gsis fixes for nickname/short-form ADP names the auto-matcher misses
    (committed at ``reference/adp_name_overrides.csv``; columns name, position, gsis_id)."""
    if NAME_OVERRIDES_CSV.exists():
        ov = pd.read_csv(NAME_OVERRIDES_CSV, dtype=str)
        if {"name", "position", "gsis_id"}.issubset(ov.columns):
            return ov.dropna(subset=["name", "gsis_id"])
    return pd.DataFrame(columns=["name", "position", "gsis_id"])


def match_adp_to_gsis(adp: pd.DataFrame, ids: pd.DataFrame,
                      overrides: pd.DataFrame | None = None) -> pd.DataFrame:
    """Attach ``gsis_id`` to ADP rows by normalized name, preferring (in order) a team+position
    match, then a position match closest in draft-year to the ADP season, then name-only, then
    a manual nickname override (``overrides``: name/position/gsis_id).
    """
    a = adp.copy()
    a["_nn"] = a["name"].map(normalize_name)
    a["_pos"] = a["position"].astype(str).str.upper()
    a = a.reset_index(drop=True)
    a["_row"] = a.index

    i = ids.dropna(subset=["gsis_id"]).copy()
    i["_nn"] = i["name"].map(normalize_name)
    i["_pos"] = i["position"].astype(str).str.upper()
    i = i[["_nn", "_pos", "gsis_id", "team", "draft_year"]].rename(columns={"team": "_idteam"})

    # candidate pool by (name, position); score each candidate, keep the best per ADP row.
    cand = a[["_row", "_nn", "_pos", "team", "season"]].merge(i, on=["_nn", "_pos"], how="left")
    cand["_teammatch"] = (cand["_idteam"].astype(str) == cand["team"].astype(str)).astype(int)
    dy = pd.to_numeric(cand["draft_year"], errors="coerce")
    cand["_dyok"] = (dy <= cand["season"]).fillna(False).astype(int)
    cand["_dydist"] = (cand["season"] - dy).abs().fillna(99)
    cand["_score"] = cand["_teammatch"] * 100 + cand["_dyok"] * 10 - cand["_dydist"] * 0.1
    best = (
        cand.dropna(subset=["gsis_id"])
        .sort_values("_score")
        .groupby("_row", as_index=False)
        .tail(1)[["_row", "gsis_id"]]
    )
    out = a.merge(best, on="_row", how="left")

    # tier 3: name-only fallback for whatever's still unmatched.
    miss = out["gsis_id"].isna()
    if miss.any():
        name_only = i.drop_duplicates("_nn").set_index("_nn")["gsis_id"]
        out.loc[miss, "gsis_id"] = out.loc[miss, "_nn"].map(name_only)

    # tier 4: manual nickname/short-form overrides (name + position).
    if overrides is not None and len(overrides):
        ov = overrides.copy()
        ov["_nn"] = ov["name"].map(normalize_name)
        ov["_pos"] = ov["position"].astype(str).str.upper()
        ov_keys = zip(ov["_nn"], ov["_pos"], strict=False)
        ovmap = dict(zip(ov_keys, ov["gsis_id"], strict=False))
        miss = out["gsis_id"].isna()
        if miss.any():
            out.loc[miss, "gsis_id"] = [
                ovmap.get(k)
                for k in zip(out.loc[miss, "_nn"], out.loc[miss, "_pos"], strict=False)
            ]

    return out.drop(columns=["_nn", "_pos", "_row"])


def dedupe_gsis_within_snapshot(df: pd.DataFrame, key: list[str]) -> tuple[pd.DataFrame, int]:
    """Enforce a gsis_id maps to at most one row per ADP snapshot. Homonyms (two real players
    with the same name+position in one board — e.g. the two 2010 "Mike Williams" WRs) can both
    resolve to the same gsis; keep the lower-ADP (more prominent) row and NULL the rest so joins
    stay 1:1. Returns (df, n_nulled)."""
    out = df.copy()
    m = out["gsis_id"].notna()
    ranked = out[m].copy()
    ranked["_r"] = ranked.groupby([*key, "gsis_id"])["adp"].rank(method="first")
    losers = ranked.index[ranked["_r"] > 1]
    out.loc[losers, "gsis_id"] = None
    return out, int(len(losers))


# --------------------------------------------------------------------------------------------
# FFC pull
# --------------------------------------------------------------------------------------------
def _pull_ffc(scoring: str, teams: int, year: int) -> pd.DataFrame:
    """Pull one (scoring, teams, year) ADP table from FFC. Returns empty if that year has none."""
    r = httpx.get(f"{FFC_BASE}/{scoring}",
                  params={"teams": teams, "year": year, "position": "all"},
                  headers=HEADERS, timeout=30)
    r.raise_for_status()
    time.sleep(0.5)  # be polite to FFC
    j = r.json()
    players, meta = j.get("players", []), j.get("meta", {})
    if not players or not meta.get("end_date"):
        return pd.DataFrame()
    df = pd.DataFrame(players)
    df["season"] = year
    df["scoring"] = scoring
    df["teams"] = teams
    df["source"] = "ffc"
    df["format"] = "redraft"
    df["snapshot_date"] = meta["end_date"]
    df["start_date"] = meta.get("start_date")
    df["total_drafts"] = meta.get("total_drafts")
    return df.rename(columns={"player_id": "ffc_player_id"})


def ingest_adp(con, years=DEFAULT_YEARS, scorings=DEFAULT_SCORINGS, teams_list=DEFAULT_TEAMS,
               refresh: bool = False) -> int:
    """Pull the FFC grid, gsis-match, compute pos_rank, write ``adp_snapshots``."""
    ids = con.execute("SELECT name, position, team, gsis_id, draft_year FROM player_ids").df()
    overrides = _load_name_overrides()
    frames = []
    for scoring in scorings:
        for teams in teams_list:
            for year in years:
                df = cache.load_or_pull(
                    ADP_RAW / f"ffc_{scoring}_t{teams}_{year}.parquet",
                    lambda s=scoring, t=teams, y=year: _pull_ffc(s, t, y),
                    refresh=refresh,
                )
                if not df.empty:
                    frames.append(df)
    raw = pd.concat(frames, ignore_index=True)
    raw = match_adp_to_gsis(raw, ids, overrides=overrides)
    raw, n_nulled = dedupe_gsis_within_snapshot(
        raw, ["season", "source", "format", "scoring", "teams"]
    )
    if n_nulled:
        log.info("nulled %d homonym-collided gsis so each snapshot maps 1:1", n_nulled)
    raw["snapshot_date"] = pd.to_datetime(raw["snapshot_date"]).dt.date
    raw["start_date"] = pd.to_datetime(raw["start_date"], errors="coerce").dt.date
    raw["pos_rank"] = (
        raw.groupby(["season", "source", "format", "scoring", "teams", "position"])["adp"]
        .rank(method="first")
        .astype(int)
    )
    keep = [
        "season", "snapshot_date", "start_date", "source", "format", "scoring", "teams",
        "gsis_id", "ffc_player_id", "name", "position", "team", "adp", "pos_rank",
        "times_drafted", "stdev", "high", "low", "bye", "total_drafts",
    ]
    raw = raw[[c for c in keep if c in raw.columns]]

    unmatched = raw[raw["gsis_id"].isna() & ~raw["position"].isin(_NON_GSIS_POS)]
    if len(unmatched):
        out = ADP_RAW / "unmatched_adp.csv"
        unmatched[["season", "name", "position", "team", "adp"]].to_csv(out, index=False)
        log.info("logged %d unmatched ADP rows -> %s", len(unmatched), out)
    return db.write_df(con, "adp_snapshots", raw)


# --------------------------------------------------------------------------------------------
# Stage 0 — recurring in-season snapshot series (the 2026 board is unrecoverable later)
# --------------------------------------------------------------------------------------------
SNAPSHOT_DIR = ADP_RAW / "snapshots"


def new_snapshot_rows(df: pd.DataFrame, existing_keys: set[tuple]) -> pd.DataFrame:
    """Rows of ``df`` whose ``(season, source, format, scoring, teams, snapshot_date)`` key is not
    already in the store — the idempotency filter for the snapshot append (pure, unit-tested)."""
    if df.empty:
        return df
    keys = list(zip(
        df["season"].astype(int), df["source"], df["format"], df["scoring"],
        df["teams"].astype(int), pd.to_datetime(df["snapshot_date"]).dt.date,
        strict=True,
    ))
    mask = [k not in existing_keys for k in keys]
    return df[mask]


def _existing_snapshot_keys(con, season: int) -> set[tuple]:
    if not db.table_exists(con, "adp_snapshots"):
        return set()
    rows = con.execute(
        "SELECT DISTINCT season, source, format, scoring, teams, snapshot_date "
        "FROM adp_snapshots WHERE season = ?", [int(season)]
    ).fetchall()
    return {(int(r[0]), r[1], r[2], r[3], int(r[4]), pd.Timestamp(r[5]).date()) for r in rows}


def snapshot_adp(con, season: int, scorings=DEFAULT_SCORINGS, teams_list=DEFAULT_TEAMS) -> dict:
    """Bank today's FFC board for ``season`` as a new PIT snapshot (Stage 0 recurring pull).

    Unlike :func:`ingest_adp` (one late-preseason snapshot per historical season, table replace),
    this accumulates a **series** of snapshots for one live season: each pull is cached to a
    parquet keyed by FFC's ``meta.end_date`` under ``data/raw/adp/snapshots/``, then *every*
    cached snapshot for the season is replayed and only rows whose
    ``(season, source, format, scoring, teams, snapshot_date)`` key is missing from
    ``adp_snapshots`` are appended — idempotent per day, and self-healing after any 0.4 table
    rebuild (which only restores the single per-season snapshots). ``adp_asof`` needs no change:
    it already selects the latest snapshot ≤ as_of.
    """
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    pulled = []
    for scoring in scorings:
        for teams in teams_list:
            df = _pull_ffc(scoring, teams, season)
            if df.empty:
                log.warning("FFC returned no %s/%d-team board for %d", scoring, teams, season)
                continue
            snap = pd.to_datetime(df["snapshot_date"].iloc[0]).date()
            path = SNAPSHOT_DIR / f"ffc_{scoring}_t{teams}_{season}_{snap}.parquet"
            df.to_parquet(path, index=False)
            pulled.append(path.name)

    cached = sorted(SNAPSHOT_DIR.glob(f"ffc_*_{season}_*.parquet"))
    if not cached:
        return {"pulled": pulled, "new_rows": 0, "snapshot_dates": []}
    raw = pd.concat([pd.read_parquet(p) for p in cached], ignore_index=True)

    ids = con.execute("SELECT name, position, team, gsis_id, draft_year FROM player_ids").df()
    raw = match_adp_to_gsis(raw, ids, overrides=_load_name_overrides())
    # snapshot_date joins every key: the series holds many snapshots per (season, config).
    snap_key = ["season", "source", "format", "scoring", "teams", "snapshot_date"]
    raw, n_nulled = dedupe_gsis_within_snapshot(raw, snap_key)
    if n_nulled:
        log.info("nulled %d homonym-collided gsis within snapshots", n_nulled)
    raw["snapshot_date"] = pd.to_datetime(raw["snapshot_date"]).dt.date
    raw["start_date"] = pd.to_datetime(raw["start_date"], errors="coerce").dt.date
    raw["pos_rank"] = (
        raw.groupby([*snap_key, "position"])["adp"].rank(method="first").astype(int)
    )
    keep = [
        "season", "snapshot_date", "start_date", "source", "format", "scoring", "teams",
        "gsis_id", "ffc_player_id", "name", "position", "team", "adp", "pos_rank",
        "times_drafted", "stdev", "high", "low", "bye", "total_drafts",
    ]
    raw = raw[[c for c in keep if c in raw.columns]]

    new = new_snapshot_rows(raw, _existing_snapshot_keys(con, season))
    if len(new):
        db.append_df(con, "adp_snapshots", new)
    dates = sorted(pd.to_datetime(new["snapshot_date"]).dt.date.unique()) if len(new) else []
    return {"pulled": pulled, "new_rows": int(len(new)), "snapshot_dates": [str(d) for d in dates]}


# --------------------------------------------------------------------------------------------
# PIT accessor — the done-criterion
# --------------------------------------------------------------------------------------------
def adp_asof(con, season: int, as_of, source: str = "ffc", scoring: str = "ppr",
             teams: int = 10) -> pd.DataFrame:
    """Latest ADP snapshot for ``season`` dated **on or before** ``as_of`` (PIT).

    Asserts no returned row is dated after ``as_of`` — the structural guard against look-ahead.
    """
    as_of_d = pd.to_datetime(as_of).date()
    df = con.execute(
        """
        SELECT * FROM adp_snapshots
        WHERE season = ? AND source = ? AND scoring = ? AND teams = ?
          AND snapshot_date <= ?
        QUALIFY snapshot_date = MAX(snapshot_date) OVER ()
        ORDER BY adp
        """,
        [season, source, scoring, teams, as_of_d],
    ).df()
    if not df.empty:
        latest = pd.to_datetime(df["snapshot_date"]).max()
        assert latest <= pd.Timestamp(as_of_d), "PIT violation: adp_asof returned a future snapshot"
    return df


def coverage(con) -> dict:
    seasons = [r[0] for r in con.execute(
        "SELECT DISTINCT season FROM adp_snapshots ORDER BY season").fetchall()]
    return {"seasons": seasons, "min": min(seasons), "max": max(seasons)}


def match_rate(con) -> dict:
    """gsis match rate overall and among draftable skill players (top-150 ADP, non-DST/K)."""
    skip = ", ".join(f"'{p}'" for p in _NON_GSIS_POS)
    total, matched = con.execute(
        f"SELECT COUNT(*), COUNT(gsis_id) FROM adp_snapshots WHERE position NOT IN ({skip})"
    ).fetchone()
    t150, m150 = con.execute(
        f"SELECT COUNT(*), COUNT(gsis_id) FROM adp_snapshots "
        f"WHERE position NOT IN ({skip}) AND adp <= 150"
    ).fetchone()
    return {
        "skill_rows": int(total),
        "skill_unmatched_rate": (total - matched) / total if total else float("nan"),
        "top150_rows": int(t150),
        "top150_unmatched_rate": (t150 - m150) / t150 if t150 else float("nan"),
    }
