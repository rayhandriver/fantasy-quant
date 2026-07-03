"""Phase 0.5 — Vegas markets ingest (de-vig'd), point-in-time.

**What's free & historical (landed now):** game **spreads + totals + moneylines** via nflverse
``import_schedules`` (back to 2014+), from which we derive **implied team totals** and de-vig'd
fair win probabilities. Stored in ``game_lines``, timestamped by ``captured_at`` (= gameday; these
are closing lines — we don't get intra-week line movement from this source).

**What's paid/gated (built, key-gated):** **player props** (rec/rush/pass yds, anytime-TD) come
from the-odds-api and are **live-only** — historical prop lines are the paid gap.
``ingest_player_props`` runs only if ``ODDS_API_KEY`` is set; the parse + de-vig logic
(:func:`parse_props_payload`,
:func:`devig`) is unit-tested regardless so the machinery is ready the moment a key exists.

**Win totals:** nflverse ``import_win_totals`` is currently empty ("source in flux") → deferred.

De-vig is **proportional** by default (Shin / power-method are noted alternatives).
"""

from __future__ import annotations

import logging
import os

import numpy as np
import pandas as pd

from fantasy_quant.config import RAW_DIR
from fantasy_quant.data import cache, db

log = logging.getLogger(__name__)

DEFAULT_YEARS: list[int] = list(range(2014, 2026))
MARKETS_RAW = RAW_DIR / "markets"
ODDS_API_BASE = "https://api.the-odds-api.com/v4"


# --------------------------------------------------------------------------------------------
# odds math (pure, unit-tested)
# --------------------------------------------------------------------------------------------
def american_to_prob(odds) -> float:
    """American odds -> implied probability (includes the vig)."""
    o = float(odds)
    return 100.0 / (o + 100.0) if o > 0 else (-o) / (-o + 100.0)


def decimal_to_prob(price) -> float:
    """Decimal odds -> implied probability (includes the vig)."""
    return 1.0 / float(price)


def devig(implied_probs, method: str = "proportional") -> np.ndarray:
    """Remove the bookmaker overround so the probabilities sum to 1.

    ``proportional`` (default) scales each implied prob by 1/overround — simple and robust.
    (Shin and power methods are alternatives for asymmetric favourite-longshot bias; TODO if
    the props ever justify it.)
    """
    p = np.asarray(implied_probs, dtype=float)
    if method == "proportional":
        total = np.nansum(p)
        return p / total if total else p
    raise ValueError(f"unknown de-vig method: {method!r}")


def fair_two_way(odds_a, odds_b, to_prob=american_to_prob):
    """De-vig a two-outcome market -> (fair_a, fair_b), summing to 1 (NaN-safe, vectorized)."""
    a = pd.to_numeric(pd.Series(odds_a), errors="coerce")
    b = pd.to_numeric(pd.Series(odds_b), errors="coerce")
    ia = a.map(lambda x: american_to_prob(x) if pd.notna(x) else np.nan)
    ib = b.map(lambda x: american_to_prob(x) if pd.notna(x) else np.nan)
    if to_prob is decimal_to_prob:
        ia = a.map(lambda x: decimal_to_prob(x) if pd.notna(x) else np.nan)
        ib = b.map(lambda x: decimal_to_prob(x) if pd.notna(x) else np.nan)
    s = ia + ib
    return (ia / s).to_numpy(), (ib / s).to_numpy()


def implied_team_total(total_line, spread_line):
    """Implied team totals from a game total and home spread.

    nflverse convention: ``spread_line`` is the **home** margin (positive => home favored).
    Returns (home_implied, away_implied) = ((total+spread)/2, (total-spread)/2).
    """
    total = pd.to_numeric(pd.Series(total_line), errors="coerce")
    spread = pd.to_numeric(pd.Series(spread_line), errors="coerce")
    return ((total + spread) / 2.0).to_numpy(), ((total - spread) / 2.0).to_numpy()


# --------------------------------------------------------------------------------------------
# game lines (free, historical)  -> table `game_lines`
# --------------------------------------------------------------------------------------------
_SCHED_COLS = [
    "game_id", "season", "game_type", "week", "gameday", "home_team", "away_team",
    "spread_line", "total_line", "home_moneyline", "away_moneyline",
    "home_spread_odds", "away_spread_odds", "over_odds", "under_odds",
    "home_score", "away_score", "result", "total", "roof", "temp",
]


def _pull_schedules(years) -> pd.DataFrame:
    import nfl_data_py as nfl

    frames = []
    for y in years:
        try:
            frames.append(nfl.import_schedules([y]))
        except Exception as e:  # noqa: BLE001
            log.warning("skip schedules %d: %s", y, e)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def ingest_game_lines(con, years=DEFAULT_YEARS, refresh: bool = False) -> int:
    """Land spreads/totals/moneylines + derived implied team totals + fair win probs."""
    sched = cache.load_or_pull(
        MARKETS_RAW / "schedules.parquet",
        lambda: _pull_schedules(years),
        refresh=refresh,
    )
    df = sched[[c for c in _SCHED_COLS if c in sched.columns]].copy()
    home_itt, away_itt = implied_team_total(df["total_line"], df["spread_line"])
    df["home_implied_total"] = home_itt
    df["away_implied_total"] = away_itt
    hw, aw = fair_two_way(df["home_moneyline"], df["away_moneyline"])
    df["home_fair_winprob"] = hw
    df["away_fair_winprob"] = aw
    df["captured_at"] = pd.to_datetime(df["gameday"], errors="coerce").dt.date
    return db.write_df(con, "game_lines", df)


