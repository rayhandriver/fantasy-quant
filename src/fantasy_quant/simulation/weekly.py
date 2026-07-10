"""Phase 10 — weekly-grain distributions (the Phase-5 deferral, folded in as planned).

Phase 5 calibrated **season totals**; the season sim needs **weeks**. We go top-down (user
decision 2026-07-09) so everything already validated survives by construction:

1. **Season draws** come from the Phase-5 sampler itself (``assemble_distribution`` with
   ``return_games=True`` so each draw keeps its own games-played ``G``), then the whole board is
   correlated **once** with the Phase-8 relationship-typed Σ via an Iman–Conover *permutation*
   (:func:`correlation_permutation`) — the same reordering as ``roster_risk.correlate_samples``,
   exposed as indices so ``G`` rides along with its own draw.
2. **Weeks** split each season draw across the player's active weeks: his ``G`` missed games are
   placed uniformly at random (documented approximation), his team's real NFL **bye** (from
   ``game_lines``, PIT — the schedule is public before draft day) is a forced zero, and the
   active-week shares are **Dirichlet** with concentration ``α = 1/CoV²`` from his own 5.3
   weekly volatility — so a boom/bust player's weeks fan out and a grinder's stay flat, while
   every player-week vector **sums exactly to its season draw** (no re-calibration needed).

Players outside the Phase-5 universe score deterministic weekly constants: rostered K/DST get
the prior season's top-``n_teams`` weekly average at their position; an offense player without a
cloud (rare — deep sleepers) gets his position's prior-season replacement level per week. Both
are PIT (strictly prior season) and documented.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from fantasy_quant.backtest import metrics, scoring
from fantasy_quant.backtest.scoring import RuleSet
from fantasy_quant.covariance.estimate import nearest_psd, player_covariance
from fantasy_quant.projections import variance
from fantasy_quant.projections.distribution import cached_distribution

OFFENSE = ("QB", "RB", "WR", "TE")
COV_CLIP = (0.2, 2.5)          # weekly CoV clipped to a physical band before α = 1/CoV²
DEFAULT_COV = 0.9              # fallback weekly CoV when a player has no prior weeks at all


# ------------------------------------------------------------------------------------------------
# Iman–Conover as a permutation (so companion arrays ride along with their draws)
# ------------------------------------------------------------------------------------------------
def correlation_permutation(samples: np.ndarray, corr: np.ndarray,
                            rng: np.random.Generator) -> np.ndarray:
    """The Iman–Conover reordering of ``roster_risk.correlate_samples`` as an index array.

    Returns ``idx`` with shape ``(k, n)`` such that ``np.take_along_axis(samples, idx, 1)``
    equals ``correlate_samples(samples, corr, rng)`` for the same rng state (regression-tested).
    Exposing the indices lets the games-played companion be permuted identically, keeping each
    season draw paired with its own ``G``.
    """
    samples = np.asarray(samples, float)
    k, n = samples.shape
    c = nearest_psd(np.asarray(corr, float))
    chol = np.linalg.cholesky(c + 1e-10 * np.eye(k))
    scores = chol @ rng.standard_normal((k, n))
    idx = np.empty((k, n), dtype=np.int64)
    for i in range(k):
        ranks = np.argsort(np.argsort(scores[i]))
        idx[i] = np.argsort(samples[i])[ranks]
    return idx


# ------------------------------------------------------------------------------------------------
# the week splitter (pure — the unit-test target)
# ------------------------------------------------------------------------------------------------
def split_weeks(y: np.ndarray, g: np.ndarray, wk_cov: float, eligible: np.ndarray,
                n_weeks: int, rng: np.random.Generator) -> np.ndarray:
    """Disaggregate season draws into weekly points, ``(n_sims, n_weeks)``.

    For each draw: place ``min(g, len(eligible))`` active weeks uniformly at random within
    ``eligible`` (0-based week indices — byes already excluded), split ``y`` across them with
    Dirichlet(α = 1/wk_cov²) shares. Row sums equal ``y`` exactly whenever at least one week is
    active; ``g = 0`` draws (lost season) are all-zero rows.
    """
    y = np.asarray(y, float)
    g = np.asarray(g)
    eligible = np.asarray(eligible, int)
    n_sims, m = len(y), len(eligible)
    out = np.zeros((n_sims, n_weeks))
    if m == 0:
        return out
    counts = np.clip(g, 0, m).astype(int)

    # uniformly-random active subset per sim: the `counts` lowest of m uniform keys
    order_rank = np.argsort(np.argsort(rng.random((n_sims, m)), axis=1), axis=1)
    active = order_rank < counts[:, None]

    cov = float(np.clip(wk_cov if np.isfinite(wk_cov) else DEFAULT_COV, *COV_CLIP))
    shares = rng.gamma(1.0 / cov**2, 1.0, (n_sims, m)) * active
    tot = shares.sum(axis=1, keepdims=True)
    np.divide(shares, tot, out=shares, where=tot > 0)
    out[:, eligible] = shares * y[:, None]
    return out


# ------------------------------------------------------------------------------------------------
# supporting PIT lookups (real byes; prior-season constants for K/DST and cloudless players)
# ------------------------------------------------------------------------------------------------
def team_bye_weeks(con, season: int, max_week: int) -> dict[str, int]:
    """Each team's bye week within ``1..max_week`` from the real NFL schedule (``game_lines``,
    public before draft day — PIT). Teams with no bye in range are absent."""
    gl = con.execute(
        "SELECT week, home_team, away_team FROM game_lines "
        "WHERE season = ? AND game_type = 'REG' AND week <= ?", [int(season), int(max_week)]
    ).df()
    byes: dict[str, int] = {}
    teams = pd.unique(pd.concat([gl["home_team"], gl["away_team"]]))
    played = {t: set(gl.loc[(gl["home_team"] == t) | (gl["away_team"] == t), "week"])
              for t in teams}
    for t, wks in played.items():
        missing = sorted(set(range(1, max_week + 1)) - wks)
        if missing:
            byes[str(t)] = int(missing[0])
    return byes


def kdst_weekly_baseline(con, prior_season: int, ruleset: RuleSet | None = None,
                         n_teams: int = 10) -> dict[str, float]:
    """Deterministic weekly points for rostered K/DST: the prior season's top-``n_teams``
    (a startable unit) average weekly score at the position."""
    out = {}
    for pos, fn, key in (("K", scoring.kicker_weekly_points, "gsis_id"),
                         ("DST", scoring.dst_weekly_points, "team")):
        wk = fn(con, prior_season, ruleset)
        totals = wk.groupby(key)["points"].sum().nlargest(n_teams)
        n_weeks = wk["week"].nunique()
        out[pos] = float(totals.mean() / max(n_weeks, 1)) if len(totals) else 0.0
    return out


def replacement_weekly(con, prior_season: int, ruleset: RuleSet | None = None,
                       n_teams: int = 10) -> dict[str, float]:
    """Per-position weekly points for offense players with no Phase-5 cloud: the prior season's
    replacement level (1.4) divided by its weeks — the honest floor for a deep sleeper."""
    repl = metrics.replacement_levels(con, prior_season, n_teams=n_teams, ruleset=ruleset)
    n_weeks = max(len(scoring.weekly_points(con, prior_season, ruleset)["week"].unique()), 1)
    return {pos: float(repl.level(pos)) / n_weeks for pos in OFFENSE}


# ------------------------------------------------------------------------------------------------
# the assembled weekly model (one per season; every league in that season reuses it)
# ------------------------------------------------------------------------------------------------
@dataclass
class WeeklyModel:
    """Correlated season draws + everything needed to expand any player to weekly points."""
    summary: pd.DataFrame            # player_key · pos · team · role_rank · mean · sd · wk_cov
    samples: np.ndarray              # (k, n_draws) Σ-correlated season totals
    games: np.ndarray                # (k, n_draws) games played, paired with samples
    byes: dict[str, int]             # team -> bye week (1-based)
    kdst: dict[str, float]           # constant weekly points for K / DST
    repl_weekly: dict[str, float]    # constant weekly points for cloudless offense players
    n_weeks: int                     # fantasy weeks simulated (1..n_weeks)
    index: dict[str, int] = field(init=False)

    def __post_init__(self) -> None:
        self.index = {k: i for i, k in enumerate(self.summary["player_key"])}

    @property
    def n_draws(self) -> int:
        return self.samples.shape[1]

    def player_weekly(self, player_key: str, pos: str, sim_cols: np.ndarray,
                      rng: np.random.Generator) -> np.ndarray:
        """Weekly points for one player over the selected sim draws, ``(n_sims, n_weeks)``."""
        n_sims = len(sim_cols)
        if pos in ("K", "DST"):
            return np.full((n_sims, self.n_weeks), self.kdst.get(pos, 0.0))
        row = self.index.get(player_key)
        if row is None:
            return np.full((n_sims, self.n_weeks), self.repl_weekly.get(pos, 0.0))
        team = self.summary["team"].iloc[row]
        bye = self.byes.get(str(team)) if pd.notna(team) else None
        eligible = np.array([w for w in range(self.n_weeks) if (w + 1) != bye], int)
        return split_weeks(self.samples[row, sim_cols], self.games[row, sim_cols],
                           float(self.summary["wk_cov"].iloc[row]), eligible,
                           self.n_weeks, rng)


def build_weekly_model(con, season: int, ruleset: RuleSet | None = None,
                       n_draws: int = 2000, n_weeks: int = 17, seed: int = 0) -> WeeklyModel:
    """Assemble the season's :class:`WeeklyModel` (PIT: everything trains strictly < season).

    Correlation is imposed board-wide exactly once — every league simulated in this season
    indexes the same joint draws (a column = one joint world).
    """
    # local imports: draft.optimizer imports valuation which is a sibling — avoid module cycles.
    from fantasy_quant.backtest.walkforward import draft_date
    from fantasy_quant.data.sources.adp import adp_asof
    from fantasy_quant.draft.optimizer import _board_teams, assemble_correlation

    ruleset = ruleset or RuleSet()
    # T6: the *same* shared draw cloud the draft optimizer scores value against (keyed on seed), so
    # the value the greedy drafts and the value the sim scores can never silently diverge.
    summary, samples, games = cached_distribution(con, season, ruleset, n_draws=n_draws, seed=seed)
    summary = summary.copy()

    as_of = draft_date(con, season)
    board = adp_asof(con, season, as_of)
    summary = summary.merge(_board_teams(board), on="player_key", how="left")
    summary["role_rank"] = summary["role_rank"].fillna(1).astype(int)

    vol = variance.weekly_volatility(con, [season - 1], ruleset)
    summary = summary.merge(vol[["player_key", "wk_cov"]], on="player_key", how="left")
    pos_med = summary.groupby("pos")["wk_cov"].transform("median")
    summary["wk_cov"] = summary["wk_cov"].fillna(pos_med).fillna(DEFAULT_COV)

    corr = assemble_correlation(con, season, ruleset)
    r = player_covariance(np.ones(len(summary)), summary["team"].fillna("?"),
                          summary["pos"], summary["role_rank"], corr.rho)
    rng = np.random.default_rng(seed + 1)
    idx = correlation_permutation(samples, r, rng)
    samples = np.take_along_axis(samples, idx, axis=1)
    games = np.take_along_axis(games, idx, axis=1)

    return WeeklyModel(
        summary=summary, samples=samples, games=games,
        byes=team_bye_weeks(con, season, n_weeks),
        kdst=kdst_weekly_baseline(con, season - 1, ruleset),
        repl_weekly=replacement_weekly(con, season - 1, ruleset),
        n_weeks=n_weeks,
    )
