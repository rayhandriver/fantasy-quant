"""Phase 12.1 — news sources (the PIT, timestamped, deduped news-event stream).

Phase 0.6 already *ingests* the raw feeds (``news/ingest.py``: ``injuries``, ``depth_charts``,
``news_raw``). This module turns them into the one thing the extractor (12.2), the event study
(12.3) and the validation gate (12.4) all consume: a **unified event stream** with a common schema,
each row a single timestamped fact keyed (where possible) to a ``player_key`` = ``gsis_id``.

    player_key · season · week · team · pos · news_type · status · detail · magnitude · event_ts ·
    text

Two of the three feeds are **historical and PIT-backfillable**, and they are the ones the event
study / gate actually run on:

* **injury_status** — official injury-report designations (Out / Doubtful / Questionable / Probable)
  with the report's own ``date_modified`` timestamp. 2014–2025, native ``gsis_id``. The
  freshest-information edge the reframe cares about: a Wednesday "Out" is known before Sunday's
  games
  yet a set-and-forget lineup (or a stale season projection) hasn't reacted.
* **depth_change** — week-over-week movement in a player's depth-chart rank (``depth_team``): a
  demotion (rank worsens) or promotion (rank improves) is a role-change event.

The third, **headline** (beat-writer RSS), is **forward-capture only** (``news_raw`` can't be
backfilled — 109 rows and counting) and its player identity + structured meaning need the LLM
extractor (12.2). It is surfaced here as raw ``text`` with a null ``player_key``; it does not enter
the historical event study. This is the honest consequence of the free-data constraint (the same one
that shelved props): the *validated* Phase-12 signal is the structured feeds; the free-text/LLM path
is a real but forward-only seam.

PIT discipline: every accessor takes an optional ``as_of`` and filters ``event_ts <= as_of`` (with a
structural assert). For the historical walk-forward the natural as-of is the game week itself — an
injury report filed in week ``t`` is known before week-``t`` games, so ``(season, week)`` is a valid
PIT key even where the finer ``date_modified`` stamp is missing on older rows.
"""

from __future__ import annotations

import pandas as pd

NEWS_TYPES = ("injury_status", "depth_change", "headline")

# report_status → a severity in [0, 1] (how much the designation threatens this week's
# availability).
# "Out"/"Doubtful"/"IR" are near-certain misses; "Questionable" is a coin flip skewed to playing;
# "Probable"/"Full" practice is noise. Calibrated against realized play rates in 12.3.
STATUS_SEVERITY: dict[str, float] = {
    "Out": 1.0, "Injured Reserve": 1.0, "IR": 1.0, "Doubtful": 0.75,
    "Questionable": 0.35, "Probable": 0.10,
}

_UNIFIED_COLS = ["player_key", "season", "week", "team", "pos", "news_type", "status",
                 "detail", "magnitude", "event_ts", "text"]


def _seasons_clause(seasons) -> str:
    if seasons is None:
        return ""
    vals = ", ".join(str(int(s)) for s in seasons)
    return f" AND season IN ({vals})"


# ------------------------------------------------------------------------------------------------
# injury-report events (historical, PIT, native gsis) — the load-bearing structured feed
# ------------------------------------------------------------------------------------------------
def injury_events(con, seasons=None, as_of=None, statuses=None) -> pd.DataFrame:
    """Official injury-report designations as a clean event stream (one row per player-week report).

    ``player_key`` = ``gsis_id``; ``status`` = ``report_status``
    (Out/Doubtful/Questionable/Probable);
    ``detail`` = the primary injury text; ``magnitude`` = :data:`STATUS_SEVERITY`; ``event_ts`` =
    ``date_modified`` (the PIT stamp, coalesced to the week where missing). Restrict to ``statuses``
    (default: the four designations that carry signal — a blank status is a listed-but-cleared row).
    ``as_of`` filters ``event_ts <= as_of`` with a structural PIT assert.
    """
    statuses = tuple(statuses) if statuses is not None else tuple(STATUS_SEVERITY)
    status_list = ", ".join(f"'{s}'" for s in statuses)
    df = con.execute(
        f"""
        SELECT gsis_id AS player_key, season, week, team, position AS pos,
               report_status AS status, report_primary_injury AS detail,
               practice_status, date_modified
        FROM injuries
        WHERE gsis_id IS NOT NULL AND report_status IN ({status_list}){_seasons_clause(seasons)}
        """
    ).df()
    if df.empty:
        return pd.DataFrame(columns=_UNIFIED_COLS)
    df["season"] = df["season"].astype(int)
    df["week"] = df["week"].astype(int)
    df["news_type"] = "injury_status"
    df["magnitude"] = df["status"].map(STATUS_SEVERITY).fillna(0.0)
    # event_ts: the report's own timestamp when present, else the game week (both are PIT-valid for
    # a
    # week-t decision — reports are filed before week-t games).
    ts = pd.to_datetime(df["date_modified"], errors="coerce", utc=True)
    df["event_ts"] = ts
    df["text"] = (df["status"].astype(str) + " — " + df["detail"].fillna("").astype(str)).str.strip(
        " —")
    # dedupe: the latest report per (player, season, week) is the one in force that week.
    df = (df.sort_values(["player_key", "season", "week", "event_ts"])
          .drop_duplicates(["player_key", "season", "week"], keep="last"))
    out = df.reindex(columns=_UNIFIED_COLS)
    return _apply_asof(out, as_of)


