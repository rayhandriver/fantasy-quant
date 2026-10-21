"""Assemble team books: one season's metric frame, its league context, and a book per team.

Pipeline, per season::

    season_frame(con, season)            team × every registry metric (NULL where a family
                                          is absent)
      → league_context(frame)            rank · percentile · z · median, within the season
      → build_season_books(...)          one dict per team: meta, coaching, metrics, traits,
                                          players, weekly
    attach_cross_season(books_by_season) comps (most similar team-seasons) + trends, which need
                                          every season at once

★ **Rank means "best" for a polar metric and "most" for a tendency.** EPA allowed ranks 1st at the
lowest value; 12-personnel share ranks 1st at the highest. A tendency is not good or bad, so its
rank only says where the team sits.

★ **A z-score is never filled.** A metric that is NULL below its floor has a NULL z, and the
similarity search compares two team-seasons only on the metrics *both* have — a 2026 defense, which
has no coverage shells yet, is matched on what it does have rather than on zeros.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from fantasy_quant.data.teams import canon_team
from fantasy_quant.situation import coaches as off_coaches
from fantasy_quant.situation import defense_coaches as def_coaches
from fantasy_quant.situation.scheme_panel import weekly_aggregate_sql
from fantasy_quant.teambook import metrics as M
from fantasy_quant.teambook import pbp_family as pf

#: Trait thresholds: a metric is notable when it is top/bottom-3 or this many sd from the mean.
TRAIT_Z = 1.5
TRAIT_EDGE = 3
TRAITS_PER_SIDE = {"offense": 5, "defense": 5, "special": 2}

#: Similarity: how many comps, the fewest shared scheme metrics a comparison may rest on, and the
#: share of the team's *own* metrics a candidate must also have. Without the share a candidate
#: from before FTN charting is compared on fewer, noisier dimensions — and the minimum of noisier
#: distances is systematically smaller, so pre-2022 seasons would crowd out the like-for-like.
N_COMPS = 5
MIN_SHARED = {"offense": 8, "defense": 4}
MIN_SHARED_FRAC = 0.8

PARTICIPATION_KEYS = M.keys(M.PARTICIPATION)
CONSTRUCTION_KEYS = M.keys(M.CONSTRUCTION)


# --- the season frame --------------------------------------------------------------------------
def reg_weeks(con, season: int) -> int:
    return int(con.execute(
        f"select max(week) from schedules where season = {int(season)} and game_type = 'REG'"
    ).fetchone()[0])


def pressure_rate(con, season: int) -> pd.DataFrame:
    """Pressure on dropbacks, straight from the play file.

    ⚠ The panel's ``pressure_rate`` is **1.0 for every team from 2023** (T57). The break map
    registered ``was_pressure = False`` as the 2023+ non-pass sentinel and the panel drops it on
    every row — but on a *dropback* False is the real answer, so excluding it leaves only the
    pressured plays. The dropback filter is what separates a sentinel from a negative here.
    """
    return con.execute(f"""
        select {pf.canon('b.defteam')} as team,
               avg(case when p.was_pressure then 1.0 else 0.0 end) as pressure_rate
        from participation p
        join {pf.reg_pbp(season)} b using (game_id, play_id)
        where b.qb_dropback = 1 and b.play_type in ('pass', 'run') and b.defteam is not null
          and p.was_pressure is not null
        group by 1
    """).df()


def participation_frame(con, season: int) -> pd.DataFrame:
    """The participation family for one season, regular season only, from the frozen panel."""
    where = f"season = {int(season)} and week <= {reg_weeks(con, season)}"
    agg = con.execute(weekly_aggregate_sql(where)).df()
    agg = agg.drop(columns="pressure_rate").merge(pressure_rate(con, season), on="team",
                                                  how="left")
    return agg[["team", *[k for k in PARTICIPATION_KEYS if k in agg.columns]]]


def construction_frame(con, season: int) -> pd.DataFrame:
    df = con.execute(
        f"select team, {', '.join(CONSTRUCTION_KEYS)} from team_construction_season "
        f"where season = {int(season)}"
    ).df()
    df["team"] = canon_team(df["team"]).astype(str)
    return df


def season_frame(con, season: int, *, participation: bool = True,
                 construction: pd.DataFrame | bool | None = True) -> pd.DataFrame:
    """Team × every registry metric for one season. Missing families are NULL columns.

    ``participation=False`` is the live-season shape. ``construction`` may be a frame supplied
    by the caller (the in-season path carries it from the last full export), ``True`` to read it
    from the store, or ``None`` to leave it NULL.
    """
    frame = pf.offense(con, season).merge(pf.defense(con, season), on="team", how="outer")
    frame = frame.merge(pf.special(con, season).drop(columns="head_coach"), on="team",
                        how="left")
    if participation:
        frame = frame.merge(participation_frame(con, season), on="team", how="left")
    if construction is True:
        construction = construction_frame(con, season)
    if isinstance(construction, pd.DataFrame) and not construction.empty:
        frame = frame.merge(construction[["team", *CONSTRUCTION_KEYS]], on="team", how="left")
    for key in M.BY_KEY:
        if key not in frame.columns:
            frame[key] = np.nan
        elif season < M.BY_KEY[key].floor or season > (M.BY_KEY[key].ceiling or season):
            frame[key] = np.nan  # outside its seasons a metric does not exist (never 0)
    frame.insert(0, "season", int(season))
    return frame.sort_values("team").reset_index(drop=True)


# --- league context ----------------------------------------------------------------------------
def league_context(frame: pd.DataFrame) -> dict[str, dict]:
    """Per metric: mean, sd, median, and each team's rank / percentile / z."""
    out: dict[str, dict] = {}
    for key, m in M.BY_KEY.items():
        col = frame.set_index("team")[key].astype(float)
        vals = col.dropna()
        if vals.empty:
            continue
        mean, sd = float(vals.mean()), float(vals.std(ddof=1)) if len(vals) > 1 else 0.0
        ascending = m.polarity < 0  # rank 1 = lowest only when lower is better
        rank = vals.rank(ascending=ascending, method="min").astype(int)
        pct = vals.rank(pct=True, method="average")
        out[key] = {
            "mean": mean, "sd": sd, "median": float(vals.median()), "n": int(len(vals)),
            "min": float(vals.min()), "max": float(vals.max()),
            "values": {t: float(v) for t, v in vals.items()},
            "rank": rank.to_dict(), "pct": pct.to_dict(),
            "z": {t: ((v - mean) / sd if sd > 0 else None) for t, v in vals.items()},
        }
    return out


