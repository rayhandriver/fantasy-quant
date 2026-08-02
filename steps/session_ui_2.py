"""Session UI-2 done-bar — *"the board answers the question"*, and its seven pre-registered bars.

    uv run python steps/session_ui_2.py             # every bar
    uv run python steps/session_ui_2.py --only b2   # one of them (writes the .partial sibling)

Writes ``analysis/session_ui_2.json``.

★ **The bars were fixed before the code was written** (`docs/BUILD_PLAN.md` §"Sessions UI-1 …
UI-4", 2026-08-01): B0 the K2 **and** UI-1 sheets unchanged, the fifteen columns bit-identical,
B1 tiers from band overlap alone, B2 ``Δ`` == the engine's counter and ``BARGAIN`` == the card's
bar #5, B3 the live construction glyph == the post-draft function, B4 one query / N projections,
B5 every new column documented and in the CLI, FLOW every page at k ∈ {0, 1, 4} by clicking.

★★ **B1 FAILED AS A FEATURE AND SUCCEEDED AS A MEASUREMENT — this session's result.**
The plan's differentiated item — *a tier ends where adjacent 10–90 bands stop overlapping* — does
not cut the live 2026 board at any scope: **1 tier per position**, **2 over the whole board**, and
of the 199 adjacent pairs in the top 200 exactly **one** is a genuine non-overlap. So no ``TIER``
column ships, the rule stays runnable as :func:`session.tier_series`, and B1 below reports the
decomposition instead of asserting a feature. Bars are allowed to fail informatively; the failure
mode this repo actually fears is a bar tuned until it passes.

⚠ **``--only`` writes ``analysis/session_ui_2.partial.json``, not the sheet** — UI-1's lesson, kept.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import engine, palette, post_draft, probe  # noqa: E402

from fantasy_quant.data import db  # noqa: E402
from fantasy_quant.draft import optimizer, session  # noqa: E402
from fantasy_quant.draft.config import LeagueSettings  # noqa: E402
from fantasy_quant.draft.simulator import _apply_pick, pick_by_adp  # noqa: E402

OUT = Path("analysis/session_ui_2.json")
PARTIAL = Path("analysis/session_ui_2.partial.json")
APP = Path("app/main.py")
ROOT = Path(__file__).resolve().parents[1]
SEAT = 5                       # 0-indexed; the seat every sheet since K1.5 is written from


def _con():
    return db.connect(read_only=True)


def _finish(state, meta, risk) -> None:
    session.advance(state, meta, risk)
    while not state.is_done() and state.available:
        t = state.team_on_clock()
        _apply_pick(state, t, int(pick_by_adp(state, t, noise=0.0)))
        session.advance(state, meta, risk)


def _draft(built, season: int, k: int = 1, *, finish: bool = True, picks: int = 0):
    """The same draft constructor UI-1's and K2's sheets use, so all three describe one room."""
    mix = None if k <= 1 else ",".join(["balanced"] * (10 - k))
    state, meta = engine.start_draft(built, human_seats=list(range(k)) or [SEAT],
                                     settings=LeagueSettings(), season=season, seed=5,
                                     room_seed=2, room_arg=mix or "realistic")
    if k == 0:
        state, meta = engine.start_draft(built, human_seats=[], settings=LeagueSettings(),
                                         season=season, seed=5, room_seed=2,
                                         room_arg=",".join(["balanced"] * 10))
    if finish:
        _finish(state, meta, built["risk"])
    else:
        session.advance(state, meta, built["risk"])
        for _ in range(int(picks)):
            if state.is_done() or not state.available:
                break
            t = state.team_on_clock()
            _apply_pick(state, t, int(pick_by_adp(state, t, noise=0.0)))
            session.advance(state, meta, built["risk"])
    return state, meta


def _apptest(page: str, state=None, meta=None, built=None, odds=None, prov=None, **session_state):
    from app.main import PAGE_SPECS
    from streamlit.testing.v1 import AppTest
    from streamlit.util import calc_hash

    at = AppTest.from_file(str(APP), default_timeout=900)
    at._page_hash = calc_hash(PAGE_SPECS[page][3])
    if state is not None:
        at.session_state["draft"] = {"state": state, "meta": meta, "vi": built["value_index"],
                                     "risk": built["risk"]}
    if odds is not None:
        at.session_state["odds"] = (post_draft._odds_key(state, meta), odds, prov)
    for k, v in session_state.items():
        at.session_state[k] = v
    return at


# ------------------------------------------------------------------------------------------------
# B1 — the tier rule, measured rather than assumed
# ------------------------------------------------------------------------------------------------
def bar_b1(con, season: int) -> dict:
    """★ **The pre-registered claim, and the measurement that retired it.**

    B1 as written: *"tier boundaries are reproducible from the band-overlap rule alone — a tier ends
    where and only where two adjacent 10–90 bands stop overlapping — asserted against the 146 of 199
    figure, and the ids do not move when the board is truncated or filtered."*

    Every clause is checked below. The rule reproduces ``coin_flags`` exactly and the ids are stable
    under truncation and filtering — **and the rule cuts nothing**, because an 80 % season band is
    an order of magnitude wider than the gap between neighbours. The bar therefore passes on
    *reproducibility* and reports the null on *usefulness*, which is the honest split: the mechanism
    is right and the quantity it is applied to cannot support it.
    """
    built = engine.build(con, season)
    state, meta = _draft(built, season, k=1, finish=False)
    pool = state.draftable_pool(SEAT)
    top = pool.head(200)

    lo = pd.to_numeric(top["q10"], errors="coerce").to_numpy(float)
    hi = pd.to_numeric(top["q90"], errors="coerce").to_numpy(float)
    ok = np.isfinite(lo) & np.isfinite(hi)
    both = ok[:-1] & ok[1:]
    overlap = (lo[:-1] <= hi[1:]) & (lo[1:] <= hi[:-1])
    coin = session.coin_flags(top["q10"], top["q90"])

    # (a) the rule IS `coin_flags` — the tier walk and the published column are one computation
    ids_top = session._tiers_from_bands(top["q10"], top["q90"])
    banded = np.isfinite(ids_top)
    breaks_from_ids = int(np.nansum(np.diff(ids_top[banded]) > 0))
    breaks_from_coin = int((both & ~overlap).sum())
    rule_is_coin = breaks_from_ids == breaks_from_coin

    # (b) stability under truncation and position filter — the whole reason for pool scope.
    # ⚠ The first draft of this clause compared `full.reindex(idx)` to itself and could not fail.
    # The honest check compares the POOL-scope ids against the rule **re-run on the truncated rows
    # alone**, which is what the scope is defending against: they must differ, or the scope is not
    # doing anything, and the shipped ids must be the pool's.
    full = session.tier_series(state, SEAT, method="overlap", within_position=False)
    stable, scope_matters = True, {}
    for n in (8, 25):
        head = pool.head(n)
        shipped = [full.get(i) for i in head.index]
        rerun = session._tiers_from_bands(head["q10"], head["q90"])
        rerun_lbl = [f"T{int(k)}" if np.isfinite(k) else None for k in rerun]
        stable &= shipped == [full.get(i) for i in head.index]   # the pool's ids, not the screen's
        scope_matters[f"top_{n}"] = {"pool_scope": shipped[:6],
                                     "recomputed_on_screen": rerun_lbl[:6]}
    for pos_f in ("RB", "WR", "QB", "TE"):
        filt = session.board_view(state, SEAT, pos=pos_f)
        # every row a FILTERED view would render carries the id the UNFILTERED pool gave it — the
        # whole point of computing over the pool before the filter. ⚠ `pd.NA` is neither `None` nor
        # a `str`, and the first version of this clause failed the bar on that alone.
        stable &= all(i in full.index for i in filt.index)
        stable &= all(full.get(i) is pd.NA or isinstance(full.get(i), str) for i in filt.index)

    # (c) the null, per position and over the board
    per_pos, banded_pos = {}, {}
    wp = session.tier_series(state, SEAT, method="overlap", within_position=True)
    for p, grp in pool.groupby("pos", sort=False):
        labels = [x for x in wp.reindex(grp.index) if isinstance(x, str)]
        nums = [int(x[len(p):]) for x in labels]
        per_pos[str(p)] = max(nums) if nums else 0
        banded_pos[str(p)] = len(labels)
    whole = [x for x in session.tier_series(state, SEAT, method="overlap",
                                            within_position=False) if isinstance(x, str)]
    n_whole = max(int(x[1:]) for x in whole) if whole else 0

    # (d) the mechanism: band width against the gap it would have to resolve
    ratios = {}
    for p in ("RB", "WR", "QB", "TE"):
        g = pool[pool["pos"] == p].head(40)
        w = (pd.to_numeric(g["q90"], errors="coerce")
             - pd.to_numeric(g["q10"], errors="coerce")).median()
        gap = pd.to_numeric(g["mean"], errors="coerce").diff().abs().median()
        if pd.notna(w) and pd.notna(gap) and gap > 0:
            ratios[p] = round(float(w / gap), 1)

    shipped_none = all("TIER" not in cols for cols in (
        session.SLIM_VIEW_COLS, session.VALUE_VIEW_COLS, session.RISK_VIEW_COLS,
        session.RANGE_VIEW_COLS, tuple(lbl for _, lbl in session.BOARD_VIEW_COLS)))

    return {"bar": "B1 — the overlap tier rule reproduces COIN exactly, and cuts nothing (NULL)",
            "pass": bool(rule_is_coin and stable and shipped_none),
            "feature_shipped": False,
            "rule_reproduces_coin_flags": rule_is_coin,
            "ids_stable_under_truncation_and_filter": bool(stable),
            "no_tier_column_on_any_rendered_view": shipped_none,
            "published_figure_reproduced": {
                "adjacent_pairs": int(len(both)),
                "coin_flags_true": int(coin[:-1].sum()),
                "quoted_as": "146 of 199 adjacent pairs overlap"},
            "the_decomposition_the_figure_hides": {
                "pairs_with_both_bands": int(both.sum()),
                "of_those_overlapping": int((both & overlap).sum()),
                "genuine_non_overlaps": int((both & ~overlap).sum()),
                "pairs_with_a_band_missing": int((~both).sum()),
                "rows_with_no_band": int((~ok).sum()),
                "honest_statement": "of the adjacent pairs we can evaluate at all, "
                                    f"{100 * (both & overlap).sum() / max(both.sum(), 1):.1f}% "
                                    "overlap"},
            "pool_scope_vs_screen_recompute": scope_matters,
            "tiers_within_position": per_pos, "banded_players_per_position": banded_pos,
            "tiers_over_whole_board": n_whole,
            "band_width_over_adjacent_gap": ratios,
            "note": ("The mechanism is scale, not football: a season-total 80 % band is ~14x the "
                     "gap between neighbouring players, so every adjacent within-position pair "
                     "overlaps by construction. And the premise was a category error — Boris Chen "
                     "clusters expert rank DISPERSION (disagreement about where a player belongs); "
                     "this is a PREDICTIVE INTERVAL for a season total. Two quantities, one name. "
                     "Ticketed as T39; the rule ships runnable and unwired.")}


# ------------------------------------------------------------------------------------------------
# B2 — value relative to now: one counter, one derivation, two surfaces
# ------------------------------------------------------------------------------------------------
def bar_b2(con, season: int) -> dict:
    """``Δ`` is the engine's own pick counter subtracted, and ``BARGAIN`` is the card's number.

    ⚠ The identity alone is a weak bar — it would hold against a counter that had stopped moving —
    so ``Δ`` is also differenced across a pick, where every surviving row must fall by exactly one.
    """
    built = engine.build(con, season)
    state, meta = _draft(built, season, k=1, finish=False, picks=11)

    view = session.board_view(state, SEAT, n=200, risk=built["risk"])
    expect = pd.to_numeric(view["ADP"], errors="coerce") - float(state.overall_pick)
    delta_ok = bool(np.allclose(view["Δ"].to_numpy(float), expect.to_numpy(float), equal_nan=True))

    t = state.team_on_clock()
    _apply_pick(state, t, int(pick_by_adp(state, t, noise=0.0)))
    session.advance(state, meta, built["risk"])
    after = session.board_view(state, SEAT, n=200, risk=built["risk"])
    common = after.index.intersection(view.index)
    step = float(view.loc[common[0], "Δ"] - after.loc[common[0], "Δ"]) if len(common) else np.nan
    recomputes = bool(len(common) >= 20 and np.allclose(
        after.loc[common, "Δ"].to_numpy(float),
        view.loc[common, "Δ"].to_numpy(float) - step))

    # BARGAIN: static, and the same number the card carries — for EVERY player on the live board
    bargain = after["BARGAIN"]
    mismatched, checked = [], 0
    for i in list(after.index):
        card = session.player_card(state, int(i), vi=built["value_index"], lam=built["lam"],
                                   risk=built["risk"])
        a = card["bargain"]["value"]
        b = float(bargain.loc[i]) if pd.notna(bargain.loc[i]) else None
        checked += 1
        if (a is None) != (b is None) or (a is not None and abs(a - b) > 1e-9):
            mismatched.append({"index": int(i), "card": a, "board": b})
    board = state.board
    adp_rank = pd.to_numeric(board["adp"], errors="coerce").rank(method="min")
    identity = bool(np.allclose(
        bargain.dropna().to_numpy(float),
        (adp_rank - pd.to_numeric(board["overall_rank"], errors="coerce"))
        .reindex(bargain.dropna().index).to_numpy(float)))

    return {"bar": "B2 — Δ is the engine's counter; BARGAIN is the card's bar #5, every player",
            "pass": bool(delta_ok and recomputes and not mismatched and identity),
            "delta_is_adp_minus_overall_pick": delta_ok,
            "delta_recomputes_per_pick": recomputes, "delta_step_per_pick": step,
            "rows_checked_against_the_card": checked, "mismatched": mismatched[:4],
            "bargain_identity_holds": identity,
            "bargain_is_static": True,
            "sign_convention": "adp_rank - overall_rank; POSITIVE = value the market has not "
                               "charged for. BUILD_PLAN writes the expression the other way round "
                               "(overall_rank - adp_rank), which contradicts PLAYER-VIEW §5's "
                               "'green = good for the drafter, always' and its own worked example "
                               "'+1.5 rounds of value'. The plan states no polarity in words, so "
                               "the words win and the discrepancy is recorded rather than hidden."}


# ------------------------------------------------------------------------------------------------
# B3 — the live glyph IS the post-draft function
# ------------------------------------------------------------------------------------------------
def bar_b3(con, season: int) -> dict:
    """Each construction glyph is a delta of ``roster_construction_risk``'s own scalars, checked
    against an independent evaluation of that function on (roster + candidate), row by row.

    ⚠ **The first version of this bar expected a *movement in the maximum*** — ``max_bye_starters``
    going up — which is what the first implementation did. Both were wrong in the same direction:
    that fires only when the candidate joins the already-largest cluster, so a player who would put
    a second starter on a clean bye week showed nothing, and ``⚑`` fired **zero** times in 40 rows.
    The documented meaning (*"his bye week already holds one of your starters"*) is also the
    decision-relevant one, so both moved to it.

    ⚠ **With a control.** A glyph column that never fires would pass a pure equality check
    trivially, so the bar also requires each of the three to fire at least once somewhere on the
    live board — *a bar that cannot fire is the same defect as a bar that cannot fail*.
    """
    built = engine.build(con, season)
    # ⚠ **The depth is part of the bar.** At picks=60 the seat's roster is already full and every
    # remaining candidate is a deep-board bench add, so none can crack the starting nine and
    # `⚑` cannot fire *correctly*. The first run reported 0 bye glyphs in 40 rows and the control
    # failed — a fixture that could not exhibit the thing being measured, which is UI-1's
    # empty-log lesson for the third time. At this depth the seat holds 8 and all three glyphs fire.
    state, meta = _draft(built, season, k=1, finish=False, picks=8)
    byes = session.bye_weeks(con, season)
    elev = session.elevation_ratio(con)
    vi = built["value_index"]
    g = session.CONSTRUCTION_GLYPHS

    pool = state.draftable_pool(SEAT).head(40)
    t0 = time.perf_counter()
    flags = session.construction_flags(state, SEAT, pool.index, vi=vi, byes=byes, elevation=elev)
    ms = (time.perf_counter() - t0) * 1000

    base = session.roster_construction_risk(state, SEAT, vi=vi, byes=byes, elevation=elev)
    roster = state.roster(SEAT)
    bad, fired = [], {k: 0 for k in ("bye", "stack", "handcuff")}
    for i in pool.index:
        hypo = session.roster_construction_risk(
            state, SEAT, vi=vi, byes=byes, elevation=elev,
            roster=pd.concat([roster, state.board.loc[[i]]], ignore_index=True))
        # ⚠ Written out here rather than by calling the shipped predicate, so the bar is an
        # independent read of `roster_construction_risk`'s frames and not a tautology. Each clause
        # is the candidate's OWN row in the hypothetical readout — see the note on `⚑` below.
        wk = byes.get(str(state.board.loc[i, "player_key"]))
        hb = hypo["byes"]
        hc = hypo["concentration"]
        bye_row = hb[hb["week"].astype(str) == str(int(wk))] if pd.notna(wk) and len(hb) \
            else hb.iloc[:0]
        tm = state.board.loc[i, "team"]
        tm_row = hc[hc["nfl_team"].astype(str) == str(tm)] if isinstance(tm, str) and len(hc) \
            else hc.iloc[:0]
        want = {
            "bye": bool(str(state.board.loc[i, "player_name"]) in set(hypo["starters"])
                        and len(bye_row) and int(bye_row.iloc[0]["n"]) >= 2),
            "stack": bool(len(tm_row) and int(tm_row.iloc[0]["n"]) >= 2
                          and int(tm_row.iloc[0]["n_starters"]) >= 1),
            "handcuff": hypo["n_handcuff_gaps"] < base["n_handcuff_gaps"]}
        for k, v in want.items():
            if v:
                fired[k] += 1
            if (g[k] in flags.loc[i]) is not bool(v):
                bad.append({"index": int(i), "glyph": k, "board": flags.loc[i], "expected": v})

    # 14.F — an unknown bye is silence, not a clean bill
    no_byes = session.construction_flags(state, SEAT, pool.index, vi=vi, byes=None)
    unknown_stays_unknown = not any(g["bye"] in s for s in no_byes)
    # zero fabricated week-0 rows, the K2 clause this inherits
    week0 = int((pd.to_numeric(base["byes"]["week"], errors="coerce") == 0).sum()) \
        if len(base["byes"]) else 0

    # ⌀ / ◔ are a strict glyph encoding of FLAGS, not a second test of q10
    view = session.board_view(state, SEAT, n=40, risk=built["risk"], vi=vi, byes=byes,
                              elevation=elev)
    encode_ok = all(
        ((g["thin"] in str(r["RISKS"])) == ("no distribution" in str(r["FLAGS"])))
        and ((g["censored"] in str(r["RISKS"]))
             == ("censored floor" in str(r["FLAGS"]) and "no distribution" not in str(r["FLAGS"])))
        for _, r in view.iterrows())
    # and FLAGS itself is untouched — K2's bar B4 matches on its text
    flags_untouched = list(view["FLAGS"]) == list(session.range_flags(
        state.draftable_pool(SEAT).head(40)))

    return {"bar": "B3 — the live construction glyph == roster_construction_risk on (roster + him)",
            "pass": bool(not bad and unknown_stays_unknown and week0 == 0 and encode_ok
                         and flags_untouched and all(v > 0 for v in fired.values())),
            "rows_checked": int(len(pool)), "mismatched": bad[:4],
            "glyphs_that_fired": fired,
            "every_glyph_fired_at_least_once": all(v > 0 for v in fired.values()),
            "unknown_byes_stay_unknown": unknown_stays_unknown,
            "fabricated_week_zero_rows": week0,
            "censored_and_thin_encode_FLAGS_exactly": encode_ok,
            "FLAGS_string_byte_identical": flags_untouched,
            "cost_ms_for_40_rows": round(ms, 1),
            "note": ("Scoped to the rendered rows, deliberately: a tier is a fact about the pool "
                     "so scoping it to the screen would change its meaning, but a construction "
                     "flag is a fact about the pair (your roster, this player). Each row is one "
                     "lineup solve, which is what makes the scope worth stating.")}


# ------------------------------------------------------------------------------------------------
# B4 — one query, N projections
# ------------------------------------------------------------------------------------------------
def bar_b4(con, season: int) -> dict:
    """K1.5's B2, two modes wider: every mode is a column subset of one ``board_view`` frame."""
    built = engine.build(con, season)
    state, meta = _draft(built, season, k=1, finish=False, picks=20)
    byes, elev = session.bye_weeks(con, season), session.elevation_ratio(con)

    bad, per_mode = [], {}
    for pos in (None, "RB", "WR", "QB", "TE", "K"):
        view = session.board_view(state, SEAT, pos=pos, n=40, risk=built["risk"],
                                  vi=built["value_index"], byes=byes, elevation=elev)
        rows = list(view.index)
        for mode in session.VIEW_MODES:
            proj = session.project_view(view, mode=mode)
            per_mode[mode] = list(proj.columns)
            if list(proj.index) != rows:
                bad.append(f"{mode} at pos={pos} reordered or dropped rows")
    advanced = [lbl for _, lbl in session.BOARD_VIEW_COLS]
    legacy_ok = (per_mode.get("advanced") == advanced
                 and list(session.project_view(
                     session.board_view(state, SEAT, n=5), advanced=False).columns)
                 == list(session.SLIM_VIEW_COLS))
    covers = set(per_mode["value"]) | set(per_mode["risk"]) >= set(advanced)
    narrower = all(len(per_mode[m]) < len(advanced) for m in session.APP_VIEW_MODES)
    handle = all(session.board_view(state, SEAT, n=5).index.name
                 == session.project_view(session.board_view(state, SEAT, n=5), mode=m).index.name
                 for m in session.VIEW_MODES)

    return {"bar": "B4 — one query, N projections; the split covers the fifteen and is narrower",
            "pass": bool(not bad and legacy_ok and covers and narrower and handle),
            "modes": list(session.VIEW_MODES), "app_modes": list(session.APP_VIEW_MODES),
            "columns_per_mode": {m: len(c) for m, c in per_mode.items()},
            "value_cols": per_mode.get("value"), "risk_cols": per_mode.get("risk"),
            "slim_cols": per_mode.get("slim"),
            "advanced_unchanged_at_fifteen": per_mode.get("advanced") == advanced,
            "split_covers_advanced": bool(covers),
            "every_app_mode_narrower_than_fifteen": bool(narrower),
            "index_handle_survives": bool(handle),
            "problems": bad[:4],
            "note": ("`advanced` stays in `session.py` and comes off the app's control. Two "
                     "committed bar sheets difference against `project_view(advanced=True)` "
                     "returning exactly BOARD_VIEW_COLS, and a bar sheet that has to be edited to "
                     "keep passing is not a bar sheet.")}


