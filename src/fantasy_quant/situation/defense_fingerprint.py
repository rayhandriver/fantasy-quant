"""Phase 0.13.8 — the **defensive fingerprint**, and the widened offensive one.

T48's whole content was that ``situation/fingerprint.py``'s apparatus — within-season z-scoring,
empirical-Bayes shrinkage by regime length, PARTIAL-season handling — had **no defensive
counterpart to run on**, because ``coaches.csv`` is offense-only. 0.13.1 built the subject and
0.13.7 built the metrics; this module is the two meeting.

★ **The machinery is reused, not reimplemented.** ``fingerprint.eb_weights`` and
``fingerprint.fingerprints`` gained one optional ``metrics`` argument defaulting to the offensive
vector, so every existing caller is byte-identical and the defensive side passes its own vector to
the *same* method-of-moments shrinkage. The alternative — a parallel copy for defense — is how the
two sides drift apart, and this repo has the ``coaches.csv``/``defense_coaches.csv`` pair precisely
because only the **data** genuinely differs.

★ **Also widened: the offensive vector.** ``fingerprint.METRICS`` is 14 metrics off ``pbp`` +
``weekly`` only — it reads neither participation nor FTN nor NGS, so personnel groupings, motion,
play-action and formation were absent from it despite sitting in the store since DATA-1.
:data:`OFFENSE_SCHEME_METRICS` adds them from the 0.13.7 panel.

⚠ **DESCRIPTIVE ONLY**, consistent with ``fingerprint.py``'s own docstring and with DATA-2's rule
that this session builds no feature. There is **no FDR gate and no backtested-edge claim** here,
and nothing in ``draft/optimizer.py``, ``valuation/value_board.py`` or ``valuation/cost_report.py``
imports this module — :func:`assert_not_wired_into_the_optimizer` is the guard that keeps it that
way, because an unenforced "descriptive only" is a comment.

⚠ **Season grain, and PARTIAL regimes are dropped rather than averaged.** The offensive module pins
a partial regime to a week window; ``defense_coaches.csv`` has **no** PARTIAL rows (its inclusion
rule is majority-of-games, with excluded stints documented in an adjacent row's notes), so there is
nothing to pin and the safe side of *"averaging two coordinators' games into one fingerprint is the
easiest way to make the module lie"* is to fingerprint only the regimes the table asserts.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from fantasy_quant.situation import defense_coaches, fingerprint

log = logging.getLogger(__name__)

#: The defensive fingerprint vector, from ``team_scheme_season``. Front, pressure, coverage and
#: the safety proxy — the four axes the user's ask names, in the order he named them.
DEFENSE_METRICS: tuple[str, ...] = (
    # front / personnel
    "share_base", "share_nickel", "share_dime", "dl_mean", "lb_mean", "db_mean",
    "box_mean", "share_box_8plus",
    # pressure
    "blitz_rate", "big_blitz_rate", "rush3_rate", "rushers_mean", "pressure_rate",
    # coverage (2018+ — the per-column floor, and the reason these shrink harder)
    "man_share", "share_cover_1", "share_cover_2", "share_cover_3", "share_cover_4",
    # the secondary proxy (a PERSONNEL proxy, never alignment)
    "proxy_safeties_mean", "proxy_single_high_share", "proxy_two_high_share",
)

#: The metrics the offensive vector was missing. Deliberately **additive** to
#: ``fingerprint.METRICS`` rather than a replacement — the existing 14 are validated and consumed.
OFFENSE_SCHEME_METRICS: tuple[str, ...] = (
    "share_p11", "share_p12", "share_p21", "share_p13",
    "share_shotgun", "share_empty", "share_under_center", "share_i_form",
    "rb_mean", "te_mean", "wr_mean",
    "no_huddle_rate", "pass_rate_neutral", "pass_oe_mean",
    # FTN, 2022+ — one DEV season, descriptive only, and they shrink almost to the league mean
    # because a one-season regime carries almost no weight. That is the correct behaviour, not a
    # bug: the shrinkage is what stops a single charted season reading as a coach's identity.
    "motion_rate", "play_action_rate", "rpo_rate", "screen_rate",
)

PANEL_TABLE = "team_scheme_season"


def load_panel(con, metrics: tuple[str, ...], seasons: tuple[int, ...] | None = None
               ) -> pd.DataFrame:
    """The 0.13.7 season panel, restricted to the metric columns a fingerprint needs."""
    cols = ", ".join(("season", "team", *metrics))
    where = f"where season in {tuple(seasons)}" if seasons else ""
    return con.execute(f"select {cols} from {PANEL_TABLE} {where}").df()


def league_moments(panel: pd.DataFrame, metrics: tuple[str, ...]) -> pd.DataFrame:
    """Per-season league mean and sd of each metric — the z reference.

    Mirrors ``fingerprint.league_moments`` exactly, over the panel instead of the profile frame:
    always **whole** seasons, so a regime is never compared against a partial league.
    """
    g = panel.groupby("season")[list(metrics)]
    return g.mean().add_suffix("_mean").join(g.std(ddof=0).add_suffix("_sd")).reset_index()


def regime_profiles(panel: pd.DataFrame, coaches: pd.DataFrame, mom: pd.DataFrame,
                    metrics: tuple[str, ...]) -> pd.DataFrame:
    """One z-scored row per (play_caller, team, season) the coaches table asserts.

    ★ **The coaches tables are keyed on ``LAR``; the panel is keyed on ``LA``.** Both
    ``coaches.csv`` and ``defense_coaches.csv`` use the ADP-side franchise canon, and everything
    derived from ``pbp`` uses the pbp-side one (``data/teams.py``). Without the canonization below,
    **six LAR defensive regime-seasons (2020-2025) and every McVay-era offensive one vanish** —
    which is the identical failure ``fingerprint.assert_regime_coverage``'s docstring already
    records, met a second time by the person who had just read it.

    ⚠ And it passed the guard, which is the more useful half of the lesson: the drop carried the
    reason *"no panel row for this team-season"*, which is **true, available for every possible
    drop, and therefore not a reason at all.** A drop is only legitimate here if the season is
    below the panel's own floor; :func:`assert_regime_coverage` now checks that instead of
    checking that a string is non-empty.
    """
    from fantasy_quant.data.teams import PBP_ALIAS

    mom_i = mom.set_index("season")
    p_i = panel.set_index(["season", "team"])
    rows = []
    for r in coaches[coaches["season"] < 2026].itertuples():
        team = PBP_ALIAS.get(str(r.team).upper(), str(r.team).upper())
        key = (int(r.season), team)
        if key not in p_i.index or int(r.season) not in mom_i.index:
            rows.append({"play_caller": str(r.play_caller), "team": team,
                         "team_as_written": str(r.team), "season": int(r.season),
                         "dropped": True,
                         "drop_reason": "season is below the panel floor"
                                        if int(r.season) < int(panel["season"].min())
                                        else "NO PANEL ROW — this is a join failure, not a floor"})
            continue
        vals = p_i.loc[key]
        z = {"play_caller": str(r.play_caller), "team": team,
             "team_as_written": str(r.team), "season": int(r.season),
             "partial": False, "n_weeks": 0, "dropped": False, "drop_reason": "",
             "confidence": str(getattr(r, "confidence", "")),
             "hc_calls_defense": int(getattr(r, "hc_calls_defense", 0) or 0)}
        for c in metrics:
            sd = mom_i.at[int(r.season), f"{c}_sd"]
            mean = mom_i.at[int(r.season), f"{c}_mean"]
            v = float(vals[c]) if pd.notna(vals[c]) else np.nan
            z[c] = (v - mean) / sd if sd and np.isfinite(v) else np.nan
        rows.append(z)
    return pd.DataFrame(rows)


def build_defense_fingerprints(con, seasons: tuple[int, ...] | None = None
                               ) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    """The deliverable: EB-shrunk defensive fingerprints, one row per defensive play-caller."""
    coaches = defense_coaches.load_defense_coaches()
    panel = load_panel(con, DEFENSE_METRICS, seasons)
    mom = league_moments(panel, DEFENSE_METRICS)
    rp = regime_profiles(panel, coaches, mom, DEFENSE_METRICS)
    kept = rp[~rp["dropped"]].copy()
    k = fingerprint.eb_weights(kept, DEFENSE_METRICS)
    fp = fingerprint.fingerprints(kept, k, by=("play_caller",), metrics=DEFENSE_METRICS)
    return fp, rp, k


def build_offense_scheme_fingerprints(con, seasons: tuple[int, ...] | None = None
                                      ) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    """The **widened** offensive fingerprint — the personnel/formation/FTN metrics fingerprint.py
    never read. Keyed to ``coaches.csv``'s offensive play-callers."""
    from fantasy_quant.situation import coaches as off_coaches

    coaches = off_coaches.load_coaches()
    panel = load_panel(con, OFFENSE_SCHEME_METRICS, seasons)
    mom = league_moments(panel, OFFENSE_SCHEME_METRICS)
    rp = regime_profiles(panel, coaches, mom, OFFENSE_SCHEME_METRICS)
    kept = rp[~rp["dropped"]].copy()
    k = fingerprint.eb_weights(kept, OFFENSE_SCHEME_METRICS)
    fp = fingerprint.fingerprints(kept, k, by=("play_caller",),
                                  metrics=OFFENSE_SCHEME_METRICS)
    return fp, rp, k