# --- traits ------------------------------------------------------------------------------------
def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _phrase(m: M.Metric, rank: int, n: int, z: float) -> str:
    """``"Play-action rate: 2nd-highest in the league"`` — label first, so it always reads."""
    if m.polarity == 0:
        high = z >= 0
        r = rank if high else n - rank + 1
        word = "highest" if high else "lowest"
    else:
        good = rank <= n / 2
        r = rank if good else n - rank + 1
        word = "best" if good else "worst"
    return f"{m.label}: {word if r == 1 else _ordinal(r) + '-' + word} in the league"


def traits(team: str, ctx: dict[str, dict]) -> list[dict]:
    """The metrics where a team sits furthest from the league, as structured, templated lines."""
    rows = []
    for key, c in ctx.items():
        m = M.BY_KEY[key]
        if m.side not in TRAITS_PER_SIDE or team not in c["values"]:
            continue
        z, rank, n = c["z"].get(team), c["rank"][team], c["n"]
        if z is None:
            continue
        if abs(z) >= TRAIT_Z or rank <= TRAIT_EDGE or rank > n - TRAIT_EDGE:
            rows.append({"key": key, "side": m.side, "rank": int(rank), "n": n, "z": float(z),
                         "value": c["values"][team], "median": c["median"],
                         "text": _phrase(m, rank, n, z)})
    out = []
    for side, cap in TRAITS_PER_SIDE.items():
        mine = sorted((r for r in rows if r["side"] == side), key=lambda r: -abs(r["z"]))
        out.extend(mine[:cap])
    return out


