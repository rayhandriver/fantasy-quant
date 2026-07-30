"""Personalization spine · step 1 — ``DraftConfig``, the constraint object we own.

The direct-indexing reframe (2026-07-04, ``docs/PERSONALIZATION.md``) turns the draft into a
*constrained optimization*: build the team the user wants, and honestly price what wanting it cost.
This module is the **contract** every downstream piece reads — the optimizer (step 2) and the cost
report (step 3). Per CLAUDE.md §4 "own the contracts": the human owns this shape; the optimizer
interior is delegated, but this object is not.

Scope is the near-term MVP surface of ``docs/PERSONALIZATION.md`` §7 — league context, one
archetype (a master positional dial), the hard/soft player preferences that actually ship, and the
risk dial (λ). The fuller §3 schema (fandom excludes, correlation appetite, control tiers, benchmark
sets) is deliberately *not* built until it's needed; adding a field here is cheap and honest, a
half-used schema is not.

Three signal layers stay separate (the §2 hard contract): **value** = consensus→VBD (risk-adjusted
by λ), **availability** = ADP (+noise opponents, the MVP opponent model), **variance** = our own
distributions (Phase 5, feeding λ). Nothing here collapses them.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from fantasy_quant.backtest.scoring import (
    SCORING_PRESETS,
    RuleSet,
    ruleset_from_preset,
)
from fantasy_quant.draft.simulator import DRAFTABLE, RosterSlots
from fantasy_quant.simulation.season import (
    PLAYOFF_SIZES,
    LeagueFormat,
    bracket_rounds,
    derived_byes,
)
from fantasy_quant.valuation.utility import DEFAULT_LAMBDA

# ------------------------------------------------------------------------------------------------
# archetypes — the "master dial" (one choice pre-tilts the whole board by position × round)
# ------------------------------------------------------------------------------------------------
# Each archetype is a function ``(pos, round, have) -> tilt_in_rounds``: a POSITIVE tilt drafts that
# position *sooner* (reach), a negative tilt *fades* it. ``have`` = how many of that position you
# already roster, so "get one anchor and stop" archetypes don't keep reaching (the stateless version
# drafted two elite TEs). The optimizer turns a round of tilt into ``n_teams`` picks of priority
# (step 2). Magnitudes are modest — an archetype nudges, value still leads — all overridable.
#
# ``adaptive`` (spine step 6) is the exception: it is not a fixed ``(pos, round, have)`` curve but a
# *wrapper* that follows a static ``adaptive_parent`` while the board tracks ADP and **melts the
# parent's fade when the board breaks** — see :func:`_adaptive_tilt`. It therefore needs live board
# context (a candidate's ADP vs the current overall pick), which
# :meth:`DraftConfig.total_tilt_rounds` threads in; with no context it degrades to the parent
# exactly (so leave-one-out / benchmark redraft behave sensibly).
ARCHETYPES: tuple[str, ...] = ("bpa", "zero_rb", "hero_rb", "elite_te", "late_qb", "adaptive")


def _bpa(pos: str, rnd: int, have: int) -> float:
    """Best-player-available — the neutral benchmark. No positional tilt at all."""
    return 0.0


def _zero_rb(pos: str, rnd: int, have: int) -> float:
    """Fade RB through the early rounds; load WR/TE, then take RB value on the way back."""
    if pos == "RB":
        return -2.0 if rnd <= 5 else 0.5
    if pos == "WR":
        return 0.75
    if pos == "TE":
        return 0.5
    return 0.0


def _hero_rb(pos: str, rnd: int, have: int) -> float:
    """One anchor RB early, then fade RB and pivot to receivers."""
    if pos == "RB":
        return 1.0 if have == 0 and rnd <= 3 else -1.25    # one anchor, then fade further RB
    if pos == "WR":
        return 0.5 if rnd >= 3 else 0.0
    return 0.0


def _elite_te(pos: str, rnd: int, have: int) -> float:
    """Pay up for ONE of the scarce difference-making tight ends, early — then stop reaching."""
    if pos == "TE" and have == 0 and rnd <= 5:
        return 1.75
    return 0.0


def _late_qb(pos: str, rnd: int, have: int) -> float:
    """Stream/wait at QB in a 1-QB league, then pounce on your one starter once value catches up."""
    if pos == "QB" and have == 0:
        return -1.75 if rnd <= 7 else 1.0
    return 0.0


_ARCHETYPE_FNS = {"bpa": _bpa, "zero_rb": _zero_rb, "hero_rb": _hero_rb,
                  "elite_te": _elite_te, "late_qb": _late_qb}


def archetype_tilt(name: str, pos: str, rnd: int, have: int = 0) -> float:
    """The archetype's positional tilt (rounds) for ``pos`` at round ``rnd``, given you already
    roster ``have`` of that position (defaults to 0 = the first-of-position case)."""
    return _ARCHETYPE_FNS[name](pos, rnd, have)


# ------------------------------------------------------------------------------------------------
# spine step 6 — the adaptive wrapper ("abandon the plan when the board breaks")
# ------------------------------------------------------------------------------------------------
# The archetypes above are static curves: they fade/reach a position on a fixed schedule, assuming
# the room drafts on ADP. When the room *doesn't* — an elite RB slides two rounds past his ADP — a
# static Zero-RB keeps fading the very value that fell to it. ``adaptive`` fixes exactly that, with
# one rule (docs/PERSONALIZATION.md §6.6, ROADMAP done-bar): a fade is only trustworthy while the
# board honors ADP, so **melt the fade in proportion to how far a candidate's availability has
# diverged from his ADP** — faster for a player who has actively *slid* to us (value falling to it).
# A fade only ever melts toward 0 (never flips into a reach): when it clears, the player's own
# risk-adjusted ``base_value`` decides the pick — precisely "let the value come to you". When the
# board tracks ADP (slide ≈ 0) adaptive reproduces its parent to the float. Reaching archetypes
# (a positive tilt, e.g. elite_te chasing the scarce TE) are untouched — there is no fade to melt.
ADAPTIVE_PARENTS: tuple[str, ...] = ("zero_rb", "hero_rb", "elite_te", "late_qb")  # non-bpa statics
ADAPT_DECAY = 0.5          # fraction of the fade removed per round the board diverges from ADP
ADAPT_SLIDE_WEIGHT = 2.0   # value that has actively slid to us melts the fade this many× faster


def _adaptive_tilt(parent: str, pos: str, rnd: int, have: int, *,
                   adp: float | None, overall_pick: int | None, n_teams: int) -> float:
    """The ``adaptive`` tilt: the ``parent`` archetype's tilt with any *fade* melted by board
    divergence. ``slide`` = rounds this candidate is available past his ADP (+ = fell to us,
    − = a reach because the cheap ones are already gone); a fade of magnitude ``base`` decays by
    ``ADAPT_DECAY·max(|slide|, ADAPT_SLIDE_WEIGHT·max(0, slide))``. Missing board context (either
    ``adp`` or ``overall_pick`` is None) ⇒ the parent's static tilt, unchanged."""
    base = archetype_tilt(parent, pos, rnd, have)
    if base >= 0.0 or adp is None or overall_pick is None:
        return base
    slide = (float(overall_pick) - float(adp)) / max(int(n_teams), 1)
    melt = ADAPT_DECAY * max(abs(slide), ADAPT_SLIDE_WEIGHT * max(0.0, slide))
    return base * max(0.0, 1.0 - melt)


