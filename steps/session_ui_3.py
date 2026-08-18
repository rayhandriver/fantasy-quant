"""Session UI-3 done-bar — *"preferences are first-class"*, and its seven pre-registered bars.

    uv run python steps/session_ui_3.py             # every bar
    uv run python steps/session_ui_3.py --only b3   # one of them (writes the .partial sibling)

Writes ``analysis/session_ui_3.json``.

★ **The bars were fixed before the code was written** (`docs/BUILD_PLAN.md` §"Session UI-3",
2026-08-01): **B0** every prior sheet re-runs passing · **B1** a tag set on the Board page reaches
the Cost page's ``DraftConfig`` without re-entry, differenced against a recorded run · **B2** the
strip's five bars *are* ``player_card``'s numbers and the strip and the dialog read the same call ·
**B3** §5's grammar satisfied **on the rendered HTML**, asserted on a player whose risk trait
would read as praise un-inverted · **B4** tags survive navigation and a rerun, and
``never`` is inviolable ·
**B5** ≤ 2 interactions to draft a queued player, ≤ 3 for an arbitrary search · **FLOW**.

⚠ **T36 is open and this session sits on top of it.** ``st.dataframe(on_select=…)`` is a *client*
event ``AppTest`` cannot fire, so the row-select **click** is still uncovered. A2 was built to hang
off ``pending_pick`` rather than off the selection event precisely so everything downstream of the
click — the strip, its five bars, its confirm — is driven here through the routes that *are*
drivable. **The gap is one event, and it is named in the sheet rather than papered over by FLOW.**

⚠ ``--only`` writes ``analysis/session_ui_3.partial.json``, not the sheet — UI-1's lesson, kept.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import engine, palette, probe  # noqa: E402
from steps import _app_drive, _sheet_diff  # noqa: E402

from fantasy_quant.data import db  # noqa: E402
from fantasy_quant.draft import session  # noqa: E402
from fantasy_quant.draft.config import LeagueSettings  # noqa: E402
from fantasy_quant.draft.simulator import _apply_pick, pick_by_adp  # noqa: E402

OUT = Path("analysis/session_ui_3.json")
PARTIAL = Path("analysis/session_ui_3.partial.json")
BASELINE = Path("analysis/ui3_cost_multiselect_baseline.json")
APP = Path("app/main.py")
ROOT = Path(__file__).resolve().parents[1]
SEAT = 5                       # 0-indexed; the seat every sheet since K1.5 is written from

#: ★ **The control for B0's own clause: the eight card bars, spelled out literally.**
#: A3 replaced exactly this list inside :func:`session.player_card` with
#: :data:`session.CARD_BARS` so the percentiles could not hold a second opinion about which column
#: ``BUST`` reads. Keeping the literal *here* — in the measurement, not in the code — is what makes
#: the refactor checkable: if the tuple and this ever disagree, one of them is wrong and the bar
#: says which leaf.
PRE_A3_BARS: tuple[tuple[str, str], ...] = (
    ("PROJ", "proj_points"), ("MEAN", "mean"), ("AVAIL", "games_played_mean"),
    ("Q10", "q10"), ("MED", "q50"), ("Q90", "q90"),
    ("BOOM", "boom_prob_live"), ("BUST", "bust_prob_live"),
)


def _con():
    return db.connect(read_only=True)


def _draft(built, season: int, k: int = 1, *, picks: int = 0):
    """The same draft constructor UI-1's and UI-2's sheets use, so all three describe one room."""
    mix = None if k <= 1 else ",".join(["balanced"] * (10 - k))
    state, meta = engine.start_draft(built, human_seats=list(range(k)) or [SEAT],
                                     settings=LeagueSettings(), season=season, seed=5,
                                     room_seed=2, room_arg=mix or "realistic")
    if k == 0:
        state, meta = engine.start_draft(built, human_seats=[], settings=LeagueSettings(),
                                         season=season, seed=5, room_seed=2,
                                         room_arg=",".join(["balanced"] * 10))
    session.advance(state, meta, built["risk"])
    for _ in range(int(picks)):
        if state.is_done() or not state.available:
            break
        t = state.team_on_clock()
        _apply_pick(state, t, int(pick_by_adp(state, t, noise=0.0)))
        session.advance(state, meta, built["risk"])
    return state, meta


def _apptest(page: str, state=None, meta=None, built=None, **session_state):
    from app.main import PAGE_SPECS
    from streamlit.testing.v1 import AppTest
    from streamlit.util import calc_hash

    at = AppTest.from_file(str(APP), default_timeout=900)
    at._page_hash = calc_hash(PAGE_SPECS[page][3])
    if state is not None:
        at.session_state["draft"] = {"state": state, "meta": meta, "vi": built["value_index"],
                                     "risk": built["risk"]}
    for k, v in session_state.items():
        at.session_state[k] = v
    return at


def _bars_on_screen(at) -> list[dict]:
    """Every drawn §5 bar in the rendered page, parsed back out of its own markup.

    ⚠ **Read off the DOM, not off the function that produced it.** B3's claim is that the grammar
    holds *on the rendered HTML*; re-calling :func:`views.bar_html` here and asserting on its
    output would be a test of a string formatter, which is not the thing that was wrong before
    (what was wrong was that the spec lived in a document and ``st.metric`` shipped).
    """
    out = []
    for el in at.get("html"):
        body = str(getattr(el.proto, "body", ""))
        if "border-radius:5px" not in body:
            continue
        label = re.search(r"<span>([^<]+)</span>", body)
        number = re.search(r"<b>([^<]*)</b>", body)
        width = re.search(r"width:([0-9.]+)%", body)
        tick = re.search(r"left:([0-9.]+)%", body)
        hue = re.search(r"background:(#[0-9A-Fa-f]{6})", body)
        out.append({"label": label.group(1) if label else None,
                    "text": number.group(1) if number else None,
                    "fill": float(width.group(1)) if width else None,
                    "tick": float(tick.group(1)) if tick else None,
                    "hue": hue.group(1) if hue else None,
                    "dashed": "dashed" in body,
                    "says_position": "at his position" in body})
    return out


# ------------------------------------------------------------------------------------------------
# B1 — a tag set on the board reaches the Cost page's DraftConfig, without re-entry
# ------------------------------------------------------------------------------------------------
def bar_b1(con, season: int) -> dict:
    """★ **The workflow claim, differenced against a path that no longer exists.**

    The four ``st.multiselect``s are deleted, so they cannot be re-run; the ``DraftConfig`` they
    produced was written to ``analysis/ui3_cost_multiselect_baseline.json`` *before* the deletion
    and this differences the tag-derived config against that record, field by field. The second
    half is the part a unit test cannot make: the tag is set **once**, in session state, and the
    **Cost page** is then rendered from it with no re-entry anywhere.
    """
    rec = json.loads(BASELINE.read_text())
    keys, want = rec["keys"], rec["config"]
    tags = {keys["must"]: "must", keys["never"]: "never",
            keys["reach"]: "reach", keys["wait"]: "wait"}
    cfg = session.tag_config(tags, archetype=want["archetype"],
                             risk_lambda=want["risk_lambda"])
    must = [[m.player_key, m.reach_budget] for m in cfg.must_draft]
    same = {
        "must_draft": must == want["must_draft"],
        "never_draft": sorted(cfg.never_draft) == want["never_draft"],
        "tilts": dict(cfg.tilts) == want["tilts"],
        "archetype": cfg.archetype == want["archetype"],
        "risk_lambda": cfg.risk_lambda == want["risk_lambda"],
    }

    built = engine.build(con, season)
    # ⚠ **picks=0.** Each iteration of `_draft`'s loop is one *human* pick and the room advances
    # behind it, so `picks=8` is ~80 players off the board — and the recorded baseline names four
    # of the top fifteen, who would all have been drafted. A tag on a drafted player is a real
    # case (`tag_summary` still names him) but it is not the case B1 is about.
    state, meta = _draft(built, season, picks=0)
    # the tag is set once, on the board's own vocabulary, and read on a different page
    board_at = _apptest("board", state, meta, built, tags=tags, queue=[])
    board_at.run()
    board_tagged = sum(g in _text(board_at) for g in
                       (session.TAGS["must"]["glyph"], session.TAGS["never"]["glyph"]))
    cost_at = _apptest("cost", state, meta, built, tags=tags, queue=[])
    cost_at.run()
    cost_text = _text(cost_at)
    bkeys = state.board["player_key"].astype(str)
    named = [str(state.board.loc[bkeys == k, "player_name"].iloc[0])
             for k in tags if (bkeys == k).any()]
    on_cost = [n for n in named if n in cost_text]
    exceptions = [str(e.value)[:200] for e in board_at.exception] + \
                 [str(e.value)[:200] for e in cost_at.exception]

    return {"bar": "B1 — a Board tag is the Cost page's DraftConfig, "
                   "differenced against the recorded run",
            "pass": bool(all(same.values()) and board_tagged and len(on_cost) == len(named)
                         and named and not exceptions),
            "baseline_vintage": rec.get("board_vintage"),
            "fields_matching_the_recorded_run": same,
            "tagged_glyphs_on_the_board_page": board_tagged,
            "tagged_players_named_on_the_cost_page": f"{len(on_cost)}/{len(named)}",
            "re_entry_required": False,
            "n_exceptions": len(exceptions), "exceptions": exceptions[:3]}


def _text(at) -> str:
    """Every rendered string, from every primitive — UI-1's ``_all_text``, including ``html``."""
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
    # ⚠ **the dataframes, stringified.** The first version of this scrape read only the text
    # primitives and reported B1 as a failure with `0/4` — while the `TAG` column was on screen
    # the whole time, inside an Arrow payload. K2's instrument lesson, third time: *a scrape that
    # cannot see the surface reports the surface as missing.*
    for frame in at.dataframe:
        v = getattr(frame, "value", None)
        parts.append(v.to_string() if hasattr(v, "to_string") else str(v))
    return " ".join(parts)