# --- coaching ----------------------------------------------------------------------------------
def _clean(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    return v


def coaching_table(season: int) -> dict[str, dict]:
    off = off_coaches.load_coaches()
    dfn = def_coaches.load_defense_coaches()
    lin = pd.concat([off_coaches.load_lineage().assign(side="offense"),
                     def_coaches.load_defense_lineage().assign(side="defense")])
    for df in (off, dfn, lin):
        df["team"] = canon_team(df["team"]).astype(str)
    out: dict[str, dict] = {}
    for _, r in off[off["season"] == season].iterrows():
        out.setdefault(r["team"], {})["offense"] = {
            "head_coach": _clean(r["head_coach"]),
            "coordinator": _clean(r["offensive_coordinator"]),
            "play_caller": _clean(r["play_caller"]), "hc_calls": bool(r["hc_calls_plays"]),
            "notes": _clean(r["notes"]), "confidence": _clean(r["confidence"])}
    for _, r in dfn[dfn["season"] == season].iterrows():
        out.setdefault(r["team"], {})["defense"] = {
            "head_coach": _clean(r["head_coach"]),
            "coordinator": _clean(r["defensive_coordinator"]),
            "play_caller": _clean(r["play_caller"]), "hc_calls": bool(r["hc_calls_defense"]),
            "notes": _clean(r["notes"]), "confidence": _clean(r["confidence"])}
    for _, r in lin[lin["season"] == season].iterrows():
        out.setdefault(r["team"], {}).setdefault("lineage", []).append({
            "side": r["side"], "play_caller": _clean(r["play_caller"]),
            "mentor": _clean(r["mentor"]), "learned_at": _clean(r["learned_at"]),
            "seasons": _clean(r["learned_seasons"]), "role": _clean(r["role"])})
    return out


# --- players -----------------------------------------------------------------------------------
OFF_PLAYER_COLS = ("gsis_id", "name", "position", "games", "off_snaps", "snap_share", "targets",
                   "target_share", "receptions", "rec_yds", "rec_td", "air_yards",
                   "air_yards_share", "adot", "carries", "carry_share", "rush_yds", "rush_td",
                   "rz_targets", "rz_carries", "pass_att", "pass_yds", "pass_td", "ints",
                   "ppr_points", "ppr_per_game")
DEF_PLAYER_COLS = ("gsis_id", "name", "position", "games", "def_snaps", "snap_share", "sacks",
                   "qb_hits", "tfl", "ints", "passes_defended")
#: How deep each roster table goes. A team book describes the players who carry the snaps.
MAX_OFF_PLAYERS, MAX_DEF_PLAYERS = 18, 24


def personnel_target_shares(con, season: int) -> pd.DataFrame:
    """Participation extra: each receiver's share of the team's targets in 11 / 12 / 13."""
    return con.execute(f"""
        with w as (
            select gsis_id, team, sum(targets_p11) as t11, sum(targets_p12) as t12,
                   sum(targets_p13) as t13
            from offense_player_week
            where season = {int(season)} and week <= {reg_weeks(con, season)}
            group by 1, 2
        )
        select gsis_id, team,
               t11 / nullif(sum(t11) over (partition by team), 0) as tgt_share_p11,
               t12 / nullif(sum(t12) over (partition by team), 0) as tgt_share_p12,
               t13 / nullif(sum(t13) over (partition by team), 0) as tgt_share_p13
        from w
    """).df()


def package_snaps(con, season: int) -> pd.DataFrame:
    """Participation extra: each defender's share of the team's base / nickel / dime snaps."""
    return con.execute(f"""
        with w as (
            select gsis_id, team, sum(snaps_base) as b, sum(snaps_nickel) as n,
                   sum(snaps_dime) as d
            from defense_player_week
            where season = {int(season)} and week <= {reg_weeks(con, season)}
            group by 1, 2
        ), t as (
            select team, max(b) as tb, max(n) as tn, max(d) as td from w group by 1
        )
        select gsis_id, team, b / nullif(tb, 0) as base_share,
               n / nullif(tn, 0) as nickel_share, d / nullif(td, 0) as dime_share
        from w join t using (team)
    """).df()


def _records(df: pd.DataFrame, cols) -> list[dict]:
    keep = [c for c in cols if c in df.columns]
    return [{k: _clean(v) for k, v in row.items()} for row in df[keep].to_dict("records")]


def player_tables(con, season: int, participation: bool) -> dict[str, pd.DataFrame]:
    off = pf.offense_players(con, season)
    dfn = pf.defense_players(con, season)
    if participation:
        off = off.merge(personnel_target_shares(con, season), on=["gsis_id", "team"], how="left")
        dfn = dfn.merge(package_snaps(con, season), on=["gsis_id", "team"], how="left")
    return {"offense": off, "defense": dfn}


# --- the books ---------------------------------------------------------------------------------
def team_meta(con) -> dict[str, dict]:
    df = con.execute("select * from teams_meta").df()
    df["team_abbr"] = canon_team(df["team_abbr"]).astype(str)
    out = {}
    for _, r in df.drop_duplicates("team_abbr").iterrows():
        out[r["team_abbr"]] = {"name": r["team_name"], "nick": r["team_nick"],
                               "conference": r["team_conf"], "division": r["team_division"],
                               "color": r["team_color"], "color2": r["team_color2"],
                               "logo": r["team_logo_espn"]}
    return out


def unavailable_reasons(season: int, participation: bool, has_construction: bool) -> dict:
    out = {}
    if season < M.BY_KEY["motion_rate"].floor:
        out[M.FTN] = f"FTN charting begins in {M.BY_KEY['motion_rate'].floor}."
    if not participation:
        out[M.PARTICIPATION] = ("Personnel groupings, formations, defensive fronts, coverage and "
                                "pressure come from nflverse's participation data, which is "
                                "published a few months after the season ends.")
    if not has_construction:
        out[M.CONSTRUCTION] = "Roster construction is not built for this season yet."
    return out


def build_season_books(con, season: int, *, participation: bool = True,
                       construction: pd.DataFrame | bool | None = True,
                       meta: dict[str, dict] | None = None) -> dict:
    """Every team's book for one season, plus the league context they were ranked against."""
    frame = season_frame(con, season, participation=participation, construction=construction)
    ctx = league_context(frame)
    recs = pf.records(con, season).set_index("team")
    weekly = pf.weekly_series(con, season)
    players = player_tables(con, season, participation)
    coaching = coaching_table(season)
    meta = meta if meta is not None else team_meta(con)
    has_construction = frame[CONSTRUCTION_KEYS].notna().any().any()
    missing = unavailable_reasons(season, participation, bool(has_construction))
    through = int(recs["through_week"].max()) if recs["through_week"].notna().any() else 0
    complete = through >= reg_weeks(con, season)

    books = {}
    for team in frame["team"]:
        rec = recs.loc[team] if team in recs.index else None
        metrics = {}
        for key, c in ctx.items():
            if team in c["values"]:
                metrics[key] = {"v": c["values"][team], "rank": int(c["rank"][team]),
                                "n": c["n"], "pct": float(c["pct"][team]),
                                "z": c["z"][team], "median": c["median"]}
        off = players["offense"][players["offense"]["team"] == team].head(MAX_OFF_PLAYERS)
        dfn = players["defense"][players["defense"]["team"] == team].head(MAX_DEF_PLAYERS)
        books[team] = {
            "team": team, "season": int(season),
            "status": {"complete": bool(complete), "through_week": through,
                       "participation": bool(participation), "unavailable": missing},
            "meta": {**meta.get(team, {}),
                     "record": None if rec is None else {
                         "w": int(rec["wins"]), "l": int(rec["losses"]), "t": int(rec["ties"])},
                     "games": None if rec is None else int(rec["games_played"]),
                     "points_for": None if rec is None else _clean(rec["points_for"]),
                     "points_against": None if rec is None else _clean(rec["points_against"]),
                     "bye_weeks": [] if rec is None else [int(w) for w in rec["bye_weeks"]]},
            "coaching": coaching.get(team, {}),
            "metrics": metrics,
            "traits": traits(team, ctx),
            "players": {
                "offense": _records(off, OFF_PLAYER_COLS + ("tgt_share_p11", "tgt_share_p12",
                                                            "tgt_share_p13")),
                "defense": _records(dfn, DEF_PLAYER_COLS + ("base_share", "nickel_share",
                                                            "dime_share")),
            },
            "weekly": _records(weekly[weekly["team"] == team].drop(columns="team"),
                               [c for c in weekly.columns if c != "team"]),
        }
    return {"season": int(season), "frame": frame, "context": ctx, "books": books}


# --- cross-season: comps and trends --------------------------------------------------------------
#: A context per season is all the cross-season pieces need, so the live export can rebuild them
#: from the committed league files without the store.
Contexts = dict[int, dict[str, dict]]


def z_matrix(contexts: Contexts, side: str) -> pd.DataFrame:
    keys = [m.key for m in M.REGISTRY if m.scheme and m.side == side]
    rows = []
    for season, ctx in contexts.items():
        teams = sorted({t for c in ctx.values() for t in c["values"]})
        for team in teams:
            rows.append({"season": season, "team": team,
                         **{k: ctx.get(k, {}).get("z", {}).get(team) for k in keys}})
    return pd.DataFrame(rows).set_index(["season", "team"]).astype(float)


def similar(zmat: pd.DataFrame, season: int, team: str, side: str,
            n: int = N_COMPS, pool: set[int] | None = None) -> list[dict]:
    """Nearest other-team seasons by RMS z-distance over the scheme metrics both have.

    ``pool`` restricts the candidates to those seasons — the export draws comps from completed
    seasons only, so a book's comps do not churn as the live season gains a week.
    """
    if (season, team) not in zmat.index:
        return []
    me = zmat.loc[(season, team)]
    others = zmat.drop(index=[i for i in zmat.index
                              if i[1] == team or (pool is not None and i[0] not in pool)])
    both = others.notna() & me.notna().values
    shared = both.sum(axis=1)
    diff2 = ((others - me.values) ** 2).where(both)
    dist = np.sqrt(diff2.sum(axis=1) / shared.replace(0, np.nan))
    ok = (shared >= MIN_SHARED[side]) & (shared >= MIN_SHARED_FRAC * me.notna().sum())
    best = dist[ok].sort_values().head(n)
    return [{"season": int(s), "team": t, "distance": float(d), "shared": int(shared[(s, t)])}
            for (s, t), d in best.items()]


def comps(contexts: Contexts, targets: dict[int, list[str]],
          pool: set[int] | None = None) -> dict[tuple[int, str], dict]:
    """``{(season, team): {"offense": [...], "defense": [...]}}`` for every target team-season."""
    zmats = {side: z_matrix(contexts, side) for side in ("offense", "defense")}
    callers = {}
    for season in contexts:
        for team, c in coaching_table(season).items():
            callers[(season, team)] = {side: c.get(side, {}).get("play_caller")
                                       for side in ("offense", "defense")}
    out = {}
    for season, teams in targets.items():
        for team in teams:
            book_comps = {}
            for side, zm in zmats.items():
                rows = similar(zm, season, team, side, pool=pool)
                for r in rows:
                    r["play_caller"] = callers.get((r["season"], r["team"]), {}).get(side)
                book_comps[side] = rows
            out[(season, team)] = book_comps
    return out


def team_trends(contexts: Contexts) -> dict[str, dict[str, list]]:
    """``{team: {metric: [[season, value, league median, rank, n], ...]}}``, seasons ascending."""
    out: dict[str, dict[str, list]] = {}
    for season in sorted(contexts):
        for key, c in contexts[season].items():
            for team, v in c["values"].items():
                out.setdefault(team, {}).setdefault(key, []).append(
                    [season, v, c["median"], int(c["rank"][team]), c["n"]])
    return out


def attach_cross_season(seasons: dict[int, dict], pool: set[int] | None = None) -> None:
    """Add ``comps`` and ``trends`` to every book, in place."""
    contexts = {s: v["context"] for s, v in seasons.items()}
    found = comps(contexts, {s: list(v["books"]) for s, v in seasons.items()}, pool=pool)
    trends = team_trends(contexts)
    for season, s in seasons.items():
        for team, book in s["books"].items():
            book["comps"] = found[(season, team)]
            book["trends"] = trends.get(team, {})