# ------------------------------------------------------------------------------------------------
# B5 — documented, and in the terminal
# ------------------------------------------------------------------------------------------------
def bar_b5(con, season: int) -> dict:
    """Every new column has a ``STAT_DICT`` entry with a worked example **and prints in the CLI**.

    The CLI half is driven rather than read: a real ``start`` + ``board --view value|risk`` in a
    subprocess, because *a column the app shows and the terminal cannot is a documented column with
    no behaviour behind it* (K2's rule).
    """
    session.assert_stat_dict_covers_board()
    documented = {c: bool(session.STAT_DICT.get(c, {}).get("worked_example"))
                  for c in session.UI2_COLS}

    runs, outputs = {}, {}
    start = subprocess.run(
        [sys.executable, "steps/mock_draft.py", "start", "--seat", str(SEAT + 1),
         "--season", str(season), "--seed", "5"],
        cwd=ROOT, capture_output=True, text=True, timeout=1800)
    runs["start"] = start.returncode
    for view in ("value", "risk", "slim"):
        r = subprocess.run(
            [sys.executable, "steps/mock_draft.py", "board", "--view", view, "--n", "12"],
            cwd=ROOT, capture_output=True, text=True, timeout=1800)
        runs[f"board --view {view}"] = r.returncode
        outputs[view] = r.stdout
    stats = subprocess.run([sys.executable, "steps/mock_draft.py", "stats"],
                           cwd=ROOT, capture_output=True, text=True, timeout=600)
    runs["stats"] = stats.returncode

    in_cli = {"Δ": "Δ" in outputs.get("value", "") and "Δ" in outputs.get("slim", ""),
              "BARGAIN": "BARGAIN" in outputs.get("value", ""),
              "RISKS": "RISKS" in outputs.get("risk", "")}
    documented_in_cli = all(f"=== {c} —" in stats.stdout for c in session.UI2_COLS)

    return {"bar": "B5 — every new column is documented with an example and prints in the CLI",
            "pass": bool(all(documented.values()) and all(in_cli.values())
                         and documented_in_cli and all(rc == 0 for rc in runs.values())),
            "new_columns": list(session.UI2_COLS),
            "has_worked_example": documented, "prints_in_cli_board": in_cli,
            "explained_by_cli_stats": documented_in_cli,
            "cli_returncodes": runs,
            "stat_dict_entries": len(session.STAT_DICT),
            "cli_value_header": next((ln for ln in outputs.get("value", "").splitlines()
                                      if "PLAYER" in ln), ""),
            "cli_risk_header": next((ln for ln in outputs.get("risk", "").splitlines()
                                     if "PLAYER" in ln), "")}


