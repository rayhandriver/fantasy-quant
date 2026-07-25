"""Phase 6.1 — the ADP-alpha panel (where the market is soft).

The reframe (2026-07-04) repurposes ADP-bias mining: not "beat the draft market" but *find where
ADP is systematically soft, so we know how cheaply a personalization preference can be indulged.* A
player's **ADP-alpha** is how much their realized value beat (or missed) what their draft slot
implied — the fantasy analog of a factor return. Mining which **observable, point-in-time traits**
predict a positive alpha tells us which kinds of players the crowd under-drafts (cheap/free to
prefer) versus over-drafts (costly to chase).

**Target (chosen 2026-07-07): value-over-replacement alpha.** ``alpha = realized_vor −
adp_implied_vor``, where realized VOR is a player's realized season points minus their position's
replacement level (Phase-1.4 units, so it is position-fair and shares the cost report's scale), and
the ADP-implied baseline is a **leave-one-season-out isotonic fit** of realized VOR on ADP
positional rank (monotone, low-parameter, and — crucially — never fit on the season it scores, so no
outcome leaks into a player's own baseline).

**Features are all PIT at draft time** (CLAUDE.md §3): position, experience / rookie status, ADP
tier, ADP **dispersion** (the crowd's own disagreement — FFC ``stdev``), and prior-season durability
and productivity. Runs on all of ``DEV_SEASONS``; the 2023/24 lockbox is never read.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

from fantasy_quant.backtest.metrics import replacement_ranks
from fantasy_quant.backtest.scoring import RuleSet, season_points
from fantasy_quant.backtest.walkforward import draft_date
from fantasy_quant.config import DEV_SEASONS
from fantasy_quant.data.sources.adp import adp_asof
from fantasy_quant.draft.simulator import RosterSlots

OFFENSE = ("QB", "RB", "WR", "TE")
_CANON = {"QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE", "FB": "RB", "HB": "RB"}

# The trait hypotheses the Phase-6.2 regression tests (all knowable on draft day). Continuous ones
# are z-scored in the regression; ``rookie`` and the position dummies stay 0/1. **Pinned**: this is
# the frozen-softness model spec (the cost-report DURABILITY credit was estimated on exactly these),
# so it must not grow — see ``adp/softness.py``.
FEATURES: tuple[str, ...] = ("rookie", "experience", "adp_stdev", "prior_games", "prior_ppg")

# Phase-16.1 situation-change extension (2026-07-24): does the crowd misprice a player whose
# offseason situation moved? These are mined **alongside** FEATURES only by the walled-off Phase-16
# step (``PHASE16_FEATURES``), never folded into the frozen FEATURES default — so the cost-report
# softness credit is untouched. They ride the panel as 0/1 columns regardless; the regression only
# sees them when a caller passes them. 16.2 will append its competition-change flags here.
SITUATION_FEATURES: tuple[str, ...] = ("team_changed", "new_starting_qb",
                                       "competition_change_roster", "competition_change_depth")
PHASE16_FEATURES: tuple[str, ...] = (*FEATURES, *SITUATION_FEATURES)

# Franchise aliases so a **relocation / abbreviation drift** never reads as a player changing teams.
# ``weekly`` is normalized to modern codes (Raiders always LV, Rams LA); the ADP board keeps the
# season's era-accurate code (OAK pre-2020, LAR, plus ``FA`` for free agents). Collapse both to one
# canonical token before any cross-source team comparison. ``FA`` → missing (no team).
_TEAM_ALIAS: dict[str, object] = {"OAK": "LV", "SD": "LAC", "STL": "LAR", "LA": "LAR",
                                  "JAC": "JAX", "ARZ": "ARI", "WSH": "WAS", "FA": pd.NA}


# ------------------------------------------------------------------------------------------------
# per-season ingredients
# ------------------------------------------------------------------------------------------------
def _canon_pos(s: pd.Series) -> pd.Series:
    return s.astype(str).str.upper().map(_CANON)


def _canon_team(s: pd.Series) -> pd.Series:
    """Canonical franchise code — collapses relocations/abbreviation variants (see ``_TEAM_ALIAS``)
    so team codes align across the ADP board (era-accurate) and ``weekly`` (modern-normalized)."""
    return s.astype("string").str.upper().replace(_TEAM_ALIAS)


def _offense_season_points(con, season: int, ruleset: RuleSet | None) -> pd.DataFrame:
    """Realized season fantasy points per offensive player (canonical position, games played)."""
    sp = season_points(con, season, ruleset)
    sp = sp.assign(pos=_canon_pos(sp["position"])).dropna(subset=["pos", "gsis_id"])
    return sp.groupby(["gsis_id", "pos"], as_index=False).agg(points=("points", "sum"),
                                                              games=("weeks", "max"))


def _replacement_levels(points: pd.DataFrame, slots: RosterSlots, n_teams: int) -> dict[str, float]:
    """Offense replacement level per position = realized season points at the replacement rank
    (QB10/RB24/WR24/TE12 in the baseline league). Computed straight from realized points — no K/DST
    play-by-play scoring needed (keeps the panel build fast)."""
    ranks = replacement_ranks(slots, n_teams)
    out = {}
    for pos in OFFENSE:
        vals = np.sort(points.loc[points["pos"] == pos, "points"].to_numpy(float))[::-1]
        rank = ranks[pos]
        out[pos] = float(vals[min(rank - 1, len(vals) - 1)]) if len(vals) else 0.0
    return out


def _prior_features(con, season: int, ruleset: RuleSet | None) -> pd.DataFrame:
    """Prior-season durability + productivity per player (PIT: fully known before the draft)."""
    prev = _offense_season_points(con, season - 1, ruleset)
    if prev.empty:
        return pd.DataFrame(columns=["gsis_id", "prior_games", "prior_ppg"])
    prev = prev.assign(prior_ppg=prev["points"] / prev["games"].clip(lower=1))
    return prev.rename(columns={"games": "prior_games"})[["gsis_id", "prior_games", "prior_ppg"]]


# ------------------------------------------------------------------------------------------------
# Phase-16.1 situation-change ingredients (team change · new starting QB) — all PIT at draft day.
# NB: the ADP board's ``team`` column is NOT usable here — it is contaminated with an end-of-season
# crosswalk (verified 2026-07-24: the Sep-1 2022 board lists McCaffrey on SF, Toney on KC, Claypool
# on CHI, all mid-season *trades* not yet made at draft time). So team-of-record is derived entirely
# from ``weekly``: the **first-game (Week-1) team** is the PIT draft-day proxy — the opening roster
# is set at/before the draft and, unlike the board field, does not encode a later trade.
# ------------------------------------------------------------------------------------------------
def _early_season_team(con, season: int) -> pd.DataFrame:
    """Each player's draft-day team proxy = the team of his **first game** in season S (min week).
    PIT: the Week-1 roster is known at the draft and does not leak a later mid-season trade."""
    w = con.execute(
        "SELECT gsis_id, recent_team AS team, week FROM weekly "
        "WHERE season = ? AND gsis_id IS NOT NULL AND recent_team IS NOT NULL",
        [season]).df()
    if w.empty:
        return pd.DataFrame(columns=["gsis_id", "team"])
    w = w.sort_values(["gsis_id", "week"]).drop_duplicates("gsis_id")
    w["team"] = _canon_team(w["team"])
    return w[["gsis_id", "team"]]


def _prev_primary_team(con, season: int) -> pd.DataFrame:
    """Each player's primary team in the prior season (PIT — S−1 is fully realized): the team he
    logged the most weeks for (a mid-season trade resolves to the dominant team)."""
    w = con.execute(
        "SELECT gsis_id, recent_team AS team_prev, COUNT(*) AS wk FROM weekly "
        "WHERE season = ? AND gsis_id IS NOT NULL AND recent_team IS NOT NULL "
        "GROUP BY gsis_id, recent_team", [season - 1]).df()
    if w.empty:
        return pd.DataFrame(columns=["gsis_id", "team_prev"])
    w = w.sort_values(["gsis_id", "wk"], ascending=[True, False]).drop_duplicates("gsis_id")
    w["team_prev"] = _canon_team(w["team_prev"])
    return w[["gsis_id", "team_prev"]]


def _starting_qb(con, season: int, weeks: str) -> pd.DataFrame:
    """The starting QB per (canonical) team = the passer with the most attempts over ``weeks`` (a
    ``week`` SQL predicate). ``weeks='TRUE'`` → the full prior season's QB1 (incumbent); ``week=1``
    → this season's opening starter (a PIT proxy — the Week-1 starter is known at draft)."""
    a = con.execute(
        "SELECT recent_team AS team, gsis_id, SUM(attempts) AS att FROM weekly "
        f"WHERE season = ? AND ({weeks}) AND gsis_id IS NOT NULL AND recent_team IS NOT NULL "
        "GROUP BY recent_team, gsis_id HAVING SUM(attempts) > 0", [season]).df()
    if a.empty:
        return pd.DataFrame(columns=["team", "qb1"])
    a = a.sort_values(["team", "att"], ascending=[True, False]).drop_duplicates("team")
    a["team"] = _canon_team(a["team"])
    return a.rename(columns={"gsis_id": "qb1"})[["team", "qb1"]]


