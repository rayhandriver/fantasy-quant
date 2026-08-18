"""The bar-sheet comparator — **T41's fix, and the reason it needed one home.**

Every session since K1 closes with the same claim: *if a display change moves a number, it is not a
display change.* The instrument behind it re-runs the committed sheets and enumerates every
leaf that moved. It lived as a copy-paste in ``steps/session_ui_1.py`` and
``steps/session_ui_2.py``, and by 2026-08-17 the two copies had **already diverged** — UI-1's
list carried ``ui2_column_lists``,
UI-2's carried ``ui2_columns``/``ui2_modes`` and had dropped the other. Two comparators is how the
control that guards against drift starts drifting, so there is one now.

★★ **What T41 actually asked for, and what is built here.** The ticket's finding: after the mandated
weekly Stage-0 pull, B0 failed with **122 unclassified leaves in K1's sheet and 23 in K2's**, every
nested sheet still passing its own bars — the ADP board had simply moved. ``_ALLOWED_MOVES`` names
rendered-element counts, entropy draws, timings and column lists; it has **no category for *the
input moved***, so the operator had to re-derive by hand each week whether the cause was the
board or the code. The fix has two halves and both are here:

1. **Partition the output.** A moved leaf is attributed to ``vintage_changed`` / ``room_changed``
   only when the sheet's *stamped* inputs actually moved, and never when the leaf is a **gate** —
   a ``pass`` flag, an identity, a difference count, a "nothing was missing". Those must hold on any
   board, so a board move can never excuse one. This is a classification, not an allowance: the
   leaves stay enumerated and stay in the sheet. ⚠ ``ALLOWED_MOVES`` is **not** widened to swallow
   them, which the ticket says in bold and which is the whole point of the register entry.
2. **Pin the input.** Attribution is a hypothesis until something tests it, so the caller pairs this
   with a control that re-runs the same code on the *old* board and the *old* room
   (``session.build_board(..., asof=)``, VH.0) and demands bit-identity. See
   ``steps/session_ui_1.py``'s ``bar_b0``. Without that control this module is a nicer way to say
   "probably the world"; with it, "the world, and here is the proof".

⚠ **The room is an input too, and T41 did not know that yet.** The ticket was written 2026-08-01;
MM-1a seated ``fitted_manager`` in ``REALISTIC_ROOM`` on 08-05, so the sheets' k=1 drafts changed
composition for a reason that has nothing to do with the ADP board. Both stamps are carried for the
same reason: *a control that cannot name its inputs cannot tell you which one moved.*
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fantasy_quant.adp import boards  # noqa: E402
from fantasy_quant.draft import mock, session  # noqa: E402

#: What a *display* session is allowed to move in a committed sheet, and nothing else. Each entry is
#: ``(category, predicate on the flattened JSON path)``. **An unmatched change fails the bar**,
#: which is the point: "all bars still pass" is a weaker claim than "and here is exactly what moved
#: and why", and the second is the one K1's rule actually makes.
#:
#: ★ **Cumulative by design.** It says what a display session is *allowed* to move — not what any
#: one session did — so a later session that legitimately adds a board column extends it rather than
#: being failed by it. **The values in those columns are a separate claim, checked separately**,
#: column by column, by each session's own B0: a list getting longer is a display change, a number
#: inside it moving is not.
ALLOWED_MOVES: tuple[tuple[str, str], ...] = (
    # counts of *rendered elements* — UI-1 adds a table to 14.N (T38) and a panel to the rail (T37)
    ("display_count", "n_elements_rendered"),
    ("display_count", "n_dataframes"),
    ("display_count", "post_page_dataframes"),
    # T34's entropy defaults: the app draws its seeds from the OS, so these were never stable and a
    # sheet that reproduced them would mean the randomisation had stopped working
    ("entropy", "randomized_seed"), ("entropy", "randomized_room_seed"),
    ("entropy", "replayed_seed"), ("entropy", "replayed_room_seed"),
    ("entropy", "distinct_openings"), ("entropy", "example_openings"),
    # wall clock. ⚠ `worst_seat` is the **argmax** of `worst_pick_ms_by_seat`, and it was the one
    # leaf the first version of this list missed — correctly, in the sense that the bar caught it
    # rather than waving it through. It belongs here: the seven seats sit within a few milliseconds
    # of each other, so *the argmax of a noisy vector is noisier than the vector*, and a run where
    # `reacher` beats `upside_chaser` by 0.4 ms is not a finding about either.
    ("timing", "worst_ms"), ("timing", "worst_pick_ms_by_seat"), ("timing", "worst_seat"),
    # …and UI-2's own wall-clock leaf, which is the same kind of number under a different name
    # (2026-08-17): `cost_ms_for_40_rows` moved 406 → 455 ms between two runs of identical code.
    ("timing", "cost_ms"),
    # the stat dictionary gains entries as columns are documented. ⚠ The *count* is what is allowed;
    # `assert_stat_dict_covers_board`'s verdict is a gate (`covers`) and is not excused by this.
    ("stat_dict", "n_entries"), ("stat_dict", "documented"), ("stat_dict", "stat_dict_entries"),
    # UI-1: `Δ` joins the slim view, lengthening the column list K1.5's bar B2 records
    ("column_lists", "slim_columns"),
    # UI-2: three columns join the frame's union and the mode list grows by two
    ("column_lists", "n_columns"), ("column_lists", "columns"), ("column_lists", "board_columns"),
    ("view_modes", "modes"), ("view_modes", "n_modes"), ("view_modes", "view_modes"),
    # ★ **The comparator's own output, which cannot be evidence in its own comparison.** A sheet
    # records what moved when it ran; the next run's diff necessarily differs there, and reading
    # that as a regression is a self-reference, not a finding. Scoped to the two subtrees this
    # module writes — never to the leaves they describe.
    ("comparator_self", "moves_vs_committed"), ("comparator_self", "pinned_control"),
    # T40 (2026-08-17): UI-2's B3 control changed shape when it stopped being sampled. The renamed
    # keys are the instrument; the numbers under them are still checked.
    ("t40_control", "glyphs_that_fired"), ("t40_control", "every_glyph_fired"),
    ("t40_control", "constructed_control"),
    # UI-3 step 4 / A7 (2026-08-17): three sheets drove their FLOW bar through the six-button
    # quick-pick row, and A7 deleted it. They now drive `steps/_app_drive.pick_by_clicking`.
    # **Scoped to the instrument's own two keys, on T40's precedent.** `clicked`, `picks_before`
    # and `picks_after` are deliberately *not* here: the selector's first real option is the same
    # best-available player the quick row's first button was, so the pick that lands must
    # reproduce on its own — which is the only thing that makes the re-pointing checkable rather
    # than merely plausible.
    ("a7_pick_path", "quick_pick_buttons"), ("a7_pick_path", "pick_path"),
    # UI-1's prose census, which every later UI session moves **by construction** — A7 deleted the
    # search box's help text and the quick row, so `draft_room.py` went 6 → 5 blocks. The bar's own
    # verdict is `n_after <= PROSE_TARGET`, and `pass` is a gate this cannot excuse; what is allowed
    # here is the *count*, which is a readout of a deletion the session declared. ⚠ Note the
    # direction is not asserted: a count that went **up** would also land here, and it is B3 — the
    # honesty-surface bar UI-1 deliberately paired with B2 — that stops prose being traded for a
    # deleted warning. One bar's readout, another bar's gate.
    ("prose_census", "after_total"), ("prose_census", "after_by_file"),
    ("prose_census", "removed"),
)

#: Path segments that mark a leaf as a **gate** — something a bar's verdict rests on. A gate
#: holds on *any* board and in *any* room, so it is never attributable to a moved input: when
#: one of these changes the answer is "the code moved", full stop.
GATE_SEGMENTS: frozenset[str] = frozenset({"pass", "passed", "all_pass", "ok"})

#: Substrings with the same standing as :data:`GATE_SEGMENTS`, matched against the final path
#: segment. These are the vocabularies this repo's bars state identity in.
GATE_FRAGMENTS: tuple[str, ...] = (
    "identical", "differing", "mismatch", "violat", "fabricated", "n_missing", "n_exceptions",
    "stays_unknown", "unknown_stays", "reproduc", "byte", "who_matches", "picks_match",
    "n_teams_matched", "covers", "inviolable",
)


def board_stamp(con, season: int) -> str:
    """Which ADP board a run measured — ``mock.board_vintage`` on the resolved raw board.

    The same call K1's B2 has always made, hoisted so every sheet can stamp itself.
    """
    raw, src = boards.resolve_board(con, int(season), "ppr", 10, allow_ecr=False, include_dst=True)
    return mock.board_vintage(raw, src)


def room_stamp() -> list[str]:
    """The composition the sheets' k=1 drafts run against — the *second* input T41 did not know it
    had. MM-1a seated ``fitted_manager`` here on 2026-08-05, five days after the ticket was written.
    """
    return list(session.realistic_mix(1))


def input_stamp(con, season: int) -> dict:
    """The two leaves every sheet carries from 2026-08-17 on. Splat into the report dict."""
    return {"board_vintage": board_stamp(con, int(season)), "room_mix": room_stamp()}


def flatten(obj: Any, prefix: str = "") -> Iterator[tuple[str, Any]]:
    """Every leaf of a decoded JSON document as ``(dotted.path[i], value)``."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from flatten(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from flatten(v, f"{prefix}[{i}]")
    else:
        yield prefix, obj


