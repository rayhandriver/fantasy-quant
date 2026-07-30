"""Phase 1.1 — the league scoring engine (raw stats -> fantasy points under a ruleset).

The first brick of the backtest harness: turn a player-week's counting stats into fantasy
points so every downstream method is scored on the *same* league rules. The offensive path is
validated against nflverse's own ``fantasy_points_ppr`` (the reconstruction must match to
rounding — the done-criterion). Kickers and team defenses aren't in the offensive ``weekly``
table, so their weekly points are **derived from play-by-play** (``pbp``) + final scores
(``game_lines``) — the added scope from the full 9-starter league lineup (QB/2RB/2WR/TE/FLEX+K+DST).

Design: the arithmetic lives in **pure, unit-tested functions** (``score_offense``,
``kick_play_points``, ``pa_tier_points``, ``score_dst``); thin DB wrappers (``weekly_points``,
``kicker_weekly_points``, ``dst_weekly_points``) just query and delegate. Rules are a pydantic
``RuleSet`` so half-PPR / TE-premium / custom leagues are a config change, not a code change.
"""

from __future__ import annotations

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from fantasy_quant.data.sources.adp import normalize_name


# --------------------------------------------------------------------------------------------
# the ruleset (pydantic — parametrized so non-standard leagues are a config change)
# --------------------------------------------------------------------------------------------
class _Rules(BaseModel):
    """Base for every scoring-rule block. ``extra="forbid"`` is the point: 17.2 chose a **bounded**
    field set over an open ``{stat: value}`` map precisely so a misspelled setting raises at
    construction instead of scoring 0.0 for a whole season. Silently ignoring an unknown key is the
    worst available behaviour here — it looks like it worked."""
    model_config = ConfigDict(extra="forbid")


class OffenseRules(_Rules):
    """Per-stat weights. Defaults reproduce nflverse ``fantasy_points_ppr`` exactly (full-PPR,
    4-pt pass TD, -2 INT, -2 fumble-lost) so the reconstruction can be asserted against it."""
    pass_yd: float = 0.04          # 1 pt / 25 passing yards
    pass_td: float = 4.0
    interception: float = -2.0
    rush_yd: float = 0.1
    rush_td: float = 6.0
    rec: float = 1.0               # full-PPR (set 0.0 standard, 0.5 half-PPR)
    rec_yd: float = 0.1
    rec_td: float = 6.0
    st_td: float = 6.0             # return TDs credited via weekly.special_teams_tds
    two_pt: float = 2.0
    fumble_lost: float = -2.0
    # -- 17.2 custom scoring. All default to 0.0, so the lockbox-validated full-PPR ruleset is
    #    byte-identical and every one of these is opt-in. --------------------------------------
    #: Extra points per reception for **tight ends only** (TE-premium leagues, typically 0.5).
    te_rec_bonus: float = 0.0
    #: Flat weekly yardage milestone bonuses (ESPN/Yahoo "100-yard game" style), applied once per
    #: player-week when the threshold is reached. Thresholds are inclusive.
    pass_yd_bonus: float = 0.0
    pass_yd_bonus_at: float = 300.0
    rush_yd_bonus: float = 0.0
    rush_yd_bonus_at: float = 100.0
    rec_yd_bonus: float = 0.0
    rec_yd_bonus_at: float = 100.0


class KickingRules(_Rules):
    """Field goals scored by distance bucket + PATs. Misses default to 0 (no penalty)."""
    fg_0_39: float = 3.0
    fg_40_49: float = 4.0
    fg_50_plus: float = 5.0
    pat: float = 1.0
    fg_miss: float = 0.0
    pat_miss: float = 0.0


class DstRules(_Rules):
    """Team-defense event weights + points-allowed tiers. Blocked kicks are not derived from
    ``pbp`` cleanly, so ``block`` is defined but not currently scored (documented approximation)."""
    sack: float = 1.0
    interception: float = 2.0
    fumble_rec: float = 2.0
    td: float = 6.0                # defensive + return TDs (td_team == defteam)
    safety: float = 2.0
    block: float = 2.0             # defined, not currently derived (see docstring)
    # (upper-inclusive points-allowed, points): first tier whose bound >= PA wins.
    pa_tiers: list[tuple[int, float]] = Field(
        default_factory=lambda: [(0, 10.0), (6, 7.0), (13, 4.0), (20, 1.0),
                                 (27, 0.0), (34, -1.0), (99, -4.0)]
    )


