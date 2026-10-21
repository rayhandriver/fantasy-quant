"""Write the team books to ``site/data/`` — the only thing the static site reads.

Layout::

    site/data/index.json                 teams, seasons + their status, the metric registry
    site/data/{season}/{TEAM}.json       one book per team-season (comps attached)
    site/data/league/{season}.json       every team's value + rank per metric (strip plots, comps)
    site/data/trends/{TEAM}.json         the team's series across every exported season
    site/data/carry/{season}.json        what a live season needs from the store but cannot read
                                         from the releases: roster construction and team meta

Two writers, one layout:

* :func:`export_history` runs locally against the project store and writes the completed seasons
  plus the live season's carry file.
* :func:`export_live` needs **no store**. It rebuilds the live season from the nflverse releases
  (:mod:`~fantasy_quant.teambook.inseason`), reads the carry file and the completed seasons'
  league files from disk, and rewrites only the live season, the trends and the index. That is
  what the weekly CI job runs.

★ **Comps are drawn from completed seasons only.** A 2024 book's nearest neighbours must not
change because 2026 gained a week, and a six-week sample is not a season to be compared *to*. The
live season's own books are matched *against* the completed seasons.

★ **Trends are a function of the league files**, so both writers produce them the same way and a
historical book's Trends tab still shows the live season's point.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from fantasy_quant.config import PROJECT_ROOT
from fantasy_quant.teambook import build as B
from fantasy_quant.teambook import inseason as I
from fantasy_quant.teambook import metrics as M
from fantasy_quant.teambook import schema as S

SITE_DATA = PROJECT_ROOT / "site" / "data"
LIVE_SEASON = 2026
HISTORY = tuple(range(M.FIRST_SEASON, LIVE_SEASON))

#: Significant digits kept in a book (display) and in a league file (z-scores for comps).
BOOK_DIGITS, LEAGUE_DIGITS = 4, 6
#: Uncompressed size a book must stay under; Pages gzips, so the wire size is a fraction of this.
MAX_BOOK_BYTES = 80_000


# --- serialization -----------------------------------------------------------------------------
def compact(obj, digits: int = BOOK_DIGITS):
    """Round every float to ``digits`` significant figures; NaN/inf become null; numpy → python."""
    if isinstance(obj, dict):
        return {str(k): compact(v, digits) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [compact(v, digits) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (float, np.floating)):
        x = float(obj)
        if not math.isfinite(x):
            return None
        return float(f"{x:.{digits}g}")
    return obj


def write_json(path: Path, obj) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
    path.write_text(text)
    return len(text.encode())


def read_json(path: Path):
    return json.loads(path.read_text())


# --- league files ------------------------------------------------------------------------------
def league_record(result: dict) -> dict:
    """One season's context in the shape the site and the live export both read."""
    status = next(iter(result["books"].values()))["status"]
    metrics = {}
    for key, c in result["context"].items():
        metrics[key] = {k: c[k] for k in ("mean", "sd", "median", "n", "min", "max")}
        metrics[key]["values"] = c["values"]
        metrics[key]["rank"] = {t: int(r) for t, r in c["rank"].items()}
    return compact({"season": result["season"], "status": status, "metrics": metrics},
                   LEAGUE_DIGITS)


def context_from_league(rec: dict) -> dict[str, dict]:
    """Rebuild :func:`build.league_context`'s shape (incl. z) from a league file."""
    ctx = {}
    for key, c in rec["metrics"].items():
        sd = c["sd"]
        ctx[key] = {**c, "z": {t: ((v - c["mean"]) / sd if sd else None)
                               for t, v in c["values"].items()}}
    return ctx


def read_contexts(out: Path, seasons) -> B.Contexts:
    found = {}
    for s in seasons:
        path = out / "league" / f"{s}.json"
        if path.exists():
            found[int(s)] = context_from_league(read_json(path))
    return found


# --- books -------------------------------------------------------------------------------------
def write_books(out: Path, result: dict, found_comps: dict) -> dict[str, int]:
    """Guard and write one season's books; return each book's size in bytes."""
    S.assert_season_sane(result["books"])
    sizes = {}
    for team, book in result["books"].items():
        book = {**book, "comps": found_comps.get((result["season"], team), {})}
        book.pop("trends", None)
        sizes[team] = write_json(out / str(result["season"]) / f"{team}.json", compact(book))
    worst = max(sizes, key=sizes.get)
    if sizes[worst] > MAX_BOOK_BYTES:
        raise S.BookError(f"{worst} {result['season']}: {sizes[worst]} bytes > {MAX_BOOK_BYTES}")
    return sizes


