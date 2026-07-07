"""Personalization spine · step 3 — the cost-of-personalization report (the deliverable).

The direct-indexing payoff (PERSONALIZATION §1): not "we beat ADP" but "here is *exactly what your
preferences cost*, versus the value-optimal team from your seat." We draft the personalized
roster and its unconstrained benchmark through the **same** optimizer, over the **same** seeds (same
opponents, same value signal), and difference their total risk-adjusted value. Then, by
**leave-one-out**, we attribute the gap to each individual preference — the reach-budget advice
the app promises ("waiting a round on your guy is nearly free; refusing a WR can be costly").

§7 discipline: lead with **relative / directional** numbers ("this choice vs that"), stay humble on
absolute title-equity — this is a projected draft-day value gap, not a realized-season claim. A
walk-forward realized-PAR validation is the natural next layer (future work).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from fantasy_quant.backtest.walkforward import draft_date, preseason_board
from fantasy_quant.draft.config import DraftConfig
from fantasy_quant.draft.optimizer import (
    DEFAULT_NOISE,
    assemble_value,
    optimize_draft,
    team_value,
)


@dataclass
class CostReport:
    """A priced personalization decision. ``cost_points`` is the projected total risk-adjusted
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

    def render(self) -> str:
        """A compact plain-text scorecard for the step script / CLI."""
        pct = f"{self.cost_pct:+.1%}"
        lines = [
            f"Cost of personalization — {self.season}, seat {self.seat + 1}, "
            f"archetype={self.archetype}, λ={self.risk_lambda:g}  ({self.n_drafts} drafts)",
            f"  benchmark team value : {self.benchmark_value:8.1f}  (unconstrained, same seat & λ)",
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
                         attribute: bool = True) -> CostReport:
    """Price ``config``'s personalization for ``season`` (see module docstring).

    Runs ``k_drafts`` paired drafts (personalized vs benchmark on identical seeds). With
    ``attribute`` it adds a leave-one-out redraft per preference — set it False for a fast headline
    (e.g. a snappy UI) and skip the per-constraint breakdown.
    """
    as_of = draft_date(con, season)
    if as_of is None:
        raise ValueError(f"no PIT ADP board for {season}")
    if value_index is None:
        value_index = assemble_value(con, season, config, as_of)
    name_map = _name_map(preseason_board(con, season, as_of))
    seeds = [seed + i for i in range(k_drafts)]
    bench = config.benchmark()

    def mean_value(cfg: DraftConfig) -> tuple[float, list]:
        states = [optimize_draft(con, season, cfg, value_index, noise, seed=s) for s in seeds]
        vals = [team_value(s.your_roster(), value_index) for s in states]
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

    return CostReport(
        season=season, seat=config.league.your_team, n_drafts=k_drafts,
        archetype=config.archetype, risk_lambda=config.risk_lambda,
        benchmark_value=bench_value, personalized_value=pers_value,
        cost_points=cost, cost_pct=(cost / bench_value if bench_value else 0.0),
        per_constraint=per_constraint, secured=secured,
        personalized_roster=_roster_frame(pers_states[0], value_index),
        benchmark_roster=_roster_frame(bench_states[0], value_index),
        name_map=name_map,
    )
