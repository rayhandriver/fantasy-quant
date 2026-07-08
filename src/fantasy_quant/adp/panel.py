"""Phase 6.1 — the ADP-alpha panel (where the market is soft).

The reframe (2026-07-04) repurposes ADP-bias mining: not "beat the draft market" but *find where
ADP is systematically soft, so we know how cheaply a personalization preference can be indulged.* A
player's **ADP-alpha** is how much their realized value beat (or missed) what their draft slot
implied — the fantasy analog of a factor return. Mining which **observable, point-in-time traits**
predict a positive alpha tells us which kinds of players the crowd under-drafts (cheap/free to
prefer) versus over-drafts (costly to chase).

**Target (chosen 2026-07-07): value-over-replacement alpha.** ``alpha = realized_vor −
adp_implied_vor``, where realized VOR is a player's realized season points minus their position's
replacement level (Phase-1.4 units, so it is position-fair and shares the cost report's scale), and
the ADP-implied baseline is a **leave-one-season-out isotonic fit** of realized VOR on ADP
positional rank (monotone, low-parameter, and — crucially — never fit on the season it scores, so no
outcome leaks into a player's own baseline).

**Features are all PIT at draft time** (CLAUDE.md §3): position, experience / rookie status, ADP
tier, ADP **dispersion** (the crowd's own disagreement — FFC ``stdev``), and prior-season durability
and productivity. Runs on all of ``DEV_SEASONS``; the 2023/24 lockbox is never read.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

from fantasy_quant.backtest.metrics import replacement_ranks
from fantasy_quant.backtest.scoring import RuleSet, season_points
from fantasy_quant.backtest.walkforward import draft_date
from fantasy_quant.config import DEV_SEASONS
from fantasy_quant.data.sources.adp import adp_asof
from fantasy_quant.draft.simulator import RosterSlots

OFFENSE = ("QB", "RB", "WR", "TE")
_CANON = {"QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE", "FB": "RB", "HB": "RB"}

# The trait hypotheses the Phase-6.2 regression tests (all knowable on draft day). Continuous ones
# are z-scored in the regression; ``rookie`` and the position dummies stay 0/1.
FEATURES: tuple[str, ...] = ("rookie", "experience", "adp_stdev", "prior_games", "prior_ppg")


# ------------------------------------------------------------------------------------------------
# per-season ingredients
# ------------------------------------------------------------------------------------------------
def _canon_pos(s: pd.Series) -> pd.Series:
    return s.astype(str).str.upper().map(_CANON)


def _offense_season_points(con, season: int, ruleset: RuleSet | None) -> pd.DataFrame:
    """Realized season fantasy points per offensive player (canonical position, games played)."""
    sp = season_points(con, season, ruleset)
    sp = sp.assign(pos=_canon_pos(sp["position"])).dropna(subset=["pos", "gsis_id"])
    return sp.groupby(["gsis_id", "pos"], as_index=False).agg(points=("points", "sum"),
                                                              games=("weeks", "max"))


def _replacement_levels(points: pd.DataFrame, slots: RosterSlots, n_teams: int) -> dict[str, float]:
    """Offense replacement level per position = realized season points at the replacement rank
    (QB10/RB24/WR24/TE12 in the baseline league). Computed straight from realized points — no K/DST
    play-by-play scoring needed (keeps the panel build fast)."""
    ranks = replacement_ranks(slots, n_teams)
    out = {}
    for pos in OFFENSE:
        vals = np.sort(points.loc[points["pos"] == pos, "points"].to_numpy(float))[::-1]
        rank = ranks[pos]
        out[pos] = float(vals[min(rank - 1, len(vals) - 1)]) if len(vals) else 0.0
    return out


def _prior_features(con, season: int, ruleset: RuleSet | None) -> pd.DataFrame:
    """Prior-season durability + productivity per player (PIT: fully known before the draft)."""
    prev = _offense_season_points(con, season - 1, ruleset)
    if prev.empty:
        return pd.DataFrame(columns=["gsis_id", "prior_games", "prior_ppg"])
    prev = prev.assign(prior_ppg=prev["points"] / prev["games"].clip(lower=1))
    return prev.rename(columns={"games": "prior_games"})[["gsis_id", "prior_games", "prior_ppg"]]


def _season_rows(con, season: int, ids: pd.DataFrame, slots: RosterSlots, n_teams: int,
                 max_adp: float, ruleset: RuleSet | None) -> pd.DataFrame:
    """One season's raw panel rows: PIT ADP board × realized VOR × PIT traits (pre-baseline)."""
    as_of = draft_date(con, season)
    if as_of is None:
        return pd.DataFrame()
    board = adp_asof(con, season, as_of)
    board = board.assign(pos=_canon_pos(board["position"]))
    board = board[board["pos"].isin(OFFENSE) & board["gsis_id"].notna()
                  & (pd.to_numeric(board["adp"], errors="coerce") <= max_adp)]
    if board.empty:
        return pd.DataFrame()

    pts = _offense_season_points(con, season, ruleset)
    repl = _replacement_levels(pts, slots, n_teams)
    pts = pts.assign(realized_vor=pts["points"] - pts["pos"].map(repl))

    idy = ids[["gsis_id", "draft_year"]].drop_duplicates("gsis_id")
    df = board.merge(pts[["gsis_id", "points", "realized_vor"]], on="gsis_id", how="left")
    df = df.merge(idy, on="gsis_id", how="left")
    df = df.merge(_prior_features(con, season, ruleset), on="gsis_id", how="left")

    dy = pd.to_numeric(df["draft_year"], errors="coerce")
    exp = (season - dy)
    out = pd.DataFrame({
        "season": season,
        "gsis_id": df["gsis_id"],
        "name": df["name"],
        "pos": df["pos"],
        "adp": pd.to_numeric(df["adp"], errors="coerce"),
        "pos_rank": pd.to_numeric(df["pos_rank"], errors="coerce"),
        "adp_stdev": pd.to_numeric(df.get("stdev"), errors="coerce"),
        # realized value-over-replacement; a drafted player who never recorded a stat scored 0
        # points (survivorship guard) → VOR = −replacement, the honest bust outcome, not a drop.
        "realized_vor": df["realized_vor"].fillna(-df["pos"].map(repl)),
        "rookie": (exp == 0).fillna(False).astype(int),
        "experience": exp,
        "prior_games": df["prior_games"],
        "prior_ppg": df["prior_ppg"],
    })
    # rookies / first-year-in-data players have no prior line: zero it (rookie flag carries it).
    out["prior_games"] = out["prior_games"].fillna(0.0)
    out["prior_ppg"] = out["prior_ppg"].fillna(0.0)
    out["experience"] = out["experience"].fillna(out["experience"].median()).clip(lower=0)
    return out


