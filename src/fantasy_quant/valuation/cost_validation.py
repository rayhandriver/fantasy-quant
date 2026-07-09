"""Personalization spine · step 4 — realized-PAR validation of the cost number.

The cost report (step 3) prices personalization in **projected** ``base_value`` units (risk-adjusted
value-over-replacement from our own board). That is a draft-day *estimate*; its docstring flags the
"walk-forward realized-PAR validation" as the natural next layer. This module is that layer.

For each archetype we draft the personalized roster **and** its unconstrained ``bpa`` benchmark
through the same optimizer, over the **same seeded opponents** (the paired design of
:mod:`~fantasy_quant.backtest.significance`), then score each roster's **realized** optimal-lineup
season points against what actually happened (the Phase-1 harness, survivorship-safe). Because both
rosters share the season's replacement level, their starter-point difference **is** the PAR
difference (the replacement term cancels). We form the per-season realized-cost series, put a
**stationary block-bootstrap 95% CI** on it (§1.5), and cross-check it against the projected cost.

Availability is **not** validated here: a true draft-availability Brier needs real pick-by-pick
draft logs (a live Sleeper/ESPN scrape), which the historical FFC data — season-level ADP
aggregates — does not contain. That is deferred until a real draft-log source lands. Everything runs
on ``DEV_SEASONS`` only; the 2023/2024 lockbox is untouched (CLAUDE.md §4).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from fantasy_quant.backtest.significance import BootstrapCI, block_bootstrap_ci
from fantasy_quant.backtest.walkforward import build_realized, draft_date, roster_season_points
from fantasy_quant.config import DEV_SEASONS
from fantasy_quant.draft.config import ARCHETYPES, DraftConfig, LeagueSetup
from fantasy_quant.draft.optimizer import (
    DEFAULT_NOISE,
    assemble_correlation,
    assemble_value,
    optimize_draft,
    portfolio_value,
)

log = logging.getLogger(__name__)

# The value board leans on the conformal calibration, which needs >= 3 prior training seasons
# (projections/distribution._conformal_adjustment). So a season is only *validatable* once it has
# that much DEV history behind it — 2017 onward. Earlier DEV seasons stay in for training but are
# not scored here (their board would be assembled on < 3 seasons and isn't trustworthy).
_MIN_TRAIN = 3
VALIDATION_SEASONS: tuple[int, ...] = tuple(
    s for s in DEV_SEASONS if sum(t < s for t in DEV_SEASONS) >= _MIN_TRAIN
)


# ------------------------------------------------------------------------------------------------
# the paired realized-vs-projected cost draws (the raw evidence)
# ------------------------------------------------------------------------------------------------
def _seat_config(base: DraftConfig, seat: int) -> DraftConfig:
    """``base`` re-seated at 0-indexed ``seat`` (rotating draft position for a robust estimate)."""
    return replace(base, league=replace(base.league, draft_slot=seat + 1))


def _score(con, season: int, cfg: DraftConfig, vi: pd.DataFrame, realized, slots,
           noise: float, seed: int, corr) -> tuple[float, float]:
    """Draft ``cfg`` for ``season`` and return (realized starter points, projected portfolio CE —
    the Phase-8 objective the covariance-aware greedy climbs)."""
    roster = optimize_draft(con, season, cfg, vi, noise, seed=seed, corr=corr).your_roster()
    return (roster_season_points(roster, realized, slots),
            portfolio_value(roster, vi, corr, cfg.risk_lambda))


def paired_costs(con, subjects: dict[str, DraftConfig], benchmark: DraftConfig,
                 seasons: Iterable[int] = VALIDATION_SEASONS, k_drafts: int = 10,
                 noise: float = DEFAULT_NOISE, seed: int = 0) -> pd.DataFrame:
    """Draft every ``subjects`` config **and** the shared ``benchmark`` on matched seeds across
    ``seasons``; return one row per (subject, season, draft) with the realized and projected cost.

    Efficiency: the value index is assembled **once per season** (it depends only on league + λ,
    which every subject here shares) and the benchmark is drafted **once per (season, seat, seed)**
    and reused for all subjects — so a 5-archetype sweep costs one value build + 6 drafts per seed,
    not 5 independent walk-forwards.
    """
    lg = benchmark.league
    slots, ruleset, n_teams = lg.slots, lg.ruleset, lg.n_teams
    rows: list[dict] = []
    for season in seasons:
        if draft_date(con, season) is None:
            continue
        try:
            vi = assemble_value(con, season, benchmark)
        except Exception as e:  # noqa: BLE001 — a thin-history season can't build a board; skip it
            log.warning("skipping %d: value board would not assemble (%s)", season, e)
            continue
        corr = assemble_correlation(con, season, ruleset)   # PIT, shared by every subject
        realized = build_realized(con, season, ruleset)
        for k in range(k_drafts):
            seat = k % n_teams
            s = seed + int(season) * 1000 + k
            b_pts, b_val = _score(con, season, _seat_config(benchmark, seat), vi, realized,
                                  slots, noise, s, corr)
            for name, cfg in subjects.items():
                p_pts, p_val = _score(con, season, _seat_config(cfg, seat), vi, realized,
                                      slots, noise, s, corr)
                rows.append({
                    "subject": name, "season": int(season), "draft": k, "seat": seat,
                    "bench_points": b_pts, "pers_points": p_pts,
                    "realized_cost": b_pts - p_pts,   # + = preference gave up real points
                    "projected_cost": b_val - p_val,  # + = it gave up projected VOR (base_value)
                })
    return pd.DataFrame(rows)


# ------------------------------------------------------------------------------------------------
# per-subject summary (the honest, replacement-cancelling headline + CI)
# ------------------------------------------------------------------------------------------------
@dataclass
class RealizedValidation:
    """One archetype's cost, validated on realized outcomes. ``realized_cost`` is mean per-season
    benchmark-minus-personalized starter points (= PAR difference); positive means the preference
    cost real points. ``ci`` is the block-bootstrap 95% interval on the per-season series."""
    subject: str
    n_seasons: int
    n_drafts: int
    projected_cost: float          # mean per-season projected cost (base_value units)
    realized_cost: float           # mean per-season realized PAR cost (points)
    ci: BootstrapCI                # 95% CI on the per-season realized-cost series
    bench_points: float            # mean benchmark realized starter points (for scale)
    per_season: pd.DataFrame       # season · realized_cost · projected_cost · bench_points

    @property
    def verdict(self) -> str:
        """Whether the realized cost is distinguishable from zero (a *cost* whose CI covers 0 means
        the preference did **not** measurably cost realized points — good news for indulging it)."""
        if self.ci.lo > 0:
            return "REAL COST (CI > 0)"
        if self.ci.hi < 0:
            return "REAL GAIN (CI < 0)"
        return "not distinguishable from 0"

    def render(self) -> str:
        pct = self.realized_cost / self.bench_points if self.bench_points else 0.0
        return (f"  {self.subject:9s} projected {self.projected_cost:+6.1f} | "
                f"realized {self.realized_cost:+6.1f} pts/season ({pct:+.1%}) "
                f"[95% CI {self.ci.lo:+.1f}, {self.ci.hi:+.1f}]  {self.verdict}")


def summarize(long: pd.DataFrame, subject: str, n_boot: int = 10000, seed: int = 0,
              ci: float = 0.95) -> RealizedValidation:
    """Collapse one ``subject``'s per-draft rows into a per-season series and bootstrap its CI."""
    sub = long[long["subject"] == subject]
    per_season = (sub.groupby("season", as_index=False)
                  .agg(realized_cost=("realized_cost", "mean"),
                       projected_cost=("projected_cost", "mean"),
                       bench_points=("bench_points", "mean")))
    series = per_season["realized_cost"].to_numpy()
    cires = block_bootstrap_ci(series, n_boot=n_boot, ci=ci, seed=seed)
    return RealizedValidation(
        subject=subject, n_seasons=len(per_season), n_drafts=int(len(sub)),
        projected_cost=float(per_season["projected_cost"].mean()),
        realized_cost=float(series.mean()), ci=cires,
        bench_points=float(per_season["bench_points"].mean()), per_season=per_season,
    )


