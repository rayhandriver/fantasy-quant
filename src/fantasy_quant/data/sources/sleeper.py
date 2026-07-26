"""Step 0.10 — Sleeper draft ingest (pick-by-pick draft data): the corpus intake.

**Source.** Sleeper's public read-only v1 API (``https://api.sleeper.app/v1``) — no auth, no key
(https://docs.sleeper.com; stay under 1000 calls/min). Two ways into the draft corpus:
  - **explicit ``draft_ids``** — the id is in a draft-board URL (``sleeper.com/draft/nfl/<id>``);
    this is how *mock* drafts are ingested (mocks are not attached to the user endpoint), and
  - **discovery from a ``username``/``user_id``** — walk ``user -> leagues -> drafts`` so a batch of
    real leagues folds in with one call. Unlike solo-vs-bots mocks (``picked_by`` empty, one entry
    in ``draft_order``), real-league picks populate ``picked_by`` = a **persistent manager
    identity** across drafts — the signal the Phase-11 behavioral opponent model needs.

**Identity.** A pick's ``player_id`` is a Sleeper id; join to ``gsis`` via the nflverse
``player_ids.sleeper_id`` crosswalk (stored **DOUBLE** -> cast to an int-string; ``gsis`` is
sometimes **whitespace-padded** -> strip). Measured on the drafted cohort: **QB/RB/WR/TE = 100%**,
K ~80%, and team **DEF** carry the *team abbreviation* as their id (no gsis) -> bridged to a
``dst_team`` key (the :mod:`~fantasy_quant.backtest.scoring` DST convention). Unmatched **skill**
players are logged, not dropped.

**Deliverables** (DuckDB, gitignored store):
  - ``sleeper_drafts``      — one row per draft (format, status, the human's slot, source).
  - ``sleeper_draft_picks`` — the pick-by-pick list, gsis-joined.
Derived on demand:
  - :func:`build_mock_adp` — an ADP board in the **``adp_snapshots`` contract** (``source``
    ``'sleeper_mock'``), so :func:`~fantasy_quant.data.sources.adp.adp_asof` and the draft
    simulator (:mod:`fantasy_quant.draft.simulator`) consume it **unchanged**.
  - :func:`build_tendencies` — per-slot (mocks) / per-manager (real leagues) positional cadence +
    reach-vs-ADP: a proof-of-concept on bot mocks, the seed of the Phase-11 model.

Pure helpers (``parse_*``, ``crosswalk_picks_to_gsis``, ``build_*``) operate on dicts/DataFrames
and are unit-tested offline against a saved payload fixture; the ``fetch_*``/``ingest_*`` wrappers
add the network + DuckDB.
"""

from __future__ import annotations

import logging
import time

import httpx
import pandas as pd

from fantasy_quant.config import PROJECT_ROOT, RAW_DIR
from fantasy_quant.data import cache, db
from fantasy_quant.data.sources.adp import dedupe_gsis_within_snapshot

log = logging.getLogger(__name__)

BASE = "https://api.sleeper.app/v1"
HEADERS = {"User-Agent": "fantasy-quant research (contact rayhan.driver@gmail.com)"}
SLEEPER_RAW = RAW_DIR / "sleeper"
SKILL_POS = ("QB", "RB", "WR", "TE")
_DEF_POS = ("DEF", "DST")
MOCK_SOURCE = "sleeper_mock"      # bot-only mock drafts (Sleeper's algo ADP)
HUMAN_SOURCE = "sleeper_human"    # real multi-manager drafts (the ADP the opponent model wants)
# derived artifacts (ADP boards, manager profiles) use only finished pick-order drafts — abandoned
# drafts (a common crawl artifact: people quit mid-draft) and auctions would pollute ADP/reach.
_QUALITY_FILTER = "d.status = 'complete' AND d.draft_type IN ('snake', 'linear')"
# ★ ADP boards are REDRAFT-only, and carry the board's true scoring label (FFC's vocabulary, so
# `adp_asof` reads Sleeper and FFC boards interchangeably). The crawled corpus is mostly NOT
# redraft — measured 2026-07-25: of 7,399 complete human snake/linear drafts only 1,312 are PPR
# redraft, against 2,547 dynasty_2qb, 952 2qb, 861 dynasty and 610 IDP. Pooling those onto one
# board labelled 'ppr' (which is what a hardcoded `scoring="ppr"` did) prices a startup dynasty
# room and a 2QB room as if they were redraft PPR. The non-redraft drafts stay in the raw tables
# for Phase 17; they are simply not *redraft ADP*.
REDRAFT_SCORING = {"ppr": "ppr", "half_ppr": "half-ppr", "std": "standard"}
SEEDS_FILE = PROJECT_ROOT / "reference" / "sleeper_seeds.txt"
# how many past seasons a user-history crawl walks back over. 2017 is Sleeper's first NFL season,
# so this is the full reachable history — nothing is gained by starting later.
CRAWL_SEASONS = tuple(str(y) for y in range(2017, 2027))
_CRAWL_SLEEP = 0.05               # legacy per-call nap; superseded by the shared rate limiter
CRAWL_RATE = 10.0                 # calls/sec ceiling — see _RateLimiter
ARCHIVE_PAYLOADS = True           # T7 raw-payload archive; off for bulk crawls (see crawl_frontier)


class _RateLimiter:
    """Token-bucket pacing shared by every Sleeper call.

    Sleeper documents ~1000 calls/min (16.7/s) and we sit deliberately under it. A bucket rather
    than a flat ``sleep`` per call because a flat nap *adds* to response latency instead of
    absorbing it: the old fixed 0.05 s nap measured **29 calls/s** in practice, i.e. above the
    documented ceiling. Here a slow response pays for its own latency and the ceiling is real.
    Set ``rate <= 0`` to disable (tests).
    """

    def __init__(self, rate: float):
        self.rate = rate
        self._next = 0.0

    def wait(self) -> None:
        if self.rate <= 0:
            return
        now = time.monotonic()
        if now < self._next:
            time.sleep(self._next - now)
        self._next = max(now, self._next) + 1.0 / self.rate


_RATE = _RateLimiter(CRAWL_RATE)