def is_gate(path: str) -> bool:
    """Is this leaf something a bar's verdict rests on?

    Segment-exact for the short words (``pass``, ``ok``) because a substring test on them matches
    half the repo — ``n_passes``, ``token``, ``book``. Substring for the identity vocabulary, which
    is distinctive enough that a false positive costs only a leaf reported as unclassified, i.e.
    the *safe* direction: an unattributed leaf is read by a human, an over-attributed one is not.
    """
    last = path.rsplit(".", 1)[-1].split("[", 1)[0]
    return last in GATE_SEGMENTS or any(f in last for f in GATE_FRAGMENTS)


def sheet_vintage(doc: dict) -> str | None:
    """The ADP board a committed sheet was measured on, if it says.

    ``bars.b2.vintage`` is K1's — it has stamped the vintage since the session was written, which is
    why T41's evidence table could name the boards at all. The top-level ``board_vintage`` is what
    the UI sheets stamp from 2026-08-17 (this ticket). A sheet that carries neither returns ``None``
    and is treated as an unstamped baseline by :func:`classify_moves`.
    """
    top = doc.get("board_vintage")
    if top:
        return str(top)
    b2 = (doc.get("bars") or {}).get("b2") or {}
    return str(b2["vintage"]) if b2.get("vintage") else None


