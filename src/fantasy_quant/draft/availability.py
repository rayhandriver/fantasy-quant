"""Phase 11.2 — per-pick availability distributions (and the availability Brier).

The value the opponent model (11.1) buys the drafter is a better answer to *"will player p still
be on the board at my next pick?"* — the availability signal the personalization spine (S4) is
built on. This module turns the fitted :class:`~fantasy_quant.draft.opponent_model.OpponentModel`
into **survival probabilities** by Monte-Carlo simulating the intervening opponent picks, and
scores those survival forecasts against realized availability on the real Sleeper corpus — the
**availability Brier** owed since the MVP shipped with the crude ``survival_prob`` (ADP + Gaussian
noise) placeholder.

The comparison is apples-to-apples: on the same contested candidate band, in the same real draft
windows, behavioral-flow survival vs the incumbent ``survival_prob``. Lower Brier ⇒ the behavioral
model is a better availability oracle and earns promotion from opt-in to the S4 default.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fantasy_quant.adp.boards import resolve_boards
from fantasy_quant.adp.drift_panel import eligible_drafts
from fantasy_quant.draft.opponent_model import (
    CHOICE_TOP_K,
    RUN_WINDOW,
    _load_profiles,
    detect_run,
    run_bonus,
)
from fantasy_quant.draft.optimizer import DEFAULT_NOISE, survival_prob
from fantasy_quant.draft.simulator import canon_pos


def _softmax(u: np.ndarray) -> np.ndarray:
    u = u - u.max()
    e = np.exp(u)
    return e / e.sum()


def _draft_blocks(draft_of_win: np.ndarray) -> dict[int, np.ndarray]:
    """Row indices of ``draft_of_win`` grouped by draft, for the cluster bootstrap (T14).

    Equivalent to ``{u: np.flatnonzero(draft_of_win == u)}`` but computed in one sort rather than
    one full-array scan per draft per bootstrap replicate.
    """
    order = np.argsort(draft_of_win, kind="stable")
    sorted_dow = draft_of_win[order]
    uniq = np.unique(draft_of_win)
    lo = np.searchsorted(sorted_dow, uniq, side="left")
    hi = np.searchsorted(sorted_dow, uniq, side="right")
    return {int(u): order[a:b] for u, a, b in zip(uniq, lo, hi, strict=False)}


def simulate_survival(cand: pd.DataFrame, avail0: np.ndarray, seat_plan: list[dict],
                      model, *, n_sims: int, rng: np.random.Generator,
                      recent0: list | None = None,
                      top_k: int | None = CHOICE_TOP_K,
                      run_w: float = 0.0) -> np.ndarray:
    """MC survival of each ``cand`` row over a window of opponent picks.

    ``cand`` is a positional-index board (``adp``, ``pos``, optional ``team``/``rookie``);
    ``avail0`` marks who is available at the window start; ``seat_plan`` has one context dict per
    intervening opponent pick (``lean``/``fav``/``need`` for the manager on the clock, any of which
    may be absent → neutral). Returns P(available at window end) per row.

    ``top_k`` restricts each simulated pick to the top-``k`` **still-available players by ADP** —
    the candidate set the conditional logit was actually estimated on
    (:func:`~fantasy_quant.draft.opponent_model.build_choice_frame`, ``top_k=40``). A conditional
    logit's β is only interpretable relative to its choice set, so simulating over the whole board
    is applying the model outside its contract; ``top_k=None`` restores that (pre-Session-G)
    behaviour and is kept only for the comparison that measured the difference.

    ``run_w`` switches on the Phase-16.16 reactive run adjustment: each simulated pick re-reads the
    room's positional run intensity (:func:`~fantasy_quant.draft.opponent_model.detect_run`) and
    bumps candidates at a running position. ``run_w=0`` — the default — takes the identical code
    path as before, so the validated 11.2 forecast is unchanged unless a caller opts in.
    """
    m = len(cand)
    idx_all = np.arange(m)
    surv = np.zeros(m)
    pos_arr = cand["pos"].to_numpy()
    beta = model.beta
    # rank by ADP so "top_k available" is well-defined even if `cand` arrives unsorted
    adp_order = np.argsort(cand["adp"].to_numpy(float), kind="stable")
    adp_rank = np.empty(m, int)
    adp_rank[adp_order] = np.arange(m)

    # --- hoisted design matrices (T14) --------------------------------------------------------
    # The per-pick cost used to be `model.candidate_utility(cand.iloc[ai], ...)`, which re-sliced a
    # DataFrame and rebuilt every feature column from pandas at each of the ~13M simulated picks a
    # scaled 11.2 run makes. All of that is invariant across draws, so build **one design matrix per
    # seat context** up front and index rows instead. `pos_run3` is the only column that moves
    # within a draw (it counts the last <=3 picks), so it alone is overwritten in place.
    # Row-wise columns ⇒ X[ai] is exactly the matrix the old path built on `cand.iloc[ai]`, so the
    # utilities, the softmax, the RNG stream and hence the returned probabilities are unchanged.
    mats = [model.candidate_matrix(cand, lean=c.get("lean"), fav=c.get("fav"), need=c.get("need"))
            for c in seat_plan]
    run_col = model.feature_cols.index("pos_run3") if "pos_run3" in model.feature_cols else None
    pos_codes, pos_levels = pd.factorize(pos_arr)
    lvl_of = {p: i for i, p in enumerate(pos_levels)}
    # trailing slot stays 0 so an unfactorized position (code -1) contributes no run count
    counts = np.zeros(len(pos_levels) + 1)

    for _ in range(n_sims):
        avail = avail0.copy()
        recent = list(recent0 or [])
        for X in mats:
            ai = idx_all[avail]
            if ai.size == 0:
                break
            if top_k is not None and ai.size > top_k:
                ai = ai[np.argsort(adp_rank[ai], kind="stable")[:top_k]]
            if run_col is not None:
                counts[:] = 0.0
                for p in recent[-3:]:
                    j = lvl_of.get(p)
                    if j is not None:
                        counts[j] += 1.0
                X[:, run_col] = counts[pos_codes]
            u = X[ai] @ beta
            if run_w:
                # 16.16: intensity is measured against the *still-available* pool, so it reflects
                # the room's live supply/demand rather than a fixed prior.
                u = u + run_bonus(pos_arr[ai], detect_run(recent, pos_arr[ai]), run_w)
            choice = int(rng.choice(ai, p=_softmax(u)))
            avail[choice] = False
            recent.append(pos_arr[choice])
        surv += avail
    return surv / n_sims


# =============================================================================================
# availability Brier — behavioral flow vs the incumbent ADP+noise survival_prob
# =============================================================================================
_NEED_TARGET = {"QB": 1, "RB": 4, "WR": 4, "TE": 1}
_NOISE_GRID = (3.0, 5.0, 8.0, 12.0, 18.0, 26.0, 36.0)   # ADP+noise baseline tuned over this grid


def availability_brier(con, model, *, seasons=None, allow_ecr: bool = True,
                       n_sims: int = 60, contested_k: int = 30,
                       max_drafts_per_season: int = 8, noise: float = DEFAULT_NOISE,
                       n_boot: int = 400, seed: int = 0,
                       top_k: int | None = CHOICE_TOP_K,
                       run_w: float = 0.0, require_run: float | None = None) -> dict:
    """Score availability forecasts on real draft windows. For every seat's consecutive pick pair
    in a sample of human drafts, predict P(available at the seat's next pick) for the contested
    band (the ``contested_k`` lowest-ADP available players) under (a) the behavioral flow and
    (b) ``survival_prob`` (ADP+noise), and Brier-score both against realized availability.
    Bootstraps the per-window Brier difference for a CI.

    Draws from the same eligible-redraft corpus as
    :func:`~fantasy_quant.draft.opponent_model.build_choice_frame`, each draft against its own
    (season, scoring, teams) board — see :mod:`fantasy_quant.adp.boards`. ``max_drafts_per_season``
    is the sampling budget, and it, not the corpus, is what held the reported ``n_drafts`` to 21
    through Session F.5.

    Phase 16.16 adds two optional knobs, both inert at their defaults so the validated 11.2 number
    is reproduced exactly: ``run_w`` makes the simulated flow react to positional runs, and
    ``require_run`` restricts scoring to windows that **open during a run** (max positional
    intensity at the window start ≥ the threshold). Those are the windows where a reactive model
    can differ from a static one at all, so scoring everything would dilute the comparison to
    nothing — the same dilution 12.4 measured when an injury signal was judged leaguewide instead
    of on the designated subset.
    """
    rng = np.random.default_rng(seed)
    drafts = eligible_drafts(con, seasons)
    if drafts.empty:
        raise ValueError("no eligible redraft drafts in the corpus")
    keys = list(zip(drafts["season"], drafts["ffc_scoring"], drafts["board_teams"], strict=False))
    resolved = resolve_boards(con, keys, allow_ecr=allow_ecr)
    board_cache: dict[tuple, pd.DataFrame] = {}
    for key, (bd, _src) in resolved.items():
        if bd.empty:
            continue
        bd = bd.copy()
        bd["pos"] = bd["position"].map(canon_pos)
        bd["adp"] = pd.to_numeric(bd["adp"], errors="coerce")
        bd = bd.dropna(subset=["pos", "adp"])
        bd = bd[bd["pos"].isin(("QB", "RB", "WR", "TE"))]
        board_cache[key] = bd.sort_values("adp").reset_index(drop=True)
    board_key_of = {
        str(d): (int(s), str(sc), int(t))
        for d, s, sc, t in zip(drafts["draft_id"], drafts["season"], drafts["ffc_scoring"],
                               drafts["board_teams"], strict=False)
    }
    eligible_ids = [d for d in board_key_of if board_key_of[d] in board_cache]

    prof = _load_profiles(con)
    lean_by_mgr: dict = {}
    fav_by_mgr: dict = {}
    if not prof.empty:
        pos_mean = {p: float(prof[f"pos_share_{p}"].mean()) for p in ("QB", "RB", "WR", "TE")}
        for _, r in prof.iterrows():
            lean_by_mgr[r["manager"]] = {p: float(r[f"pos_share_{p}"]) - pos_mean[p]
                                         for p in ("QB", "RB", "WR", "TE")}
            fv = r["fav_teams"]
            fv = [t.strip() for t in fv.split(",")] if isinstance(fv, str) else list(fv or [])
            fav_by_mgr[r["manager"]] = set(fv)

    exp = con.execute("SELECT season, gsis_id, MIN(years_exp) ye FROM sleeper_draft_picks "
                      "WHERE gsis_id IS NOT NULL GROUP BY 1,2").df()
    rookie_set = set(zip(exp.loc[exp["ye"] == 0, "season"],
                         exp.loc[exp["ye"] == 0, "gsis_id"], strict=False))

    ph = ",".join("?" * len(eligible_ids))
    picks = con.execute(
        f"""SELECT p.draft_id, p.season, p.pick_no, p.picked_by, p.gsis_id, p.position
            FROM sleeper_draft_picks p
            WHERE p.draft_id IN ({ph}) AND p.picked_by IS NOT NULL AND p.gsis_id IS NOT NULL
            ORDER BY p.draft_id, p.pick_no""",
        eligible_ids,
    ).df()
    picks["pos"] = picks["position"].map(canon_pos)

    # sample drafts evenly across seasons
    chosen_drafts = []
    for _s, g in picks.groupby("season"):
        dids = [str(x) for x in g["draft_id"].unique()]
        rng.shuffle(dids)
        chosen_drafts.extend(dids[:max_drafts_per_season])

    beh_br, base_br, draft_of_win = [], [], []
    for di, draft_id in enumerate(chosen_drafts):
        dpicks = picks[picks["draft_id"] == draft_id].sort_values("pick_no")
        season = int(dpicks["season"].iloc[0])
        bd = board_cache[board_key_of[str(draft_id)]].copy()
        bd["rookie"] = [1.0 if (season, g) in rookie_set else 0.0 for g in bd["gsis_id"]]
        gsis_to_row = {g: i for i, g in enumerate(bd["gsis_id"])}
        pick_rows = dpicks[["pick_no", "picked_by", "gsis_id", "pos"]].to_records(index=False)
        # map each overall pick to the board row it removed (skip off-board picks)
        taken_at = {}
        for pr in pick_rows:
            if pr.gsis_id in gsis_to_row:
                taken_at[int(pr.pick_no)] = gsis_to_row[pr.gsis_id]
        seat_at = {int(pr.pick_no): pr.picked_by for pr in pick_rows}
        pos_at = {int(pr.pick_no): pr.pos for pr in pick_rows}

        # roster-so-far per manager (for `need`) is rebuilt incrementally below
        by_seat: dict = {}
        for pr in pick_rows:
            by_seat.setdefault(pr.picked_by, []).append(int(pr.pick_no))

        for _mgr, seat_picks in by_seat.items():
            seat_picks = sorted(seat_picks)
            for t1, t2 in zip(seat_picks, seat_picks[1:], strict=False):
                # available just after the focal pick at t1
                taken_before = {taken_at[p] for p in range(1, t1 + 1) if p in taken_at}
                avail0 = np.ones(len(bd), bool)
                for r in taken_before:
                    avail0[r] = False
                # contested band: lowest-ADP available rows
                avail_rows = np.flatnonzero(avail0)
                if avail_rows.size == 0:
                    continue
                order = np.argsort(bd["adp"].to_numpy()[avail_rows])
                contested = avail_rows[order][:contested_k]
                # realized: survived to t2 iff not removed by picks t1+1..t2-1
                removed_in_win = {taken_at[p] for p in range(t1 + 1, t2) if p in taken_at}
                realized = np.array([0.0 if r in removed_in_win else 1.0 for r in contested])

                # seat plan for intervening picks
                seat_plan = []
                for p in range(t1 + 1, t2):
                    m2 = seat_at.get(p)
                    roster_pos = [pos_at[q] for q in by_seat.get(m2, []) if q < p]
                    cnt = {}
                    for rp in roster_pos:
                        cnt[rp] = cnt.get(rp, 0) + 1
                    need = {pp: max(0.0, _NEED_TARGET.get(pp, 0) - cnt.get(pp, 0))
                            for pp in ("QB", "RB", "WR", "TE")}
                    seat_plan.append({"lean": lean_by_mgr.get(m2), "fav": fav_by_mgr.get(m2),
                                      "need": need})
                recent0 = [pos_at[p] for p in range(max(1, t1 - 2), t1 + 1) if p in pos_at]

                if require_run is not None:
                    # the run as it stands when the window OPENS — the only information a live
                    # drafter would actually have at that moment
                    look = [pos_at[p] for p in range(max(1, t1 - RUN_WINDOW + 1), t1 + 1)
                            if p in pos_at]
                    inten = detect_run(look, bd["pos"].to_numpy()[avail_rows])
                    if not inten or max(inten.values()) < require_run:
                        continue

                # behavioral survival (only need it for the contested rows)
                surv_full = simulate_survival(
                    bd, avail0, seat_plan, model, n_sims=n_sims, rng=rng, recent0=recent0,
                    top_k=top_k, run_w=run_w)
                p_beh = surv_full[contested]
                cadp = bd["adp"].to_numpy()[contested]
                beh_br.append(float(np.mean((p_beh - realized) ** 2)))
                # ADP+noise baseline over a NOISE GRID (fair: behavioral vs best-tuned baseline)
                base_br.append({
                    nz: float(np.mean((survival_prob(cadp, float(t2 - 1), nz) - realized) ** 2))
                    for nz in _NOISE_GRID})
                draft_of_win.append(di)

    if not beh_br:
        # the `require_run` filter can legitimately empty the sample on a small budget; say so
        # rather than dividing by zero and reporting a nan as if it were a measurement.
        return {"n_windows": 0, "n_drafts": 0, "require_run": require_run, "run_w": run_w}
    beh_br = np.array(beh_br)
    draft_of_win = np.array(draft_of_win)
    base_grid = {nz: np.array([b[nz] for b in base_br]) for nz in _NOISE_GRID}
    # pick the best-tuned noise (lowest mean Brier) as the honest baseline, plus keep default=5
    best_nz = min(_NOISE_GRID, key=lambda nz: base_grid[nz].mean())
    base_best = base_grid[best_nz]
    base_default = base_grid[noise] if noise in base_grid else base_grid[best_nz]
    d = base_best - beh_br            # >0 ⇒ behavioral beats the BEST-tuned ADP+noise
    uniq = np.unique(draft_of_win)
    # T14: index each draft's windows once, instead of rescanning the full window array per draft
    # per replicate (the old O(n_boot x n_drafts x n_windows) scan). Same draws, same statistic.
    blocks = _draft_blocks(draft_of_win)
    boots = []
    for _ in range(n_boot):
        pick = rng.choice(uniq, uniq.size, replace=True)
        mask = np.concatenate([blocks[int(u)] for u in pick])
        boots.append(d[mask].mean())
    boots = np.array(boots)
    return {
        "n_windows": int(len(d)), "n_drafts": int(uniq.size),
        "beh_brier": float(beh_br.mean()),
        "base_brier_default_noise5": float(base_default.mean()),
        "base_brier_best_tuned": float(base_best.mean()), "best_noise": float(best_nz),
        "brier_gain_vs_best": float(d.mean()),
        "brier_gain_ci": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
        "beats_best_adp_noise": bool(np.percentile(boots, 2.5) > 0),
        "run_w": float(run_w), "require_run": require_run,
    }
