"""Session K2 done-bar — surfacing + the post-draft page, and its eight pre-registered bars.

    uv run python steps/session_k2_app.py            # every bar
    uv run python steps/session_k2_app.py --only b3  # one of them

Writes ``analysis/session_k2_app.json``.

★ **The bars were fixed before the code was written** (2026-07-31, stated in-session): B0 the K1
rule, B1 14.N renders and agrees, B2 the cliff is the *decision path's*, B3 the three construction
risks compute and an unknown bye stays unknown, B4 three projections of one query, B5 the grade
reproduces from its printed parts, B6 the reach labels are the engine's, B7 a human can finish a
draft by clicking and land on the page.

★ **The rule that outranks all eight is K1's:** *if a display change moves a number, it is not a
display change.* K2 adds two board columns, a third projection and a page; it refits nothing, and
B0 re-runs **both** committed sheets to prove it.

Everything runs on the **live board** through the app's own entry points, for the reason Session K1
learned the hard way — nine bars passed on an app that would not start.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import engine, post_draft, probe  # noqa: E402

from fantasy_quant.data import db  # noqa: E402
from fantasy_quant.draft import drift, optimizer, session  # noqa: E402
from fantasy_quant.draft.config import LeagueSettings  # noqa: E402
from fantasy_quant.draft.enrichment import CENSOR_AT  # noqa: E402
from fantasy_quant.draft.simulator import _apply_pick, pick_by_adp  # noqa: E402

OUT = Path("analysis/session_k2_app.json")
APP = Path("app/main.py")
ROOT = Path(__file__).resolve().parents[1]
SEAT = 5                       # 0-indexed; the seat K1.5's sheet is written from
BAR_SIMS = 120                 # the sheet's sim budget; the app ships `post_draft.ARRIVAL_SIMS`


def _con():
    return db.connect(read_only=True)


def _finish(state, meta, risk) -> None:
    """Autodraft every human seat by ADP and run the room out — a deterministic full draft."""
    session.advance(state, meta, risk)
    while not state.is_done() and state.available:
        t = state.team_on_clock()
        _apply_pick(state, t, int(pick_by_adp(state, t, noise=0.0)))
        session.advance(state, meta, risk)


def _draft(built, season: int, k: int = 1, *, finish: bool = True):
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
    return state, meta


# ------------------------------------------------------------------------------------------------
# B2 — 14.E: the cliff on the board is the cliff the room drafts on
# ------------------------------------------------------------------------------------------------
def bar_b2(con, season: int) -> dict:
    """★ Not "the display agrees with a re-derivation" — *the display reads the decision path*.

    ``RiskModel.effective_rank`` computes ``positional_cliff(pool.player_key, pool.pos, risk.bv)``
    to price 9.1 urgency. This asserts the ``CLIFF`` column is that exact vector, on the same pool
    with the same ``bv`` map. T27's lesson is that a display path and a decision path built
    separately will disagree and nobody will notice; the only durable fix is that there is one path.
    """
    built = engine.build(con, season)
    risk = built["risk"]
    state, meta = _draft(built, season, k=1, finish=False)
    bad, checks = [], 0
    for team in (SEAT, 0):
        pool = state.draftable_pool(team)
        want = optimizer.positional_cliff(pool["player_key"], pool["pos"], risk.bv)
        got = session.board_view(state, team, risk=risk)["CLIFF"].to_numpy(float)
        checks += 1
        if not np.allclose(want, got, equal_nan=True):
            bad.append(f"seat {team}: max |Δ| {np.nanmax(np.abs(want - got)):.6f}")

    # the strip's arithmetic: n_before counts players at or above the cliff row, in board order
    tab = session.cliff_table(state, SEAT, risk=risk)
    pool = state.draftable_pool(SEAT)
    cliffs = session.cliff_series(state, SEAT, risk=risk)
    strip_bad = []
    for r in tab.itertuples(index=False):
        grp = pool[pool["pos"] == r.pos]
        if list(grp.index).index(r.at_index) + 1 != r.n_before:
            strip_bad.append(f"{r.pos}: n_before {r.n_before}")
        if abs(float(cliffs.loc[r.at_index]) - r.drop) > 1e-9:
            strip_bad.append(f"{r.pos}: drop {r.drop}")

    # a truncated view must not change a cliff — it is a fact about the pool, not about the screen
    small = session.board_view(state, SEAT, n=8, risk=risk)["CLIFF"]
    full = session.board_view(state, SEAT, risk=risk)["CLIFF"]
    window_stable = bool(np.allclose(small.to_numpy(float),
                                     full.reindex(small.index).to_numpy(float), equal_nan=True))
    return {"bar": "B2 — the CLIFF column IS optimizer.positional_cliff on risk.bv",
            "pass": bool(not bad and not strip_bad and window_stable),
            "seats_checked": checks, "mismatches": bad, "strip_problems": strip_bad[:6],
            "cliff_invariant_to_row_cap": window_stable,
            "positions": tab["pos"].tolist(), "drops": [round(d, 1) for d in tab["drop"]],
            "note": ("Also asserted: the cliff does not move when the board is truncated to 8 "
                     "rows. A cliff is a statement about what is left at a position, so a "
                     "screen-local one would mean 'the tier runs out on this screen'.")}


# ------------------------------------------------------------------------------------------------
# B4 — 14.G: three projections of one query, and a censored floor renders as censored
# ------------------------------------------------------------------------------------------------
def bar_b4(con, season: int) -> dict:
    built = engine.build(con, season)
    state, _ = _draft(built, season, k=1, finish=False)
    bad, checks = [], 0
    for pos in (None, "RB", "WR", "QB,TE", "K,DST"):
        view = session.board_view(state, SEAT, pos=pos, n=50, risk=built["risk"])
        proj = {m: session.project_view(view, mode=m) for m in session.VIEW_MODES}
        checks += 1
        for m, f in proj.items():
            if list(f.index) != list(view.index):
                bad.append(f"{m} rows diverged at pos={pos}")
        if list(proj["ranges"].columns) != list(session.RANGE_VIEW_COLS):
            bad.append(f"ranges columns wrong at pos={pos}")
        if list(proj["advanced"].columns) != [lbl for _, lbl in session.BOARD_VIEW_COLS]:
            bad.append(f"advanced columns wrong at pos={pos}")
    # K1.5's two-state control still means what it meant — its committed sheet differences on it
    v = session.board_view(state, SEAT, n=20, risk=built["risk"])
    legacy_ok = (list(session.project_view(v, advanced=False).columns)
                 == list(session.SLIM_VIEW_COLS)
                 and list(session.project_view(v, advanced=True).columns)
                 == [lbl for _, lbl in session.BOARD_VIEW_COLS])

    # the bands are the frozen contract's, and a censored floor is flagged rather than printed as 0
    ranges = session.project_view(session.board_view(state, SEAT, n=200, risk=built["risk"]),
                                  mode="ranges")
    pool = state.draftable_pool(SEAT).head(200)
    frozen_ok = bool(np.allclose(ranges["Q10"].to_numpy(float),
                                 pd.to_numeric(pool["q10"], errors="coerce").to_numpy(float),
                                 equal_nan=True))
    at_floor = ranges["Q10"].le(CENSOR_AT) & ranges["Q10"].notna()
    flagged = ranges.loc[at_floor, "FLAGS"].astype(str).str.contains("censored floor")
    censor_ok = bool(at_floor.sum() == 0 or flagged.all())
    no_dist = ranges["FLAGS"].astype(str).str.contains("no distribution")
    coin = int(pd.Series(ranges["COIN"]).fillna(False).astype(bool).sum())
    return {"bar": "B4 — slim/ranges/advanced are one query; bands frozen; censoring flagged",
            "pass": bool(not bad and legacy_ok and frozen_ok and censor_ok),
            "filters_checked": checks, "problems": bad[:6],
            "k1_5_advanced_flag_unchanged": legacy_ok,
            "bands_are_frozen_q10": frozen_ok,
            "rows": int(len(ranges)), "at_censoring_point": int(at_floor.sum()),
            "all_censored_rows_flagged": censor_ok,
            "no_distribution_rows": int(no_dist.sum()),
            "adjacent_overlapping_pairs": coin,
            "note": ("A season total cannot be negative, so q10 piles up on zero. Printing a bare "
                     "0 there would read as 'his floor is zero' — the T22 defect (blank is not "
                     "zero) with the other sign. It reads `censored floor` instead.")}


# ------------------------------------------------------------------------------------------------
# B3 — 14.F: the three construction risks compute, and an unknown bye stays unknown
# ------------------------------------------------------------------------------------------------
def bar_b3(con, season: int) -> dict:
    built = engine.build(con, season)
    state, meta = _draft(built, season, k=1)
    byes = session.bye_weeks(con, season)
    elev = session.elevation_ratio(con)
    r = session.roster_construction_risk(state, SEAT, vi=built["value_index"], byes=byes,
                                         elevation=elev)

    # the bye table is over STARTERS, and it accounts for every one of them exactly once
    slots, _ = session.lineup_choice(state, state.roster(SEAT), built["value_index"])
    n_starters = len({i for i in slots.values() if i is not None})
    counted = int(r["byes"]["n"].sum()) if len(r["byes"]) else 0
    accounted = counted + r["unknown_byes"] == n_starters

    # ...and it traces to the store, not to a fabricated week 0
    keys = set(str(k) for k in state.roster(SEAT)["player_key"])
    from_store = {k: float(byes[k]) for k in keys if k in byes.index}
    zero_weeks = int((r["byes"]["week"] == 0).sum()) if len(r["byes"]) else 0

    # a lead back's handcuff is the RB2, never the RB1 (the first run had this upside down)
    hc_bad = []
    for row in r["handcuffs"].itertuples(index=False):
        mates = state.board[(state.board["team"] == row.nfl_team) & (state.board["pos"] == "RB")]
        if str(mates.iloc[0]["player_name"]) != row.starter:
            hc_bad.append(f"{row.starter} is not {row.nfl_team}'s lead back")
        if str(mates.iloc[1]["player_name"]) != row.backup:
            hc_bad.append(f"{row.backup} is not {row.starter}'s handcuff")

    empty = session.roster_construction_risk(state, SEAT, vi=built["value_index"], byes=None,
                                             elevation=None)
    return {"bar": "B3 — bye / concentration / handcuff gaps compute; unknown stays unknown",
            "pass": bool(accounted and zero_weeks == 0 and not hc_bad
                         and r["max_team_players"] >= 1 and empty["max_bye_starters"] == 0),
            "n_starters": n_starters, "byes_counted": counted,
            "unknown_byes": r["unknown_byes"], "starters_accounted_for": accounted,
            "fabricated_week_zero_rows": zero_weeks,
            "bye_source_rows_for_this_roster": len(from_store),
            "max_bye_starters": r["max_bye_starters"],
            "max_team_players": r["max_team_players"],
            "n_handcuff_gaps": r["n_handcuff_gaps"], "handcuff_problems": hc_bad[:4],
            "elevation_ratio": round(elev, 3),
            "degrades_without_byes": empty["max_bye_starters"] == 0,
            "note": ("The store has no schedule table: byes come from the FantasyPros ECR "
                     "snapshots and ~1 row in 10 has none. A missing bye is counted as unknown "
                     "and shown as unknown — an fillna(0) would file him under week 0, which "
                     "reads as 'no bye'.")}


# ------------------------------------------------------------------------------------------------
# B5 — 14.I: the grade reproduces from the four numbers printed beside it
# ------------------------------------------------------------------------------------------------
def bar_b5(con, season: int) -> dict:
    """★ The one bar that matters for an invented weighting.

    The blend is a presentation choice with nothing validating it — which is *allowed*, and is the
    user's call, as long as it is legible. Legible means: the weights are one named constant, they
    sum to 100, and the total is exactly the sum of the per-component points printed next to it. A
    grade a reader cannot re-add by hand is a claim wearing a number's clothes.
    """
    built = engine.build(con, season)
    state, meta = _draft(built, season, k=1)
    sm = session.seat_map_from(meta)
    odds, _ = session.odds_table(con, state, meta, sm, sims=BAR_SIMS)
    byes = session.bye_weeks(con, season)
    grade = session.draft_grade(state, meta, sm, odds=odds, vi=built["value_index"], byes=byes,
                                elevation=session.elevation_ratio(con))

    weights_sum = float(sum(session.GRADE_WEIGHTS.values()))
    parts = sum(grade[f"points_{c}"] for c in session.GRADE_WEIGHTS)
    reproduces = bool(np.allclose(parts.to_numpy(float), grade["total"].to_numpy(float)))
    in_range = bool(grade["total"].between(-1e-9, 100 + 1e-9).all())
    letters_ok = all(ltr == session.grade_letter(t)
                     for ltr, t in zip(grade["letter"], grade["total"], strict=False))
    # the curve is on the room: someone tops each component and someone floors it
    curved = all(np.isclose(grade[f"score_{c}"].max(), 1.0)
                 and np.isclose(grade[f"score_{c}"].min(), 0.0)
                 for c in session.GRADE_WEIGHTS if grade[c].nunique() > 1)
    # ...and a middling roster must not read as a failure — the defect the first run exposed
    median_letter = session.grade_letter(float(grade["total"].median()))

    # k human seats get k rows and there is nowhere to put a combined one
    state4, meta4 = _draft(built, season, k=4)
    sm4 = session.seat_map_from(meta4)
    odds4, _ = session.odds_table(con, state4, meta4, sm4, sims=BAR_SIMS)
    g4 = session.draft_grade(state4, meta4, sm4, odds=odds4, vi=built["value_index"], byes=byes,
                             elevation=session.elevation_ratio(con))
    per_seat = int(g4["human"].sum()) == 4 and len(g4) == 10
    no_blend = "total" in g4.columns and not any(
        str(c).startswith(("mean_", "avg_", "combined")) for c in g4.columns)

    return {"bar": "B5 — the grade is exactly the sum of its printed parts, once per human seat",
            "pass": bool(reproduces and in_range and letters_ok and per_seat and no_blend
                         and abs(weights_sum - 100.0) < 1e-9),
            "weights": dict(session.GRADE_WEIGHTS), "weights_sum": weights_sum,
            "reproduces_from_components": reproduces, "totals_in_0_100": in_range,
            "letters_match_bands": letters_ok, "min_max_curve_on_the_room": curved,
            "median_team_letter": median_letter,
            "k4_rows": len(g4), "k4_human_rows": int(g4["human"].sum()),
            "no_combined_column": no_blend,
            "grades": {str(r["who"]): f"{r['letter']} {r['total']:.0f}"
                       for _, r in grade.iterrows()},
            "note": ("★ The bands are anchored to this scale, not to a school gradebook. On plain "
                     "90/80/70/60 bands the median team in a ten-team room graded D+ and six of "
                     "ten graded D or F — the app calling an average draft a failure because the "
                     "letters assumed 50 % was a fail when on a curve 50 is the middle.")}


# ------------------------------------------------------------------------------------------------
# B6 — 16.12: the reach-risk readout is the engine's, both probabilities kept
# ------------------------------------------------------------------------------------------------
def bar_b6(con, season: int) -> dict:
    built = engine.build(con, season)
    state, meta = _draft(built, season, k=1, finish=False)
    frame = session.reach_risk_view(state, meta, SEAT, n=25)
    labels_ok = all(drift.reach_risk_label(p) == lbl
                    for p, lbl in zip(frame["p_available"], frame["reach_risk"],
                                      strict=False))
    both = {"p_available", "p_available_baseline"} <= set(frame.columns)
    bounded = bool(frame["p_available"].between(0.0, 1.0).all())

    # the window is the snake's, taken from the optimizer rather than counted here
    last = state.n_teams * state.rounds
    nxt = optimizer._next_own_pick(state.overall_pick, SEAT, state.n_teams, last)
    mine = state.team_on_clock() == SEAT
    want = 0 if nxt is None else max(0, int(nxt) - int(state.overall_pick) - (1 if mine else 0))
    window_ok = frame.attrs.get("window_picks") == want

    # monotone in ADP is the sanity gate: a player who goes later survives at least as often
    ordered = frame.sort_values("adp")["p_available"].to_numpy(float)
    spearman = float(pd.Series(ordered).corr(pd.Series(np.arange(len(ordered))), method="spearman"))
    return {"bar": "B6 — P(available) is drift.availability_readout, labelled by the engine",
            "pass": bool(labels_ok and both and bounded and window_ok and spearman > 0.8),
            "labels_from_reach_risk_label": labels_ok,
            "both_probabilities_present": both, "probabilities_in_0_1": bounded,
            "window_picks": frame.attrs.get("window_picks"), "window_expected": want,
            "next_own_pick": nxt, "spearman_p_vs_adp": round(spearman, 3),
            "buckets": frame["reach_risk"].value_counts().to_dict(),
            "note": ("Both columns ship because the drift adjustment is not backtestable — FFC "
                     "publishes one board a season, so 16.11's momentum could only be validated "
                     "forward. Drift is opt-in and off by default, so the two usually agree, and "
                     "that agreement is a fact about the default rather than about the model.")}


# ------------------------------------------------------------------------------------------------
# B1 — 14.N renders for k ∈ {0,1,4} and shows the session's own numbers
# ------------------------------------------------------------------------------------------------
def bar_b1(con, season: int) -> dict:
    try:
        from streamlit.testing.v1 import AppTest
        from streamlit.util import calc_hash
    except ImportError as exc:
        return {"bar": "B1", "pass": False, "reason": str(exc)}

    from app.main import PAGE_SPECS
    page_hash = calc_hash(PAGE_SPECS["post"][3])
    built = engine.build(con, season)
    runs, exceptions = [], []
    for k in (0, 1, 4):
        state, meta = _draft(built, season, k=k)
        sm = session.seat_map_from(meta)
        odds, prov = session.odds_table(con, state, meta, sm, sims=BAR_SIMS)
        at = AppTest.from_file(str(APP), default_timeout=900)
        at._page_hash = page_hash
        at.session_state["draft"] = {"state": state, "meta": meta, "vi": built["value_index"],
                                     "risk": built["risk"]}
        # seed the page's own cache under its own key, so the bar exercises the cache path and
        # does not pay for `ARRIVAL_SIMS` three times
        at.session_state["odds"] = (post_draft._odds_key(state, meta), odds, prov)
        probe.reset()
        at.run()
        exceptions += [str(e.value)[:400] for e in at.exception]
        ran = probe.snapshot()
        frames = [d.value for d in at.dataframe]
        want = session.summary_table(state, sm, built["value_index"])
        # the standings frame on screen carries the T28 pair, in the session's own numbers
        match = [f for f in frames if "STARTABLE" in getattr(f, "columns", [])]
        startable_ok = bool(match) and np.allclose(
            np.sort(match[0]["STARTABLE"].to_numpy(float)),
            np.sort(want["startable"].to_numpy(float)))
        # ⚠ scrape the alert elements too, not just markdown/caption: both 16.17 honesty rules are
        # rendered with `st.warning`/`st.info`, and a check that only reads markdown would report
        # them missing from a page that shows them — a bar failing for the wrong reason is a bar
        # nobody trusts the next time it fails.
        text = " ".join(str(e.value) for kind in ("markdown", "caption", "warning", "info",
                                                  "success")
                        for e in getattr(at, kind, []))
        runs.append({
            "k": k, "page_bodies": ran, "n_dataframes": len(frames),
            "standings_matches_session": startable_ok,
            "capital_labelled": bool(match) and "CAPITAL" in list(match[0].columns),
            "odds_lead_with_multiple": any("x" in str(v) for f in frames
                                           if "TITLE" in getattr(f, "columns", [])
                                           for v in f["TITLE"]),
            "one_observation_rule_rendered": (k <= 1) or ("ONE observation" in text),
            "fully_simulated_scope_rendered": "fully simulated" in text,
            "grade_rendered": any("letter" in str(f.columns).lower() or "COMPONENT"
                                  in getattr(f, "columns", []) for f in frames),
        })
    ok = (not exceptions
          and all(r["page_bodies"] == {"post": 1} for r in runs)
          and all(r["standings_matches_session"] and r["capital_labelled"] for r in runs)
          and all(r["odds_lead_with_multiple"] for r in runs)
          and all(r["one_observation_rule_rendered"] for r in runs)
          and all(r["fully_simulated_scope_rendered"] for r in runs)
          and all(r["grade_rendered"] for r in runs if r["k"] > 0))
    return {"bar": "B1 — 14.N renders at k∈{0,1,4}, one page body, showing session's own numbers",
            "pass": bool(ok), "runs": runs,
            "n_exceptions": len(exceptions), "exceptions": exceptions[:4],
            "note": ("The page body is counted, not timed (T35's instrument): 14.N must be one "
                     "page, not a tab whose neighbours also run. The standings frame is compared "
                     "against `session.summary_table` rather than against a second computation — "
                     "there is one derivation and the page formats it.")}


# ------------------------------------------------------------------------------------------------
# B7 — FLOW: a human finishes a draft by clicking and lands on the page
# ------------------------------------------------------------------------------------------------
def bar_flow(con, season: int) -> dict:
    """★ K1.5's lesson, carried forward: *an import bar and a use bar are different claims.*

    ⚠ **What this cannot drive, stated rather than skipped.** ``AppTest`` has no way to make a
    selection in an ``st.dataframe`` (``on_select`` is a client event), so the player modal cannot
    be opened by a simulated click. It is covered instead by asserting the card its dialog renders
    is complete for a live board row — the content, not the click. That is a smaller claim than
    B7's other half and is labelled as one.
    """
    try:
        from streamlit.testing.v1 import AppTest
        from streamlit.util import calc_hash
    except ImportError as exc:
        return {"bar": "FLOW", "pass": False, "reason": str(exc)}

    from app.main import PAGE_SPECS
    built = engine.build(con, season)

    # --- half 1: the last pick, made by clicking, sends you to the post-draft page --------------
    state, meta = engine.start_draft(built, human_seats=[SEAT], settings=LeagueSettings(),
                                     season=season, seed=5, room_seed=2)
    _finish(state, meta, built["risk"])
    # rewind to one pick short of done by replaying all but the human's last pick
    state2, meta2 = engine.start_draft(built, human_seats=[SEAT], settings=LeagueSettings(),
                                       season=season, seed=5, room_seed=2)
    session.advance(state2, meta2, built["risk"])
    while not state2.is_done() and state2.available:
        t = state2.team_on_clock()
        if t == SEAT and len(state2.roster(SEAT)) == state2.rounds - 1:
            break
        _apply_pick(state2, t, int(pick_by_adp(state2, t, noise=0.0)))
        session.advance(state2, meta2, built["risk"])
    picks_before = len(state2.log)

    a = AppTest.from_file(str(APP), default_timeout=900)
    a._page_hash = calc_hash(PAGE_SPECS["draft"][3])
    a.session_state["draft"] = {"state": state2, "meta": meta2, "vi": built["value_index"],
                                "risk": built["risk"]}
    a.run()
    quick = [x for x in a.button if x.key and x.key.startswith("quick_")]
    if quick:
        quick[0].click().run()
    after = a.session_state["draft"]["state"]
    completed = after.is_done() or not after.available
    # ⚠ `AppTest.session_state` is a SafeSessionState, not a dict — it has no `.get`
    arrived = ("_arrived_post_draft" in a.session_state
               and bool(a.session_state["_arrived_post_draft"]))

    # --- half 2: the page a finished draft lands on renders ------------------------------------
    sm = session.seat_map_from(meta)
    odds, prov = session.odds_table(con, state, meta, sm, sims=BAR_SIMS)
    b = AppTest.from_file(str(APP), default_timeout=900)
    b._page_hash = calc_hash(PAGE_SPECS["post"][3])
    b.session_state["draft"] = {"state": state, "meta": meta, "vi": built["value_index"],
                                "risk": built["risk"]}
    b.session_state["odds"] = (post_draft._odds_key(state, meta), odds, prov)
    b.run()
    letters = {r["letter"] for _, r in session.draft_grade(
        state, meta, sm, odds=odds, vi=built["value_index"],
        byes=session.bye_weeks(con, season),
        elevation=session.elevation_ratio(con)).iterrows()}

    # --- half 3: the modal's content (the click itself is not drivable) -------------------------
    board_index = int(session.board_view(state, SEAT, n=1, risk=built["risk"]).index[0])
    card = session.player_card(state, board_index, vi=built["value_index"], lam=built["lam"],
                               risk=built["risk"])
    card_ok = (len(card["bars"]) == 8 and card["name"] and card["chain"]
               and len(card["chain"][0]["rows"]) >= 8)

    # --- half 4: every page still renders with a live draft in session state -------------------
    # ⚠ K2 edited three pages that already existed (board, draft room, room grid) and added one.
    # K1 shipped an app that would not start while nine bars said PASS; the cheapest guard against
    # the repeat is to open every page and look for an exception.
    pages, page_errors = {}, []
    for name, spec in PAGE_SPECS.items():
        p = AppTest.from_file(str(APP), default_timeout=900)
        p._page_hash = calc_hash(spec[3])
        p.session_state["draft"] = {"state": state, "meta": meta, "vi": built["value_index"],
                                    "risk": built["risk"]}
        p.session_state["odds"] = (post_draft._odds_key(state, meta), odds, prov)
        p.run()
        pages[name] = len(p.exception)
        page_errors += [f"{name}: {str(e.value)[:200]}" for e in p.exception]

    exceptions = ([str(e.value)[:300] for e in a.exception]
                  + [str(e.value)[:300] for e in b.exception] + page_errors)
    return {"bar": "FLOW — the last pick lands on 14.N by clicking; every page renders",
            "pass": bool(quick and completed and arrived and card_ok and not exceptions),
            "pages_rendered": pages, "page_errors": page_errors[:4],
            "picks_before": picks_before, "picks_after": len(after.log),
            "draft_completed_by_click": completed, "navigated_to_post_draft": arrived,
            "clicked": quick[0].label.split("\n")[0] if quick else None,
            "post_page_dataframes": len(b.dataframe), "letters_seen": sorted(letters),
            "card_player": card["name"], "card_bars": len(card["bars"]),
            "card_chain_rows": len(card["chain"][0]["rows"]) if card["chain"] else 0,
            "n_exceptions": len(exceptions), "exceptions": exceptions[:3],
            "modal_click_not_drivable": True}


# ------------------------------------------------------------------------------------------------
# B0 — the K1 rule, twice over: both committed sheets still pass
# ------------------------------------------------------------------------------------------------
def bar_b0() -> dict:
    """*If a display change moves a number, it is not a display change.*

    K2 adds two columns to the advanced board, a third projection, a page and a grade. None of it
    refits anything, so both committed sheets must come back unchanged — and K1.5's is the stricter
    of the two, because it re-runs K1's inside itself.
    """
    results = {}
    for name, script in (("k1_5", "steps/session_k1_5_app.py"), ):
        r = subprocess.run([sys.executable, script], cwd=ROOT, capture_output=True, text=True,
                           timeout=10800)
        sheet = Path("analysis/session_k1_5_app.json")
        data = json.loads(sheet.read_text()) if sheet.exists() else {}
        results[name] = {"returncode": r.returncode, "all_pass": data.get("all_pass"),
                         "per_bar": {k: v.get("pass")
                                     for k, v in (data.get("bars") or {}).items()},
                         "tail": r.stdout[-800:] if not data.get("all_pass") else ""}
    k1 = json.loads(Path("analysis/session_k1_app.json").read_text()) \
        if Path("analysis/session_k1_app.json").exists() else {}
    results["k1_nested"] = {"all_pass": k1.get("all_pass"),
                            "per_bar": {k: v.get("pass")
                                        for k, v in (k1.get("bars") or {}).items()}}
    return {"bar": "B0 — Session K1's and K1.5's committed bar sheets still pass, unchanged",
            "pass": bool(results["k1_5"]["all_pass"] and results["k1_nested"]["all_pass"]),
            **results}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=None)
    ap.add_argument("--only", default=None, help="b0|b1|b2|b3|b4|b5|b6|flow")
    a = ap.parse_args()

    con = _con()
    season = a.season or engine.live_season(con)
    print(f"=== SESSION K2 DONE-BAR — season {season} ===\n")
    plan = {
        "b2": lambda: bar_b2(con, season),
        "b4": lambda: bar_b4(con, season),
        "b3": lambda: bar_b3(con, season),
        "b5": lambda: bar_b5(con, season),
        "b6": lambda: bar_b6(con, season),
        "b1": lambda: bar_b1(con, season),
        "flow": lambda: bar_flow(con, season),
        "b0": bar_b0,
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

    report = {"season": season, "seat": SEAT + 1, "bar_sims": BAR_SIMS,
              "app_arrival_sims": post_draft.ARRIVAL_SIMS,
              "all_pass": all(r["pass"] for r in results.values()), "bars": results}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str))
    con.close()
    print(f"{'ALL BARS PASS' if report['all_pass'] else 'SOME BARS FAILED'} -> {OUT}")


if __name__ == "__main__":
    main()
