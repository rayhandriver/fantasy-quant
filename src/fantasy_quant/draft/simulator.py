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


def canon_pos(pos) -> str | None:
    """FFC/nflverse position -> canonical ``QB/RB/WR/TE/K/DST`` (or None if not draftable)."""
    return _CANON.get(str(pos).upper().strip())


@dataclass(frozen=True)
class RosterSlots:
    """The league roster: starter slots + bench, and per-position roster **caps** the ADP
    opponents respect so they build realistic rosters (no 8-QB teams). Baseline = 10-team,
    9-starter QB/2RB/2WR/TE/FLEX(RB/WR/TE)+K+DST, 6 bench (15 total)."""
    qb: int = 1
    rb: int = 2
    wr: int = 2
    te: int = 1
    flex: int = 1
    k: int = 1
    dst: int = 1
    bench: int = 6
    flex_positions: tuple[str, ...] = ("RB", "WR", "TE")
    pos_caps: dict[str, int] = field(
        default_factory=lambda: {"QB": 2, "RB": 6, "WR": 6, "TE": 2, "K": 1, "DST": 1}
    )

    @property
    def starters(self) -> int:
        return self.qb + self.rb + self.wr + self.te + self.flex + self.k + self.dst

    @property
    def total(self) -> int:
        return self.starters + self.bench

    def base_demand(self) -> dict[str, int]:
        """Fixed (non-FLEX) starter demand per position."""
        return {"QB": self.qb, "RB": self.rb, "WR": self.wr, "TE": self.te,
                "K": self.k, "DST": self.dst}


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

    def draftable_pool(self, team: int) -> pd.DataFrame:
        """Available players at a position the team is still under its (soft) cap for, ADP-ascending
        — falls back to the full available board when every under-cap position is exhausted."""
        avail = self.available_board()
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
    sort by ADP and re-index 0..n-1 (the row-labels used throughout the draft)."""
    name_col = "player_name" if "player_name" in board.columns else "name"
    rank_col = "adp_pos_rank" if "adp_pos_rank" in board.columns else "pos_rank"
    key_col = "gsis_id" if "gsis_id" in board.columns else name_col
    adp = pd.to_numeric(board["adp"], errors="coerce")
    # `value` (lower = draft sooner) drives value_pick_fn; defaults to ADP when no rank_fn set it.
    value = pd.to_numeric(board["value"], errors="coerce") if "value" in board.columns else adp
    b = pd.DataFrame({
        "player_name": board[name_col].astype(str),
        "pos": board["position"].map(canon_pos),
        "adp": adp,
        "pos_rank": board[rank_col] if rank_col in board.columns else np.nan,
        "player_key": board[key_col].where(board[key_col].notna(), board[name_col]),
        "value": value,
    })
    b = b[b["pos"].isin(DRAFTABLE) & b["adp"].notna()]
    b = b.sort_values("adp").reset_index(drop=True)
    return b


def simulate_draft(board: pd.DataFrame, your_pick_fn=None, n_teams: int = 10, rounds: int = 15,
                   slots: RosterSlots | None = None, your_team: int = 0, noise: float = 5.0,
                   seed: int | None = None) -> DraftState:
    """Simulate a full ``n_teams`` x ``rounds`` snake draft.

    ``your_pick_fn(state) -> board_label`` drives your seat (defaults to :func:`adp_pick_fn`);
    every other seat picks via :func:`pick_by_adp` with ``noise``. Reproducible given ``seed``.
    Returns the final :class:`DraftState` (``.your_roster()``, ``.pick_log()``, ``.rosters``).
    """
    slots = slots or RosterSlots()
    b = _prepare_board(board)
    state = DraftState(
        board=b, n_teams=n_teams, rounds=rounds, slots=slots, your_team=your_team,
        rng=np.random.default_rng(seed), noise=noise,
        available=set(b.index), rosters=[[] for _ in range(n_teams)],
    )
    pick_fn = your_pick_fn or adp_pick_fn

    while not state.is_done() and state.available:
        team = state.team_on_clock()
        if team == your_team:
            idx = int(pick_fn(state))
            if idx not in state.available:
                raise ValueError(f"your_pick_fn returned unavailable pick {idx}")
        else:
            idx = pick_by_adp(state, team, noise=noise)
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