# ------------------------------------------------------------------------------------------------
# B2 — the strip IS the card
# ------------------------------------------------------------------------------------------------
def bar_b2(con, season: int) -> dict:
    """★ **One call, two surfaces** — and the surface is checked where it renders.

    ``session.card_strip`` takes the *card*, not the state, so the strip cannot hold a number the
    dialog does not; that is structure, and it is asserted in ``tests/test_app.py``. What this bar
    adds is that the numbers the app actually draws are those numbers — the five bars scraped back
    out of the rendered page, matched against ``card_strip``'s own text for the same player.
    """
    built = engine.build(con, season)
    state, meta = _draft(built, season, picks=6)
    idx = int(sorted(state.available)[3])
    card = session.player_card(state, idx, vi=built["value_index"], lam=built["lam"],
                               risk=built["risk"])
    want = session.card_strip(card)

    at = _apptest("board", state, meta, built, pending_pick=idx)
    at.run()
    drawn = {b["label"]: b for b in _bars_on_screen(at)}
    matched = {e["label"]: (e["label"] in drawn
                            and drawn[e["label"]]["text"] == (e["text"] or "—"))
               for e in want}
    # the dialog reads the same call: its eight bars are the card's eight, and the five are a
    # projection of them plus the two card fields — so a mismatch here is a *second derivation*
    labels_are_a_projection = all(
        e["label"] in {b["label"] for b in card["bars"]} | {"IMPACT", "BARGAIN"} for e in want)
    exceptions = [str(e.value)[:200] for e in at.exception]

    return {"bar": "B2 — the strip's five bars are `player_card`'s numbers, drawn",
            "pass": bool(all(matched.values()) and labels_are_a_projection and len(want) == 5
                         and not exceptions),
            "player": card["name"], "board_index": idx,
            "strip_labels": [e["label"] for e in want],
            "matched_on_screen": matched,
            "five_bars": len(want) == 5,
            "labels_are_a_projection_of_the_card": labels_are_a_projection,
            "one_call": "session.card_strip(session.player_card(...))",
            "n_exceptions": len(exceptions), "exceptions": exceptions[:3]}


