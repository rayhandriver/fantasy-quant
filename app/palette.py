"""The one place a position becomes a colour (UI-1 step 2 / UI-PLAN §S1).

★ **Position is a colour, everywhere, always.** It is the first convention in the shared design
grammar every surveyed product obeys, and the census that opened this session found **zero** uses of
colour to encode anything in 1,903 lines of ``app/``. One hue per position, identical on the board,
the room grid, the log, the roster rail and the post-draft rosters — five surfaces, one constant.
Bar **B1** asserts the hex strings appear exactly once in ``app/``, because the failure mode here is
not "the colours are wrong", it is "the colours are right in four places and stale in the fifth".

★ **Okabe-Ito, not the market convention** (the user's call, taken with the trade-off stated). The
category standard is QB gold · RB red · WR blue · TE orange · K purple · DST green, and matching it
would be free familiarity for anyone who has drafted on ESPN or Sleeper. It also puts **red, orange
and gold within one hue family**, which is three of the six positions rendered as one colour for a
deuteranope — roughly 1 in 12 men. Okabe-Ito is the standard qualitative set built to survive the
three common colour-vision deficiencies, so the encoding still carries information for the readers a
convention-matching palette silently drops. Familiarity is worth something; a channel that does not
reach a twelfth of your users is worth less.

★ **Two treatments, one constant, and both are theme-independent.** UI-PLAN §S1 proposes a ~35 %
tint with full-strength text. That is right for dark and wrong for light — full-strength ``#0072B2``
on a 35 %-``#0072B2`` tint over the dark background is a contrast ratio of about **2.4**, under the
4.5 the text needs, and it inverts entirely when a reader flips the theme toggle. So:

* :func:`chip_style` — a **solid** hue lettered in whichever of black or white actually has more
  contrast on it (:func:`ink_for`, and see its docstring for why that is a comparison and not a
  threshold). Used where the cell *is* the position (a two-letter ``POS`` column). Reads as a chip,
  and its contrast does not depend on what is behind it, because nothing is: the hue is opaque.
* :func:`tint_style` — an ``rgba`` tint at :data:`TINT_ALPHA` with **no text colour set**, so the
  text keeps the theme's own foreground. Used where the cell is a *player* and the position is one
  fact about him. The browser composites the tint over whatever background the active theme has, so
  it is light-on-light and dark-on-dark automatically.

*A colour that only works in one theme is a colour that breaks the day someone presses the toggle.*
"""

from __future__ import annotations

import re
from collections import Counter

import pandas as pd

#: surface name -> how many times it has been styled in this process. **Bar B1's instrument**, and
#: it ships in the app for the same reason ``app/probe.py`` does: *a probe that only exists under
#: the test measures the test.* Streamlit encodes a Styler's CSS into the Arrow payload rather than
#: exposing it, so "did this surface get coloured" is not readable from ``AppTest``; counting the
#: call is. One dict increment per styled frame.
STYLED: Counter[str] = Counter()

#: The five surfaces S1 promises. Named here rather than in the bar so the claim and the check
#: cannot drift: if a sixth surface is coloured it is opt-in, and if one of these five stops being
#: coloured B1 fails.
SURFACES: tuple[str, ...] = ("board", "room_grid", "log", "roster_rail", "post_draft_rosters")


def record(surface: str) -> None:
    STYLED[str(surface)] += 1


def reset() -> None:
    STYLED.clear()


def styled() -> dict[str, int]:
    return dict(STYLED)

#: Draft positions, in the order the board, the roster rail and every chart list them. The order is
#: part of the contract: ``.streamlit/config.toml``'s ``chartCategoricalColors`` is this sequence,
#: and bar B1 asserts the two agree rather than trusting them to.
POSITIONS: tuple[str, ...] = ("QB", "RB", "WR", "TE", "K", "DST")

#: The palette. Okabe-Ito's qualitative set, one hue per position — see the module docstring for why
#: this rather than the market convention. **These six strings appear nowhere else in ``app/``.**
POSITION_COLORS: dict[str, str] = {
    "QB": "#E69F00",     # orange
    "RB": "#D55E00",     # vermillion
    "WR": "#0072B2",     # blue
    "TE": "#CC79A7",     # reddish purple
    "K": "#56B4E9",      # sky blue
    "DST": "#009E73",    # bluish green
}

