"""The team-book **metric registry**: what each number means, where it comes from, when it starts.

One row per metric the book shows. The registry is the contract between the builders (which must
produce every key) and the site (which renders whatever the registry says), so a metric is added
in exactly one place.

★ **Three source families, and the family decides what a live season can carry.**

* ``pbp`` — computable from nflverse play-by-play alone. Available every season, including the one
  being played, refreshed nightly upstream.
* ``ftn`` — FTN charting (play-action, motion, RPO, screens, blitzers, box count). **2022+**, and
  also refreshed in-season.
* ``participation`` — the 22-man on-field record (personnel groupings, defensive fronts, coverage
  shells, man/zone, pressure). Published **after** the season (2025's file landed 2026-02-10), so a
  live season has none of it. These come from the frozen scheme panel, never recomputed here.

``construction`` (cap, age, continuity) is season-grain from ``team_construction_season``.

★ **Floors are per metric.** Coverage shells and man share start in **2018** (``defense_*_type`` is
empty before that), FTN in **2022**. Below its floor a metric is **NULL, never 0** — a team that
was never charted did not play zero man coverage (the T50 rule). ``tests/test_teambook.py`` checks
the participation floors against ``team_scheme_columns`` so the two cannot drift apart.

★ **Polarity** says which direction is good *for the team* (+1 higher, −1 lower, 0 = a tendency,
neither good nor bad). Only polar metrics get good/bad colouring on the site; a scheme tendency
such as 12-personnel share is coloured by distance from the league, never by "good".
"""

from __future__ import annotations

from dataclasses import dataclass

from fantasy_quant.data.sources.nflverse_release import SEASON_FLOORS

#: The first season the book covers. Charted coverage starts here, so every tab is full from 2018.
FIRST_SEASON = 2018

PBP, FTN, PARTICIPATION, CONSTRUCTION = "pbp", "ftn", "participation", "construction"
SOURCES = (PBP, FTN, PARTICIPATION, CONSTRUCTION)

#: participation columns whose own floor is later than the table's (T49). Everything else from
#: participation starts with the panel in 2016, i.e. before the book does.
CHARTED_COVERAGE_FLOOR = 2018


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    side: str            # offense | defense | special | construction
    group: str           # display section within the side
    source: str          # one of SOURCES
    fmt: str             # pct | rate3 | num1 | num2 | int | signed1
    polarity: int = 0    # +1 higher is good for the team, -1 lower is good, 0 a tendency
    scheme: bool = False  # used for "most similar team-seasons"
    note: str = ""

    @property
    def floor(self) -> int:
        if self.source == FTN:
            return SEASON_FLOORS["ftn_charting"]
        if self.source == PARTICIPATION and (self.key.startswith("share_cover_")
                                             or self.key in ("man_share", "share_2_man")):
            return CHARTED_COVERAGE_FLOOR
        return 2016


def _m(*args, **kw) -> Metric:
    return Metric(*args, **kw)


