"""Phase 4.1 — consensus-projections ingest (the reframe's VALUE signal), two-track + PIT.

Reframe (2026-07-04): the value signal is **consensus projections → VBD**, not an own edge-seeking
model (our Phase-2 backtest shows that fight is unwinnable on ~10 seasons). Free *historical*
consensus boards don't exist, so this runs **two tracks behind one interface**:

  * **LIVE (current season):** scrape the free FantasyPros consensus projection pages, re-score the
    projected component stats to full-PPR with our own :class:`RuleSet` (so consensus points match
    the rest of the repo exactly — not FantasyPros' own scoring), name-match to ``gsis_id``,
    PIT-stamp, and write ``consensus_projections``.
  * **HISTORICAL (backtest):** no free consensus board exists for 2014–2024, so the Phase-2 baseline
    (:mod:`projections.baseline`) stands in as the consensus **proxy** — documented and honest
    (`findings.md` 2026-07-05). The optimizer machinery is identical; only the mean's provenance
    differs, and the live board is what a real user drafts on.

:func:`consensus_projection` dispatches: a scraped board for ``season`` in the store → use it (PIT);
otherwise → the baseline proxy. Both return the same ``[player_key, pos, proj_points]`` shape, so
either drops straight into :func:`fantasy_quant.valuation.vbd.vbd_rank_fn` and the Phase-4.2 board.
"""

from __future__ import annotations

import io
import logging
import time

import httpx
import pandas as pd

from fantasy_quant.backtest.scoring import RuleSet, score_offense
from fantasy_quant.config import RAW_DIR
from fantasy_quant.data import cache, db
from fantasy_quant.data.sources.adp import _load_name_overrides, match_adp_to_gsis
from fantasy_quant.projections.baseline import baseline_projection

log = logging.getLogger(__name__)

FP_BASE = "https://www.fantasypros.com/nfl/projections"
HEADERS = {"User-Agent": "Mozilla/5.0 (fantasy-quant research; contact rayhan.driver@gmail.com)"}
CONSENSUS_RAW = RAW_DIR / "consensus"
FP_POSITIONS = ("qb", "rb", "wr", "te", "k")
CONSENSUS_TABLE = "consensus_projections"
# FantasyPros occasionally serves a truncated ~10-row shell on a cold CDN hit; a healthy page has
# many more. Below this per-position floor we treat the page as partial and retry (never cache it).
# (FantasyPros reliably serves only its top ~10 kickers without JS — enough for a 10-team draft.)
_MIN_ROWS = {"qb": 24, "rb": 40, "wr": 50, "te": 24, "k": 10}

# FantasyPros grouped column -> our weekly-style stat name (so score_offense reconstructs full-PPR).
# FL (fumbles lost) folds into one fumble bucket; score_offense sums the three, so use just one.
_COLMAP = {
    "passing_yds": "passing_yards", "passing_tds": "passing_tds", "passing_ints": "interceptions",
    "rushing_yds": "rushing_yards", "rushing_tds": "rushing_tds",
    "receiving_rec": "receptions", "receiving_yds": "receiving_yards",
    "receiving_tds": "receiving_tds", "misc_fl": "rushing_fumbles_lost",
}
_STAT_COLS = list(dict.fromkeys(_COLMAP.values()))


# --------------------------------------------------------------------------------------------
# parsing (pure, unit-tested — no network)
# --------------------------------------------------------------------------------------------
def parse_player_team(cell: str | float) -> tuple[str, str | None]:
    """Split a FantasyPros ``Player`` cell ("Jahmyr Gibbs DET") into (name, team-abbrev).

    The team is the trailing 2–3 uppercase-letter token; if there's no such token (rare), team is
    ``None`` and the whole cell is the name.
    """
    if not isinstance(cell, str) or not cell.strip():
        return "", None
    toks = cell.split()
    if len(toks) >= 2 and toks[-1].isupper() and 2 <= len(toks[-1]) <= 3:
        return " ".join(toks[:-1]), toks[-1]
    return cell.strip(), None


