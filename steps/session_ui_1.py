"""Session UI-1 done-bar — *"it looks like a product"*, and its eight pre-registered bars.

    uv run python steps/session_ui_1.py             # every bar
    uv run python steps/session_ui_1.py --only b2   # one of them (writes the .partial sibling)

Writes ``analysis/session_ui_1.json``.

★ **The bars were fixed before the code was written** (`docs/BUILD_PLAN.md` §"Sessions UI-1 … UI-4",
2026-08-01): B0 the K2 sheet unchanged, B1 one palette / five surfaces, B2 prose 68 → ≤ 25, B3 all
seven honesty surfaces still render, B4 the seat strip agrees with the `SeatMap` and the snake, B5
`P(THERE)` is `reach_risk_view`'s own number with no expander in its path, B6 zero `st.json`, FLOW
every page at k ∈ {0, 1, 4} driven by clicking.

★ **The rule that outranks all eight is still K1's:** *if a display change moves a number, it is not
a display change.* UI-1 is a formatting session — it adds a theme, a palette, a strip and a
compression pass — so **B0 re-runs the K2 sheet in full**, which re-runs K1.5's, which re-runs K1's.

⚠ **One deliberate deviation from the "do not touch `session.py`" rule, taken with the user's
explicit decision (2026-08-01).** ``P(THERE)`` is an existing number in a new placement, so
``session.attach_reach`` / ``session.next_pick_info`` / ``session.team_for_pick`` were added *there*
rather than joining a frame inside a renderer. The alternative — a merge in ``app/`` — is the
T18 / F.5 / T27 family this repo has already paid for three times, and it would give the app a
column the CLI could not print. Nothing existing moved, which is what B0 is for.

⚠ **`--only` writes `analysis/session_ui_1.partial.json`, not the sheet.** The house pattern
overwrites the real artifact with a one-bar run, which happened to this session for real: a
30-second `--only b6` against the *K2* runner replaced a committed eight-bar sheet with one bar, and
it had to be restored from git. A partial measurement should not be able to look like a full one.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import engine, palette, post_draft, probe, views  # noqa: E402
from steps import _app_drive, _sheet_diff  # noqa: E402

from fantasy_quant.data import db  # noqa: E402
from fantasy_quant.draft import optimizer, session  # noqa: E402
from fantasy_quant.draft.config import LeagueSettings  # noqa: E402
from fantasy_quant.draft.personalities import PROFILE_FALLBACK  # noqa: E402
from fantasy_quant.draft.simulator import _apply_pick, pick_by_adp  # noqa: E402

OUT = Path("analysis/session_ui_1.json")
PARTIAL = Path("analysis/session_ui_1.partial.json")
APP = Path("app/main.py")
ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
CONFIG = ROOT / ".streamlit" / "config.toml"
SEAT = 5                       # 0-indexed; the seat every sheet since K1.5 is written from
BAR_SIMS = 120
#: K1's B1 constants, re-stated so the pinned control (T41) replays *that* draft, not a lookalike.
K1_SEED, K1_ROOM_SEED, K1_SEATS = 7, 1, "3,7"

#: The census that produced the 68. **It ships here so the before and the after are one
#: instrument** — a compression bar measured with a different ruler than the one that set the
#: target is not a measurement, it is a coincidence. `st.caption` + the four alert primitives; the
#: 28 `st.markdown` blocks are excluded because they are mostly headers and labels, and 37 + 31 is
#: exactly the 68 `docs/UI-PLAN.md` §3.1 reports.
PROSE_RE = re.compile(r"\.(caption|warning|info|error|success)\(")
PROSE_BEFORE = 68              # UI-PLAN §3.1, re-derived from git in bar B2 rather than trusted
PROSE_TARGET = 25              # the user's call, 2026-08-01
#: ★★ **The commit "before" means, pinned — Session K2, the tree UI-1 started from.**
#: B2 read its baseline from ``git show HEAD:``, which was the *pre*-UI-1 app for exactly as long as
#: UI-1 stayed uncommitted. The moment the work landed (``c712f86``) the baseline became the
#: compressed app and the census read **24 → 24, removed: 0** — a compression bar reporting that no
#: compression happened, on the session that did it. Third member of the family this repo keeps
#: meeting: *a stale reference is not a control* (seat-map terms), T41 for the board, and this for
#: the diff. A baseline is a **fixed point in history**; anything that moves with `HEAD` is a moving
#: target wearing a baseline's name.
PROSE_BEFORE_REF = "5eff21d"


def _con():
    return db.connect(read_only=True)


def _finish(state, meta, risk) -> None:
    session.advance(state, meta, risk)
    while not state.is_done() and state.available:
        t = state.team_on_clock()
        _apply_pick(state, t, int(pick_by_adp(state, t, noise=0.0)))
        session.advance(state, meta, risk)


def _draft(built, season: int, k: int = 1, *, finish: bool = True):
    """The same draft constructor K2's sheet uses, so the two sheets describe the same rooms."""
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


def _apptest(page: str, state=None, meta=None, built=None, odds=None, prov=None, **session_state):
    """An ``AppTest`` on one page with a draft already in session state."""
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


