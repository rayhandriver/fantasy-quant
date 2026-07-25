"""Phase 0.11 — FantasyPros **ECR** (Expert Consensus *Rank*) ingest.

Distinct from ``projections/consensus.py``, which scrapes the FantasyPros *projection* pages
(points). This scrapes the **cheatsheet/ranking** pages, which carry what we never stored before:
the experts' consensus **rank**, their **disagreement** (``rank_std``, ``rank_min``/``rank_max``
across ~90–230 experts), the published **tier**, and the recent **ECR delta**. Phase 16.8 wants a
true "expert-rank minus ADP" gap rather than the VBD-``overall_rank`` proxy.

**★ The archive is real but it is a single END-OF-PRESEASON snapshot (verified 2026-07-25).**
``?year=YYYY`` genuinely serves that season's board (2020 → McCaffrey/Barkley/Elliott, 2018 →
Gurley/Johnson/Brown), so history back to 2017 is free — but every archived board's
``last_updated_ts`` lands in **early-to-mid September**, i.e. at kickoff, *after* the drafts we
would explain with it. Measured on the Phase-16.7 corpus: **1 of 38** preseason drafts starts on or
after its own season's ECR timestamp.

Two consequences, both structural rather than advisory:

1. :func:`ecr_asof` refuses to return a board dated after the caller's as-of, exactly like
   :func:`~fantasy_quant.data.sources.adp.adp_asof`. Any PIT consumer therefore gets an **empty
   frame** for a pre-September as-of rather than a silently future-dated board.
2. Phase 16.8 consequently does **not** use ECR historically (it keeps the VBD-gap proxy); ECR is a
   live-season input. This is not a limitation of the scrape — it is the archive's grain.

Banking the history anyway is deliberate: it is free, it may vanish, and a ~Sep-7 board **is**
PIT-clean for anything scored on the *season outcome* (Week 1 onward), e.g. a genuine expert
baseline for the Phase-6/16.1 value work where the FFC board (~Sep 1) is already the as-of.

Underdog ADP (the other half of 0.11 as originally scoped) is **not** ingested: it has no keyless
endpoint — the marketing routes 404 and the board is a JS app behind an unpublished API. Deferred,
not attempted. See ``docs/BUILD_PLAN.md`` §0.11.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
import time
from collections.abc import Iterable, Sequence

import httpx
import pandas as pd

from fantasy_quant.config import RAW_DIR
from fantasy_quant.data import cache, db
from fantasy_quant.data.sources.adp import (
    _load_name_overrides,
    dedupe_gsis_within_snapshot,
    match_adp_to_gsis,
)

log = logging.getLogger(__name__)

ECR_RAW = RAW_DIR / "ecr"
FP_RANKINGS = "https://www.fantasypros.com/nfl/rankings"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; fantasy-quant research)"}

#: scoring → cheatsheet page slug. Keys match ``adp_snapshots.scoring`` so the two boards join.
ECR_SLUGS: dict[str, str] = {
    "ppr": "ppr-cheatsheets.php",
    "half-ppr": "half-point-ppr-cheatsheets.php",
    "standard": "consensus-cheatsheets.php",
}
SOURCE = "fantasypros_ecr"

DEFAULT_YEARS: tuple[int, ...] = tuple(range(2017, 2027))
DEFAULT_SCORINGS: tuple[str, ...] = ("ppr", "half-ppr", "standard")

#: a real board is never this small — below the floor we retry rather than cache a truncated shell.
MIN_ROWS = 150

# The rankings payload is a ``var ecrData = {...};`` blob in the page source.
_ECR_RE = re.compile(r"var\s+ecrData\s*=\s*(\{.*?\})\s*;\s*\n", re.S)

_NON_GSIS_POS = {"DST", "DEF", "K", "PK"}

CONTRACT_COLS = [
    "season", "as_of", "is_preseason", "source", "scoring", "gsis_id", "name", "position", "team",
    "ecr", "ecr_min", "ecr_max", "ecr_avg", "ecr_std", "pos_rank", "tier", "ecr_delta",
    "bye", "total_experts", "n_players",
]

#: A board stamped after this (month, day) of its own season was re-touched *during or after* the
#: season, so it is not a preseason consensus at all. Observed live: the 2023 PPR board carries
#: ``as_of = 2024-02-12`` — post-Super-Bowl. ``ecr_asof`` still keeps it PIT-safe (it refuses a
#: future-dated join), but any consumer wanting a *draft-season* expert baseline must filter on
#: ``is_preseason``, because that board saw the season it is supposed to precede.
PRESEASON_CUTOFF = (9, 15)


# ------------------------------------------------------------------------------------------------
# pure parsing (no network — the offline-testable half)
# ------------------------------------------------------------------------------------------------
def extract_ecr_json(html: str) -> dict:
    """Pull the ``ecrData`` blob out of a cheatsheet page. Raises if the page has no payload.

    NB the page *also* embeds unrelated player widgets whose contents are identical across years;
    matching those instead of ``ecrData`` is what made the archive look non-historical on a first
    pass. Always key off this blob.
    """
    m = _ECR_RE.search(html)
    if not m:
        raise ValueError("no ecrData payload in page (layout change or blocked response)")
    return json.loads(m.group(1))


def _as_of_from_meta(meta: dict) -> dt.date | None:
    """Board date from ``last_updated_ts`` (epoch seconds). This is the PIT stamp — the archived
    board is whatever the consensus last said, which for a past season is at/near kickoff."""
    ts = meta.get("last_updated_ts")
    if ts in (None, "", 0):
        return None
    return dt.datetime.fromtimestamp(int(ts), tz=dt.UTC).date()


def _num(s) -> float:
    try:
        return float(s)
    except (TypeError, ValueError):
        return float("nan")


def parse_ecr(html: str, *, scoring: str, season: int | None = None) -> pd.DataFrame:
    """Flatten one cheatsheet page into the ECR row shape (pre-gsis-match).

    ``season`` overrides the page's own ``year`` only when the page omits it; a mismatch between
    the requested and served year is the caller's to police (:func:`_pull_ecr` asserts it).
    """
    data = extract_ecr_json(html)
    players = data.get("players") or []
    if not players:
        return pd.DataFrame()
    rows = pd.DataFrame(players)
    year = int(data.get("year") or season or 0)
    out = pd.DataFrame({
        "season": year,
        "as_of": _as_of_from_meta(data),
        "source": SOURCE,
        "scoring": scoring,
        "name": rows.get("player_name"),
        "position": rows.get("player_position_id"),
        "team": rows.get("player_team_id"),
        "ecr": pd.to_numeric(rows.get("rank_ecr"), errors="coerce"),
        "ecr_min": rows.get("rank_min").map(_num) if "rank_min" in rows else float("nan"),
        "ecr_max": rows.get("rank_max").map(_num) if "rank_max" in rows else float("nan"),
        "ecr_avg": rows.get("rank_ave").map(_num) if "rank_ave" in rows else float("nan"),
        # expert disagreement — the ECR analog of the FFC board's ``stdev``.
        "ecr_std": rows.get("rank_std").map(_num) if "rank_std" in rows else float("nan"),
        "tier": pd.to_numeric(rows.get("tier"), errors="coerce"),
        "ecr_delta": pd.to_numeric(rows.get("player_ecr_delta"), errors="coerce"),
        "bye": pd.to_numeric(rows.get("player_bye_week"), errors="coerce"),
        "total_experts": pd.to_numeric(data.get("total_experts"), errors="coerce"),
        "n_players": int(data.get("count") or len(rows)),
    })
    # ``pos_rank`` ships as "WR1"/"RB12" — keep the integer so it joins the ADP board's pos_rank.
    if "pos_rank" in rows:
        out["pos_rank"] = pd.to_numeric(
            rows["pos_rank"].astype(str).str.extract(r"(\d+)", expand=False), errors="coerce")
    else:
        out["pos_rank"] = pd.NA
    out = out[out["ecr"].notna()].reset_index(drop=True)
    out["is_preseason"] = _is_preseason(out["as_of"], year)
    return out


def _is_preseason(as_of, season: int) -> pd.Series | bool:
    """Whether a board's stamp precedes its own season's kickoff (see :data:`PRESEASON_CUTOFF`)."""
    cutoff = dt.date(int(season), *PRESEASON_CUTOFF) if season else None
    if cutoff is None:
        return False
    s = pd.Series(as_of) if not isinstance(as_of, pd.Series) else as_of
    return s.map(lambda d: bool(d is not None and d == d and d <= cutoff))


# ------------------------------------------------------------------------------------------------
# network pull
# ------------------------------------------------------------------------------------------------
def _pull_ecr(scoring: str, year: int, attempts: int = 3) -> pd.DataFrame:
    """Fetch one (scoring, year) ECR board. Retries a truncated page, archives the best payload.

    Asserts the served ``year`` matches the request — FantasyPros silently falls back to the
    current cycle for years it has no archive for, and a mis-stamped board would poison the panel.
    """
    slug = ECR_SLUGS[scoring]
    params = {"year": str(year)}
    best = pd.DataFrame()
    for _ in range(attempts):
        r = httpx.get(f"{FP_RANKINGS}/{slug}", params=params, headers=HEADERS, timeout=30,
                      follow_redirects=True)
        r.raise_for_status()
        time.sleep(0.6)  # be polite
        try:
            df = parse_ecr(r.text, scoring=scoring, season=year)
        except ValueError:
            df = pd.DataFrame()
        if len(df) > len(best):
            best = df
            cache.archive_text(ECR_RAW / "payloads", f"ecr_{scoring}_{year}", r.text, "html")
        if len(best) >= MIN_ROWS:
            break
        time.sleep(1.0)
    if best.empty:
        log.warning("ECR %s %d: no rows after %d attempts", scoring, year, attempts)
        return best
    served = int(best["season"].iloc[0])
    if served != int(year):
        # not an assert: a missing archive year should skip, not kill a multi-year ingest.
        log.warning("ECR %s: requested %d but page served %d — skipping", scoring, year, served)
        return pd.DataFrame()
    if len(best) < MIN_ROWS:
        log.warning("ECR %s %d: %d rows (< floor %d) — partial page", scoring, year, len(best),
                    MIN_ROWS)
    return best


# ------------------------------------------------------------------------------------------------
# ingest
# ------------------------------------------------------------------------------------------------
def ingest_ecr(con, years: Iterable[int] = DEFAULT_YEARS,
               scorings: Sequence[str] = DEFAULT_SCORINGS, refresh: bool = False) -> int:
    """Pull the ECR grid, gsis-match, and write ``ecr_snapshots``. Returns the row count.

    Cached per (scoring, year) like the FFC grid, so a rerun is cheap and the archive is captured
    once. K/DST carry no gsis and are kept unmatched (same convention as the ADP board).
    """
    ids = con.execute("SELECT name, position, team, gsis_id, draft_year FROM player_ids").df()
    overrides = _load_name_overrides()
    frames = []
    for scoring in scorings:
        for year in years:
            df = cache.load_or_pull(
                ECR_RAW / f"ecr_{scoring}_{year}.parquet",
                lambda s=scoring, y=year: _pull_ecr(s, y),
                refresh=refresh,
            )
            if not df.empty:
                frames.append(df)
    if not frames:
        return 0
    raw = pd.concat(frames, ignore_index=True)
    raw = match_adp_to_gsis(raw, ids, overrides=overrides)
    # ``dedupe_gsis_within_snapshot`` keeps the lowest-``adp`` row per collided gsis; on a rank
    # board the same tiebreak is the lowest ``ecr``, so alias it rather than fork the helper.
    raw["adp"] = raw["ecr"]
    raw, n_nulled = dedupe_gsis_within_snapshot(raw, ["season", "source", "scoring"])
    raw = raw.drop(columns=["adp"])
    if n_nulled:
        log.info("nulled %d homonym-collided gsis so each ECR board maps 1:1", n_nulled)
    raw["as_of"] = pd.to_datetime(raw["as_of"], errors="coerce").dt.date
    raw = raw[[c for c in CONTRACT_COLS if c in raw.columns]]
    return db.write_df(con, "ecr_snapshots", raw)


# ------------------------------------------------------------------------------------------------
# PIT reader
# ------------------------------------------------------------------------------------------------
def ecr_asof(con, season: int, as_of, scoring: str = "ppr") -> pd.DataFrame:
    """Latest ECR board for ``season`` dated **on or before** ``as_of`` (PIT).

    Returns an **empty frame** when the only archived board post-dates ``as_of`` — which for a
    historical season is the normal case, because the archive is a kickoff-dated snapshot (module
    docstring). That emptiness is the point: it makes a look-ahead join impossible rather than
    merely discouraged.
    """
    as_of_d = pd.to_datetime(as_of).date()
    df = con.execute(
        """
        SELECT * FROM ecr_snapshots
        WHERE season = ? AND source = ? AND scoring = ? AND as_of <= ?
        QUALIFY as_of = MAX(as_of) OVER ()
        ORDER BY ecr
        """,
        [int(season), SOURCE, scoring, as_of_d],
    ).df()
    if not df.empty:
        assert pd.to_datetime(df["as_of"]).max() <= pd.Timestamp(as_of_d), \
            "PIT violation: ecr_asof returned a future board"
    return df


def coverage(con) -> pd.DataFrame:
    """Per (season, scoring): board size, as-of date, expert count — the ingest's report card."""
    return con.execute(
        """
        SELECT season, scoring, MAX(as_of) AS as_of, BOOL_AND(is_preseason) AS is_preseason,
               COUNT(*) AS n_rows, MAX(total_experts) AS experts,
               AVG(CASE WHEN gsis_id IS NOT NULL THEN 1.0 ELSE 0.0 END) AS gsis_rate
        FROM ecr_snapshots GROUP BY season, scoring ORDER BY season, scoring
        """
    ).df()


def match_rate(con, top_n: int = 150) -> float:
    """gsis match rate among draftable skill players (top-``top_n`` ECR, excluding K/DST)."""
    row = con.execute(
        f"""
        SELECT AVG(CASE WHEN gsis_id IS NOT NULL THEN 1.0 ELSE 0.0 END)
        FROM ecr_snapshots
        WHERE ecr <= {int(top_n)} AND UPPER(position) NOT IN ('DST','DEF','K','PK')
        """
    ).fetchone()
    return float(row[0]) if row and row[0] is not None else 0.0