def flatten_fp_table(raw: pd.DataFrame, pos: str) -> pd.DataFrame:
    """Flatten a FantasyPros MultiIndex projection table into tidy weekly-style stat columns.

    Returns ``name, team, position`` + whatever of :data:`_STAT_COLS` the page carries + ``fp_fpts``
    (FantasyPros' own points, kept only for a sanity cross-check). Pure — the unit-test target.
    """
    # collapse the MultiIndex to scalar labels first (rename() on a MultiIndex maps per-level, not
    # per-tuple), mapping each grouped "group_stat" column to our weekly-style stat name.
    new_cols = []
    for col in raw.columns:
        parts = col if isinstance(col, tuple) else (col,)
        key = "_".join(str(p) for p in parts).lower()
        second = str(parts[-1]).lower()
        if "player" in second:
            new_cols.append("player")
        elif second == "fpts":
            new_cols.append("fp_fpts")
        else:
            new_cols.append(next((v for k, v in _COLMAP.items() if key.endswith(k)), key))
    df = raw.copy()
    df.columns = new_cols
    df = df.loc[:, ~df.columns.duplicated()]
    keep = ["player", *[c for c in _STAT_COLS if c in df.columns]]
    if "fp_fpts" in df.columns:
        keep.append("fp_fpts")
    df = df[[c for c in keep if c in df.columns]].copy()

    pt = df["player"].map(parse_player_team)
    df["name"] = pt.map(lambda x: x[0])
    df["team"] = pt.map(lambda x: x[1])
    df["position"] = pos.upper()
    df = df[df["name"].str.len() > 0].drop(columns=["player"])
    for c in [*_STAT_COLS, "fp_fpts"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    return df.reset_index(drop=True)


def consensus_points(df: pd.DataFrame, ruleset: RuleSet | None = None) -> pd.Series:
    """Full-PPR points for projected offensive stats via :func:`score_offense` (our RuleSet, not
    FantasyPros'). Kickers carry no reconstructable stats here, so K rows fall back to ``fp_fpts``.
    """
    rs = ruleset or RuleSet()
    pts = score_offense(df, rs.offense)
    is_k = df["position"].astype(str).str.upper().isin(["K", "PK"])
    if is_k.any() and "fp_fpts" in df.columns:
        pts = pts.mask(is_k, df["fp_fpts"])
    return pts


# --------------------------------------------------------------------------------------------
# network pull + ingest
# --------------------------------------------------------------------------------------------
def _pull_fp(pos: str, scoring_slug: str = "PPR", attempts: int = 4) -> pd.DataFrame:
    """Fetch + flatten one FantasyPros position page (full-season "draft" projections).

    Retries when the page comes back below its :data:`_MIN_ROWS` floor (a transient truncated
    shell), keeping the largest table seen so a partial page is never cached downstream.
    """
    floor = _MIN_ROWS.get(pos, 20)
    best = pd.DataFrame()
    for _ in range(attempts):
        r = httpx.get(f"{FP_BASE}/{pos}.php", params={"week": "draft", "scoring": scoring_slug},
                      headers=HEADERS, timeout=30)
        r.raise_for_status()
        time.sleep(0.5)  # be polite
        tables = pd.read_html(io.StringIO(r.text))
        df = flatten_fp_table(tables[0], pos) if tables else pd.DataFrame()
        if len(df) > len(best):
            best = df
        if len(best) >= floor:
            return best
        time.sleep(1.0)  # back off before retrying a partial page
    if len(best) < floor:
        log.warning("FantasyPros %s: %d rows after %d attempts (< floor %d) — partial page",
                    pos, len(best), attempts, floor)
    return best


def ingest_consensus(con, season: int, scoring_slug: str = "PPR", refresh: bool = False) -> int:
    """Scrape the FantasyPros consensus board for ``season``, re-score to full-PPR, gsis-match, and
    write ``consensus_projections`` (PIT-stamped with today's ``snapshot_date``). Returns row count.

    ``season`` is the *target* season being drafted; FantasyPros serves the current cycle, so this
    is meaningful only for the live/upcoming season. Historical seasons use the baseline proxy.
    """
    season = int(season)
    frames = []
    for pos in FP_POSITIONS:
        df = cache.load_or_pull(
            CONSENSUS_RAW / f"fp_{season}_{scoring_slug}_{pos}.parquet",
            lambda p=pos: _pull_fp(p, scoring_slug), refresh=refresh)
        if not df.empty:
            frames.append(df)
    if not frames:
        log.warning("FantasyPros returned no consensus rows for %s", season)
        return 0
    raw = pd.concat(frames, ignore_index=True)
    raw["proj_points"] = consensus_points(raw)
    raw["season"] = season

    ids = con.execute("SELECT name, position, team, gsis_id, draft_year FROM player_ids").df()
    matched = match_adp_to_gsis(raw, ids, overrides=_load_name_overrides())
    matched["snapshot_date"] = pd.Timestamp(db.utc_now().date())
    matched["source"] = "fantasypros"
    matched["scoring"] = scoring_slug.lower()

    keep = ["season", "snapshot_date", "source", "scoring", "gsis_id", "name", "position", "team",
            "proj_points", "fp_fpts", *[c for c in _STAT_COLS if c in matched.columns]]
    out = matched[[c for c in keep if c in matched.columns]]
    unmatched = int(out["gsis_id"].isna().sum())
    if unmatched:
        log.info("consensus %s: %d/%d rows unmatched to gsis (new rookies/name gaps)",
                 season, unmatched, len(out))
    return db.write_df(con, CONSENSUS_TABLE, out)


# --------------------------------------------------------------------------------------------
# PIT accessor + the two-track dispatch
# --------------------------------------------------------------------------------------------
def has_consensus(con, season: int) -> bool:
    """True iff a scraped consensus board exists in the store for ``season``."""
    if not db.table_exists(con, CONSENSUS_TABLE):
        return False
    n = con.execute(f"SELECT COUNT(*) FROM {CONSENSUS_TABLE} WHERE season = ?",
                    [int(season)]).fetchone()[0]
    return n > 0


def consensus_asof(con, season: int, as_of=None) -> pd.DataFrame:
    """Latest scraped consensus board for ``season`` dated **on or before** ``as_of`` (PIT), as
    ``[player_key, pos, proj_points]``. ``player_key`` = gsis where matched, else the normalized
    name (so unmatched newcomers still line up with an ADP-name board key)."""
    as_of = as_of or f"{season}-09-01"
    as_of_d = pd.to_datetime(as_of).date()
    df = con.execute(
        f"""
        SELECT * FROM {CONSENSUS_TABLE}
        WHERE season = ? AND snapshot_date <= ?
        QUALIFY snapshot_date = MAX(snapshot_date) OVER ()
        """,
        [int(season), as_of_d],
    ).df()
    if df.empty:
        return pd.DataFrame(columns=["player_key", "pos", "proj_points"])
    assert pd.to_datetime(df["snapshot_date"]).max().date() <= as_of_d, \
        "PIT violation: consensus_asof returned a future snapshot"
    df["player_key"] = df["gsis_id"].where(df["gsis_id"].notna(), df["name"])
    return (df.rename(columns={"position": "pos"})[["player_key", "pos", "proj_points"]]
              .dropna(subset=["player_key"]).drop_duplicates("player_key").reset_index(drop=True))


def consensus_projection(con, season: int, as_of=None, ruleset: RuleSet | None = None,
                         allow_proxy: bool = True) -> pd.DataFrame:
    """The VALUE mean for ``season`` as ``[player_key, pos, proj_points]`` (two-track):

      * a scraped FantasyPros consensus board if one exists for ``season`` (the live track); else
      * the Phase-2 baseline as the historical-consensus **proxy** (``allow_proxy``).

    Rookies are absent from the baseline proxy (no prior production) → filled by the Phase-4.3
    rookie model in the value board; the live FantasyPros board already includes them.
    """
    if has_consensus(con, season):
        board = consensus_asof(con, season, as_of)
        if not board.empty:
            return board
    if not allow_proxy:
        return pd.DataFrame(columns=["player_key", "pos", "proj_points"])
    return baseline_projection(con, season, as_of, ruleset)