class RuleSet(_Rules):
    """The league ruleset the backtest scores against (stated baseline: 10-team full-PPR, 1-QB,
    9-starter QB/2RB/2WR/TE/FLEX+K+DST)."""
    name: str = "full_ppr_1qb"
    offense: OffenseRules = Field(default_factory=OffenseRules)
    kicking: KickingRules = Field(default_factory=KickingRules)
    dst: DstRules = Field(default_factory=DstRules)


DEFAULT_RULESET = RuleSet()


#: 17.2 — the named scoring presets a settings form offers. ``full_ppr`` **is** ``DEFAULT_RULESET``
#: (the lockbox-validated baseline); every other preset differs from it only in the reception rate
#: or the TE bonus, so a board built under one is comparable to a board built under another.
#: Anything a preset cannot express is set field-by-field on the returned :class:`RuleSet`.
SCORING_PRESETS: dict[str, dict] = {
    "standard":    {"rec": 0.0},
    "half_ppr":    {"rec": 0.5},
    "full_ppr":    {},
    "te_premium":  {"te_rec_bonus": 0.5},
}


def ruleset_from_preset(preset: str = "full_ppr", **overrides) -> RuleSet:
    """Build a :class:`RuleSet` from a named preset plus arbitrary offense overrides (17.2).

    ``ruleset_from_preset("full_ppr")`` returns a ruleset **equal to** :data:`DEFAULT_RULESET`,
    ``name`` included. That equality is load-bearing, not cosmetic: ``RuleSet`` is serialized into
    the cache key of :func:`~fantasy_quant.projections.distribution.cached_distribution` (and the
    16.13 board caches beneath it), so a preset that produced identical scoring under a *different*
    name would silently force a full 9-season rebuild and split the cache in two.

    Overrides are validated by pydantic with ``extra="forbid"``, which is the point of a bounded
    field set rather than an open ``{stat: value}`` map — a typo raises here instead of silently
    scoring zero for the rest of the season.
    """
    key = str(preset).strip().lower()
    if key not in SCORING_PRESETS:
        raise ValueError(f"unknown scoring preset {preset!r}; "
                         f"known: {sorted(SCORING_PRESETS)}")
    offense = OffenseRules(**{**SCORING_PRESETS[key], **overrides})
    if key == "full_ppr" and not overrides:
        return RuleSet()
    name = key if not overrides else f"{key}_custom"
    return RuleSet(name=name, offense=offense)


# --------------------------------------------------------------------------------------------
# pure scoring — offense (validated vs nflverse fantasy_points_ppr)
# --------------------------------------------------------------------------------------------
def _num(df: pd.DataFrame, col: str) -> pd.Series:
    """Numeric column, missing/NaN -> 0 (a stat a player didn't record is simply zero)."""
    if col not in df.columns:
        return pd.Series(0.0, index=df.index)
    return pd.to_numeric(df[col], errors="coerce").fillna(0.0)


