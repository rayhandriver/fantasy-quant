"""Phase 16.7 — the draft-slot **drift** panel (the availability twin of the 16.1 alpha panel).

16.1–16.5 asked whether a changed situation makes a player **out-earn** his ADP. This asks the
sibling question: does it make him get **drafted earlier** than his ADP? That is the *availability*
signal, and it targets a concrete UX failure — a player falls to you across ten mock drafts, then
gets sniped two rounds early in the real one because every drafter in the room read the same take.

**Sign convention:** ``drift > 0`` means **drafted EARLIER than ADP** (a reach — the hype
direction). This follows the repo's existing ``reach`` convention in
``data/sources/sleeper.py::build_tendencies`` (``reach = board ADP − pick_no``). Note this is the
**negative** of the ``actual_slot − ADP`` written in ``docs/BUILD_PLAN.md`` §16.7; the flip is
deliberate, so that "positive = hyped = goes early" reads the same way through 16.8–16.12.

**Units: rounds, not picks.** A pick number means different things in an 8- and a 16-team league,
and the FFC board only publishes 10- and 12-team ADP. Both sides are therefore divided by their own
team count — ``slot_rounds = pick_no / teams``, ``adp_rounds = adp / board_teams`` — so everything
is "how many rounds deep", comparable across league sizes. This is what lets the panel use the
whole human corpus rather than only exact 10/12-team drafts (+7 drafts, ~20 % more picks).

**★ Three corpus facts that shape the design, all measured 2026-07-25 rather than assumed:**

1. **The Sleeper corpus is not a preseason corpus.** Draft start times run from *February* to
   *November*. A February dynasty-startup or a November in-season draft compared against a
   September ADP board does not measure narrative drift, it measures a different market. Hence
   :data:`PRESEASON_WINDOW` — and it is the single biggest filter, cutting 117 human drafts to 38.
2. **The FFC board post-dates most drafts** (board ~Sep 1–4; median draft late August). The board
   is the *definition of the yardstick*, so this is not a predictive look-ahead — but the gap does
   inject real market movement into the measurement, so every row carries ``days_to_board`` and
   16.8 controls on it. See :func:`season_board` for why the strict ``adp_asof`` guard is
   deliberately not used here.
3. **``sleeper_human`` ADP is built from these very drafts** (``build_mock_adp`` averages their
   pick numbers), so using it as a feature against this target is self-prediction. 16.8's
   ``source_divergence`` therefore comes from :func:`heldout_sleeper_board` — a leave-one-draft-out
   board — and 16.8 additionally reports the ablation without it.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable

import numpy as np
import pandas as pd

from fantasy_quant.adp.panel import OFFENSE, _canon_pos

#: Drafts outside this (month, day) window of their own season are excluded — see fact (1) above.
#: Aug 1 → Sep 15 spans training camp through kickoff, which is when redraft leagues actually draft.
PRESEASON_WINDOW: tuple[tuple[int, int], tuple[int, int]] = ((8, 1), (9, 15))

#: Sleeper ``scoring`` values that are genuinely redraft formats with an FFC board analog.
#: ``dynasty_*``/``idp`` are a different market (rookie picks, defensive players) and are excluded.
SCORING_MAP: dict[str, str] = {"ppr": "ppr", "half_ppr": "half-ppr", "std": "standard"}

#: FFC publishes 10- and 12-team boards only; a draft is compared to whichever is closer in size.
FFC_TEAM_SIZES: tuple[int, ...] = (10, 12)

PANEL_COLS = [
    "season", "draft_id", "teams", "scoring", "start_ts", "days_to_board",
    "pick_no", "round", "draft_slot", "gsis_id", "name", "pos",
    "slot_rounds", "adp", "board_teams", "adp_rounds", "adp_stdev", "drift", "drift_centered",
]


# ------------------------------------------------------------------------------------------------
# draft selection
# ------------------------------------------------------------------------------------------------
def _in_window(ts: pd.Series, season: pd.Series) -> pd.Series:
    """True where the draft started inside its own season's preseason window."""
    (lo_m, lo_d), (hi_m, hi_d) = PRESEASON_WINDOW
    ts = pd.to_datetime(ts, utc=True)
    lo = pd.to_datetime(pd.Series([dt.datetime(int(s), lo_m, lo_d) for s in season]), utc=True)
    hi = pd.to_datetime(pd.Series([dt.datetime(int(s), hi_m, hi_d, 23, 59) for s in season]),
                        utc=True)
    lo.index = hi.index = ts.index
    return (ts >= lo) & (ts <= hi)


