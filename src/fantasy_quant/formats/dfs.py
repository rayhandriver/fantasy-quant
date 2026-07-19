"""Phase 15.3 — DFS GPP (salary cap · modeled ownership · leverage · field-relative scoring).

Daily fantasy is a different game from season-long: a single-slate, salary-capped lineup entered
against a
large field with a **top-heavy** payout. Two forces the season-long engine doesn't have:

* **Ownership + leverage.** In a big GPP you win by being *different and right*. The chalk (the best
  points-per-dollar plays) is rostered by most of the field, so even a high-scoring chalk lineup is
  duplicated and splits the prize; a lineup that leans on **low-owned** players is unique when they
  hit.
  Leverage = projection weighted *against* ownership.
* **Field-relative, convex payoff.** Payout is a steep function of finish rank — first place pays
orders of
  magnitude more than the min-cash. Under that convexity a higher-*ceiling*
  (higher-variance-of-finish)
  lineup has more EV than a safe one with the same mean, even though it "loses" most weeks — the DFS
  analog of the best-ball convexity (15.2), now over finish *rank* instead of weekly points.

**Data caveat (honest, per the free-data constraint).** There is **no free DraftKings/FanDuel
salary or
ownership feed** (the same gap that shelved props). So salaries are **synthesised** monotone in
projection
(as real DFS pricing largely is) and ownership is **modeled** from points-per-dollar. This module
therefore
delivers the *mechanics* — a salary-cap optimizer, a leverage objective, and a GPP field sim — and
shows
leverage beats chalk under them; it is **not** Brier-validated against a real slate, and says so.
Wire a
real salaries/ownership source (a DFS API) and the same kernels become validatable.

Done-bar (:func:`gpp_skill`): a leverage-aware lineup beats the chalk (projection-max) lineup on
expected
tournament payout, entered into the same simulated field over many correlated-weekly-outcome
contests.
"""

from __future__ import annotations

import numpy as np

from fantasy_quant.backtest.scoring import RuleSet
from fantasy_quant.draft.simulator import RosterSlots
from fantasy_quant.inseason.lineup import _slot_plan
from fantasy_quant.simulation.weekly import OFFENSE, build_weekly_model

# a classic offense-only DFS lineup (single entry, no bench): 1QB/2RB/3WR/1TE/1FLEX = 8.
DFS_SLOTS = RosterSlots(qb=1, rb=2, wr=3, te=1, flex=1, k=0, dst=0, bench=0,
                        pos_caps={"QB": 1, "RB": 3, "WR": 4, "TE": 2})
SALARY_CAP = 50000.0
SALARY_BASE = 1000.0          # a min-priced player floor
SALARY_PER_POINT = 520.0      # $ per projected *weekly* point (tuned so the cap binds — an
# unconstrained projection-max lineup runs ~$68k, forcing studs-plus-punts trade-offs)
OWN_TEMP = 5.0                # ownership softmax temperature over projection (lower = chalkier)
LEVERAGE_LAMBDA = 0.8         # how hard the leverage objective fades owned players


# ------------------------------------------------------------------------------------------------
# pure kernels: synthetic pricing, modeled ownership, leverage, the cap optimizer
# ------------------------------------------------------------------------------------------------
def synthetic_salaries(proj, *, base: float = SALARY_BASE, per_point: float = SALARY_PER_POINT,
                       cap: float = SALARY_CAP) -> np.ndarray:
    """Synthetic DFS salaries, monotone in projection (as real pricing largely is): ``base +
    per_point·proj``, rounded to $100 and clipped to ``[base, cap]``. **Modeled, not real** — no
    free
    salary feed exists (module docstring)."""
    proj = np.asarray(proj, float)
    sal = base + per_point * np.clip(proj, 0.0, None)
    return np.clip(np.round(sal / 100.0) * 100.0, base, cap)


def modeled_ownership(proj, salary, positions, *, temp: float = OWN_TEMP) -> np.ndarray:
    """Modeled field ownership fraction per player: a per-position softmax of **projection** — the
    field
    chases points, so the studs the projection-max (chalk) lineup selects are the most-owned. Scaled
    within position by the slot demand and capped at 60%. **Modeled, not real** — no ownership feed
    exists (module docstring); ``salary`` is accepted for signature symmetry / future value-based
    tweaks. This projection-driven shape is what creates leverage: chalk is high-owned and
    duplicated;
    a contrarian lineup that fades it is unique."""
    proj = np.asarray(proj, float)
    pos = np.asarray(list(positions))
    own = np.zeros(len(proj))
    demand = {"QB": 1, "RB": 2.5, "WR": 3.5, "TE": 1, "K": 0, "DST": 0}   # ~slots incl FLEX share
    for p in np.unique(pos):
        m = pos == p
        w = np.exp((proj[m] - proj[m].max()) / max(temp, 1e-6))
        share = w / w.sum() if w.sum() > 0 else w
        own[m] = np.clip(share * demand.get(str(p), 1), 0.0, 0.6)          # cap any one play at 60%
    return own