# ------------------------------------------------------------------------------------------------
# does the projected cost actually predict the realized cost?
# ------------------------------------------------------------------------------------------------
@dataclass
class CrossCheck:
    """How well the report's projected cost tracks realized PAR cost across all subject-seasons."""
    spearman: float                # rank correlation projected vs realized (subject-season level)
    p_value: float
    sign_agreement: float          # fraction of subject-seasons where the two costs share a sign
    n: int

    def render(self) -> str:
        return (f"  projected→realized: Spearman ρ={self.spearman:+.2f} (p={self.p_value:.2f}), "
                f"sign agreement {self.sign_agreement:.0%} over {self.n} subject-seasons")


def crosscheck(long: pd.DataFrame) -> CrossCheck:
    """Correlate projected and realized cost at the subject-season level (the report's honesty test:
    a preference the board *projects* as costly should, on average, cost realized points too)."""
    g = (long.groupby(["subject", "season"], as_index=False)
         .agg(realized_cost=("realized_cost", "mean"), projected_cost=("projected_cost", "mean")))
    x, y = g["projected_cost"].to_numpy(), g["realized_cost"].to_numpy()
    rho, p = (spearmanr(x, y) if len(g) >= 3 and np.ptp(x) > 0 else (float("nan"), float("nan")))
    nz = (np.sign(x) != 0) & (np.sign(y) != 0)
    agree = float(np.mean(np.sign(x[nz]) == np.sign(y[nz]))) if nz.any() else float("nan")
    return CrossCheck(spearman=float(rho), p_value=float(p), sign_agreement=agree, n=int(len(g)))