# ------------------------------------------------------------------------------------------------
# depth-chart change events (historical, PIT, native gsis)
# ------------------------------------------------------------------------------------------------
def depth_events(con, seasons=None, as_of=None, min_delta: int = 1) -> pd.DataFrame:
    """Week-over-week depth-chart rank changes as role-change events.

    From the week-grain ``depth_charts`` (2014–24; ``depth_team`` = the rank, 1 = starter). A row is
    emitted when a player's rank changes by ``>= min_delta`` from the prior week at the same team/
    position: ``magnitude`` = the signed change **in "toward starter" units** (+ = promotion, − =
    demotion), ``status`` = ``"promotion"``/``"demotion"``. PIT: keyed to the week it takes effect.
    """
    df = con.execute(
        f"""
        SELECT gsis_id AS player_key, season, week, club_code AS team, position AS pos,
               CAST(depth_team AS INTEGER) AS depth_rank
        FROM depth_charts
        WHERE gsis_id IS NOT NULL AND depth_team IS NOT NULL
          AND week IS NOT NULL AND season IS NOT NULL{_seasons_clause(seasons)}
        """
    ).df()
    if df.empty:
        return pd.DataFrame(columns=_UNIFIED_COLS)
    df["season"] = df["season"].astype(int)
    df["week"] = df["week"].astype(int)
    df = (df.sort_values(["player_key", "season", "week"])
          .drop_duplicates(["player_key", "season", "week"], keep="last"))
    df["prev_rank"] = df.groupby(["player_key", "season"])["depth_rank"].shift(1)
    df = df.dropna(subset=["prev_rank"])
    # a smaller depth_team is a better role, so promotion = prev_rank − depth_rank > 0.
    df["magnitude"] = (df["prev_rank"] - df["depth_rank"]).astype(float)
    df = df[df["magnitude"].abs() >= float(min_delta)]
    df["news_type"] = "depth_change"
    df["status"] = df["magnitude"].map(lambda m: "promotion" if m > 0 else "demotion")
    df["detail"] = ("rank " + df["prev_rank"].astype(int).astype(str) + "→"
                    + df["depth_rank"].astype(int).astype(str))
    df["event_ts"] = pd.NaT
    df["text"] = df["status"] + " (" + df["detail"] + ")"
    out = df.reindex(columns=_UNIFIED_COLS)
    return _apply_asof(out, as_of)


# ------------------------------------------------------------------------------------------------
# headline events (forward-capture only; player identity resolved by the 12.2 extractor)
# ------------------------------------------------------------------------------------------------
def headline_events(con, as_of=None) -> pd.DataFrame:
    """Beat-writer RSS headlines as raw-text events (``news_raw``), ``player_key`` unresolved.

    Forward-capture only (news can't be backfilled), so these never enter the historical event study
    — they are the free-text substrate the LLM extractor (12.2) turns into structured signal for
    live/forward use. ``event_ts`` = the item's published time (coalesced to ``captured_at``).
    """
    from fantasy_quant.data import db
    if not db.table_exists(con, "news_raw"):
        return pd.DataFrame(columns=_UNIFIED_COLS)
    df = con.execute(
        "SELECT source, title, summary, published, captured_at FROM news_raw"
    ).df()
    if df.empty:
        return pd.DataFrame(columns=_UNIFIED_COLS)
    df["player_key"] = pd.NA
    df["season"] = pd.NA
    df["week"] = pd.NA
    df["team"] = pd.NA
    df["pos"] = pd.NA
    df["news_type"] = "headline"
    df["status"] = df["source"]
    df["detail"] = df["summary"]
    df["magnitude"] = pd.NA
    pub = pd.to_datetime(df["published"], errors="coerce", utc=True)
    cap = pd.to_datetime(df["captured_at"], errors="coerce", utc=True)
    df["event_ts"] = pub.fillna(cap)
    df["text"] = (df["title"].fillna("").astype(str) + ". "
                  + df["summary"].fillna("").astype(str)).str.strip(". ")
    out = df.reindex(columns=_UNIFIED_COLS)
    return _apply_asof(out, as_of)


# ------------------------------------------------------------------------------------------------
# the unified stream + the PIT guard
# ------------------------------------------------------------------------------------------------
def _apply_asof(df: pd.DataFrame, as_of) -> pd.DataFrame:
    """Filter to events at-or-before ``as_of`` (on ``event_ts``) and assert no future leak. Rows
    with
    a missing ``event_ts`` (older injury reports, depth changes) are kept — their ``(season, week)``
    PIT key is enforced by the caller's season/week windowing, not a wall-clock timestamp."""
    if as_of is None:
        return df.reset_index(drop=True)
    as_of_ts = pd.to_datetime(as_of, utc=True)
    ts = pd.to_datetime(df["event_ts"], errors="coerce", utc=True)
    keep = ts.isna() | (ts <= as_of_ts)
    out = df[keep].reset_index(drop=True)
    future = ts[keep].dropna()
    assert future.empty or future.max() <= as_of_ts, "PIT violation: news event after as_of"
    return out


def news_stream(con, seasons=None, as_of=None, *, include_headlines: bool = False) -> pd.DataFrame:
    """The unified, timestamped, deduped news-event stream (the 12.1 deliverable).

    Concatenates the two historical structured feeds (injury_status + depth_change); headlines are
    included only when ``include_headlines=True`` (forward/live use) since they carry no historical
    PIT key. Sorted by ``(season, week, news_type)``.
    """
    parts = [injury_events(con, seasons, as_of), depth_events(con, seasons, as_of)]
    if include_headlines:
        parts.append(headline_events(con, as_of))
    out = pd.concat([p for p in parts if not p.empty], ignore_index=True) if any(
        not p.empty for p in parts) else pd.DataFrame(columns=_UNIFIED_COLS)
    if out.empty:
        return out
    return out.sort_values(["season", "week", "news_type"], na_position="last").reset_index(
        drop=True)
