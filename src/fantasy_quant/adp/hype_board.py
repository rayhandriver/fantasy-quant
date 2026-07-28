"""Phase 16.10 — the curated hype board.

**Why a curated table exists at all.** 16.8 asked whether a model can predict which players get
drafted ahead of their ADP, and the answer was a clean null: the headline's whole apparent skill
came from `source_divergence`, a sibling-derived leak, and the ablation without it scored *worse*
than assuming everyone drafts at ADP. 16.9 then found that the correlated narrative shock cannot
move a hyped player into the candidate set at all, because `top_k` is a hard rank filter applied
before utility. So there is no fitted channel through which "the room is high on this guy" reaches
the simulator. What is left is the honest one: a **human writes it down**, and the machine applies
it exactly as written.

That makes this the sibling of `reference/coaches.csv` — the other place in this repo where a table
is hand-curated because no feed answers the question. It is emphatically **not** the sibling of
`reference/situation_events_2026.csv`, which 16.5 taught us to *derive*: the rule from that episode
("derived-vs-curated") is that you hand-curate only the residue no ingested table can answer, and
you spend the human budget there. Applied here, that splits the work in two:

* **WHO to look at is derived** (:func:`nominate`) — the machine ranks the board by the terms that
  actually survived 16.8's ablation, plus live 16.11 momentum. No human guesses at the candidate
  list, which is exactly the failure the 16.5 rebuild caught (a hand-written board that missed
  A.J. Brown at ADP 13.6 while carrying a player at ADP 167).
* **WHY, and how much, is curated** — the ``note``/``source``/``pick_delta`` columns. A narrative
  is not in any table we ingest, so that is where the human budget goes.

**The claim this table makes, stated plainly.** ``pick_delta`` is a *curated, not backtested*
assertion that the room will draft this player that many picks earlier than the consensus board
says. Nothing in Phase 16 validates it — three separate honest nulls say the opposite is
unprovable on the data we have. It is therefore **opt-in everywhere and default OFF**, the same
"kept, not default" treatment as the 16.9 shock, Phase 7, the props layer and the 13.2 win-tilt.

**The review gate is structural, not advisory.** Rows carry ``reviewed``; :func:`load_hype_board`
refuses unreviewed rows by default, so a Claude-drafted board cannot reach a simulation until a
human has actually signed the file. Same contract as the 16.3 playcaller table.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from fantasy_quant.draft.opponent_model import ADP_SPEC as _ADP_SPEC

HYPE_CSV = Path("reference/hype_board.csv")

HYPE_COLS = ["season", "gsis_id", "player", "position", "team", "adp", "pick_delta",
             "note", "source", "evidence", "confidence", "reviewed"]

_EVIDENCE = ("derived", "web", "derived+web")
_CONFIDENCE = ("high", "med", "low")

#: A hard cap on how far a curated row may move a player, in picks. A hype board is a nudge on a
#: consensus board, not a replacement for it; without a cap one typo (or one enthusiastic research
#: pass) silently rewrites the draft. Two rounds in a 12-team league is already a large claim.
MAX_PICK_DELTA = 24.0

#: Ranking weights = the 16.8 coefficients that **survived the `source_divergence` ablation**, in
#: their measured units (rounds of drift per unit / per SD). Reusing the measured terms rather than
#: inventing weights is the one licensed use of a null model: 16.8 could not forecast an individual
#: player's drift, but it did measure which observables describe rooms drafting off-consensus.
ABLATION_SURVIVOR_W: dict[str, float] = {
    "rookie": 0.73,          # +0.73 rounds, the single largest survivor
    "adp_stdev_z": 0.35,     # +0.35 rounds/SD — the crowd disagreeing with itself
    "vbd_gap_z": 0.18,       # +0.18 rounds/SD
}

#: Weight on live 16.11 momentum, once it has been put on the same scale as the terms above.
#: Not a fitted coefficient — momentum is forward-only and unbacktestable by construction — so it
#: is a judgment, isolated here where it can be turned off.
MOMENTUM_W = 1.0

#: Nominal draft date. FFC's historical boards are dated around here, so it is also the horizon a
#: 2026 velocity is extrapolated to.
DRAFT_MONTH_DAY = (9, 1)

#: Cap on how many rounds of movement momentum may contribute. :data:`ABLATION_SURVIVOR_W` is in
#: *rounds of drift*, while velocity is *rounds per week*, so the two are only commensurate after
#: multiplying by a horizon — without that step momentum is nearly inert, and the first run of this
#: function duly dropped Daniel Jones (the single largest riser on the live board, +5.3 picks/wk,
#: a locked-in starter on a new $88M deal) clean out of the top 45. But linearly extrapolating a
#: three-snapshot slope five weeks forward is not a credible forecast either, so the contribution
#: is capped: enough to rank a genuine mover, not enough to let one steep line run the table.
MOMENTUM_CAP_ROUNDS = 2.0

#: FFC-vs-ECR divergence, off by default. It is a genuinely *independent* second vendor (unlike
#: 16.8's leaky sibling-draft divergence), but it has never been walk-forward scored and never can
#: be: 0.11 established the FantasyPros ECR archive is kickoff-dated. Shipping it off, with a
#: switch, is the ablation discipline that turned 16.8's weak positive into an honest null — built
#: in from the start this time rather than discovered afterwards.
ECR_DIVERGENCE_W = 0.0


# ------------------------------------------------------------------------------------------------
# WHO — derived nomination
# ------------------------------------------------------------------------------------------------
def _z(v: pd.Series) -> np.ndarray:
    x = pd.to_numeric(v, errors="coerce").to_numpy(float)
    if np.all(np.isnan(x)):
        return np.zeros(len(x))
    x = np.where(np.isnan(x), np.nanmedian(x), x)
    sd = x.std()
    return (x - x.mean()) / sd if sd > 0 else np.zeros(len(x))


def _z_resid(v: pd.Series, adp: pd.Series, pos: pd.Series | None = None) -> np.ndarray:
    """z-score of ``v`` **after removing what board depth (and position) alone explain**.

    This is not a refinement, it is a correctness fix. :data:`ABLATION_SURVIVOR_W` holds *partial*
    coefficients: 16.8 fit them with ``adp_rounds`` in the model (itself −0.19/SD), so each one
    means "holding depth fixed". Both carriers are strongly depth-dependent — ADP standard deviation
    grows mechanically with ADP (2026: sd≈3 picks at the top of the board, ≈30 near the bottom), and
    a rank gap has more room to open up deep. Scoring them unconditionally therefore does not rank
    players by disagreement or by value gap; it ranks them by *how deep they are*, and the first run
    of :func:`nominate` duly returned an ADP-120-to-175 list with almost nothing from the early
    rounds.

    Regressing depth out first restores the intended reading: *unusually* disputed **for a player
    at his cost**. The control carries **both** ``log(adp)`` and ``adp``, which nests the two
    plausible shapes rather than betting on one — with ``log`` alone, a carrier that happens to grow
    linearly in ADP leaks its curvature into the residual and lands the very top of the board in the
    output for purely functional-form reasons.

    ``pos`` extends the same argument to position, which 16.8 also carried as its own dummies
    (``pos_WR`` +0.47, ``pos_TE``). Without it the second run of :func:`nominate` came back
    TE-flooded — our value board likes tight ends more than ADP does across the board, so every TE
    inherited a large ``vbd_gap``. That is a *value* claim about a position, and a real one, but it
    is not evidence that any individual tight end has a narrative. Netting it out leaves the
    within-position outlier, which is what a hype board is asking for.
    """
    y = pd.to_numeric(v, errors="coerce").to_numpy(float)
    if np.all(np.isnan(y)):
        return np.zeros(len(y))
    y = np.where(np.isnan(y), np.nanmedian(y), y)
    a = pd.to_numeric(adp, errors="coerce").to_numpy(float)
    a = np.where(np.isnan(a) | (a <= 0), np.nanmedian(a[a > 0]) if (a > 0).any() else 1.0, a)
    cols = [np.ones(len(y)), np.log(a), a]
    if pos is not None:
        p = pos.astype(str).to_numpy()
        # drop one level (the first, alphabetically) to keep the design full rank
        for lv in sorted(set(p))[1:]:
            cols.append((p == lv).astype(float))
    x = np.column_stack(cols)
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    resid = y - x @ beta
    sd = resid.std()
    # A carrier fully explained by its controls has residuals at floating-point zero — and
    # `resid / resid.std()` would then divide ~1e-15 by ~1e-15 and hand back O(1) z-scores made
    # entirely of rounding error, which is worse than useless because it looks like signal. Scale
    # the floor to the data so it degrades to "no information" instead.
    floor = 1e-9 * max(float(np.abs(y).max()), 1.0)
    return resid / sd if sd > floor else np.zeros(len(resid))


def _weeks_to_draft(vel: pd.DataFrame, season: int) -> float:
    """Weeks from the freshest snapshot to the nominal draft date, floored at zero.

    Read from the data rather than hardcoded, so the horizon shrinks automatically as the season
    approaches and momentum stops being extrapolated past the draft it is meant to anticipate.
    """
    if vel.empty:
        return 0.0
    last = pd.Timestamp(max(vel["last_date"]))
    draft = pd.Timestamp(year=int(season), month=DRAFT_MONTH_DAY[0], day=DRAFT_MONTH_DAY[1])
    return max((draft - last).days, 0) / 7.0


def nominate(con, season: int, *, scoring: str = "ppr", teams: int = 10, k: int = 40,
             ecr_w: float = ECR_DIVERGENCE_W, momentum_w: float = MOMENTUM_W) -> pd.DataFrame:
    """Rank the ``season`` board by how likely a player is to *have a narrative worth researching*.

    This is a **research-triage device, not a forecast**. It says "these are the players a human
    should go read about", and every component is reported alongside the composite so the reviewer
    can see which term nominated each row and discount accordingly.

    Components, and where each comes from:

    ``rookie`` / ``adp_stdev_z`` / ``vbd_gap_z``
        The three 16.8 ablation survivors, weighted by their measured effect sizes
        (:data:`ABLATION_SURVIVOR_W`).
    ``momentum``
        16.11 ``velocity_shrunk``, converted to rounds/week. Live-2026-only and not backtestable.
    ``ecr_divergence``
        FFC ADP minus ECR-implied ADP (positive ⇒ the experts rank him *ahead* of where the drafting
        public takes him). Reported always; weighted **zero** by default — see
        :data:`ECR_DIVERGENCE_W`.
    """
    from fantasy_quant.adp.boards import ecr_to_adp_calibration
    from fantasy_quant.adp.momentum import adp_velocity
    from fantasy_quant.situation import events
    from fantasy_quant.valuation.value_board import value_board

    bd = events.board(con, season)                       # reuse: dual-sourced, team-checked
    if bd.empty:
        return pd.DataFrame(columns=["gsis_id", "player", "position", "team", "adp", "score"])

    # --- adp_stdev + momentum, off the live snapshot series ------------------------------------
    vel = adp_velocity(con, season, scoring=scoring, teams=teams)
    board_size = max(int(teams), 1)
    horizon = _weeks_to_draft(vel, season)
    if not vel.empty:
        mom = vel[["gsis_id", "velocity_shrunk", "stdev_now", "n_snapshots"]].copy()
        # picks/wk -> rounds/wk -> rounds of movement still to come by draft day, capped
        mom["momentum"] = (mom["velocity_shrunk"] / board_size * horizon).clip(
            -MOMENTUM_CAP_ROUNDS, MOMENTUM_CAP_ROUNDS)
        bd = bd.merge(mom[["gsis_id", "momentum", "stdev_now", "n_snapshots"]],
                      on="gsis_id", how="left")
    else:
        bd["momentum"], bd["stdev_now"], bd["n_snapshots"] = 0.0, np.nan, 0
    bd["momentum"] = bd["momentum"].fillna(0.0)

    # --- rookie: never appeared in ANY prior season -------------------------------------------
    # Deliberately *not* 16.5's `new_to_league` (no snaps in season-1): that flag exists to mark a
    # changed room and correctly fires for a veteran who missed the year, but 16.8's `rookie` came
    # from Sleeper `years_exp == 0` and means genuinely new. The first run of this function used the
    # season-1 test and labelled Brandon Aiyuk, Tank Dell and Jonathon Brooks rookies — all
    # established players returning from injury. Looking back across every season separates them.
    seen = con.execute(
        "SELECT DISTINCT gsis_id FROM weekly WHERE season < ? AND gsis_id IS NOT NULL",
        [int(season)],
    ).df()
    bd["rookie"] = (~bd["gsis_id"].isin(set(seen["gsis_id"]))).astype(float)

    # --- vbd_gap: the value board's own rank vs the market's, in rounds ------------------------
    vb = value_board(con, season)
    rank = dict(zip(vb["player_key"], vb["overall_rank"].astype(float), strict=False))
    bd["vbd_rank"] = bd["gsis_id"].map(rank)
    bd["vbd_gap"] = (bd["adp"] - bd["vbd_rank"]) / board_size      # >0 ⇒ we like him more than ADP

    # --- ecr divergence: an independent second vendor, reported, unweighted by default ----------
    bd["ecr_divergence"] = np.nan
    cal = ecr_to_adp_calibration(con, scoring)
    ecr = con.execute(
        """SELECT gsis_id, CAST(ecr AS DOUBLE) AS ecr FROM ecr_snapshots
           WHERE season = ? AND scoring = ? AND is_preseason AND gsis_id IS NOT NULL
           QUALIFY as_of = MAX(as_of) OVER ()""",
        [int(season), scoring],
    ).df()
    if not ecr.empty and cal is not None:
        iso, depth = cal
        ecr = ecr[ecr["ecr"] <= depth].copy()
        ecr["ecr_adp"] = iso.predict(ecr["ecr"].to_numpy())
        bd = bd.merge(ecr[["gsis_id", "ecr_adp"]], on="gsis_id", how="left")
        bd["ecr_divergence"] = (bd["adp"] - bd["ecr_adp"]) / board_size

    # --- the composite -------------------------------------------------------------------------
    # depth- and position-residualized: ABLATION_SURVIVOR_W holds partial coefficients
    # (see _z_resid)
    bd["adp_stdev_z"] = _z_resid(bd["stdev_now"], bd["adp"], bd["position"])
    bd["vbd_gap_z"] = _z_resid(bd["vbd_gap"], bd["adp"], bd["position"])
    bd["ecr_divergence_z"] = _z_resid(bd["ecr_divergence"], bd["adp"], bd["position"])
    bd["score"] = (
        ABLATION_SURVIVOR_W["rookie"] * bd["rookie"]
        + ABLATION_SURVIVOR_W["adp_stdev_z"] * bd["adp_stdev_z"]
        + ABLATION_SURVIVOR_W["vbd_gap_z"] * bd["vbd_gap_z"]
        + float(momentum_w) * bd["momentum"]
        + float(ecr_w) * bd["ecr_divergence_z"]
    )
    # ★ Ranked by |score|, so BOTH tails are nominated. The composite is signed — positive means
    # "the room reaches for him" — and taking the top k by raw score therefore surfaces only
    # risers. A faller is exactly as worth researching: the strongest claim on the current board is
    # Zach Charbonnet at −10 picks (placed on the PUP list, out a minimum four games), and ranking
    # by raw score dropped him off the list entirely. Direction is preserved in `score` for the
    # reviewer; only the ordering is two-sided.
    bd["abs_score"] = bd["score"].abs()
    cols = ["gsis_id", "player", "position", "team", "adp", "score", "momentum", "rookie",
            "adp_stdev_z", "vbd_gap_z", "ecr_divergence", "stdev_now", "vbd_rank", "n_snapshots"]
    return bd.sort_values("abs_score", ascending=False).head(k)[cols].reset_index(drop=True)


# ------------------------------------------------------------------------------------------------
# the table: schema, load, review gate
# ------------------------------------------------------------------------------------------------
def assert_hype_schema(df: pd.DataFrame) -> None:
    """Structural validation. Raises rather than warns — a malformed hype row silently moves a
    player on a draft board, which is precisely the class of error nobody notices."""
    missing = [c for c in HYPE_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"hype board is missing columns: {missing}")
    if df.empty:
        return
    d = pd.to_numeric(df["pick_delta"], errors="coerce")
    if d.isna().any():
        bad = df.loc[d.isna(), "player"].tolist()[:5]
        raise ValueError(f"non-numeric pick_delta for: {bad}")
    if (d.abs() > MAX_PICK_DELTA).any():
        bad = df.loc[d.abs() > MAX_PICK_DELTA, "player"].tolist()[:5]
        raise ValueError(f"pick_delta beyond +/-{MAX_PICK_DELTA} picks for: {bad} — a hype board "
                         "nudges a consensus board, it does not replace it")
    if df["gsis_id"].isna().any() or (df["gsis_id"].astype(str).str.strip() == "").any():
        raise ValueError("every hype row needs a gsis_id — a name alone cannot be joined safely")
    if df["gsis_id"].duplicated().any():
        dup = df.loc[df["gsis_id"].duplicated(), "player"].tolist()[:5]
        raise ValueError(f"duplicate hype rows for: {dup}")
    bad_ev = set(df["evidence"].dropna()) - set(_EVIDENCE)
    if bad_ev:
        raise ValueError(f"unknown evidence values: {sorted(bad_ev)} (allowed {_EVIDENCE})")
    bad_cf = set(df["confidence"].dropna()) - set(_CONFIDENCE)
    if bad_cf:
        raise ValueError(f"unknown confidence values: {sorted(bad_cf)} (allowed {_CONFIDENCE})")


def _as_bool(s: pd.Series) -> pd.Series:
    return (s.astype(str).str.strip().str.lower()
            .isin(("true", "1", "yes", "y", "t")))


def load_hype_board(path: Path | str = HYPE_CSV, season: int | None = None, *,
                    require_reviewed: bool = True) -> pd.DataFrame:
    """Load, validate and (by default) **refuse unreviewed rows**.

    ``require_reviewed=False`` exists for the drafting/inspection path only — the done-bar step
    reads its own freshly generated board that way. Every consumer that can move a simulated draft
    leaves the default alone, so an un-signed board is inert rather than quietly live.
    """
    p = Path(path)
    if not p.exists():
        return pd.DataFrame(columns=HYPE_COLS)
    df = pd.read_csv(p, comment="#")
    if df.empty:
        return pd.DataFrame(columns=HYPE_COLS)
    assert_hype_schema(df)
    df["reviewed"] = _as_bool(df["reviewed"])
    df["pick_delta"] = pd.to_numeric(df["pick_delta"], errors="coerce")
    if season is not None:
        df = df[df["season"].astype(int) == int(season)]
    if require_reviewed:
        df = df[df["reviewed"]]
    return df.reset_index(drop=True)


# ------------------------------------------------------------------------------------------------
# APPLY — pick-space and utility-space
# ------------------------------------------------------------------------------------------------
def hype_deltas(board: pd.DataFrame, hype: pd.DataFrame, *,
                key: str = "player_key") -> np.ndarray:
    """Per-board-row ``pick_delta``, positive = the room takes him **earlier** than ADP.

    Aligned to ``board``'s row order (0 where the player has no hype row), which is the contract
    every consumer here depends on. ``key`` is the board's player-id column — a simulator board
    calls it ``player_key``, a raw ADP board ``gsis_id``.
    """
    out = np.zeros(len(board))
    if hype.empty or key not in board.columns:
        return out
    lut = dict(zip(hype["gsis_id"].astype(str),
                   pd.to_numeric(hype["pick_delta"], errors="coerce").fillna(0.0), strict=False))
    ids = board[key].astype(str).to_numpy()
    for i, pid in enumerate(ids):
        out[i] = lut.get(pid, 0.0)
    return out


def apply_hype(board: pd.DataFrame, hype: pd.DataFrame, *, beta_adp_s: float,
               key: str = "player_key", adp_spec=None, adp_col: str = "adp") -> np.ndarray:
    """Convert the curated pick-space board into the **utility offset** the 16.9 channel takes.

    The conversion runs through the opponent model's own ADP coefficient rather than a tuning
    constant: a row saying "the room takes him 6 picks early" produces exactly the utility the model
    would have assigned had his ADP been 6 picks lower. So a hype row means the same thing to the
    simulator as it does to the human who wrote it, and it inherits the model's units automatically
    if 11.1 is ever refit.

        u_offset = -beta_adp_s * (f(adp) - f(adp - pick_delta))

    ★ **T15 made this exact rather than linear.** It used to read ``pick_delta / _ADP_SCALE``, the
    derivative of a linear ``adp_s``. Under curvature the utility a claim is worth depends on *where
    on the board the player sits* — the same "+6 picks" is worth far more at ADP 8 than at ADP 150,
    which is precisely the asymmetry T16 ran into (a deep claim that moved nothing). Taking the
    exact difference rather than a local derivative keeps a large ``pick_delta`` honest, since the
    board's curvature over 24 picks is not negligible at the top.

    Feed the result to :func:`~fantasy_quant.draft.personalities.make_opponent_pick_fn` as ``hype``.
    Note the sign: ``beta_adp_s`` is negative (a later ADP is less attractive), so a positive
    ``pick_delta`` yields a positive utility bump.
    """
    deltas = hype_deltas(board, hype, key=key)
    spec = adp_spec if adp_spec is not None else _ADP_SPEC
    if spec.kind == "linear":
        return -float(beta_adp_s) * deltas / float(spec.scale)
    adp = pd.to_numeric(board[adp_col], errors="coerce").to_numpy(float)
    adp = np.where(np.isfinite(adp), adp, float(spec.scale))
    shifted = np.clip(adp - deltas, 0.5, None)     # a claim cannot push a player before pick 0.5
    return -float(beta_adp_s) * (spec.feature(adp) - spec.feature(shifted))


def hyped_adp(board: pd.DataFrame, hype: pd.DataFrame, *, adp_col: str = "adp",
              key: str = "player_key") -> np.ndarray:
    """The board's ADP shifted by the curated deltas — the **pick-space** view of the same claim.

    This is what an availability/lookahead consumer wants (16.12b): a hyped player's *effective*
    draft cost is earlier, so he is less likely to survive to your next pick.
    """
    adp = pd.to_numeric(board[adp_col], errors="coerce").to_numpy(float)
    return adp - hype_deltas(board, hype, key=key)


def summarize(hype: pd.DataFrame) -> dict:
    """What the loaded board actually contains — leads with the review state, because an unreviewed
    board is inert and that fact should never be inferred from a row count."""
    if hype.empty:
        return {"n_rows": 0, "n_reviewed": 0, "curated_not_backtested": True}
    rev = _as_bool(hype["reviewed"]) if hype["reviewed"].dtype == object else hype["reviewed"]
    return {
        "n_rows": int(len(hype)),
        "n_reviewed": int(rev.sum()),
        "curated_not_backtested": True,
        "seasons": sorted({int(s) for s in hype["season"]}),
        "mean_abs_delta": float(pd.to_numeric(hype["pick_delta"]).abs().mean()),
        "max_abs_delta": float(pd.to_numeric(hype["pick_delta"]).abs().max()),
        "by_position": hype["position"].value_counts().to_dict(),
        "n_positive": int((pd.to_numeric(hype["pick_delta"]) > 0).sum()),
        "n_negative": int((pd.to_numeric(hype["pick_delta"]) < 0).sum()),
    }
