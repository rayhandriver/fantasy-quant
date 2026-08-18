"""Driving the app's **one pick path**, in one place — shared by every bar sheet that clicks.

★ **Why this module exists.** K1.5, K2 and UI-1 each carry a FLOW bar whose claim is *"a human can
start a draft and make a pick by clicking"*, and each drove it through the six-button quick-pick
row. UI-3's A7 deleted that row (it duplicated the top of the table it sat under and was the app's
only one-click irreversible pick), so three committed sheets suddenly drove a control that no
longer exists.

**The claim did not change; the control did.** That distinction is the whole reason this is a
shared function rather than three edits: the next session to move the pick path edits one drive and
every sheet keeps making the same statement, instead of three sheets drifting into testing three
different eras of the room. It is `_sheet_diff`'s argument one layer up — *an instrument that lives
in the thing it measures cannot outlive it.*

⚠ **A sheet re-pointed at a new control is a moved leaf, and it is declared.** `quick_pick_buttons`
disappears from three sheets and `pick_path` replaces it; both are named in
:data:`~steps._sheet_diff.ALLOWED_MOVES` under ``a7_pick_path``, on T40's precedent — *the renamed
keys are the instrument, the numbers under them are still checked.* The pick that lands is
unchanged (the selector's first real option is the same best-available player the quick row's first
button was), so `clicked`, `picks_before` and `picks_after` are **not** excused by that allowance
and must reproduce on their own.
"""

from __future__ import annotations

#: The selector's label. One string, because a bar that looks for a control by a label typed out
#: three times is a bar that goes quietly green when the label is edited in two of them.
PICK_SELECTOR_LABEL = "Search the board"

#: The confirm button on A2's strip — the only thing in the app that turns an intention into a pick.
CONFIRM_LABEL = "Draft him"


def pick_by_clicking(at, option_index: int = 1) -> tuple[str | None, object]:
    """Make one pick the way a human does: **select, then confirm.** Returns ``(name, at)``.

    ``option_index`` is into the selector's own options, whose zeroth entry is the empty
    "nothing selected" state — so the default ``1`` is the **best available legal player**, which
    is exactly who the deleted quick row's first button was. That equality is deliberate: it is
    what lets three committed sheets keep their recorded ``clicked`` value across the change, and
    therefore what makes the re-pointing checkable rather than merely plausible.

    Returns ``(None, at)`` if either control is missing, so a caller's ``pass`` predicate fails
    loudly instead of a missing control reading as a clean run.
    """
    sel = [s for s in at.selectbox if str(getattr(s, "label", "")) == PICK_SELECTOR_LABEL]
    if not sel or len(sel[0].options) <= option_index:
        return None, at
    wanted = str(sel[0].options[option_index])
    at = sel[0].select(wanted).run()
    confirm = [b for b in at.button if str(getattr(b, "label", "")) == CONFIRM_LABEL]
    if not confirm:
        return None, at
    at = confirm[0].click().run()
    return wanted.split(" · ")[0], at