def eligible_drafts(con, seasons: Iterable[int] | None = None) -> pd.DataFrame:
    """The human redraft drafts a drift measurement is meaningful on.

    Filters, in order of how much each costs: real human league (``is_human`` — bot mocks carry no
    opponent identity), ``status='complete'`` (≈44 % of crawled drafts are abandoned), ``snake``
    (auction/linear price differently), a redraft ``scoring`` with an FFC analog, and the
    :data:`PRESEASON_WINDOW`.
    """
    d = con.execute(
        """
        SELECT draft_id, season, teams, rounds, scoring, draft_type,
               to_timestamp(start_time_ms / 1000) AS start_ts
        FROM sleeper_drafts
        WHERE is_human AND status = 'complete' AND draft_type = 'snake'
          AND start_time_ms IS NOT NULL
        """
    ).df()
    if d.empty:
        return d
    d = d[d["scoring"].isin(SCORING_MAP)].copy()
    d["start_ts"] = pd.to_datetime(d["start_ts"], utc=True)
    d = d[_in_window(d["start_ts"], d["season"])]
    if seasons is not None:
        d = d[d["season"].isin({int(s) for s in seasons})]
    d["ffc_scoring"] = d["scoring"].map(SCORING_MAP)
    # nearest published board size (FFC has 10 and 12 only); the rounds normalization absorbs the
    # residual difference, so this only picks *which* consensus board to read.
    d["board_teams"] = [min(FFC_TEAM_SIZES, key=lambda t: abs(t - int(n))) for n in d["teams"]]
    return d.sort_values(["season", "start_ts"]).reset_index(drop=True)


# ------------------------------------------------------------------------------------------------
# the reference board
# ------------------------------------------------------------------------------------------------
def season_board(con, season: int, scoring: str, teams: int) -> pd.DataFrame:
    """That season's canonical FFC consensus board (one snapshot per historical season).

    **Why this does not call** :func:`~fantasy_quant.data.sources.adp.adp_asof`: that reader
    enforces ``snapshot_date <= as_of`` and would return **empty** for the median draft here, since
    FFC stamps its board ~Sep 1–4 and most drafts run in late August. The board is not a *predictor*
    of the draft — it is the yardstick the drift is defined against, the same yardstick for every
    draft in the season — so reading it whole is correct. The cost is real and is not hidden: the
    board may have moved between a draft and its stamp, so every panel row carries
    ``days_to_board`` and Phase 16.8 controls on it. Board-derived *features* inherit the same
    caveat; features taken from ``weekly``/``draft_picks`` do not.
    """
    return con.execute(
        """
        SELECT gsis_id, name, position, adp, stdev, pos_rank, snapshot_date
        FROM adp_snapshots
        WHERE season = ? AND source = 'ffc' AND scoring = ? AND teams = ?
          AND gsis_id IS NOT NULL
        QUALIFY snapshot_date = MAX(snapshot_date) OVER ()
        """,
        [int(season), scoring, int(teams)],
    ).df()


def _picks(con, draft_ids: list[str]) -> pd.DataFrame:
    if not draft_ids:
        return pd.DataFrame()
    ph = ",".join("?" * len(draft_ids))
    return con.execute(
        f"""
        SELECT draft_id, season, pick_no, round, draft_slot, gsis_id, player_name AS name, position
        FROM sleeper_draft_picks
        WHERE draft_id IN ({ph}) AND gsis_id IS NOT NULL
        """,
        draft_ids,
    ).df()