#: Opacity for :func:`tint_style`. Low enough that a full row of tinted cells does not shout, high
#: enough that the hue survives compositing over either theme's background.
TINT_ALPHA = 0.22

#: **UI-2 — the signed-value pair, and why it is allowed to be red/green when the palette is not.**
#: `docs/UI-PLAN.md` convention #7 asks for green-undervalued / red-overvalued on the value-vs-now
#: columns, and UI-1 rejected exactly that hue family for **position** because there six categories
#: were carried by hue *alone*, so a deuteranope lost the encoding outright. Here the channel is
#: **redundant**: ``Δ`` and ``BARGAIN`` both render with an explicit sign (``%+``), so a reader who
#: cannot separate the hues still reads the direction off the number. Colour that duplicates an
#: available channel is a convenience; colour that replaces one is a barrier. Different case,
#: different answer.
#:
#: ⚠ Deliberately **not** members of :data:`POSITION_COLORS` — a value signal and a position are
#: different meanings and must not share a hue, and bar B1's "the six hexes appear exactly once"
#: stays a statement about the palette rather than about every colour in the app.
#:
#: ★ **Measured, not chosen.** The first pair here was a deep green/red (``#1B7F4B``/``#A32B22``)
#: picked by eye. Checked, it failed twice over: the red sat at contrast **2.63** on the dark
#: background — under the 3.0 a *mark* needs, on the theme the app actually ships — and **both**
#: poles were under 4.5 as **text**, on both themes at once. The shipped pair clears 3.0 on
#: ``#0F1115``, ``#181B21`` **and** white (worst case **3.39**), holds 27.0 normal-vision ΔE, and
#: survives all three dichromacies (deuteranopia 21.1 · protanopia 8.1 · tritanopia 24.9, OKLab
#: ×100, floor 8) — because the two differ in **lightness** as much as in hue, which is what makes
#: a red/green pair survive at all. *The palette lesson from UI-1, one session on: a colour chosen
#: by eye is a colour nobody re-derives when the surface changes.*
VALUE_GOOD = "#2E9E63"
VALUE_BAD = "#D9564A"

#: A cell like ``"Bijan Robinson (RB)"`` or ``"1.01  Bijan Robinson (RB)"`` — the shape
#: :func:`~fantasy_quant.draft.session.room_grid` writes for both its layouts. Parsing the rendered
#: string is formatting, not derivation: the position is already *in* the cell, and the alternative
#: (re-querying the roster per cell) would be a second read of a frame we are looking at.
_IN_CELL = re.compile(r"\(([A-Z]{1,3})\)\s*$")

#: A slot label like ``QB``, ``RB1``, ``WR3``, ``FLEX``, ``BN4``. Only the ones that name a single
#: position get a colour — ``FLEX``, ``SUPERFLEX`` and the bench rows are deliberately uncoloured,
#: because a flex slot is not a position and colouring it as one would assert something false.
_SLOT = re.compile(r"^([A-Z]{1,3})\d*$")


