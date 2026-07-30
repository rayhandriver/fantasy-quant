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

**Phase 8 upgrade (2026-07-09, Phase-9.1 pulled forward): the greedy is covariance-aware.** The
marginal certainty equivalent of adding player *j* to roster *R* is

    ΔCE(j|R) = base_value_j − 2λ · σ_j · Σ_{i∈R, same team} ρ_ij σ_i

so each pick's priority is the *portfolio* CE, not the standalone one: doubling up on one offense
now pays its covariance price at draft time. ρ comes from the shrunk :class:`CorrelationModel`
(8.2, fit PIT on strictly-prior DEV seasons; draft-time roles from ADP order within team). The
penalty is mapped through the static value→rank curve, so ADP-fallback (K/DST) timing and every
must/never/tilt mechanic are unchanged, and λ=0 reproduces the covariance-blind greedy exactly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.special import ndtr

from fantasy_quant.backtest.metrics import replacement_ranks
from fantasy_quant.backtest.scoring import RuleSet
from fantasy_quant.backtest.walkforward import draft_date, preseason_board
from fantasy_quant.config import DEV_SEASONS
from fantasy_quant.covariance.estimate import MAX_ROLE_RANK
from fantasy_quant.covariance.shrinkage import CorrelationModel, estimate_correlation_model
from fantasy_quant.draft.config import DraftConfig
from fantasy_quant.draft.simulator import (
    DraftState,
    RosterSlots,
    _apply_pick,
    canon_pos,
    run_to_completion,
    simulate_draft,
)
from fantasy_quant.projections import distribution
from fantasy_quant.valuation import utility
from fantasy_quant.valuation.value_board import value_board

DEFAULT_NOISE = 5.0
# 9.1/9.4 scarcity+lookahead: how much of a candidate's availability-gated positional cliff is
# added to his priority value (points-over-replacement units). Modest — value still leads, scarcity
# only breaks ties toward the player at a thin position who won't survive to your next pick.
DEFAULT_SCARCITY_W = 0.5
SCARCITY_HORIZON = 3          # the cliff is the value drop to the 3rd-next same-position player


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


def _board_teams(board_adp: pd.DataFrame) -> pd.DataFrame:
    """PIT team + within-team depth role per ``player_key``, straight off the ADP board.

    ``role_rank`` = ADP order within (team, position) capped at :data:`MAX_ROLE_RANK` — the
    market's own read of who is the WR1/RB2 *at draft time* (the correlation model was estimated on
    realized roles; applying it at ADP-implied roles is the PIT-consistent choice, documented)."""
    gsis = board_adp["gsis_id"] if "gsis_id" in board_adp.columns else pd.Series(
        pd.NA, index=board_adp.index)
    t = pd.DataFrame({
        "player_key": gsis.where(gsis.notna(), board_adp["name"]),
        "team": board_adp.get("team"),
        "pos_c": board_adp["position"].map(canon_pos),
        "adp": pd.to_numeric(board_adp["adp"], errors="coerce"),
    }).dropna(subset=["team", "pos_c", "adp"])
    t["role_rank"] = (t.groupby(["team", "pos_c"])["adp"]
                      .rank(method="first").clip(upper=MAX_ROLE_RANK).astype(int))
    return t.drop_duplicates("player_key")[["player_key", "team", "role_rank"]]