def _all_text(at) -> str:
    """Every rendered string, from **every** render primitive.

    ⚠ K2's lesson applied to this session's own instrument: `st.badge` renders as *markdown*
    (`:green-badge[…]`), popover and expander and tab bodies render as their children, and a scrape
    that read only `markdown`/`caption` would report a compressed honesty surface as missing from a
    page that shows it. *A bar failing for the wrong reason is a bar nobody trusts the next time it
    fails* — and after a compression pass that is precisely the bar most likely to fail.
    """
    parts = []
    for kind in ("markdown", "caption", "warning", "info", "success", "error", "header",
                 "subheader", "title", "text", "metric"):
        for e in getattr(at, kind, []):
            parts.append(str(getattr(e, "value", "")))
            for attr in ("label", "delta", "help"):
                v = getattr(e, attr, None)
                if v:
                    parts.append(str(v))
    for e in at.get("html"):
        parts.append(str(getattr(e.proto, "body", "")))
    return " ".join(parts)


# ------------------------------------------------------------------------------------------------
# B1 — one palette, five surfaces, zero second copies
# ------------------------------------------------------------------------------------------------
def _hex_occurrences(path: Path, hexes: list[str]) -> int:
    """How many palette hexes appear in ``path`` as a **value**, ignoring prose about them.

    ⚠ Written this way because the naive text count failed on its first run and was **right to**:
    it reported 9 in ``palette.py``, and the three extras were the module's own docstring explaining
    why full-strength ``#0072B2`` on a 35 %-``#0072B2`` tint is a contrast ratio of 2.4. *Prose that
    names a colour is not a second copy of it; a string literal the code evaluates is.* Comments
    never reach the AST, and docstrings are excluded explicitly — so what is counted is exactly the
    thing the claim is about.
    """
    import ast

    tree = ast.parse(path.read_text())
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            body = getattr(node, "body", [])
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                docstrings.add(id(body[0].value))
    total = 0
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in docstrings):
            total += sum(node.value.upper().count(h.upper()) for h in hexes)
    return total


def bar_b1(con, season: int) -> dict:
    """★ Not "the colours look right" — *the six hex strings exist once and reach five surfaces.*

    The failure mode for a palette is never that it is wrong on day one; it is that it is right in
    four places and stale in the fifth. So the bar has three parts: the strings appear exactly once
    in ``app/``, the one unavoidable duplicate (``.streamlit/config.toml``, which Streamlit reads
    before any of our Python runs) is *asserted equal* rather than hoped about, and driving the app
    records all five surfaces through :data:`app.palette.STYLED`.
    """
    hexes = list(palette.POSITION_COLORS.values())
    counts = {f.name: _hex_occurrences(f, hexes) for f in sorted(APP_DIR.glob("*.py"))}
    counts = {k: v for k, v in counts.items() if v}
    single_home = counts == {"palette.py": len(hexes)}

    cfg = tomllib.loads(CONFIG.read_text())
    cfg_colors = [str(c).upper() for c in cfg["theme"]["chartCategoricalColors"]]
    config_agrees = cfg_colors == [h.upper() for h in hexes]
    base_dark = cfg["theme"]["base"] == "dark"

    # every chip is legible — the palette is a colourblind-safe set, and a set chosen for one
    # accessibility property should not fail a different one
    contrast = {p: round(palette.contrast_ratio(h, palette.ink_for(h)), 2)
                for p, h in palette.POSITION_COLORS.items()}
    aa = min(contrast.values()) >= 4.5

    # The five surfaces need two different drafts, and finding that out is what the first run of
    # this bar was for. ⚠ **A mid-draft state at k=1 has an EMPTY log** — the human seat is T1, so
    # `advance` makes zero picks before handing over — and an empty log renders "No picks yet",
    # not a table. The bar reported four of five surfaces coloured and the missing one was not a
    # rendering defect at all; it was a fixture that could not exhibit the thing being measured.
    # *A surface with no rows is not a surface that failed to colour.*
    built = engine.build(con, season)
    live, live_meta = _draft(built, season, k=1, finish=False)
    done, done_meta = _draft(built, season, k=1)
    palette.reset()
    exceptions = []
    for page, s, m in (("draft", live, live_meta), ("grid", done, done_meta),
                       ("post", done, done_meta)):
        at = _apptest(page, s, m, built)
        at.run()
        exceptions += [f"{page}: {str(e.value)[:200]}" for e in at.exception]
        if page == "grid":
            # the **log** is behind a radio, so a bar that only loads the page never sees it. A
            # surface reachable in one click is still a surface; drive the click.
            at.radio[0].set_value("Log").run()
            exceptions += [f"grid/log: {str(e.value)[:200]}" for e in at.exception]
    styled = palette.styled()
    surfaces_ok = all(styled.get(s, 0) > 0 for s in palette.SURFACES) and not exceptions

    return {"bar": "B1 — one palette constant, five surfaces, zero second copies",
            "pass": bool(single_home and config_agrees and base_dark and aa and surfaces_ok),
            "palette": dict(palette.POSITION_COLORS),
            "hex_occurrences_per_app_file": counts,
            "single_home_in_app": single_home,
            "config_toml_matches_palette": config_agrees, "theme_base": cfg["theme"]["base"],
            "chip_contrast_ratios": contrast, "min_contrast": min(contrast.values()),
            "wcag_aa_all_chips": aa,
            "required_surfaces": list(palette.SURFACES),
            "styled_surfaces": styled,
            "all_five_surfaces_styled": all(styled.get(s, 0) > 0 for s in palette.SURFACES),
            "n_exceptions": len(exceptions), "exceptions": exceptions[:4],
            "note": ("`.streamlit/config.toml` is the one place the hex strings are duplicated "
                     "outside `app/palette.py` and the duplication is unavoidable — a TOML file is "
                     "read before any of our Python runs, so it cannot import a constant. The bar "
                     "therefore asserts the two agree rather than pretending there is one copy. "
                     "A duplication you assert is a duplication; a duplication you hope about is "
                     "a bug.")}


