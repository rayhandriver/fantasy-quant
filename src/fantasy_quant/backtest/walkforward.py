"""Phase 1.3 — the walk-forward harness (the engine that scores a ranking method on history).

*ranking method -> simulated drafts -> realized season outcomes*, across seasons, strictly
point-in-time. Without this you cannot tell if a method is an improvement. For each season it:

  1. finds the **draft date** = that season's FFC ADP snapshot (PIT: the latest info a drafter had);
  2. builds the draftable board via ``adp_asof`` (0.4) and **asserts it is PIT** (nothing dated
     after the draft date — the intern Step 5.1 guard, reused from :func:`assert_panel_pit`);
  3. lets a pluggable ``rank_fn`` produce your draft ranking (baseline = ADP);
  4. simulates ``k_drafts`` drafts from **varied seats** (1.2), opponents drafting by ADP+noise;
  5. scores each resulting roster against that season's **actual** weekly results via **optimal
     weekly lineups** (1.1 scoring), with the **survivorship guard**: a drafted player who never
     recorded a stat contributes 0 (LEFT JOIN to realized), never dropped.

Swapping ``rank_fn`` is a one-argument change — the whole point (mirrors the intern
``cov_builder_fn`` plug). PAR / significance vs the ADP baseline are Phases 1.4 / 1.5; here the
per-roster score is total optimal-starter points.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from fantasy_quant.backtest import scoring
from fantasy_quant.backtest.scoring import RuleSet, dst_team_from_adp_name
from fantasy_quant.data.panel import assert_panel_pit
from fantasy_quant.data.sources.adp import adp_asof
from fantasy_quant.draft.simulator import RosterSlots, simulate_draft, value_pick_fn

OFFENSE = ("QB", "RB", "WR", "TE")
RankFn = Callable[..., pd.Series]


# --------------------------------------------------------------------------------------------
# rank_fn contract + the ADP baseline
# --------------------------------------------------------------------------------------------
def rank_by_adp(board: pd.DataFrame, con=None, season=None, as_of=None) -> pd.Series:
    """Baseline ``rank_fn``: draft by consensus ADP (lower = sooner), aligned to ``board.index``.

    A ``rank_fn`` returns a numeric draft-priority per board row on the **ADP/pick-number scale**
    (lower = draft sooner); NaN falls back to that player's ADP. It receives the board plus PIT
    context (``con``, ``season``, ``as_of``) so a model can pull as-of features itself.
    """
    return pd.to_numeric(board["adp"], errors="coerce")


# --------------------------------------------------------------------------------------------
# optimal weekly lineup (pure, unit-tested)
# --------------------------------------------------------------------------------------------
def optimal_lineup_points(points, positions, slots: RosterSlots) -> float:
    """Max legal starting-lineup total for one week given a roster's ``points``/``positions``.

    Greedy is optimal for **nested** flex eligibility: fill each dedicated slot with its top
    scorers, then each flex group most-restrictive-first with the best remaining eligible players.
    Missing/empty slots contribute 0.

    This is the **reference** implementation — slow, obvious, one row at a time — and
    ``simulation.season.lineup_points_matrix`` is the vectorized one. They are regression-tested
    equal, so both must consume :meth:`RosterSlots.flex_groups` rather than re-deriving the fill
    order (17.1: the ordering rule lives in one place).
    """
    df = pd.DataFrame({"pos": list(positions), "pts": np.asarray(points, dtype=float)})
    used = pd.Series(False, index=df.index)
    total = 0.0
    for pos, n in slots.base_demand().items():
        cand = df[(df["pos"] == pos) & ~used].nlargest(n, "pts")
        total += float(cand["pts"].sum())
        used.loc[cand.index] = True
    for count, eligible in slots.flex_groups():
        cand = df[df["pos"].isin(eligible) & ~used].nlargest(count, "pts")
        total += float(cand["pts"].sum())
        used.loc[cand.index] = True
    return total


# --------------------------------------------------------------------------------------------
# realized weekly points per season (built once; the survivorship-safe scoring source)
# --------------------------------------------------------------------------------------------
@dataclass
class Realized:
    off: pd.DataFrame    # gsis_id x week  (offense)
    kick: pd.DataFrame   # gsis_id x week  (kickers)
    dst: pd.DataFrame    # team    x week  (defenses)
    weeks: list[int]


def _pivot(df: pd.DataFrame, index: str, weeks: list[int]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(index=pd.Index([], name=index), columns=weeks, dtype=float)
    return (df.pivot_table(index=index, columns="week", values="points", aggfunc="sum")
              .reindex(columns=weeks).fillna(0.0))


def build_realized(con, season: int, ruleset: RuleSet | None = None) -> Realized:
    """Materialize the season's realized weekly points for offense (gsis), kickers (gsis) and
    defenses (team). Weeks are the REG weeks that actually occurred."""
    off = scoring.weekly_points(con, season, ruleset)
    kick = scoring.kicker_weekly_points(con, season, ruleset)
    dst = scoring.dst_weekly_points(con, season, ruleset)
    weeks = sorted(int(w) for w in off["week"].unique())
    return Realized(_pivot(off, "gsis_id", weeks), _pivot(kick, "gsis_id", weeks),
                    _pivot(dst, "team", weeks), weeks)


def _player_week_vector(player_key: str, pos: str, realized: Realized) -> np.ndarray:
    """Realized weekly points for one drafted player; **zeros if they never recorded a stat**
    (the survivorship guard — a bust is scored 0, not dropped)."""
    zeros = np.zeros(len(realized.weeks))
    if pos in OFFENSE:
        src, key = realized.off, player_key
    elif pos == "K":
        src, key = realized.kick, player_key
    elif pos == "DST":
        src, key = realized.dst, dst_team_from_adp_name(player_key)
    else:
        return zeros
    return src.loc[key].to_numpy() if key in src.index else zeros


def roster_weekly_points(roster: pd.DataFrame, realized: Realized,
                         slots: RosterSlots) -> np.ndarray:
    """Per-week optimal-starting-lineup points for a drafted roster (survivorship-safe)."""
    if roster.empty:
        return np.zeros(len(realized.weeks))
    positions = roster["pos"].tolist()
    mat = np.vstack([_player_week_vector(r.player_key, r.pos, realized)
                     for r in roster.itertuples(index=False)])
    return np.array([optimal_lineup_points(mat[:, w], positions, slots)
                     for w in range(len(realized.weeks))])


def roster_season_points(roster: pd.DataFrame, realized: Realized, slots: RosterSlots) -> float:
    """Total optimal-starting-lineup points a drafted roster would have scored over the season."""
    return float(roster_weekly_points(roster, realized, slots).sum())


# --------------------------------------------------------------------------------------------
# the harness
# --------------------------------------------------------------------------------------------
@dataclass
class WalkForwardResult:
    per_draft: pd.DataFrame      # season, draft, your_seat, starter_points
    per_season: pd.DataFrame     # season, n_drafts, mean_points, std_points
    pooled: dict                 # mean/std/n over all drafts

    def __repr__(self) -> str:
        p = self.pooled
        return (f"WalkForwardResult(seasons={len(self.per_season)}, "
                f"drafts={int(p['n'])}, pooled_mean={p['mean']:.1f} ± {p['std']:.1f})")


def draft_date(con, season: int, source="ffc", scoring_fmt="ppr", teams=10) -> pd.Timestamp | None:
    """That season's FFC ADP snapshot date — the PIT as-of for the draft."""
    row = con.execute(
        "SELECT MAX(snapshot_date) FROM adp_snapshots "
        "WHERE season=? AND source=? AND scoring=? AND teams=?",
        [int(season), source, scoring_fmt, teams],
    ).fetchone()
    return pd.Timestamp(row[0]) if row and row[0] is not None else None