def score_offense(df: pd.DataFrame, rules: OffenseRules | None = None) -> pd.Series:
    """Fantasy points for offensive player-weeks from ``weekly``-style component columns.

    With the default ruleset this equals nflverse ``fantasy_points_ppr`` (set ``rec=0`` for the
    ``fantasy_points`` standard column). Pure/vectorized — the unit-test target.
    """
    r = rules or DEFAULT_RULESET.offense
    fumbles = (_num(df, "sack_fumbles_lost") + _num(df, "rushing_fumbles_lost")
               + _num(df, "receiving_fumbles_lost"))
    two_pt = (_num(df, "passing_2pt_conversions") + _num(df, "rushing_2pt_conversions")
              + _num(df, "receiving_2pt_conversions"))
    # 17.2 — TE premium. Per-reception rate is `rec` plus a TE-only bonus, so it needs the row's
    # position; when the frame carries none (pure unit-test frames, some derived panels) the bonus
    # is simply not applied, which keeps the default `te_rec_bonus=0.0` path byte-identical.
    rec_rate = pd.Series(float(r.rec), index=df.index)
    if r.te_rec_bonus and "position" in df.columns:
        is_te = df["position"].astype("string").str.upper().eq("TE").fillna(False)
        rec_rate = rec_rate + is_te.astype(float) * float(r.te_rec_bonus)
    return (
        _num(df, "passing_yards") * r.pass_yd
        + _num(df, "passing_tds") * r.pass_td
        + _num(df, "interceptions") * r.interception
        + _num(df, "rushing_yards") * r.rush_yd
        + _num(df, "rushing_tds") * r.rush_td
        + _num(df, "receiving_yards") * r.rec_yd
        + _num(df, "receiving_tds") * r.rec_td
        + _num(df, "receptions") * rec_rate
        + _num(df, "special_teams_tds") * r.st_td
        + two_pt * r.two_pt
        + fumbles * r.fumble_lost
        + _num(df, "passing_yards").ge(r.pass_yd_bonus_at).astype(float) * r.pass_yd_bonus
        + _num(df, "rushing_yards").ge(r.rush_yd_bonus_at).astype(float) * r.rush_yd_bonus
        + _num(df, "receiving_yards").ge(r.rec_yd_bonus_at).astype(float) * r.rec_yd_bonus
    )


# --------------------------------------------------------------------------------------------
# pure scoring — kickers (from pbp field-goal / extra-point plays)
# --------------------------------------------------------------------------------------------
def kick_play_points(plays: pd.DataFrame, rules: KickingRules | None = None) -> pd.Series:
    """Points for each kicking play (rows with ``field_goal_attempt`` or ``extra_point_attempt``).

    FG scored by ``kick_distance`` bucket when ``field_goal_result='made'``; PAT on
    ``extra_point_result='good'``; misses use the (default-0) penalty. Pure — the unit-test target.
    """
    r = rules or DEFAULT_RULESET.kicking
    fga = _num(plays, "field_goal_attempt") == 1
    made = (plays["field_goal_result"].eq("made") if "field_goal_result" in plays.columns
            else pd.Series(False, index=plays.index))
    dist = _num(plays, "kick_distance")
    fg_pts = pd.Series(0.0, index=plays.index)
    fg_pts = fg_pts.mask(fga & made & (dist < 40), r.fg_0_39)
    fg_pts = fg_pts.mask(fga & made & (dist >= 40) & (dist < 50), r.fg_40_49)
    fg_pts = fg_pts.mask(fga & made & (dist >= 50), r.fg_50_plus)
    fg_pts = fg_pts.mask(fga & ~made, r.fg_miss)

    xpa = _num(plays, "extra_point_attempt") == 1
    good = (plays["extra_point_result"].eq("good") if "extra_point_result" in plays.columns
            else pd.Series(False, index=plays.index))
    xp_pts = pd.Series(0.0, index=plays.index)
    xp_pts = xp_pts.mask(xpa & good, r.pat)
    xp_pts = xp_pts.mask(xpa & ~good, r.pat_miss)
    return fg_pts + xp_pts


# --------------------------------------------------------------------------------------------
# pure scoring — team defense (event counts + points allowed)
# --------------------------------------------------------------------------------------------
def pa_tier_points(pa: pd.Series, tiers: list[tuple[int, float]] | None = None) -> pd.Series:
    """Points-allowed tier bonus: first ``(bound, pts)`` whose bound >= PA. Vectorized/pure."""
    tiers = tiers or DEFAULT_RULESET.dst.pa_tiers
    pa = pd.to_numeric(pa, errors="coerce")
    out = pd.Series(float("nan"), index=pa.index)
    for bound, pts in sorted(tiers):
        out = out.mask(out.isna() & (pa <= bound), pts)
    return out.fillna(sorted(tiers)[-1][1])