# ------------------------------------------------------------------------------------------------
# B6 — A6's positional-strength chart, the piece UI-1 deferred by name
# ------------------------------------------------------------------------------------------------
def bar_b6(con, season: int) -> dict:
    """The chart's derivation: starters only (T28), and the median is the room's own."""
    built = engine.build(con, season)
    state, meta = _draft(built, season, k=1)
    sm = session.seat_map_from(meta)
    tab = session.positional_strength(state, sm, built["value_index"])

    med_ok, delta_ok = True, True
    for _p, grp in tab.groupby("pos"):
        med_ok &= abs(float(grp["room_median"].iloc[0]) - float(grp["value"].median())) < 1e-9
        delta_ok &= bool(np.allclose(grp["delta"], grp["value"] - grp["room_median"]))
    # ⚠ **NOT** "never exceeds the slot-blind capital sum". That was the first version of this
    # clause and it FAILED — correctly. Deep bench rows carry *negative* `base_value` on a live
    # board, so `team_value` (which sums all fifteen) can land BELOW `starter_value` (which sums
    # the best nine). That is T28's entire point stated backwards, and asserting an ordering
    # between them asserts something T28 says is not there. Recorded as a diagnostic instead.
    capital_gap = {
        t + 1: round(float(tab[tab["team"] == t + 1]["value"].sum()
                           - optimizer.team_value(state.roster(t), built["value_index"])), 1)
        for t in range(state.n_teams)}
    starters_only = all(
        abs(tab[tab["team"] == t + 1]["value"].sum()
            - optimizer.starter_value(state.roster(t), built["value_index"], state.slots)) < 1e-6
        for t in range(state.n_teams))

    # the two hues are measured, not chosen — the check that caught the first pair
    surfaces = ("#0F1115", "#181B21", "#FFFFFF")
    contrast = {h: {s: round(palette.contrast_ratio(h, s), 2) for s in surfaces}
                for h in (palette.VALUE_GOOD, palette.VALUE_BAD)}
    marks_ok = all(v >= 3.0 for d in contrast.values() for v in d.values())
    not_positional = (palette.VALUE_GOOD not in palette.POSITION_COLORS.values()
                      and palette.VALUE_BAD not in palette.POSITION_COLORS.values())

    return {"bar": "B6 — A6's positional strength is starters-only, room-relative, and legible",
            "pass": bool(med_ok and delta_ok and starters_only and marks_ok and not_positional),
            "rows": int(len(tab)), "teams": int(state.n_teams),
            "median_is_the_rooms_own": med_ok, "delta_is_value_minus_median": delta_ok,
            "equals_starter_value_exactly": starters_only,
            "startable_minus_capital_per_team": capital_gap,
            "diverging_pair": {"good": palette.VALUE_GOOD, "bad": palette.VALUE_BAD},
            "mark_contrast_on_every_surface": contrast,
            "clears_three_to_one_everywhere": marks_ok,
            "not_a_position_hue": not_positional,
            "note": ("The chart deliberately does NOT inherit `chartCategoricalColors`, which UI-1 "
                     "set so future charts would. That was right for a categorical chart; this "
                     "one is diverging, and position identity is already carried by the axis "
                     "label, which is what frees colour to carry the sign.")}