def preseason_board(con, season: int, as_of) -> pd.DataFrame:
    """The PIT draftable universe (adp_asof) + a harness-level leak assert on the snapshot date."""
    board = adp_asof(con, season, as_of)
    assert_panel_pit(board, as_of, ["snapshot_date"])  # planted future ADP would trip here
    return board


def walk_forward(con, rank_fn: RankFn = rank_by_adp, seasons: Iterable[int] = range(2014, 2025),
                 k_drafts: int = 10, n_teams: int = 10, rounds: int = 15,
                 slots: RosterSlots | None = None, noise: float = 5.0, seed: int = 0,
                 ruleset: RuleSet | None = None) -> WalkForwardResult:
    """Score ``rank_fn`` across ``seasons``: build the PIT board, simulate ``k_drafts`` drafts from
    rotating seats, and total each of your rosters' realized optimal-lineup points."""
    slots = slots or RosterSlots()
    rows = []
    for season in seasons:
        as_of = draft_date(con, season)
        if as_of is None:
            continue
        board = preseason_board(con, season, as_of)
        board = board.assign(value=pd.to_numeric(rank_fn(board, con, season, as_of),
                                                  errors="coerce").to_numpy())
        realized = build_realized(con, season, ruleset)
        for k in range(k_drafts):
            seat = k % n_teams
            result = simulate_draft(board, your_pick_fn=value_pick_fn, n_teams=n_teams,
                                    rounds=rounds, slots=slots, your_team=seat, noise=noise,
                                    seed=seed + int(season) * 1000 + k)
            pts = roster_season_points(result.your_roster(), realized, slots)
            rows.append({"season": int(season), "draft": k, "your_seat": seat,
                         "starter_points": pts})

    per_draft = pd.DataFrame(rows)
    per_season = (per_draft.groupby("season", as_index=False)
                  .agg(n_drafts=("draft", "count"), mean_points=("starter_points", "mean"),
                       std_points=("starter_points", "std")))
    pooled = {"mean": float(per_draft["starter_points"].mean()),
              "std": float(per_draft["starter_points"].std()),
              "n": int(len(per_draft))}
    return WalkForwardResult(per_draft, per_season, pooled)
