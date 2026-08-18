"""Session K1.5 done-bar — the draft room a human can use, and its six pre-registered bars.

    uv run python steps/session_k1_5_app.py            # every bar
    uv run python steps/session_k1_5_app.py --only b3  # one of them

Writes ``analysis/session_k1_5_app.json``.

★ **The bars run on the live board and through the app's own entry points**, for the reason
Session K1 learned the hard way: its unit tests, its ``AppTest`` run and its server bar all shared
one false assumption and the app shipped broken with nine PASSes on the sheet. So B0 drives the CLI
as a **subprocess** the way a human does, B1 counts page bodies under Streamlit's own runtime, and
B4 checks the display grid against the frozen solver's headline number rather than against itself.

**And the K1 rule that outranks all six:** *if a display change moves a number, it is not a display
change.* ``--k1`` re-runs ``steps/session_k1_app.py`` and asserts its bars still pass.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import engine, probe  # noqa: E402
from steps import _sheet_diff  # noqa: E402

from fantasy_quant.data import db  # noqa: E402
from fantasy_quant.draft import session  # noqa: E402
from fantasy_quant.draft.config import LeagueSettings  # noqa: E402
from fantasy_quant.draft.optimizer import starter_value  # noqa: E402
from fantasy_quant.draft.simulator import _apply_pick, pick_by_adp  # noqa: E402

OUT = Path("analysis/session_k1_5_app.json")
APP = Path("app/main.py")
ROOT = Path(__file__).resolve().parents[1]
#: The board :data:`app.engine.T34_REFERENCE` was measured on, as `resolve_board(asof=)` wants it.
#: It is stated once, here, because two places would be two answers the first time one is edited.
T34_REFERENCE_ASOF = "2026-07-30"
SEAT = 5                       # 0-indexed; the seat the T34 report was made from (seat 6)


def _con():
    return db.connect(read_only=True)


def _finish(state, meta, risk) -> None:
    """Autodraft every human seat by ADP and run the room out — a deterministic full draft."""
    session.advance(state, meta, risk)
    while not state.is_done() and state.available:
        t = state.team_on_clock()
        _apply_pick(state, t, int(pick_by_adp(state, t, noise=0.0)))
        session.advance(state, meta, risk)


# ------------------------------------------------------------------------------------------------
# B0 — a mock draft is a NEW draft, and the CLI's measurement default did not move (T34)
# ------------------------------------------------------------------------------------------------
def bar_b0(con, season: int, n_drafts: int = 20) -> dict:
    built = engine.build(con, season)
    opens = []
    for _ in range(n_drafts):
        state, meta = engine.start_draft(built, human_seats=[SEAT], settings=LeagueSettings(),
                                         season=season)
        session.advance(state, meta, built["risk"])
        opens.append(tuple(p["player_name"] for p in state.log[:5]))
    distinct = len(set(opens))

    # replay: the drawn seeds are in `meta`, so a locked pair reproduces the draft pick-for-pick
    a, meta_a = engine.start_draft(built, human_seats=[SEAT], settings=LeagueSettings(),
                                   season=season)
    session.advance(a, meta_a, built["risk"])
    b, meta_b = engine.start_draft(built, human_seats=[SEAT], settings=LeagueSettings(),
                                   season=season, seed=meta_a["seed"],
                                   room_seed=meta_a["room_seed"])
    session.advance(b, meta_b, built["risk"])
    replays = ([p["player_name"] for p in a.log] == [p["player_name"] for p in b.log]
               and meta_a["room"] == meta_b["room"])

    # ⚠ the other half: `steps/` must still mean what every committed bar sheet assumes — asserted
    # **on the board the reference names**, and reported on today's.
    ref = engine.T34_REFERENCE
    cli = _cli_first_five(season, asof=T34_REFERENCE_ASOF)
    live = _cli_first_five(season)
    cli_unchanged = cli["first_five"] == ref["first_five"]
    twice_identical = cli["identical_twice"] and live["identical_twice"]
    parsed_clean = (cli["lines_that_did_not_parse"] == 0
                    and live["lines_that_did_not_parse"] == 0)

    return {"bar": "B0 — no two app drafts alike · a locked seed replays · the CLI has not moved",
            "pass": bool(distinct > 1 and replays and cli_unchanged and twice_identical
                         and parsed_clean),
            "n_drafts": n_drafts, "distinct_openings": distinct,
            "example_openings": [" · ".join(o) for o in sorted(set(opens))[:3]],
            "locked_seeds_replay": replays,
            "replayed_seed": meta_a["seed"], "replayed_room_seed": meta_a["room_seed"],
            "cli_first_five": cli["first_five"], "cli_reference": ref["first_five"],
            "cli_matches_reference": cli_unchanged, "cli_identical_twice": twice_identical,
            "reference_board": ref["board"], "reference_asof": T34_REFERENCE_ASOF,
            "cli_log_lines_that_did_not_parse": cli["lines_that_did_not_parse"]
            + live["lines_that_did_not_parse"],
            # a readout, never a gate: which players the frozen defaults produce on *today's* board
            "cli_first_five_live_board": live["first_five"],
            "note": ("The app draws both seeds from OS entropy; the CLI keeps --seed 7 and an "
                     "unset --room-seed. A measurement default and a human default are different "
                     "objects, and this repo was shipping one of them twice. ★ The reference "
                     "clause is asserted with the board PINNED to the vintage T34_REFERENCE names "
                     "(T41): the CLI's defaults are frozen, the ADP under them is not, so an "
                     "unpinned comparison fails every time the Stage-0 chore runs and says the "
                     "wrong thing when it does.")}


_PICK_LINE = re.compile(r"^\s+\d+\.\d+\s+T\d+\s+\S[\S ]*?\s{2,}(\S[\S ]*?)\s{2,}\S+\s+\(ADP")
#: Looser sibling — a line that *is* a pick, on its number and team alone. The two counts must agree
#: or the fixed-width parse has drifted; see `session_k1_app._cli_picks` for the instance that cost
#: a session an hour (a 14-character personality in a 15-wide column).
_PICK_ROW = re.compile(r"^\s+\d+\.\d+\s+T\d+\s")


def _cli_first_five(season: int, asof: str | None = None) -> dict:
    """Run ``mock_draft.py start`` twice at the frozen defaults; parse the first five picks.

    ★ **T41 (2026-08-17) — ``asof`` pins the board this reference was measured on.**
    :data:`~app.engine.T34_REFERENCE` names its own vintage (*"2026 FFC (07-30)"*) and the sequence
    it records is a property of **that** board: the CLI's defaults are frozen, the ADP under them is
    not. Left unpinned, this clause turned the mandated weekly Stage-0 chore into a bar failure
    reading *"the CLI has moved"* — the same defect as T41 one layer in, a **stale reference used as
    a control**. Pinned, the claim is the one the constant actually supports.
    """
    gaps: list[int] = []

    def run() -> list[str]:
        cmd = [sys.executable, "steps/mock_draft.py", "start", "--seat", str(SEAT + 1),
               "--season", str(season)] + (["--asof", asof] if asof else [])
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=1800)
        if r.returncode:
            return []
        names = [m.group(1).strip() for m in map(_PICK_LINE.match, r.stdout.splitlines()) if m]
        # ⚠ a dropped row does not shorten this list, it *shifts* it — the first five would then be
        # five real picks in the wrong order, which is why the completeness check is not optional.
        rows = sum(1 for ln in r.stdout.splitlines() if _PICK_ROW.match(ln))
        gaps.append(rows - len(names))
        return names[:5]

    first, second = run(), run()
    return {"first_five": first, "identical_twice": bool(first) and first == second,
            "lines_that_did_not_parse": sum(gaps)}


# ------------------------------------------------------------------------------------------------
# B1 — one page body per rerun (T35), and K1's app==CLI identity survives the move
# ------------------------------------------------------------------------------------------------
def _goto(at, url_path: str):
    """Point an ``AppTest`` at one of this app's pages.

    ``AppTest.switch_page`` resolves a **file path** — it is written for the legacy ``pages/``
    directory — and 14.K's pages are callables registered with ``st.navigation``, which have no
    script of their own. Streamlit identifies such a page by ``calc_hash(url_path)``
    (``StreamlitPage._script_hash``), so this navigates by the app's own page identity rather than
    by faking one: the url paths come from ``app/main.py``'s registry, not from a literal here.
    """
    from app.main import PAGE_SPECS
    from streamlit.util import calc_hash

    at._page_hash = calc_hash(PAGE_SPECS[url_path][3])
    return at


def bar_b1() -> dict:
    """★ The measurable half of 14.K, counted rather than timed.

    ``st.tabs`` hides inactive tabs client-side; it does not skip them. Under K1 a keystroke in the
    draft room re-ran all four bodies, including the cost page's whole-board option build. The
    probe counts page-body executions, so "one page ran" is asserted directly instead of being
    inferred from a stopwatch.
    """
    try:
        from streamlit.testing.v1 import AppTest
    except ImportError as exc:
        return {"bar": "B1", "pass": False, "reason": str(exc)}

    probe.reset()
    at = AppTest.from_file(str(APP), default_timeout=900)
    at.run()
    first = probe.snapshot()
    exceptions = [str(e.value)[:400] for e in at.exception]

    # a rerun on the default page must execute that page's body once, and no other
    probe.reset()
    at.run()
    single = probe.snapshot()
    exceptions += [str(e.value)[:400] for e in at.exception]

    # ...and the same on a different page, so the claim is about the router and not about which
    # page happens to be default
    probe.reset()
    _goto(at, "draft")
    at.run()
    on_draft = probe.snapshot()
    exceptions += [str(e.value)[:400] for e in at.exception]

    ok = (sum(single.values()) == 1 and sum(on_draft.values()) == 1
          and set(on_draft) == {"draft"} and not exceptions)
    return {"bar": "B1 — a rerun executes ONE page body (T35), with no uncaught exception",
            "pass": bool(ok),
            "first_run": first, "rerun_default_page": single, "rerun_draft_page": on_draft,
            "n_exceptions": len(exceptions), "exceptions": exceptions[:4],
            "note": ("Under st.tabs every one of these would read 4. The counter lives in the "
                     "shipped code, not in the test: a probe that only exists under the test "
                     "measures the test.")}


# ------------------------------------------------------------------------------------------------
# FLOW — drive the widgets a human clicks, because K1 proved bars can all pass on a broken app
# ------------------------------------------------------------------------------------------------
def bar_flow(con, season: int) -> dict:
    """★ Start a draft with the button, then make a pick with the button.

    Session K1 shipped an app that raised ``ModuleNotFoundError`` for the first human who opened
    it while nine bars said PASS, and the fix that session added (``bar_imports``) proves the entry
    point *imports*. This proves the app **works**: the widgets a drafter actually clicks are
    clicked, and the state they are supposed to change is checked afterwards. It found the
    ``session_state.setdefault`` on a widget key that no other bar in this session noticed.

    ⚠ The pick is driven on a **pre-seeded** draft rather than by continuing from the started one.
    That is an ``AppTest`` limitation, not a workaround for a defect: when a page's widget set
    changes shape between runs (the setup form gives way to the room), ``AppTest`` replays widget
    states the new tree no longer has and raises a ``KeyError`` on its own bookkeeping. A browser
    posts only the widgets it currently shows. Both halves are still driven by clicks.
    """
    try:
        from streamlit.testing.v1 import AppTest
        from streamlit.util import calc_hash
    except ImportError as exc:
        return {"bar": "FLOW", "pass": False, "reason": str(exc)}

    from app.main import PAGE_SPECS
    draft_hash = calc_hash(PAGE_SPECS["draft"][3])

    # --- half 1: the Start draft button really starts a draft ---------------------------------
    a = AppTest.from_file(str(APP), default_timeout=900)
    a._page_hash = draft_hash
    a.run()
    start = [b for b in a.button if b.label == "Start draft"]
    if start:
        start[0].click().run()
    started = "draft" in a.session_state
    meta = a.session_state["draft"]["meta"] if started else {}

    # --- half 2: a quick-pick button really makes that pick ------------------------------------
    built = engine.build(con, season)
    state, meta2 = engine.start_draft(built, human_seats=[SEAT], settings=LeagueSettings(),
                                      season=season, seed=7, room_seed=1)
    session.advance(state, meta2, built["risk"])
    before = len(state.log)
    b = AppTest.from_file(str(APP), default_timeout=900)
    b._page_hash = draft_hash
    b.session_state["draft"] = {"state": state, "meta": meta2, "vi": built["value_index"],
                                "risk": built["risk"]}
    b.run()
    quick = [x for x in b.button if x.key and x.key.startswith("quick_")]
    wanted = quick[0].label.split("\n")[0] if quick else None
    if quick:
        quick[0].click().run()
    after = b.session_state["draft"]["state"]
    mine = [p["player_name"] for p in after.log if p["team"] == SEAT]
    exceptions = ([str(e.value)[:300] for e in a.exception]
                  + [str(e.value)[:300] for e in b.exception])

    return {"bar": "FLOW — a human can start a draft and make a pick by clicking",
            "pass": bool(started and quick and wanted in mine and len(after.log) > before
                         and not exceptions),
            "start_button_started_a_draft": started,
            "randomized_seed": meta.get("seed"), "randomized_room_seed": meta.get("room_seed"),
            "quick_pick_buttons": len(quick), "clicked": wanted, "your_picks": mine,
            "picks_before": before, "picks_after": len(after.log),
            "n_exceptions": len(exceptions), "exceptions": exceptions[:3]}


# ------------------------------------------------------------------------------------------------
# B2 — the slim board and the advanced board are one query, two projections
# ------------------------------------------------------------------------------------------------
def bar_b2(con, season: int) -> dict:
    built = engine.build(con, season)
    state, _ = engine.start_draft(built, human_seats=[SEAT], settings=LeagueSettings(),
                                  season=season, seed=7, room_seed=1)
    checks, bad = 0, []
    for pos in (None, "RB", "WR", "QB,TE", "K,DST"):
        view = session.board_view(state, SEAT, pos=pos, n=50)
        slim = session.project_view(view, advanced=False)
        adv = session.project_view(view, advanced=True)
        checks += 1
        if list(slim.index) != list(adv.index):
            bad.append(f"rows diverged at pos={pos}")
        if list(slim.columns) != list(session.SLIM_VIEW_COLS):
            bad.append(f"slim columns wrong at pos={pos}")

    # row-select ≡ typed query, on the live board where names are actually distinct
    view = session.board_view(state, SEAT, n=40)
    mismatched = []
    for row in range(len(view)):
        idx = int(view.index[row])
        if session.resolve_pick(state, SEAT, str(idx)) != idx:
            mismatched.append(f"# handle {idx}")
        typed = session.resolve_pick(state, SEAT, str(view.iloc[row]["PLAYER"]))
        found = {typed} if isinstance(typed, int) else {m["index"] for m in typed}
        if idx not in found:
            mismatched.append(str(view.iloc[row]["PLAYER"]))
    return {"bar": "B2 — slim ≡ advanced rows/order; row-select ≡ typed pick",
            "pass": bool(not bad and not mismatched),
            "filters_checked": checks, "rows_checked": len(view),
            "problems": bad[:6], "mismatched": mismatched[:6],
            "slim_columns": list(session.SLIM_VIEW_COLS),
            "advanced_columns": [lbl for _, lbl in session.BOARD_VIEW_COLS]}


# ------------------------------------------------------------------------------------------------
# B3 — the clock changes WHEN picks happen, never WHICH; and it does not promise what it can't meet
# ------------------------------------------------------------------------------------------------
def bar_b3(con, season: int) -> dict:
    built = engine.build(con, season)

    def run(one_at_a_time: bool) -> tuple[list[str], dict]:
        state, meta = engine.start_draft(built, human_seats=[SEAT], settings=LeagueSettings(),
                                         season=season, seed=7, room_seed=1)
        sm = session.seat_map_from(meta)
        opp = session.room_pick_fn(meta, built["risk"])
        per: dict[str, list[float]] = {}
        while not state.is_done() and state.available:
            team = state.team_on_clock()
            if team in state.human_teams:
                _apply_pick(state, team, int(pick_by_adp(state, team, noise=0.0)))
                continue
            t0 = time.perf_counter()
            if one_at_a_time:                                  # the clock's step
                session.advance_one(state, meta, built["risk"], opp)
            else:
                session.advance(state, meta, built["risk"])
            per.setdefault(session.seat_label(team, sm), []).append(time.perf_counter() - t0)
        return [p["player_name"] for p in state.log], per

    clocked, lat = run(True)
    stepped, _ = run(False)
    worst = {k: round(max(v) * 1000, 1) for k, v in sorted(lat.items())}
    worst_seat = max(worst, key=worst.get) if worst else None
    worst_ms = worst.get(worst_seat, 0.0)
    from app.draft_room import MIN_CLOCK_SECONDS
    return {"bar": "B3 — a clocked draft and a stepped draft are the same draft; latency reported",
            "pass": bool(clocked == stepped and worst_ms / 1000.0 <= MIN_CLOCK_SECONDS),
            "logs_identical": clocked == stepped, "n_picks": len(clocked),
            "worst_pick_ms_by_seat": worst, "worst_seat": worst_seat, "worst_ms": worst_ms,
            "clock_floor_s": MIN_CLOCK_SECONDS,
            "note": ("★ The pre-registered worry does not survive the measurement: 14.M expected "
                     "`value_hawk`'s Phase-9 greedy to be too slow for a 5s clock, and the slowest "
                     "single pick in a full draft is ~10 ms. The floor stays as a floor — it is "
                     "what stops the NEXT slow seat overrunning silently — and the app reports "
                     "actual tick cost so the constant cannot go stale unnoticed.")}


# ------------------------------------------------------------------------------------------------
# B4 — both grids agree with the state and with the frozen solver
# ------------------------------------------------------------------------------------------------
def bar_b4(con, season: int, ks=(1, 4)) -> dict:
    built = engine.build(con, season)
    vi = built["value_index"]
    runs = []
    for k in ks:
        mix = None if k <= 1 else ",".join(["balanced"] * (10 - k))
        state, meta = engine.start_draft(built, human_seats=list(range(k)),
                                         settings=LeagueSettings(), season=season, seed=5,
                                         room_seed=2, room_arg=mix or "realistic")
        _finish(state, meta, built["risk"])
        sm = session.seat_map_from(meta)

        pick_grid = session.room_grid(state, sm, by="pick")
        misplaced = [p["player_name"] for p in state.log
                     if p["player_name"] not in pick_grid.iat[int(p["round"]) - 1, int(p["team"])]]
        filled = int((pick_grid != "").to_numpy().sum())

        slot_grid = session.room_grid(state, sm, by="slot", vi=vi)
        slot_rows = [r for r in slot_grid.index if not r.startswith("BN")]
        worst_gap, dupes = 0.0, 0
        for t in range(state.n_teams):
            roster = state.roster(t)
            col = slot_grid.columns[t]
            started = [c for r, c in slot_grid[col].items() if r in slot_rows and c]
            bv = dict(zip(roster["player_name"],
                          roster["base_value"].fillna(0.0), strict=False))
            total = sum(bv.get(c.rsplit(" (", 1)[0], 0.0) for c in started)
            worst_gap = max(worst_gap, abs(total - float(starter_value(roster, vi, state.slots))))
            names = [c for c in slot_grid[col] if c]
            dupes += len(names) - len(set(names))
        runs.append({"k": k, "n_picks": len(state.log), "cells_filled": filled,
                     "misplaced": misplaced[:4], "n_misplaced": len(misplaced),
                     "duplicate_cells": dupes,
                     "worst_startable_gap": round(worst_gap, 9)})
    ok = all(r["n_misplaced"] == 0 and r["cells_filled"] == r["n_picks"]
             and r["duplicate_cells"] == 0 and r["worst_startable_gap"] < 1e-6 for r in runs)
    return {"bar": "B4 — BY PICK re-reads the log exactly; BY SLOT == the frozen startable lineup",
            "pass": bool(ok), "runs": runs,
            "note": ("The slot grid is checked against `starter_value`, which reaches the same "
                     "fill order through a DIFFERENT solver (vectorized `lineup_points_matrix` vs "
                     "the labelled `inseason.lineup` fill). Both consume RosterSlots.flex_groups, "
                     "which is 17.1's single fill-order rule.")}


# ------------------------------------------------------------------------------------------------
# B5 — every column documented; the rail agrees with the state
# ------------------------------------------------------------------------------------------------
def bar_b5(con, season: int) -> dict:
    session.assert_stat_dict_covers_board()
    fields = ("label", "one_line", "what_it_means", "worked_example", "how_to_read_it",
              "provenance")
    thin = [f"{c}.{f}" for c, e in session.STAT_DICT.items() for f in fields
            if not str(e.get(f, "")).strip()]
    # no entry may duplicate another's text — a dictionary of copy-paste is not a dictionary
    examples = Counter(e["worked_example"] for e in session.STAT_DICT.values())
    dupes = [t for t, n in examples.items() if n > 1]

    built = engine.build(con, season)
    state, meta = engine.start_draft(built, human_seats=[SEAT], settings=LeagueSettings(),
                                     season=season, seed=7, room_seed=1)
    session.advance(state, meta, built["risk"])
    for _ in range(5):
        t = state.team_on_clock()
        _apply_pick(state, t, int(pick_by_adp(state, t, noise=0.0)))
        session.advance(state, meta, built["risk"])
    sm = session.seat_map_from(meta)
    grid = session.room_grid(state, sm, by="slot", vi=built["value_index"])
    col = grid.columns[SEAT]
    disagreements = []
    for pos, owed in state.starter_needs(SEAT).items():
        if pos == "FLEX":
            continue
        rows = [r for r in grid.index if r.rstrip("0123456789") == pos]
        openc = sum(1 for r in rows if not grid.at[r, col])
        if openc != owed:
            disagreements.append(f"{pos}: rail {openc} open, state {owed}")

    cli = subprocess.run([sys.executable, "steps/mock_draft.py", "stats", "BUST"],
                         cwd=ROOT, capture_output=True, text=True, timeout=600)
    return {"bar": "B5 — every column documented with a worked example; rail == starter_needs",
            "pass": bool(not thin and not dupes and not disagreements
                         and cli.returncode == 0 and "never seen play" in cli.stdout),
            "n_entries": len(session.STAT_DICT), "empty_fields": thin[:6],
            "duplicate_examples": dupes[:3], "rail_disagreements": disagreements,
            "cli_stats_ok": cli.returncode == 0,
            "note": ("The dictionary is served to the board tooltips, the room grid page and the "
                     "CLI's `stats` command from one object; the app-only `_BOARD_HELP` copy is "
                     "deleted rather than kept in sync.")}


# ------------------------------------------------------------------------------------------------
# the K1 rule: if a display change moved a number, it was not a display change
# ------------------------------------------------------------------------------------------------
def bar_k1() -> dict:
    r = subprocess.run([sys.executable, "steps/session_k1_app.py"], cwd=ROOT,
                       capture_output=True, text=True, timeout=5400)
    sheet = Path("analysis/session_k1_app.json")
    data = json.loads(sheet.read_text()) if sheet.exists() else {}
    return {"bar": "K1 — Session K1's bars still pass unchanged after a display-only session",
            "pass": bool(r.returncode == 0 and data.get("all_pass")),
            "all_pass": data.get("all_pass"),
            "per_bar": {k: v.get("pass") for k, v in (data.get("bars") or {}).items()},
            "tail": r.stdout[-600:] if not data.get("all_pass") else ""}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=None)
    ap.add_argument("--only", default=None, help="b0|b1|b2|b3|b4|b5|flow|k1")
    a = ap.parse_args()

    con = _con()
    season = a.season or engine.live_season(con)
    print(f"=== SESSION K1.5 DONE-BAR — season {season} ===\n")
    plan = {
        "b0": lambda: bar_b0(con, season),
        "b1": bar_b1,
        "b2": lambda: bar_b2(con, season),
        "b3": lambda: bar_b3(con, season),
        "b4": lambda: bar_b4(con, season),
        "b5": lambda: bar_b5(con, season),
        "flow": lambda: bar_flow(con, season),
        "k1": bar_k1,
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
              # ★ T41 — every sheet names the two inputs it was measured under, so a
              # comparator can tell "the world moved" from "the code broke".
              **_sheet_diff.input_stamp(con, season),
              "all_pass": all(r["pass"] for r in results.values()), "bars": results}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str))
    con.close()
    print(f"{'ALL BARS PASS' if report['all_pass'] else 'SOME BARS FAILED'} -> {OUT}")


if __name__ == "__main__":
    main()