# --- offense ----------------------------------------------------------------------------------
OFFENSE: tuple[Metric, ...] = (
    _m("snaps_per_game", "Offensive snaps / game", "offense", "Volume & efficiency", PBP, "num1",
       note="Scrimmage plays (pass + run) per game played."),
    _m("dropbacks_per_game", "Dropbacks / game", "offense", "Volume & efficiency", PBP, "num1"),
    _m("epa_per_play", "EPA / play", "offense", "Volume & efficiency", PBP, "rate3", +1),
    _m("pass_epa", "EPA / dropback", "offense", "Volume & efficiency", PBP, "rate3", +1),
    _m("rush_epa", "EPA / rush", "offense", "Volume & efficiency", PBP, "rate3", +1),
    _m("success_rate", "Success rate", "offense", "Volume & efficiency", PBP, "pct", +1),
    _m("explosive_rate", "Explosive play rate", "offense", "Volume & efficiency", PBP, "pct", +1,
       note="Passes of 20+ yards and runs of 10+ yards, per play."),
    _m("pass_rate", "Pass rate", "offense", "Tendencies", PBP, "pct", scheme=True),
    _m("pass_rate_neutral", "Neutral-script pass rate", "offense", "Tendencies", PBP, "pct",
       scheme=True, note="Within one score, outside the final five minutes — the rate a team "
                         "chooses rather than the one the scoreboard forces."),
    _m("pass_oe_mean", "Pass rate over expected (PROE)", "offense", "Tendencies", PBP, "signed1",
       scheme=True,
       note="Percentage points above nflverse's expected pass rate for the situation."),
    _m("early_down_pass_rate", "Early-down pass rate", "offense", "Tendencies", PBP, "pct",
       scheme=True, note="1st and 2nd down, neutral script."),
    _m("shotgun_rate", "Shotgun rate", "offense", "Tendencies", PBP, "pct", scheme=True),
    _m("no_huddle_rate", "No-huddle rate", "offense", "Tendencies", PBP, "pct", scheme=True),
    _m("share_under_center", "Under-center rate", "offense", "Formation", PARTICIPATION, "pct",
       scheme=True),
    _m("share_singleback", "Singleback formation", "offense", "Formation", PARTICIPATION, "pct",
       scheme=True),
    _m("share_i_form", "I-formation", "offense", "Formation", PARTICIPATION, "pct", scheme=True),
    _m("share_pistol", "Pistol", "offense", "Formation", PARTICIPATION, "pct", scheme=True),
    _m("share_p11", "11 personnel", "offense", "Personnel", PARTICIPATION, "pct", scheme=True,
       note="1 RB · 1 TE · 3 WR."),
    _m("share_p12", "12 personnel", "offense", "Personnel", PARTICIPATION, "pct", scheme=True,
       note="1 RB · 2 TE · 2 WR."),
    _m("share_p13", "13 personnel", "offense", "Personnel", PARTICIPATION, "pct", scheme=True,
       note="1 RB · 3 TE · 1 WR."),
    _m("share_p21", "21 personnel", "offense", "Personnel", PARTICIPATION, "pct", scheme=True,
       note="2 RB · 1 TE · 2 WR."),
    _m("share_p22", "22 personnel", "offense", "Personnel", PARTICIPATION, "pct", scheme=True),
    _m("share_p10", "10 personnel", "offense", "Personnel", PARTICIPATION, "pct", scheme=True),
    _m("te_mean", "TEs on the field", "offense", "Personnel", PARTICIPATION, "num2", scheme=True),
    _m("wr_mean", "WRs on the field", "offense", "Personnel", PARTICIPATION, "num2", scheme=True),
    _m("motion_rate", "Pre-snap motion", "offense", "Play design", FTN, "pct", scheme=True),
    _m("play_action_rate", "Play-action rate", "offense", "Play design", FTN, "pct", scheme=True,
       note="Share of dropbacks."),
    _m("rpo_rate", "RPO rate", "offense", "Play design", FTN, "pct", scheme=True),
    _m("screen_rate", "Screen rate", "offense", "Play design", FTN, "pct", scheme=True,
       note="Share of dropbacks."),
    _m("qb_under_center_ftn", "QB under center (charted)", "offense", "Play design", FTN, "pct",
       scheme=True, note="FTN's QB alignment. Available in-season, unlike the participation "
                         "formation above."),
    _m("backfield_mean", "Backs in the backfield", "offense", "Play design", FTN, "num2",
       scheme=True),
)

# --- defense ----------------------------------------------------------------------------------
DEFENSE: tuple[Metric, ...] = (
    _m("def_epa_per_play", "EPA / play allowed", "defense", "Results allowed", PBP, "rate3", -1),
    _m("def_pass_epa", "EPA / dropback allowed", "defense", "Results allowed", PBP, "rate3", -1),
    _m("def_rush_epa", "EPA / rush allowed", "defense", "Results allowed", PBP, "rate3", -1),
    _m("def_success_rate", "Success rate allowed", "defense", "Results allowed", PBP, "pct", -1),
    _m("def_explosive_rate", "Explosive plays allowed", "defense", "Results allowed", PBP, "pct",
       -1),
    _m("def_sack_rate", "Sack rate", "defense", "Results allowed", PBP, "pct", +1,
       note="Sacks per opponent dropback."),
    _m("takeaways_per_game", "Takeaways / game", "defense", "Results allowed", PBP, "num2", +1),
    _m("opp_pass_rate", "Opponent pass rate", "defense", "Results allowed", PBP, "pct",
       note="How often offenses chose to throw on this defense."),
    _m("share_base", "Base (4 DB)", "defense", "Fronts & personnel", PARTICIPATION, "pct",
       scheme=True),
    _m("share_nickel", "Nickel (5 DB)", "defense", "Fronts & personnel", PARTICIPATION, "pct",
       scheme=True),
    _m("share_dime", "Dime (6+ DB)", "defense", "Fronts & personnel", PARTICIPATION, "pct",
       scheme=True),
    _m("dl_mean", "Defensive linemen on the field", "defense", "Fronts & personnel",
       PARTICIPATION, "num2", scheme=True),
    _m("lb_mean", "Linebackers on the field", "defense", "Fronts & personnel", PARTICIPATION,
       "num2", scheme=True),
    _m("man_share", "Man coverage", "defense", "Coverage", PARTICIPATION, "pct", scheme=True,
       note="Share of charted dropbacks."),
    _m("share_cover_0", "Cover 0", "defense", "Coverage", PARTICIPATION, "pct", scheme=True),
    _m("share_cover_1", "Cover 1", "defense", "Coverage", PARTICIPATION, "pct", scheme=True),
    _m("share_cover_2", "Cover 2", "defense", "Coverage", PARTICIPATION, "pct", scheme=True),
    _m("share_2_man", "2-Man", "defense", "Coverage", PARTICIPATION, "pct", scheme=True),
    _m("share_cover_3", "Cover 3", "defense", "Coverage", PARTICIPATION, "pct", scheme=True),
    _m("share_cover_4", "Cover 4 (quarters)", "defense", "Coverage", PARTICIPATION, "pct",
       scheme=True),
    _m("share_cover_6", "Cover 6", "defense", "Coverage", PARTICIPATION, "pct", scheme=True),
    _m("proxy_two_high_share", "Two-high safety looks", "defense", "Coverage", PARTICIPATION,
       "pct", scheme=True, note="A personnel proxy: two safeties on the field, not alignment."),
    _m("blitz_rate", "Blitz rate", "defense", "Pressure & box", PARTICIPATION, "pct",
       scheme=True, note="5+ pass rushers, share of dropbacks."),
    _m("rushers_mean", "Pass rushers / dropback", "defense", "Pressure & box", PARTICIPATION,
       "num2", scheme=True),
    _m("pressure_rate", "Pressure rate", "defense", "Pressure & box", PARTICIPATION, "pct", +1),
    _m("box_mean", "Defenders in the box", "defense", "Pressure & box", PARTICIPATION, "num2",
       scheme=True),
    _m("share_box_8plus", "8+ man box", "defense", "Pressure & box", PARTICIPATION, "pct",
       scheme=True),
    _m("ftn_blitz_rate", "Blitz rate (charted)", "defense", "Charted live", FTN, "pct",
       scheme=True, note="FTN's count of 5+ rushers. A different charting vendor from the "
                         "participation blitz rate, so the two are never mixed."),
    _m("ftn_rushers_mean", "Pass rushers (charted)", "defense", "Charted live", FTN, "num2",
       scheme=True),
    _m("ftn_box_mean", "Box defenders (charted)", "defense", "Charted live", FTN, "num2",
       scheme=True),
    _m("ftn_box_8plus", "8+ man box (charted)", "defense", "Charted live", FTN, "pct",
       scheme=True),
)

