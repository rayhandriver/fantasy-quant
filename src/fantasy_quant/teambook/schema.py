"""The team book's output guard — the analogue of every other gate in this repo.

``assert_book_sane`` runs on every book before it is written. It fails on an impossible value
rather than letting the site draw one: a share above 1, a rank outside 1..n, a metric reported
below its own floor, or a family the status block says is missing that nonetheless has numbers.
"""

from __future__ import annotations

import math

from fantasy_quant.teambook import metrics as M

N_TEAMS = 32
REQUIRED = ("team", "season", "status", "meta", "coaching", "metrics", "traits", "players",
            "weekly")


class BookError(AssertionError):
    pass


def _fail(book: dict, msg: str) -> None:
    raise BookError(f"{book.get('team')} {book.get('season')}: {msg}")


def assert_book_sane(book: dict) -> None:
    for key in REQUIRED:
        if key not in book:
            _fail(book, f"missing section {key!r}")
    season = book["season"]
    missing = book["status"]["unavailable"]
    for key, cell in book["metrics"].items():
        m = M.BY_KEY.get(key)
        if m is None:
            _fail(book, f"unregistered metric {key!r}")
        v = cell["v"]
        if v is None or (isinstance(v, float) and not math.isfinite(v)):
            _fail(book, f"{key} carries a non-finite value; absent metrics are omitted, not NaN")
        if season < m.floor:
            _fail(book, f"{key} reported in {season}, below its {m.floor} floor")
        if m.source in missing:
            _fail(book, f"{key} reported although {m.source} is marked unavailable")
        if m.fmt == "pct" and not (-1e-9 <= v <= 1 + 1e-9):
            _fail(book, f"{key} = {v} is not a share")
        if not 1 <= cell["rank"] <= cell["n"] <= N_TEAMS:
            _fail(book, f"{key} rank {cell['rank']} of {cell['n']}")
        if not 0 < cell["pct"] <= 1:
            _fail(book, f"{key} percentile {cell['pct']}")
    rec = book["meta"].get("record")
    if rec is not None and rec["w"] + rec["l"] + rec["t"] != book["meta"]["games"]:
        _fail(book, "record does not sum to games played")
    for side in ("offense", "defense"):
        for row in book["players"][side]:
            share = row.get("snap_share")
            if share is not None and not 0 <= share <= 1 + 1e-9:
                _fail(book, f"{row.get('name')} snap share {share}")


def assert_season_sane(books: dict[str, dict]) -> None:
    """A season is 32 sane books with one status block between them."""
    if len(books) != N_TEAMS:
        raise BookError(f"{len(books)} teams in a season, expected {N_TEAMS}")
    statuses = {repr(sorted(b["status"]["unavailable"])) for b in books.values()}
    if len(statuses) != 1:
        raise BookError(f"teams disagree on which families are available: {statuses}")
    for book in books.values():
        assert_book_sane(book)