def coverage_report(rp: pd.DataFrame) -> pd.DataFrame:
    """How much history each play-caller actually has — the honest denominator of a fingerprint.

    0.13.1 signed off 27 of 32 2026 play-callers with prior history and **5 with none**. A
    fingerprint table that lists everyone hides that; this counts it.
    """
    kept = rp[~rp["dropped"]]
    g = kept.groupby("play_caller").agg(
        n_seasons=("season", "nunique"),
        teams=("team", lambda s: ",".join(sorted(set(s)))),
        first_season=("season", "min"),
        last_season=("season", "max"),
    ).reset_index()
    return g.sort_values(["n_seasons", "play_caller"], ascending=[False, True])


def assert_regime_coverage(rp: pd.DataFrame, panel_floor: int) -> None:
    """★ A regime-season may only be dropped because it is **below the panel's floor**.

    ``fingerprint.py``'s version asks for a non-empty ``drop_reason``, and this module shipped one
    that satisfied it while silently losing six LAR seasons to a franchise-code mismatch: *"no
    panel row for this team-season"* is true of every possible drop, so it distinguishes a floor
    from a join failure not at all. **A reason that is always available is not a reason** — the
    check has to be against something that can be false.
    """
    illegitimate = rp[rp["dropped"] & (rp["season"] >= panel_floor)]
    assert illegitimate.empty, (
        "regime-seasons dropped ABOVE the panel floor — the coaches table did not join the "
        "panel (check the franchise canon: the coaches CSVs are LAR-keyed, the panel is LA-keyed): "
        + ", ".join(f"{r.season} {r.team} {r.play_caller}"
                    for r in illegitimate.itertuples())
    )


def assert_not_wired_into_the_optimizer() -> None:
    """★ 'Descriptive only' as a **guard**, not a comment (UI-1's lesson 4).

    DATA-2 builds no feature, and 0.13.8 is the substep most likely to be quietly promoted into
    one — it produces exactly the kind of per-coach vector an optimizer would like. This asserts
    that the three frozen consumers do not import it. If a future session wants the wiring, it
    deletes this assertion **deliberately**, which is the point.
    """
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    forbidden = ("draft/optimizer.py", "valuation/value_board.py", "valuation/cost_report.py")
    offenders = []
    for rel in forbidden:
        path = root / rel
        if not path.exists():
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""] + [a.name for a in node.names]
            if any("defense_fingerprint" in n for n in names):
                offenders.append(rel)
    assert not offenders, (
        f"defense_fingerprint is descriptive-only and must not feed the frozen value stack, "
        f"but it is imported by: {sorted(set(offenders))}"
    )