# --- special teams & game management ----------------------------------------------------------
SPECIAL: tuple[Metric, ...] = (
    _m("fourth_go_rate", "4th-down go rate", "special", "Decisions", PBP, "pct", scheme=True,
       note="4th and ≤5 between the 30s, within two scores."),
    _m("two_point_rate", "2-point attempt rate", "special", "Decisions", PBP, "pct",
       scheme=True),
    _m("rz_stall_rate", "Red-zone stall rate", "special", "Decisions", PBP, "pct", -1,
       note="Drives reaching the 20 that did not end in a touchdown."),
    _m("fg_pct", "Field-goal %", "special", "Kicking", PBP, "pct", +1),
    _m("fg_pct_long", "Field-goal % (50+)", "special", "Kicking", PBP, "pct", +1),
    _m("fg_dist_mean", "Average FG distance", "special", "Kicking", PBP, "num1"),
    _m("punt_dist_mean", "Average punt distance", "special", "Kicking", PBP, "num1", +1),
)

# --- roster construction ----------------------------------------------------------------------
CONSTRUCTION_METRICS: tuple[Metric, ...] = tuple(
    _m(f"cap_share_{g}", f"Cap share: {g.upper()}", "construction", "Cap allocation",
       CONSTRUCTION, "pct")
    for g in ("qb", "rb", "wr", "te", "ol", "dl", "lb", "db")
) + tuple(
    _m(f"age_{g}", f"Snap-weighted age: {g.upper()}", "construction", "Age", CONSTRUCTION, "num1")
    for g in ("qb", "rb", "wr", "te", "ol", "dl", "lb", "db")
) + (
    _m("continuity_offense", "Offensive continuity", "construction", "Continuity", CONSTRUCTION,
       "pct", note="Share of this season's offensive snaps played by last season's players."),
    _m("continuity_defense", "Defensive continuity", "construction", "Continuity", CONSTRUCTION,
       "pct"),
    _m("draft_capital_offense", "Draft capital: offense", "construction", "Continuity",
       CONSTRUCTION, "num1"),
    _m("draft_capital_defense", "Draft capital: defense", "construction", "Continuity",
       CONSTRUCTION, "num1"),
)

REGISTRY: tuple[Metric, ...] = OFFENSE + DEFENSE + SPECIAL + CONSTRUCTION_METRICS
BY_KEY: dict[str, Metric] = {m.key: m for m in REGISTRY}
assert len(BY_KEY) == len(REGISTRY), "duplicate metric key"

#: Which sides a season carries when a source family is missing. The site reads this to render a
#: "not published yet" state instead of an empty chart.
SIDES = ("offense", "defense", "special", "construction")


def keys(source: str | None = None, side: str | None = None) -> list[str]:
    return [m.key for m in REGISTRY
            if (source is None or m.source == source) and (side is None or m.side == side)]


def registry_records() -> list[dict]:
    """The registry as plain dicts, for the site's metadata file."""
    return [{"key": m.key, "label": m.label, "side": m.side, "group": m.group,
             "source": m.source, "fmt": m.fmt, "polarity": m.polarity, "scheme": m.scheme,
             "floor": m.floor, "note": m.note} for m in REGISTRY]