# ------------------------------------------------------------------------------------------------
# the panel
# ------------------------------------------------------------------------------------------------
def build_drift_panel(con, seasons: Iterable[int] | None = None) -> pd.DataFrame:
    """One row per (draft, boarded pick): where the player actually went vs the consensus board.

    Returns :data:`PANEL_COLS` at **pick grain** — deliberately not pre-aggregated to player-season.
    With only a handful of drafts per season, a player-season mean is estimated from very few
    observations; keeping every pick lets 16.8 fit on ~5k rows and cluster the uncertainty by
    season/draft instead of throwing the within-season spread away. :func:`aggregate_player_season`
    provides the aggregate view for reporting and for 16.9's dispersion match.
    """
    drafts = eligible_drafts(con, seasons)
    if drafts.empty:
        return pd.DataFrame(columns=PANEL_COLS)
    picks = _picks(con, drafts["draft_id"].tolist())
    if picks.empty:
        return pd.DataFrame(columns=PANEL_COLS)

    picks["pos"] = _canon_pos(picks["position"])
    picks = picks[picks["pos"].isin(OFFENSE)]
    df = picks.merge(drafts[["draft_id", "teams", "scoring", "ffc_scoring", "board_teams",
                             "start_ts"]], on="draft_id", how="inner")

    frames = []
    for (season, scoring, bteams), g in df.groupby(["season", "ffc_scoring", "board_teams"]):
        board = season_board(con, int(season), str(scoring), int(bteams))
        if board.empty:
            continue
        board = board.rename(columns={"name": "board_name"})
        board["adp"] = pd.to_numeric(board["adp"], errors="coerce")
        board["stdev"] = pd.to_numeric(board["stdev"], errors="coerce")
        m = g.merge(board[["gsis_id", "adp", "stdev", "snapshot_date"]], on="gsis_id", how="inner")
        if m.empty:
            continue
        m["board_teams"] = int(bteams)
        m["days_to_board"] = (pd.to_datetime(m["snapshot_date"], utc=True)
                              - pd.to_datetime(m["start_ts"], utc=True)).dt.total_seconds() / 86400
        frames.append(m)
    if not frames:
        return pd.DataFrame(columns=PANEL_COLS)

    out = pd.concat(frames, ignore_index=True)
    out["slot_rounds"] = out["pick_no"] / out["teams"]
    out["adp_rounds"] = out["adp"] / out["board_teams"]
    # positive = taken EARLIER than the board said (a reach / the hype direction) — see module doc.
    out["drift"] = out["adp_rounds"] - out["slot_rounds"]
    # Each room has its own level offset (a 14-round draft against a ~200-deep board leaves a
    # systematic gap, and K/DST picks consume slots the offense-only panel never sees), so raw
    # drift carries a draft fixed effect that has nothing to do with any player. Centering within
    # the draft isolates the actual question: did *this* player go early **relative to how this
    # room drafted overall**. This is the headline 16.8 target; raw ``drift`` is kept for reporting.
    out["drift_centered"] = out["drift"] - out.groupby("draft_id")["drift"].transform("mean")
    out["adp_stdev"] = out["stdev"]
    out = out.dropna(subset=["drift"])
    return out[PANEL_COLS].sort_values(["season", "draft_id", "pick_no"]).reset_index(drop=True)