# ------------------------------------------------------------------------------------------------
# B2 — the prose census, before and after, on one instrument
# ------------------------------------------------------------------------------------------------
def _census(read) -> dict[str, int]:
    out = {}
    for f in sorted(APP_DIR.glob("*.py")):
        text = read(f)
        if text is None:
            continue
        n = len(PROSE_RE.findall(text))
        if n:
            out[f.name] = n
    return out


def bar_b2() -> dict:
    """68 → ≤ 25, counted **the same way both times**, with the "before" read out of git.

    ⚠ The compression is only honest because B3 is paired with it. Deleting a paragraph passes this
    bar; deleting an honesty surface passes it too, which is why the two bars ship together and why
    B3 asserts by driving the app rather than by reading the diff.

    ⚠ **The baseline is a commit, not ``HEAD``** — see :data:`PROSE_BEFORE_REF`. Reading it from
    ``HEAD`` made the bar true only while the session was uncommitted, and self-refuting afterwards.
    """
    def from_git(f: Path):
        r = subprocess.run(["git", "show", f"{PROSE_BEFORE_REF}:app/{f.name}"], cwd=ROOT,
                           capture_output=True, text=True)
        return r.stdout if r.returncode == 0 else None

    before = _census(from_git)
    after = _census(lambda f: f.read_text())
    n_before, n_after = sum(before.values()), sum(after.values())
    return {"bar": f"B2 — prose blocks {PROSE_BEFORE} → ≤ {PROSE_TARGET}, one census both ways",
            "pass": bool(n_after <= PROSE_TARGET and n_before == PROSE_BEFORE),
            "before_total": n_before, "after_total": n_after, "target": PROSE_TARGET,
            "before_reproduces_ui_plan_68": n_before == PROSE_BEFORE,
            "before_by_file": before, "after_by_file": after,
            "before_ref": PROSE_BEFORE_REF,
            "removed": n_before - n_after,
            "note": ("The census is `st.caption` + the four alert primitives — 37 + 31 = the 68 in "
                     "UI-PLAN §3.1. `st.markdown` is excluded because those 28 blocks are mostly "
                     "headers and labels. The 'before' is read from `git show HEAD:` rather than "
                     "hard-coded, so the two numbers come off one ruler.")}


# ------------------------------------------------------------------------------------------------
# B3 — all seven honesty surfaces still render, asserted by DRIVING
# ------------------------------------------------------------------------------------------------
def bar_b3(con, season: int) -> dict:
    """★ **The bar most likely to be argued with, and the reason the compression is allowed.**

    A compression pass fails silently: a surface that stops rendering looks exactly like a surface
    that got tidier, and both look like a smaller diff. So each of the seven is checked by *running
    the page it lives on and reading what came out*, including popover and expander and tab bodies
    and `st.badge` labels — the primitives a naive scrape misses.
    """
    built = engine.build(con, season)
    found: dict[str, bool] = {}
    detail: dict[str, str] = {}

    # 1 — the lockbox banner, BOTH branches. Both describe supported leagues; the difference is
    #     evidence, not capability, so a bar that only checks the green one has checked nothing.
    at = _apptest("settings", settings=LeagueSettings())
    at.run()
    txt = _all_text(at)
    ok_validated = "LOCKBOX-VALIDATED" in txt and "0.088" in txt
    at2 = _apptest("settings", settings=LeagueSettings(superflex=1))
    at2.run()
    txt2 = _all_text(at2)
    ok_not = "NOT LOCKBOX-VALIDATED" in txt2 and "no out-of-sample claim" in txt2.lower()
    found["lockbox_both_branches"] = bool(ok_validated and ok_not)
    detail["lockbox_both_branches"] = f"validated={ok_validated} not_validated={ok_not}"

    # 2/3 — COIN and the censored floor, on the board's RANGES view.
    # ⚠ **The row count is part of the check, not a detail.** At the page's default 40 rows the
    # live board has no censored floor on screen at all — they are deep-board rows (59 % past ADP
    # 100) — so the first run of this bar reported the surface missing from a page that renders it
    # correctly whenever there is one to render. The slider is driven to a depth where the thing
    # being asserted exists.
    state, meta = _draft(built, season, k=1, finish=False)
    atb = _apptest("board", state, meta, built, board_mode="RANGES")
    atb.run()
    atb.slider[0].set_value(200).run()
    board_txt = _all_text(atb)
    found["coin_overlap"] = "pairs overlap" in board_txt
    found["censored_floor"] = "censored floor" in board_txt.lower()
    detail["censored_floor"] = board_txt[max(board_txt.lower().find("censored"), 0):][:90]

    # 4/5 — T22 (blank is not zero) and T31 (the level cap) live in STAT_DICT, which the room
    #       page's stat dictionary renders in full. ⚠ It is the **third** radio option, so loading
    #       the page is not enough — same lesson as the log in B1.
    atg = _apptest("grid", state, meta, built)
    atg.run()
    atg.radio[0].set_value("Stat dictionary").run()
    grid_txt = _all_text(atg)
    found["t22_blank_is_not_zero"] = ("never busts" in grid_txt.lower()
                                      and "never booms" in grid_txt.lower())
    found["t31_level_cap"] = ("t31" in grid_txt.lower()
                              and "extrapolating below" in grid_txt.lower())

    # 6/7 — the k-seats rule and the printed grade weights, on the post-draft page at k = 4
    s4, m4 = _draft(built, season, k=4)
    sm4 = session.seat_map_from(m4)
    odds4, prov4 = session.odds_table(con, s4, m4, sm4, sims=BAR_SIMS)
    atp = _apptest("post", s4, m4, built, odds4, prov4)
    atp.run()
    post_txt = _all_text(atp)
    found["k_seats_one_observation"] = "ONE observation" in post_txt
    weights = tuple(int(w) for w in session.GRADE_WEIGHTS.values())
    found["printed_grade_weights"] = (str(weights) in post_txt
                                      and "nothing validates" in post_txt.lower())
    detail["printed_grade_weights"] = str(weights)

    exceptions = [str(e.value)[:200] for a in (at, at2, atb, atg, atp) for e in a.exception]
    return {"bar": "B3 — all seven honesty surfaces still render after the compression",
            "pass": bool(all(found.values()) and not exceptions),
            "surfaces": found, "detail": detail,
            "n_exceptions": len(exceptions), "exceptions": exceptions[:3],
            "note": ("Scraped from every render primitive, not markdown/caption only: `st.badge` "
                     "renders as markdown, and popover / expander / tab bodies render as their "
                     "children. Compression moved most of these into popovers and chips — a scrape "
                     "that could not see those would fail this bar for the wrong reason.")}