# ------------------------------------------------------------------------------------------------
# league context + the config object
# ------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class LeagueSetup:
    """Read-not-asked league context (§5): scoring/slots/size/seat set replacement levels and
    positional priority. Defaults are the project baseline — 10-team full-PPR, 1-QB snake."""
    n_teams: int = 10
    draft_slot: int = 1                # 1-indexed seat at the table
    rounds: int = 15
    slots: RosterSlots = field(default_factory=RosterSlots)
    ruleset: RuleSet = field(default_factory=RuleSet)
    scoring: str = "ppr"               # the FFC ADP-board key (ppr / half / standard)
    fmt: str = "snake"                 # MVP supports snake; auction/linear are later

    @property
    def your_team(self) -> int:
        """0-indexed seat the simulator uses (``draft_slot`` is 1-indexed for humans)."""
        return self.draft_slot - 1

    def validate(self) -> None:
        if self.fmt != "snake":
            raise ValueError(f"MVP supports snake drafts only, not {self.fmt!r}")
        if not 1 <= self.draft_slot <= self.n_teams:
            raise ValueError(f"draft_slot {self.draft_slot} out of 1..{self.n_teams}")
        if self.rounds < self.slots.total:
            raise ValueError(f"rounds {self.rounds} < roster size {self.slots.total}")


