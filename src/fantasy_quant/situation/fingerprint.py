"""Phase 16.4 — play-caller **scheme fingerprints** and their **transport** onto 2026 rosters.

A *fingerprint* is what a play-caller's offense looks like once you strip out the league year:
how often he throws, how early, how fast, how deep, how much he concentrates the backfield and
the target tree. A *transport* asks the descriptive question this phase exists for — **if this
man's offense arrives here, which way does each role move?**

Three things make it honest rather than a horoscope:

* **Everything is z-scored within season** before it is aggregated. League pass rate and pace
  drift a lot over 2014-2025; a raw average across a coach's seasons would read that drift as
  personality. A fingerprint is therefore always *relative to the league that year*.
* **Empirical-Bayes shrinkage toward the league baseline**, per metric, by regime length. A
  one-season regime barely moves off league average; Andy Reid's twelve are nearly raw. The
  weight is estimated from the data (method of moments on within- vs between-regime variance),
  not picked by hand.
* **Partial regimes are cut to the weeks the coach actually called plays.** Six seasons in
  `reference/coaches.csv` are flagged PARTIAL/SPLIT with a pinnable window (see
  :data:`PARTIAL_WEEKS`); three more are flagged but too vague to pin and are dropped outright
  (:data:`UNRESOLVED_PARTIAL`). Averaging two coaches' games into one fingerprint would be the
  easiest way to make this module lie.

**Descriptive only.** No FDR gate, no backtested-edge claim, no baseline to beat — the sample of
clean transport events is far too thin for that bar, and BUILD_PLAN scopes it accordingly. Output
is a hypothesis to look at, not a recommendation. Nothing here is wired into `draft/optimizer.py`,
`valuation/value_board.py` or `valuation/cost_report.py`; the module reads `pbp`, `weekly`,
`adp_snapshots` and `consensus_projections` and writes nothing back.

Reads the reviewed table via :mod:`situation.coaches` — ask `coaches.fingerprint_source` what to
fingerprint each team on rather than re-deriving it from the `in_house` flag.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fantasy_quant.adp.panel import _canon_team

POSITIONS: tuple[str, ...] = ("QB", "RB", "WR", "TE")

#: The fingerprint vector. Team-level scheme traits first, then the role-share split.
#: `*_hhi` are Herfindahl concentrations — the bellcow-vs-committee axis, which is the single
#: most fantasy-relevant thing a play-caller does with a backfield.
TEAM_METRICS: tuple[str, ...] = (
    "pass_rate", "early_down_pass_rate", "plays_pg", "rz_pass_rate", "team_adot",
)
ROLE_METRICS: tuple[str, ...] = (
    "wr1_tgt_share", "wr2_tgt_share", "wr3_tgt_share", "te1_tgt_share", "rb_tgt_share",
    "rb1_carry_share", "rb2_carry_share", "tgt_hhi", "carry_hhi",
)
METRICS: tuple[str, ...] = TEAM_METRICS + ROLE_METRICS

#: Seasons where the listed play-caller only called part of the year, with a window we can pin
#: from the row's own `notes`. Specs resolve against the weeks the team **actually played**, so
#: byes never shift a boundary: ``("first", n)`` / ``("last", n)`` take that many played weeks,
#: ``("weeks", lo, hi)`` takes an explicit inclusive range.
#:
#: NB the IND entry is keyed to **2022**: the note documenting it sits on the 2021 row ("2022
#: PARTIAL: fired in early November after 9 of 17 games"), and 2021 itself was a full season.
PARTIAL_WEEKS: dict[tuple[int, str, str], tuple] = {
    (2018, "CLE", "Freddie Kitchens"): ("last", 8),
    (2018, "GB", "Mike McCarthy"): ("first", 12),
    (2019, "LAC", "Shane Steichen"): ("weeks", 9, 17),
    (2020, "CHI", "Matt Nagy"): ("first", 9),
    (2022, "IND", "Frank Reich"): ("first", 9),
    # Reich called 1-6, handed off for three games, took them back, then was fired after 12.
    # Only the opening window is unambiguous; the reclaimed stretch is dropped with the rest.
    (2023, "CAR", "Frank Reich"): ("weeks", 1, 6),
}

#: Flagged PARTIAL/SPLIT but with no pinnable boundary — excluded from fingerprints entirely
#: rather than guessed at. Value = why, so the exclusion is auditable.
UNRESOLVED_PARTIAL: dict[tuple[int, str, str], str] = {
    (2021, "CAR", "Joe Brady"): "note says '~13 of 17' — approximate, no pinnable boundary",
    (2025, "DET", "John Morton"): "split season, no game count in the note",
    (2025, "LV", "Chip Kelly"): "split season, no game count in the note",
}


# ------------------------------------------------------------------------------------------------
# the two warehouse reads (week grain, so a partial regime can be cut to its own games)
# ------------------------------------------------------------------------------------------------
def team_week_tendencies(con, seasons=None) -> pd.DataFrame:
    """Per (team, season, week) play-calling tendencies from ``pbp``.

    Definitions deliberately mirror `features/environment.py` (3.4) so that an unrestricted
    16.4 team-season reconciles with the Phase-3 environment feature — a test asserts it.
    """
    where = ""
    if seasons is not None:
        where = f"AND season IN ({', '.join(str(int(s)) for s in seasons)})"
    sql = f"""
        SELECT posteam AS team, season, week,
               SUM(CASE WHEN pass=1 THEN 1 ELSE 0 END) AS pass_plays,
               SUM(CASE WHEN rush=1 THEN 1 ELSE 0 END) AS rush_plays,
               SUM(CASE WHEN pass=1 AND down IN (1,2) THEN 1 ELSE 0 END) AS ed_pass,
               SUM(CASE WHEN (pass=1 OR rush=1) AND down IN (1,2) THEN 1 ELSE 0 END) AS ed_plays,
               SUM(CASE WHEN pass=1 AND yardline_100 <= 20 THEN 1 ELSE 0 END) AS rz_pass,
               SUM(CASE WHEN rush=1 AND yardline_100 <= 20 THEN 1 ELSE 0 END) AS rz_rush,
               SUM(CASE WHEN pass=1 THEN COALESCE(air_yards, 0) ELSE 0 END) AS air_yards,
               SUM(CASE WHEN pass_attempt=1 THEN 1 ELSE 0 END) AS pass_atts
        FROM pbp
        WHERE season_type='REG' AND posteam IS NOT NULL AND (pass=1 OR rush=1) {where}
        GROUP BY posteam, season, week
    """
    df = con.execute(sql).df()
    # pbp/weekly say LA, `reference/coaches.csv` says LAR — collapse to the project's canonical
    # token before anything joins on team, or Sean McVay silently has no seasons at all.
    df["team"] = _canon_team(df["team"]).astype(str)
    return df


def player_week_usage(con, seasons=None) -> pd.DataFrame:
    """Per (gsis_id, team, season, week) targets/carries for skill players, from ``weekly``."""
    where = ""
    if seasons is not None:
        where = f"AND season IN ({', '.join(str(int(s)) for s in seasons)})"
    sql = f"""
        SELECT gsis_id, player_display_name AS player, position,
               recent_team AS team, season, week,
               COALESCE(targets, 0) AS targets, COALESCE(carries, 0) AS carries
        FROM weekly
        WHERE season_type='REG' AND gsis_id IS NOT NULL AND recent_team IS NOT NULL
              AND position IN ('QB','RB','WR','TE') {where}
    """
    df = con.execute(sql).df()
    df["team"] = _canon_team(df["team"]).astype(str)
    return df


# ------------------------------------------------------------------------------------------------
# week selection
# ------------------------------------------------------------------------------------------------
def resolve_weeks(spec: tuple, played: list[int]) -> list[int]:
    """Turn a :data:`PARTIAL_WEEKS` spec into concrete weeks, given the weeks actually played."""
    played = sorted(played)
    kind = spec[0]
    if kind == "first":
        return played[: int(spec[1])]
    if kind == "last":
        return played[-int(spec[1]):]
    if kind == "weeks":
        lo, hi = int(spec[1]), int(spec[2])
        return [w for w in played if lo <= w <= hi]
    raise ValueError(f"unknown week spec {spec!r}")


def regime_season_weeks(tend: pd.DataFrame, season: int, team: str,
                        play_caller: str) -> list[int] | None:
    """The weeks of (season, team) that belong to `play_caller`.

    ``None`` means "drop this season" — it is flagged partial with no pinnable window.
    """
    key = (int(season), str(team), str(play_caller))
    if key in UNRESOLVED_PARTIAL:
        return None
    played = tend.loc[(tend["season"] == season) & (tend["team"] == team), "week"].tolist()
    if not played:
        return None
    if key in PARTIAL_WEEKS:
        return resolve_weeks(PARTIAL_WEEKS[key], played)
    return sorted(played)


# ------------------------------------------------------------------------------------------------
# the profile of one (team, season), optionally cut to a week window
# ------------------------------------------------------------------------------------------------
def team_season_profile(tend: pd.DataFrame, usage: pd.DataFrame, season: int, team: str,
                        weeks: list[int] | None = None) -> dict[str, float]:
    """The raw (un-normalized) :data:`METRICS` vector for one team-season or week window."""
    t = tend[(tend["season"] == season) & (tend["team"] == team)]
    u = usage[(usage["season"] == season) & (usage["team"] == team)]
    if weeks is not None:
        t, u = t[t["week"].isin(weeks)], u[u["week"].isin(weeks)]
    if t.empty:
        return {}

    plays = float(t["pass_plays"].sum() + t["rush_plays"].sum())
    ed = float(t["ed_plays"].sum())
    rz = float(t["rz_pass"].sum() + t["rz_rush"].sum())
    atts = float(t["pass_atts"].sum())
    out = {
        "pass_rate": float(t["pass_plays"].sum()) / plays if plays else np.nan,
        "early_down_pass_rate": float(t["ed_pass"].sum()) / ed if ed else np.nan,
        "plays_pg": plays / max(len(t), 1),
        "rz_pass_rate": float(t["rz_pass"].sum()) / rz if rz else np.nan,
        "team_adot": float(t["air_yards"].sum()) / atts if atts else np.nan,
    }

    tot_t = float(u["targets"].sum())
    tot_c = float(u["carries"].sum())
    by = u.groupby(["gsis_id", "position"], as_index=False)[["targets", "carries"]].sum()

    def _slot(pos: str, col: str, rank: int, total: float) -> float:
        if total <= 0:
            return np.nan
        s = by[by["position"] == pos].sort_values(col, ascending=False)[col]
        return float(s.iloc[rank - 1]) / total if len(s) >= rank else 0.0

    out["wr1_tgt_share"] = _slot("WR", "targets", 1, tot_t)
    out["wr2_tgt_share"] = _slot("WR", "targets", 2, tot_t)
    out["wr3_tgt_share"] = _slot("WR", "targets", 3, tot_t)
    out["te1_tgt_share"] = _slot("TE", "targets", 1, tot_t)
    out["rb1_carry_share"] = _slot("RB", "carries", 1, tot_c)
    out["rb2_carry_share"] = _slot("RB", "carries", 2, tot_c)
    rb_t = float(by.loc[by["position"] == "RB", "targets"].sum())
    out["rb_tgt_share"] = rb_t / tot_t if tot_t > 0 else np.nan
    out["tgt_hhi"] = _hhi(by["targets"], tot_t)
    out["carry_hhi"] = _hhi(by["carries"], tot_c)
    out["weeks"] = float(len(t))
    return out


def _hhi(counts: pd.Series, total: float) -> float:
    """Herfindahl concentration of a usage column: 1.0 = one man gets everything."""
    if total <= 0:
        return np.nan
    sh = counts.to_numpy(dtype=float) / total
    return float(np.sum(sh * sh))


# ------------------------------------------------------------------------------------------------
# league normalization + regime aggregation
# ------------------------------------------------------------------------------------------------
def league_profiles(tend: pd.DataFrame, usage: pd.DataFrame) -> pd.DataFrame:
    """Full-season profiles for **every** team-season — the league baseline each z is taken against.

    Always whole seasons: the baseline is "what a team looked like that year", so cutting it to a
    coach's window would compare a partial regime against a partial league.
    """
    rows = []
    for (season, team), _ in tend.groupby(["season", "team"]):
        p = team_season_profile(tend, usage, season, team)
        if p:
            rows.append({"season": int(season), "team": str(team), **p})
    return pd.DataFrame(rows)


def league_moments(prof: pd.DataFrame) -> pd.DataFrame:
    """Per-season league mean and sd of each metric (the z reference, and the un-z for levels)."""
    g = prof.groupby("season")[list(METRICS)]
    out = g.mean().add_suffix("_mean").join(g.std(ddof=0).add_suffix("_sd"))
    return out.reset_index()


def zscore(prof: pd.DataFrame, mom: pd.DataFrame) -> pd.DataFrame:
    """Within-season z-scores of `prof`, so league-year drift never reads as personality."""
    out = prof[["season", "team"]].copy()
    m = prof.merge(mom, on="season", how="left")
    for c in METRICS:
        sd = m[f"{c}_sd"].replace(0, np.nan)
        out[c] = (m[c] - m[f"{c}_mean"]) / sd
    return out


def regime_season_table(coaches: pd.DataFrame, tend: pd.DataFrame) -> pd.DataFrame:
    """Every (play_caller, team, season) the fingerprints are built from, with its week window.

    `dropped` rows are the unpinnable partial regimes; they are reported, not silently removed.
    """
    rows = []
    for r in coaches[coaches["season"] < 2026].itertuples():
        weeks = regime_season_weeks(tend, int(r.season), str(r.team), str(r.play_caller))
        key = (int(r.season), str(r.team), str(r.play_caller))
        rows.append({
            "play_caller": str(r.play_caller), "team": str(r.team), "season": int(r.season),
            "weeks": None if weeks is None else weeks,
            "n_weeks": 0 if weeks is None else len(weeks),
            "partial": key in PARTIAL_WEEKS,
            "dropped": weeks is None,
            "drop_reason": UNRESOLVED_PARTIAL.get(key, ""),
        })
    return pd.DataFrame(rows)


def regime_profiles(rst: pd.DataFrame, tend: pd.DataFrame, usage: pd.DataFrame,
                    mom: pd.DataFrame) -> pd.DataFrame:
    """One z-scored row per kept (play_caller, team, season), cut to that regime's own weeks."""
    rows = []
    mom_i = mom.set_index("season")
    for r in rst[~rst["dropped"]].itertuples():
        p = team_season_profile(tend, usage, r.season, r.team, weeks=r.weeks)
        if not p or r.season not in mom_i.index:
            continue
        z = {"play_caller": r.play_caller, "team": r.team, "season": r.season,
             "partial": r.partial, "n_weeks": r.n_weeks}
        for c in METRICS:
            sd = mom_i.at[r.season, f"{c}_sd"]
            z[c] = (p[c] - mom_i.at[r.season, f"{c}_mean"]) / sd if sd else np.nan
        rows.append(z)
    return pd.DataFrame(rows)