# ------------------------------------------------------------------------------------------------
# B4 — the seat strip agrees with the SeatMap and with the snake
# ------------------------------------------------------------------------------------------------
def bar_b4(con, season: int) -> dict:
    """★ **The exhaustive control is the point**, not the chip layout.

    ``session.team_for_pick`` is a *second copy* of ``DraftState.team_on_clock``'s geometry, and the
    only thing that makes a second copy acceptable in this repo is 16.17's precedent: write it once
    and difference it against the original **exhaustively**. So this replays a whole draft and
    asserts the two agree at every one of the 150 picks, then checks the strip's content against the
    seat map and the next-pick badge against the optimizer's own ``_next_own_pick``.
    """
    built = engine.build(con, season)
    problems: list[str] = []

    # the exhaustive control: team_for_pick == team_on_clock at every pick of a full draft
    state, meta = _draft(built, season, k=1, finish=False)
    checked = 0
    replay, _ = engine.start_draft(built, human_seats=[SEAT], settings=LeagueSettings(),
                                   season=season, seed=5, room_seed=2)
    # ⚠ **stepped pick-by-pick, never through `session.advance`.** The first version of this loop
    # advanced the room between checks, so it landed on the human's seat once a round and reported
    # "15 picks checked" while calling itself exhaustive. 15 of 150 is a sample; the whole point of
    # allowing a second copy of the snake formula is that the difference is *complete*.
    while not replay.is_done() and replay.available:
        want = replay.team_on_clock()
        got = session.team_for_pick(replay, replay.overall_pick)
        checked += 1
        if want != got:
            problems.append(f"pick {replay.overall_pick}: {want} != {got}")
        _apply_pick(replay, want, int(pick_by_adp(replay, want, noise=0.0)))
    complete = checked == replay.n_teams * replay.rounds
    out_of_range = (session.team_for_pick(replay, 0) is None
                    and session.team_for_pick(replay, replay.n_teams * replay.rounds + 1) is None)

    runs = []
    for k in (1, 4):
        s, m = _draft(built, season, k=k, finish=False)
        sm = session.seat_map_from(m)
        rows = views.seat_strip_rows(s, m, sm)
        order_ok = [r["team"] for r in rows] == list(range(1, s.n_teams + 1))
        labels_ok = all(r["label"] == session.seat_label(r["seat"], sm) for r in rows)
        clock = [r["seat"] for r in rows if r["on_clock"]]
        clock_ok = clock == [s.team_on_clock()]
        deck_want = session.team_for_pick(s, s.overall_pick + 1)
        deck = [r["seat"] for r in rows if r["on_deck"]]
        deck_ok = deck == ([deck_want] if deck_want != s.team_on_clock() else [])
        you_ok = {r["seat"] for r in rows if r["you"]} == set(sm.human_teams)

        info = session.next_pick_info(s, SEAT if k == 1 else 0)
        seat = SEAT if k == 1 else 0
        last = s.n_teams * s.rounds
        want_next = optimizer._next_own_pick(s.overall_pick, seat, s.n_teams, last)
        next_ok = info["next_pick"] == (None if want_next is None else int(want_next))
        # ...and the window the availability readout sizes itself with is the SAME number
        window_ok = session.reach_risk_view(s, m, seat, n=5).attrs["window_picks"] \
            == info["picks_away"]

        at = _apptest("draft", s, m, built)
        at.run()
        html = [str(e.proto.body) for e in at.get("html")]
        strip = html[0] if html else ""
        chips_in_order = all(f">T{t}" in strip for t in range(1, s.n_teams + 1))
        one_strip = len(html) == 1
        if not (order_ok and labels_ok and clock_ok and deck_ok and you_ok and next_ok
                and window_ok and chips_in_order and one_strip):
            problems.append(f"k={k}: strip/next-pick mismatch")
        runs.append({"k": k, "chip_order_is_seat_order": order_ok,
                     "labels_from_seat_map": labels_ok,
                     "exactly_one_on_the_clock": clock_ok, "on_deck_is_team_for_pick": deck_ok,
                     "your_seats_marked": you_ok, "next_pick_is_optimizers": next_ok,
                     "window_matches_reach_readout": window_ok,
                     "every_chip_rendered": chips_in_order, "one_strip_element": one_strip,
                     "next_pick": info["next_pick"], "picks_away": info["picks_away"]})

    return {"bar": "B4 — the seat strip is the SeatMap's order and the optimizer's own next pick",
            "pass": bool(not problems and complete and out_of_range),
            "picks_checked_against_team_on_clock": checked,
            "every_pick_of_a_full_draft_checked": complete,
            "team_for_pick_mismatches": problems[:4],
            "out_of_range_returns_none": out_of_range,
            "runs": runs,
            "note": ("`team_for_pick` duplicates the snake formula so the strip can say who is on "
                     "*deck*, one pick ahead of what `team_on_clock` answers. The K1.5 seat-map "
                     "defect was that arithmetic written four times and correct in three; the fix "
                     "that stuck was an exhaustive difference, so that is what this runs.")}