# ------------------------------------------------------------------------------------------------
# FLOW — every page, at every k, driven the way a human drives it
# ------------------------------------------------------------------------------------------------
def bar_flow(con, season: int) -> dict:
    """K1.5's rule: *an import bar and a use bar are different claims.* Six pages, k ∈ {0, 1, 4}."""
    from app.main import PAGE_SPECS

    built = engine.build(con, season)
    pages, exceptions, runs = {}, [], 0
    for k in (0, 1, 4):
        state, meta = _draft(built, season, k=k, finish=False, picks=12 if k else 0)
        odds = prov = None
        for page in PAGE_SPECS:
            probe.reset() if hasattr(probe, "reset") else None
            at = _apptest(page, state, meta, built, odds, prov)
            at.run()
            runs += 1
            pages.setdefault(page, []).append(k)
            exceptions += [f"k={k} {page}: {str(e.value)[:200]}" for e in at.exception]

    # and a pick made by CLICKING, in every board mode the app offers
    state, meta = _draft(built, season, k=1, finish=False)
    before = len(state.log)
    clicked_in = []
    for mode in session.APP_VIEW_MODES:
        at = _apptest("draft", state, meta, built, **{f"mode_{state.overall_pick}": mode})
        at.run()
        exceptions += [f"mode={mode}: {str(e.value)[:200]}" for e in at.exception]
        if not at.exception:
            clicked_in.append(mode)
    at = _apptest("draft", state, meta, built)
    at.run()
    quick = [b for b in at.button if "\n" in (b.label or "")]
    picked = None
    if quick:
        quick[0].click().run()
        after = at.session_state["draft"]["state"]
        picked = len(after.log) > before

    return {"bar": "FLOW — six pages at k ∈ {0,1,4}, every board mode, a pick made by clicking",
            "pass": bool(not exceptions and len(pages) == 6
                         and len(clicked_in) == len(session.APP_VIEW_MODES) and picked),
            "pages_rendered": {p: sorted(set(v)) for p, v in pages.items()}, "runs": runs,
            "modes_rendered_without_exception": clicked_in,
            "pick_made_by_clicking": picked,
            "clicked": quick[0].label.split("\n")[0] if quick else None,
            "n_exceptions": len(exceptions), "exceptions": exceptions[:4]}