def eb_weights(rp: pd.DataFrame, metrics: tuple[str, ...] = METRICS) -> dict[str, float]:
    """Per-metric shrinkage constant ``k = sigma^2 / tau^2`` by method of moments.

    `sigma^2` is season-to-season noise **within** a play-caller, `tau^2` the spread of true
    play-caller means. A regime of length n then keeps weight ``n / (n + k)``: one season of a
    noisy metric is mostly league average, a long tenure is nearly raw.

    `metrics` defaults to the offensive vector, so every existing caller is unchanged; 0.13.8
    passes the **defensive** vector to run the identical shrinkage on the other side of the ball.
    """
    out = {}
    for c in metrics:
        g = rp.groupby("play_caller")[c]
        within = g.var(ddof=1).dropna()
        n = g.count()
        sigma2 = float(within.mean()) if len(within) else 1.0
        means = g.mean().dropna()
        between = float(means.var(ddof=1)) if len(means) > 1 else 0.0
        n_bar = float(n[n > 0].mean()) if len(n) else 1.0
        tau2 = max(between - sigma2 / max(n_bar, 1.0), 1e-3)
        out[c] = float(max(sigma2, 1e-6) / tau2)
    return out


def fingerprints(rp: pd.DataFrame, k: dict[str, float] | None = None,
                 by: tuple[str, ...] = ("play_caller",),
                 metrics: tuple[str, ...] = METRICS) -> pd.DataFrame:
    """The deliverable: one EB-shrunk fingerprint per group, plus the raw mean and n.

    Columns: `<by> · n_seasons · teams · <metric> (shrunk) · <metric>_raw · <metric>_w`.

    `by` defaults to the **play-caller**, pooling his spells at different teams — the same grain
    `coaches.coverage`/`fingerprint_source` count prior seasons at, so `prior_seasons` and
    `n_seasons` mean the same thing. Pass `("play_caller", "team")` for the per-spell table.
    """
    k = eb_weights(rp, metrics) if k is None else k
    rows = []
    for key, g in rp.groupby(list(by)):
        key = key if isinstance(key, tuple) else (key,)
        row = {**dict(zip(by, key, strict=True)), "n_seasons": int(len(g)),
               "teams": ",".join(sorted(g["team"].unique())),
               "seasons": ",".join(str(s) for s in sorted(g["season"].unique())),
               "any_partial": bool(g["partial"].any())}
        for c in metrics:
            vals = g[c].dropna()
            n = len(vals)
            raw = float(vals.mean()) if n else np.nan
            w = n / (n + k[c]) if n else 0.0
            row[f"{c}_raw"] = raw
            row[f"{c}_w"] = float(w)
            row[c] = float(raw * w) if n else np.nan
        rows.append(row)
    return pd.DataFrame(rows).sort_values(list(by)).reset_index(drop=True)