# --------------------------------------------------------------------------------------------
# player props (live-only, key-gated)  -> table `props`
# --------------------------------------------------------------------------------------------
def parse_props_payload(events: list, captured_at=None) -> pd.DataFrame:
    """Parse a the-odds-api v4 player-props payload into a tidy, de-vig'd frame.

    One row per (event, book, player, market): the line ``point`` plus de-vig'd Over/Under fair
    probabilities. Kept pure so it's testable without a live key.
    """
    rows = []
    for ev in events:
        eid = ev.get("id")
        commence = ev.get("commence_time")
        for bk in ev.get("bookmakers", []):
            book = bk.get("key")
            cap = captured_at or bk.get("last_update") or commence
            for mk in bk.get("markets", []):
                market = mk.get("key")
                # group the market's outcomes by (player, line) -> {Over, Under} prices
                sides: dict[tuple, dict] = {}
                for oc in mk.get("outcomes", []):
                    key = (oc.get("description"), oc.get("point"))
                    sides.setdefault(key, {})[str(oc.get("name", "")).lower()] = oc.get("price")
                for (player, point), pr in sides.items():
                    over_p, under_p = pr.get("over"), pr.get("under")
                    fair_over = np.nan
                    if over_p is not None and under_p is not None:
                        fo, _ = fair_two_way([over_p], [under_p], to_prob=decimal_to_prob)
                        fair_over = float(fo[0])
                    rows.append({
                        "event_id": eid, "book": book, "captured_at": cap,
                        "player": player, "market": market, "line": point,
                        "over_price": over_p, "under_price": under_p,
                        "fair_over_prob": fair_over,
                    })
    return pd.DataFrame(rows)


def ingest_player_props(con, markets=("player_reception_yds", "player_rush_yds",
                                      "player_pass_yds", "player_anytime_td"),
                        refresh: bool = False) -> int:
    """Live player props via the-odds-api. No-op (logs) unless ``ODDS_API_KEY`` is set."""
    key = os.getenv("ODDS_API_KEY")
    if not key:
        log.warning(
            "ODDS_API_KEY not set -> skipping player-props pull (live-only; historical props are "
            "the paid gap). `props` table not created. See data/README.md / PLAN.md."
        )
        return 0
    import httpx

    MARKETS_RAW.mkdir(parents=True, exist_ok=True)
    events_url = f"{ODDS_API_BASE}/sports/americanfootball_nfl/events"
    evs = httpx.get(events_url, params={"apiKey": key}, timeout=30).json()
    all_rows = []
    for ev in evs:
        url = f"{ODDS_API_BASE}/sports/americanfootball_nfl/events/{ev['id']}/odds"
        r = httpx.get(url, params={"apiKey": key, "regions": "us",
                                   "markets": ",".join(markets), "oddsFormat": "decimal"},
                      timeout=30)
        if r.status_code == 200:
            all_rows.append(parse_props_payload([r.json()]))
    props = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
    if props.empty:
        return 0
    return db.write_df(con, "props", props)


# --------------------------------------------------------------------------------------------
# PIT accessor + checks
# --------------------------------------------------------------------------------------------
def odds_asof(con, as_of, season: int | None = None) -> pd.DataFrame:
    """Game lines known **on or before** ``as_of`` (PIT). Asserts no future-dated row escapes."""
    as_of_d = pd.to_datetime(as_of).date()
    q = "SELECT * FROM game_lines WHERE captured_at <= ?"
    params: list = [as_of_d]
    if season is not None:
        q += " AND season = ?"
        params.append(season)
    df = con.execute(q, params).df()
    if not df.empty:
        assert pd.to_datetime(df["captured_at"]).max() <= pd.Timestamp(as_of_d), \
            "PIT violation: odds_asof returned a future-dated line"
    return df


def implied_total_sanity(con) -> dict:
    """Implied team totals should sit in a sane football range (~17–30 typical)."""
    row = con.execute(
        """
        SELECT MIN(v), quantile_cont(v, 0.5), MAX(v),
               AVG(CASE WHEN v BETWEEN 10 AND 40 THEN 1.0 ELSE 0.0 END)
        FROM (
            SELECT home_implied_total AS v FROM game_lines WHERE home_implied_total IS NOT NULL
            UNION ALL
            SELECT away_implied_total FROM game_lines WHERE away_implied_total IS NOT NULL
        )
        """
    ).fetchone()
    return {"min": row[0], "median": row[1], "max": row[2], "frac_in_10_40": row[3]}