# ------------------------------------------------------------------------------------------------
# B3 — §5's grammar, on the rendered HTML
# ------------------------------------------------------------------------------------------------
def bar_b3(con, season: int) -> dict:
    """★ **Asserted on the markup, and on the player where an un-inverted bar would be praise.**

    §5's rule is *green = good for the drafter, always*, so the test case is the board's **highest
    bust rate**: un-inverted he draws the longest, greenest bar on the page. The bar also requires
    both baselines to be present (fill **and** tick) and an unmeasured readout to draw as a dashed
    empty track rather than a zero-width fill — T22's rule in the display layer.
    """
    built = engine.build(con, season)
    state, meta = _draft(built, season, picks=4)
    bust = pd.to_numeric(state.board["bust_prob_live"], errors="coerce")
    riskiest = int(bust.idxmax())
    safest = int(bust.idxmin())

    def _card_bars(idx: int) -> dict:
        at = _apptest("board", state, meta, built, pending_pick=idx)
        at.run()
        # the strip renders the five; the deep page's eight arrive through the dialog, which is not
        # drivable — so the eight are checked through `player_card` and the *drawing* through the
        # five, which is the honest split given T36.
        return {b["label"]: b for b in _bars_on_screen(at)}, at

    risky, at_risky = _card_bars(riskiest)
    safe, _ = _card_bars(safest)
    pc_risky = session.player_card(state, riskiest, vi=built["value_index"], lam=built["lam"],
                                   risk=built["risk"])
    pc_safe = session.player_card(state, safest, vi=built["value_index"], lam=built["lam"],
                                  risk=built["risk"])
    bust_risky = {b["label"]: b for b in pc_risky["bars"]}["BUST"]
    bust_safe = {b["label"]: b for b in pc_safe["bars"]}["BUST"]

    inverted = bool(bust_risky["pct_overall"] < bust_safe["pct_overall"])
    hue_risky = palette.tier_color(bust_risky["pct_overall"])
    hue_safe = palette.tier_color(bust_safe["pct_overall"])
    # length and colour read the same scale: no long red bar, no short green one
    scale_agrees = all(
        (b["hue"] != palette.VALUE_GOOD or b["fill"] >= palette.TIER_CUTS[1] * 100 - 1e-6)
        and (b["hue"] != palette.VALUE_BAD or b["fill"] < palette.TIER_CUTS[0] * 100 + 1e-6)
        for b in risky.values() if b["hue"] and b["fill"] is not None)
    both_baselines = {k: bool(v["fill"] is not None and v["tick"] is not None
                              and v["says_position"]) for k, v in risky.items()}

    # an unmeasured readout: dashed, no hue, no fill
    unmeasured = state.board.index[state.board["bust_prob_live"].isna()]
    blank = None
    if len(unmeasured):
        b_at = _apptest("board", state, meta, built, pending_pick=int(unmeasured[0]))
        b_at.run()
        boom = {b["label"]: b for b in _bars_on_screen(b_at)}.get("BOOM")
        blank = None if boom is None else {
            "dashed": boom["dashed"], "fill": boom["fill"], "hue": boom["hue"],
            "text": boom["text"]}

    ok_blank = blank is None or (blank["dashed"] and blank["fill"] is None
                                 and blank["hue"] is None)
    exceptions = [str(e.value)[:200] for e in at_risky.exception]

    return {"bar": "B3 — §5 on the rendered HTML: green=good with the risk trait inverted, "
                   "both baselines, no bar without a reading",
            "pass": bool(inverted and hue_risky == palette.VALUE_BAD
                         and hue_safe == palette.VALUE_GOOD and scale_agrees
                         and all(both_baselines.values()) and ok_blank and not exceptions),
            "riskiest_player": pc_risky["name"], "riskiest_bust": bust_risky["value"],
            "riskiest_bust_percentile": bust_risky["pct_overall"], "riskiest_hue": hue_risky,
            "safest_player": pc_safe["name"], "safest_bust": bust_safe["value"],
            "safest_bust_percentile": bust_safe["pct_overall"], "safest_hue": hue_safe,
            "inversion_holds": inverted,
            "length_and_colour_agree": scale_agrees,
            "both_baselines_per_bar": both_baselines,
            "unmeasured_readout": blank,
            "tier_mid": palette.TIER_MID, "tier_cuts": list(palette.TIER_CUTS),
            "n_exceptions": len(exceptions), "exceptions": exceptions[:3]}


