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

#: ★ **The formation vocabulary changed in 2023 (T57).** Through 2022 the participation file names
#: SINGLEBACK / I_FORM / EMPTY / JUMBO / WILDCAT; from 2023 those all collapse into one value,
#: ``UNDER CENTER``. The panel's shares read **0 on the far side of the seam** — every team "ran no
#: singleback" in 2024 and "never lined up under center" in 2020 — so each share is bounded to the
#: seasons whose vocabulary it was written against: ``(first, last)``, ``None`` = unbounded.
#: Under-center *before* 2023 is not lost entirely: FTN's ``qb_under_center_ftn`` covers 2022+.
FORMATION_SEAM = 2023
SEASON_BOUNDS: dict[str, tuple[int | None, int | None]] = {
    "share_under_center": (FORMATION_SEAM, None),
    "share_singleback": (None, FORMATION_SEAM - 1),
    "share_i_form": (None, FORMATION_SEAM - 1),
    "share_empty": (None, FORMATION_SEAM - 1),
}


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
        first = SEASON_BOUNDS.get(self.key, (None, None))[0]
        if first is not None:
            return first
        if self.source == FTN:
            return SEASON_FLOORS["ftn_charting"]
        if self.source == PARTICIPATION and (self.key.startswith("share_cover_")
                                             or self.key in ("man_share", "share_2_man")):
            return CHARTED_COVERAGE_FLOOR
        return 2016

    @property
    def ceiling(self) -> int | None:
        """The last season the metric means what its label says (``None``: still does)."""
        return SEASON_BOUNDS.get(self.key, (None, None))[1]


def _m(*args, **kw) -> Metric:
    return Metric(*args, **kw)