def write_trends(out: Path) -> int:
    seasons = sorted(int(p.stem) for p in (out / "league").glob("*.json"))
    trends = B.team_trends(read_contexts(out, seasons))
    for team, series in trends.items():
        write_json(out / "trends" / f"{team}.json", compact(series))
    return len(trends)


def write_index(out: Path, *, participation_published: bool | None = None) -> dict:
    """The site's entry point: teams, seasons (newest first) with their status, the registry."""
    carry = read_json(out / "carry" / f"{LIVE_SEASON}.json")
    seasons = []
    for path in sorted((out / "league").glob("*.json"), reverse=True):
        status = read_json(path)["status"]
        seasons.append({"season": int(path.stem), **status})
    live = next((s for s in seasons if s["season"] == LIVE_SEASON), None)
    if live is not None and participation_published is not None:
        live["participation_published"] = participation_published
    index = {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "live_season": LIVE_SEASON,
        "teams": carry["meta"],
        "seasons": seasons,
        "registry": M.registry_records(),
        "sources": {
            M.PBP: "nflverse play by play",
            M.FTN: "FTN charting through nflverse",
            M.PARTICIPATION: "nflverse participation data",
            M.CONSTRUCTION: "nflverse rosters, contracts and draft picks",
        },
    }
    write_json(out / "index.json", index)
    return index


# --- the two writers ---------------------------------------------------------------------------
def export_history(con, seasons=HISTORY, out: Path = SITE_DATA) -> dict:
    """Completed seasons from the store, plus the carry file the live export will need."""
    meta = B.team_meta(con)
    for team in meta.values():
        team.pop("logo", None)  # no third-party logos on the site; colours carry the identity
    results = {s: B.build_season_books(con, s, meta=meta) for s in seasons}
    contexts = {s: r["context"] for s, r in results.items()}
    found = B.comps(contexts, {s: list(r["books"]) for s, r in results.items()},
                    pool=set(seasons))
    sizes = {}
    for s, r in results.items():
        write_json(out / "league" / f"{s}.json", league_record(r))
        sizes[s] = write_books(out, r, found)
    construction = B.construction_frame(con, LIVE_SEASON)
    write_json(out / "carry" / f"{LIVE_SEASON}.json", compact({
        "season": LIVE_SEASON, "meta": meta,
        "construction": construction.to_dict("records"),
        "note": "Roster construction is read from the project store; continuity needs the "
                "season's snaps and fills in at the next full export.",
    }, LEAGUE_DIGITS))
    n_trends = write_trends(out)
    write_index(out)
    return {"seasons": list(seasons), "books": sum(len(v) for v in sizes.values()),
            "max_book_bytes": max(max(v.values()) for v in sizes.values()),
            "median_book_bytes": int(np.median([b for v in sizes.values() for b in v.values()])),
            "trend_files": n_trends}


def export_live(season: int = LIVE_SEASON, out: Path = SITE_DATA, *, con=None,
                refresh: bool = True) -> dict:
    """The live season, with no store: releases + the carry file + the committed league files."""
    carry = read_json(out / "carry" / f"{season}.json")
    construction = pd.DataFrame(carry["construction"])
    result = I.build_live_season(season, con=con, construction=construction,
                                 meta=carry["meta"], refresh=refresh)
    history = read_contexts(out, [s for s in HISTORY if s != season])
    contexts = {**history, season: result["context"]}
    found = B.comps(contexts, {season: list(result["books"])}, pool=set(history))
    write_json(out / "league" / f"{season}.json", league_record(result))
    sizes = write_books(out, result, found)
    write_trends(out)
    published = I.participation_published(season) if refresh else None
    write_index(out, participation_published=published)
    status = next(iter(result["books"].values()))["status"]
    return {"season": season, "books": len(sizes), "through_week": status["through_week"],
            "complete": status["complete"], "max_book_bytes": max(sizes.values()),
            "participation_published": published}