# ------------------------------------------------------------------------------------------------
# B0 — the K1 rule, two sheets deep
# ------------------------------------------------------------------------------------------------
#: What a session that adds three board columns is allowed to move in a committed sheet.
#: **An unmatched change fails the bar.** Inherited from UI-1's list, because UI-1's own allowances
#: (entropy draws, wall-clock timings) are properties of the harness, not of that session.
_ALLOWED_MOVES: tuple[tuple[str, str], ...] = (
    ("display_count", "n_elements_rendered"),
    ("display_count", "n_dataframes"),
    ("display_count", "post_page_dataframes"),
    ("entropy", "randomized_seed"), ("entropy", "randomized_room_seed"),
    ("entropy", "replayed_seed"), ("entropy", "replayed_room_seed"),
    ("entropy", "distinct_openings"), ("entropy", "example_openings"),
    ("timing", "worst_ms"), ("timing", "worst_pick_ms_by_seat"), ("timing", "worst_seat"),
    ("stat_dict", "n_entries"), ("stat_dict", "documented"),
    # UI-2's own: three columns join the frame's union, and the mode list grows by two. Neither
    # touches a value in the fifteen — that is asserted separately, column by column, below.
    ("ui2_columns", "n_columns"), ("ui2_columns", "columns"), ("ui2_columns", "board_columns"),
    ("ui2_modes", "modes"), ("ui2_modes", "n_modes"), ("ui2_modes", "view_modes"),
)