# ------------------------------------------------------------------------------------------------
# B4 — tags persist, and `never` is inviolable
# ------------------------------------------------------------------------------------------------
def bar_b4(con, season: int) -> dict:
    """★ **The hard-constraint half is the one that matters**, and it is set up so that refusing
    actually costs something: the ``never``-tagged player is **available, legal and first in the
    queue**. A queue that skipped him only when he was already gone would prove nothing.
    """
    built = engine.build(con, season)
    state, meta = _draft(built, season, picks=0)
    pool = state.draftable_pool(SEAT)
    forbidden = str(pool["player_key"].iloc[0])
    wanted = str(pool["player_key"].iloc[1])
    tags = {forbidden: "never"}
    queue = [forbidden, wanted]

    res = session.queue_next(state, SEAT, queue, tags)
    refused = bool(res["board_index"] is not None
                   and res["player_key"] == wanted
                   and any(s["player_key"] == forbidden for s in res["skipped"]))
    forbidden_was_takeable = bool(forbidden in set(pool["player_key"].astype(str)))

    # persistence: the same session state, three pages, one rerun each
    seen = {}
    for page in ("board", "draft", "cost"):
        at = _apptest(page, state, meta, built, tags=tags, queue=queue)
        at.run()
        at.run()                       # a rerun, which is what a widget interaction causes
        seen[page] = {"tags": dict(at.session_state["tags"]),
                      "queue": list(at.session_state["queue"]),
                      "exceptions": [str(e.value)[:200] for e in at.exception]}
    persisted = all(v["tags"] == tags and v["queue"] == queue for v in seen.values())

    # and the room never offers him: the queue rail's button names the *next legal* player
    room = _apptest("draft", state, meta, built, tags=tags, queue=queue)
    room.run()
    labels = [str(b.label) for b in room.button]
    forbidden_name = str(state.board.loc[
        state.board["player_key"].astype(str) == forbidden, "player_name"].iloc[0])
    not_offered = not any(lbl == f"Draft {forbidden_name}" for lbl in labels)
    exceptions = sum((v["exceptions"] for v in seen.values()), []) + \
                 [str(e.value)[:200] for e in room.exception]

    return {"bar": "B4 — tags survive navigation and a rerun; `never` is inviolable",
            "pass": bool(refused and forbidden_was_takeable and persisted and not_offered
                         and not exceptions),
            "forbidden_player": forbidden_name,
            "forbidden_was_available_and_legal": forbidden_was_takeable,
            "queue_skipped_him": refused,
            "skip_reason": (res["skipped"][0]["why"] if res["skipped"] else None),
            "queue_offered_instead": res.get("player_name"),
            "never_button_absent_from_the_room": not_offered,
            "persisted_across": {k: (v["tags"] == tags and v["queue"] == queue)
                                 for k, v in seen.items()},
            "n_exceptions": len(exceptions), "exceptions": exceptions[:3]}