def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _luminance(hex_color: str) -> float:
    """WCAG relative luminance — what decides whether a chip is lettered in black or white."""
    def channel(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in _rgb(hex_color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: str, b: str) -> float:
    """WCAG contrast between two hex colours. AA body text wants ≥ 4.5."""
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


#: The two inks a chip can be lettered in. Near-black rather than pure black so the chip does not
#: out-contrast the page it sits on.
INK: tuple[str, str] = ("#111111", "#FFFFFF")


def color_for(pos: object) -> str | None:
    """The hue for a position label, or ``None`` if it names no single position."""
    key = str(pos).strip().upper()
    return POSITION_COLORS.get(key)


def ink_for(hue: str) -> str:
    """Black or white, **whichever actually has more contrast on this hue.**

    ⚠ Written as a comparison rather than as a luminance threshold because the first version used
    a threshold and got QB wrong: ``#E69F00`` has relative luminance 0.410, which reads as "light"
    to any threshold above it, and the naive cut of 0.5 lettered it in **white at a contrast ratio
    of 2.3** — under the 4.5 AA asks for, on the most-drafted position on the board. The break-even
    luminance is 0.179, not 0.5, and the way to not have to know that is to compute both and take
    the larger. *A constant chosen by eye is a constant nobody re-derives when the palette changes.*
    """
    return max(INK, key=lambda ink: contrast_ratio(hue, ink))


def chip_style(pos: object) -> str:
    """CSS for a cell whose content *is* a position — solid hue, auto-contrast lettering."""
    hue = color_for(pos)
    if hue is None:
        return ""
    return f"background-color: {hue}; color: {ink_for(hue)}; font-weight: 600"


def tint_style(pos: object) -> str:
    """CSS for a cell that *mentions* a position — a tint, with the theme's own text colour."""
    hue = color_for(pos)
    if hue is None:
        return ""
    r, g, b = _rgb(hue)
    return f"background-color: rgba({r}, {g}, {b}, {TINT_ALPHA})"


def signed_style(value: object) -> str:
    """Tint a signed value cell: green above zero, red below, nothing on zero or a blank.

    ⚠ **A tint with no text colour set, not ink** — :func:`tint_style`'s treatment, for
    :func:`tint_style`'s reason. Inking these cells in :data:`VALUE_GOOD`/:data:`VALUE_BAD` was the
    obvious build and it fails AA on *both* themes at once: no single mid-tone clears 4.5 against a
    near-black background and against white, which is the same trap UI-PLAN §S1's "35 % tint with
    full-strength text" fell into. A tint composites over whichever background the active theme
    has, and the theme's own foreground stays legible on top of it.
    """
    v = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(v) or v == 0:
        return ""
    r, g, b = _rgb(VALUE_GOOD if v > 0 else VALUE_BAD)
    return f"background-color: rgba({r}, {g}, {b}, {TINT_ALPHA})"


def pos_in_cell(value: object) -> str | None:
    """The position named in a rendered grid cell, e.g. ``"3.07  Puka Nacua (WR)"`` → ``"WR"``."""
    m = _IN_CELL.search(str(value))
    return m.group(1) if m and m.group(1) in POSITION_COLORS else None


def pos_in_slot(value: object) -> str | None:
    """The position a starting-slot label names — ``"RB2"`` → ``"RB"``; ``"FLEX"`` → ``None``."""
    m = _SLOT.match(str(value).strip())
    return m.group(1) if m and m.group(1) in POSITION_COLORS else None


# ------------------------------------------------------------------------------------------------
# the three ways a frame gets coloured
# ------------------------------------------------------------------------------------------------
def style_pos_columns(frame: pd.DataFrame, columns=("POS", "pos"), *, surface: str = "board"):
    """Chip the named position columns. Returns a ``Styler`` — ``st.dataframe`` renders it.

    ⚠ Streamlit honours only ``background-color`` and ``color`` from a Styler, which is exactly the
    two properties this module sets. ``font-weight`` is passed through where the browser gets it and
    ignored where it does not; nothing depends on it.
    """
    record(surface)
    cols = [c for c in columns if c in frame.columns]
    styler = frame.style
    if cols:
        styler = styler.map(chip_style, subset=cols)
    # UI-2 — `Δ` and `BARGAIN` wherever they appear. Listed by column name rather than passed in so
    # that every surface showing them inks them the same way without each caller remembering to.
    signed = [c for c in ("Δ", "BARGAIN") if c in frame.columns]
    if signed:
        styler = styler.map(signed_style, subset=signed)
    return styler


def style_grid_cells(frame: pd.DataFrame, *, index: bool = False, surface: str = "room_grid"):
    """Tint every ``"name (POS)"`` cell in a room grid, optionally the slot index too."""
    record(surface)
    styler = frame.style.map(lambda v: tint_style(pos_in_cell(v)))
    if index:
        styler = styler.map_index(lambda v: tint_style(pos_in_slot(v)), axis=0)
    return styler


def style_roster_rail(frame: pd.DataFrame, *, surface: str = "roster_rail"):
    """The rail: ``SLOT`` chipped where it names a position, ``PLAYER`` tinted by his own."""
    record(surface)
    styler = frame.style
    if "SLOT" in frame.columns:
        styler = styler.map(lambda v: chip_style(pos_in_slot(v)), subset=["SLOT"])
    if "PLAYER" in frame.columns:
        styler = styler.map(lambda v: tint_style(pos_in_cell(v)), subset=["PLAYER"])
    return styler
