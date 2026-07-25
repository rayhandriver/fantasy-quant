"""Phase 16.5 — the live situation-change event board for the upcoming draft.

**Why this is derived and not researched.** The first cut of `reference/situation_events_2026.csv`
was hand-assembled from offseason trackers: 9 rows. That method is unsound, and the failure is
measurable — it missed **16 of the 23** team changes among draftable skill players, including
A.J. Brown PHI->NE at ADP 13.6 (a first-round pick), and it carried Tyler Allgeier at ADP 167 while
omitting the two highest-ADP players in the league, both of whom have a changed backfield. A tracker
recap surfaces whatever was newsworthy; it is not a frame over the players you will actually draft.

Almost all of it is free. Three tables already in the warehouse pin down a player's situation:

* ``adp_snapshots`` (2026, FFC) — the draftable board *and* each player's current team,
* ``consensus_projections`` (2026) — an **independent** second read on that same team assignment,
* ``weekly`` (2025) — the prior-season team of record, and prior-season workload.

Diffing them enumerates the event board exhaustively at a stated ADP cutoff. What is *not* derivable
is the **mechanism** (trade vs free agency vs draft) and the terms — those stay hand-annotated, and
:func:`merge_annotations` carries them onto the derived rows so verified research is never lost.

**The ADP-board `team` column is safe here, and only here.** ``adp/panel.py`` documents that it is
unusable for historical seasons — the backfilled boards are contaminated with an end-of-season
crosswalk (the Sep-1 2022 board lists McCaffrey on SF, a mid-season trade not yet made at draft
time). That contamination is *retroactive*. A snapshot of a season that has not started cannot
encode a trade that has not happened, so for the target season the board's team is a live roster
read. :func:`board` still cross-checks it against ``consensus_projections`` and fails loudly on any
disagreement rather than trusting one source.

Grain: **one row per player**, never per team. A coaching change is a *column*
(``new_play_caller``), folded in from 16.3b at player grain, so the file stays one shape and 16.6
can render it directly.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from fantasy_quant.adp.panel import _canon_team
from fantasy_quant.situation import coaches as C

REFERENCE = Path(__file__).resolve().parents[3] / "reference"
EVENTS_CSV = REFERENCE / "situation_events_2026.csv"

#: The frozen column order of the event board.
SCHEMA: tuple[str, ...] = ("player", "position", "team", "prev_team", "event_type", "mechanism",
                           "adp", "new_play_caller", "play_caller", "new_qb", "qb", "arrivals",
                           "departures", "evidence", "confidence", "notes")

#: Skill positions that can carry a fantasy situation change.
POSITIONS: tuple[str, ...] = ("QB", "RB", "WR", "TE")

#: Default ADP cutoff — a 12-team league drafts ~192 players, so the top 200 skill players are
#: "everyone you could plausibly draft". Widening it only adds rows nobody rosters.
MAX_ADP: float = 200.0

#: 2025 workload (carries + targets + pass attempts) above which a player who has *left* the
#: draftable board counts as a real departure rather than roster noise.
MATERIAL_LOAD: int = 100

_EVENT_TYPES = ("team_change", "new_to_league", "room_change", "context_only")
_MECHANISMS = ("trade", "free_agent", "draft", "return", "unknown")
_CONFIDENCE = ("high", "med", "low")


# ------------------------------------------------------------------------------------------------
# the three free reads
# ------------------------------------------------------------------------------------------------
def board(con, season: int, max_adp: float = MAX_ADP) -> pd.DataFrame:
    """The draftable skill board for `season`: player, position, current team, ADP.

    Dual-sourced. The ADP board's team is cross-checked against ``consensus_projections``; a
    disagreement raises, because a wrong team silently corrupts every downstream event.
    """
    adp = con.execute("""
        SELECT gsis_id, any_value(name) AS player, any_value(position) AS position,
               any_value(team) AS team, avg(adp) AS adp
        FROM adp_snapshots
        WHERE season = ? AND source = 'ffc' AND scoring = 'ppr' AND teams = 12
          AND snapshot_date = (SELECT max(snapshot_date) FROM adp_snapshots
                               WHERE season = ? AND source = 'ffc')
          AND gsis_id IS NOT NULL
        GROUP BY gsis_id
    """, [season, season]).df()
    if adp.empty:
        raise ValueError(f"no {season} FFC ADP board — 16.5 needs a live board to frame the events")
    adp["team"] = _canon_team(adp["team"])
    adp = adp[adp["position"].isin(POSITIONS)]

    proj = con.execute("""
        SELECT gsis_id, any_value(team) AS team_proj FROM consensus_projections
        WHERE season = ? AND gsis_id IS NOT NULL GROUP BY gsis_id
    """, [season]).df()
    if not proj.empty:
        proj["team_proj"] = _canon_team(proj["team_proj"])
        chk = adp.merge(proj, on="gsis_id", how="inner")
        bad = chk[chk["team"] != chk["team_proj"]]
        if len(bad):
            rows = ", ".join(f"{r.player} adp={r.team} proj={r.team_proj}"
                             for r in bad.head(5).itertuples())
            raise ValueError(f"team disagreement between the ADP board and consensus projections "
                             f"on {len(bad)} players: {rows}")

    out = adp[adp["adp"] <= max_adp].sort_values("adp").reset_index(drop=True)
    return out[["gsis_id", "player", "position", "team", "adp"]]


def prior_team(con, season: int) -> pd.DataFrame:
    """Each player's team of record in `season - 1` — the team he logged the most weeks for, so a
    mid-season trade resolves to the dominant side. Absent ⇒ he did not play (rookie, or missed the
    whole season)."""
    w = con.execute("""
        SELECT gsis_id, recent_team AS prev_team, count(*) AS wk FROM weekly
        WHERE season = ? AND gsis_id IS NOT NULL AND recent_team IS NOT NULL
        GROUP BY gsis_id, recent_team
    """, [season - 1]).df()
    if w.empty:
        return pd.DataFrame(columns=["gsis_id", "prev_team", "wk"])
    w = w.sort_values(["gsis_id", "wk"], ascending=[True, False]).drop_duplicates("gsis_id")
    w["prev_team"] = _canon_team(w["prev_team"])
    return w[["gsis_id", "prev_team", "wk"]]


def departed_producers(con, season: int, on_board: set[str],
                       material_load: int = MATERIAL_LOAD) -> pd.DataFrame:
    """Players who carried a **material** `season - 1` workload but are not on the `season` board at
    all — retired, unsigned, or fallen off. They vacate opportunity exactly like a traded player
    does, so the room they left is a real situation change for whoever remains."""
    p = con.execute("""
        SELECT gsis_id, any_value(player_display_name) AS player, any_value(position) AS position,
               any_value(recent_team) AS prev_team,
               sum(coalesce(carries, 0) + coalesce(targets, 0) + coalesce(attempts, 0)) AS load
        FROM weekly
        WHERE season = ? AND season_type = 'REG' AND gsis_id IS NOT NULL
        GROUP BY gsis_id
    """, [season - 1]).df()
    if p.empty:
        return pd.DataFrame(columns=["gsis_id", "player", "position", "prev_team", "load"])
    p["prev_team"] = _canon_team(p["prev_team"])
    p = p[p["position"].isin(POSITIONS) & (p["load"] >= material_load)]
    return p[~p["gsis_id"].isin(on_board)].sort_values("load", ascending=False)


# ------------------------------------------------------------------------------------------------
# the event board
# ------------------------------------------------------------------------------------------------
def _room_churn(moves: pd.DataFrame, gone: pd.DataFrame) -> tuple[dict, dict]:
    """Per ``(team, position)`` room: who arrived, and who left. Keyed on the *canonical* room so an
    incumbent can be matched to the churn around him."""
    arrivals: dict[tuple[str, str], list[str]] = {}
    departures: dict[tuple[str, str], list[str]] = {}
    for r in moves.itertuples():
        key_to = (r.team, r.position)
        if r.event_type == "team_change":
            arrivals.setdefault(key_to, []).append(r.player)
            departures.setdefault((r.prev_team, r.position), []).append(r.player)
        elif r.event_type == "new_to_league":
            arrivals.setdefault(key_to, []).append(r.player)
    for r in gone.itertuples():
        departures.setdefault((r.prev_team, r.position), []).append(r.player)
    return arrivals, departures


def build_event_board(con, season: int, max_adp: float = MAX_ADP,
                      coaches: pd.DataFrame | None = None) -> pd.DataFrame:
    """The full derived event board for `season`, one row per affected draftable player.

    Four event types, in priority order — a player gets the strongest one that applies:

    ``team_change``      he is on a different team than last season
    ``new_to_league``    he is on the board with no prior-season snaps (rookie, or missed the year)
    ``room_change``      he stayed put, but a same-position draftable player arrived or left
    ``play_caller_only`` nothing moved around him, but his team has a new play-caller (16.3b)

    A player with none of the four is not an event and is not on the board.
    """
    bd = board(con, season, max_adp)
    prev = prior_team(con, season)
    df = bd.merge(prev, on="gsis_id", how="left")

    moved = df["prev_team"].notna() & (df["prev_team"] != df["team"])
    fresh = df["prev_team"].isna()
    df["event_type"] = pd.NA
    df.loc[moved, "event_type"] = "team_change"
    df.loc[fresh, "event_type"] = "new_to_league"

    gone = departed_producers(con, season, on_board=set(_all_board_ids(con, season)))
    arrivals, departures = _room_churn(df[moved | fresh], gone)

    # a player's churn is always the room he will play in this season — for a mover that is the
    # room he arrived into, not the one he left
    key = list(zip(df["team"], df["position"], strict=False))
    df["arrivals"] = [", ".join(sorted(set(arrivals.get(k, [])) - {p}))
                      for k, p in zip(key, df["player"], strict=False)]
    df["departures"] = [", ".join(sorted(set(departures.get(k, [])) - {p}))
                        for k, p in zip(key, df["player"], strict=False)]

    # --- fold in 16.3b's play-caller regimes at player grain ------------------------------------
    cdf = C.load_coaches() if coaches is None else coaches
    tgt = cdf[cdf["season"] == season]
    pc = dict(zip(tgt["team"], tgt["play_caller"], strict=False))
    src = C.fingerprint_source(cdf, season, C.load_lineage())
    new_pc = set(src.loc[src["is_new_regime"], "team"])
    df["play_caller"] = df["team"].map(pc).fillna("(unknown)")
    df["new_play_caller"] = df["team"].isin(new_pc).astype(int)

    # --- and the offense-wide read a same-position room cannot see: a changed quarterback ---------
    qbs = new_qb_map(con, season)
    sq = starting_qb(con, season)
    df["qb"] = df["team"].map(dict(zip(sq["team"], sq["qb"], strict=False))).fillna("(unsettled)")
    df["new_qb"] = df["team"].isin(qbs).astype(int)

    churned = (df["arrivals"] != "") | (df["departures"] != "")
    context = (df["new_play_caller"] == 1) | (df["new_qb"] == 1)
    df.loc[df["event_type"].isna() & churned, "event_type"] = "room_change"
    df.loc[df["event_type"].isna() & context, "event_type"] = "context_only"
    df = df[df["event_type"].notna()].copy()

    df["mechanism"] = "unknown"
    df.loc[df["event_type"] == "new_to_league", "mechanism"] = "draft"
    df["evidence"] = "derived"
    df["confidence"] = "high"
    df["notes"] = ""
    df["adp"] = df["adp"].round(1)
    df = df.sort_values(["adp", "player"]).reset_index(drop=True)
    return df[list(SCHEMA)]


def starting_qb(con, season: int, bd: pd.DataFrame | None = None) -> pd.DataFrame:
    """Projected QB1 per team for `season` — the lowest-ADP quarterback the board puts on that team.

    The target season has not been played, so the usual "most pass attempts" definition is
    unavailable; draft-market consensus is the only PIT read on who opens under center, and it is a
    good one. For a *past* season this falls back to attempts, matching ``adp/panel._starting_qb``.
    """
    if season <= _last_played_season(con):
        a = con.execute("""
            SELECT recent_team AS team, any_value(player_display_name) AS qb, sum(attempts) AS att
            FROM weekly WHERE season = ? AND gsis_id IS NOT NULL AND recent_team IS NOT NULL
            GROUP BY recent_team, gsis_id HAVING sum(attempts) > 0
        """, [season]).df()
        a["team"] = _canon_team(a["team"])
        return (a.sort_values(["team", "att"], ascending=[True, False])
                 .drop_duplicates("team")[["team", "qb"]].reset_index(drop=True))
    q = (board(con, season, max_adp=float("inf")) if bd is None else bd)
    q = q[q["position"] == "QB"].sort_values("adp").drop_duplicates("team")
    return q.rename(columns={"player": "qb"})[["team", "qb"]].reset_index(drop=True)


def _last_played_season(con) -> int:
    return int(con.execute("SELECT max(season) FROM weekly").fetchone()[0])


def new_qb_map(con, season: int) -> dict[str, str]:
    """Per canonical team: the incoming QB1's name, for teams whose quarterback changed. A changed
    quarterback moves every pass-catcher and every game script on that roster, so it is an
    offense-wide situation change that same-position room churn cannot see.

    Two deliberate calls:

    * A team with **no** quarterback anywhere on the season's ADP board maps to ``(unsettled)`` and
      counts as changed. Those are not missing data to skip over — they are the *most* uncertain
      rooms in the league (2026: ARI, ATL, CLE, NYJ, PIT), and defaulting them to "no change" would
      be exactly backwards.
    * The prior-season baseline is the attempts leader, matching ``adp/panel._starting_qb`` so this
      flag means the same thing here as in 16.1. It therefore fires when an incumbent *missed time*
      and a backup led attempts (2026 WAS: Jayden Daniels vs a Marcus Mariota baseline). That is a
      known false positive, left visible rather than silently patched — 16.6 shows the QB names.
    """
    cur = starting_qb(con, season).rename(columns={"qb": "cur"})
    prev = starting_qb(con, season - 1).rename(columns={"qb": "prev"})
    t = cur.merge(prev, on="team", how="outer")
    t["cur"] = t["cur"].fillna("(unsettled)")
    changed = t["prev"].notna() & (t["cur"] != t["prev"])
    return dict(zip(t.loc[changed, "team"], t.loc[changed, "cur"], strict=False))


def _all_board_ids(con, season: int) -> list[str]:
    """Every gsis_id on the season's ADP board at any depth — used to decide who has *left* the
    league's draftable pool, which must not be limited by the top-N cutoff."""
    return con.execute("""
        SELECT DISTINCT gsis_id FROM adp_snapshots
        WHERE season = ? AND gsis_id IS NOT NULL
    """, [season]).df()["gsis_id"].tolist()