# ------------------------------------------------------------------------------------------------
# the leave-one-season-out ADP-implied baseline → alpha
# ------------------------------------------------------------------------------------------------
def _loso_isotonic_baseline(panel: pd.DataFrame) -> pd.Series:
    """ADP-implied VOR for each row = a monotone (non-increasing in ``pos_rank``) isotonic fit of
    realized VOR, trained **within position on every season but the row's own** (leave-one-season-
    out, so no outcome leaks into its baseline). Thin position-seasons fall back to the LOO mean."""
    implied = pd.Series(np.nan, index=panel.index)
    for _pos, g in panel.groupby("pos"):
        for s in g["season"].unique():
            train = g[g["season"] != s]
            test = g[g["season"] == s]
            if len(train) >= 8:
                iso = IsotonicRegression(increasing=False, out_of_bounds="clip")
                iso.fit(train["pos_rank"].to_numpy(float), train["realized_vor"].to_numpy(float))
                pred = iso.predict(test["pos_rank"].to_numpy(float))
            else:
                pred = np.full(len(test), train["realized_vor"].mean() if len(train) else 0.0)
            implied.loc[test.index] = pred
    return implied


def build_alpha_panel(con, seasons: Iterable[int] = DEV_SEASONS, max_adp: float = 180.0,
                      slots: RosterSlots | None = None, n_teams: int = 10,
                      ruleset: RuleSet | None = None) -> pd.DataFrame:
    """Build the ADP-alpha panel over ``seasons`` (see the module docstring).

    Returns one row per drafted (season, offensive player) with the ADP-alpha target and all PIT
    trait features. ``alpha`` = realized VOR − leave-one-season-out ADP-implied VOR; positive = the
    player beat their draft slot (the crowd under-drafted his kind).
    """
    slots = slots or RosterSlots()
    ids = con.execute("SELECT gsis_id, draft_year FROM player_ids WHERE gsis_id IS NOT NULL").df()
    frames = [_season_rows(con, int(s), ids, slots, n_teams, max_adp, ruleset) for s in seasons]
    panel = pd.concat([f for f in frames if not f.empty], ignore_index=True)
    panel = panel.dropna(subset=["pos_rank", "realized_vor"]).reset_index(drop=True)
    panel["adp_stdev"] = panel["adp_stdev"].fillna(panel["adp_stdev"].median())

    panel["adp_implied_vor"] = _loso_isotonic_baseline(panel)
    panel["alpha"] = panel["realized_vor"] - panel["adp_implied_vor"]
    return panel
