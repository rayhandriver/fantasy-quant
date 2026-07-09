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

from fantasy_quant.backtest.metrics import replacement_ranks
from fantasy_quant.backtest.scoring import RuleSet
from fantasy_quant.backtest.walkforward import draft_date, preseason_board
from fantasy_quant.config import DEV_SEASONS
from fantasy_quant.covariance.estimate import MAX_ROLE_RANK
from fantasy_quant.covariance.shrinkage import CorrelationModel, estimate_correlation_model
from fantasy_quant.draft.config import DraftConfig
from fantasy_quant.draft.simulator import DraftState, RosterSlots, canon_pos, simulate_draft
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


def assemble_value(con, season: int, config: DraftConfig, as_of=None) -> pd.DataFrame:
    """The value index the optimizer drafts against, keyed by ``player_key``.

    ``base_value`` = **risk-adjusted value-over-replacement**: the Phase-5 certainty equivalent
    (mean − λ·Var) minus its own positional replacement level, so cross-position priority is on the
    VBD scale *and* carries the risk dial. Players with no distribution (rare — e.g. a body the
    Phase-5 board misses) fall back to the plain Phase-4 VBD; team defenses carry no projection and
    stay on ADP (``base_value`` NaN → the simulator's ADP fallback). Also carries each player's PIT
    ``team`` + ``role_rank`` (from the ADP board) so the covariance layer can price same-team
    co-movement.
    """
    lg = config.league
    if as_of is None:
        as_of = draft_date(con, season)
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
    cross-terms."""
    bv = (value_index.dropna(subset=["base_value"]).drop_duplicates("player_key")
          .set_index("player_key")["base_value"])
    return float(roster["player_key"].map(bv).fillna(0.0).sum())


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

    def effective_rank(self, pool: pd.DataFrame, roster: pd.DataFrame) -> np.ndarray:
        """Covariance-adjusted priority rank per pool row (NaN where unvalued → ADP fallback):
        rank(base_value − 2λ·σ_j·Σ_{i∈roster, same team} ρ_ij σ_i) through the static curve."""
        mine = [(self.team.get(k), self.pos.get(k), self.role.get(k, 1), self.sd.get(k))
                for k in roster["player_key"]]
        mine = [m for m in mine if m[0] and m[3] and np.isfinite(m[3])]
        my_teams = {t for t, _, _, _ in mine}
        out = np.full(len(pool), np.nan)
        for n, (pk, pos) in enumerate(zip(pool["player_key"], pool["pos"], strict=False)):
            v = self.bv.get(pk)
            if v is None or not np.isfinite(v):
                continue
            pen = 0.0
            tj, sj = self.team.get(pk), self.sd.get(pk)
            if tj in my_teams and sj and np.isfinite(sj):
                rj = self.role.get(pk, 1)
                for ti, pi, ri, si in mine:
                    if ti == tj:
                        pen += 2.0 * self.lam * sj * si * self.corr.rho(pi, ri, pos, rj)
            out[n] = float(np.interp(v - pen, self.rank_x, self.rank_y))
        return out


def build_risk_model(board: pd.DataFrame, value_index: pd.DataFrame, corr: CorrelationModel,
                     lam: float) -> RiskModel:
    """Assemble the :class:`RiskModel` from a value-attached board + the value index. The rank
    curve interpolates the board's own ``base_value → value`` mapping, so a zero penalty reproduces
    the static rank (and λ=0 the covariance-blind draft) exactly."""
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
        rank_x=x, rank_y=y,
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


def personalized_pick_fn(config: DraftConfig, noise: float = DEFAULT_NOISE,
                         risk: RiskModel | None = None):
    """Build the ``your_pick_fn`` the simulator drives your seat with, from a resolved config.

    With a :class:`RiskModel` (and λ>0) each candidate's priority is re-ranked per pick by its
    covariance-adjusted marginal value against your current roster; without one (or at λ=0) the
    static value rank is used unchanged — the pre-Phase-8 behavior."""
    margin = max(noise, 1.0)
    cov_aware = risk is not None and risk.lam > 0

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
        if cov_aware:                                            # marginal-portfolio-CE re-rank
            base = risk.effective_rank(pool, state.your_roster())
        else:
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
                   noise: float = DEFAULT_NOISE, seed: int = 0,
                   corr: CorrelationModel | None = None) -> DraftState:
    """Draft a personalized roster for ``season`` from ``config``'s seat, PIT.

    Pass a shared ``value_index`` (from :func:`assemble_value`) to draft several configs against the
    same value signal — the cost report reuses one index across the personalized team, benchmark,
    and every leave-one-out redraft, so only the config differs. ``corr`` (the Phase-8 correlation
    model) is built PIT — and memoized — when not supplied; the greedy is covariance-aware whenever
    ``config.risk_lambda > 0``.
    """
    lg = config.league
    as_of = draft_date(con, season)
    if as_of is None:
        raise ValueError(f"no PIT ADP board for {season} — can't plan around availability")
    board = preseason_board(con, season, as_of)
    if value_index is None:
        value_index = assemble_value(con, season, config, as_of)
    if corr is None:
        corr = assemble_correlation(con, season, lg.ruleset)
    board = attach_value(board, value_index)
    risk = build_risk_model(board, value_index, corr, config.risk_lambda)
    return simulate_draft(board, your_pick_fn=personalized_pick_fn(config, noise, risk),
                          n_teams=lg.n_teams, rounds=lg.rounds, slots=lg.slots,
                          your_team=lg.your_team, noise=noise, seed=seed)