def _new_starting_qb_map(con, season: int) -> dict[str, int]:
    """Per (canonical) team: 1 if this season's opening starting QB differs from the prior-season
    incumbent (both known), else 0. A player inherits his team's flag; unknown team ⇒ 0."""
    cur = _starting_qb(con, season, "week = 1").rename(columns={"qb1": "cur_qb1"})
    prev = _starting_qb(con, season - 1, "TRUE").rename(columns={"qb1": "prev_qb1"})
    teams = cur.merge(prev, on="team", how="outer")
    changed = (teams["cur_qb1"].notna() & teams["prev_qb1"].notna()
               & (teams["cur_qb1"] != teams["prev_qb1"])).astype(int)
    return dict(zip(teams["team"], changed, strict=False))


# ------------------------------------------------------------------------------------------------
# Phase-16.2 competition-change, **dual-sourced** (2026-07-24). Did a *same-position teammate*
# arrive or depart between seasons? Two independent operationalizations, mined side by side to test
# whether roster-turnover avoids the null Phase 12.3 found on the depth-chart source:
#   (a) roster-turnover  — from weekly usage + draft_picks (a material vet or high-pick rookie).
#   (b) depth-chart      — from the season-opening depth chart's top-N at the position.
# Both **exclude the player himself** (so it is teammate churn, not his own team change) and are
# keyed on the PIT Week-1 team. NB: depth uses ``depth_charts`` (2014–24), not ``depth_charts_ts``
# (2025-only), so the DEV window is covered.
# ------------------------------------------------------------------------------------------------
# 'Material' = a startable-caliber competitor whose arrival/exit actually changes the touch/target
# competition. Prior-season leaguewide finish inside these per-position ranks (roughly a 10–12-team
# starter pool); a lower bar floods the feature (deep-bench churn hits ~every room every year).
MATERIAL_RANK: dict[str, int] = {"QB": 18, "RB": 30, "WR": 36, "TE": 15}
ROOKIE_ROUND = 2       # a rookie drafted this early is a material incoming competitor (no prior)
DEPTH_TOP = 2          # 'competition' = a team's top-N (starter-level) depth-chart slots at a spot