# ------------------------------------------------------------------------------------------------
# transport
# ------------------------------------------------------------------------------------------------
def transport(fp: pd.DataFrame, zs: pd.DataFrame, src: pd.DataFrame, season: int,
              baseline_season: int | None = None) -> pd.DataFrame:
    """Team-level transport for `season`'s new regimes: incoming fingerprint minus the team's own
    most recent realized profile, per metric, in z units.

    Where the fingerprint comes from a **mentor** (a first-time play-caller) and that mentor is not
    the team's own outgoing caller, the continuity reading is a genuinely different prior — so the
    row carries `alt_*` columns for the outgoing caller's fingerprint and the caller is expected to
    show both. `source == "none"` teams get a row with nothing filled in: silence, not a guess.
    """
    baseline_season = season - 1 if baseline_season is None else baseline_season
    base = zs[zs["season"] == baseline_season].set_index("team")
    fpi = fp.set_index("play_caller")
    rows = []
    for r in src[src["is_new_regime"]].itertuples():
        row = {"team": r.team, "play_caller": r.play_caller, "source": r.source,
               "fingerprint_on": r.fingerprint_on, "prior_seasons": int(r.prior_seasons),
               "same_team": r.same_team, "prev_play_caller": r.prev_play_caller,
               "baseline_season": baseline_season}
        on = r.fingerprint_on if r.source != "none" else None
        has = on is not None and on in fpi.index
        row["fingerprinted"] = bool(has)
        # A second, *disagreeing* prior: the mentor's lineage vs. who actually called here last
        # year. Only when they differ — at DEN and WAS the mentor is the outgoing caller (a
        # same-building promotion), so there is one reading, not two. NB `same_team` is a pandas
        # nullable boolean: `is not True` is wrong on np.bool_ and would fire on every row.
        same = False if pd.isna(r.same_team) else bool(r.same_team)
        alt = r.prev_play_caller if (r.source == "lineage" and not same) else None
        row["alt_prior_on"] = alt if (alt is not None and alt in fpi.index) else pd.NA
        for c in METRICS:
            inc = float(fpi.at[on, c]) if has else np.nan
            bl = float(base.at[r.team, c]) if r.team in base.index else np.nan
            row[f"{c}_in"] = inc
            row[f"{c}_base"] = bl
            row[f"{c}_delta"] = inc - bl
            row[f"{c}_alt"] = (float(fpi.at[row["alt_prior_on"], c])
                               if not pd.isna(row["alt_prior_on"]) else np.nan)
        rows.append(row)
    return pd.DataFrame(rows)