def leverage_score(proj, ownership, lam: float = LEVERAGE_LAMBDA) -> np.ndarray:
    """The GPP objective: ``proj·(1 − λ·ownership)`` — projection faded by how chalky the play is,
    so a
    low-owned player at a given projection is preferred (uniqueness when he hits). Pure."""
    return np.asarray(proj, float) * (1.0 - lam * np.asarray(ownership, float))


def optimize_lineup(score, salary, positions, slots: RosterSlots, *, cap: float = SALARY_CAP,
                    exclude=frozenset()) -> list[int]:
    """A salary-cap lineup maximising total ``score``: greedy score-max per slot, then **repair to
    the
    cap** by repeatedly swapping the player whose downgrade to a cheaper same-position alternative
    saves
    the most salary per point lost (until under the cap). Always cap-feasible and near-optimal for
    projection-monotone salaries. Fills dedicated slots then FLEX (the shared slot convention);
    returns
    player indices."""
    score = np.asarray(score, float)
    salary = np.asarray(salary, float)
    pos = np.asarray(list(positions))
    n = len(score)
    used = set(exclude)
    chosen: list[list] = []                                 # [allowed_positions, player_idx]
    for _label, allowed in _slot_plan(slots):
        elig = [j for j in range(n) if j not in used and pos[j] in allowed]
        if not elig:
            continue
        pick = max(elig, key=lambda j: score[j])
        used.add(pick)
        chosen.append([allowed, pick])

    guard = 0
    while sum(salary[p] for _, p in chosen) > cap and guard < 500:
        guard += 1
        cur = {p for _, p in chosen}
        best = None                                     # (saved_per_lost, slot_idx, alt_idx)
        for i, (allowed, p) in enumerate(chosen):
            alts = [j for j in range(n)
                    if j not in cur and pos[j] in allowed and salary[j] < salary[p]]
            if not alts:
                continue
            alt = min(alts, key=lambda j: salary[j])        # cheapest legal replacement
            saved, lost = salary[p] - salary[alt], score[p] - score[alt]
            key = saved / max(lost, 1e-6)
            if best is None or key > best[0]:
                best = (key, i, alt)
        if best is None:
            break
        chosen[best[1]][1] = best[2]
    return [p for _, p in chosen]


