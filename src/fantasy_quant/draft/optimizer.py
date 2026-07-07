"""Personalization spine · step 2 — the constrained greedy optimizer.

Given a :class:`~fantasy_quant.draft.config.DraftConfig`, build the best roster the user's
constraints allow, **planning around ADP availability**. This is the MVP form of §7 (and a first cut
of the Phase-9 draft policy): a greedy that at each pick takes the highest **risk-adjusted
value-over-replacement** player, after (a) removing hard excludes, (b) bending priority by the soft
archetype + per-player tilts, and (c) honoring must-draft players *as late as their reach budget and
ADP allow* — never reaching when a player will fall to you anyway.

The three signals stay separate (PERSONALIZATION §2): **value** is ``base_value`` = risk-adjusted
VBD (Phase-4 consensus→VBD, risk-dialed by λ through the Phase-5 certainty equivalent);
**availability** is the ADP board + the ADP+noise opponents baked into the simulator (the MVP
opponent model); **variance** rides inside ``base_value`` via λ. The unconstrained peer (same seat,
same λ, no preferences — :meth:`DraftConfig.benchmark`) runs the identical machinery, so the
cost report (step 3) isolates a pure *preference* cost.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fantasy_quant.backtest.metrics import replacement_ranks
from fantasy_quant.backtest.walkforward import draft_date, preseason_board
from fantasy_quant.draft.config import DraftConfig
from fantasy_quant.draft.simulator import DraftState, RosterSlots, simulate_draft
from fantasy_quant.projections import distribution
from fantasy_quant.valuation import utility
from fantasy_quant.valuation.value_board import value_board

DEFAULT_NOISE = 5.0


# ------------------------------------------------------------------------------------------------
# the value signal (built once, reused by the personalized draft and its benchmark)
# ------------------------------------------------------------------------------------------------
def _replacement_from(values: pd.Series, positions: pd.Series, slots: RosterSlots,
                      n_teams: int) -> dict[str, float]:
    """Positional replacement level = the value at each position's replacement rank (QB10/RB24/…),
    computed on whatever value column is passed (here the risk-adjusted CE)."""
    ranks = replacement_ranks(slots, n_teams)
    out = {}
    for pos, rank in ranks.items():
        v = np.sort(values[positions == pos].to_numpy(float))[::-1]
        out[pos] = float(v[min(rank - 1, len(v) - 1)]) if len(v) else 0.0
    return out


def assemble_value(con, season: int, config: DraftConfig, as_of=None) -> pd.DataFrame:
    """The value index the optimizer drafts against, keyed by ``player_key``.

    ``base_value`` = **risk-adjusted value-over-replacement**: the Phase-5 certainty equivalent
    (mean − λ·Var) minus its own positional replacement level, so cross-position priority is on the
    VBD scale *and* carries the risk dial. Players with no distribution (rare — e.g. a body the
    Phase-5 board misses) fall back to the plain Phase-4 VBD; team defenses carry no projection and
    stay on ADP (``base_value`` NaN → the simulator's ADP fallback).
    """
    lg = config.league
    vb = value_board(con, season, as_of, ruleset=lg.ruleset, slots=lg.slots, n_teams=lg.n_teams)
    dist, _ = distribution.assemble_distribution(con, season, ruleset=lg.ruleset)
    ceb = utility.risk_adjusted_board(dist, lam=config.risk_lambda)

    ce_repl = _replacement_from(ceb["ce_value"], ceb["pos"], lg.slots, lg.n_teams)
    ceb = ceb.assign(ce_vbd=ceb["ce_value"] - ceb["pos"].map(ce_repl))

    merged = pd.merge(
        vb[["player_key", "pos", "proj_points", "vbd"]],
        ceb[["player_key", "pos", "mean", "sd", "ce_value", "ce_vbd"]],
        on="player_key", how="outer", suffixes=("_vb", "_ce"),
    )
    merged["pos"] = merged["pos_vb"].where(merged["pos_vb"].notna(), merged["pos_ce"])
    merged["base_value"] = merged["ce_vbd"].where(merged["ce_vbd"].notna(), merged["vbd"])
    cols = ["player_key", "pos", "proj_points", "vbd", "mean", "sd", "ce_value", "ce_vbd",
            "base_value"]
    return merged[cols]


def attach_value(board_adp: pd.DataFrame, value_index: pd.DataFrame) -> pd.DataFrame:
    """Merge ``base_value`` onto a PIT ADP board and set the simulator's ``value`` priority column
    (lower = draft sooner). Higher value → lower priority rank; unvalued rows stay NaN so the pick
    policy falls back to their ADP (matching the Phase-1 harness convention)."""
    b = board_adp.copy()
    gsis = b["gsis_id"] if "gsis_id" in b.columns else pd.Series(pd.NA, index=b.index)
    name = b["name"] if "name" in b.columns else b.get("player_name")
    pk = gsis.where(gsis.notna(), name)
    bv = (value_index.dropna(subset=["base_value"]).drop_duplicates("player_key")
          .set_index("player_key")["base_value"])
    b["base_value"] = pk.map(bv)
    b["value"] = (-b["base_value"]).rank(method="first")     # 1 = best value = draft first
    return b


def team_value(roster: pd.DataFrame, value_index: pd.DataFrame) -> float:
    """A roster's total ``base_value`` (risk-adjusted value-over-replacement); unvalued picks (DST)
    contribute 0. The common yardstick the cost report differences between two rosters."""
    bv = (value_index.dropna(subset=["base_value"]).drop_duplicates("player_key")
          .set_index("player_key")["base_value"])
    return float(roster["player_key"].map(bv).fillna(0.0).sum())


# ------------------------------------------------------------------------------------------------
# snake geometry helpers (pure) — "when do I pick next?"
# ------------------------------------------------------------------------------------------------
def _team_on_clock(overall: int, n_teams: int) -> int:
    """0-indexed seat picking at 1-indexed ``overall`` pick (snake). Matches DraftState."""
    rnd0, idx = (overall - 1) // n_teams, (overall - 1) % n_teams
    return idx if rnd0 % 2 == 0 else n_teams - 1 - idx


def _next_own_pick(overall: int, seat: int, n_teams: int, last: int) -> int | None:
    """The next overall pick number after ``overall`` that belongs to ``seat`` (None if the draft
    ends first) — how the must-draft logic knows whether a player can wait one more turn."""
    for q in range(overall + 1, last + 1):
        if _team_on_clock(q, n_teams) == seat:
            return q
    return None


# ------------------------------------------------------------------------------------------------
# the constrained greedy pick policy
# ------------------------------------------------------------------------------------------------
def _must_now(state: DraftState, config: DraftConfig, margin: float) -> int | None:
    """The must-draft urgency rule: return a must-draft player's board index iff he is legal to
    roster, we're within his reach budget, and he is *unlikely to survive to our next pick*
    (ADP ≤ next-pick + a noise margin). Waiting as long as the budget allows preserves value; this
    fires only at the last responsible moment. Most-urgent (smallest ADP slack) wins ties."""
    if not config.must_draft:
        return None
    seat, p = state.your_team, state.overall_pick
    last = state.n_teams * state.rounds
    nxt = _next_own_pick(p, seat, state.n_teams, last)
    avail = state.available_board()
    best: tuple[float, int] | None = None
    for md in config.must_draft:
        rows = avail[avail["player_key"] == md.player_key]
        if rows.empty or not state.can_draft(seat, rows["pos"].iloc[0]):
            continue
        adp = float(rows["adp"].iloc[0])
        within_budget = p >= adp - md.reach_budget * state.n_teams
        will_last = nxt is not None and adp > nxt + margin
        if within_budget and not will_last:
            slack = adp - p
            if best is None or slack < best[0]:
                best = (slack, int(rows.index[0]))
    return best[1] if best else None


def personalized_pick_fn(config: DraftConfig, noise: float = DEFAULT_NOISE):
    """Build the ``your_pick_fn`` the simulator drives your seat with, from a resolved config."""
    margin = max(noise, 1.0)

    def pick_fn(state: DraftState) -> int:
        seat = state.your_team
        pool = state.draftable_pool(seat)
        if config.never_draft:                                   # hard exclude
            pool = pool[~pool["player_key"].isin(config.never_draft)]
            if pool.empty:                                       # never leave a slot unfilled
                av = state.available_board()
                av = av[~av["player_key"].isin(config.never_draft)]
                pool = av if not av.empty else state.available_board()

        forced = _must_now(state, config, margin)                # secure must-draft in time
        if forced is not None and forced in state.available:
            return forced

        rnd = state.round()
        counts = state.roster_counts(seat)                       # for state-aware archetypes
        base = pool["value"].to_numpy(float)
        base = np.where(np.isnan(base), pool["adp"].to_numpy(float), base)   # ADP fallback
        tilt = np.fromiter(
            (config.total_tilt_rounds(pk, pos, rnd, counts.get(pos, 0))
             for pk, pos in zip(pool["player_key"], pool["pos"], strict=False)),
            dtype=float, count=len(pool),
        )
        eff = base - state.n_teams * tilt                        # + tilt rounds → sooner
        return int(pool.index[int(np.argmin(eff))])

    return pick_fn


# ------------------------------------------------------------------------------------------------
# the driver
# ------------------------------------------------------------------------------------------------
def optimize_draft(con, season: int, config: DraftConfig, value_index: pd.DataFrame | None = None,
                   noise: float = DEFAULT_NOISE, seed: int = 0) -> DraftState:
    """Draft a personalized roster for ``season`` from ``config``'s seat, PIT.

    Pass a shared ``value_index`` (from :func:`assemble_value`) to draft several configs against the
    same value signal — the cost report reuses one index across the personalized team, benchmark,
    and every leave-one-out redraft, so only the config differs.
    """
    lg = config.league
    as_of = draft_date(con, season)
    if as_of is None:
        raise ValueError(f"no PIT ADP board for {season} — can't plan around availability")
    board = preseason_board(con, season, as_of)
    if value_index is None:
        value_index = assemble_value(con, season, config, as_of)
    board = attach_value(board, value_index)
    return simulate_draft(board, your_pick_fn=personalized_pick_fn(config, noise),
                          n_teams=lg.n_teams, rounds=lg.rounds, slots=lg.slots,
                          your_team=lg.your_team, noise=noise, seed=seed)