# ------------------------------------------------------------------------------------------------
# B5 — P(THERE) is reach_risk_view's number, and no expander is in its path
# ------------------------------------------------------------------------------------------------
def bar_b5(con, season: int) -> dict:
    """One derivation, two placements — the slim board's column and the rail's panel.

    ⚠ **The expander half is T37, and it is the whole reason step 0 exists.** The readout shipped
    inside ``st.expander(..., expanded=False)`` directly beneath a docstring arguing that it must
    not, for a whole session, while every K2 bar passed. A docstring is not a guard. The bar is that
    the draft room renders **no expander at all**, which is a claim a future edit cannot satisfy by
    accident.
    """
    built = engine.build(con, season)
    state, meta = _draft(built, season, k=1, finish=False)
    reach = session.reach_risk_view(state, meta, SEAT, n=25)

    # the column IS the readout's number, row for row, joined on the board index
    view = session.board_view(state, SEAT, n=40, risk=built["risk"])
    slim = session.attach_reach(session.project_view(view, mode="slim"), reach)
    want = pd.Series(reach["p_available"].to_numpy(float),
                     index=pd.Index(reach["board_index"].astype(int)))
    got = slim[session.REACH_COL]
    covered = got.index.intersection(want.index)
    identical = bool(np.allclose(got.loc[covered].to_numpy(float),
                                 want.loc[covered].to_numpy(float)))
    # ⚠ rows the readout did not simulate stay NaN. T22's rule with the other sign: a player nobody
    # simulated is not a player with a 0 % chance of surviving.
    uncovered = got.index.difference(want.index)
    nan_ok = bool(len(uncovered) == 0 or got.loc[uncovered].isna().all())

    at = _apptest("draft", state, meta, built)
    at.run()
    frames = [f.value for f in at.dataframe]
    on_slim = [f for f in frames if session.REACH_COL in list(getattr(f, "columns", []))
               and "PROJ" in list(getattr(f, "columns", []))]
    in_rail = [f for f in frames if session.REACH_COL in list(getattr(f, "columns", []))
               and "BASELINE" in list(getattr(f, "columns", []))]
    n_expanders = len(at.expander)
    documented = session.REACH_COL in session.STAT_DICT

    # ...and the CLI shows the same column (K2's rule: a column the terminal cannot show is a
    # documented column with no behaviour behind it)
    cli_has = session.REACH_COL in _cli_slim_columns()

    return {"bar": "B5 — P(THERE) on the slim board IS reach_risk_view, and no expander hides it",
            "pass": bool(identical and nan_ok and on_slim and in_rail and n_expanders == 0
                         and documented and cli_has),
            "rows_compared": int(len(covered)), "values_identical": identical,
            "uncovered_rows_stay_nan": nan_ok, "uncovered_rows": int(len(uncovered)),
            "slim_board_carries_column": bool(on_slim),
            "rail_panel_renders": bool(in_rail),
            "expanders_on_the_draft_page": n_expanders,
            "documented_in_stat_dict": documented,
            "in_cli_slim_board": cli_has,
            "window_picks": int(reach.attrs["window_picks"]),
            "note": ("T37 closed: the draft room now renders zero expanders. The readout is our "
                     "single most differentiated number — a validated P(available) with an "
                     "un-drifted baseline, which FantasyPros' Pick Predictor has neither of — and "
                     "it shipped collapsed for a session.")}