def sheet_room(doc: dict) -> list[str] | None:
    """The room composition a committed sheet was measured under, if it says."""
    mix = doc.get("room_mix")
    return [str(x) for x in mix] if mix else None


def classify_moves(rel: str, *, vintage: tuple[str | None, str | None] = (None, None),
                   room: tuple[list[str] | None, list[str] | None] = (None, None)) -> dict:
    """Every leaf that changed in a committed sheet, and which allowance it falls under.

    ``vintage`` / ``room`` are ``(committed, current)`` pairs. When the committed side is unknown —
    a sheet written before this ticket — the transition is reported as ``inputs_unstamped_baseline``
    and the caller is expected to lean on the pinned control instead of on this classification. That
    bucket should appear **exactly once** in the repo's history, on the run that lands the stamps.
    """
    head = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=ROOT, capture_output=True, text=True)
    if head.returncode != 0:
        return {"comparable": False, "reason": "not in HEAD (uncommitted)"}
    before = dict(flatten(json.loads(head.stdout)))
    after = dict(flatten(json.loads((ROOT / rel).read_text())))

    v_before, v_now = vintage
    r_before, r_now = room
    unstamped = v_before is None or r_before is None
    v_moved = bool(v_before and v_now and v_before != v_now)
    r_moved = bool(r_before and r_now and list(r_before) != list(r_now))
    if unstamped:
        input_bucket: str | None = "inputs_unstamped_baseline"
    elif v_moved and r_moved:
        input_bucket = "vintage_and_room_changed"      # two inputs moved; this cannot separate them
    elif v_moved:
        input_bucket = "vintage_changed"
    elif r_moved:
        input_bucket = "room_changed"
    else:
        input_bucket = None                            # inputs held, so nothing excuses a move

    moved: dict[str, list[str]] = {}
    unclassified: list[str] = []
    for key in sorted(set(before) | set(after)):
        if before.get(key) == after.get(key):
            continue
        cat = next((c for c, frag in ALLOWED_MOVES if frag in key), None)
        if cat is None:
            cat = input_bucket if (input_bucket and not is_gate(key)) else None
        if cat is None:
            unclassified.append(f"{key}: {before.get(key)!r} -> {after.get(key)!r}")
        moved.setdefault(cat or "UNCLASSIFIED", []).append(key)
    return {"comparable": True, "leaves": len(set(before) | set(after)),
            "vintage": {"committed": v_before, "current": v_now, "moved": v_moved},
            "room": {"committed": r_before, "current": r_now, "moved": r_moved},
            "input_bucket": input_bucket,
            "moved": {k: len(v) for k, v in moved.items()},
            "moved_paths": {k: v[:8] for k, v in moved.items()},
            "unclassified": unclassified[:8],
            "n_unclassified": len(unclassified)}