#: Which fingerprint metric governs each draftable role slot, by (position, depth rank).
SLOT_METRIC: dict[tuple[str, int], str] = {
    ("WR", 1): "wr1_tgt_share", ("WR", 2): "wr2_tgt_share", ("WR", 3): "wr3_tgt_share",
    ("TE", 1): "te1_tgt_share",
    ("RB", 1): "rb1_carry_share", ("RB", 2): "rb2_carry_share",
}


def depth_board(con, season: int, max_adp: float = 200.0) -> pd.DataFrame:
    """Draftable skill players with a **projected** depth rank inside their own team+position.

    Rank comes from the current ADP board, i.e. the market's read on the pecking order going into
    the draft — the only depth order that exists before a snap is played, and PIT-safe for `season`.
    """
    df = con.execute("""
        SELECT gsis_id, any_value(name) AS player, any_value(position) AS position,
               any_value(team) AS team, avg(adp) AS adp
        FROM adp_snapshots
        WHERE season = ? AND source = 'ffc' AND scoring = 'ppr' AND teams = 12
          AND snapshot_date = (SELECT max(snapshot_date) FROM adp_snapshots
                               WHERE season = ? AND source = 'ffc')
          AND gsis_id IS NOT NULL
        GROUP BY gsis_id
    """, [season, season]).df()
    if df.empty:
        raise ValueError(f"no {season} FFC ADP board — 16.4's player board needs a live board")
    df = df[df["position"].isin(POSITIONS) & (df["adp"] <= max_adp)].copy()
    df["team"] = _canon_team(df["team"]).astype(str)
    df["depth_rank"] = df.groupby(["team", "position"])["adp"].rank(method="first").astype(int)
    return df.sort_values("adp").reset_index(drop=True)