def _season_pos(con, season: int) -> dict[str, str]:
    """gsis_id → canonical position for ``season`` (modal weekly position; position never leaks)."""
    w = con.execute("SELECT gsis_id, position FROM weekly WHERE season = ? AND gsis_id IS NOT NULL",
                    [season]).df()
    w["pos"] = _canon_pos(w["position"])
    w = w.dropna(subset=["pos"])
    if w.empty:
        return {}
    modal = w.groupby("gsis_id")["pos"].agg(lambda s: s.mode().iat[0])
    return modal.to_dict()


def _prev_room(con, season: int) -> dict[tuple[str, str], frozenset]:
    """{(canonical team, pos): {gsis_id}} of *material* (startable-caliber) same-position players in
    S−1 — prior-season leaguewide PPR finish inside ``MATERIAL_RANK[pos]``, on their primary team.
    The incumbent competition, PIT."""
    w = con.execute(
        "SELECT gsis_id, position, recent_team, fantasy_points_ppr AS ppr FROM weekly "
        "WHERE season = ? AND gsis_id IS NOT NULL AND recent_team IS NOT NULL", [season - 1]).df()
    if w.empty:
        return {}
    w["pos"], w["team"] = _canon_pos(w["position"]), _canon_team(w["recent_team"])
    w = w.dropna(subset=["pos", "team"])
    prim = (w.groupby(["gsis_id", "team"]).size().reset_index(name="wk")
            .sort_values("wk", ascending=False).drop_duplicates("gsis_id"))
    ppr = w.groupby("gsis_id")["ppr"].sum().reset_index()
    pos = w.groupby("gsis_id")["pos"].agg(lambda s: s.mode().iat[0]).reset_index()
    u = prim.merge(ppr, on="gsis_id").merge(pos, on="gsis_id")
    u["rank"] = u.groupby("pos")["ppr"].rank(ascending=False, method="first")
    u = u[u["rank"] <= u["pos"].map(MATERIAL_RANK)]
    return {k: frozenset(g["gsis_id"]) for k, g in u.groupby(["team", "pos"])}