@dataclass(frozen=True)
class Keeper:
    """17.4 — a player kept from last season, and the pick it costs.

    ``round`` is the round whose pick the owning team forfeits (ESPN/Yahoo's "keep him at the round
    you drafted him"). ``team`` is 1-indexed like ``LeagueSetup.draft_slot``. Kept players leave the
    draftable pool entirely, and the forfeited picks are the price: a team that keeps three studs
    drafts three fewer times, which is what makes the trade honest rather than free.
    """
    player_key: str
    team: int
    round: int


@dataclass(frozen=True)
class MustDraft:
    """A player you insist on rostering, with a **reach budget**: how many rounds early you'll reach
    to secure them. The optimizer waits as late as the budget and ADP allow (never overpays)."""
    player_key: str
    reach_budget: float = 2.0


@dataclass
class DraftConfig:
    """The complete preference spec the optimizer consumes (the §3 object, MVP subset).

    Hard constraints (``never_draft``, roster legality) are inviolable. Soft levers (``archetype``,
    ``tilts``) bend draft priority by a bounded number of rounds; ``must_draft`` secures a player
    within its reach budget. ``risk_lambda`` is the value↔variance dial (0 = risk-neutral VBD).
    Normalized + validated on construction so the optimizer never sees a bad field.
    """
    league: LeagueSetup = field(default_factory=LeagueSetup)
    archetype: str = "bpa"
    adaptive_parent: str | None = None   # required iff archetype == "adaptive": the preset it wraps
    must_draft: tuple[MustDraft, ...] = ()
    never_draft: frozenset[str] = frozenset()
    tilts: Mapping[str, float] = field(default_factory=dict)   # player_key -> rounds (+ = sooner)
    risk_lambda: float = DEFAULT_LAMBDA
    objective: str = "make_playoffs"    # or "championship_or_bust" — report framing (MVP: label)

    def __post_init__(self) -> None:
        self.archetype = str(self.archetype).lower().strip()
        self.adaptive_parent = (None if self.adaptive_parent is None
                                else str(self.adaptive_parent).lower().strip() or None)
        self.must_draft = tuple(
            m if isinstance(m, MustDraft)
            else MustDraft(*m) if isinstance(m, tuple)
            else MustDraft(m)
            for m in self.must_draft
        )
        self.never_draft = frozenset(self.never_draft)
        self.tilts = dict(self.tilts)
        self.validate()

    # -- validation --------------------------------------------------------------------------
    def validate(self) -> None:
        self.league.validate()
        if self.archetype not in ARCHETYPES:
            raise ValueError(f"unknown archetype {self.archetype!r}; pick from {ARCHETYPES}")
        if self.archetype == "adaptive":
            if self.adaptive_parent not in ADAPTIVE_PARENTS:
                raise ValueError(f"adaptive archetype needs adaptive_parent in {ADAPTIVE_PARENTS}, "
                                 f"got {self.adaptive_parent!r}")
        elif self.adaptive_parent is not None:
            raise ValueError("adaptive_parent is only valid when archetype='adaptive'")
        if self.risk_lambda < 0:
            raise ValueError(f"risk_lambda must be >= 0, got {self.risk_lambda}")
        if self.objective not in ("make_playoffs", "championship_or_bust"):
            raise ValueError(f"unknown objective {self.objective!r}")
        clash = {m.player_key for m in self.must_draft} & self.never_draft
        if clash:
            raise ValueError(f"players in both must_draft and never_draft: {sorted(clash)}")

    # -- levers the optimizer reads ----------------------------------------------------------
    def total_tilt_rounds(self, player_key: str, pos: str, rnd: int, have: int = 0, *,
                          adp: float | None = None, overall_pick: int | None = None) -> float:
        """Combined soft tilt (in rounds, + = sooner) = per-player tilt + the archetype's, given you
        already roster ``have`` at ``pos`` (so 'get one anchor' archetypes stop after the first).

        ``adp``/``overall_pick`` are the live board context the ``adaptive`` archetype (step 6)
        reads to melt a fade when a candidate has slid off his ADP; every static archetype ignores
        them, so the optimizer can pass them unconditionally (and omitting them degrades adaptive to
        its parent — the leave-one-out / benchmark path)."""
        per_player = float(self.tilts.get(player_key, 0.0))
        if self.archetype == "adaptive":
            arch = _adaptive_tilt(self.adaptive_parent, pos, rnd, have,
                                  adp=adp, overall_pick=overall_pick, n_teams=self.league.n_teams)
        else:
            arch = archetype_tilt(self.archetype, pos, rnd, have)
        return per_player + arch

    def constraint_labels(self) -> list[str]:
        """Human-readable id per active constraint — the rows of the cost report's attribution."""
        labels: list[str] = []
        if self.archetype == "adaptive":
            labels.append(f"archetype:adaptive({self.adaptive_parent})")
        elif self.archetype != "bpa":
            labels.append(f"archetype:{self.archetype}")
        labels += [f"must:{m.player_key}" for m in self.must_draft]
        labels += [f"never:{pk}" for pk in sorted(self.never_draft)]
        labels += [f"tilt:{pk}{r:+g}" for pk, r in self.tilts.items()]
        return labels

    def label_player_key(self, label: str) -> str | None:
        """The player a constraint label refers to (None for the archetype) — so a report can show
        a name, not the raw label. Tilt labels embed a signed number, so match, never parse."""
        kind, _, ident = label.partition(":")
        if kind in ("must", "never"):
            return ident
        if kind == "tilt":
            return next((pk for pk, r in self.tilts.items() if f"{pk}{r:+g}" == ident), None)
        return None

    def without_constraint(self, label: str) -> DraftConfig:
        """A copy with exactly one constraint (from :meth:`constraint_labels`) removed — the
        leave-one-out configs the cost report redrafts to attribute cost per preference."""
        kind, _, ident = label.partition(":")
        removing_arch = kind == "archetype"
        arch = "bpa" if removing_arch else self.archetype
        parent = None if removing_arch else self.adaptive_parent   # clears with the archetype
        must = self.must_draft
        never = self.never_draft
        tilts = dict(self.tilts)
        if kind == "must":
            must = tuple(m for m in must if m.player_key != ident)
        elif kind == "never":
            never = never - {ident}
        elif kind == "tilt":
            # match on the regenerated label (player keys contain hyphens — never parse them apart).
            tilts = {pk: r for pk, r in tilts.items() if f"{pk}{r:+g}" != ident}
        return DraftConfig(league=self.league, archetype=arch, adaptive_parent=parent,
                           must_draft=must, never_draft=never, tilts=tilts,
                           risk_lambda=self.risk_lambda, objective=self.objective)

    def benchmark(self) -> DraftConfig:
        """The unconstrained value-optimal peer from the same seat & risk appetite — the direct-
        indexing benchmark the personalization cost is priced against (strip every preference,
        keep league + λ)."""
        return DraftConfig(league=self.league, risk_lambda=self.risk_lambda,
                           objective=self.objective)


