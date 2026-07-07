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

from fantasy_quant.backtest.scoring import RuleSet
from fantasy_quant.draft.simulator import DRAFTABLE, RosterSlots
from fantasy_quant.valuation.utility import DEFAULT_LAMBDA

# ------------------------------------------------------------------------------------------------
# archetypes — the "master dial" (one choice pre-tilts the whole board by position × round)
# ------------------------------------------------------------------------------------------------
# Each archetype is a function ``(pos, round, have) -> tilt_in_rounds``: a POSITIVE tilt drafts that
# position *sooner* (reach), a negative tilt *fades* it. ``have`` = how many of that position you
# already roster, so "get one anchor and stop" archetypes don't keep reaching (the stateless version
# drafted two elite TEs). The optimizer turns a round of tilt into ``n_teams`` picks of priority
# (step 2). Magnitudes are modest — an archetype nudges, value still leads — all overridable.
ARCHETYPES: tuple[str, ...] = ("bpa", "zero_rb", "hero_rb", "elite_te", "late_qb")


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
    must_draft: tuple[MustDraft, ...] = ()
    never_draft: frozenset[str] = frozenset()
    tilts: Mapping[str, float] = field(default_factory=dict)   # player_key -> rounds (+ = sooner)
    risk_lambda: float = DEFAULT_LAMBDA
    objective: str = "make_playoffs"    # or "championship_or_bust" — report framing (MVP: label)

    def __post_init__(self) -> None:
        self.archetype = str(self.archetype).lower().strip()
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
        if self.archetype not in _ARCHETYPE_FNS:
            raise ValueError(f"unknown archetype {self.archetype!r}; pick from {ARCHETYPES}")
        if self.risk_lambda < 0:
            raise ValueError(f"risk_lambda must be >= 0, got {self.risk_lambda}")
        if self.objective not in ("make_playoffs", "championship_or_bust"):
            raise ValueError(f"unknown objective {self.objective!r}")
        clash = {m.player_key for m in self.must_draft} & self.never_draft
        if clash:
            raise ValueError(f"players in both must_draft and never_draft: {sorted(clash)}")

    # -- levers the optimizer reads ----------------------------------------------------------
    def total_tilt_rounds(self, player_key: str, pos: str, rnd: int, have: int = 0) -> float:
        """Combined soft tilt (in rounds, + = sooner) = per-player tilt + the archetype's, given you
        already roster ``have`` at ``pos`` (so 'get one anchor' archetypes stop after the first)."""
        return (float(self.tilts.get(player_key, 0.0))
                + archetype_tilt(self.archetype, pos, rnd, have))

    def constraint_labels(self) -> list[str]:
        """Human-readable id per active constraint — the rows of the cost report's attribution."""
        labels: list[str] = []
        if self.archetype != "bpa":
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
        arch = "bpa" if kind == "archetype" else self.archetype
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
        return DraftConfig(league=self.league, archetype=arch, must_draft=must, never_draft=never,
                           tilts=tilts, risk_lambda=self.risk_lambda, objective=self.objective)

    def benchmark(self) -> DraftConfig:
        """The unconstrained value-optimal peer from the same seat & risk appetite — the direct-
        indexing benchmark the personalization cost is priced against (strip every preference,
        keep league + λ)."""
        return DraftConfig(league=self.league, risk_lambda=self.risk_lambda,
                           objective=self.objective)


__all__ = ["ARCHETYPES", "DraftConfig", "LeagueSetup", "MustDraft", "archetype_tilt", "DRAFTABLE"]