# ------------------------------------------------------------------------------------------------
# B5 — time to pick, counted in interactions
# ------------------------------------------------------------------------------------------------
def bar_b5(con, season: int) -> dict:
    """★ **Counted, not estimated.** Each ``.select()``/``.click()`` below is one thing a human
    does. The pre-registered targets are ≤ 2 for a queued player and ≤ 3 for an arbitrary search
    (both were 3 before this session)."""
    built = engine.build(con, season)

    # --- arbitrary search: select, confirm -----------------------------------------------------
    state, meta = _draft(built, season, picks=0)
    before = len(state.log)
    at = _apptest("draft", state, meta, built)
    at.run()
    sel = [s for s in at.selectbox if str(getattr(s, "label", "")) == "Search the board"]
    n_options = len(sel[0].options) if sel else 0
    at = sel[0].select(sel[0].options[1]).run() if sel else at          # 1
    strip_loaded = any(str(b.label) == "Draft him" for b in at.button)
    if strip_loaded:
        at = [b for b in at.button if str(b.label) == "Draft him"][0].click().run()   # 2
    search_state = at.session_state["draft"]["state"]
    search_taps = 2 if (sel and strip_loaded) else None
    search_landed = len([p for p in search_state.log if p["team"] == 0]) > 0

    # --- queued player: the queue button, then confirm -----------------------------------------
    state2, meta2 = _draft(built, season, picks=0)
    idx = int(state2.draftable_pool(0).index[4])
    key = str(state2.board.loc[idx, "player_key"])
    name = str(state2.board.loc[idx, "player_name"])
    q = _apptest("draft", state2, meta2, built, queue=[key], tags={})
    q.run()
    btn = [b for b in q.button if str(b.label) == f"Draft {name}"]
    q = btn[0].click().run() if btn else q                              # 1
    confirm = [b for b in q.button if str(b.label) == "Draft him"]
    q = confirm[0].click().run() if confirm else q                      # 2
    mine = [p["player_name"] for p in q.session_state["draft"]["state"].log if p["team"] == 0]
    queue_taps = 2 if (btn and confirm) else None
    queue_landed = bool(mine and mine[0] == name)

    exceptions = [str(e.value)[:200] for e in at.exception] + \
                 [str(e.value)[:200] for e in q.exception]
    return {"bar": "B5 — ≤2 interactions for a queued player, ≤3 for an arbitrary search",
            "pass": bool(search_taps is not None and search_taps <= 3 and search_landed
                         and queue_taps is not None and queue_taps <= 2 and queue_landed
                         and not exceptions),
            "search_interactions": search_taps, "search_target": 3,
            "queued_interactions": queue_taps, "queued_target": 2,
            "before_this_session": {"search": 3, "queued": 3},
            "selector_options": n_options,
            "search_pick_landed": search_landed,
            "queued_player": name, "queued_pick_landed": queue_landed,
            "picks_before": before,
            "n_exceptions": len(exceptions), "exceptions": exceptions[:3]}