def _now_room(con, season: int) -> dict[tuple[str, str], frozenset]:
    """{(canonical team, pos): {gsis_id}} of *material* same-position players entering season S on
    their Week-1 team — a returning/arriving vet (prior PPR ≥ threshold) or a high-pick rookie. PIT:
    Week-1 team + prior usage + draft capital are all known at the draft."""
    base = _early_season_team(con, season)                 # gsis_id, team (Week-1, canonical)
    if base.empty:
        return {}
    pos = _season_pos(con, season)
    prev = _prev_room(con, season)                         # to read prior materiality by identity
    material_vets = frozenset().union(*prev.values()) if prev else frozenset()
    rooks = con.execute(
        "SELECT gsis_id FROM draft_picks WHERE season = ? AND round <= ? AND gsis_id IS NOT NULL",
        [season, ROOKIE_ROUND]).df()["gsis_id"]
    material = material_vets | frozenset(rooks)
    base = base[base["gsis_id"].isin(material)].copy()
    base["pos"] = base["gsis_id"].map(pos)
    base = base.dropna(subset=["pos", "team"])
    return {k: frozenset(g["gsis_id"]) for k, g in base.groupby(["team", "pos"])}


def _depth_room(con, season: int, top: int | None) -> dict[tuple[str, str], frozenset]:
    """{(canonical team, pos): {gsis_id}} from the season-opening depth chart (``depth_charts``,
    earliest week). ``top`` caps the depth rank (e.g. 2 = the starter-level slots); ``None`` = the
    whole positional depth chart."""
    d = con.execute(
        "SELECT gsis_id, club_code, position, depth_team, week FROM depth_charts "
        "WHERE season = ? AND gsis_id IS NOT NULL AND week IS NOT NULL", [season]).df()
    if d.empty:
        return {}
    d = d[d["week"] == d["week"].min()]                    # season-opening depth
    d["pos"], d["team"] = _canon_pos(d["position"]), _canon_team(d["club_code"])
    d["depth"] = pd.to_numeric(d["depth_team"], errors="coerce")
    d = d.dropna(subset=["pos", "team", "depth"])
    if top is not None:
        d = d[d["depth"] <= top]
    return {k: frozenset(g["gsis_id"]) for k, g in d.groupby(["team", "pos"])}