def score_dst(df: pd.DataFrame, rules: DstRules | None = None) -> pd.Series:
    """Team-defense fantasy points from per-team-week event counts + points allowed.

    Expects columns: ``sacks, ints, fum_rec, def_tds, safeties, pa``. Pure — the unit-test target.
    """
    r = rules or DEFAULT_RULESET.dst
    return (
        _num(df, "sacks") * r.sack
        + _num(df, "ints") * r.interception
        + _num(df, "fum_rec") * r.fumble_rec
        + _num(df, "def_tds") * r.td
        + _num(df, "safeties") * r.safety
        + pa_tier_points(df["pa"], r.pa_tiers)
    )


# --------------------------------------------------------------------------------------------
# DB wrappers — pull raw stats, delegate to the pure scorers
# --------------------------------------------------------------------------------------------
def weekly_points(con, season: int, ruleset: RuleSet | None = None) -> pd.DataFrame:
    """Offensive player-week points for ``season`` (REG) + nflverse's own points for validation."""
    rs = ruleset or DEFAULT_RULESET
    df = con.execute(
        """
        SELECT gsis_id, player_display_name AS player_name, position, recent_team AS team,
               season, week,
               passing_yards, passing_tds, interceptions, passing_2pt_conversions,
               rushing_yards, rushing_tds, rushing_2pt_conversions,
               receptions, receiving_yards, receiving_tds, receiving_2pt_conversions,
               special_teams_tds, sack_fumbles_lost, rushing_fumbles_lost, receiving_fumbles_lost,
               fantasy_points, fantasy_points_ppr
        FROM weekly WHERE season = ? AND season_type = 'REG'
        """,
        [int(season)],
    ).df()
    df["points"] = score_offense(df, rs.offense)
    return df


def season_points(con, season: int, ruleset: RuleSet | None = None) -> pd.DataFrame:
    """Season fantasy-point totals per offensive player (sum of :func:`weekly_points`)."""
    wk = weekly_points(con, season, ruleset)
    return (wk.groupby(["gsis_id", "player_name", "position", "season"], as_index=False)
              .agg(points=("points", "sum"), weeks=("week", "nunique")))


def kicker_weekly_points(con, season: int, ruleset: RuleSet | None = None) -> pd.DataFrame:
    """Kicker player-week points for ``season`` (REG), derived from ``pbp`` kicking plays.

    Keyed on ``kicker_player_id`` (gsis format), joining to the ADP board's resolved kicker gsis.
    """
    rs = ruleset or DEFAULT_RULESET
    plays = con.execute(
        """
        SELECT kicker_player_id AS gsis_id, kicker_player_name AS player_name,
               posteam AS team, season, week,
               field_goal_attempt, field_goal_result, kick_distance,
               extra_point_attempt, extra_point_result
        FROM pbp
        WHERE season = ? AND season_type = 'REG' AND kicker_player_id IS NOT NULL
          AND (field_goal_attempt = 1 OR extra_point_attempt = 1)
        """,
        [int(season)],
    ).df()
    plays["pts"] = kick_play_points(plays, rs.kicking)
    return (plays.groupby(["gsis_id", "player_name", "team", "season", "week"], as_index=False)
                 .agg(points=("pts", "sum")))


def dst_weekly_points(con, season: int, ruleset: RuleSet | None = None) -> pd.DataFrame:
    """Team-defense player-week points for ``season`` (REG), from ``pbp`` events + PA (game_lines).

    Keyed on the defending ``team`` abbreviation, so it joins to an ADP defense resolved via
    :func:`dst_team_from_adp_name`. Defensive + return TDs are ``td_team == defteam``; points
    allowed is the opponent's final score. Blocked kicks are not derived (see :class:`DstRules`).
    """
    rs = ruleset or DEFAULT_RULESET
    events = con.execute(
        """
        SELECT defteam AS team, season, week,
               SUM(COALESCE(sack, 0))          AS sacks,
               SUM(COALESCE(interception, 0))  AS ints,
               SUM(COALESCE(fumble_lost, 0))   AS fum_rec,
               SUM(CASE WHEN td_team = defteam THEN 1 ELSE 0 END) AS def_tds,
               SUM(COALESCE(safety, 0))        AS safeties
        FROM pbp
        WHERE season = ? AND season_type = 'REG' AND defteam IS NOT NULL
        GROUP BY defteam, season, week
        """,
        [int(season)],
    ).df()
    pa = con.execute(
        """
        SELECT season, week, home_team AS team, away_score AS pa
        FROM game_lines WHERE season = ? AND game_type = 'REG'
        UNION ALL
        SELECT season, week, away_team AS team, home_score AS pa
        FROM game_lines WHERE season = ? AND game_type = 'REG'
        """,
        [int(season), int(season)],
    ).df()
    df = events.merge(pa, on=["season", "week", "team"], how="left")
    df["points"] = score_dst(df, rs.dst)
    return df