def merge_annotations(derived: pd.DataFrame,
                      annotations: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Carry hand-researched `mechanism` / `notes` / `confidence` onto the derived rows.

    The derived half owns *who* and *where* (it is dual-sourced and exhaustive); the annotation half
    owns *how* and *how sure* (trade terms, contract, role expectation) — the part no feed carries.
    An annotation for a player the derivation did not surface is kept and marked, never dropped:
    that disagreement is itself a finding.
    """
    out = derived.copy()
    ann = annotations.set_index("player")
    for col in ("mechanism", "notes", "confidence"):
        if col not in ann.columns:
            continue
        hit = out["player"].map(ann[col])
        out[col] = hit.where(hit.notna() & (hit.astype("string").str.strip() != ""), out[col])
    out.loc[out["player"].isin(ann.index), "evidence"] = "derived+web"
    orphan = [p for p in ann.index if p not in set(out["player"])]
    return out, orphan


def load_events(path: Path | str = EVENTS_CSV) -> pd.DataFrame:
    """Read the event board, skipping the `#` header commentary."""
    df = pd.read_csv(path, comment="#", dtype={"notes": "string"}, keep_default_na=False,
                     na_values=[""])
    return df


def assert_events_schema(df: pd.DataFrame) -> None:
    """Structural gate: exact columns, known enums, no missing identity fields."""
    if tuple(df.columns) != SCHEMA:
        raise ValueError(f"event board schema drift: {tuple(df.columns)} != {SCHEMA}")
    for col in ("player", "position", "team", "event_type"):
        if df[col].isna().any():
            raise ValueError(f"{col} is required on every row")
    bad_pos = set(df["position"]) - set(POSITIONS)
    if bad_pos:
        raise ValueError(f"non-skill positions on the board: {sorted(bad_pos)}")
    bad_evt = set(df["event_type"]) - set(_EVENT_TYPES)
    if bad_evt:
        raise ValueError(f"unknown event_type: {sorted(bad_evt)}")
    bad_mech = set(df["mechanism"].dropna()) - set(_MECHANISMS)
    if bad_mech:
        raise ValueError(f"unknown mechanism: {sorted(bad_mech)}")
    bad_conf = set(df["confidence"].dropna()) - set(_CONFIDENCE)
    if bad_conf:
        raise ValueError(f"unknown confidence: {sorted(bad_conf)}")
    if df["player"].duplicated().any():
        dup = sorted(df.loc[df["player"].duplicated(), "player"])
        raise ValueError(f"a player appears twice on the board: {dup}")
    tc = df[df["event_type"] == "team_change"]
    if tc["prev_team"].isna().any():
        raise ValueError("a team_change row has no prev_team")
    if (tc["prev_team"] == tc["team"]).any():
        raise ValueError("a team_change row where prev_team == team")


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    """Row counts by event type and evidence — the shape of the board at a glance."""
    return (df.groupby(["event_type", "evidence"], as_index=False)
              .agg(n=("player", "size"), best_adp=("adp", "min"))
              .sort_values(["event_type", "evidence"]))