# --------------------------------------------------------------------------------------------
# network (keyless, read-only, 404-tolerant, retry-guarded, rate-limited)
# --------------------------------------------------------------------------------------------
def _get(client: httpx.Client, path: str, *, retries: int = 3):
    """GET ``BASE+path``; return parsed JSON, ``None`` on 404, retrying transient errors.

    A **429 backs off hard** (5 s × attempt) rather than hammering: on a multi-hour crawl the
    polite thing and the effective thing coincide — the server stops answering either way."""
    last: Exception | None = None
    for attempt in range(retries):
        _RATE.wait()
        try:
            r = client.get(f"{BASE}{path}")
            if r.status_code == 404:
                return None
            if r.status_code == 429:
                log.warning("Sleeper 429 on %s — backing off", path)
                last = RuntimeError(f"rate limited: {path}")
                time.sleep(5.0 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError) as e:  # network hiccup / truncated JSON
            last = e
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"Sleeper GET failed after {retries} tries: {path}") from last


def fetch_draft(client: httpx.Client, draft_id: str) -> dict | None:
    """Draft metadata (type/status/settings/draft_order). Archives the raw JSON (T7)."""
    d = _get(client, f"/draft/{draft_id}")
    if d is not None and ARCHIVE_PAYLOADS:
        cache.archive_text(SLEEPER_RAW / "payloads", f"draft_{draft_id}",
                           _dumps(d), "json")
    return d


def fetch_picks(client: httpx.Client, draft_id: str) -> list[dict]:
    """The pick-by-pick list for a draft. Archives the raw JSON (T7)."""
    p = _get(client, f"/draft/{draft_id}/picks") or []
    if p and ARCHIVE_PAYLOADS:
        cache.archive_text(SLEEPER_RAW / "payloads", f"picks_{draft_id}", _dumps(p), "json")
    return p


def discover_draft_ids(client: httpx.Client, *, username: str | None = None,
                       user_id: str | None = None, seasons=None, sport: str = "nfl",
                       seen_leagues: set[str] | None = None) -> list[str]:
    """All draft_ids reachable from a ``username``/``user_id`` across ``seasons`` (user -> leagues
    -> drafts). Mocks won't appear here (they're not attached to the user); real leagues do.

    ``seen_leagues`` is a caller-owned set of league_ids already expanded this run. A crawl over a
    manager frontier revisits the *same* leagues constantly — the managers were discovered from
    each other's leagues in the first place — so without this the ``/league/<id>/drafts`` call is
    re-spent once per co-manager. Passing the set in (rather than caching internally) keeps the
    function's cost visible to its caller and leaves it stateless between runs."""
    if user_id is None:
        if username is None:
            return []
        user = _get(client, f"/user/{username}")
        if not user:
            log.warning("Sleeper user %r not found", username)
            return []
        user_id = user["user_id"]
    seasons = [str(s) for s in (seasons or _default_seasons(client))]
    ids: list[str] = []
    for season in seasons:
        leagues = _get(client, f"/user/{user_id}/leagues/{sport}/{season}") or []
        for lg in leagues:
            lid = str(lg.get("league_id") or "")
            if not lid or (seen_leagues is not None and lid in seen_leagues):
                continue
            if seen_leagues is not None:
                seen_leagues.add(lid)
            drafts = _get(client, f"/league/{lid}/drafts") or []
            ids.extend(str(d["draft_id"]) for d in drafts if d.get("draft_id"))
        # a user can also own drafts directly (some are exposed on this endpoint)
        udrafts = _get(client, f"/user/{user_id}/drafts/{sport}/{season}") or []
        ids.extend(str(d["draft_id"]) for d in udrafts if d.get("draft_id"))
    return list(dict.fromkeys(ids))  # de-dup, preserve order


def _default_seasons(client: httpx.Client) -> list[str]:
    st = _get(client, "/state/nfl") or {}
    yrs = [st.get("league_season"), st.get("season"), st.get("previous_season")]
    return list(dict.fromkeys(str(y) for y in yrs if y))


# --------------------------------------------------------------------------------------------
# parsing (pure)
# --------------------------------------------------------------------------------------------
def parse_draft_meta(draft: dict) -> dict:
    """One ``sleeper_drafts`` row from a raw draft object. ``draft_order`` maps user_id -> slot;
    a mock has exactly one entry (the human), so ``human_slot`` tags which seat was the user."""
    s = draft.get("settings") or {}
    m = draft.get("metadata") or {}
    order = draft.get("draft_order") or {}
    human_uid = next(iter(order), None)
    human_slot = order.get(human_uid) if human_uid else None
    league_id = draft.get("league_id")
    league_id = str(league_id) if league_id not in (None, "", "0") else None
    return {
        "draft_id": str(draft.get("draft_id")),
        "league_id": league_id,
        "season": _to_int(draft.get("season")),
        "sport": draft.get("sport"),
        "draft_type": draft.get("type"),
        "status": draft.get("status"),
        "teams": _to_int(s.get("teams")),
        "rounds": _to_int(s.get("rounds")),
        "scoring": m.get("scoring_type"),
        "start_time_ms": draft.get("start_time"),
        "human_user_id": str(human_uid) if human_uid else None,
        "human_slot": _to_int(human_slot),
        "source": "league" if league_id else "mock",
    }


def parse_picks(draft: dict, picks: list[dict]) -> pd.DataFrame:
    """The ``sleeper_draft_picks`` rows for one draft (pure). ``is_human_slot`` marks the user's
    own picks (via ``draft_order``); ``picked_by`` is empty for bot mocks, a manager id for
    real leagues."""
    meta = parse_draft_meta(draft)
    rows = []
    for p in picks:
        md = p.get("metadata") or {}
        sid = p.get("player_id")
        name = f"{md.get('first_name', '')} {md.get('last_name', '')}".strip()
        slot = _to_int(p.get("draft_slot"))
        rows.append({
            "draft_id": meta["draft_id"],
            "season": meta["season"],
            "pick_no": _to_int(p.get("pick_no")),
            "round": _to_int(p.get("round")),
            "draft_slot": slot,
            "roster_id": _to_int(p.get("roster_id")),
            "picked_by": p.get("picked_by") or None,
            "sleeper_player_id": str(sid) if sid is not None else None,
            "position": (md.get("position") or "").upper() or None,
            "player_name": name or (md.get("team") or str(sid) if sid is not None else None),
            "nfl_team": md.get("team") or None,
            "years_exp": _to_int(md.get("years_exp")),
            "is_keeper": bool(p.get("is_keeper")),
            "is_human_slot": meta["human_slot"] is not None and slot == meta["human_slot"],
        })
    return pd.DataFrame(rows)