def player_board(con, tr: pd.DataFrame, fp: pd.DataFrame, prof: pd.DataFrame, mom: pd.DataFrame,
                 season: int, baseline_season: int | None = None,
                 max_adp: float = 200.0) -> pd.DataFrame:
    """Per-player transport readout for draftable players on `season`'s new-regime teams.

    Reports the role share the incoming scheme implies for that slot against what the team's own
    last season actually produced there — as a **percentage-point delta** and a unitless
    **implied multiplier**. Share units, never points: a points translation would read as an edit
    to the frozen projections, which this module is walled off from.
    """
    baseline_season = season - 1 if baseline_season is None else baseline_season
    bd = depth_board(con, season, max_adp=max_adp)
    fpi, momi = fp.set_index("play_caller"), mom.set_index("season")
    profi = prof[prof["season"] == baseline_season].set_index("team")
    tri = tr.set_index("team")
    rows = []
    for r in bd.itertuples():
        if r.team not in tri.index:
            continue
        t = tri.loc[r.team]
        metric = SLOT_METRIC.get((r.position, int(r.depth_rank)))
        if metric is None or not bool(t["fingerprinted"]):
            continue
        on = t["fingerprint_on"]
        if on not in fpi.index or r.team not in profi.index:
            continue
        mean, sd = momi.at[baseline_season, f"{metric}_mean"], momi.at[baseline_season,
                                                                       f"{metric}_sd"]
        z = float(fpi.at[on, metric])
        implied = float(mean + z * sd)                       # un-z back into share units
        actual = float(profi.at[r.team, metric])
        rows.append({
            "player": r.player, "position": r.position, "team": r.team, "adp": round(r.adp, 1),
            "depth_rank": int(r.depth_rank), "slot_metric": metric,
            "play_caller": t["play_caller"], "source": t["source"], "fingerprint_on": on,
            "prior_seasons": int(t["prior_seasons"]),
            "share_prev": actual, "share_league": float(mean), "share_implied": implied,
            "delta_pp": (implied - actual) * 100.0,
            # The split that keeps this honest. Most of `delta_pp` is usually NOT the new coach:
            # it is the incumbent slot regressing toward the league, which any hire would produce.
            # `scheme_pp` is the only part the fingerprint actually claims.
            "reversion_pp": (mean - actual) * 100.0,
            "scheme_pp": z * sd * 100.0,
            "scheme_z": z,
            "multiplier": implied / actual if actual > 0 else np.nan,
            "alt_prior_on": t["alt_prior_on"],
        })
    out = pd.DataFrame(rows)
    return out.sort_values("adp").reset_index(drop=True) if len(out) else out