# --- offense ----------------------------------------------------------------------------------
OFFENSE: tuple[Metric, ...] = (
    _m("snaps_per_game", "Offensive snaps per game", "offense", "Volume and efficiency", PBP,
       "num1",
       note="Counts every pass and run play, divided by games played."),
    _m("dropbacks_per_game", "Dropbacks per game", "offense", "Volume and efficiency", PBP, "num1"),
    _m("epa_per_play", "EPA per play", "offense", "Volume and efficiency", PBP, "rate3", +1),
    _m("pass_epa", "EPA per dropback", "offense", "Volume and efficiency", PBP, "rate3", +1),
    _m("rush_epa", "EPA per rush", "offense", "Volume and efficiency", PBP, "rate3", +1),
    _m("success_rate", "Success rate", "offense", "Volume and efficiency", PBP, "pct", +1),
    _m("explosive_rate", "Explosive play rate", "offense", "Volume and efficiency", PBP, "pct", +1,
       note="The share of plays that were passes of 20 or more yards or runs of 10 or more."),
    _m("pass_rate", "Pass rate", "offense", "Tendencies", PBP, "pct", scheme=True),
    _m("pass_rate_neutral", "Neutral-script pass rate", "offense", "Tendencies", PBP, "pct",
       scheme=True, note="Only counts plays when the game is within one score and more than five "
                         "minutes remain, so a team that spent the year trailing is not inflated."),
    _m("pass_oe_mean", "Pass rate over expected (PROE)", "offense", "Tendencies", PBP, "signed1",
       scheme=True,
       note="How many percentage points more often the team passed than nflverse's model "
            "expects given down, distance, field position and score."),
    _m("early_down_pass_rate", "Early-down pass rate", "offense", "Tendencies", PBP, "pct",
       scheme=True, note="First and second down plays in a close game."),
    _m("shotgun_rate", "Shotgun rate", "offense", "Tendencies", PBP, "pct", scheme=True),
    _m("no_huddle_rate", "No-huddle rate", "offense", "Tendencies", PBP, "pct", scheme=True),
    _m("share_under_center", "Under-center rate", "offense", "Formation", PARTICIPATION, "pct",
       scheme=True),
    _m("share_singleback", "Singleback formation", "offense", "Formation", PARTICIPATION, "pct",
       scheme=True),
    _m("share_i_form", "I-formation", "offense", "Formation", PARTICIPATION, "pct", scheme=True),
    _m("share_empty", "Empty formation", "offense", "Formation", PARTICIPATION, "pct",
       scheme=True),
    _m("share_pistol", "Pistol", "offense", "Formation", PARTICIPATION, "pct", scheme=True),
    _m("share_p11", "11 personnel", "offense", "Personnel", PARTICIPATION, "pct", scheme=True,
       note="One running back, one tight end and three receivers."),
    _m("share_p12", "12 personnel", "offense", "Personnel", PARTICIPATION, "pct", scheme=True,
       note="One running back, two tight ends and two receivers."),
    _m("share_p13", "13 personnel", "offense", "Personnel", PARTICIPATION, "pct", scheme=True,
       note="One running back, three tight ends and one receiver."),
    _m("share_p21", "21 personnel", "offense", "Personnel", PARTICIPATION, "pct", scheme=True,
       note="Two running backs, one tight end and two receivers."),
    _m("share_p22", "22 personnel", "offense", "Personnel", PARTICIPATION, "pct", scheme=True),
    _m("share_p10", "10 personnel", "offense", "Personnel", PARTICIPATION, "pct", scheme=True),
    _m("te_mean", "TEs on the field", "offense", "Personnel", PARTICIPATION, "num2", scheme=True),
    _m("wr_mean", "WRs on the field", "offense", "Personnel", PARTICIPATION, "num2", scheme=True),
    _m("motion_rate", "Pre-snap motion", "offense", "Play design", FTN, "pct", scheme=True),
    _m("play_action_rate", "Play-action rate", "offense", "Play design", FTN, "pct", scheme=True,
       note="Measured as a share of dropbacks."),
    _m("rpo_rate", "RPO rate", "offense", "Play design", FTN, "pct", scheme=True),
    _m("screen_rate", "Screen rate", "offense", "Play design", FTN, "pct", scheme=True,
       note="Measured as a share of dropbacks."),
    _m("qb_under_center_ftn", "QB under center (charted)", "offense", "Play design", FTN, "pct",
       scheme=True, note="Charted by FTN during the season, so it is available for the current "
                         "year even before the formation data above is published."),
    _m("backfield_mean", "Backs in the backfield", "offense", "Play design", FTN, "num2",
       scheme=True),
)