def crosswalk_picks_to_gsis(picks: pd.DataFrame, ids: pd.DataFrame) -> pd.DataFrame:
    """Attach ``gsis_id`` to picks via the ``player_ids.sleeper_id`` crosswalk (cast DOUBLE ->
    int-string; strip whitespace-padded gsis). Team DEF (id = team abbr, no gsis) get a
    ``dst_team`` bridge key instead. Pure: pass the ``player_ids`` frame in."""
    xw: dict[str, str] = {}
    for sid, gid in ids[["sleeper_id", "gsis_id"]].itertuples(index=False):
        if sid is None or pd.isna(sid):
            continue
        g = str(gid).strip() if gid is not None and not pd.isna(gid) else ""
        if g:
            xw[str(int(sid))] = g
    out = picks.copy()
    out["gsis_id"] = out["sleeper_player_id"].map(
        lambda x: xw.get(str(x)) if x is not None else None)
    is_def = out["position"].astype(str).str.upper().isin(_DEF_POS)
    out["dst_team"] = None
    out.loc[is_def, "dst_team"] = out.loc[is_def, "sleeper_player_id"]
    return out


def skill_match_rate(picks: pd.DataFrame) -> dict:
    """gsis crosswalk coverage on the drafted **skill** cohort (QB/RB/WR/TE) + a per-position
    breakdown. The skill rate is the number the crosswalk gate asserts on."""
    pos = picks["position"].astype(str).str.upper()
    skill = picks[pos.isin(SKILL_POS)]
    per = {}
    for p in ("QB", "RB", "WR", "TE", "K", "DEF"):
        sub = picks[pos == p]
        per[p] = None if sub.empty else round(sub["gsis_id"].notna().mean(), 4)
    return {
        "skill_rows": int(len(skill)),
        "skill_match_rate": round(skill["gsis_id"].notna().mean(), 4) if len(skill) else None,
        "by_position": per,
    }


# --------------------------------------------------------------------------------------------
# derived: mock ADP board (in the adp_snapshots contract) + opponent tendencies
# --------------------------------------------------------------------------------------------
def build_mock_adp(picks: pd.DataFrame, *, snapshot_date, season: int | None = None,
                   scoring: str = "ppr", teams: int = 10, source: str = MOCK_SOURCE,
                   fmt: str = "redraft", min_drafts: int = 1) -> pd.DataFrame:
    """Aggregate pick numbers across the corpus into a board matching the ``adp_snapshots`` schema.

    Per player: ``adp`` = mean pick, ``stdev`` = sd, ``high`` = earliest (min) pick, ``low`` =
    latest (max) pick, ``times_drafted`` = drafts appeared in; ``total_drafts`` = corpus size.
    Players are keyed by ``gsis_id`` where present, else a synthetic key (DST team / sleeper id) so
    K/DST still board. Emits the exact columns :func:`adp_asof` / the simulator expect.
    """
    df = picks.copy()
    if df.empty:
        return pd.DataFrame()
    n_drafts = df["draft_id"].nunique()
    # `.astype(object)` first: a corpus slice with no DST at all round-trips `dst_team` out of
    # DuckDB as an all-NULL *numeric* column, and writing the string fallback into it raises. The
    # key is a string by construction, so make the columns hold strings before choosing between
    # them (the same all-NULL column-type drift `_upsert` reconciles on the write side).
    _gsis = df["gsis_id"].astype(object)
    _dst = df["dst_team"].astype(object)
    df["_pkey"] = _gsis.where(
        _gsis.notna(),
        _dst.where(_dst.notna(), "SLPR:" + df["sleeper_player_id"].astype(str)),
    )
    g = df.groupby("_pkey")
    board = pd.DataFrame({
        "adp": g["pick_no"].mean(),
        "stdev": g["pick_no"].std(ddof=0).fillna(0.0),
        "high": g["pick_no"].min(),
        "low": g["pick_no"].max(),
        "times_drafted": g["draft_id"].nunique(),
        "gsis_id": g["gsis_id"].first(),
        "name": g["player_name"].first(),
        "position": g["position"].first(),
        "team": g["nfl_team"].first(),
    }).reset_index(drop=True)
    board = board[board["times_drafted"] >= min_drafts].copy()
    board["season"] = int(season) if season is not None else _to_int(picks["season"].iloc[0])
    board["snapshot_date"] = pd.to_datetime(snapshot_date).date()
    board["start_date"] = None
    board["source"] = source
    board["format"] = fmt
    board["scoring"] = scoring
    board["teams"] = int(teams)
    board["ffc_player_id"] = None
    board["bye"] = None
    board["total_drafts"] = int(n_drafts)
    # de-dup any gsis collisions within the board, then rank within position (ADP-ascending).
    snap_key = ["season", "source", "format", "scoring", "teams"]
    board, _ = dedupe_gsis_within_snapshot(board, snap_key)
    board = board.sort_values("adp").reset_index(drop=True)
    board["pos_rank"] = board.groupby("position")["adp"].rank(method="first").astype(int)
    keep = [
        "season", "snapshot_date", "start_date", "source", "format", "scoring", "teams",
        "gsis_id", "ffc_player_id", "name", "position", "team", "adp", "pos_rank",
        "times_drafted", "stdev", "high", "low", "bye", "total_drafts",
    ]
    return board[keep]


