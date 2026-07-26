"""Phase 11.1 — the behavioral opponent model (a Brier-verifiable draft-flow predictor).

The reframe (2026-07-04) promotes the opponent model from "unverifiable frontier flex" to
**core, verifiable infrastructure**: its job — *who does each manager pick, given who's on the
board* — has hard ground truth (the observed pick), so it is Brier/log-loss-scorable over the
real Sleeper corpus (7,699 human drafts after the Session-F.5 expansion, 24,696 managers; the
**eligible redraft** subset the model actually fits on is reported by :func:`corpus_funnel`).

The model is a **conditional (McFadden) logit**: at a pick, the manager chooses one player from
the set still on the board; the utility of each candidate is a linear function of behavioral
features, and the choice probability is the softmax over available candidates. This is the
honest, interpretable upgrade of "ADP + Gaussian noise" — it keeps ADP as the dominant term and
learns the *deviations* real managers show (positional runs, personal position leans, rookie
hype, home-team fandom, roster need).

Two models share this machinery:
  * :class:`OpponentModel` — the full behavioral model (all features).
  * the **ADP-only** baseline (``feature_cols=["adp_s"]``) — a conditional logit on ADP alone,
    i.e. exactly "pick by ADP with logistic noise". Beating *this* on held-out log-loss/Brier is
    the fair 11.1 done-when bar (strictly stronger than the simulator's ADP+Gaussian opponent).

Features are built by :func:`build_choice_frame`; the two **tiers** matter for reuse:
  * **Tier-A (portable):** ``adp_s``, position dummies, ``pos_run3`` — computable from any live
    :class:`~fantasy_quant.draft.simulator.DraftState` board, so the fitted β also drives
    availability simulation (11.2) and realistic mock opponents (11.3).
  * **Tier-B (corpus-only):** ``mgr_lean``, ``rookie``, ``fandom``, ``need`` — need the manager
    profile / player metadata. In a live sim where those are unknown they are set to 0, which
    (utility being linear) is the exact marginalization "no information on this term".

PIT / lockbox note: the corpus spans 2017–2026. Per the 2026-07-11 decision the opponent model
predicts *draft flow*, not player value, so it is treated as **outside** the value-stack lockbox
and may fit on all seasons — but every reported number is **walk-forward** (fit on other seasons,
scored on a held-out season), so no metric is in-sample.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from fantasy_quant.adp.boards import resolve_boards
from fantasy_quant.adp.drift_panel import eligible_drafts
from fantasy_quant.draft.simulator import canon_pos

# Feature layout -------------------------------------------------------------------------------
_POS_DUMMIES = ("is_RB", "is_WR", "is_TE", "is_QB")   # K/DST = reference level
TIER_A = ("adp_s", *_POS_DUMMIES, "pos_run3")
TIER_B = ("mgr_lean", "rookie", "fandom", "need")
ALL_FEATURES = (*TIER_A, *TIER_B)
ADP_ONLY = ("adp_s",)

# roster targets used for the `need` feature (matches simulator RosterSlots base demand)
_NEED_TARGET = {"QB": 1, "RB": 4, "WR": 4, "TE": 1, "K": 1, "DST": 1}
_RUN_WINDOW = 3          # picks looked back for a "positional run"
_ADP_SCALE = 50.0        # adp is divided by this so β is O(1)

#: **The choice-set contract.** A conditional logit estimates β *relative to the candidate set it
#: sees*, so every consumer that simulates picks from this β must offer the same set: the top-K
#: still-available players by consensus ADP. Session G found the simulator (11.3) and the
#: availability sim (11.2) both drawing from the *whole* board instead, which inflated simulated
#: draft-slot dispersion by ~59 %. Fit and simulation now read this one constant.
CHOICE_TOP_K = 40


# =============================================================================================
# feature construction
# =============================================================================================
def _load_board(con, source: str, scoring: str, teams: int) -> pd.DataFrame:
    """Per-season consensus ADP board keyed by gsis (the candidate universe + `adp` feature)."""
    df = con.execute(
        """
        SELECT season, gsis_id, name, position, team, adp
        FROM adp_snapshots
        WHERE source = ? AND scoring = ? AND teams = ? AND gsis_id IS NOT NULL
        QUALIFY snapshot_date = MAX(snapshot_date) OVER (PARTITION BY season)
        """,
        [source, scoring, teams],
    ).df()
    df["pos"] = df["position"].map(canon_pos)
    df = df.dropna(subset=["pos", "adp"])
    df["adp"] = pd.to_numeric(df["adp"], errors="coerce")
    df = df.dropna(subset=["adp"]).sort_values(["season", "adp"])
    return df


def _load_profiles(con) -> pd.DataFrame:
    if not con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name='sleeper_manager_profiles'"
    ).fetchone()[0]:
        return pd.DataFrame()
    prof = con.execute(
        "SELECT manager, avg_reach, pos_share_QB, pos_share_RB, pos_share_WR, pos_share_TE, "
        "fav_teams FROM sleeper_manager_profiles"
    ).df()
    return prof


def build_choice_frame(con, *, top_k: int = CHOICE_TOP_K, skill_only: bool = True,
                       seasons: Iterable[int] | None = None, allow_ecr: bool = True,
                       max_drafts_per_season: int | None = None,
                       seed: int = 0) -> tuple[pd.DataFrame, list[str]]:
    """Turn the human-draft corpus into conditional-logit **choice rows**.

    One row per *(pick, candidate)*: for every real human pick we form the candidate set = the
    ``top_k`` still-available players by consensus ADP, mark the realized pick ``chosen=1``, and
    attach the behavioral features. Returns ``(frame, feature_cols)`` where ``frame`` has a
    ``group`` id (one draft-pick), ``season``, ``draft_id``, ``board_source``, ``chosen`` and the
    feature columns.

    **The corpus is** :func:`~fantasy_quant.adp.drift_panel.eligible_drafts` **, and each draft is
    scored against its own board.** Until Session F.6 this function read *every* human draft —
    dynasty, 2QB, IDP, auction, abandoned — against one hardcoded 10-team PPR board. At the 149-
    draft corpus that was ~26 % contamination and survivable; after the F.5 expansion it is 74 %,
    and a 2QB room's pick order is not evidence about redraft PPR behaviour. This is the same
    format-contamination bug F.5 fixed on the ADP board path, in its second home; see
    :mod:`fantasy_quant.adp.boards` for why a board key is (season, scoring, teams).
    """
    drafts = eligible_drafts(con, seasons)
    if drafts.empty:
        return pd.DataFrame(columns=["group", "season", "draft_id", "board_source", "chosen",
                                     *ALL_FEATURES]), list(ALL_FEATURES)
    if max_drafts_per_season is not None:
        # An explicit, reported sampling budget — not a silent cap. Sampling is per season so the
        # walk-forward keeps every held-out season; `seed` makes the draw reproducible.
        keep = [g.sample(min(len(g), max_drafts_per_season), random_state=seed)
                for _s, g in drafts.groupby("season", sort=True)]
        drafts = pd.concat(keep, ignore_index=True)
    keys = list(zip(drafts["season"], drafts["ffc_scoring"], drafts["board_teams"], strict=False))
    resolved = resolve_boards(con, keys, allow_ecr=allow_ecr)

    board_cache: dict[tuple, tuple[pd.DataFrame, str]] = {}
    for key, (bd, src) in resolved.items():
        if bd.empty:
            continue
        bd = bd.copy()
        bd["pos"] = bd["position"].map(canon_pos)
        bd["adp"] = pd.to_numeric(bd["adp"], errors="coerce")
        bd = bd.dropna(subset=["pos", "adp"])
        if skill_only:  # candidates are skill players only (K/DST availability is trivially late)
            bd = bd[bd["pos"].isin(("QB", "RB", "WR", "TE"))]
        board_cache[key] = (bd.sort_values("adp").reset_index(drop=True), src)
    board_key_of = {
        str(d): (int(s), str(sc), int(t))
        for d, s, sc, t in zip(drafts["draft_id"], drafts["season"], drafts["ffc_scoring"],
                               drafts["board_teams"], strict=False)
    }

    # per-season rookie map (years_exp == 0 anywhere in the corpus that season)
    exp = con.execute(
        "SELECT season, gsis_id, MIN(years_exp) ye FROM sleeper_draft_picks "
        "WHERE gsis_id IS NOT NULL GROUP BY 1,2"
    ).df()
    rookie_set = set(zip(exp.loc[exp["ye"] == 0, "season"],
                         exp.loc[exp["ye"] == 0, "gsis_id"], strict=False))

    prof = _load_profiles(con)
    pos_mean = {}
    fav = {}
    prof_lean = {}
    if not prof.empty:
        for p in ("QB", "RB", "WR", "TE"):
            pos_mean[p] = float(prof[f"pos_share_{p}"].mean())
        for _, r in prof.iterrows():
            teams_list = r["fav_teams"]
            if isinstance(teams_list, str):    # stored comma-separated, e.g. "CLE,MIA,DET"
                teams_list = [t.strip() for t in teams_list.split(",") if t.strip()]
            fav[r["manager"]] = set(teams_list or [])
            prof_lean[r["manager"]] = {
                p: float(r[f"pos_share_{p}"]) - pos_mean.get(p, 0.0)
                for p in ("QB", "RB", "WR", "TE")
            }

    ids = drafts["draft_id"].astype(str).tolist()
    ph = ",".join("?" * len(ids))
    picks = con.execute(
        f"""
        SELECT p.draft_id, p.season, p.pick_no, p.picked_by, p.gsis_id, p.position, p.nfl_team
        FROM sleeper_draft_picks p
        WHERE p.draft_id IN ({ph}) AND p.picked_by IS NOT NULL AND p.gsis_id IS NOT NULL
        ORDER BY p.draft_id, p.pick_no
        """,
        ids,
    ).df()
    picks["pos"] = picks["position"].map(canon_pos)
    if skill_only:
        picks = picks[picks["pos"].isin(("QB", "RB", "WR", "TE"))]

    # One draft contributes ~140 boarded picks x `top_k` candidates, so the full eligible corpus
    # is ~8M rows. Accumulated as Python tuples that does not fit in memory; rows are therefore
    # built as one typed block per draft and concatenated once, with draft_id / board_source held
    # as integer codes and rehydrated as categoricals at the end.
    blocks: list[np.ndarray] = []
    draft_codes: list[np.ndarray] = []
    src_codes: list[np.ndarray] = []
    draft_levels: list[str] = []
    src_levels: list[str] = []
    src_index: dict[str, int] = {}
    gid = 0
    for draft_id, dpicks in picks.groupby("draft_id", sort=False):
        season = int(dpicks["season"].iloc[0])
        cached = board_cache.get(board_key_of.get(str(draft_id), ()))
        if cached is None:
            continue                      # no consensus board published for this draft's cell
        bd, board_src = cached
        rows: list[tuple] = []
        if board_src not in src_index:
            src_index[board_src] = len(src_levels)
            src_levels.append(board_src)
        adp_map = dict(zip(bd["gsis_id"], bd["adp"], strict=False))
        pos_map = dict(zip(bd["gsis_id"], bd["pos"], strict=False))
        team_map = dict(zip(bd["gsis_id"], bd["team"], strict=False))
        board_ids = bd["gsis_id"].to_numpy()
        board_adp = bd["adp"].to_numpy()

        taken: set[str] = set()
        mgr_counts: dict[str, dict[str, int]] = {}
        recent_pos: list[str] = []
        dpicks = dpicks.sort_values("pick_no")
        for _, pk in dpicks.iterrows():
            chosen_id = pk["gsis_id"]
            mgr = pk["picked_by"]
            # candidate universe: top_k still-available by ADP (must include the realized pick)
            avail_mask = ~np.isin(board_ids, list(taken))
            av_ids = board_ids[avail_mask]
            av_adp = board_adp[avail_mask]
            order = np.argsort(av_adp)
            cand_ids = av_ids[order][:top_k]
            if chosen_id in adp_map and chosen_id not in cand_ids:
                cand_ids = np.append(cand_ids, chosen_id)   # keep a rare deep reach in-set
            if chosen_id not in adp_map:
                # picked player not on the consensus board — can't score; still advance state
                taken.add(chosen_id)
                recent_pos.append(pk["pos"])
                recent_pos[:] = recent_pos[-_RUN_WINDOW:]
                mgr_counts.setdefault(mgr, {}).__setitem__(
                    pk["pos"], mgr_counts.get(mgr, {}).get(pk["pos"], 0) + 1)
                continue

            lean = prof_lean.get(mgr, {})
            mc = mgr_counts.get(mgr, {})
            favset = fav.get(mgr, set())
            for cid in cand_ids:
                cpos = pos_map.get(cid)
                if cpos is None:
                    continue
                capp = adp_map[cid]
                rows.append((
                    gid, season, int(cid == chosen_id),
                    capp / _ADP_SCALE,                                     # adp_s
                    1.0 if cpos == "RB" else 0.0,
                    1.0 if cpos == "WR" else 0.0,
                    1.0 if cpos == "TE" else 0.0,
                    1.0 if cpos == "QB" else 0.0,
                    float(sum(1 for p in recent_pos if p == cpos)),        # pos_run3
                    lean.get(cpos, 0.0),                                    # mgr_lean
                    1.0 if (season, cid) in rookie_set else 0.0,            # rookie
                    1.0 if team_map.get(cid) in favset else 0.0,           # fandom
                    max(0.0, _NEED_TARGET.get(cpos, 0) - mc.get(cpos, 0)), # need (unmet demand)
                ))
            gid += 1
            taken.add(chosen_id)
            recent_pos.append(pk["pos"])
            recent_pos[:] = recent_pos[-_RUN_WINDOW:]
            mgr_counts.setdefault(mgr, {})
            mgr_counts[mgr][pk["pos"]] = mgr_counts[mgr].get(pk["pos"], 0) + 1

        if rows:
            blk = np.asarray(rows, dtype=np.float32)
            blocks.append(blk)
            draft_codes.append(np.full(len(blk), len(draft_levels), dtype=np.int32))
            src_codes.append(np.full(len(blk), src_index[board_src], dtype=np.int8))
            draft_levels.append(str(draft_id))

    num_cols = ["group", "season", "chosen", *ALL_FEATURES]
    if not blocks:
        return (pd.DataFrame(columns=["group", "season", "draft_id", "board_source", "chosen",
                                      *ALL_FEATURES]), list(ALL_FEATURES))
    arr = np.concatenate(blocks)
    del blocks
    frame = pd.DataFrame(arr, columns=num_cols)
    frame["group"] = frame["group"].astype(np.int32)
    frame["season"] = frame["season"].astype(np.int16)
    frame["chosen"] = frame["chosen"].astype(np.int8)
    frame["draft_id"] = pd.Categorical.from_codes(np.concatenate(draft_codes), draft_levels)
    frame["board_source"] = pd.Categorical.from_codes(np.concatenate(src_codes), src_levels)
    cols = ["group", "season", "draft_id", "board_source", "chosen", *ALL_FEATURES]
    return frame[cols], list(ALL_FEATURES)


def corpus_funnel(con, seasons: Iterable[int] | None = None,
                  *, allow_ecr: bool = True) -> dict:
    """How the raw human corpus narrows to the drafts the behavioral model may learn from.

    Reported rather than assumed: the gap between "human drafts we hold" and "human *redraft*
    drafts with a board" is the whole substance of the F.5/F.6 contamination lesson.
    """
    raw = int(con.execute("SELECT count(*) FROM sleeper_drafts WHERE is_human").fetchone()[0])
    drafts = eligible_drafts(con, seasons)
    if drafts.empty:
        return {"human_drafts": raw, "eligible": 0, "with_board": 0, "by_board_source": {}}
    keys = list(zip(drafts["season"], drafts["ffc_scoring"], drafts["board_teams"], strict=False))
    resolved = resolve_boards(con, keys, allow_ecr=allow_ecr)
    src_of = {k: s for k, (b, s) in resolved.items() if not b.empty}
    got = [src_of.get((int(s), str(sc), int(t)), "")
           for s, sc, t in zip(drafts["season"], drafts["ffc_scoring"], drafts["board_teams"],
                               strict=False)]
    by_src: dict[str, int] = {}
    for s in got:
        if s:
            by_src[s] = by_src.get(s, 0) + 1
    return {"human_drafts": raw, "eligible": int(len(drafts)),
            "with_board": int(sum(1 for s in got if s)), "by_board_source": by_src}


# =============================================================================================
# grouped-softmax conditional logit
# =============================================================================================
def _group_ptr(groups: np.ndarray) -> np.ndarray:
    """Boundaries of contiguous groups in a group-sorted array -> (G+1,) index pointer."""
    change = np.flatnonzero(np.diff(groups)) + 1
    return np.concatenate(([0], change, [len(groups)]))


def _softmax_by_group(u: np.ndarray, ptr: np.ndarray):
    """Vectorized per-group softmax + log-sum-exp. Requires `u` laid out group-contiguous."""
    starts = ptr[:-1]
    counts = np.diff(ptr)
    gmax = np.maximum.reduceat(u, starts)
    ex = np.exp(u - np.repeat(gmax, counts))
    Z = np.add.reduceat(ex, starts)
    soft = ex / np.repeat(Z, counts)
    lse = np.log(Z) + gmax
    return soft, lse


@dataclass
class OpponentModel:
    """A fitted conditional-logit opponent model. ``beta`` aligns with ``feature_cols``."""
    feature_cols: list[str]
    beta: np.ndarray | None = None
    l2: float = 1.0
    meta: dict = field(default_factory=dict)

    # -- fit ----------------------------------------------------------------------------------
    def fit(self, frame: pd.DataFrame) -> OpponentModel:
        f = frame.sort_values("group", kind="stable").reset_index(drop=True)
        X = f[self.feature_cols].to_numpy(float)
        y = f["chosen"].to_numpy(float)
        groups = f["group"].to_numpy()
        ptr = _group_ptr(groups)
        counts = np.diff(ptr)
        lam = self.l2

        def nll_grad(beta):
            u = X @ beta
            soft, lse = _softmax_by_group(u, ptr)
            # NLL = -sum(u[chosen]) + sum_g lse_g ; chosen is one-per-group
            nll = (-float((X[y == 1] @ beta).sum()) + float(lse.sum())
                   + 0.5 * lam * float(beta @ beta))
            grad = X.T @ (soft - y) + lam * beta
            return nll, grad

        from scipy.optimize import minimize
        b0 = np.zeros(X.shape[1])
        res = minimize(nll_grad, b0, jac=True, method="L-BFGS-B",
                       options={"maxiter": 500, "ftol": 1e-9})
        self.beta = res.x
        self.meta = {"n_groups": int(len(counts)), "n_rows": int(len(f)),
                     "converged": bool(res.success), "nll": float(res.fun)}
        return self

    # -- predict / score ----------------------------------------------------------------------
    def probs(self, frame: pd.DataFrame) -> np.ndarray:
        f = frame.sort_values("group", kind="stable").reset_index(drop=True)
        X = f[self.feature_cols].to_numpy(float)
        ptr = _group_ptr(f["group"].to_numpy())
        soft, _ = _softmax_by_group(X @ self.beta, ptr)
        # restore original row order
        soft_series = pd.Series(soft, index=f.index)
        return soft_series.reindex(range(len(frame))).to_numpy()

    def candidate_matrix(self, cand: pd.DataFrame, *, recent_pos=None, lean=None,
                         fav=None, need=None) -> np.ndarray:
        """The design matrix behind :meth:`candidate_utility`, columns in ``feature_cols`` order.

        Split out so hot loops can build it **once per context for a whole board** and then index
        rows, rather than re-deriving it from pandas at every simulated pick — every column here is
        row-wise, so ``candidate_matrix(board)[rows]`` equals
        ``candidate_matrix(board.iloc[rows])``. See
        :func:`~fantasy_quant.draft.availability.simulate_survival`, which relies on that identity.
        """
        recent_pos = recent_pos or {}
        pos = cand["pos"].to_numpy()
        team = cand["team"].to_numpy() if "team" in cand.columns else np.array([None] * len(cand))
        rk = cand["rookie"].to_numpy(float) if "rookie" in cand.columns else np.zeros(len(cand))
        cols = {
            "adp_s": cand["adp"].to_numpy(float) / _ADP_SCALE,
            "is_RB": (pos == "RB").astype(float), "is_WR": (pos == "WR").astype(float),
            "is_TE": (pos == "TE").astype(float), "is_QB": (pos == "QB").astype(float),
            "pos_run3": np.array([recent_pos.get(p, 0) for p in pos], float),
            "mgr_lean": np.array([(lean or {}).get(p, 0.0) for p in pos], float),
            "rookie": rk,
            "fandom": np.array([1.0 if (fav and t in fav) else 0.0 for t in team], float),
            "need": np.array([(need or {}).get(p, 0.0) for p in pos], float),
        }
        return np.column_stack([cols[c] for c in self.feature_cols])

    def candidate_utility(self, cand: pd.DataFrame, *, recent_pos=None, lean=None,
                          fav=None, need=None) -> np.ndarray:
        """Utility (Xβ) for a set of live candidates — the portable path used by availability
        simulation (11.2) and mock opponents (11.3). ``cand`` needs ``adp``, ``pos`` and
        optionally ``team``/``rookie``; the Tier-B context (``recent_pos`` positional-run counts,
        manager ``lean``/``fav``/``need``) defaults to neutral (0) when unknown, which is the exact
        "no information on this term" marginalization. Only ``feature_cols`` are used, so an
        ADP-only model ignores everything but ``adp``."""
        return self.candidate_matrix(cand, recent_pos=recent_pos, lean=lean, fav=fav,
                                     need=need) @ self.beta

    def score(self, frame: pd.DataFrame) -> dict:
        """Held-out fit quality: log-loss, multiclass Brier, top-1 accuracy, mean realized rank."""
        f = frame.sort_values("group", kind="stable").reset_index(drop=True)
        X = f[self.feature_cols].to_numpy(float)
        y = f["chosen"].to_numpy(float)
        ptr = _group_ptr(f["group"].to_numpy())
        soft, _ = _softmax_by_group(X @ self.beta, ptr)
        starts, counts = ptr[:-1], np.diff(ptr)
        p_chosen = soft[y == 1]
        logloss = float(-np.log(np.clip(p_chosen, 1e-12, 1)).mean())
        # multiclass Brier per group: sum_c (p_c - 1{c=chosen})^2, averaged over groups
        brier_rows = (soft - y) ** 2
        brier = float(np.add.reduceat(brier_rows, starts).mean())
        top1 = float((np.maximum.reduceat(soft, starts) == p_chosen).mean())
        # rank of the chosen (1 = model's top choice)
        ranks = []
        for s, c in zip(starts, counts, strict=False):
            sg = soft[s:s + c]
            yc = y[s:s + c]
            chosen_p = sg[yc == 1][0]
            ranks.append(int((sg > chosen_p).sum()) + 1)
        return {"logloss": logloss, "brier": brier, "top1_acc": top1,
                "mean_rank": float(np.mean(ranks)), "n_groups": int(len(counts))}


# =============================================================================================
# walk-forward evaluation (11.1 done-when)
# =============================================================================================
def walk_forward(frame: pd.DataFrame, feature_cols: list[str], *, l2: float = 1.0,
                 baseline_cols: list[str] | None = None, n_boot: int = 400,
                 seed: int = 0) -> dict:
    """Leave-one-season-out: fit on the other seasons, score the held-out season. Compares the
    full behavioral model to the ADP-only baseline and bootstraps the pooled log-loss gain
    (resampling held-out groups) for a CI. Returns per-season rows + the pooled verdict.
    """
    baseline_cols = list(ADP_ONLY) if baseline_cols is None else baseline_cols
    seasons = sorted(frame["season"].unique())
    per_season = []
    # accumulate per-group held-out chosen-prob for the pooled bootstrap
    beh_lp, base_lp, beh_br, base_br = [], [], [], []
    rng = np.random.default_rng(seed)
    for s in seasons:
        tr = frame[frame["season"] != s]
        te = frame[frame["season"] == s]
        if te["group"].nunique() < 5 or tr["group"].nunique() < 20:
            continue
        beh = OpponentModel(list(feature_cols), l2=l2).fit(tr)
        base = OpponentModel(list(baseline_cols), l2=l2).fit(tr)
        sb, sbase = beh.score(te), base.score(te)
        per_season.append({"season": int(s), "n_groups": sb["n_groups"],
                           "beh_logloss": sb["logloss"], "base_logloss": sbase["logloss"],
                           "beh_brier": sb["brier"], "base_brier": sbase["brier"],
                           "beh_top1": sb["top1_acc"], "base_top1": sbase["top1_acc"],
                           "beh_rank": sb["mean_rank"], "base_rank": sbase["mean_rank"]})
        # per-group chosen probs for pooled CI
        for mdl, lp, br in ((beh, beh_lp, beh_br), (base, base_lp, base_br)):
            fte = te.sort_values("group", kind="stable").reset_index(drop=True)
            X = fte[mdl.feature_cols].to_numpy(float)
            y = fte["chosen"].to_numpy(float)
            ptr = _group_ptr(fte["group"].to_numpy())
            soft, _ = _softmax_by_group(X @ mdl.beta, ptr)
            starts = ptr[:-1]
            lp.extend((-np.log(np.clip(soft[y == 1], 1e-12, 1))).tolist())
            br.extend(np.add.reduceat((soft - y) ** 2, starts).tolist())

    beh_lp = np.array(beh_lp)
    base_lp = np.array(base_lp)
    beh_br = np.array(beh_br)
    base_br = np.array(base_br)
    d_ll = base_lp - beh_lp          # >0 = behavioral better (lower log-loss)
    d_br = base_br - beh_br
    n = len(d_ll)
    boot_ll = np.array([d_ll[rng.integers(0, n, n)].mean() for _ in range(n_boot)])
    boot_br = np.array([d_br[rng.integers(0, n, n)].mean() for _ in range(n_boot)])
    pooled = {
        "n_groups": int(n),
        "beh_logloss": float(beh_lp.mean()), "base_logloss": float(base_lp.mean()),
        "logloss_gain": float(d_ll.mean()),
        "logloss_gain_ci": [float(np.percentile(boot_ll, 2.5)),
                            float(np.percentile(boot_ll, 97.5))],
        "beh_brier": float(beh_br.mean()), "base_brier": float(base_br.mean()),
        "brier_gain": float(d_br.mean()),
        "brier_gain_ci": [float(np.percentile(boot_br, 2.5)), float(np.percentile(boot_br, 97.5))],
    }
    pooled["beats_adp"] = bool(pooled["logloss_gain_ci"][0] > 0)
    return {"per_season": per_season, "pooled": pooled}
