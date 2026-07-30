"""Phase 1.2 — the draft simulator (a full snake draft vs ADP-following opponents).

The second brick of the backtest harness. Opponents pick by **ADP + Gaussian noise** (the
baseline opponent model — richer Bayesian board inference is Phase 11.1); your team is driven by
a pluggable ``your_pick_fn(state)`` so any ranking method / policy can be dropped in. The result
is a :class:`DraftState` — full rosters + a pick log — which becomes the input to every later
draft policy (Phases 9/11) and to the walk-forward harness (1.3).

Design notes:
  - **Board = any ADP frame** (``adp_asof`` (0.4) or ``preseason_panel`` (0.7)): needs a name,
    position and ADP. Positions are canonicalized to ``QB/RB/WR/TE/K/DST`` (FFC ``PK``->K,
    ``DEF``->DST). K carry a gsis; DST don't — the ``player_key`` falls back to the name, which the
    harness maps to a team via :func:`fantasy_quant.backtest.scoring.dst_team_from_adp_name`.
  - **Reproducible:** all opponent randomness comes from a single seeded ``rng``.
  - FFC's aggregate board lists only ~5 kickers / ~6 defenses, so K/DST are **undersupplied** for
    10 teams — teams that miss out simply leave the slot empty (a realistic streaming assumption).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

_CANON = {"QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE",
          "PK": "K", "K": "K", "DEF": "DST", "DST": "DST", "D/ST": "DST"}
DRAFTABLE = ("QB", "RB", "WR", "TE", "K", "DST")

#: Optional board columns :func:`_prepare_board` carries through untouched when a caller supplies
#: them (Phase 16.13). Everything here is **read-only context** a pick policy may consult — the
#: enrichment never changes how the draft runs, only what an opponent personality is able to *see*.
#: An ADP-only board simply has none of them and every consumer falls back (the marginalization
#: convention :meth:`~fantasy_quant.draft.opponent_model.OpponentModel.candidate_utility` already
#: uses for unknown Tier-B context). Populate via
#: :func:`~fantasy_quant.draft.enrichment.enrich_board`.
#: ⚠ Must remain a superset of ``personalities.SIGNAL_COLS`` — a weightable signal that is not
#: passed through is silently skipped by ``signal_bonus`` and the weight becomes a no-op that still
#: completes a legal draft. That has now happened three times (``fandom``, ``rookie``,
#: ``durability``), so ``test_personalities`` asserts the containment.
#:
#: ★ **``stdev`` joined this list for T24 (2026-07-28) and its absence is the whole ticket.** The
#: board carried the crowd's own disagreement all along — 16.8 had even measured it as a drift
#: driver, +0.35 rounds/SD — but ``_prepare_board`` dropped it, so nothing in ``draft/`` could read
#: it and every width the room had was indexed on the **round**. A column that never reaches the
#: pick path is a finding that was never fed back into the room. Fourth instance of the same shape.
#:
#: ★ **``proj_points`` and ``base_value`` joined for T27 (2026-07-30) and, like ``stdev``, their
#: absence *was* the ticket.** They are the two ends of the value chain — the number a human reads
#: (consensus projection) and the number every seat optimizes (risk-adjusted VOR) — and on the live
#: 2026 board they disagree by up to 179 points. Neither could reach ``DraftState.board``, so the
#: CLI re-attached ``proj_points`` by hand after ``_prepare_board`` and ``base_value`` was simply
#: invisible to anything a human could read.
#: ⚠ **All three of ``proj_points``/``mean``/``base_value`` are LEVEL columns and must never enter
#: ``personalities.SIGNAL_COLS``** — ``signal_bonus`` z-scores within position, which is precisely
#: the level-vs-shape defect 16.14R/T19 spent a session undoing. ``test_personalities`` asserts the
#: exclusion; the containment assertion above only runs the other way.
PASSTHROUGH_COLS = ("team", "rookie", "stdev", "boom_prob", "q90", "bust_prob", "q10", "q50",
                    "games_played_mean", "mean", "upside", "floor", "durability", "tail_risk",
                    "vbd", "overall_rank", "cos", "role_share", "role_delta",
                    "td_regression", "boom_prob_live", "bust_prob_live",
                    "proj_points", "base_value")

#: The T27 value chain, in the order the arithmetic runs — what ``mock_draft.py why`` prints and
#: what :func:`~fantasy_quant.data.validate.value_scale_gate` audits. Level columns, never signals.
VALUE_SCALE_COLS: tuple[str, ...] = ("proj_points", "mean", "games_played_mean", "base_value")


def canon_pos(pos) -> str | None:
    """FFC/nflverse position -> canonical ``QB/RB/WR/TE/K/DST`` (or None if not draftable)."""
    return _CANON.get(str(pos).upper().strip())


def board_player_key(board: pd.DataFrame) -> pd.Series:
    """The board's join key: ``gsis_id`` where present, else the player name.

    Split out so any frame that has to line up with a board (16.13's enrichment, a value index)
    derives the key **the same way** the simulator does. Re-implementing the fallback is how a
    joiner silently misses team defenses, which carry no gsis and key on their name.
    """
    name_col = "player_name" if "player_name" in board.columns else "name"
    key_col = "gsis_id" if "gsis_id" in board.columns else name_col
    return board[key_col].where(board[key_col].notna(), board[name_col])


@dataclass(frozen=True)
class RosterSlots:
    """The league roster: starter slots + bench, and per-position roster **caps** the ADP
    opponents respect so they build realistic rosters (no 8-QB teams). Baseline = 10-team,
    9-starter QB/2RB/2WR/TE/FLEX(RB/WR/TE)+K+DST, 6 bench (15 total).

    **17.1 — generalized, with the default path bit-identical.** ``qb``/``flex`` take any count, and
    a **superflex** (a flex whose eligibility includes QB) is expressed as a *second* flex group.
    Every solver in the repo consumes :meth:`flex_groups` rather than reading ``flex``/
    ``flex_positions`` directly, so the ordering rule lives in exactly one place.

    ⚠ **Eligibility must be NESTED** (each group's positions a superset of the previous one's).
    Greedy most-restrictive-first is provably optimal for nested slots and stays vectorized over
    ``(n_sims, n_weeks)``; for *non-nested* sets (say a WR/TE flex beside an RB/WR flex) it is not,
    and the correct solver is a per-cell assignment that no longer vectorizes. Non-nested rosters
    are therefore **refused at construction** rather than silently mis-solved — see
    :meth:`assert_nested`, which :class:`~fantasy_quant.draft.config.LeagueSettings` calls.
    """
    qb: int = 1
    rb: int = 2
    wr: int = 2
    te: int = 1
    flex: int = 1
    k: int = 1
    dst: int = 1
    bench: int = 6
    flex_positions: tuple[str, ...] = ("RB", "WR", "TE")
    #: A flex that may also take a QB (a.k.a. OP / superflex). 0 in the lockbox-validated default.
    superflex: int = 0
    superflex_positions: tuple[str, ...] = ("QB", "RB", "WR", "TE")
    pos_caps: dict[str, int] = field(
        default_factory=lambda: {"QB": 2, "RB": 6, "WR": 6, "TE": 2, "K": 1, "DST": 1}
    )

    @property
    def starters(self) -> int:
        return (self.qb + self.rb + self.wr + self.te + self.flex + self.superflex
                + self.k + self.dst)

    @property
    def total(self) -> int:
        return self.starters + self.bench

    def base_demand(self) -> dict[str, int]:
        """Fixed (non-FLEX) starter demand per position."""
        return {"QB": self.qb, "RB": self.rb, "WR": self.wr, "TE": self.te,
                "K": self.k, "DST": self.dst}

    # -- 17.1 flex generalization: ONE ordering rule, consumed by every solver ----------------
    def flex_groups(self) -> tuple[tuple[int, tuple[str, ...]], ...]:
        """``((count, positions), ...)`` **most-restrictive first** — the fill order every lineup
        solver uses. Empty groups are dropped, so the 1-QB default returns exactly one group and
        every consumer reduces to its pre-17.1 behaviour."""
        groups = [(self.flex, tuple(self.flex_positions)),
                  (self.superflex, tuple(self.superflex_positions))]
        out = [(n, p) for n, p in groups if n > 0 and p]
        return tuple(sorted(out, key=lambda g: len(g[1])))

    def total_flex(self) -> int:
        """Total flex-family slots across all groups."""
        return sum(n for n, _ in self.flex_groups())

    def flex_eligible(self) -> frozenset[str]:
        """Every position that can fill *some* flex slot — the union over groups. This is the right
        set for "could this player ever start in a flex", which is what the optimizer, the auction
        bidder and ``remaining_needs`` each want."""
        return frozenset(p for _, positions in self.flex_groups() for p in positions)

    def assert_nested(self) -> None:
        """Raise unless the flex groups are nested (each a superset of the previous).

        The greedy fill is optimal for nested eligibility and *not* in general; refusing here is a
        deliberate scope choice (see the class docstring) so a league we cannot solve correctly
        never reaches a solver that would answer anyway."""
        prev: frozenset[str] = frozenset()
        for _, positions in self.flex_groups():
            cur = frozenset(positions)
            if prev and not prev <= cur:
                raise ValueError(
                    f"flex eligibility must be nested, most-restrictive first; {sorted(cur)} "
                    f"does not contain {sorted(prev)}. Non-nested flex slots need a per-cell "
                    "assignment solver, which this engine deliberately does not implement.")
            prev = cur


@dataclass
class DraftState:
    """Live draft state; also the returned result (rosters + pick log). ``your_pick_fn`` receives
    this and returns the board row-label to draft."""
    board: pd.DataFrame                 # canonical: player_key, player_name, pos, adp, pos_rank
    n_teams: int
    rounds: int
    slots: RosterSlots
    your_team: int
    rng: np.random.Generator
    noise: float
    available: set[int] = field(default_factory=set)
    rosters: list[list[int]] = field(default_factory=list)
    log: list[dict] = field(default_factory=list)
    overall_pick: int = 1
    #: 17.4 — ``(team, round)`` slots forfeited to a keeper. ``run_to_completion`` skips them, so a
    #: team that kept three players simply drafts three fewer times.
    skipped_picks: set[tuple[int, int]] = field(default_factory=set)

    # -- draft geometry (snake order) --------------------------------------------------------
    def round(self) -> int:
        return (self.overall_pick - 1) // self.n_teams + 1

    def pick_in_round(self) -> int:
        return (self.overall_pick - 1) % self.n_teams + 1

    def team_on_clock(self) -> int:
        rnd0 = (self.overall_pick - 1) // self.n_teams
        idx = (self.overall_pick - 1) % self.n_teams
        return idx if rnd0 % 2 == 0 else self.n_teams - 1 - idx  # snake: even rounds reverse

    def is_done(self) -> bool:
        return self.overall_pick > self.n_teams * self.rounds

    # -- views the pick_fn uses --------------------------------------------------------------
    def available_board(self) -> pd.DataFrame:
        """Available players, ADP-ascending (best value first)."""
        return self.board.loc[sorted(self.available)].sort_values("adp")

    def roster(self, team: int) -> pd.DataFrame:
        return self.board.loc[self.rosters[team]]

    def your_roster(self) -> pd.DataFrame:
        return self.roster(self.your_team)

    def roster_counts(self, team: int) -> dict[str, int]:
        if not self.rosters[team]:
            return {}
        return self.board.loc[self.rosters[team], "pos"].value_counts().to_dict()

    def can_draft(self, team: int, pos: str) -> bool:
        """Position not yet at its roster cap and the team still has an open roster spot."""
        if len(self.rosters[team]) >= self.slots.total:
            return False
        return self.roster_counts(team).get(pos, 0) < self.slots.pos_caps.get(pos, 99)

    def mandatory_needs(self, team: int) -> dict[str, int]:
        """Unfilled **dedicated** starter demand — every slot nothing else can cover.

        ★ **T23 — this used to exempt ``slots.flex_positions`` and that read the membership
        backwards.** The exemption said RB/WR/TE demand is never mandatory because a FLEX can
        absorb it, and for **TE** that is simply false: the dedicated TE slot has no substitute, so
        a seat with zero TEs cannot field a legal lineup. *TE is in ``flex_positions`` because a TE
        may fill FLEX, not because anything may fill TE.* Measured over 40 seeded drafts x 10 seats
        x 9 seasons, the exemption left **12.1 % of seats** unable to fill that slot — 46.9 % of
        ``autopilot`` and 47.5 % of ``chalk``, the seats that follow ADP and never reach TE depth.

        The same argument disposes of RB/WR: FLEX absorbs a *surplus*, never a *deficit*, and a
        seat holding one RB cannot fill ``RB/RB`` either. That case was never observed only because
        RB/WR demand is met long before the deadline — an unsound exemption that happened not to
        bind. So demand is now simply :meth:`RosterSlots.base_demand`, which excludes FLEX by
        construction; nothing is exempt and a roster-shape change is picked up for free.
        """
        counts = self.roster_counts(team)
        owed = {p: n - counts.get(p, 0) for p, n in self.slots.base_demand().items()}
        return {p: n for p, n in owed.items() if n > 0}

    def picks_remaining(self, team: int) -> int:
        """Picks this team has left in the draft (every seat gets exactly ``rounds``)."""
        return max(0, self.rounds - len(self.rosters[team]))

    def draftable_pool(self, team: int) -> pd.DataFrame:
        """Available players at a position the team is still under its (soft) cap for, ADP-ascending
        — falls back to the full available board when every under-cap position is exhausted.

        ★ **T20 — one hard filter sits in front of the soft caps.** When a team has exactly as many
        picks left as it has unfilled :meth:`mandatory_needs`, the pool is restricted to those
        positions, so the draft cannot end with an unfillable starting slot. Before T20 nothing did
        this: the caps steer a team *away* from over-drafting and never *toward* completing a
        lineup, so a pure-ADP seat never reached kicker ADP (128–163) inside 15 rounds and no seat
        ever took a defense at all.

        It is deliberately a **filter applied before utility**, the same class of object as
        ``BandSpec``: it changes which candidates exist, never what the fitted β thinks of one, so
        no coefficient is being used outside its estimation conditions. And it is gated on
        ``rounds >= slots.starters`` — in a short draft (a 5-round best-ball, an 8-round mock)
        there is no legal full lineup to protect and forcing a kicker in round 5 would be worse
        than the hole it fills.

        ★ **Widening the need set (T23) cannot deadlock the draft, by induction.** The filter fires
        only at ``picks_remaining <= sum(need)``; every pick it forces is at a needed position, so
        it decrements both sides by exactly one and the invariant is preserved to the last pick.
        The worst case moves from 3 slots to 8, but the extra five are RB/WR/TE demand that an
        ADP-ordered board fills in the first few rounds, so in practice the deadline still binds at
        3–4 picks out. It also stays honest when the board runs dry: ``forced.empty`` falls through
        to the ordinary pool rather than raising, because a season whose board carries five kickers
        for ten seats (2022) has an unfillable slot no policy can fill.
        """
        avail = self.available_board()
        if self.rounds >= self.slots.starters:
            need = self.mandatory_needs(team)
            if need and self.picks_remaining(team) <= sum(need.values()):
                forced = avail[avail["pos"].isin(need)]
                if not forced.empty:
                    return forced
        counts = self.roster_counts(team)
        caps = self.slots.pos_caps
        under = avail["pos"].map(lambda p: counts.get(p, 0) < caps.get(p, 99)).to_numpy()
        pool = avail[under]
        return pool if not pool.empty else avail

    def starter_needs(self, team: int) -> dict[str, int]:
        """Remaining *starter* demand (FLEX-aware) — for richer policies / reporting."""
        counts = self.roster_counts(team)
        base = self.slots.base_demand()
        remaining = {p: max(0, base[p] - counts.get(p, 0)) for p in base}
        flex_used = sum(max(0, counts.get(p, 0) - base.get(p, 0))
                        for p in self.slots.flex_positions)
        remaining["FLEX"] = max(0, self.slots.flex - flex_used)
        return remaining

    def pick_log(self) -> pd.DataFrame:
        return pd.DataFrame(self.log)

    def clone(self, rng: np.random.Generator | None = None) -> DraftState:
        """A detached copy for lookahead rollouts (9.4/9.5): mutating the clone (further picks)
        leaves this state untouched. The board is shared (read-only during a draft); ``available``,
        ``rosters`` and ``log`` are copied. Pass ``rng`` to control the rollout's opponent draws
        (default: a fresh independent stream) so a rollout never consumes this state's rng."""
        return DraftState(
            board=self.board, n_teams=self.n_teams, rounds=self.rounds, slots=self.slots,
            your_team=self.your_team, rng=rng or np.random.default_rng(0), noise=self.noise,
            available=set(self.available), rosters=[list(r) for r in self.rosters],
            log=list(self.log), overall_pick=self.overall_pick,
            skipped_picks=set(self.skipped_picks),      # 17.4: a rollout must forfeit them too
        )


# --------------------------------------------------------------------------------------------
# pick policies
# --------------------------------------------------------------------------------------------
def pick_by_adp(state: DraftState, team: int, noise: float = 0.0) -> int:
    """Draft the lowest-ADP available player the team can still roster, jittered by ``noise``
    (Gaussian, in ADP points). ``noise=0`` is the deterministic best-available-by-ADP pick.

    Caps are **soft**: they steer away from over-drafting a position while an under-cap
    alternative exists, but if every under-cap position is exhausted the team takes the best
    available anyway (a roster is never left short). Roster counts are computed once per pick.
    """
    pool = state.draftable_pool(team)
    key = pool["adp"].to_numpy(dtype=float)
    if noise > 0:
        key = key + state.rng.normal(0.0, noise, size=len(pool))
    return int(pool.index[int(np.argmin(key))])


def adp_pick_fn(state: DraftState) -> int:
    """Default ``your_pick_fn``: pure best-available-by-ADP for your team (no noise)."""
    return pick_by_adp(state, state.your_team, noise=0.0)


def value_pick_fn(state: DraftState) -> int:
    """Your-seat policy that drafts by the board's ``value`` column (lower = draft sooner, on the
    ADP/pick-number scale), falling back to a player's ADP where ``value`` is NaN. This is how a
    ``rank_fn`` (Phase 1.3+) drives your picks: the harness sets ``value = rank_fn(board)``. Soft
    caps apply (via :meth:`DraftState.draftable_pool`)."""
    pool = state.draftable_pool(state.your_team)
    val = pool["value"].to_numpy(dtype=float)
    adp = pool["adp"].to_numpy(dtype=float)
    key = np.where(np.isnan(val), adp, val)
    return int(pool.index[int(np.argmin(key))])


# --------------------------------------------------------------------------------------------
# the simulator
# --------------------------------------------------------------------------------------------
def _prepare_board(board: pd.DataFrame) -> pd.DataFrame:
    """Normalize any ADP frame to canonical columns, drop non-draftable / null-ADP rows,
    sort by ADP and re-index 0..n-1 (the row-labels used throughout the draft).

    Any :data:`PASSTHROUGH_COLS` the caller supplied ride along untouched (16.13), so an enriched
    board reaches ``draftable_pool`` with its risk/value context intact. Columns the caller did not
    supply are simply absent — never synthesized — so an ADP-only board is byte-for-byte what it
    always was.
    """
    name_col = "player_name" if "player_name" in board.columns else "name"
    rank_col = "adp_pos_rank" if "adp_pos_rank" in board.columns else "pos_rank"
    adp = pd.to_numeric(board["adp"], errors="coerce")
    # `value` (lower = draft sooner) drives value_pick_fn; defaults to ADP when no rank_fn set it.
    value = pd.to_numeric(board["value"], errors="coerce") if "value" in board.columns else adp
    b = pd.DataFrame({
        "player_name": board[name_col].astype(str),
        "pos": board["position"].map(canon_pos),
        "adp": adp,
        "pos_rank": board[rank_col] if rank_col in board.columns else np.nan,
        "player_key": board_player_key(board),
        "value": value,
    })
    for c in PASSTHROUGH_COLS:
        if c in board.columns:
            b[c] = board[c]
    b = b[b["pos"].isin(DRAFTABLE) & b["adp"].notna()]
    b = b.sort_values("adp").reset_index(drop=True)
    return b


def simulate_draft(board: pd.DataFrame, your_pick_fn=None, n_teams: int = 10, rounds: int = 15,
                   slots: RosterSlots | None = None, your_team: int = 0, noise: float = 5.0,
                   seed: int | None = None, opponent_pick_fn=None, keepers=()) -> DraftState:
    """Simulate a full ``n_teams`` x ``rounds`` snake draft.

    ``your_pick_fn(state) -> board_label`` drives your seat (defaults to :func:`adp_pick_fn`);
    every other seat picks via ``opponent_pick_fn(state, team) -> board_label`` when supplied
    (Phase 11.3 behavioral/personality opponents), else :func:`pick_by_adp` with ``noise``.
    Reproducible given ``seed``. Returns the final :class:`DraftState`.
    """
    slots = slots or RosterSlots()
    b = _prepare_board(board)
    state = DraftState(
        board=b, n_teams=n_teams, rounds=rounds, slots=slots, your_team=your_team,
        rng=np.random.default_rng(seed), noise=noise,
        available=set(b.index), rosters=[[] for _ in range(n_teams)],
    )
    if keepers:
        apply_keepers(state, keepers)
    return run_to_completion(state, your_pick_fn, opponent_pick_fn)


def apply_keepers(state: DraftState, keepers) -> DraftState:
    """17.4 — seat kept players and forfeit the picks they cost, **before** the draft runs.

    Two things happen, and both are the point:

    1. **The kept player leaves the pool** and lands on his owner's roster, so nobody else can draft
       him and the board everyone else sees is genuinely shorter. Because ADP is a *rank* on the
       remaining board, this is what re-inflates everyone's effective ADP — a stud kept at round 6
       pulls every later player up. There is no separate "ADP adjustment": removing supply *is* the
       adjustment, and doing it any other way would double-count.
    2. **The owning team forfeits that round's pick**, recorded in ``skipped_picks``. That is the
       price, and it is what stops keepers being free: a team keeping three studs drafts three fewer
       times. ``run_to_completion`` skips those slots.

    ``keepers`` is a sequence of :class:`~fantasy_quant.draft.config.Keeper` (``player_key``,
    1-indexed ``team``, ``round``). A ``player_key`` not on the board is ignored — a keeper the
    board never listed cannot be removed from it, and raising would make an ordinary stale-board
    case fatal.
    """
    keys = board_player_key(state.board).astype(str)
    by_key = {k: i for i, k in zip(state.board.index, keys, strict=True)}
    for kp in keepers:
        idx = by_key.get(str(kp.player_key))
        team0 = int(kp.team) - 1
        if not 0 <= team0 < state.n_teams:
            raise ValueError(f"keeper team {kp.team} out of 1..{state.n_teams}")
        if not 1 <= int(kp.round) <= state.rounds:
            raise ValueError(f"keeper round {kp.round} out of 1..{state.rounds}")
        state.skipped_picks.add((team0, int(kp.round)))
        if idx is None:
            continue
        state.available.discard(idx)
        state.rosters[team0].append(idx)
        row = state.board.loc[idx]
        state.log.append({
            "overall_pick": 0, "round": int(kp.round), "team": team0,
            "is_you": team0 == state.your_team, "player_key": str(kp.player_key),
            "player_name": row.get("player_name"), "pos": row.get("pos"),
            "adp": row.get("adp"), "keeper": True,
        })
    return state


def run_to_completion(state: DraftState, your_pick_fn=None, opponent_pick_fn=None) -> DraftState:
    """Drive ``state`` from its current pick to the end of the draft, in place (and return it).

    Your seat uses ``your_pick_fn`` (defaults to :func:`adp_pick_fn`); every other seat uses
    ``opponent_pick_fn(state, team)`` when supplied (11.3), else :func:`pick_by_adp` with
    ``state.noise`` — the MVP ADP+noise baseline. :func:`simulate_draft` runs this from a fresh
    state; the 9.5 win-prob policy runs it on a :meth:`DraftState.clone`.
    """
    pick_fn = your_pick_fn or adp_pick_fn
    while not state.is_done() and state.available:
        team = state.team_on_clock()
        if (team, state.round()) in state.skipped_picks:      # 17.4: forfeited to a keeper
            state.overall_pick += 1
            continue
        if team == state.your_team:
            idx = int(pick_fn(state))
            if idx not in state.available:
                raise ValueError(f"your_pick_fn returned unavailable pick {idx}")
        elif opponent_pick_fn is not None:
            idx = int(opponent_pick_fn(state, team))
            if idx not in state.available:
                raise ValueError(f"opponent_pick_fn returned unavailable pick {idx}")
        else:
            idx = pick_by_adp(state, team, noise=state.noise)
        _apply_pick(state, team, idx)
    return state


def _apply_pick(state: DraftState, team: int, idx: int) -> None:
    row = state.board.loc[idx]
    state.available.discard(idx)
    state.rosters[team].append(idx)
    state.log.append({
        "overall_pick": state.overall_pick,
        "round": state.round(),
        "pick_in_round": state.pick_in_round(),
        "team": team,
        "is_you": team == state.your_team,
        "player_key": row["player_key"],
        "player_name": row["player_name"],
        "pos": row["pos"],
        "adp": float(row["adp"]),
        "pos_rank": row["pos_rank"],
    })
    state.overall_pick += 1