def _cli_slim_columns() -> list[str]:
    """The terminal board's slim columns, read from the CLI's own format map."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("_mock_cli", ROOT / "steps" / "mock_draft.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return list(mod._VIEW_FMT["slim"])


# ------------------------------------------------------------------------------------------------
# B6 — zero st.json, and what was dumped is now a titled table
# ------------------------------------------------------------------------------------------------
def _json_calls(path: Path) -> int:
    """``.json(...)`` **calls** in ``path``, from the AST.

    ⚠ A `re.findall(r"\\.json\\(")` reported 1 here and was wrong: the hit was the comment recording
    what T38 replaced (`c1.json(frames["elite"])`). Second time in one bar sheet that a text scan
    counted a mention as an occurrence — B1's hex census had it too. *A grep does not know the
    difference between doing a thing and describing it.*
    """
    import ast

    return sum(1 for node in ast.walk(ast.parse(path.read_text()))
               if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
               and node.func.attr == "json")


def bar_b6(con, season: int) -> dict:
    """T38. A raw JSON dump on the page whose job is to be a report card."""
    calls = {f.name: _json_calls(f) for f in sorted(APP_DIR.glob("*.py"))}
    calls = {k: v for k, v in calls.items() if v}
    total = sum(calls.values())

    built = engine.build(con, season)
    state, meta = _draft(built, season, k=1)
    sm = session.seat_map_from(meta)
    odds, prov = session.odds_table(con, state, meta, sm, sims=BAR_SIMS)
    at = _apptest("post", state, meta, built, odds, prov)
    at.run()
    n_json = len(at.json)
    frames = [f.value for f in at.dataframe]
    elite = [f for f in frames
             if len(getattr(f, "columns", [])) == 2
             and f.iloc[:, 0].astype(str).str.contains("Consensus top-12").any()]
    # the table says the same things the dump did, in the same units
    table = views.elite_fall_table(session.drift_frames(state, meta, sm)["elite"])
    return {"bar": "B6 — zero st.json in app/; the elite-fall dump is a titled table",
            "pass": bool(total == 0 and n_json == 0 and elite),
            "st_json_call_sites": calls,
            "st_json_total": total, "json_elements_rendered": n_json,
            "elite_table_rendered": bool(elite),
            "elite_table_rows": table.iloc[:, 0].tolist(),
            "note": ("The dump was not wrong, it was unreadable — and it survived into 14.N "
                     "because K2 *moved* the readouts from the room page rather than rewriting "
                     "them. A defect that changes address without being looked at is the cheapest "
                     "kind to keep.")}


# ------------------------------------------------------------------------------------------------
# FLOW — every page, zero exceptions, k ∈ {0,1,4}, on a draft advanced by clicking
# ------------------------------------------------------------------------------------------------
def bar_flow(con, season: int) -> dict:
    """★ K1's rule and K1.5's, carried: *an import bar and a use bar are different claims.*

    ⚠ **What this cannot drive, stated rather than skipped (T36).** ``AppTest`` cannot make a
    selection in an ``st.dataframe`` — ``on_select`` is a client event — so the row-select path and
    the player modal are reachable here only through the pieces around them. FLOW covers content
    and every other route; it does not cover that click, and saying so is the difference between a
    gap and a false claim.
    """
    built = engine.build(con, season)
    pages, page_errors = {}, []
    runs = []
    for k in (0, 1, 4):
        state, meta = _draft(built, season, k=k)
        sm = session.seat_map_from(meta)
        odds, prov = session.odds_table(con, state, meta, sm, sims=BAR_SIMS)
        probe.reset()
        from app.main import PAGE_SPECS
        for name in PAGE_SPECS:
            at = _apptest(name, state, meta, built, odds, prov)
            at.run()
            pages[f"k{k}:{name}"] = len(at.exception)
            page_errors += [f"k={k} {name}: {str(e.value)[:200]}" for e in at.exception]
        runs.append({"k": k, "pages": len(PAGE_SPECS), "page_bodies": probe.snapshot()})

    # ...and a pick made by clicking still completes a draft and lands on 14.N
    state2, meta2 = engine.start_draft(built, human_seats=[SEAT], settings=LeagueSettings(),
                                       season=season, seed=5, room_seed=2)
    session.advance(state2, meta2, built["risk"])
    while not state2.is_done() and state2.available:
        t = state2.team_on_clock()
        if t == SEAT and len(state2.roster(SEAT)) == state2.rounds - 1:
            break
        _apply_pick(state2, t, int(pick_by_adp(state2, t, noise=0.0)))
        session.advance(state2, meta2, built["risk"])
    before = len(state2.log)
    a = _apptest("draft", state2, meta2, built)
    a.run()
    # UI-3 A7 — one pick path (see `steps/_app_drive.py`); this used to click the quick row.
    clicked, a = _app_drive.pick_by_clicking(a)
    after = a.session_state["draft"]["state"]
    completed = after.is_done() or not after.available
    arrived = ("_arrived_post_draft" in a.session_state
               and bool(a.session_state["_arrived_post_draft"]))
    exceptions = page_errors + [str(e.value)[:200] for e in a.exception]

    return {"bar": "FLOW — all six pages render at k ∈ {0,1,4}; a pick made by clicking completes",
            "pass": bool(not exceptions and clicked and completed and arrived),
            "pages_rendered": pages, "runs": runs,
            "picks_before": before, "picks_after": len(after.log),
            "completed_by_click": completed, "navigated_to_post_draft": arrived,
            "clicked": clicked, "pick_path": "selectbox -> strip confirm",
            "n_exceptions": len(exceptions), "exceptions": exceptions[:4],
            "modal_click_not_drivable": True}


# ------------------------------------------------------------------------------------------------
# B0 — the K1 rule: nothing this session touched moved a number
# ------------------------------------------------------------------------------------------------
def _committed_room(committed: dict, n_humans: int) -> tuple[list[str], str]:
    """The room a committed sheet was measured under, at the seat count the control needs.

    ★ **Read from the sheet's own stamp, never assumed.** A sheet written from 2026-08-17 carries
    ``room_mix``; whether it contains ``fitted_manager`` is the whole question, because that is the
    seat MM-1a added. For the pre-stamp sheets the answer is known from the register — they were
    measured before 08-05 — and the fallback says so **in the artifact** rather than in a comment.

    It is not hard-coded either way: 16.18's own gate degrades a ``requires_profile`` seat to
    ``balanced`` and its docstring promises that an uncovered season reproduces the pre-16.18 room
    *bit-for-bit*, so this asks the shipped code for the old room instead of asserting what it was.
    """
    stamp = _sheet_diff.sheet_room(committed)
    had_fitted = ("fitted_manager" in stamp) if stamp else False
    source = "the sheet's room_mix stamp" if stamp else "pre-MM-1a (sheet predates the stamp)"
    room = list(session.realistic_mix(int(n_humans)))
    if not had_fitted:
        room = [PROFILE_FALLBACK if n == "fitted_manager" else n for n in room]
    return room, source


def _pinned_control(con, season: int, committed_vintage: str | None) -> dict:
    """★★ **T41's other half: pin the input, do not merely report it.**

    Classifying a moved leaf as *the board moved* is a hypothesis. This is the test of it — the
    **same code** re-run on the **committed sheet's board** (``build_board(..., asof=)``, VH.0) and
    the **committed sheet's room** (16.18's gate, via a season the profile does not cover), asked to
    reproduce K1's ``app_summary`` **bit-for-bit**. If it does, every leaf that moved on the live
    board moved because the world moved. If it does not, the classification is worthless and B0 says
    so, which is the failure mode the register entry cares about: *a control that cannot tell "the
    world moved" from "the code broke".*

    ⚠ It reproduces the draft K1's B1 builds — same seats, same seeds, same constructor — because
    that block is where 122 of the 145 unclassified leaves lived.
    """
    committed = json.loads(
        subprocess.run(["git", "show", "HEAD:analysis/session_k1_app.json"], cwd=ROOT,
                       capture_output=True, text=True).stdout or "{}")
    want = ((committed.get("bars") or {}).get("b1") or {}).get("app_summary")
    vintage = committed and _sheet_diff.sheet_vintage(committed)
    asof = _asof_for(vintage)
    if not want or not asof:
        return {"ran": False, "reason": f"committed K1 sheet has no reproducible input "
                                        f"(app_summary={bool(want)}, vintage={vintage!r})"}
    built = engine.build(con, season, asof=asof)
    seats = session.parse_seats(K1_SEATS)
    room, room_source = _committed_room(committed, len(seats))   # K1's B1 drives TWO seats -> eight
    state, meta = engine.start_draft(built, human_seats=seats, settings=LeagueSettings(),
                                     season=season, seed=K1_SEED, room_seed=K1_ROOM_SEED,
                                     room_arg=",".join(room))
    _finish(state, meta, built["risk"])
    got = session.summary_table(state, session.seat_map_from(meta),
                                built["value_index"]).round(4).to_dict("records")
    differing = [f"{i}.{k}" for i, (a, b) in enumerate(zip(want, got, strict=False))
                 for k in a if a.get(k) != b.get(k)]
    return {"ran": True, "pinned_vintage": vintage, "asof": asof,
            "pinned_room": room, "pinned_room_source": room_source,
            "live_room": _sheet_diff.room_stamp(),
            "rows_compared": min(len(want), len(got)), "n_rows_committed": len(want),
            "reproduced_bit_for_bit": not differing and len(want) == len(got),
            "differing": differing[:12],
            "note": ("The committed sheet's board and room, replayed by today's code. This is "
                     "what licenses the `vintage_changed` / `room_changed` classification below; "
                     "without it those buckets are a guess with a name on it.")}


def _asof_for(vintage: str | None) -> str | None:
    """``'ffc-20260801'`` -> ``'2026-08-01'``, the date ``resolve_board(asof=)`` wants."""
    if not vintage or "-" not in vintage:
        return None
    d = vintage.rsplit("-", 1)[-1]
    return f"{d[:4]}-{d[4:6]}-{d[6:]}" if len(d) == 8 and d.isdigit() else None


def bar_b0(con, season: int) -> dict:
    """*If a display change moves a number, it is not a display change.*

    UI-1 adds a theme, a palette, a strip, a compression pass and one attached column. It refits
    nothing and re-reads no lockbox, so the K2 sheet must come back passing — and K2's own B0
    re-runs K1.5's sheet, which re-runs K1's, so this is three committed sheets deep.

    ⚠ **Passing is not the same as unchanged, and the difference is where a display session hides.**
    22 leaves of 538 did move across the three sheets, and *every one of them being harmless is a
    claim that deserves an instrument rather than a sentence*. So the second half of this bar diffs
    each sheet against ``git show HEAD:`` and requires every changed leaf to fall under a named
    allowance. **An unclassified move fails the bar.**

    ★★ **T41 (2026-08-17).** Two inputs moved under these sheets between 08-01 and 08-17 — the
    Stage-0 chore banked a new ADP board, and MM-1a seated ``fitted_manager`` in the room — and the
    comparator had no way to say either. It does now: each sheet stamps its board vintage and room
    mix, board- and room-driven leaves land in named buckets **only when the stamps actually
    moved**, gates are never attributable, and :func:`_pinned_control` re-runs the old inputs
    through today's code to prove the attribution rather than assert it.
    """
    r = subprocess.run([sys.executable, "steps/session_k2_app.py"], cwd=ROOT,
                       capture_output=True, text=True, timeout=14400)
    sheet = ROOT / "analysis" / "session_k2_app.json"
    data = json.loads(sheet.read_text()) if sheet.exists() else {}
    per_bar = {k: v.get("pass") for k, v in (data.get("bars") or {}).items()}
    nested = data.get("bars", {}).get("b0", {})

    now_v, now_r = _sheet_diff.board_stamp(con, season), _sheet_diff.room_stamp()
    moves = {}
    for p in ("analysis/session_k1_app.json", "analysis/session_k1_5_app.json",
              "analysis/session_k2_app.json"):
        head = subprocess.run(["git", "show", f"HEAD:{p}"], cwd=ROOT, capture_output=True,
                              text=True)
        doc = json.loads(head.stdout) if head.returncode == 0 else {}
        moves[p] = _sheet_diff.classify_moves(
            p, vintage=(_sheet_diff.sheet_vintage(doc), now_v),
            room=(_sheet_diff.sheet_room(doc), now_r))
    clean = all(not m.get("unclassified") for m in moves.values())
    pinned = _pinned_control(con, season, now_v)
    attributed = bool(pinned.get("reproduced_bit_for_bit"))
    inputs_moved = any((m.get("input_bucket") or "") != "" for m in moves.values())
    return {"bar": "B0 — the K2 sheet re-runs (K1.5 and K1 nested), and every moved leaf is named",
            # ★ when an input moved, the classification is only believed if the pinned control
            # reproduced the old measurement. A named bucket is not evidence; the replay is.
            "pass": bool(data.get("all_pass") and clean and (attributed or not inputs_moved)),
            "returncode": r.returncode, "k2_all_pass": data.get("all_pass"),
            "k2_per_bar": per_bar,
            "k1_5_all_pass": nested.get("k1_5", {}).get("all_pass"),
            "k1_all_pass": nested.get("k1_nested", {}).get("all_pass"),
            "every_moved_leaf_classified": clean,
            "board_vintage": now_v, "room_mix": now_r,
            "pinned_control": pinned,
            "moves_vs_committed": moves,
            "note": ("No **model** number moved: every 'differing: 0' / '150 of 150 identical' / "
                     "Brier / grade / cliff / probability field is untouched. What moved is the "
                     "count of rendered elements (UI-1 adds a table to 14.N and a panel to the "
                     "rail), the OS-entropy seeds T34 deliberately draws fresh, wall-clock "
                     "timings, the stat dictionary gaining `P(THERE)` — and, from 2026-08-17, the "
                     "two *inputs*: a newer ADP board and MM-1a's room."),
            "tail": "" if data.get("all_pass") else r.stdout[-1500:]}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=None)
    ap.add_argument("--only", default=None, help="b0|b1|b2|b3|b4|b5|b6|flow")
    a = ap.parse_args()

    con = _con()
    season = a.season or engine.live_season(con)
    print(f"=== SESSION UI-1 DONE-BAR — season {season} ===\n")
    plan = {
        "b1": lambda: bar_b1(con, season),
        "b2": bar_b2,
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

    report = {"season": season, "seat": SEAT + 1, "bar_sims": BAR_SIMS,
              "prose_before": PROSE_BEFORE, "prose_target": PROSE_TARGET,
              "palette": dict(palette.POSITION_COLORS),
              # ★ T41 — the sheet says which inputs produced it. A comparator can then tell "the
              # world moved" from "the code broke"; without these two leaves it cannot, and it
              # said the alarming thing both times for a fortnight.
              **_sheet_diff.input_stamp(con, season),
              "all_pass": all(r["pass"] for r in results.values()), "bars": results}
    # ⚠ a partial run writes a partial artifact. See the module docstring.
    out = OUT if not a.only else PARTIAL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str))
    con.close()
    print(f"{'ALL BARS PASS' if report['all_pass'] else 'SOME BARS FAILED'} -> {out}")


if __name__ == "__main__":
    main()