def assemble_value(con, season: int, config: DraftConfig, as_of=None,
                   seed: int = 0) -> pd.DataFrame:
    """The value index the optimizer drafts against, keyed by ``player_key``.

    ``base_value`` = **risk-adjusted value-over-replacement**: the Phase-5 certainty equivalent
    (mean − λ·Var) minus its own positional replacement level, so cross-position priority is on the
    VBD scale *and* carries the risk dial. Players with no distribution (rare — e.g. a body the
    Phase-5 board misses) fall back to the plain Phase-4 VBD; team defenses carry no projection and
    stay on ADP (``base_value`` NaN → the simulator's ADP fallback). Also carries each player's PIT
    ``team`` + ``role_rank`` (from the ADP board) so the covariance layer can price same-team
    co-movement.

    ``seed`` selects the shared Phase-5 draw cloud (T6): pass the same seed the season sim uses and
    the value the greedy drafts against is scored on the *same* joint draws (see
    :func:`fantasy_quant.projections.distribution.cached_distribution`).
    """
    lg = config.league
    if as_of is None:
        as_of = draft_date(con, season)
    vb = value_board(con, season, as_of, ruleset=lg.ruleset, slots=lg.slots, n_teams=lg.n_teams)
    dist = distribution.cached_distribution(con, season, ruleset=lg.ruleset, seed=seed)[0]
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
    if as_of is not None:
        merged = merged.merge(_board_teams(preseason_board(con, season, as_of)),
                              on="player_key", how="left")
    else:
        merged["team"], merged["role_rank"] = pd.NA, pd.NA
    cols = ["player_key", "pos", "proj_points", "vbd", "mean", "sd", "ce_value", "ce_vbd",
            "base_value", "team", "role_rank"]
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
    contribute 0. The independent-players yardstick — :func:`portfolio_value` adds the covariance
    cross-terms.

    ⚠ **Slot-blind by definition** (T28): this is *total roster capital*, so a bench QB2 counts in
    full. :func:`starter_value` is the startable-lineup companion; report them side by side and
    label them, never substitute one for the other — this one is the frozen cost report's input.
    """
    return float(roster["player_key"].map(_bv_map(value_index)).fillna(0.0).sum())


def _bv_map(value_index: pd.DataFrame) -> pd.Series:
    """``player_key -> base_value`` (one row per key). The single lookup :func:`team_value` and
    :func:`starter_value` share, so the two metrics can never disagree about a player's value —
    only about whether he is in the lineup."""
    return (value_index.dropna(subset=["base_value"]).drop_duplicates("player_key")
            .set_index("player_key")["base_value"])


def starter_value(roster: pd.DataFrame, value_index: pd.DataFrame,
                  slots: RosterSlots | None = None) -> float:
    """The roster's **startable** ``base_value``: the best legal starting lineup, not the sum of
    fifteen players (T28).

    ★ **Why this ships beside** :func:`team_value` **and never as an edit to it.** ``team_value``
    sums ``base_value`` over every roster row, so a bench QB2 is priced as though he starts — on the
    2026 walkthrough the second QB alone moved a team's headline by −101.6 (Caleb Williams), −92.1
    (Kyler Murray) and +51.0 (Hurts) against a room total of 1,938. But ``team_value`` is also what
    the frozen cost report differences and what the spent lockbox was evaluated on, so its numbers
    are output, not opinion. Two labelled metrics, never one silently redefined — the T18 rule
    (*a column whose meaning changes needs a new name*).

    **The slot logic is not reimplemented here.** It is
    :func:`~fantasy_quant.simulation.season.lineup_points_matrix`, the same vectorized solver the
    Phase-10 season sim scores every week with (itself regression-tested against the Phase-1.3
    reference), called on a value vector instead of a points vector. A third lineup solver is
    exactly how two parts of a repo start disagreeing about what "starting" means.

    Unvalued rows (team defenses carry no projection) contribute 0.0, matching ``team_value`` — so
    on a roster that *is* the starting nine the two functions return the same number by
    construction, which is bar **B4**.
    """
    slots = slots or RosterSlots()
    if roster.empty:
        return 0.0
    bv = _bv_map(value_index)
    vals = roster["player_key"].map(bv).fillna(0.0).to_numpy(float)
    from fantasy_quant.simulation.season import lineup_points_matrix
    return float(np.ravel(lineup_points_matrix(vals[:, None], roster["pos"].tolist(), slots))[0])


def starter_marginal(cand_values: np.ndarray, pos: str, roster_by_pos: dict[str, np.ndarray],
                     slots: RosterSlots) -> np.ndarray:
    """Vectorized ``starter_value(roster + one player at ``pos``) − starter_value(roster)`` for a
    whole array of candidate values — the pick-path form of :func:`starter_value`.

    Calling :func:`starter_value` once per candidate would be ~16M solver calls across a batch
    measurement, so this evaluates the same piecewise-linear function in closed form. It is **not**
    a second definition of "starting": ``test_phase9`` asserts it equals the
    :func:`starter_value` difference on random rosters, which is what keeps the fast path honest.

    ``roster_by_pos`` maps position -> that position's current ``base_value``s (any order).
    """
    need = slots.base_demand()

    # 17.1 — the closed form below reasons about **one** flex slot. Rather than approximate a
    # multi-flex or superflex roster with it, route those formats to the exact solver: build the
    # candidates along the trailing axis `lineup_points_matrix` already vectorizes over, so this
    # stays one call, not a loop. (A silently-approximate fast path is how the repo's two lineup
    # solvers would start disagreeing again — see `starter_value`'s docstring.)
    if len(slots.flex_groups()) > 1 or slots.total_flex() > 1:
        from fantasy_quant.simulation.season import lineup_points_matrix
        cand = np.asarray(cand_values, float)
        base_vals, base_pos = [], []
        for q, arr in roster_by_pos.items():
            a = np.asarray(arr, float)
            base_vals.append(a)
            base_pos += [q] * len(a)
        stack = np.concatenate(base_vals) if base_vals else np.empty(0)
        base_total = float(np.ravel(lineup_points_matrix(
            stack[:, None], base_pos, slots))[0]) if len(stack) else 0.0
        safe = np.where(np.isfinite(cand), cand, 0.0)
        mat = np.vstack([np.repeat(stack[:, None], len(cand), axis=1), safe[None, :]]) \
            if len(stack) else safe[None, :]
        totals = np.asarray(lineup_points_matrix(mat, [*base_pos, pos], slots), float)
        return np.where(np.isfinite(cand), totals - base_total, np.nan)

    flex_ok = bool(slots.flex) and pos in slots.flex_positions
    n_p = int(need.get(pos, 0))

    def top(arr: np.ndarray, k: int) -> float:
        return float(np.sort(arr)[::-1][:k].sum()) if k > 0 and len(arr) else 0.0

    def nth(arr: np.ndarray, k: int) -> float:
        s = np.sort(arr)[::-1]
        return float(s[k]) if len(s) > k else -np.inf

    mine = np.asarray(roster_by_pos.get(pos, np.empty(0)), float)
    # the best flex candidate the *other* flex-eligible positions already offer
    other_flex = -np.inf
    if slots.flex:
        for q, arr in roster_by_pos.items():
            if q == pos or q not in slots.flex_positions:
                continue
            other_flex = max(other_flex, nth(np.asarray(arr, float), int(need.get(q, 0))))

    base_ded = top(mine, n_p)
    base_flex = max(nth(mine, n_p), other_flex) if slots.flex else -np.inf
    base = base_ded + (base_flex if np.isfinite(base_flex) else 0.0)

    out = np.empty(len(cand_values), float)
    for i, v in enumerate(np.asarray(cand_values, float)):
        if not np.isfinite(v):
            out[i] = np.nan
            continue
        new = np.concatenate([mine, [v]])
        ded = top(new, n_p)
        fl = max(nth(new, n_p), other_flex) if (slots.flex and flex_ok) else base_flex
        out[i] = ded + (fl if np.isfinite(fl) else 0.0) - base
    return out


def cross_covariance(roster: pd.DataFrame, value_index: pd.DataFrame,
                     corr: CorrelationModel) -> float:
    """The roster's same-team covariance cross-terms ``Σ_{i<j} ρ_ij σ_i σ_j`` (season-points²).
    Positive = the roster concentrates co-moving outcomes (stacks); negative = it hedges."""
    if "sd" not in value_index.columns or "team" not in value_index.columns:
        return 0.0                               # pre-Phase-8 value index: no covariance info
    vi = (value_index.dropna(subset=["sd", "team"]).drop_duplicates("player_key")
          .set_index("player_key"))
    keys = [k for k in roster["player_key"] if k in vi.index]
    m = vi.loc[keys]
    total = 0.0
    for i in range(len(m)):
        for j in range(i + 1, len(m)):
            if m["team"].iloc[i] != m["team"].iloc[j]:
                continue
            rho = corr.rho(m["pos"].iloc[i], int(m["role_rank"].iloc[i] or 1),
                           m["pos"].iloc[j], int(m["role_rank"].iloc[j] or 1))
            total += rho * float(m["sd"].iloc[i]) * float(m["sd"].iloc[j])
    return total


def portfolio_value(roster: pd.DataFrame, value_index: pd.DataFrame, corr: CorrelationModel,
                    lam: float) -> float:
    """The roster's **portfolio certainty equivalent** on the VBD scale:

        Σ base_value_i − 2λ · Σ_{i<j same team} ρ_ij σ_i σ_j

    ``base_value`` already charges each player's own λ·Var; the cross-term charges (or credits)
    the co-movement the Phase-8 Σ prices. This is the objective the covariance-aware greedy climbs
    and the yardstick the cost report differences (λ=0 collapses to :func:`team_value`)."""
    return team_value(roster, value_index) - 2.0 * lam * cross_covariance(roster, value_index,
                                                                          corr)


# ------------------------------------------------------------------------------------------------
# the PIT correlation model (memoized — the cost report drafts the same season dozens of times)
# ------------------------------------------------------------------------------------------------
_CORR_CACHE: dict[tuple, CorrelationModel] = {}


def assemble_correlation(con, season: int, ruleset: RuleSet | None = None) -> CorrelationModel:
    """The shrunk same-team correlation model for drafting ``season`` — fit on strictly-prior DEV
    seasons (PIT; the same convention as the distribution assembler). Prior-only (neutral) when no
    history exists. Memoized per (season, ruleset)."""
    rs = ruleset or RuleSet()
    key = (int(season), rs.model_dump_json())
    if key not in _CORR_CACHE:
        train = [s for s in DEV_SEASONS if s < int(season)]
        _CORR_CACHE[key] = estimate_correlation_model(con, train, rs)
    return _CORR_CACHE[key]


# ------------------------------------------------------------------------------------------------
# 9.1 positional scarcity + 9.4 availability lookahead (pure — the unit-test targets)
# ------------------------------------------------------------------------------------------------
def positional_cliff(keys, positions, bv: dict[str, float],
                     horizon: int = SCARCITY_HORIZON) -> np.ndarray:
    """The **value cliff** below each player at his own position in the current pool (9.1 scarcity).

    For each valued player: ``base_value`` minus the value of the ``horizon``-th next-best available
    same-position player (or the thinnest available one if fewer remain), floored at 0. A steep
    cliff = a scarce tier that won't refill → addressing it is urgent; a flat tier (many similar
    players) = ~0 → safe to wait. Pure pool structure; the timing gate is :func:`survival_prob`.
    """
    vals = np.array([bv.get(k, np.nan) for k in keys], float)
    pos = np.asarray(list(positions), dtype=object)
    out = np.zeros(len(vals))
    for p in {q for q in pos if q is not None}:
        ix = np.where(pos == p)[0]
        order = ix[np.argsort(-np.nan_to_num(vals[ix], nan=-np.inf))]   # value-desc, NaNs last
        rv = vals[order]
        for r, gi in enumerate(order):
            if not np.isfinite(vals[gi]):
                continue
            fb = rv[min(r + horizon, len(rv) - 1)]
            out[gi] = max(0.0, vals[gi] - (fb if np.isfinite(fb) else 0.0))
    return out


def survival_prob(adp, window_end: float | None, noise: float) -> np.ndarray:
    """P(a player is still available at your next pick) from ADP + opponent noise (9.4 lookahead).

    Opponents pick ≈ best-available by ADP + Gaussian(noise); a player with ADP ``a`` survives the
    ``window_end`` picks before your next turn iff his noised draft slot lands past it —
    ``Φ((a − window_end)/noise)``. ``window_end=None`` (no further pick of yours) ⇒ all survive
    (1.0), so nothing is urgent. Returns an array aligned to ``adp``.
    """
    a = np.asarray(adp, float)
    if window_end is None:
        return np.ones_like(a)
    return ndtr((a - float(window_end)) / max(noise, 1.0))


# ------------------------------------------------------------------------------------------------
# the risk model the covariance-aware pick policy consults
# ------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class RiskModel:
    """Everything the pick policy needs to price a candidate's *marginal* covariance: per-player
    σ/team/role, the correlation lookup, λ, and the static base_value→priority-rank curve the
    penalty is mapped through (so a points-space penalty moves a player a calibrated number of
    *picks* down the board, and the ADP-fallback scale is preserved)."""
    lam: float
    corr: CorrelationModel
    bv: dict[str, float] = field(repr=False)
    sd: dict[str, float] = field(repr=False)
    team: dict[str, str] = field(repr=False)
    pos: dict[str, str] = field(repr=False)
    role: dict[str, int] = field(repr=False)
    rank_x: np.ndarray = field(repr=False)     # base_value, ascending
    rank_y: np.ndarray = field(repr=False)     # matching priority rank (1 = draft first)
    scarcity_w: float = 0.0                    # 9.1/9.4 urgency weight (0 = covariance-only greedy)
    noise: float = DEFAULT_NOISE               # opponent ADP noise the survival model assumes
    #: Phase-16.12 **opt-in** availability drift: player_key -> picks earlier than the board says.
    #: Empty (the default) leaves this class bit-identical to its pre-16.12 behaviour, which
    #: `tests/test_drift_consumption.py` asserts by re-running the frozen greedy.
    hype: dict[str, float] = field(default_factory=dict, repr=False)
    #: ★ **T28 — how much of a candidate's value counts when he would sit on the bench.**
    #:
    #:     v_eff = Δstarter(j | roster) + bench_weight · (base_value_j − Δstarter(j | roster))
    #:
    #: ``1.0`` (the default) is **exactly** ``base_value``, so the shipped greedy, the frozen cost
    #: report and every T15/T24 bar are untouched — the algebra collapses term-for-term, and
    #: `test_phase9` re-runs the greedy to prove it rather than trusting the algebra. ``0.0`` prices
    #: a pick purely by what it adds to the best legal starting lineup, which is the behaviour T28
    #: asks about: `value_hawk` took Jaxson Dart as a *second* QB at 9.09 because a slot-blind sum
    #: says a +33.1 bench QB is worth +33.1.
    #:
    #: Anything strictly between the two says bench depth has **option value** — which it does, via
    #: injury and bye weeks — without pretending a QB2 starts. It is one knob because that is what
    #: makes the A/B legible (T24's lesson: *moving two knobs together wore the wrong credit for
    #: three runs*).
    bench_weight: float = 1.0
    #: The roster shape the starter marginal is computed against; ``None`` = the league default.
    slots: RosterSlots | None = None

    def _candidate_values(self, pool: pd.DataFrame, roster: pd.DataFrame) -> np.ndarray:
        """Each candidate's value on the objective this model carries (T28).

        ``bench_weight == 1.0`` returns ``base_value`` itself — the same ``dict.get`` the pre-T28
        loop did, in the same order, so the shipped path is not merely equivalent but identical.
        Below 1.0 the value becomes the blend documented on :attr:`bench_weight`, computed through
        :func:`starter_marginal` (which is regression-tested against :func:`starter_value`).
        """
        keys = list(pool["player_key"])
        base = np.array([self.bv.get(k, np.nan) for k in keys], float)
        if self.bench_weight >= 1.0:
            return base

        slots = self.slots or RosterSlots()
        by_pos: dict[str, list[float]] = {}
        for k in roster["player_key"]:
            p, v = self.pos.get(k), self.bv.get(k)
            if p and v is not None and np.isfinite(v):
                by_pos.setdefault(p, []).append(float(v))
        roster_by_pos = {p: np.asarray(v, float) for p, v in by_pos.items()}

        out = base.copy()
        pos_arr = np.asarray(list(pool["pos"]), dtype=object)
        for p in {q for q in pos_arr if q is not None}:
            ix = np.where(pos_arr == p)[0]
            marg = starter_marginal(base[ix], str(p), roster_by_pos, slots)
            out[ix] = marg + self.bench_weight * (base[ix] - marg)
        return out

    def effective_rank(self, pool: pd.DataFrame, roster: pd.DataFrame,
                       window_end: float | None = None) -> np.ndarray:
        """Covariance- **and scarcity-** adjusted priority rank per pool row (NaN where unvalued →
        ADP fallback), through the static value→rank curve:

            rank( base_value_j − 2λ·σ_j·Σ_{i∈roster, same team} ρ_ij σ_i
                              + scarcity_w · cliff_j · P(j gone by my next pick) )

        The covariance term (Phase 8) charges same-team co-movement; the scarcity term (9.1 cliff ×
        9.4 availability) adds urgency only when a candidate is *both* well above his positional
        fallback *and* unlikely to survive to ``window_end``. ``scarcity_w=0`` reproduces the
        covariance-only greedy exactly (regression-tested)."""
        mine = [(self.team.get(k), self.pos.get(k), self.role.get(k, 1), self.sd.get(k))
                for k in roster["player_key"]]
        mine = [m for m in mine if m[0] and m[3] and np.isfinite(m[3])]
        my_teams = {t for t, _, _, _ in mine}

        if self.scarcity_w > 0:
            cliff = positional_cliff(pool["player_key"], pool["pos"], self.bv)
            adp = pool["adp"].to_numpy(float)
            if self.hype:
                # 16.12(b): a hyped player's *effective* draft cost is earlier, so he is likelier
                # to be gone by your next turn — "he won't last, consider reaching". Opt-in only;
                # an empty `hype` skips this entirely and leaves `adp` the identical object.
                adp = adp - np.array([self.hype.get(k, 0.0) for k in pool["player_key"]], float)
            p_gone = 1.0 - survival_prob(adp, window_end, self.noise)
            urgency = self.scarcity_w * cliff * p_gone
        else:
            urgency = np.zeros(len(pool))

        vals = self._candidate_values(pool, roster)

        out = np.full(len(pool), np.nan)
        for n, (pk, pos) in enumerate(zip(pool["player_key"], pool["pos"], strict=False)):
            v = vals[n]
            if v is None or not np.isfinite(v):
                continue
            pen = 0.0
            tj, sj = self.team.get(pk), self.sd.get(pk)
            if tj in my_teams and sj and np.isfinite(sj):
                rj = self.role.get(pk, 1)
                for ti, pi, ri, si in mine:
                    if ti == tj:
                        pen += 2.0 * self.lam * sj * si * self.corr.rho(pi, ri, pos, rj)
            out[n] = float(np.interp(v - pen + urgency[n], self.rank_x, self.rank_y))
        return out


def build_risk_model(board: pd.DataFrame, value_index: pd.DataFrame, corr: CorrelationModel,
                     lam: float, scarcity_w: float = DEFAULT_SCARCITY_W,
                     noise: float = DEFAULT_NOISE,
                     hype: dict[str, float] | None = None,
                     bench_weight: float = 1.0,
                     slots: RosterSlots | None = None) -> RiskModel:
    """Assemble the :class:`RiskModel` from a value-attached board + the value index. The rank
    curve interpolates the board's own ``base_value → value`` mapping, so a zero penalty reproduces
    the static rank (and λ=0, ``scarcity_w=0`` the covariance-blind, myopic draft) exactly.
    ``scarcity_w`` weights the 9.1/9.4 urgency term; ``noise`` is the opponent ADP noise the
    survival model assumes (match the simulator's).

    ``hype`` is the Phase-16.12 opt-in drift map (``player_key -> picks earlier``); leaving it
    ``None`` — the default — keeps every number this model produces identical to the frozen,
    lockbox-evaluated stack."""
    vi = value_index.dropna(subset=["base_value"]).drop_duplicates("player_key").copy()
    for c in ("sd", "team", "role_rank"):        # tolerate pre-Phase-8 value indexes
        if c not in vi.columns:
            vi[c] = np.nan
    valued = board.dropna(subset=["base_value"])
    x = valued["base_value"].to_numpy(float)
    y = valued["value"].to_numpy(float)
    order = np.argsort(x)
    x, y = x[order], y[order]
    x, idx = np.unique(x, return_index=True)        # np.interp needs strictly ascending x
    y = y[idx]
    return RiskModel(
        lam=float(lam), corr=corr,
        bv=dict(zip(vi["player_key"], vi["base_value"].astype(float), strict=False)),
        sd=dict(zip(vi["player_key"], vi["sd"].astype(float), strict=False)),
        team=dict(zip(vi["player_key"], vi["team"], strict=False)),
        pos=dict(zip(vi["player_key"], vi["pos"], strict=False)),
        role={k: int(r) for k, r in zip(vi["player_key"], vi["role_rank"], strict=False)
              if pd.notna(r)},
        rank_x=x, rank_y=y, scarcity_w=float(scarcity_w), noise=float(noise),
        hype=dict(hype or {}), bench_weight=float(bench_weight), slots=slots,
    )


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


def _greedy_eff(state: DraftState, config: DraftConfig, risk: RiskModel | None,
                ) -> tuple[pd.DataFrame, np.ndarray]:
    """The constrained greedy's **effective priority** per legal pool row (lower = draft sooner),
    with never-excludes, the covariance/scarcity re-rank, ADP fallback and soft tilts applied.

    Shared by the myopic :func:`personalized_pick_fn` (take the argmin) and the 9.5 prefilter (take
    the top-K) so both see one identical, consistent ordering. Must-draft urgency is handled by the
    caller via :func:`_must_now` before this runs."""
    seat = state.your_team
    pool = state.draftable_pool(seat)
    if config.never_draft:                                       # hard exclude
        pool = pool[~pool["player_key"].isin(config.never_draft)]
        if pool.empty:                                           # never leave a slot unfilled
            av = state.available_board()
            av = av[~av["player_key"].isin(config.never_draft)]
            pool = av if not av.empty else state.available_board()

    rnd = state.round()
    counts = state.roster_counts(seat)                           # for state-aware archetypes
    smart = risk is not None and (risk.lam > 0 or risk.scarcity_w > 0)
    if smart:                                   # marginal-portfolio-CE + scarcity/lookahead re-rank
        last = state.n_teams * state.rounds
        nxt = _next_own_pick(state.overall_pick, seat, state.n_teams, last)
        window_end = None if nxt is None else nxt - 1            # opp picks before my next turn
        base = risk.effective_rank(pool, state.your_roster(), window_end)
    else:
        base = pool["value"].to_numpy(float)
    base = np.where(np.isnan(base), pool["adp"].to_numpy(float), base)   # ADP fallback
    overall = state.overall_pick                            # for the adaptive archetype's slide
    tilt = np.fromiter(
        (config.total_tilt_rounds(pk, pos, rnd, counts.get(pos, 0), adp=a, overall_pick=overall)
         for pk, pos, a in zip(pool["player_key"], pool["pos"],
                               pool["adp"].to_numpy(float), strict=False)),
        dtype=float, count=len(pool),
    )
    return pool, base - state.n_teams * tilt                     # + tilt rounds → sooner


def personalized_pick_fn(config: DraftConfig, noise: float = DEFAULT_NOISE,
                         risk: RiskModel | None = None):
    """Build the ``your_pick_fn`` the simulator drives your seat with, from a resolved config.

    With a :class:`RiskModel` (λ>0 or ``scarcity_w>0``) each candidate's priority is re-ranked per
    pick by its covariance-adjusted marginal value and its 9.1/9.4 scarcity urgency against your
    current roster; without one the static value rank is used unchanged (the pre-Phase-8 path)."""
    margin = max(noise, 1.0)

    def pick_fn(state: DraftState) -> int:
        forced = _must_now(state, config, margin)                # secure must-draft in time
        if forced is not None and forced in state.available:
            return forced
        pool, eff = _greedy_eff(state, config, risk)
        return int(pool.index[int(np.argmin(eff))])

    return pick_fn


# ------------------------------------------------------------------------------------------------
# 9.5 — the win-probability draft objective (opt-in; makes DraftConfig.objective real, T8a)
# ------------------------------------------------------------------------------------------------
def winprob_pick_fn(config: DraftConfig, weekly_model, fmt, risk: RiskModel | None = None,
                    noise: float = DEFAULT_NOISE, k: int = 6, sims: int = 200, base_seed: int = 0):
    """The objective-aware pick policy: portfolio-CE/scarcity **prefilter → top-``k``**, then for
    each candidate finish the draft greedily (you) vs ADP+noise (opponents) and score the resulting
    league with a Phase-10 **mini-sim**; take the candidate that maximizes the config's objective
    probability for your seat.

    ``objective`` routes the metric — ``make_playoffs`` → ``playoff_prob``, ``championship_or_bust``
    → ``title_prob`` (rewarding ceiling/variance → a genuinely different board, the point of 9.5).
    A mini-sim per candidate is expensive, so this is opt-in and budgeted by ``k``; portfolio CE
    stays the fast default. Common random numbers across candidates (one seed per pick for the
    schedule, draw columns and opponent completion) make the comparison pure roster signal, not sim
    noise. Consumes the Phase-10 probabilities the calibration gate certified (T8a)."""
    from fantasy_quant.simulation.season import league_probabilities

    margin = max(noise, 1.0)
    want_title = config.objective == "championship_or_bust"
    base_pick = personalized_pick_fn(config, noise, risk)        # the fast draft-completion policy

    def pick_fn(state: DraftState) -> int:
        forced = _must_now(state, config, margin)
        if forced is not None and forced in state.available:
            return forced
        pool, eff = _greedy_eff(state, config, risk)
        cand = [int(pool.index[i]) for i in np.argsort(eff)[:max(1, k)]]
        if len(cand) == 1:
            return cand[0]

        pick_seed = base_seed + state.overall_pick
        best_idx, best_score = cand[0], -1.0
        for c in cand:                                       # CRN: same seeds for every candidate
            roll = state.clone(np.random.default_rng(pick_seed))
            _apply_pick(roll, roll.your_team, c)             # take c, then finish the draft fast
            run_to_completion(roll, base_pick)
            rosters = [roll.roster(t) for t in range(roll.n_teams)]
            pp, tp = league_probabilities(rosters, weekly_model, fmt, roll.slots,
                                          np.random.default_rng(pick_seed + 1), sims=sims)
            score = float(tp[roll.your_team] if want_title else pp[roll.your_team])
            if score > best_score:
                best_idx, best_score = c, score
        return best_idx

    return pick_fn


# ------------------------------------------------------------------------------------------------
# the driver
# ------------------------------------------------------------------------------------------------
def optimize_draft(con, season: int, config: DraftConfig, value_index: pd.DataFrame | None = None,
                   noise: float = DEFAULT_NOISE, seed: int = 0,
                   corr: CorrelationModel | None = None, winprob: bool = False,
                   winprob_k: int = 6, winprob_sims: int = 200) -> DraftState:
    """Draft a personalized roster for ``season`` from ``config``'s seat, PIT.

    Pass a shared ``value_index`` (from :func:`assemble_value`) to draft several configs against the
    same value signal — the cost report reuses one index across the personalized team, benchmark,
    and every leave-one-out redraft, so only the config differs. ``corr`` (the Phase-8 correlation
    model) is built PIT — and memoized — when not supplied; the greedy is covariance-aware whenever
    ``config.risk_lambda > 0`` and scarcity/lookahead-aware via the value index's ``sd``/``adp``.

    ``winprob=True`` (9.5, opt-in) swaps the myopic portfolio-CE greedy for the objective-aware
    win-probability policy: it builds the season's :class:`WeeklyModel` on the **same seed** (shared
    draws, T6) and routes ``config.objective`` via a Phase-10 mini-sim (``winprob_k`` candidates,
    ``winprob_sims`` worlds per pick). Fast portfolio CE stays the default.
    """
    lg = config.league
    as_of = draft_date(con, season)
    if as_of is None:
        raise ValueError(f"no PIT ADP board for {season} — can't plan around availability")
    board = preseason_board(con, season, as_of)
    if value_index is None:
        value_index = assemble_value(con, season, config, as_of, seed=seed)
    if corr is None:
        corr = assemble_correlation(con, season, lg.ruleset)
    board = attach_value(board, value_index)
    risk = build_risk_model(board, value_index, corr, config.risk_lambda, noise=noise)

    if winprob:
        from fantasy_quant.simulation.season import LeagueFormat
        from fantasy_quant.simulation.weekly import build_weekly_model
        if lg.n_teams % 2:
            raise NotImplementedError("win-prob objective needs an even league size (round-robin)")
        wm = build_weekly_model(con, season, lg.ruleset, seed=seed)
        fmt = LeagueFormat(n_teams=lg.n_teams)
        pick_fn = winprob_pick_fn(config, wm, fmt, risk, noise=noise, k=winprob_k,
                                  sims=winprob_sims, base_seed=seed)
    else:
        pick_fn = personalized_pick_fn(config, noise, risk)

    return simulate_draft(board, your_pick_fn=pick_fn, n_teams=lg.n_teams, rounds=lg.rounds,
                          slots=lg.slots, your_team=lg.your_team, noise=noise, seed=seed)
