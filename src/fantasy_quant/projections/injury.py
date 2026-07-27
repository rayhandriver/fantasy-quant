"""Phase 5.4 — availability: a discrete-time weekly hazard → games-played distribution.

The 4.4 calibration found the mean's biggest *level* miss isn't mis-ranking — it's **games-played
attrition**: projected players who lose chunks of the season to injury. Phase 5.1–5.3 model the
*if-healthy* season; this module models the **other factor** — how many games a player actually
plays — so the assembler can multiply the two and reproduce the honest, unconditional (draft-day)
distribution without double-counting the injury downside inside the healthy spread.

We fit a **discrete-time availability hazard**: on the player-week grid (one row per player per
team game week), a logistic regression of ``P(available that week)`` on age, position, prior-season
availability, and week — the discrete-time-survival formulation (a logit on person-period rows *is*
the hazard model, and it is the right tool for a 17-week horizon, vs. a continuous-time Cox). We
model **week-level availability** (players return from injury), not an absorbing first-injury
survival, because season-long games-played — not time-to-first-injury — is what the draft dial
needs.

Games-played is then a **Beta-Binomial** over the team's games: mean from the fitted availability,
with an empirically-estimated over-dispersion ``ρ`` so the distribution keeps the fat *lost-season*
tail (injuries are lumpy — a torn ACL zeroes the rest of the year — which a plain Binomial would
miss). PIT: fit on strictly-prior DEV seasons. Documented limitation: the grid conditions on ≥1
appearance, so a player who misses an *entire* season pre-Week-1 is under-counted (the 4.4
unconditional haircut partly covers it).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from fantasy_quant.config import DEV_SEASONS
from fantasy_quant.features import player as player_features_mod

SKILL = ("QB", "RB", "WR", "TE")
_CONT = ["age", "prior_avail", "week_norm"]
_POS_DUMMIES = ["is_RB", "is_WR", "is_TE"]        # QB is the reference level
FEATURES = _CONT + _POS_DUMMIES

# T3-A: draft-capital tier boundary for the rookie/backup availability cohort. ``draft_ovr`` ≤ this
# = a premium pick (roughly rounds 1–3 of a 32-team draft) whose lost-season tail differs from a
# late/undrafted flier's. Coarse on purpose — the sub-8-prior-games cohort is small (~30/season).
CAPITAL_HI_OVR = 100
_MIN_COHORT_CELL = 15                             # below this, a (pos, tier) cell backs off to pos


def _season_games(season: int) -> int:
    return 16 if int(season) < 2021 else 17


# --------------------------------------------------------------------------------------------
# the player-week availability grid
# --------------------------------------------------------------------------------------------
def _played(con, seasons) -> pd.DataFrame:
    ss = ",".join(str(int(s)) for s in seasons)
    return con.execute(
        f"""
        SELECT season, gsis_id, week, recent_team AS team, position
        FROM weekly
        WHERE season IN ({ss}) AND season_type='REG'
          AND position IN ('QB','RB','WR','TE') AND gsis_id IS NOT NULL
        """
    ).df()


def _team_weeks(con, seasons) -> pd.DataFrame:
    ss = ",".join(str(int(s)) for s in seasons)
    return con.execute(
        f"""SELECT DISTINCT season, recent_team AS team, week FROM weekly
            WHERE season IN ({ss}) AND season_type='REG'"""
    ).df()


def games_played(con, seasons) -> pd.DataFrame:
    """Per (season, player) primary team, position, games played and team games. One
    row/player-season."""
    played = _played(con, seasons)
    if played.empty:
        return pd.DataFrame(columns=["season", "player_key", "pos", "team", "games", "team_games"])
    # primary team & position by appearances
    prim = (played.groupby(["season", "gsis_id", "team", "position"]).size()
            .reset_index(name="g").sort_values("g")
            .groupby(["season", "gsis_id"]).tail(1)[["season", "gsis_id", "team", "position"]])
    gp = (played.groupby(["season", "gsis_id"])["week"].nunique().reset_index(name="games"))
    tw = _team_weeks(con, seasons).groupby(["season", "team"])["week"].nunique().reset_index(
        name="team_games")
    out = prim.merge(gp, on=["season", "gsis_id"]).merge(tw, on=["season", "team"], how="left")
    out = out.rename(columns={"gsis_id": "player_key", "position": "pos"})
    out["team_games"] = out["team_games"].fillna(out["season"].map(_season_games))
    return out


def availability_frame(con, seasons, min_prior_games: int = 8) -> pd.DataFrame:
    """The person-period grid: one row per player per team game week with ``available`` +
    covariates.

    ``available=1`` if the player recorded stats that week, else 0 (injury/inactive). Covariates:
    ``age`` (as-of season), position dummies, ``prior_avail`` (prior-season games/team-games),
    ``week_norm`` (week/season_games). PIT-safe: covariates predate outcomes.

    The universe is **established contributors** (prior-season games ≥ ``min_prior_games``): the
    availability multiplier applies to *projected starters*, so we model *their* injury attrition —
    not the roster-depth churn of 3rd-string players who never play (that would read as 20%
    "availability" and swamp the real injury signal). Rookies/backups fall to the
    median-availability fallback in the assembler.
    """
    played = _played(con, seasons)
    if played.empty:
        return pd.DataFrame(columns=["season", "player_key", "pos", "available", *FEATURES])
    prim = (played.groupby(["season", "gsis_id", "team", "position"]).size()
            .reset_index(name="g").sort_values("g")
            .groupby(["season", "gsis_id"]).tail(1)[["season", "gsis_id", "team", "position"]])
    played_set = set(zip(played["season"], played["gsis_id"], played["week"], strict=False))

    tw = _team_weeks(con, seasons)
    grid = prim.merge(tw, on=["season", "team"], how="left")   # player × their team's game weeks
    grid["available"] = [
        float((s, g, w) in played_set)
        for s, g, w in zip(grid["season"], grid["gsis_id"], grid["week"], strict=False)]

    # prior-season availability (durability persistence) + established-contributor gate
    prior = games_played(con, [s - 1 for s in seasons])
    prior["prior_avail"] = (prior["games"] / prior["team_games"]).clip(0, 1)
    prior["season"] = prior["season"] + 1          # value it in the following season
    prior = prior.rename(columns={"player_key": "gsis_id", "games": "prior_games"})
    grid = grid.merge(prior[["season", "gsis_id", "prior_avail", "prior_games"]],
                      on=["season", "gsis_id"], how="inner")       # drop non-contributors / rookies
    grid = grid[grid["prior_games"] >= min_prior_games]

    # age (as-of season) from player features
    ages = []
    for s in seasons:
        pf = player_features_mod.player_features(con, [int(s)])[["gsis_id", "age"]].copy()
        pf["season"] = int(s)
        ages.append(pf)
    age = pd.concat(ages, ignore_index=True)
    grid = grid.merge(age, on=["season", "gsis_id"], how="left")
    grid["age"] = grid["age"].fillna(grid["age"].median())

    grid["week_norm"] = grid["week"] / grid["season"].map(_season_games)
    for pos in ("RB", "WR", "TE"):
        grid[f"is_{pos}"] = (grid["position"] == pos).astype(float)
    return grid.rename(columns={"gsis_id": "player_key", "position": "pos"})[
        ["season", "player_key", "pos", "team", "week", "available", *FEATURES]]


def projected_availability_frame(con, season: int, min_prior_games: int = 8) -> pd.DataFrame:
    """T17 — the person-period grid for a season that has **not been played yet**.

    :func:`availability_frame` builds its grid from ``weekly``, so a future season yields nothing
    and every player falls to the T3-A cohort prior — a per-``(pos, tier)`` constant written for
    rookies and backups, applied to the whole league (see ``docs/TECH-DEBT.md`` T17). But the
    hazard's covariates do not actually need the target season to have happened: ``prior_avail``
    is last season's durability, ``age`` is arithmetic on a birthdate, the position dummies are
    known, and ``week_norm`` is the schedule. Only ``available`` — the *outcome* — is missing, and
    prediction does not need it.

    So this synthesizes the grid the target season *would* have: the established universe
    (``season - 1`` games ≥ ``min_prior_games``, the same gate :func:`availability_frame` applies)
    × the target season's weeks, carrying each player's prior-season team and primary position.
    ``available`` is ``NaN`` throughout and this frame must never be passed to
    :func:`fit_availability` — it is a prediction frame only.

    Players below the gate (rookies, backups, anyone who missed most of last season) are absent by
    design and still route to the cohort prior downstream, which is the population it was built
    for. Returns the same columns as :func:`availability_frame`.
    """
    cols = ["season", "player_key", "pos", "team", "week", "available", *FEATURES]
    prior = games_played(con, [int(season) - 1])
    if prior.empty:
        return pd.DataFrame(columns=cols)

    est = prior[prior["games"] >= min_prior_games].reset_index(drop=True).copy()
    if est.empty:
        return pd.DataFrame(columns=cols)
    est["prior_avail"] = (est["games"] / est["team_games"]).clip(0, 1)

    # the target season's own week count — so `team_games` downstream (a `week.nunique()`) is the
    # season being drafted, never the prior season's. This is why T17's "team_games must come from
    # the schedule" note needs no schedule ingest: the grid is built at the right width.
    n_weeks = _season_games(season)
    grid = est.loc[est.index.repeat(n_weeks)].reset_index(drop=True)
    grid["week"] = np.tile(np.arange(1, n_weeks + 1), len(est))
    grid["season"] = int(season)
    grid["week_norm"] = grid["week"] / n_weeks

    # age as-of Sep-1 of the TARGET season, straight from the crosswalk: `player_features` keys its
    # universe off `weekly`, so it is empty for an unplayed season, but a birthdate is not.
    bd = con.execute(
        """SELECT gsis_id AS player_key, MAX(birthdate) AS birthdate
           FROM player_ids WHERE gsis_id IS NOT NULL GROUP BY 1"""
    ).df()
    grid = grid.merge(bd, on="player_key", how="left")
    asof = pd.Timestamp(f"{int(season)}-09-01")
    grid["age"] = ((asof - pd.to_datetime(grid["birthdate"], errors="coerce")).dt.days
                   / 365.25).round(2)
    grid["age"] = grid["age"].fillna(grid["age"].median())

    for pos in ("RB", "WR", "TE"):
        grid[f"is_{pos}"] = (grid["pos"] == pos).astype(float)
    grid["available"] = np.nan          # no outcome exists yet — prediction frame only
    return grid[cols]


# --------------------------------------------------------------------------------------------
# the hazard model + dispersion (pure-ish)
# --------------------------------------------------------------------------------------------
def fit_availability(frame: pd.DataFrame, features=FEATURES) -> dict:
    """Logistic availability hazard on the person-period grid. Returns a scaler + model +
    features."""
    x = frame[features].to_numpy(float)
    y = frame["available"].to_numpy(float)
    scaler = StandardScaler().fit(x)
    model = LogisticRegression(C=1.0, max_iter=1000).fit(scaler.transform(x), y)
    return {"scaler": scaler, "model": model, "features": list(features)}


def predict_availability(fit: dict, frame: pd.DataFrame) -> np.ndarray:
    x = fit["scaler"].transform(frame[fit["features"]].to_numpy(float))
    return fit["model"].predict_proba(x)[:, 1]


def estimate_dispersion(games: np.ndarray, team_games: np.ndarray, p: np.ndarray) -> float:
    """Method-of-moments Beta-Binomial over-dispersion ``ρ`` from realized games vs predicted avail.

    Standardized residual ``r=(a−p)/√(p(1−p)/G)`` has ``E[r²]≈1+(G−1)ρ`` under Beta-Binomial, so
    ``ρ≈(mean r²−1)/(mean G−1)``. Clipped to ``[0, 0.5]``. Captures the lumpy lost-season tail.
    """
    g, G, p = (np.asarray(v, float) for v in (games, team_games, p))
    a = g / G
    var = np.clip(p * (1 - p) / G, 1e-9, None)
    r2 = ((a - p) ** 2 / var)
    rho = (np.nanmean(r2) - 1.0) / max(np.nanmean(G) - 1.0, 1.0)
    return float(np.clip(rho, 0.0, 0.5))


def sample_games(p: float, team_games: int, rho: float, rng: np.random.Generator,
                 n: int) -> np.ndarray:
    """Draw ``n`` games-played counts ~ Beta-Binomial(team_games, p, ρ). ρ=0 ⇒ plain Binomial."""
    p = float(np.clip(p, 1e-3, 1 - 1e-3))
    if rho <= 1e-6:
        return rng.binomial(team_games, p, size=n)
    conc = 1.0 / rho - 1.0
    pp = rng.beta(p * conc, (1 - p) * conc, size=n)
    return rng.binomial(team_games, pp)


# --------------------------------------------------------------------------------------------
# the PIT projection
# --------------------------------------------------------------------------------------------
def availability_projection(con, season: int, train_seasons=None) -> pd.DataFrame:
    """Per-player availability for ``season``: ``[player_key, pos, avail_p, games_played_mean,
    team_games, rho]``. Fits the hazard on strictly-prior DEV seasons; ``rho`` is shared (attached
    to every row for the sampler)."""
    if train_seasons is None:
        train_seasons = [s for s in DEV_SEASONS if s < season] or list(DEV_SEASONS)
    train = availability_frame(con, train_seasons)
    fit = fit_availability(train)

    # dispersion from realized games vs. per-player mean availability on the training seasons
    gp = games_played(con, train_seasons)
    per_player = (train.assign(p=predict_availability(fit, train))
                  .groupby(["season", "player_key"])["p"].mean().reset_index())
    gpm = gp.merge(per_player, on=["season", "player_key"], how="inner")
    rho = estimate_dispersion(gpm["games"].to_numpy(), gpm["team_games"].to_numpy(),
                              gpm["p"].to_numpy()) if len(gpm) else 0.15

    # target-season players: predict availability at each player's covariates (mean over the season)
    tgt = availability_frame(con, [season])
    source = "observed"
    if tgt.empty:
        # T17: the season has not been played, so there is no observed person-period grid. Roll the
        # covariates forward rather than dropping every player onto the cohort prior. The
        # substitution is stamped on the result (`covariate_source`) so it is visible, not silent.
        tgt = projected_availability_frame(con, season)
        source = "rolled_forward"
    if tgt.empty:
        return pd.DataFrame(columns=["player_key", "pos", "avail_p", "games_played_mean",
                                     "team_games", "rho", "covariate_source"])
    tgt = tgt.assign(p=predict_availability(fit, tgt))
    out = (tgt.groupby(["player_key", "pos"]).agg(
        avail_p=("p", "mean"), team_games=("week", "nunique")).reset_index())
    out["games_played_mean"] = out["avail_p"] * out["team_games"]
    out["rho"] = rho
    out["covariate_source"] = source
    return out


# --------------------------------------------------------------------------------------------
# T3-A — the rookie/backup availability cohort prior (the sub-gate universe the hazard drops)
# --------------------------------------------------------------------------------------------
def capital_tier(draft_ovr) -> pd.Series | str:
    """``'hi'`` for a premium pick (``draft_ovr`` ≤ :data:`CAPITAL_HI_OVR`), else ``'lo'`` — the
    coarse draft-capital split for the cohort prior. Vectorized over a Series or scalar."""
    ovr = pd.to_numeric(draft_ovr, errors="coerce")
    if np.isscalar(draft_ovr) or not hasattr(draft_ovr, "__len__"):
        return "hi" if (pd.notna(ovr) and ovr <= CAPITAL_HI_OVR) else "lo"
    return np.where(ovr <= CAPITAL_HI_OVR, "hi", "lo")


def player_tiers(con, seasons) -> pd.DataFrame:
    """Per ``(season, player_key)`` position + ``capital_tier`` for skill players — the routing key
    for the cohort prior (and, downstream, the role haircut)."""
    frames = []
    for s in seasons:
        pf = player_features_mod.player_features(con, [int(s)])[
            ["gsis_id", "position", "draft_ovr"]].copy()
        if pf.empty:
            # T17, second order: `player_features` keys its universe off `weekly`, so an unplayed
            # season yields nothing and every cohort player would be filled to the LOW capital
            # tier downstream — i.e. a first-round rookie RB priced as an undrafted flier, which
            # is the exact split the T3-A prior exists to make (hi 0.67 vs lo 0.42). Position and
            # draft capital are season-independent facts, so read them from the crosswalk.
            pf = con.execute(
                """SELECT gsis_id, ARG_MAX(position, db_season) AS position,
                          MAX(draft_ovr) AS draft_ovr
                   FROM player_ids
                   WHERE gsis_id IS NOT NULL AND position IN ('QB','RB','WR','TE')
                   GROUP BY gsis_id"""
            ).df()
        pf["season"] = int(s)
        frames.append(pf)
    pf = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["gsis_id", "position", "draft_ovr", "season"])
    pf["capital_tier"] = capital_tier(pf["draft_ovr"])
    return pf.rename(columns={"gsis_id": "player_key", "position": "pos"})[
        ["season", "player_key", "pos", "capital_tier"]]


def cohort_availability_prior(con, train_seasons, min_prior_games: int = 8,
                              min_cell: int = _MIN_COHORT_CELL) -> dict:
    """Availability prior for the **sub-gate cohort** (rookies + backups the hazard drops).

    Keyed on ``(pos, capital_tier)`` with a ``(pos, '*')`` and global ``('*', '*')`` backoff. Each
    cell returns the realized mean availability *fraction* ``avail_p`` **and** its Beta-Binomial
    over-dispersion ``rho`` (rookie RBs carry a fatter lost-season tail than the league median — the
    T3 downside the single shared fallback erased). PIT: estimated only on ``train_seasons``.
    """
    gp = games_played(con, train_seasons)
    if gp.empty:
        return {("*", "*"): {"avail_p": 0.85, "rho": 0.15, "n": 0}}
    prior = games_played(con, [s - 1 for s in train_seasons]).rename(
        columns={"games": "prior_games"})
    prior["season"] = prior["season"] + 1
    gp = gp.merge(prior[["season", "player_key", "prior_games"]],
                  on=["season", "player_key"], how="left")
    gp["prior_games"] = gp["prior_games"].fillna(0)                      # no prior row -> rookie
    cohort = gp[gp["prior_games"] < min_prior_games].copy()
    tiers = player_tiers(con, train_seasons)
    cohort = cohort.merge(tiers[["season", "player_key", "capital_tier"]],
                          on=["season", "player_key"], how="left")
    cohort["capital_tier"] = cohort["capital_tier"].fillna("lo")
    cohort["frac"] = (cohort["games"] / cohort["team_games"]).clip(0, 1)

    def _cell(grp: pd.DataFrame) -> dict:
        p = float(grp["frac"].mean())
        rho = estimate_dispersion(grp["games"].to_numpy(), grp["team_games"].to_numpy(),
                                  np.full(len(grp), p))
        return {"avail_p": p, "rho": rho, "n": int(len(grp))}

    out: dict = {("*", "*"): _cell(cohort)}
    for pos, g in cohort.groupby("pos"):
        out[(str(pos), "*")] = _cell(g)
    for (pos, tier), g in cohort.groupby(["pos", "capital_tier"]):
        if len(g) >= min_cell:
            out[(str(pos), str(tier))] = _cell(g)
    return out


def lookup_cohort(prior: dict, pos: str, tier: str) -> tuple[float, float]:
    """``(avail_p, rho)`` from a :func:`cohort_availability_prior` dict with
    (pos,tier)→(pos,*)→(*,*) backoff."""
    for key in ((str(pos), str(tier)), (str(pos), "*"), ("*", "*")):
        if key in prior:
            return prior[key]["avail_p"], prior[key]["rho"]
    return 0.85, 0.15


# --------------------------------------------------------------------------------------------
# T3-B — the role-survival haircut R (the dominant *unconditional* miss: active but demoted)
# --------------------------------------------------------------------------------------------
ROLE_TIERS = ("elite", "starter", "deep")
_KEEP_FLOOR = 0.05        # a washed-out player keeps *something*; never zero the whole draw
WASHOUT_AVAIL = 0.40      # played < 40% of team games = a washed-out season (benched/buried/hurt)


def role_tier(proj_rank, startable_rank: int) -> str:
    """Coarse projected-role tier from a within-position projection rank: ``elite`` (top half of
    the startable slots), ``starter`` (the rest of the startable slots), ``deep`` (beyond startable
    — the fringe body whose crater is the unconditional-coverage killer)."""
    if proj_rank <= 0.5 * startable_rank:
        return "elite"
    if proj_rank <= startable_rank:
        return "starter"
    return "deep"


def role_retention(con, train_seasons, min_cell: int = 20, ruleset=None) -> dict:
    """Per ``(pos, role_tier)`` role-loss parameters (T3-B): the probability a projected contributor
    has his **season go bad** and, when it does, how little he plays and produces.

    The empirical diagnosis (findings 2026-07-11) is that the dominant *unconditional* (draft-day)
    coverage miss is a projected body who **washes out** — benched, buried, or hurt — and plays a
    near-zero season, not one who plays a full slate at reduced per-game output. So role loss is
    modeled through the **availability channel**: a two-component season mixture where the "washout"
    branch draws games from a low ``crater_avail``. Because the washout branch *replaces* the normal
    (injury-hazard) branch rather than stacking on it, injury is never double-counted; and because
    it fires at the true (low, tier-specific) **washout** rate — not the higher below-replacement
    rate — it fattens the games≈0 left tail without dragging down the healthy upper tail (``q90``).
    Estimated on established, projected-fantasy-relevant players (prior-season points = the PIT
    projection proxy); a washout = played < :data:`WASHOUT_AVAIL` of the team's games:

    * ``p_crater`` = P(washout)
    * ``crater_avail`` = median realized games / team games among washed-out players (≈ 0.15)
    * ``keep_frac`` = median per-game realized/projected among washed-out players (production kept)

    Returns a dict keyed ``(pos, tier)`` with ``(pos, '*')`` → ``('*', '*')`` backoff.
    """
    from fantasy_quant.backtest import metrics, scoring
    from fantasy_quant.draft.simulator import RosterSlots

    ranks = metrics.replacement_ranks(RosterSlots(), n_teams=10)
    recs = []
    for s in train_seasons:
        prior = scoring.season_points(con, s - 1, ruleset)
        cur = scoring.season_points(con, s, ruleset)
        prior = prior[prior["position"].isin(SKILL)].copy()
        cur = cur[cur["position"].isin(SKILL)].copy()
        if prior.empty or cur.empty:
            continue
        prior["proj_rank"] = prior.groupby("position")["points"].rank(
            ascending=False, method="first")
        # only players who were fantasy-relevant last year (a meaningful projected level)
        prior = prior[prior.apply(lambda r: r["proj_rank"] <= 2 * ranks[r["position"]], axis=1)]
        gp = games_played(con, [s]).rename(columns={"player_key": "gsis_id"})
        m = prior.merge(cur[["gsis_id", "points"]], on="gsis_id", how="left",
                        suffixes=("_prior", "_cur"))
        m = m.merge(gp[["gsis_id", "games", "team_games"]], on="gsis_id", how="left")
        m["points_cur"] = m["points_cur"].fillna(0.0)
        m["avail"] = (m["games"] / m["team_games"]).clip(0, 1).fillna(0.0)  # never played -> 0
        for r in m.itertuples(index=False):
            pos = r.position
            tier = role_tier(r.proj_rank, ranks[pos])
            washout = r.avail < WASHOUT_AVAIL
            per_game_prior = r.points_prior / max(_season_games(s - 1), 1)
            per_game_cur = r.points_cur / max(r.games if r.games and r.games > 0 else np.nan, 1)
            keep = float(np.clip(np.nan_to_num(per_game_cur) / max(per_game_prior, 1e-6),
                                 _KEEP_FLOOR, 1.0))
            recs.append({"pos": pos, "tier": tier, "washout": washout,
                         "avail": r.avail, "keep": keep})

    df = pd.DataFrame(recs)
    if df.empty:
        return {("*", "*"): {"p_crater": 0.12, "crater_avail": 0.15, "keep_frac": 0.7, "n": 0}}

    def _cell(g: pd.DataFrame) -> dict:
        wo = g[g["washout"]]
        return {"p_crater": float(g["washout"].mean()),
                "crater_avail": float(wo["avail"].median()) if len(wo) else 0.15,
                "keep_frac": float(wo["keep"].median()) if len(wo) else 0.7,
                "n": int(len(g))}

    out: dict = {("*", "*"): _cell(df)}
    for pos, g in df.groupby("pos"):
        out[(str(pos), "*")] = _cell(g)
    for (pos, tier), g in df.groupby(["pos", "tier"]):
        if len(g) >= min_cell:
            out[(str(pos), str(tier))] = _cell(g)
    return out


def lookup_role(retention: dict, pos: str, tier: str) -> tuple[float, float, float]:
    """``(p_crater, crater_avail, keep_frac)`` from a :func:`role_retention` dict with
    (pos,tier)→(pos,*)→(*,*) backoff."""
    for key in ((str(pos), str(tier)), (str(pos), "*"), ("*", "*")):
        if key in retention:
            c = retention[key]
            return c["p_crater"], c["crater_avail"], c["keep_frac"]
    return 0.15, 0.35, 0.7
