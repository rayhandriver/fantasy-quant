"""Personalization spine · step 3 — the cost-of-personalization report (the deliverable).

The direct-indexing payoff (PERSONALIZATION §1): not "we beat ADP" but "here is *exactly what your
preferences cost*, versus the value-optimal team from your seat." We draft the personalized
roster and its unconstrained benchmark through the **same** optimizer, over the **same** seeds (same
opponents, same value signal), and difference their total risk-adjusted value. Then, by
**leave-one-out**, we attribute the gap to each individual preference — the reach-budget advice
the app promises ("waiting a round on your guy is nearly free; refusing a WR can be costly").

§7 discipline: lead with **relative / directional** numbers ("this choice vs that"), stay humble on
absolute title-equity — this is a projected draft-day value gap, not a realized-season claim. The
walk-forward realized-PAR validation (spine step 4) is that layer: it found the projected cost is a
draft-day decision aid, not a season forecast.

**Phase 8 (2026-07-09):** values are now the **portfolio CE** — Σ base_value minus the λ-priced
same-team covariance cross-terms — matching the covariance-aware greedy's objective, and the report
carries a **risk profile** per roster (portfolio sd vs the independence read, floor/ceiling, named
stacks/hedges).

**Phase 6 wired in (2026-07-09):** under the untouched raw headline, the report adds a
**market-softness credit** — the roster's durability-exposure gap vs the benchmark × the one
FDR-stable ADP bias (prior-year games under-priced, +14.6 VOR/SD) — and a **net effective cost**
line. Credit + net line, never a silently-moved headline; flagged as a historical-bias estimate.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from fantasy_quant.adp.softness import (
    STABLE_BIASES,
    SoftnessSignal,
    prior_trait_map,
    softness_credit,
)
from fantasy_quant.backtest.walkforward import draft_date, preseason_board
from fantasy_quant.covariance.shrinkage import CorrelationModel
from fantasy_quant.draft.config import DraftConfig
from fantasy_quant.draft.optimizer import (
    DEFAULT_NOISE,
    assemble_correlation,
    assemble_value,
    optimize_draft,
    portfolio_value,
)
from fantasy_quant.valuation.roster_risk import RosterRisk, roster_risk


@dataclass
class CostReport:
    """A priced personalization decision. ``cost_points`` is the projected total **portfolio-CE**
    value-over-replacement the preferences gave up vs the benchmark; ``per_constraint`` splits it by
    preference (leave-one-out). All values in the ``base_value`` unit (points over replacement)."""
    season: int
    seat: int
    n_drafts: int
    archetype: str
    risk_lambda: float
    benchmark_value: float
    personalized_value: float
    cost_points: float
    cost_pct: float
    per_constraint: pd.DataFrame            # label · name · cost_points · cost_pct
    secured: pd.DataFrame                   # player_key · name · secured_frac (must-draft outcomes)
    personalized_roster: pd.DataFrame       # round · player_name · pos · adp · base_value
    benchmark_roster: pd.DataFrame
    name_map: dict[str, str] = field(default_factory=dict)
    risk_yours: RosterRisk | None = None    # Phase-8 portfolio read (representative draft)
    risk_bench: RosterRisk | None = None
    softness: pd.DataFrame | None = None    # Phase-6 credit table (label · exposures · credit)
    softness_points: float = 0.0            # total credit (VOR pts; + = raw cost overstates)
    net_cost_points: float = 0.0            # cost_points − softness_points

    def _softness_lines(self) -> list[str]:
        if self.softness is None or self.softness.empty:
            return []
        lines = ["  market-softness credit (Phase 6 — where ADP is systematically soft):"]
        for r in self.softness.itertuples(index=False):
            lines.append(
                f"    {r.label:28s} {r.delta_sd:+5.1f} SD vs benchmark → "
                f"{r.credit_points:+7.1f} pts  [CI {r.credit_lo:+.1f}, {r.credit_hi:+.1f}]")
        lines.append(
            f"  net effective cost   : {self.net_cost_points:8.1f} pts  "
            f"(= {self.cost_points:+.1f} raw − {self.softness_points:+.1f} credit; "
            "historical-bias estimate, not a projection)")
        return lines

    def _risk_lines(self) -> list[str]:
        ry, rb = self.risk_yours, self.risk_bench
        if ry is None or rb is None or ry.n_valued == 0:
            return []
        lines = [
            "  risk profile (portfolio, season pts — representative draft):",
            f"    {'':22s}{'you':>12s}{'benchmark':>12s}",
            f"    {'team total mean':22s}{ry.mean:12.0f}{rb.mean:12.0f}",
            f"    {'sd (portfolio)':22s}{ry.sd:12.0f}{rb.sd:12.0f}",
            f"    {'sd (if independent)':22s}{ry.sd_independent:12.0f}"
            f"{rb.sd_independent:12.0f}",
            f"    {'floor (q10)':22s}{ry.floor:12.0f}{rb.floor:12.0f}",
            f"    {'ceiling (q90)':22s}{ry.ceiling:12.0f}{rb.ceiling:12.0f}",
        ]
        for tag, rr in (("you", ry), ("benchmark", rb)):
            for d in rr.describe_pairs(self.name_map):
                lines.append(f"    {tag}: {d}")
        return lines

    def render(self) -> str:
        """A compact plain-text scorecard for the step script / CLI."""
        pct = f"{self.cost_pct:+.1%}"
        lines = [
            f"Cost of personalization — {self.season}, seat {self.seat + 1}, "
            f"archetype={self.archetype}, λ={self.risk_lambda:g}  ({self.n_drafts} drafts)",
            f"  benchmark team value : {self.benchmark_value:8.1f}  (unconstrained, same seat & λ,"
            " portfolio CE)",
            f"  your team value      : {self.personalized_value:8.1f}",
            f"  personalization cost : {self.cost_points:8.1f} pts  ({pct} of benchmark)",
        ]
        if not self.per_constraint.empty:
            lines.append("  what each preference cost (leave-one-out):")
            for r in self.per_constraint.itertuples(index=False):
                lines.append(f"    {r.name:28s} {r.cost_points:+7.1f} pts  ({r.cost_pct:+.1%})")
        if not self.secured.empty:
            miss = self.secured[self.secured["secured_frac"] < 1.0]
            for r in miss.itertuples(index=False):
                lines.append(f"  ⚠ must-draft {r.name}: secured in only {r.secured_frac:.0%} "
                             f"of drafts (ADP too early to reach within budget)")
        lines += self._softness_lines()
        lines += self._risk_lines()
        return "\n".join(lines)


def _roster_frame(state, value_index: pd.DataFrame) -> pd.DataFrame:
    """Your drafted roster, in pick order, with the value each pick carried — for display."""
    mine = state.pick_log().query("is_you").copy()
    bv = (value_index.dropna(subset=["base_value"]).drop_duplicates("player_key")
          .set_index("player_key")["base_value"])
    mine["base_value"] = mine["player_key"].map(bv)
    return mine[["round", "player_name", "pos", "adp", "base_value"]].reset_index(drop=True)


def _name_map(board_adp: pd.DataFrame) -> dict[str, str]:
    """player_key → display name (gsis where present, else the ADP name is the key itself)."""
    gsis = board_adp["gsis_id"] if "gsis_id" in board_adp.columns else None
    name = board_adp["name"]
    keys = name if gsis is None else gsis.where(gsis.notna(), name)
    return dict(zip(keys, name, strict=False))


def personalization_cost(con, season: int, config: DraftConfig,
                         value_index: pd.DataFrame | None = None, k_drafts: int = 6,
                         noise: float = DEFAULT_NOISE, seed: int = 0,
                         attribute: bool = True,
                         corr: CorrelationModel | None = None,
                         signals: tuple[SoftnessSignal, ...] = STABLE_BIASES) -> CostReport:
    """Price ``config``'s personalization for ``season`` (see module docstring).

    Runs ``k_drafts`` paired drafts (personalized vs benchmark on identical seeds). With
    ``attribute`` it adds a leave-one-out redraft per preference — set it False for a fast headline
    (e.g. a snappy UI) and skip the per-constraint breakdown. Values are the **portfolio CE**
    (Phase 8), so a stack's priced covariance shows up in the cost; ``corr`` is built PIT (and
    memoized) when not supplied. ``signals`` are the Phase-6 stable ADP biases the softness credit
    prices (pass ``()`` to disable the credit lines).
    """
    as_of = draft_date(con, season)
    if as_of is None:
        raise ValueError(f"no PIT ADP board for {season}")
    if value_index is None:
        value_index = assemble_value(con, season, config, as_of)
    if corr is None:
        corr = assemble_correlation(con, season, config.league.ruleset)
    name_map = _name_map(preseason_board(con, season, as_of))
    seeds = [seed + i for i in range(k_drafts)]
    bench = config.benchmark()

    def mean_value(cfg: DraftConfig) -> tuple[float, list]:
        states = [optimize_draft(con, season, cfg, value_index, noise, seed=s, corr=corr)
                  for s in seeds]
        vals = [portfolio_value(s.your_roster(), value_index, corr, cfg.risk_lambda)
                for s in states]
        return float(sum(vals) / len(vals)), states

    pers_value, pers_states = mean_value(config)
    bench_value, bench_states = mean_value(bench)
    cost = bench_value - pers_value

    # per-constraint leave-one-out: removing a preference recovers value = what it cost you.
    rows = []
    if attribute:
        for label in config.constraint_labels():
            v_without, _ = mean_value(config.without_constraint(label))
            pk = config.label_player_key(label)
            name = name_map.get(pk, pk) if pk else label.split(":", 1)[1]   # archetype: the name
            recovered = v_without - pers_value                             # removing it = its cost
            rows.append({"label": label, "name": name, "cost_points": recovered,
                         "cost_pct": recovered / bench_value if bench_value else 0.0})
    per_constraint = (pd.DataFrame(rows, columns=["label", "name", "cost_points", "cost_pct"])
                      .sort_values("cost_points", ascending=False).reset_index(drop=True))

    # must-draft outcomes: fraction of personalized drafts in which each must-player was secured.
    sec_rows = []
    for m in config.must_draft:
        got = sum(m.player_key in set(s.pick_log().query("is_you")["player_key"])
                  for s in pers_states)
        sec_rows.append({"player_key": m.player_key,
                         "name": name_map.get(m.player_key, m.player_key),
                         "secured_frac": got / len(pers_states)})
    secured = pd.DataFrame(sec_rows, columns=["player_key", "name", "secured_frac"])

    # Phase-6 softness credit: the rosters' exposure gap on the stable ADP biases, averaged over
    # the same paired drafts the headline uses (PIT: traits are prior-season facts).
    soft, soft_pts = None, 0.0
    if signals:
        trait_map = prior_trait_map(con, season, config.league.ruleset)
        soft = softness_credit([s.your_roster() for s in pers_states],
                               [s.your_roster() for s in bench_states], trait_map, signals)
        soft_pts = float(soft["credit_points"].sum())

    return CostReport(
        season=season, seat=config.league.your_team, n_drafts=k_drafts,
        archetype=config.archetype, risk_lambda=config.risk_lambda,
        benchmark_value=bench_value, personalized_value=pers_value,
        cost_points=cost, cost_pct=(cost / bench_value if bench_value else 0.0),
        per_constraint=per_constraint, secured=secured,
        personalized_roster=_roster_frame(pers_states[0], value_index),
        benchmark_roster=_roster_frame(bench_states[0], value_index),
        name_map=name_map,
        risk_yours=roster_risk(pers_states[0].your_roster(), value_index, corr),
        risk_bench=roster_risk(bench_states[0].your_roster(), value_index, corr),
        softness=soft, softness_points=soft_pts, net_cost_points=cost - soft_pts,
    )