# ------------------------------------------------------------------------------------------------
# the done-bar: a leverage lineup beats the chalk lineup on GPP payout, in a simulated field
# ------------------------------------------------------------------------------------------------
def _payout_curve(field_size: int) -> np.ndarray:
    """A top-heavy GPP payout by 1-indexed finish rank (winner-take-most): rank 1 huge, a thin cash
    line,
    then nothing — the convexity that rewards ceiling."""
    pay = np.zeros(field_size + 2)
    pay[1] = 100.0
    top1 = max(1, field_size // 100)
    top10 = max(1, field_size // 10)
    pay[2:top1 + 1] = 20.0
    pay[top1 + 1:top10 + 1] = 3.0
    return pay


def _lineup_world_scores(lineups, player_world) -> np.ndarray:
    """``(n_lineups, n_worlds)`` total points: each lineup's players summed in each world."""
    return np.stack([player_world[lu].sum(axis=0) for lu in lineups])


def _entry_payout(entry_scores, entry_lineup, field_scores, field_lineups, pay) -> np.ndarray:
    """Per-world payout for one entry, **splitting the prize among identical duplicate lineups** —
    the
    load-bearing GPP mechanic. rank = 1 + (# field lineups strictly outscoring the entry this
    world);
    duplicity = 1 + (# field lineups *identical* to the entry, who tie it every world and share its
    prize). A duplicated chalk lineup at rank 1 splits first place many ways; a unique contrarian
    keeps
    it. Returns ``pay[rank] / duplicity`` per world."""
    entry_set = frozenset(entry_lineup)
    dup = 1 + sum(frozenset(lu) == entry_set for lu in field_lineups)
    ranks = 1 + (field_scores > entry_scores[None, :]).sum(axis=0)
    fs = field_scores.shape[0]
    return pay[np.clip(ranks, 1, fs)] / dup


def gpp_skill(con, season: int, *, n_contests: int = 4000, field_size: int = 200,
              pool_size: int = 100, lam: float = LEVERAGE_LAMBDA, field_noise: float = 0.22,
              chalk_frac: float = 0.4, ruleset: RuleSet | None = None,
              slots: RosterSlots | None = None, n_draws: int = 800, seed: int = 0) -> dict:
    """Walk-forward mechanics check: does a leverage lineup beat the chalk lineup on GPP payout?

    Builds the season's Σ-correlated ``WeeklyModel``, a top-``pool_size`` offense pool, synthetic
    salaries + modeled ownership, and two entries: **chalk** (projection-max under the cap) and
    **leverage** (:func:`leverage_score`-max — fades the high-owned studs). The **field** duplicates
    chalk the way a real GPP field does: a ``chalk_frac`` share are *exactly* the chalk lineup, the
    rest
    are projection-max on noised projections. Over ``n_contests`` correlated-weekly worlds every
    lineup is
    scored and each entry's payout is computed with **prize-splitting among its duplicates**
    (:func:`_entry_payout`). Verdict = the leverage entry's mean payout beats the chalk entry's,
    because
    chalk splits its top finishes with the field while the contrarian keeps them. **Modeled
    salaries/ownership → mechanics, not a Brier-validated fit** (module docstring). PIT; lockbox
    unread.
    """
    slots = slots or DFS_SLOTS
    model = build_weekly_model(con, season, ruleset, n_draws=n_draws, seed=seed)
    s = model.summary
    s = s[s["pos"].isin(OFFENSE)].sort_values("mean", ascending=False).head(pool_size).reset_index(
        drop=True)
    # DFS is a single slate: price/own on the *weekly* projection (season mean ÷ active weeks),
    # while the
    # world scores below are single-week draws — both on the same per-week scale.
    proj = s["mean"].to_numpy(float) / 16.0
    pos = s["pos"].to_numpy()
    keys = s["player_key"].to_numpy()
    salary = synthetic_salaries(proj)
    own = modeled_ownership(proj, salary, pos)
    lev = leverage_score(proj, own, lam)

    chalk = optimize_lineup(proj, salary, pos, slots)
    leverage = optimize_lineup(lev, salary, pos, slots)

    rng = np.random.default_rng(seed)
    n_chalk = int(round(chalk_frac * field_size))
    field = [list(chalk) for _ in range(n_chalk)]                     # the field folds to chalk
    for _ in range(field_size - n_chalk):
        noised = proj * rng.lognormal(0.0, field_noise, len(proj))
        field.append(optimize_lineup(noised, salary, pos, slots))

    # per-world player points: reshape the correlated weekly draws into (n_players,
    # n_draws·n_weeks).
    weekly = np.stack([model.player_weekly(k, p, np.arange(model.n_draws), rng)
                       for k, p in zip(keys, pos, strict=False)])      # (n_players, n_draws, n_wk)
    player_world = weekly.reshape(len(keys), -1)                       # (n_players, worlds)
    n_w = min(n_contests, player_world.shape[1])
    worlds = rng.choice(player_world.shape[1], n_w, replace=False)
    player_world = player_world[:, worlds]

    field_scores = _lineup_world_scores(field, player_world)               # (field_size, n_worlds)
    chalk_s = player_world[chalk].sum(axis=0)
    lev_s = player_world[leverage].sum(axis=0)
    pay = _payout_curve(field_size)

    chalk_world_pay = _entry_payout(chalk_s, chalk, field_scores, field, pay)
    lev_world_pay = _entry_payout(lev_s, leverage, field_scores, field, pay)
    diff = lev_world_pay - chalk_world_pay
    boot = diff[rng.integers(0, len(diff), (2000, len(diff)))].mean(axis=1)
    lo, hi = float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))
    return {
        "season": int(season), "field_size": int(field_size), "n_contests": int(len(worlds)),
        "chalk_dupes": int(sum(frozenset(lu) == frozenset(chalk) for lu in field)),
        "chalk_salary": float(salary[chalk].sum()),
        "leverage_salary": float(salary[leverage].sum()),
        "chalk_own": float(own[chalk].sum()), "leverage_own": float(own[leverage].sum()),
        "chalk_payout": float(chalk_world_pay.mean()),
        "leverage_payout": float(lev_world_pay.mean()),
        "payout_gain": float(diff.mean()), "payout_gain_ci": (lo, hi),
        "beats_chalk": bool(lo > 0.0),
    }