# --------------------------------------------------------------------------------------------
# identity — connect ADP K/DST rows (null gsis) to a scoreable key
# --------------------------------------------------------------------------------------------
# city/name tokens -> nflverse team abbrev (handles relocations by keying on distinctive tokens).
_DST_NAME_TO_TEAM: dict[str, str] = {
    "arizona": "ARI", "atlanta": "ATL", "baltimore": "BAL", "buffalo": "BUF",
    "carolina": "CAR", "chicago": "CHI", "cincinnati": "CIN", "cleveland": "CLE",
    "dallas": "DAL", "denver": "DEN", "detroit": "DET", "green bay": "GB",
    "houston": "HOU", "indianapolis": "IND", "jacksonville": "JAX", "kansas city": "KC",
    "miami": "MIA", "minnesota": "MIN", "new england": "NE", "new orleans": "NO",
    "ny giants": "NYG", "new york giants": "NYG", "ny jets": "NYJ", "new york jets": "NYJ",
    "philadelphia": "PHI", "pittsburgh": "PIT", "san francisco": "SF", "seattle": "SEA",
    "tampa bay": "TB", "tennessee": "TEN",
    # relocations / renames (abbrev matches game_lines for the relevant seasons)
    "la rams": "LA", "los angeles rams": "LA", "st louis": "STL", "st. louis": "STL",
    "la chargers": "LAC", "los angeles chargers": "LAC", "san diego": "SD",
    "las vegas": "LV", "oakland": "OAK",
    "washington": "WAS", "washington commanders": "WAS", "washington football team": "WAS",
}


def dst_team_from_adp_name(name: str | float) -> str | None:
    """Map an FFC defense ADP name (e.g. "Philadelphia Defense") to a team abbrev, or None.

    Note: for the relocated LA/SD/STL/OAK franchises the abbrev is the *current-name* mapping;
    the harness pins it to the right era by joining on (season, week, team) against ``game_lines``.
    """
    if not isinstance(name, str):
        return None
    key = name.lower().replace("defense", "").replace("d/st", "").replace("dst", "").strip()
    key = " ".join(key.split())
    if key in _DST_NAME_TO_TEAM:
        return _DST_NAME_TO_TEAM[key]
    # fall back to longest matching token-prefix (e.g. "green bay packers" -> "green bay")
    for token, abbr in sorted(_DST_NAME_TO_TEAM.items(), key=lambda kv: -len(kv[0])):
        if key.startswith(token):
            return abbr
    return None


def resolve_kicker_gsis(con, name: str, season: int | None = None) -> str | None:
    """Resolve a kicker ADP name to a gsis_id via ``player_ids`` (position PK/K, normalized name).

    Reuses :func:`normalize_name` (0.4) so FFC and player_ids names join consistently. When a
    homonym exists, prefers the id whose ``draft_year`` is closest to (and <=) ``season``.
    """
    ids = con.execute(
        "SELECT gsis_id, name, draft_year FROM player_ids "
        "WHERE position IN ('PK', 'K') AND gsis_id IS NOT NULL"
    ).df()
    if ids.empty:
        return None
    ids["_nn"] = ids["name"].map(normalize_name)
    hit = ids[ids["_nn"] == normalize_name(name)]
    if hit.empty:
        return None
    if len(hit) > 1 and season is not None:
        dy = pd.to_numeric(hit["draft_year"], errors="coerce")
        hit = hit.assign(_dist=(season - dy).where(dy <= season, 999).abs()).sort_values("_dist")
    return str(hit.iloc[0]["gsis_id"])