# ------------------------------------------------------------------------------------------------
# FLOW — every page renders, and a pick still completes a draft by clicking
# ------------------------------------------------------------------------------------------------
def bar_flow(con, season: int) -> dict:
    from app.main import PAGE_SPECS

    built = engine.build(con, season)
    pages, runs, page_errors = {}, [], []
    for k in (0, 1, 4):
        state, meta = _draft(built, season, k=k, picks=6)
        probe.reset()
        for name in PAGE_SPECS:
            at = _apptest(name, state, meta, built, tags={}, queue=[])
            at.run()
            pages[f"k{k}:{name}"] = not at.exception
            page_errors += [f"k{k}:{name}: {str(e.value)[:200]}" for e in at.exception]
        runs.append({"k": k, "pages": len(PAGE_SPECS), "page_bodies": probe.snapshot()})

    # a pick made by clicking still completes a draft and lands on 14.N
    state2, meta2 = _draft(built, season, picks=0)
    while not state2.is_done() and state2.available:
        t = state2.team_on_clock()
        if t == 0 and len(state2.roster(0)) == state2.rounds - 1:
            break
        _apply_pick(state2, t, int(pick_by_adp(state2, t, noise=0.0)))
        session.advance(state2, meta2, built["risk"])
    before = len(state2.log)
    a = _apptest("draft", state2, meta2, built, tags={}, queue=[])
    a.run()
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
            # ⚠ named rather than implied: FLOW proves every page renders and every *drivable*
            # route works. The row-select click is not one of them (T36).
            "row_select_click_not_drivable": True,
            "n_exceptions": len(exceptions), "exceptions": exceptions[:4]}


