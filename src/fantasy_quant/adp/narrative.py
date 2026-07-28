"""Phase 16.9 — the correlated per-draft narrative shock.

**The insight this phase was opened on** (user, 2026-07-23): independent per-opponent sampling
washes out clustering. If every seat draws its own noise, a hyped player's early picks average
away and he *always* falls in your mocks — then gets sniped in the real draft. Real rooms share a
narrative: if the room is high on a player this August, *every* manager in that room is high on
him. So the shock must be drawn **once per draft** and applied to **every** opponent, not
resampled per seat.

**What measurement did to that premise (Session G).** The mechanism above is right, but the
deficit it was meant to repair was not there. Measured against the 16.7 panel, the simulator did
not under-disperse draft slots — it **over**-dispersed them, by 59 %. The cause was not behavioural
at all but a **choice-set contract violation**: 11.1 is a conditional logit fit on the top-40
available players by ADP (:data:`~fantasy_quant.draft.opponent_model.CHOICE_TOP_K`), and both the
simulator and the availability sim were applying that β to the *entire* board. A conditional
logit's coefficients only mean something relative to the candidate set they were estimated on.
Honouring the contract took pooled ``drift_centered_sd`` from 2.89 to 1.94 against a realized
1.82, and *improved* the availability Brier — so the level done-bar is met by the fix, not by a
shock.

**What is left for the shock to do — the profile, not the level.** Realized cross-draft dispersion
rises steeply with board depth (Spearman(sd_drift, ADP rounds) = **+0.68**): the consensus top of
the board goes at the same slot in every room, while a round-12 flier swings wildly. The banded
simulator's dispersion is **flat** in depth (+0.03, p=0.21). Pooled sd matches by cancellation —
too much variance at the top, too little at depth. That is exactly a *reallocation* problem, and
it is what this module is calibrated against: a per-player shock scale ``tau`` that grows with
depth and with the features that survived 16.8's ablation.

**The null's constraint (Session F, honoured here).** 16.8 found no per-player *mean* drift
signal: the headline's apparent skill was `source_divergence`, a sibling-derived leak, and the
ablation without it scored worse than "everyone drafts at ADP". So this module models **dispersion
only**. The shock is zero-mean by construction (:meth:`NarrativeShock.draw`) — it says *who is
argued about*, never *who goes early*. The surviving predictors it is allowed to use are
``rookie``, ``adp_stdev``, ``vbd_gap`` and the position dummies, plus board depth.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from fantasy_quant.draft.personalities import USE_MODEL_BAND as _USE_MODEL_BAND

#: Depth plus the 16.8 ablation survivors. `adp_stdev` is the crowd disagreeing with itself, which
#: is the most direct observable of "this player is argued about"; `rookie` was the single largest
#: survivor (+0.73 rounds); the position dummies carry the TE/WR asymmetry 16.7 measured.
NARRATIVE_FEATURES: tuple[str, ...] = (
    "log_depth", "adp_stdev_z", "vbd_gap_z", "rookie", "is_WR", "is_TE",
)

#: Floor on ADP rounds before the log, so pick 1.01 does not produce a huge negative depth.
_MIN_DEPTH = 0.25


def shock_features(board: pd.DataFrame, *, board_teams: int) -> pd.DataFrame:
    """Assemble :data:`NARRATIVE_FEATURES` for a draft board.

    ``board`` needs ``adp`` and ``pos``; ``adp_stdev``, ``vbd_gap`` and ``rookie`` are used when
    present and default to neutral (0 / the median) when not, so a bare simulator board still
    yields a usable depth-only shock rather than raising.
    """
    n = len(board)
    adp = pd.to_numeric(board["adp"], errors="coerce").to_numpy(float)
    depth = np.maximum(adp / max(board_teams, 1), _MIN_DEPTH)
    pos = board["pos"].to_numpy()

    def _z(col: str) -> np.ndarray:
        if col not in board.columns:
            return np.zeros(n)
        v = pd.to_numeric(board[col], errors="coerce").to_numpy(float)
        if np.all(np.isnan(v)):
            return np.zeros(n)
        v = np.where(np.isnan(v), np.nanmedian(v), v)
        sd = v.std()
        return (v - v.mean()) / sd if sd > 0 else np.zeros(n)

    rookie = (pd.to_numeric(board["rookie"], errors="coerce").fillna(0).to_numpy(float)
              if "rookie" in board.columns else np.zeros(n))
    return pd.DataFrame({
        "log_depth": np.log(depth),
        "adp_stdev_z": _z("adp_stdev"),
        "vbd_gap_z": _z("vbd_gap"),
        "rookie": rookie,
        "is_WR": (pos == "WR").astype(float),
        "is_TE": (pos == "TE").astype(float),
    }, index=board.index)


@dataclass
class NarrativeShock:
    """A per-player narrative dispersion scale, and the per-draft draw that applies it.

    ``coef`` maps :data:`NARRATIVE_FEATURES` to log-scale coefficients and ``intercept`` sets the
    overall size, so ``tau = exp(intercept + X @ coef)`` is strictly positive. ``intercept`` is
    **calibrated by simulation**, not read off the realized panel: the panel's dispersion is in
    draft *rounds* while the shock lives in *utility*, and part of realized dispersion is already
    produced by the model's own softmax. Only the *shape* transfers from the panel.

    ⚠ **T15 (2026-07-27): ``intercept`` is NOT transportable across an ``AdpSpec``/``BandSpec``
    change, and that is enforced rather than noted.** It is a size in *utility* units, calibrated
    by simulation against realized dispersion under one particular ADP transform. T15 replaced that
    transform (linear -> ``(adp/50)^0.15``) and refit β, so utility is no longer the same scale: the
    old intercept applied to the new room is a differently-sized shock wearing a calibrated label.
    ``calibrated_under`` records the specs a calibration was performed with, and
    :meth:`assert_transportable` refuses a mismatch. **The shipped shock is default-OFF and 16.9
    measured its intercept as unidentified** (a 50x sweep moved the target metric less than its own
    between-run noise), so nothing is re-fit here — inventing a number for a parameter that was
    already a noise draw would be worse than declaring it stale.
    """
    coef: dict[str, float] = field(default_factory=dict)
    intercept: float = -3.0
    features: tuple[str, ...] = NARRATIVE_FEATURES
    #: ``{"adp_spec": {...}, "band": {...}}`` of the model this intercept was calibrated against.
    #: ``None`` = never calibrated (the default shock is a placeholder, not a fit).
    calibrated_under: dict | None = None

    def assert_transportable(self, model) -> None:
        """Fail loudly if this shock's size was calibrated against a different model contract.

        Cheap, structural, and placed here because the failure it prevents is silent: a shock of the
        wrong size still produces a legal draft and a plausible-looking room. *A coefficient is not
        transportable without its controls* — the fourth instance in this project, and the first one
        caught before it shipped rather than afterwards.
        """
        if self.calibrated_under is None:
            return                     # never calibrated; the caller owns an uncalibrated default
        now = {"adp_spec": getattr(model, "adp_spec", None), "band": getattr(model, "band", None)}
        now = {k: (v.to_dict() if v is not None else None) for k, v in now.items()}
        if now != self.calibrated_under:
            raise ValueError(
                "NarrativeShock.intercept was calibrated under "
                f"{self.calibrated_under} but is applied to {now}. The intercept is a size in "
                "utility units and does not survive an AdpSpec/BandSpec change — re-calibrate "
                "(steps/phase16_9_narrative.py) or pass calibrated_under=None to opt out.")

    def tau(self, feats: pd.DataFrame) -> np.ndarray:
        """Per-player shock scale (utility units), strictly positive."""
        x = np.column_stack([feats[c].to_numpy(float) for c in self.features])
        b = np.array([self.coef.get(c, 0.0) for c in self.features], float)
        return np.exp(self.intercept + x @ b)

    def draw(self, feats: pd.DataFrame, rng: np.random.Generator) -> np.ndarray:
        """**One** shared narrative draw for **one** draft — call this once per simulated draft and
        hand the result to every opponent, which is the whole point of the phase. Zero-mean by
        construction: 16.8 licensed a dispersion model, not a mean-drift forecast.
        """
        return self.tau(feats) * rng.standard_normal(len(feats))


def fit_shape(agg: pd.DataFrame, feats: pd.DataFrame, *,
              min_drafts: int = 10) -> dict[str, float]:
    """The *relative* dispersion profile: weighted least squares of ``log(sd_drift)`` on
    :data:`NARRATIVE_FEATURES`.

    ``agg`` is :func:`~fantasy_quant.adp.drift_panel.aggregate_player_season` and ``feats`` the
    aligned feature frame. Weighted by ``n_drafts`` because a player-season resting on 11 drafts
    is a far noisier dispersion estimate than one resting on 200. Returns coefficients **without**
    the intercept — that is what :func:`calibrate_intercept` supplies.
    """
    keep = (agg["n_drafts"] >= min_drafts) & (agg["sd_drift"] > 0)
    a, f = agg.loc[keep], feats.loc[keep]
    if len(a) < len(NARRATIVE_FEATURES) + 2:
        return dict.fromkeys(NARRATIVE_FEATURES, 0.0)
    x = np.column_stack([np.ones(len(f))] + [f[c].to_numpy(float) for c in NARRATIVE_FEATURES])
    y = np.log(a["sd_drift"].to_numpy(float))
    w = np.sqrt(a["n_drafts"].to_numpy(float))
    beta, *_ = np.linalg.lstsq(x * w[:, None], y * w, rcond=None)
    return dict(zip(NARRATIVE_FEATURES, beta[1:], strict=False))


def calibrate_intercept(simulate_fn, target_slope: float, *,
                        grid: tuple[float, ...] = (-5.0, -4.0, -3.5, -3.0, -2.5, -2.0, -1.5),
                        ) -> tuple[float, pd.DataFrame]:
    """Pick the shock size that best reproduces the realized **depth slope** of dispersion.

    ``simulate_fn(intercept) -> dict`` runs the simulator at that shock size and reports at least
    ``depth_spearman`` (and anything else worth recording). We match the *slope* rather than the
    pooled level because the level is already carried by the choice-set band — see the module
    docstring. Returns ``(best_intercept, the full grid trace)``, because the trace is the evidence
    that the objective is smooth and the optimum interior rather than pinned to an endpoint.
    """
    rows = []
    for it in grid:
        out = dict(simulate_fn(it))
        out["intercept"] = it
        rows.append(out)
    trace = pd.DataFrame(rows)
    if trace["depth_spearman"].isna().all():
        # the usual cause is a simulation budget below `dispersion_profile`'s `min_drafts`: a
        # per-player dispersion needs several drafts per player, so too few simulated drafts per
        # season yields no estimable player-seasons at all. Fail loudly rather than pick a
        # "best" intercept out of missing data.
        raise ValueError(
            "calibration produced no estimable depth slope — simulate more drafts per season "
            "(a per-player sd needs at least `min_drafts` appearances)")
    best = trace.iloc[(trace["depth_spearman"] - target_slope).abs().argmin()]
    return float(best["intercept"]), trace


# ------------------------------------------------------------------------------------------------
# the measurement instrument: a simulated drift panel, comparable to the realized 16.7 one
# ------------------------------------------------------------------------------------------------
def simulate_drift_panel(con, drafts: pd.DataFrame, model, *, shock: NarrativeShock | None = None,
                         top_k: int | None | str = _USE_MODEL_BAND, seed: int = 0,
                         extras: pd.DataFrame | None = None) -> pd.DataFrame:
    """Replay each row of ``drafts`` as a simulated draft and return a **16.7-shaped** panel.

    One counterfactual per realized draft, matched on season / teams / rounds / board, so the
    simulated and realized dispersions are computed over the same design rather than over whichever
    drafts happened to be convenient. ``shock`` is drawn **once per draft** and shared by every
    seat. ``extras`` optionally supplies ``gsis_id``-keyed ``adp_stdev``/``vbd_gap``/``rookie`` to
    enrich the shock features beyond depth.

    Columns match the realized panel where it matters: ``drift`` (positive = taken EARLIER than the
    board said) and ``drift_centered`` (minus the draft's own mean, which strips the room-level
    offset a 15-round draft against a 200-deep board necessarily carries).
    """
    from fantasy_quant.adp import boards
    from fantasy_quant.adp.panel import OFFENSE, _canon_pos
    from fantasy_quant.draft.personalities import make_opponent_pick_fn
    from fantasy_quant.draft.simulator import simulate_draft

    rng = np.random.default_rng(seed)
    board_cache: dict[tuple, pd.DataFrame] = {}
    rows = []
    for i, (_, d) in enumerate(drafts.iterrows()):
        key = (int(d["season"]), str(d["ffc_scoring"]), int(d["board_teams"]))
        if key not in board_cache:
            bd, _src = boards.resolve_board(con, *key, allow_ecr=False)
            if not bd.empty:
                bd = bd.rename(columns={"name": "player_name"}).copy()
                bd["adp"] = pd.to_numeric(bd["adp"], errors="coerce")
                bd["adp_stdev"] = pd.to_numeric(bd.get("stdev"), errors="coerce")
                bd = bd.dropna(subset=["adp"])
                if extras is not None:
                    bd = bd.merge(extras, on="gsis_id", how="left")
            board_cache[key] = bd
        board = board_cache[key]
        if board.empty:
            continue

        hype = None
        if shock is not None:
            # `simulate_draft` re-sorts and re-indexes the board, so build the shock on the same
            # normalized frame the opponents will index into — otherwise the offsets land on the
            # wrong players, silently.
            from fantasy_quant.draft.simulator import _prepare_board
            prepped = _prepare_board(board)
            enrich = board.set_index("gsis_id") if "gsis_id" in board.columns else None
            f = prepped[["adp", "pos"]].copy()
            if enrich is not None:
                for c in ("adp_stdev", "vbd_gap", "rookie"):
                    if c in enrich.columns:
                        f[c] = prepped["player_key"].map(enrich[c]).to_numpy()
            hype = shock.draw(shock_features(f, board_teams=int(d["board_teams"])), rng)

        fn = make_opponent_pick_fn(model, top_k=top_k, hype=hype)
        st = simulate_draft(board, n_teams=int(d["teams"]), rounds=int(d["rounds"]),
                            seed=int(rng.integers(1 << 30)), opponent_pick_fn=fn,
                            your_pick_fn=lambda s, _f=fn: int(_f(s, s.your_team)))
        log = pd.DataFrame(st.log)
        log["draft_id"] = f"sim{i}"
        log["season"] = int(d["season"])
        log["teams"] = int(d["teams"])
        log["board_teams"] = int(d["board_teams"])
        rows.append(log)

    if not rows:
        return pd.DataFrame(columns=["season", "draft_id", "gsis_id", "pos", "drift",
                                     "drift_centered", "adp_rounds"])
    sim = pd.concat(rows, ignore_index=True)
    sim["pos"] = _canon_pos(sim["pos"])
    sim = sim[sim["pos"].isin(OFFENSE)].copy()
    sim["gsis_id"] = sim["player_key"]
    sim["adp_rounds"] = sim["adp"] / sim["board_teams"]
    sim["drift"] = sim["adp_rounds"] - sim["overall_pick"] / sim["teams"]
    sim["drift_centered"] = sim["drift"] - sim.groupby("draft_id")["drift"].transform("mean")
    return sim.reset_index(drop=True)


def dispersion_profile(panel: pd.DataFrame, *, min_drafts: int = 10) -> dict:
    """The two numbers 16.9 is judged on: the **level** of cross-draft dispersion and its **slope**
    in board depth. A simulator can match the level by cancellation — too much variance at the top
    of the board, too little at the bottom — so the slope is the load-bearing one."""
    from scipy import stats

    if panel.empty:
        return {"pooled_sd": float("nan"), "depth_spearman": float("nan"), "n_player_seasons": 0}
    g = panel.groupby(["season", "gsis_id"])
    ps = pd.DataFrame({
        "n_drafts": g["draft_id"].nunique(),
        "sd_drift": g["drift"].std(ddof=0),
        "adp_rounds": g["adp_rounds"].mean(),
    }).dropna()
    ps = ps[ps["n_drafts"] >= min_drafts]
    if len(ps) < 10:
        return {"pooled_sd": float(panel["drift_centered"].std(ddof=0)),
                "depth_spearman": float("nan"), "n_player_seasons": int(len(ps))}
    sp = stats.spearmanr(ps["sd_drift"], ps["adp_rounds"])
    return {
        "pooled_sd": float(panel["drift_centered"].std(ddof=0)),
        "mean_player_sd": float(ps["sd_drift"].mean()),
        "depth_spearman": float(sp.statistic),
        "depth_spearman_p": float(sp.pvalue),
        "n_player_seasons": int(len(ps)),
    }


def compare_profiles(real_panel: pd.DataFrame, sim_panel: pd.DataFrame, *,
                     min_drafts: int = 10) -> dict:
    """Realized vs simulated dispersion over the **same player-seasons**.

    Comparing each panel's own slope is a trap: a player appears in the simulated panel only when
    he is drafted, so a small simulation budget with a ``min_drafts`` floor silently keeps only the
    shallow end of the board and truncates exactly the depth range the slope is measured over. The
    realized panel rests on ~127 drafts per season and has no such truncation. Intersecting the two
    removes the artifact — both slopes are then computed on one identical set of players.
    """
    from scipy import stats

    def _ps(p: pd.DataFrame) -> pd.DataFrame:
        g = p.groupby(["season", "gsis_id"])
        out = pd.DataFrame({
            "n_drafts": g["draft_id"].nunique(),
            "sd_drift": g["drift"].std(ddof=0),
            "adp_rounds": g["adp_rounds"].mean(),
        }).dropna()
        return out[out["n_drafts"] >= min_drafts]

    a, b = _ps(real_panel), _ps(sim_panel)
    m = a.join(b, how="inner", lsuffix="_real", rsuffix="_sim")
    if len(m) < 25:
        return {"n_matched": int(len(m))}
    sr = stats.spearmanr(m["sd_drift_real"], m["adp_rounds_real"])
    ss = stats.spearmanr(m["sd_drift_sim"], m["adp_rounds_real"])
    agree = stats.spearmanr(m["sd_drift_real"], m["sd_drift_sim"])
    return {
        "n_matched": int(len(m)),
        "depth_slope_real": float(sr.statistic),
        "depth_slope_sim": float(ss.statistic),
        "depth_slope_sim_p": float(ss.pvalue),
        "sd_agreement": float(agree.statistic),
        "sd_agreement_p": float(agree.pvalue),
        "mean_sd_real": float(m["sd_drift_real"].mean()),
        "mean_sd_sim": float(m["sd_drift_sim"].mean()),
    }