def aggregate_player_season(panel: pd.DataFrame) -> pd.DataFrame:
    """Per (season, player): mean/sd drift and how many drafts it rests on.

    ``sd_drift`` is the **cross-draft dispersion** Phase 16.9 must reproduce (its done-bar is a
    variance match, not just a mean match), and ``n_drafts`` is the honesty column — most
    player-seasons here rest on very few drafts.
    """
    if panel.empty:
        return pd.DataFrame(columns=["season", "gsis_id", "name", "pos", "n_drafts",
                                     "mean_drift", "sd_drift", "mean_drift_centered",
                                     "mean_adp_rounds"])
    g = panel.groupby(["season", "gsis_id"])
    out = pd.DataFrame({
        "name": g["name"].first(),
        "pos": g["pos"].first(),
        "n_drafts": g["draft_id"].nunique(),
        "mean_drift": g["drift"].mean(),
        "sd_drift": g["drift"].std(ddof=0),
        "mean_drift_centered": g["drift_centered"].mean(),
        "mean_adp_rounds": g["adp_rounds"].mean(),
    }).reset_index()
    return out.sort_values(["season", "mean_drift"], ascending=[True, False]).reset_index(drop=True)


# ------------------------------------------------------------------------------------------------
# leave-one-draft-out Sleeper board (breaks the source_divergence circularity)
# ------------------------------------------------------------------------------------------------
def heldout_sleeper_board(panel: pd.DataFrame) -> pd.Series:
    """Leave-one-draft-out mean slot (in rounds) per (season, player), aligned to ``panel``'s index.

    The stored ``sleeper_human`` ADP board is literally the mean pick number over these drafts, so
    ``FFC − sleeper_human`` is (up to scale) the negative of this panel's own target: a model fed
    that feature would "discover" a spectacular signal that is pure self-prediction. Recomputing
    the sharper-market board from every draft **except the row's own** removes that identity while
    keeping the feature's meaning — where does the sharp room disagree with the public board?

    ``NaN`` where a player has only one draft in the season (nothing left to average over), which
    also means a single-draft season contributes no rows to the headline 16.8 fit.
    """
    if panel.empty:
        return pd.Series(dtype=float)
    key = [panel["season"], panel["gsis_id"]]
    grp = panel.groupby(key)["slot_rounds"]
    tot, cnt = grp.transform("sum"), grp.transform("count")
    # exclude every pick from the row's own draft, not merely the row itself: a draft contributes
    # exactly one pick per player, so leave-one-out at row grain is leave-one-draft-out here.
    out = (tot - panel["slot_rounds"]) / (cnt - 1)
    return out.where(cnt > 1, np.nan)


# ------------------------------------------------------------------------------------------------
# gates
# ------------------------------------------------------------------------------------------------
def assert_drift_panel_pit(panel: pd.DataFrame, drafts: pd.DataFrame) -> None:
    """Structural checks: every panel draft is an eligible one, and every row sits in-window.

    Does **not** assert ``days_to_board >= 0`` — the board legitimately post-dates most drafts
    (:func:`season_board`); that gap is measured and controlled, not forbidden.
    """
    if panel.empty:
        return
    unknown = set(panel["draft_id"]) - set(drafts["draft_id"])
    assert not unknown, f"{len(unknown)} panel drafts are not in the eligible set"
    assert _in_window(panel["start_ts"], panel["season"]).all(), \
        "a panel row falls outside the preseason window"
    assert (panel["teams"] > 0).all(), "non-positive team count would break the rounds units"


def summarize(panel: pd.DataFrame) -> dict:
    """Headline shape of the panel — what the 16.7 done-bar reports."""
    if panel.empty:
        return {"n_rows": 0}
    return {
        "n_rows": int(len(panel)),
        "n_drafts": int(panel["draft_id"].nunique()),
        "n_seasons": int(panel["season"].nunique()),
        "n_players": int(panel["gsis_id"].nunique()),
        "mean_drift": float(panel["drift"].mean()),
        "sd_drift": float(panel["drift"].std(ddof=0)),
        "p10_drift": float(panel["drift"].quantile(0.10)),
        "p90_drift": float(panel["drift"].quantile(0.90)),
        "mean_days_to_board": float(panel["days_to_board"].mean()),
    }