# ------------------------------------------------------------------------------------------------
# B0 — nothing this session touched moved a number
# ------------------------------------------------------------------------------------------------
def bar_b0(con, season: int) -> dict:
    """*If a display change moves a number, it is not a display change.*

    Runs UI-2's whole sheet — which runs UI-1's, which runs K2's, K1.5's and K1's — then adds the
    clause UI-3 owes: **the eight card bars are the eight values they were before A3 refactored
    them into :data:`session.CARD_BARS`**, checked against a literal list held here
    (:data:`PRE_A3_BARS`) rather than against the tuple under test.
    """
    r = subprocess.run([sys.executable, "steps/session_ui_2.py"], cwd=ROOT,
                       capture_output=True, text=True, timeout=21600)
    sheet = ROOT / "analysis" / "session_ui_2.json"
    data = json.loads(sheet.read_text()) if sheet.exists() else {}
    per_bar = {k: v.get("pass") for k, v in (data.get("bars") or {}).items()}
    nested = data.get("bars", {}).get("b0", {})

    # ★ UI-3's own clause: the card did not change value, only gain keys.
    built = engine.build(con, season)
    state, meta = _draft(built, season, picks=12)
    differing, checked = [], 0
    for idx in list(state.board.index[:60]):
        card = session.player_card(state, int(idx), vi=built["value_index"], lam=built["lam"],
                                   risk=built["risk"])
        got = {b["label"]: b["value"] for b in card["bars"]}
        if len(card["bars"]) != 8:
            differing.append(f"{idx}: {len(card['bars'])} bars")
            continue
        for label, col in PRE_A3_BARS:
            raw = pd.to_numeric(pd.Series([state.board.loc[int(idx), col]]),
                                errors="coerce").iloc[0]
            want = None if pd.isna(raw) else float(raw)
            if got.get(label) != want:
                differing.append(f"{idx}.{label}: {got.get(label)!r} -> {want!r}")
            checked += 1

    now_v, now_r = _sheet_diff.board_stamp(con, season), _sheet_diff.room_stamp()
    moves = {}
    for p in ("analysis/session_k1_app.json", "analysis/session_k1_5_app.json",
              "analysis/session_k2_app.json", "analysis/session_ui_1.json",
              "analysis/session_ui_2.json"):
        head = subprocess.run(["git", "show", f"HEAD:{p}"], cwd=ROOT, capture_output=True,
                              text=True)
        doc = json.loads(head.stdout) if head.returncode == 0 else {}
        moves[p] = _sheet_diff.classify_moves(
            p, vintage=(_sheet_diff.sheet_vintage(doc), now_v),
            room=(_sheet_diff.sheet_room(doc), now_r))
    clean = all(not m.get("unclassified") for m in moves.values())
    pinned = ((data.get("bars") or {}).get("b0") or {}).get("pinned_control_from_ui1") or {}
    attributed = bool(pinned.get("reproduced_bit_for_bit"))
    inputs_moved = any((m.get("input_bucket") or "") != "" for m in moves.values())

    return {"bar": "B0 — UI-2's sheet re-runs (UI-1, K2, K1.5, K1 nested); the card's eight "
                   "did not move",
            "pass": bool(data.get("all_pass") and clean and not differing
                         and (attributed or not inputs_moved)),
            "board_vintage": now_v, "room_mix": now_r,
            "returncode": r.returncode, "ui2_all_pass": data.get("all_pass"),
            "ui2_per_bar": per_bar,
            "ui1_all_pass": nested.get("ui1_all_pass"),
            "k2_all_pass": nested.get("k2_all_pass"),
            "k1_5_all_pass": nested.get("k1_5_all_pass"),
            "k1_all_pass": nested.get("k1_all_pass"),
            "pinned_control_from_ui1": pinned,
            "card_bar_values_checked": checked,
            "card_bar_values_differing": differing[:8],
            "every_moved_leaf_classified": clean,
            "moves_vs_committed": moves,
            "tail": "" if data.get("all_pass") else r.stdout[-2000:]}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=None)
    ap.add_argument("--only", default=None, help="b0|b1|b2|b3|b4|b5|flow")
    a = ap.parse_args()

    con = _con()
    season = a.season or engine.live_season(con)
    print(f"=== SESSION UI-3 DONE-BAR — season {season} ===\n")
    plan = {
        "b1": lambda: bar_b1(con, season),
        "b2": lambda: bar_b2(con, season),
        "b3": lambda: bar_b3(con, season),
        "b4": lambda: bar_b4(con, season),
        "b5": lambda: bar_b5(con, season),
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
              **_sheet_diff.input_stamp(con, season),
              "tags": {k: v["glyph"] for k, v in session.TAGS.items()},
              "queue_glyph": session.QUEUE_GLYPH,
              "strip_bars": [lbl for lbl, _ in session.STRIP_BARS],
              "inverted_bars": [lbl for lbl, _c, _f, g in session.CARD_BARS if g < 0],
              "tier_mid": palette.TIER_MID,
              # ⚠ the honest scope line, carried in the artifact rather than in a report nobody
              # re-reads: FLOW covers every page and every drivable route, and the row-select
              # click is not one of them.
              "t36_row_select_click_uncovered": True,
              "all_pass": all(r["pass"] for r in results.values()), "bars": results}
    out = OUT if not a.only else PARTIAL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str))
    con.close()
    print(f"{'ALL BARS PASS' if report['all_pass'] else 'SOME BARS FAILED'} -> {out}")


if __name__ == "__main__":
    main()