# --- defense ----------------------------------------------------------------------------------
DEFENSE: tuple[Metric, ...] = (
    _m("def_epa_per_play", "EPA per play allowed", "defense", "Results allowed", PBP, "rate3", -1),
    _m("def_pass_epa", "EPA per dropback allowed", "defense", "Results allowed", PBP, "rate3", -1),
    _m("def_rush_epa", "EPA per rush allowed", "defense", "Results allowed", PBP, "rate3", -1),
    _m("def_success_rate", "Success rate allowed", "defense", "Results allowed", PBP, "pct", -1),
    _m("def_explosive_rate", "Explosive plays allowed", "defense", "Results allowed", PBP, "pct",
       -1),
    _m("def_sack_rate", "Sack rate", "defense", "Results allowed", PBP, "pct", +1,
       note="Sacks divided by the number of times opponents dropped back to pass."),
    _m("takeaways_per_game", "Takeaways per game", "defense", "Results allowed", PBP, "num2", +1),
    _m("opp_pass_rate", "Opponent pass rate", "defense", "Results allowed", PBP, "pct",
       note="How often opposing offenses decided to throw against this defense."),
    _m("share_base", "Base (4 DB)", "defense", "Fronts and personnel", PARTICIPATION, "pct",
       scheme=True),
    _m("share_nickel", "Nickel (5 DB)", "defense", "Fronts and personnel", PARTICIPATION, "pct",
       scheme=True),
    _m("share_dime", "Dime (6+ DB)", "defense", "Fronts and personnel", PARTICIPATION, "pct",
       scheme=True),
    _m("dl_mean", "Defensive linemen on the field", "defense", "Fronts and personnel",
       PARTICIPATION, "num2", scheme=True),
    _m("lb_mean", "Linebackers on the field", "defense", "Fronts and personnel", PARTICIPATION,
       "num2", scheme=True),
    _m("man_share", "Man coverage", "defense", "Coverage", PARTICIPATION, "pct", scheme=True,
       note="Measured on dropbacks where the coverage was charted."),
    _m("share_cover_0", "Cover 0", "defense", "Coverage", PARTICIPATION, "pct", scheme=True),
    _m("share_cover_1", "Cover 1", "defense", "Coverage", PARTICIPATION, "pct", scheme=True),
    _m("share_cover_2", "Cover 2", "defense", "Coverage", PARTICIPATION, "pct", scheme=True),
    _m("share_2_man", "2-Man", "defense", "Coverage", PARTICIPATION, "pct", scheme=True),
    _m("share_cover_3", "Cover 3", "defense", "Coverage", PARTICIPATION, "pct", scheme=True),
    _m("share_cover_4", "Cover 4 (quarters)", "defense", "Coverage", PARTICIPATION, "pct",
       scheme=True),
    _m("share_cover_6", "Cover 6", "defense", "Coverage", PARTICIPATION, "pct", scheme=True),
    _m("proxy_two_high_share", "Two-high safety looks", "defense", "Coverage", PARTICIPATION,
       "pct", scheme=True, note="Based on how many safeties were on the field. The data does not "
                                "record where they lined up."),
    _m("blitz_rate", "Blitz rate", "defense", "Pressure and box", PARTICIPATION, "pct",
       scheme=True, note="Dropbacks where the defense sent five or more pass rushers."),
    _m("rushers_mean", "Pass rushers per dropback", "defense", "Pressure and box", PARTICIPATION,
       "num2", scheme=True),
    _m("pressure_rate", "Pressure rate", "defense", "Pressure and box", PARTICIPATION, "pct", +1,
       # recomputed on dropbacks, not read from the panel: T57
       note="Dropbacks where the quarterback was charted as pressured."),
    _m("box_mean", "Defenders in the box", "defense", "Pressure and box", PARTICIPATION, "num2",
       scheme=True),
    _m("share_box_8plus", "8+ man box", "defense", "Pressure and box", PARTICIPATION, "pct",
       scheme=True),
    _m("ftn_blitz_rate", "Blitz rate (charted)", "defense", "Charted in season", FTN, "pct",
       scheme=True, note="FTN's count of five or more rushers. FTN charts plays differently "
                         "from the participation data, so this is kept separate from the blitz "
                         "rate above."),
    _m("ftn_rushers_mean", "Pass rushers (charted)", "defense", "Charted in season", FTN, "num2",
       scheme=True),
    _m("ftn_box_mean", "Box defenders (charted)", "defense", "Charted in season", FTN, "num2",
       scheme=True),
    _m("ftn_box_8plus", "8+ man box (charted)", "defense", "Charted in season", FTN, "pct",
       scheme=True),
)

# --- special teams & game management ----------------------------------------------------------
SPECIAL: tuple[Metric, ...] = (
    _m("fourth_go_rate", "4th-down go rate", "special", "Decisions", PBP, "pct", scheme=True,
       note="Fourth and five or shorter between the 30 yard lines in a two score game."),
    _m("two_point_rate", "2-point attempt rate", "special", "Decisions", PBP, "pct",
       scheme=True),
    _m("rz_stall_rate", "Red-zone stall rate", "special", "Decisions", PBP, "pct", -1,
       note="Drives that reached the opponent 20 and did not end in a touchdown."),
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
       "pct", note="The share of this year's offensive snaps played by players who were on the "
            "team last year."),
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
             "floor": m.floor, "ceiling": m.ceiling, "note": m.note} for m in REGISTRY]