def build_tendencies(picks: pd.DataFrame, adp_ref: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per-drafter positional cadence + reach-vs-ADP (the POC behavioral artifact).

    Keyed by ``picked_by`` only when ≥2 distinct managers carry it (a real multi-manager league —
    a persistent identity across drafts); otherwise by ``draft_slot``. Solo-vs-bots mocks populate
    ``picked_by`` for the human's picks *only* (bots are null), so a mock keys by slot — capturing
    all ten seats rather than collapsing the bots into one bucket. ``reach`` = board ADP − pick_no
    (positive = drafted earlier than value); with a bot-mock corpus the ADP reference is that same
    corpus, so treat the numbers as a plumbing proof-of-concept, not a fit."""
    if picks.empty:
        return pd.DataFrame()
    df = picks.copy()
    n_managers = df["picked_by"].nunique(dropna=True)
    key_col, key_type = ("picked_by", "manager") if n_managers >= 2 else ("draft_slot", "slot")
    df["reach"] = _attach_reach(df, adp_ref)  # +ve => taken earlier than ADP (a reach)
    grp = df.groupby([key_col, "position"], dropna=False)
    out = grp.agg(
        n_picked=("pick_no", "size"),
        avg_round=("round", "mean"),
        avg_reach=("reach", "mean"),
    ).reset_index().rename(columns={key_col: "drafter"})
    out.insert(0, "key_type", key_type)
    out["drafter"] = out["drafter"].astype(str)
    return out.sort_values(["drafter", "position"]).reset_index(drop=True)


# --------------------------------------------------------------------------------------------
# DuckDB wrappers (idempotent corpus growth)
# --------------------------------------------------------------------------------------------
def _upsert(con, table: str, df: pd.DataFrame, key: str = "draft_id") -> int:
    """Idempotent corpus growth: create ``table`` if absent, else keep the rows whose ``key`` isn't
    in ``df`` and rewrite the table with their union. A full rewrite (not delete-then-append) so it
    is atomic and robust to the heterogeneous corpus — schema drift *and* column-type drift
    (e.g. a nullable ``league_id`` first seen all-NULL, later a real string) reconcile cleanly."""
    if df.empty:
        return db.row_count(con, table) if db.table_exists(con, table) else 0
    if not db.table_exists(con, table):
        return db.write_df(con, table, df)
    vals = ", ".join(f"'{v}'" for v in df[key].astype(str).unique())
    old = con.execute(f'SELECT * FROM "{table}" WHERE CAST({key} AS VARCHAR) NOT IN ({vals})').df()
    old = old.drop(columns=["pulled_at"], errors="ignore")
    return db.write_df(con, table, pd.concat([old, df], ignore_index=True))


def ingest_drafts(con, draft_ids=None, *, username: str | None = None, user_id: str | None = None,
                  seasons=None, client: httpx.Client | None = None) -> dict:
    """Fetch + parse + gsis-join the given drafts (explicit ids and/or discovered from a
    user/league) and idempotently upsert ``sleeper_drafts`` + ``sleeper_draft_picks``."""
    owns = client is None
    client = client or httpx.Client(timeout=60, headers=HEADERS)
    try:
        ids = list(dict.fromkeys(str(d) for d in (draft_ids or [])))
        if username or user_id:
            ids.extend(discover_draft_ids(client, username=username, user_id=user_id,
                                          seasons=seasons))
        ids = list(dict.fromkeys(ids))
        meta_rows, pick_frames, missing = [], [], []
        for did in ids:
            draft = fetch_draft(client, did)
            picks = fetch_picks(client, did)
            if not draft or not picks:
                missing.append(did)
                continue
            pf = parse_picks(draft, picks)
            meta = parse_draft_meta(draft)
            # a real multi-manager draft (human lobby / league) carries ≥2 distinct picked_by;
            # a solo-vs-bots mock carries only the human's own id.
            meta["n_drafters"] = int(pf["picked_by"].nunique(dropna=True))
            meta["is_human"] = meta["n_drafters"] >= 2
            meta_rows.append(meta)
            pick_frames.append(pf)
    finally:
        if owns:
            client.close()

    if not pick_frames:
        return {"n_drafts": 0, "n_picks": 0, "missing": missing, "draft_ids": ids}

    ids_df = con.execute("SELECT sleeper_id, gsis_id FROM player_ids").df()
    picks_df = crosswalk_picks_to_gsis(pd.concat(pick_frames, ignore_index=True), ids_df)
    meta_df = pd.DataFrame(meta_rows)

    _upsert(con, "sleeper_drafts", meta_df)
    _upsert(con, "sleeper_draft_picks", picks_df)

    cov = skill_match_rate(picks_df)
    log_unmatched_skill(picks_df)
    return {
        "n_drafts": int(meta_df["draft_id"].nunique()),
        "n_picks": int(len(picks_df)),
        "skill_match_rate": cov["skill_match_rate"],
        "coverage_by_position": cov["by_position"],
        "missing": missing,
        "draft_ids": meta_df["draft_id"].tolist(),
    }


def log_unmatched_skill(picks: pd.DataFrame) -> pd.DataFrame:
    """Skill players (QB/RB/WR/TE) that failed the gsis crosswalk — logged, not dropped."""
    pos = picks["position"].astype(str).str.upper()
    miss = picks[pos.isin(SKILL_POS) & picks["gsis_id"].isna()]
    if len(miss):
        out = SLEEPER_RAW / "unmatched_sleeper_skill.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        miss[["draft_id", "sleeper_player_id", "player_name", "position",
              "nfl_team"]].to_csv(out, index=False)
        log.info("logged %d unmatched skill picks -> %s", len(miss), out)
    return miss


def _refresh_board(con, *, is_human: bool, source: str, season: int | None,
                   min_drafts: int = 1) -> pd.DataFrame:
    """Build ADP board(s) from the drafts matching ``is_human`` and (re)write them into
    ``adp_snapshots`` under ``source``, so ``adp_asof``/the sim use them. ADP is season-specific, so
    a **separate board per (season, scoring)** is built (the crawled corpus spans years and
    formats), each tagged with that group's modal team-count. Only **complete** snake/linear
    **redraft** drafts feed the board — abandoned drafts and auctions would pollute ADP, and
    dynasty/2QB/IDP rooms are a different market rather than noisy redraft (see
    :data:`REDRAFT_SCORING`). *(Simplification: within a season,
    drafts of different team-counts pool onto the modal-teams board; per-format split later.)*"""
    fmts = ", ".join(f"'{k}'" for k in REDRAFT_SCORING)
    picks = con.execute(
        "SELECT p.*, d.is_human, d.start_time_ms, d.teams AS draft_teams, d.scoring "
        "FROM sleeper_draft_picks p JOIN sleeper_drafts d USING (draft_id) "
        f"WHERE d.is_human = ? AND {_QUALITY_FILTER} AND d.scoring IN ({fmts})", [is_human]
    ).df()
    if season is not None:
        picks = picks[picks["season"] == season]
    picks = picks[picks["season"].notna()]
    if picks.empty:
        return pd.DataFrame()
    # one board per (season, scoring): ADP is season-specific, and half-PPR/standard rooms draft
    # pass-catchers differently enough that pooling them would blur the very thing ADP measures.
    boards = []
    for s in sorted(picks["season"].unique()):
        for sleeper_fmt, board_fmt in REDRAFT_SCORING.items():
            sp = picks[(picks["season"] == s) & (picks["scoring"] == sleeper_fmt)]
            if sp.empty:
                continue
            teams = int(sp["draft_teams"].mode().iloc[0]) if sp["draft_teams"].notna().any() else 10
            b = build_mock_adp(sp, snapshot_date=_latest_date(sp["start_time_ms"]), season=int(s),
                               scoring=board_fmt, teams=teams, source=source,
                               min_drafts=min_drafts)
            if not b.empty:
                boards.append(b)
    if not boards:
        return pd.DataFrame()
    board = pd.concat(boards, ignore_index=True)
    if db.table_exists(con, "adp_snapshots"):
        seasons = ", ".join(str(int(s)) for s in board["season"].unique())
        con.execute(f"DELETE FROM adp_snapshots WHERE source = '{source}' "
                    f"AND season IN ({seasons})")
        db.append_df(con, "adp_snapshots", board)
    else:
        db.write_df(con, "adp_snapshots", board)
    return board


def refresh_mock_adp(con, *, season: int | None = None, min_drafts: int = 1) -> pd.DataFrame:
    """The ``sleeper_mock`` board — bot-only mock drafts (Sleeper's algorithmic ADP)."""
    return _refresh_board(con, is_human=False, source=MOCK_SOURCE, season=season,
                          min_drafts=min_drafts)


def refresh_human_adp(con, *, season: int | None = None, min_drafts: int = 1) -> pd.DataFrame:
    """The ``sleeper_human`` board — real multi-manager redraft drafts (the ADP the opponent model
    wants, kept separate so bot ADP never dilutes it)."""
    return _refresh_board(con, is_human=True, source=HUMAN_SOURCE, season=season,
                          min_drafts=min_drafts)


def refresh_adp_boards(con, *, season: int | None = None, min_drafts: int = 1) -> dict:
    """Rebuild both Sleeper ADP boards (human + bot) from the current corpus."""
    human = refresh_human_adp(con, season=season, min_drafts=min_drafts)
    mock = refresh_mock_adp(con, season=season, min_drafts=min_drafts)
    return {HUMAN_SOURCE: int(len(human)), MOCK_SOURCE: int(len(mock))}


def manager_profiles(picks: pd.DataFrame) -> pd.DataFrame:
    """Per-manager behavioral seed (real ``picked_by`` only) — the Phase-11 opponent-model input.

    For each manager across all their drafts: draft count, per-position pick share, mean draft
    round, mean reach-vs-ADP (needs an ADP ref joined onto ``picks`` as ``_adp``), and their most
    picked NFL teams (a crude fandom signal). Pure: pass ``picks`` (optionally with ``_adp``)."""
    df = picks[picks["picked_by"].notna()].copy()
    if df.empty:
        return pd.DataFrame()
    if "_adp" in df.columns:
        df["reach"] = df["_adp"] - df["pick_no"]
    tot = df.groupby("picked_by")["pick_no"].size().rename("n_picks")
    ndrafts = df.groupby("picked_by")["draft_id"].nunique().rename("n_drafts")
    rows = []
    for mgr, sub in df.groupby("picked_by"):
        share = (sub["position"].value_counts(normalize=True) * 100).round(1).to_dict()
        fav = sub["nfl_team"].dropna().value_counts().head(3).index.tolist()
        rows.append({
            "manager": str(mgr),
            "n_drafts": int(ndrafts[mgr]),
            "n_picks": int(tot[mgr]),
            "avg_reach": round(float(sub["reach"].mean()), 2) if "reach" in sub else None,
            "pos_share_QB": share.get("QB", 0.0), "pos_share_RB": share.get("RB", 0.0),
            "pos_share_WR": share.get("WR", 0.0), "pos_share_TE": share.get("TE", 0.0),
            "fav_teams": ",".join(fav),
        })
    return pd.DataFrame(rows).sort_values("n_picks", ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------------------------
# corpus crawler — grow the draft corpus from usernames / participant expansion
# --------------------------------------------------------------------------------------------
def participants_from_draft(draft: dict) -> set[str]:
    """Every real user_id in a draft: ``draft_order`` keys (all seated managers) — the reliable
    source (a bot mock has one; a human lobby/league has ~10). Pure."""
    order = draft.get("draft_order") or {}
    return {str(u) for u in order if u}


def crawl_user_history(client, *, username: str | None = None, user_id: str | None = None,
                       seasons=None, sport: str = "nfl", seen_leagues=None) -> list[str]:
    """All draft_ids a user is reachable from across ``seasons`` (defaults to the redraft-history
    window). Thin wrapper over :func:`discover_draft_ids` with the multi-season default."""
    return discover_draft_ids(client, username=username, user_id=user_id,
                              seasons=seasons or CRAWL_SEASONS, sport=sport,
                              seen_leagues=seen_leagues)


def _league_members(client, league_id: str) -> tuple[list[str], list[str]]:
    """A league's draft_ids + member user_ids — the seed a public league URL gives (its
    ``league_id`` is in the URL). ``/league/<id>/drafts`` + ``/league/<id>/users`` are keyless."""
    drafts = _get(client, f"/league/{league_id}/drafts") or []
    users = _get(client, f"/league/{league_id}/users") or []
    return ([str(d["draft_id"]) for d in drafts if d.get("draft_id")],
            [str(u["user_id"]) for u in users if u.get("user_id")])


def crawl_expand(client, *, seed_usernames=None, seed_draft_ids=None, seed_league_ids=None,
                 seasons=None, max_drafts: int = 500, expand_participants: bool = True,
                 existing_ids=None, users_done=None, on_user_done=None) -> list[str]:
    """Discover a corpus of draft_ids by **iterative BFS snowball**. Seed from usernames (crawl each
    user's full league/draft history), league_ids (→ their drafts + members), and draft_ids. If
    ``expand_participants``, every *human* (multi-manager) draft found queues its seated managers,
    whose histories are crawled in turn — so one league/lobby fans out through co-managers until no
    new users remain or ``max_drafts`` is hit. Skips ``existing_ids``, rate-limited. Returns the new
    draft_ids to ingest.

    ``users_done`` pre-seeds the visited set (resume a interrupted crawl); ``on_user_done`` is
    called with each user_id as its history is finished, so the caller can persist that progress.

    **Expansion is keyed on "have we expanded this draft", not "is this draft new".** The obvious
    version — expand only when ``_add_draft`` reports a new id — silently kills the crawl on every
    re-run: the caller seeds ``existing_ids`` with the whole store, so each already-ingested draft
    reports "not new" and its participants are never queued. The frontier then collapses to
    whatever the seed file happens to hold.
    """
    seen: set[str] = {str(x) for x in (existing_ids or [])}
    found: list[str] = []
    users_todo: list[str] = []
    users_done = {str(u) for u in (users_done or ())}
    expanded: set[str] = set()

    def _add_draft(did) -> bool:
        did = str(did)
        if did and did not in seen:
            seen.add(did)
            found.append(did)
            return True
        return False

    def _queue_user(uid) -> None:
        uid = str(uid)
        if uid and uid not in users_done and uid not in users_todo:
            users_todo.append(uid)

    # ---- seeds ----
    for did in (seed_draft_ids or []):
        _add_draft(did)
    for lid in (seed_league_ids or []):
        dids, uids = _league_members(client, str(lid))
        for d in dids:
            _add_draft(d)
        for u in uids:
            _queue_user(u)
    for uname in (seed_usernames or []):
        u = _get(client, f"/user/{uname}")
        if u and u.get("user_id"):
            _queue_user(u["user_id"])

    # ---- BFS snowball: crawl a user's history, queue the participants of each human draft ----
    while users_todo and len(found) < max_drafts:
        uid = users_todo.pop(0)
        if uid in users_done:
            continue
        users_done.add(uid)
        for did in crawl_user_history(client, user_id=uid, seasons=seasons):
            _add_draft(did)
            if not expand_participants or did in expanded or len(found) >= max_drafts:
                continue
            expanded.add(did)
            draft = fetch_draft(client, did)
            if draft and len(participants_from_draft(draft)) >= 2:  # a real multi-manager draft
                for pid in participants_from_draft(draft):
                    _queue_user(pid)
        if on_user_done is not None:
            on_user_done(uid)

    return found[:max_drafts]


def load_seeds() -> dict:
    """Read ``reference/sleeper_seeds.txt`` — one token per line, ``#`` comments ignored. Tokens:
    ``league:<id>`` → league_id, ``draft:<id>`` (or a bare number) → draft_id, anything else → a
    username. Returns ``{"usernames", "draft_ids", "league_ids"}`` lists."""
    out: dict = {"usernames": [], "draft_ids": [], "league_ids": []}
    if not SEEDS_FILE.exists():
        return out
    for line in SEEDS_FILE.read_text().splitlines():
        tok = line.split("#", 1)[0].strip()
        if not tok:
            continue
        low = tok.lower()
        if low.startswith("league:"):
            out["league_ids"].append(tok.split(":", 1)[1].strip())
        elif low.startswith("draft:"):
            out["draft_ids"].append(tok.split(":", 1)[1].strip())
        elif tok.isdigit():
            out["draft_ids"].append(tok)
        else:
            out["usernames"].append(tok)
    return out


# --------------------------------------------------------------------------------------------
# resumable crawl state — a bulk crawl is a long network walk that WILL be interrupted
# --------------------------------------------------------------------------------------------
USERS_TABLE = "sleeper_crawl_users"      # user_ids whose league/draft history has been walked
QUEUE_TABLE = "sleeper_crawl_queue"      # discovered draft_ids awaiting (or past) ingest
LEAGUES_TABLE = "sleeper_crawl_leagues"  # league_ids already expanded to their drafts


def ensure_crawl_state(con) -> None:
    """Create the three resume tables if absent.

    Without them an interrupted crawl restarts from zero and re-spends the whole call budget on
    work already done — the practical reason the previous run could never be extended."""
    con.execute(f"CREATE TABLE IF NOT EXISTS {USERS_TABLE} "
                "(user_id VARCHAR PRIMARY KEY, done_at TIMESTAMP)")
    con.execute(f"CREATE TABLE IF NOT EXISTS {QUEUE_TABLE} "
                "(draft_id VARCHAR PRIMARY KEY, status VARCHAR, seen_at TIMESTAMP)")
    con.execute(f"CREATE TABLE IF NOT EXISTS {LEAGUES_TABLE} "
                "(league_id VARCHAR PRIMARY KEY, done_at TIMESTAMP)")


def crawled_leagues(con) -> set[str]:
    """league_ids already expanded to their drafts (skip re-fetching them on resume)."""
    ensure_crawl_state(con)
    return {r[0] for r in con.execute(f"SELECT league_id FROM {LEAGUES_TABLE}").fetchall()}


def mark_leagues_crawled(con, league_ids) -> None:
    ids = [str(x) for x in league_ids if x]
    if ids:
        con.executemany(f"INSERT OR REPLACE INTO {LEAGUES_TABLE} VALUES (?, ?)",
                        [(x, db.utc_now()) for x in ids])


def crawled_users(con) -> set[str]:
    """user_ids whose history has already been walked (skip them on resume)."""
    ensure_crawl_state(con)
    return {r[0] for r in con.execute(f"SELECT user_id FROM {USERS_TABLE}").fetchall()}


def mark_user_crawled(con, user_id: str) -> None:
    con.execute(f"INSERT OR REPLACE INTO {USERS_TABLE} VALUES (?, ?)",
                [str(user_id), db.utc_now()])


def enqueue_drafts(con, draft_ids) -> int:
    """Add newly discovered draft_ids to the ingest queue as ``todo`` (idempotent)."""
    ids = [str(d) for d in draft_ids if d]
    if not ids:
        return 0
    ensure_crawl_state(con)
    con.executemany(f"INSERT OR IGNORE INTO {QUEUE_TABLE} VALUES (?, 'todo', ?)",
                    [(d, db.utc_now()) for d in ids])
    return len(ids)


def queue_todo(con, limit: int | None = None) -> list[str]:
    """draft_ids still awaiting ingest."""
    ensure_crawl_state(con)
    sql = f"SELECT draft_id FROM {QUEUE_TABLE} WHERE status = 'todo'"
    if limit:
        sql += f" LIMIT {int(limit)}"
    return [r[0] for r in con.execute(sql).fetchall()]


def mark_queue(con, draft_ids, status: str) -> None:
    """Retire queue rows as ``done`` (ingested) or ``dead`` (404/empty — never retry these).

    Tracking dead ids is not bookkeeping pedantry: the previous 500-draft run spent **263 of its
    500** on ids that never resolved, so more than half the budget bought nothing and every re-run
    would have spent it again."""
    ids = [str(d) for d in draft_ids if d]
    if not ids:
        return
    con.executemany(f"UPDATE {QUEUE_TABLE} SET status = ? WHERE draft_id = ?",
                    [(status, d) for d in ids])


def seed_users_from_profiles(con) -> list[str]:
    """Every manager already observed in the corpus — **the real crawl frontier**.

    :func:`load_seeds` reads only the hand-maintained seed file (a handful of ids). The managers
    discovered by past crawls live in ``sleeper_manager_profiles`` and were never fed back in as
    seeds, so each run re-walked the same tiny neighbourhood. Ordered by picks observed, so the
    most-connected managers are walked first and an interrupted run still gets the best of it."""
    if not db.table_exists(con, "sleeper_manager_profiles"):
        return []
    return [str(r[0]) for r in con.execute(
        "SELECT manager FROM sleeper_manager_profiles ORDER BY n_picks DESC").fetchall()]


def crawl_frontier(con, *, user_ids=None, seasons=None, client: httpx.Client | None = None,
                   expand_participants: bool = False, max_users: int | None = None,
                   max_seconds: float | None = None, batch: int = 400,
                   archive_payloads: bool = False, progress_every: int = 25) -> dict:
    """Walk every frontier user's history, queueing what's new, then drain the queue in batches.

    Two persisted phases so either can be interrupted and resumed:
      1. **discover** — for each user not in ``USERS_TABLE``, list their league/draft history and
         enqueue any draft_id not already in ``sleeper_drafts``; mark the user done.
      2. **drain** — pull ``todo`` ids in ``batch``-sized chunks, ingest, retire them ``done`` or
         ``dead``. Committing per batch is what makes a 45-minute run survivable.

    ``expand_participants=False`` is the *frontier-only* crawl: walk the managers we already know
    and stop, rather than snowballing into their co-managers. ``archive_payloads`` defaults off —
    at this scale the T7 archive would be ~20k files, which is not an audit trail anyone can use.
    """
    global ARCHIVE_PAYLOADS
    ensure_crawl_state(con)
    t0 = time.monotonic()
    owns = client is None
    client = client or httpx.Client(timeout=60, headers=HEADERS)
    prev_archive, ARCHIVE_PAYLOADS = ARCHIVE_PAYLOADS, archive_payloads

    users = [str(u) for u in (user_ids if user_ids is not None else seed_users_from_profiles(con))]
    done = crawled_users(con)
    todo_users = [u for u in dict.fromkeys(users) if u not in done]
    if max_users:
        todo_users = todo_users[:max_users]

    existing = set()
    if db.table_exists(con, "sleeper_drafts"):
        existing = {r[0] for r in con.execute("SELECT draft_id FROM sleeper_drafts").fetchall()}
    known = existing | {r[0] for r in con.execute(f"SELECT draft_id FROM {QUEUE_TABLE}").fetchall()}

    seen_leagues = crawled_leagues(con)
    stats = {"users_walked": 0, "users_skipped": len(users) - len(todo_users),
             "discovered": 0, "ingested": 0, "dead": 0, "leagues_seen": len(seen_leagues),
             "stopped_early": False}
    try:
        # ---- phase 1: discovery ----
        for i, uid in enumerate(todo_users, 1):
            if max_seconds and time.monotonic() - t0 > max_seconds:
                stats["stopped_early"] = True
                log.warning("crawl_frontier: time budget hit during discovery (%d/%d users)",
                            i - 1, len(todo_users))
                break
            before_leagues = set(seen_leagues)
            found = crawl_user_history(client, user_id=uid, seasons=seasons or CRAWL_SEASONS,
                                       seen_leagues=seen_leagues)
            fresh = [d for d in found if d not in known]
            known.update(fresh)
            enqueue_drafts(con, fresh)
            mark_leagues_crawled(con, seen_leagues - before_leagues)
            if expand_participants:
                # snowball: each human draft's co-managers join the frontier for a later pass
                for did in fresh:
                    draft = fetch_draft(client, did)
                    if draft and len(participants_from_draft(draft)) >= 2:
                        for pid in participants_from_draft(draft):
                            if pid not in done and pid not in todo_users:
                                todo_users.append(pid)
            mark_user_crawled(con, uid)
            done.add(uid)
            stats["users_walked"] += 1
            stats["discovered"] += len(fresh)
            if progress_every and i % progress_every == 0:
                log.info("crawl_frontier discovery %d/%d users — %d new drafts queued",
                         i, len(todo_users), stats["discovered"])
                print(f"  discovery {i}/{len(todo_users)} users — "
                      f"{stats['discovered']} new drafts queued "
                      f"({time.monotonic() - t0:.0f}s)", flush=True)

        # ---- phase 2: drain the ingest queue in committed batches ----
        while True:
            if max_seconds and time.monotonic() - t0 > max_seconds:
                stats["stopped_early"] = True
                log.warning("crawl_frontier: time budget hit during ingest")
                break
            chunk = queue_todo(con, limit=batch)
            if not chunk:
                break
            summary = ingest_drafts(con, chunk, client=client)
            got = set(summary.get("draft_ids") or [])
            # retire the WHOLE chunk first, then promote what actually landed. Marking only the
            # ids we recognise would requeue anything unrecognised forever — an infinite loop in
            # an unattended multi-hour run, which is the one failure mode worth designing out.
            mark_queue(con, chunk, "dead")
            mark_queue(con, sorted(got), "done")
            stats["ingested"] += len(got)
            stats["dead"] += len(chunk) - len(got)
            print(f"  ingest +{len(got)} (dead {len(chunk) - len(got)}) — "
                  f"{stats['ingested']} total ({time.monotonic() - t0:.0f}s)", flush=True)
    finally:
        ARCHIVE_PAYLOADS = prev_archive
        if owns:
            client.close()

    stats["elapsed_s"] = round(time.monotonic() - t0, 1)
    stats["queue_remaining"] = len(queue_todo(con))
    stats["leagues_seen"] = len(seen_leagues)
    return stats


def crawl_and_ingest(con, *, seed_usernames=None, seed_draft_ids=None, seed_league_ids=None,
                     seasons=None, max_drafts: int = 500, expand_participants: bool = True,
                     client: httpx.Client | None = None) -> dict:
    """Crawl a corpus (seed usernames/leagues/draft_ids + participant expansion), then ingest
    whatever is new and rebuild both ADP boards + the manager profiles. The crawl step's call."""
    owns = client is None
    client = client or httpx.Client(timeout=60, headers=HEADERS)
    try:
        existing = set()
        if db.table_exists(con, "sleeper_drafts"):
            existing = {r[0] for r in con.execute("SELECT draft_id FROM sleeper_drafts").fetchall()}
        new_ids = crawl_expand(client, seed_usernames=seed_usernames, seed_draft_ids=seed_draft_ids,
                               seed_league_ids=seed_league_ids, seasons=seasons,
                               max_drafts=max_drafts, expand_participants=expand_participants,
                               existing_ids=existing)
        summary = ingest_drafts(con, new_ids, client=client) if new_ids else {
            "n_drafts": 0, "n_picks": 0}
    finally:
        if owns:
            client.close()
    boards = refresh_adp_boards(con)
    prof = build_and_store_profiles(con)
    return {"crawled_new": len(new_ids), "ingested": summary, "boards": boards,
            "manager_profiles": int(len(prof))}


def build_and_store_profiles(con) -> pd.DataFrame:
    """Compute + persist ``sleeper_manager_profiles`` from human drafts (with the human ADP board as
    the reach reference)."""
    picks = con.execute(
        "SELECT p.* FROM sleeper_draft_picks p JOIN sleeper_drafts d USING (draft_id) "
        f"WHERE d.is_human = TRUE AND {_QUALITY_FILTER}"
    ).df()
    if picks.empty:
        return pd.DataFrame()
    if db.table_exists(con, "adp_snapshots"):
        ref = con.execute(
            f"SELECT gsis_id, season, adp FROM adp_snapshots WHERE source = '{HUMAN_SOURCE}'").df()
        if not ref.empty:
            ref = ref.dropna(subset=["gsis_id"])
            on = ["gsis_id", "season"] if "season" in picks.columns else ["gsis_id"]
            ref = ref.groupby(on, as_index=False)["adp"].mean().rename(columns={"adp": "_adp"})
            picks = picks.merge(ref, on=on, how="left")
    prof = manager_profiles(picks)
    if not prof.empty:
        db.write_df(con, "sleeper_manager_profiles", prof)
    return prof


def opponent_tendencies(con, *, season: int | None = None) -> pd.DataFrame:
    """Compute + persist the POC behavioral artifact (``sleeper_tendencies``) from the store."""
    picks = con.execute("SELECT * FROM sleeper_draft_picks").df()
    if season is not None:
        picks = picks[picks["season"] == season]
    adp_ref = None
    if db.table_exists(con, "adp_snapshots"):
        adp_ref = con.execute(
            f"SELECT gsis_id, adp FROM adp_snapshots WHERE source = '{MOCK_SOURCE}'").df()
    tend = build_tendencies(picks, adp_ref)
    if not tend.empty:
        db.write_df(con, "sleeper_tendencies", tend)
    return tend


# --------------------------------------------------------------------------------------------
# small utilities
# --------------------------------------------------------------------------------------------
def _attach_reach(picks: pd.DataFrame, adp_ref: pd.DataFrame | None):
    """Per-pick reach = board ADP − pick_no (+ve = drafted earlier than value). Joins on
    ``(gsis_id, season)`` when both carry season (a board is season-specific), else ``gsis_id``;
    the ref is collapsed to one ADP per key first, so a multi-season board can't fan the join."""
    if adp_ref is None or adp_ref.empty or "gsis_id" not in adp_ref.columns:
        return pd.Series(pd.NA, index=picks.index)
    on = ["gsis_id", "season"] if "season" in adp_ref.columns and "season" in picks.columns \
        else ["gsis_id"]
    ref = (adp_ref.dropna(subset=["gsis_id"]).groupby(on, as_index=False)["adp"].mean()
           .rename(columns={"adp": "_ref_adp"}))
    merged = picks[[*on, "pick_no"]].merge(ref, on=on, how="left")
    return (merged["_ref_adp"] - merged["pick_no"]).to_numpy()


def _to_int(x):
    try:
        return int(x) if x is not None and str(x).strip() != "" else None
    except (TypeError, ValueError):
        return None


def _latest_date(ms_series):
    ms = pd.to_numeric(ms_series, errors="coerce").dropna()
    if ms.empty:
        return pd.Timestamp.utcnow().date()
    return pd.to_datetime(int(ms.max()), unit="ms").date()


def _dumps(obj) -> str:
    import json
    return json.dumps(obj, default=str)