def _competition_flags(con, season: int, df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """The two 0/1 competition-change flags for the rows in ``df`` (needs ``gsis_id``, canonical
    ``pos``, canonical Week-1 ``team``); the player himself is always excluded so both measure
    *teammate* churn, not his own move.

    * **roster** — the set of *other* material (startable-caliber) same-position players changed
      between S−1 and S (a starter-quality vet or high-pick rookie arrived, or a material one left).
    * **depth**  — a genuinely *new* competitor cracked the season-S starting depth (in the top-
      ``DEPTH_TOP`` but absent from the team's entire S−1 depth chart at that position). A set-
      difference version floods to ~90 % (depth charts reshuffle yearly); the new-entrant version
      isolates a real newcomer.
    """
    prev_r, now_r = _prev_room(con, season), _now_room(con, season)
    now_top = _depth_room(con, season, top=DEPTH_TOP)
    prev_full = _depth_room(con, season - 1, top=None)

    def _roster_changed(team, pos, gid) -> int:
        if pd.isna(team) or pd.isna(pos):
            return 0
        a = prev_r.get((team, pos), frozenset()) - {gid}
        b = now_r.get((team, pos), frozenset()) - {gid}
        return int(a != b)

    def _depth_newcomer(team, pos, gid) -> int:
        if pd.isna(team) or pd.isna(pos):
            return 0
        incumbents = prev_full.get((team, pos), frozenset())
        starters = now_top.get((team, pos), frozenset()) - {gid}
        return int(any(q not in incumbents for q in starters))

    roster = [_roster_changed(t, p, g)
              for t, p, g in zip(df["team"], df["pos"], df["gsis_id"], strict=False)]
    depth = [_depth_newcomer(t, p, g)
             for t, p, g in zip(df["team"], df["pos"], df["gsis_id"], strict=False)]
    return (pd.Series(roster, index=df.index, dtype=int),
            pd.Series(depth, index=df.index, dtype=int))


def _season_rows(con, season: int, ids: pd.DataFrame, slots: RosterSlots, n_teams: int,
                 max_adp: float, ruleset: RuleSet | None) -> pd.DataFrame:
    """One season's raw panel rows: PIT ADP board × realized VOR × PIT traits (pre-baseline)."""
    as_of = draft_date(con, season)
    if as_of is None:
        return pd.DataFrame()
    board = adp_asof(con, season, as_of)
    board = board.assign(pos=_canon_pos(board["position"]))
    board = board[board["pos"].isin(OFFENSE) & board["gsis_id"].notna()
                  & (pd.to_numeric(board["adp"], errors="coerce") <= max_adp)]
    if board.empty:
        return pd.DataFrame()

    pts = _offense_season_points(con, season, ruleset)
    repl = _replacement_levels(pts, slots, n_teams)
    pts = pts.assign(realized_vor=pts["points"] - pts["pos"].map(repl))

    nsq = _new_starting_qb_map(con, season)     # canonical-team → new-starting-QB flag (PIT)
    idy = ids[["gsis_id", "draft_year"]].drop_duplicates("gsis_id")
    # drop the board's own ``team`` (an end-of-season crosswalk, see above) so the PIT Week-1 team
    # from ``_early_season_team`` is the sole team-of-record.
    board = board.drop(columns=["team"], errors="ignore")
    df = board.merge(pts[["gsis_id", "points", "realized_vor"]], on="gsis_id", how="left")
    df = df.merge(idy, on="gsis_id", how="left")
    df = df.merge(_prior_features(con, season, ruleset), on="gsis_id", how="left")
    df = df.merge(_early_season_team(con, season), on="gsis_id", how="left")   # PIT team_s
    df = df.merge(_prev_primary_team(con, season), on="gsis_id", how="left")

    dy = pd.to_numeric(df["draft_year"], errors="coerce")
    exp = (season - dy)
    team_s = df["team"]                          # draft-day (Week-1) team, PIT — already canonical
    team_prev = df["team_prev"]                  # prior season's primary team (already canonical)
    team_changed = (team_prev.notna() & team_s.notna() & (team_prev != team_s))
    comp_roster, comp_depth = _competition_flags(con, season, df)   # 16.2 dual-sourced
    out = pd.DataFrame({
        "season": season,
        "gsis_id": df["gsis_id"],
        "name": df["name"],
        "pos": df["pos"],
        "adp": pd.to_numeric(df["adp"], errors="coerce"),
        "pos_rank": pd.to_numeric(df["pos_rank"], errors="coerce"),
        "adp_stdev": pd.to_numeric(df.get("stdev"), errors="coerce"),
        # realized value-over-replacement; a drafted player who never recorded a stat scored 0
        # points (survivorship guard) → VOR = −replacement, the honest bust outcome, not a drop.
        "realized_vor": df["realized_vor"].fillna(-df["pos"].map(repl)),
        "rookie": (exp == 0).fillna(False).astype(int),
        "experience": exp,
        "prior_games": df["prior_games"],
        "prior_ppg": df["prior_ppg"],
        "team": team_s,
        # Phase-16.1 situation-change flags (0/1, PIT). team_changed: on a different franchise than
        # last season (rookies have no prior team ⇒ 0, the rookie flag separates them).
        # new_starting_qb: the team enters the season with a different starter than last year's QB1.
        "team_changed": team_changed.astype("boolean").fillna(False).astype(int),
        "new_starting_qb": team_s.map(nsq).fillna(0).astype(int),
        # 16.2 competition-change (dual-sourced): a material same-position teammate arrived/left.
        "competition_change_roster": comp_roster,
        "competition_change_depth": comp_depth,
    })
    # rookies / first-year-in-data players have no prior line: zero it (rookie flag carries it).
    out["prior_games"] = out["prior_games"].fillna(0.0)
    out["prior_ppg"] = out["prior_ppg"].fillna(0.0)
    out["experience"] = out["experience"].fillna(out["experience"].median()).clip(lower=0)
    return out


# ------------------------------------------------------------------------------------------------
# the leave-one-season-out ADP-implied baseline → alpha
# ------------------------------------------------------------------------------------------------
def _loso_isotonic_baseline(panel: pd.DataFrame) -> pd.Series:
    """ADP-implied VOR for each row = a monotone (non-increasing in ``pos_rank``) isotonic fit of
    realized VOR, trained **within position on every season but the row's own** (leave-one-season-
    out, so no outcome leaks into its baseline). Thin position-seasons fall back to the LOO mean."""
    implied = pd.Series(np.nan, index=panel.index)
    for _pos, g in panel.groupby("pos"):
        for s in g["season"].unique():
            train = g[g["season"] != s]
            test = g[g["season"] == s]
            if len(train) >= 8:
                iso = IsotonicRegression(increasing=False, out_of_bounds="clip")
                iso.fit(train["pos_rank"].to_numpy(float), train["realized_vor"].to_numpy(float))
                pred = iso.predict(test["pos_rank"].to_numpy(float))
            else:
                pred = np.full(len(test), train["realized_vor"].mean() if len(train) else 0.0)
            implied.loc[test.index] = pred
    return implied


def build_alpha_panel(con, seasons: Iterable[int] = DEV_SEASONS, max_adp: float = 180.0,
                      slots: RosterSlots | None = None, n_teams: int = 10,
                      ruleset: RuleSet | None = None) -> pd.DataFrame:
    """Build the ADP-alpha panel over ``seasons`` (see the module docstring).

    Returns one row per drafted (season, offensive player) with the ADP-alpha target and all PIT
    trait features. ``alpha`` = realized VOR − leave-one-season-out ADP-implied VOR; positive = the
    player beat their draft slot (the crowd under-drafted his kind).
    """
    slots = slots or RosterSlots()
    ids = con.execute("SELECT gsis_id, draft_year FROM player_ids WHERE gsis_id IS NOT NULL").df()
    frames = [_season_rows(con, int(s), ids, slots, n_teams, max_adp, ruleset) for s in seasons]
    panel = pd.concat([f for f in frames if not f.empty], ignore_index=True)
    panel = panel.dropna(subset=["pos_rank", "realized_vor"]).reset_index(drop=True)
    panel["adp_stdev"] = panel["adp_stdev"].fillna(panel["adp_stdev"].median())

    panel["adp_implied_vor"] = _loso_isotonic_baseline(panel)
    panel["alpha"] = panel["realized_vor"] - panel["adp_implied_vor"]
    return panel