# ------------------------------------------------------------------------------------------------
# the driver — validate the archetype sweep
# ------------------------------------------------------------------------------------------------
@dataclass
class ArchetypeValidation:
    """The full archetype-sweep validation: one :class:`RealizedValidation` per archetype + the
    projected→realized cross-check, all on ``DEV_SEASONS``."""
    per_archetype: list[RealizedValidation]
    cross: CrossCheck
    seasons: tuple[int, ...]
    long: pd.DataFrame

    def render(self) -> str:
        n = self.per_archetype[0].n_drafts if self.per_archetype else 0
        head = (f"Realized-PAR validation of personalization cost — {len(self.seasons)} DEV "
                f"seasons ({self.seasons[0]}–{self.seasons[-1]}), {n} drafts each")
        body = [v.render() for v in self.per_archetype]
        return "\n".join([head, *body, self.cross.render()])


def validate_archetypes(con, archetypes: Iterable[str] | None = None,
                        league: LeagueSetup | None = None, risk_lambda: float | None = None,
                        seasons: Iterable[int] = VALIDATION_SEASONS, k_drafts: int = 10,
                        noise: float = DEFAULT_NOISE, seed: int = 0,
                        n_boot: int = 10000) -> ArchetypeValidation:
    """Validate every non-``bpa`` archetype's cost against realized PAR across ``seasons`` (see the
    module docstring). Returns per-archetype realized cost + CI and the projected/realized
    cross-check.
    """
    league = league or LeagueSetup()
    names = list(archetypes) if archetypes is not None else [a for a in ARCHETYPES if a != "bpa"]
    bench = (DraftConfig(league=league) if risk_lambda is None
             else DraftConfig(league=league, risk_lambda=risk_lambda))
    subjects = {a: replace(bench, archetype=a) for a in names}
    seasons = tuple(int(s) for s in seasons)

    long = paired_costs(con, subjects, bench, seasons=seasons, k_drafts=k_drafts,
                        noise=noise, seed=seed)
    per = [summarize(long, a, n_boot=n_boot, seed=seed) for a in names]
    per.sort(key=lambda v: v.realized_cost, reverse=True)
    return ArchetypeValidation(per_archetype=per, cross=crosscheck(long),
                               seasons=seasons, long=long)