# ------------------------------------------------------------------------------------------------
# gates
# ------------------------------------------------------------------------------------------------
def assert_fingerprints_sane(fp: pd.DataFrame,
                            metrics: tuple[str, ...] = METRICS) -> None:
    """Structural gate: shrinkage is a real contraction and nothing escaped to a silly z."""
    assert len(fp), "no fingerprints built"
    for c in metrics:
        w = fp[f"{c}_w"].to_numpy(dtype=float)
        assert ((w >= 0) & (w <= 1)).all(), f"{c}: shrink weight outside [0,1]"
        v = fp[c].to_numpy(dtype=float)
        v = v[np.isfinite(v)]
        assert len(v), f"{c}: every fingerprint is NaN"
        assert np.abs(v).max() <= 4.0, f"{c}: |shrunk z| > 4 — check the league normalization"
        raw = fp[f"{c}_raw"].to_numpy(dtype=float)
        ok = np.isfinite(raw) & np.isfinite(fp[c].to_numpy(dtype=float))
        assert (np.abs(fp[c].to_numpy(dtype=float)[ok]) <= np.abs(raw[ok]) + 1e-9).all(), \
            f"{c}: shrunk value is further from the league mean than the raw one"


def assert_regime_coverage(rst: pd.DataFrame) -> None:
    """Gate: a regime-season may only be dropped **for a stated reason**.

    An unexplained drop means the coaches table and the warehouse failed to join — which is how
    Sean McVay's entire nine-season Rams tenure went missing on the first run (`reference/
    coaches.csv` says LAR, `pbp` says LA). A silent join failure looks exactly like a coach who
    never worked, so it has to be an error rather than an empty row.
    """
    silent = rst[rst["dropped"] & (rst["drop_reason"].fillna("") == "")]
    assert silent.empty, (
        "regime-seasons dropped with no reason — the coaches table did not join the warehouse: "
        + ", ".join(f"{r.season} {r.team} {r.play_caller}" for r in silent.itertuples())
    )


def assert_transport_honest(tr: pd.DataFrame, src: pd.DataFrame) -> None:
    """Gate: every new regime is represented, and no team without a source gets a fingerprint."""
    want = set(src.loc[src["is_new_regime"], "team"])
    assert set(tr["team"]) == want, "transport dropped or invented a new-regime team"
    bad = tr[(tr["source"] == "none") & tr["fingerprinted"]]
    assert bad.empty, f"fingerprinted a team with no source: {list(bad['team'])}"