__all__ = ["ARCHETYPES", "ADAPTIVE_PARENTS", "DraftConfig", "LeagueSetup", "MustDraft",
           "archetype_tilt", "DRAFTABLE"]


# ------------------------------------------------------------------------------------------------
# 17.3 — the platform-agnostic league-settings contract (the Phase-14 form binds to THIS)
# ------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class LeagueSettings:
    """Everything a user can tell us about their league, in **their** vocabulary, plus the builders
    that turn it into the engine's objects (:class:`RuleSet`, :class:`RosterSlots`,
    :class:`~fantasy_quant.simulation.season.LeagueFormat`, :class:`LeagueSetup`).

    **Platform-agnostic on purpose** (user decision, 2026-07-23): people are on ESPN/Yahoo/Sleeper/
    NFL.com and we do not want to be gated on any one API. This is the manual form's shape; an
    optional Sleeper auto-import that *pre-fills* it is a future convenience, never the only path.

    ⚠ **Non-default formats are NOT lockbox-validated.** The lockbox was spent once, on a 10-team
    full-PPR 1-QB league. Superflex, TE-premium, custom brackets and keepers are supported and
    unit-tested for *correctness*, but no out-of-sample claim from `findings.md` §"LOCKBOX
    EVALUATION" transfers to them. :meth:`lockbox_validated` says which case you are in, and the
    Phase-14 surfacing is expected to label it rather than let a user assume the calibration
    carries over.
    """
    # -- league shape ------------------------------------------------------------------------
    n_teams: int = 10
    draft_slot: int = 1
    rounds: int = 15
    draft_type: str = "snake"                 # snake | linear | auction (auction -> Phase 15.4)

    # -- starting lineup ---------------------------------------------------------------------
    qb: int = 1
    rb: int = 2
    wr: int = 2
    te: int = 1
    flex: int = 1
    superflex: int = 0                        # a.k.a. OP; a flex that may take a QB
    k: int = 1
    dst: int = 1
    bench: int = 6

    # -- scoring -----------------------------------------------------------------------------
    scoring_preset: str = "full_ppr"          # SCORING_PRESETS key
    scoring_overrides: Mapping[str, float] = field(default_factory=dict)

    # -- season / bracket --------------------------------------------------------------------
    reg_weeks: int = 14
    playoff_teams: int = 6
    playoff_weeks: tuple[int, ...] = (15, 16, 17)

    # -- keepers (17.4) ----------------------------------------------------------------------
    keepers: tuple[Keeper, ...] = ()

    #: The exact configuration the lockbox evaluated. Anything else is supported-but-unvalidated.
    LOCKBOX_CASE = {"n_teams": 10, "qb": 1, "rb": 2, "wr": 2, "te": 1, "flex": 1, "superflex": 0,
                    "k": 1, "dst": 1, "bench": 6, "scoring_preset": "full_ppr",
                    "playoff_teams": 6, "reg_weeks": 14, "draft_type": "snake"}

    # -- builders ----------------------------------------------------------------------------
    def ruleset(self) -> RuleSet:
        return ruleset_from_preset(self.scoring_preset, **dict(self.scoring_overrides))

    def roster_slots(self) -> RosterSlots:
        """Build :class:`RosterSlots`, with per-position caps scaled so a superflex league is
        allowed to roster the second QB it is required to start. Leaving the 1-QB cap of 2 in place
        would let a format be configured and then be undraftable, which is worse than either."""
        caps = {"QB": max(2, self.qb + self.superflex + 1), "RB": 6, "WR": 6,
                "TE": max(2, self.te + 1), "K": max(1, self.k), "DST": max(1, self.dst)}
        slots = RosterSlots(qb=self.qb, rb=self.rb, wr=self.wr, te=self.te, flex=self.flex,
                            superflex=self.superflex, k=self.k, dst=self.dst, bench=self.bench,
                            pos_caps=caps)
        slots.assert_nested()
        return slots

    def league_format(self) -> LeagueFormat:
        return LeagueFormat(n_teams=self.n_teams, reg_weeks=self.reg_weeks,
                            playoff_teams=self.playoff_teams,
                            playoff_weeks=tuple(self.playoff_weeks),
                            first_round_byes=derived_byes(self.playoff_teams))

    def league_setup(self) -> LeagueSetup:
        return LeagueSetup(n_teams=self.n_teams, draft_slot=self.draft_slot, rounds=self.rounds,
                           slots=self.roster_slots(), ruleset=self.ruleset(),
                           scoring=_ADP_SCORING_KEY.get(self.scoring_preset, "ppr"),
                           fmt=self.draft_type)

    def lockbox_validated(self) -> bool:
        """True only for the exact league the lockbox was spent on. Everything else is honest
        engineering with no out-of-sample claim attached."""
        return all(getattr(self, k) == v for k, v in self.LOCKBOX_CASE.items()) and \
            not self.scoring_overrides and not self.keepers

    def validate(self) -> None:
        """Reject anything the engine cannot actually play, with a message that says why.

        Deliberately strict: the alternative is a league that configures cleanly and then produces
        a silently wrong board, which is the failure mode this whole phase exists to avoid.
        """
        problems: list[str] = []
        if self.draft_type not in ("snake", "linear", "auction"):
            problems.append(f"draft_type {self.draft_type!r} must be snake, linear or auction")
        if self.n_teams < 2:
            problems.append("n_teams must be at least 2")
        if self.n_teams % 2:
            problems.append("n_teams must be even (the round-robin schedule pairs every team)")
        if not 1 <= self.draft_slot <= max(self.n_teams, 1):
            problems.append(f"draft_slot {self.draft_slot} out of 1..{self.n_teams}")
        for name in ("qb", "rb", "wr", "te", "flex", "superflex", "k", "dst", "bench"):
            if getattr(self, name) < 0:
                problems.append(f"{name} cannot be negative")
        if self.playoff_teams not in PLAYOFF_SIZES:
            problems.append(f"playoff_teams must be one of {sorted(PLAYOFF_SIZES)}")
        elif self.playoff_teams > self.n_teams:
            problems.append("playoff_teams cannot exceed n_teams")
        elif len(self.playoff_weeks) != bracket_rounds(self.playoff_teams):
            problems.append(f"a {self.playoff_teams}-team bracket needs "
                            f"{bracket_rounds(self.playoff_teams)} playoff weeks")
        elif self.playoff_weeks and self.playoff_weeks[0] != self.reg_weeks + 1:
            problems.append("playoffs must start the week after the regular season")
        if self.scoring_preset not in SCORING_PRESETS:
            problems.append(f"unknown scoring preset {self.scoring_preset!r}; "
                            f"known: {sorted(SCORING_PRESETS)}")
        try:
            self.ruleset()
        except Exception as exc:                                  # noqa: BLE001 — surface as text
            problems.append(f"scoring overrides invalid: {exc}")
        try:
            slots = self.roster_slots()
            if self.rounds < slots.total:
                problems.append(f"rounds {self.rounds} < roster size {slots.total}")
            if self.n_teams * slots.starters > 0 and self.superflex and not self.qb:
                problems.append("a superflex league needs at least one dedicated QB slot")
        except ValueError as exc:
            problems.append(str(exc))
        seen: set[str] = set()
        for kp in self.keepers:
            if kp.player_key in seen:
                problems.append(f"duplicate keeper {kp.player_key!r}")
            seen.add(kp.player_key)
            if kp.round < 1 or kp.round > self.rounds:
                problems.append(f"keeper {kp.player_key!r} round {kp.round} "
                                f"out of 1..{self.rounds}")
            if not 1 <= kp.team <= self.n_teams:
                problems.append(f"keeper {kp.player_key!r} team {kp.team} "
                                f"out of 1..{self.n_teams}")
        if problems:
            raise ValueError("invalid league settings: " + "; ".join(problems))


#: Which FFC ADP board a scoring preset should read. TE-premium has no FFC board of its own, so it
#: reads the PPR one — stated here rather than silently defaulted, because it is an approximation.
_ADP_SCORING_KEY: dict[str, str] = {
    "standard": "standard", "half_ppr": "half", "full_ppr": "ppr", "te_premium": "ppr",
}