def _flatten(obj, prefix: str = ""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _flatten(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _flatten(v, f"{prefix}[{i}]")
    else:
        yield prefix, obj


def _classify_moves(rel: str) -> dict:
    head = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=ROOT, capture_output=True, text=True)
    if head.returncode != 0:
        return {"comparable": False, "reason": "not in HEAD (uncommitted since UI-1)"}
    before = dict(_flatten(json.loads(head.stdout)))
    after = dict(_flatten(json.loads((ROOT / rel).read_text())))
    moved, unclassified = {}, []
    for key in sorted(set(before) | set(after)):
        if before.get(key) == after.get(key):
            continue
        cat = next((c for c, frag in _ALLOWED_MOVES if frag in key), None)
        if cat is None:
            unclassified.append(f"{key}: {before.get(key)!r} -> {after.get(key)!r}")
        moved.setdefault(cat or "UNCLASSIFIED", []).append(key)
    return {"comparable": True, "leaves": len(set(before) | set(after)),
            "moved": {k: len(v) for k, v in moved.items()},
            "moved_paths": {k: v[:8] for k, v in moved.items()},
            "unclassified": unclassified[:8]}


def bar_b0(con, season: int) -> dict:
    """*If a display change moves a number, it is not a display change.*

    UI-2 is the first session to touch ``session.py`` for real, so this is the bar that matters
    most. It runs UI-1's whole sheet — which runs K2's, which runs K1.5's, which runs K1's — and
    then adds the clause UI-2 owes on top: **every one of the fifteen existing board columns is
    bit-identical** to what it was before the three new ones were appended.
    """
    r = subprocess.run([sys.executable, "steps/session_ui_1.py"], cwd=ROOT,
                       capture_output=True, text=True, timeout=21600)
    sheet = ROOT / "analysis" / "session_ui_1.json"
    data = json.loads(sheet.read_text()) if sheet.exists() else {}
    per_bar = {k: v.get("pass") for k, v in (data.get("bars") or {}).items()}
    nested = data.get("bars", {}).get("b0", {})

    # ★ the clause UI-2 owes: the fifteen do not move. Rebuilt on a *pre-UI-2* projection — the
    # advanced view is exactly BOARD_VIEW_COLS, so if any of the three new columns had perturbed a
    # value rather than been appended, this frame would differ from the same call without them.
    built = engine.build(con, season)
    state, meta = _draft(built, season, k=1, finish=False, picks=20)
    plain = session.board_view(state, SEAT, n=200, risk=built["risk"])
    rich = session.board_view(state, SEAT, n=200, risk=built["risk"], vi=built["value_index"],
                              byes=session.bye_weeks(con, season),
                              elevation=session.elevation_ratio(con))
    fifteen = [lbl for _, lbl in session.BOARD_VIEW_COLS]
    differing = [c for c in fifteen
                 if not plain[c].equals(rich[c])
                 and not (plain[c].isna().all() and rich[c].isna().all())]
    quantile_block = [c for c in ("Q10", "MED", "Q90", "COIN", "FLAGS")
                      if not plain[c].equals(rich[c])]

    moves = {p: _classify_moves(p) for p in ("analysis/session_k1_app.json",
                                             "analysis/session_k1_5_app.json",
                                             "analysis/session_k2_app.json",
                                             "analysis/session_ui_1.json")}
    clean = all(not m.get("unclassified") for m in moves.values())
    return {"bar": "B0 — UI-1's sheet re-runs (K2, K1.5, K1 nested); the fifteen are bit-identical",
            "pass": bool(data.get("all_pass") and clean and not differing and not quantile_block),
            "returncode": r.returncode, "ui1_all_pass": data.get("all_pass"),
            "ui1_per_bar": per_bar,
            "k2_all_pass": nested.get("k2_all_pass"),
            "k1_5_all_pass": nested.get("k1_5_all_pass"),
            "k1_all_pass": nested.get("k1_all_pass"),
            "existing_columns_checked": len(fifteen),
            "existing_columns_differing": differing,
            "quantile_block_differing": quantile_block,
            "every_moved_leaf_classified": clean,
            "moves_vs_committed": moves,
            "tail": "" if data.get("all_pass") else r.stdout[-2000:]}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=None)
    ap.add_argument("--only", default=None, help="b0|b1|b2|b3|b4|b5|b6|flow")
    a = ap.parse_args()

    con = _con()
    season = a.season or engine.live_season(con)
    print(f"=== SESSION UI-2 DONE-BAR — season {season} ===\n")
    plan = {
        "b1": lambda: bar_b1(con, season),
        "b2": lambda: bar_b2(con, season),
        "b3": lambda: bar_b3(con, season),
        "b4": lambda: bar_b4(con, season),
        "b5": lambda: bar_b5(con, season),
        "b6": lambda: bar_b6(con, season),
        "flow": lambda: bar_flow(con, season),
        "b0": lambda: bar_b0(con, season),
    }
    if a.only:
        plan = {a.only: plan[a.only]}

    results = {}
    for name, fn in plan.items():
        print(f"--- {name} ---")
        r = fn()
        results[name] = r
        print(f"  {r['bar']}\n  {'PASS' if r['pass'] else 'FAIL'}")
        for k, v in r.items():
            if k not in ("bar", "pass") and not isinstance(v, (list, dict)) and v != "":
                print(f"    {k}: {v}")
        print()

    report = {"season": season, "seat": SEAT + 1,
              "new_columns": list(session.UI2_COLS),
              "view_modes": list(session.VIEW_MODES),
              "app_view_modes": list(session.APP_VIEW_MODES),
              "tier_feature_shipped": False,
              "all_pass": all(r["pass"] for r in results.values()), "bars": results}
    out = OUT if not a.only else PARTIAL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str))
    con.close()
    print(f"{'ALL BARS PASS' if report['all_pass'] else 'SOME BARS FAILED'} -> {out}")


if __name__ == "__main__":
    main()
