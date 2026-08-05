"""16.18e — **the manager profile**: one human's draft beliefs as a loadable file.

★ **What this is, and what it deliberately is not.** ``docs/BUILD_PLAN.md`` §"Sessions MM-1 · MM-2"
splits "draft like this person" into two independently-learnable objects, and keeps them in
separate boxes because a mock draft observes both at once and identifies neither cheaply:

* **beliefs** — where they disagree with consensus about *players*. This is a **board**, and it is
  what this module holds.
* **policy** — how they trade value / risk / need / scarcity *given* a board. This is a **decision
  rule**, it is fitted from choices, and the slot for it here (:attr:`ManagerProfile.policy`) is
  **empty until an elicitation session fills it**.

The split is the reframe's own value-vs-availability line one level down. It also means a profile
with beliefs and no policy is a *complete, honest* object rather than a half-built one: the seat
holds this manager's opinions about players and the corpus-average manager's tradeoffs, which is
exactly what the spec's own honest expectation ("mostly prior") describes.

★ **The mechanism is general and the subject is a parameter.** ``FittedManager`` loads a profile
*file*; nothing in the code knows whose profile it is. That is what preserves the 2026-07-23
"nothing personal to the user" decision instead of overriding it — the backlog item is a fitting
mechanism, which serves every user, and the repo owner is subject #1.

⚠ **A profile must never reach the frozen value stack, ``valuation/value_board.py`` or the cost
report's baseline.** That report's entire job is pricing a preference *against* consensus;
contaminating its baseline with the preference deletes the measurement. Per-seat, opt-in, and
availability-side only — the same wall Phase 16 already sits behind.

⚠ **A faithful replica is a more *realistic* seat, not a stronger one.** The spent lockbox says
personalization is noise-dominated on realized points. Every evaluative claim about a profile runs
on **held-out pick prediction**, never on "the roster it built looks good to the person it models"
— that is the grader-is-the-subject trap, and it is the one failure no care inside the fit can
detect.

The unit of belief is a **pick delta**, exactly as in :mod:`fantasy_quant.adp.hype_board`: a signed
number of ADP picks, positive meaning *this manager takes him earlier than the board says*. Reusing
that unit is not cosmetic — :func:`~fantasy_quant.adp.hype_board.apply_hype` already converts picks
to utility through the opponent model's own ``β_adp_s`` and ``AdpSpec``, so a belief means the same
thing to the simulator as it does to the human who wrote it, and it re-derives itself if 11.1 is
ever refit.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
import pandas as pd

from fantasy_quant.adp.hype_board import MAX_PICK_DELTA

#: Where profiles live. One JSON per ``(subject, season)``; the filename is the ``profile_id``.
#: Re-exported by :mod:`fantasy_quant.draft.personalities` so its error messages can name it.
PROFILE_DIR = Path("reference/manager_profiles")

#: The 5-point ordinal the elicitation workbook records, as a signed magnitude. Positive means the
#: manager thinks the player is worth **more** than the market has him, i.e. he drafts him earlier.
VALUE_SCORE: dict[str, int] = {
    "Very undervalued": 2, "Undervalued": 1, "Evenly valued": 0,
    "Overvalued": -1, "Very overvalued": -2,
}

#: How much a stated confidence scales the magnitude of a belief. 1 = pure gut, 5 = would bet on it.
#:
#: ★ It is a **multiplier on size, never a gate on direction.** A low-confidence opinion is a small
#: opinion, not an absent one — zeroing it would silently delete the rows where a manager is least
#: anchored to consensus, which is exactly the informative region. The floor is 0.5 rather than 0
#: for that reason.
def confidence_mult(conf: float | None) -> float:
    """``0.5 … 1.5`` over a 1–5 confidence; a missing confidence reads as the neutral ``1.0``."""
    if conf is None or not np.isfinite(float(conf)):
        return 1.0
    c = min(max(float(conf), 1.0), 5.0)
    return 0.5 + 0.25 * (c - 1.0)


#: Reasons a player can be on a profile's hard-avoid list. Stored per player so a mock's log can
#: say **why** a manager passed on someone, which is the difference between a model and a black box.
AVOID_REASONS = ("no_interest", "team_rule")


def name_key(name: str, pos: str | None = None) -> str:
    """Normalized ``name|POS`` join key — the fallback for rows with no ``gsis_id``.

    ⚠ **Team defenses carry no gsis**, so a profile that keyed on gsis alone would silently drop
    every DST — the same failure :func:`~fantasy_quant.draft.simulator.board_player_key` exists to
    prevent, which is why this mirrors its two-key rule rather than inventing a third.

    ⚠ **Digits are kept.** The first version stripped every non-letter, which silently collided any
    two names differing only by a number — caught by a synthetic fixture rather than by a board,
    which is the point of having one. No real name loses a distinction by keeping them, and
    :func:`build_profile` raises on a collision rather than letting one belief overwrite another.
    """
    s = str(name).lower().replace("'", "").replace(".", "")
    s = re.sub(r"\b(jr|sr|ii|iii|iv)\b", " ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = " ".join(s.split())
    return f"{s}|{str(pos).upper().strip()}" if pos else s


# ==================================================================================================
# the profile
# ==================================================================================================
@dataclass(frozen=True)
class ManagerProfile:
    """One manager's beliefs (and, once elicited, policy) — the file a ``FittedManager`` loads.

    ``beliefs``      ``key -> pick_delta``. Positive = he drafts this player **earlier** than the
                     consensus board. Keys are ``gsis_id`` where the player has one and
                     :func:`name_key` otherwise, matching ``board_player_key``'s own rule.
    ``avoid``        ``key -> reason``. A **hard** filter, applied to the candidate pool the way
                     T20's mandatory needs are — not a large negative weight, because a weight is
                     traded off against a strong enough opinion and "I will not draft this player"
                     is not that kind of statement. It can never empty a pool; see
                     :func:`avoid_mask`.
    ``belief_scale`` picks per unit of stated value score, at confidence 3. **Calibrated**, not
                     chosen — see ``steps/mm1_profile.py``.
    ``policy``       feature -> **deviation from the corpus β**, EB-shrunk. Empty until an
                     elicitation session runs; an empty policy is honest, not unfinished.
    ``unrated``      what to do with a player the workbook never listed. ``"neutral"`` (the only
                     shipped value) means corpus-average treatment — a manager who never rated a
                     kicker has no opinion about kickers, he simply drafts one.

    ⚠ **``unrated`` is why a "blank means never draft" rule is scoped to the workbook's own rows.**
    The rule is about players the manager *saw and skipped*; a player who was never on the sheet was
    never declined. Conflating the two makes the seat unable to draft anyone outside the top-N,
    which on this repo's own held-out data would forbid a kicker the manager took in all three of
    his mock drafts.
    """

    profile_id: str
    season: int
    beliefs: dict[str, float] = field(default_factory=dict)
    avoid: dict[str, str] = field(default_factory=dict)
    belief_scale: float = 1.0
    policy: dict[str, float] = field(default_factory=dict)
    policy_shrinkage: dict[str, float] = field(default_factory=dict)
    policy_source: str = "corpus"
    unrated: str = "neutral"
    source: str = ""
    asof: str = ""
    #: ``key -> "Name (POS)"``, for **human review only** — nothing reads it. A profile keyed on
    #: ``gsis_id`` is a wall of ``00-00391xx`` that no one can check, and this repo's rule for a
    #: curated artifact is that a human has to be able to sign it. Never join on this.
    labels: dict[str, str] = field(default_factory=dict)
    notes: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        bad = sorted(set(self.avoid.values()) - set(AVOID_REASONS))
        if bad:
            raise ValueError(f"{self.profile_id}: unknown avoid reasons {bad}; "
                             f"known: {list(AVOID_REASONS)}")
        if self.unrated != "neutral":
            raise ValueError(f"{self.profile_id}: unrated={self.unrated!r} is not shipped — the "
                             f"only honest treatment of a player who was never rated is 'neutral'")
        d = np.asarray([float(v) for v in self.beliefs.values()], float)
        if d.size and np.nanmax(np.abs(d)) > MAX_PICK_DELTA + 1e-9:
            worst = max(self.beliefs, key=lambda k: abs(self.beliefs[k]))
            raise ValueError(
                f"{self.profile_id}: belief of {self.beliefs[worst]:+.1f} picks for {worst} "
                f"exceeds +/-{MAX_PICK_DELTA}. A personal board is a re-ranking of a consensus "
                f"board, not a replacement for it — the same cap the curated hype board carries.")
        if self.policy and self.policy_source == "corpus":
            raise ValueError(f"{self.profile_id}: policy coefficients present but policy_source is "
                             f"'corpus' — say where they came from, or an unfitted seat will be "
                             f"reported as a fitted one")

    # -- serialization -------------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "profile_id": self.profile_id, "season": int(self.season),
            "belief_scale": float(self.belief_scale), "unrated": self.unrated,
            "policy_source": self.policy_source,
            "source": self.source, "asof": self.asof,
            "beliefs": {k: round(float(v), 4) for k, v in sorted(self.beliefs.items())},
            "avoid": dict(sorted(self.avoid.items())),
            "labels": dict(sorted(self.labels.items())),
            "policy": {k: float(v) for k, v in sorted(self.policy.items())},
            "policy_shrinkage": {k: float(v) for k, v in sorted(self.policy_shrinkage.items())},
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ManagerProfile:
        return cls(
            profile_id=str(d["profile_id"]), season=int(d["season"]),
            beliefs={str(k): float(v) for k, v in (d.get("beliefs") or {}).items()},
            avoid={str(k): str(v) for k, v in (d.get("avoid") or {}).items()},
            belief_scale=float(d.get("belief_scale", 1.0)),
            policy={str(k): float(v) for k, v in (d.get("policy") or {}).items()},
            policy_shrinkage={str(k): float(v)
                              for k, v in (d.get("policy_shrinkage") or {}).items()},
            policy_source=str(d.get("policy_source", "corpus")),
            unrated=str(d.get("unrated", "neutral")),
            source=str(d.get("source", "")), asof=str(d.get("asof", "")),
            labels={str(k): str(v) for k, v in (d.get("labels") or {}).items()},
            notes=dict(d.get("notes") or {}),
        )

    def covers(self, season: int | None) -> bool:
        """Does this profile describe ``season``? ``None`` means the caller did not say.

        ★★ **A belief board is season-scoped by construction, and applying one to another season is
        a POINT-IN-TIME violation, not merely a mismatch.** "Player X is undervalued at ADP 37.7"
        is a statement about one board on one date. Worse than being wrong on a 2020 board, it
        is *look-ahead*: this workbook was written in August 2026 by someone who watched 2017-2025
        happen, so seating it in a 2020 simulation feeds the future into a historical measurement
        — exactly what ``CLAUDE.md`` §3.1 makes non-negotiable.

        And the leak is **graded, which is what makes it easy to miss**: the 2026 profile fires on
        6 board rows in 2017, 21 in 2020, 55 in 2024 and 78 in 2026 (measured 2026-08-05). A seat
        that is *almost* ``balanced`` in the early seasons and *increasingly itself* toward the
        present does not look broken in any single season's output — it looks like a seat with a
        mild opinion. :func:`~fantasy_quant.draft.personalities.make_room` is where this is
        enforced, because room composition is the last place the season is still known.
        """
        return season is None or int(season) == int(self.season)

    def save(self, path: Path | str | None = None) -> Path:
        p = Path(path) if path is not None else PROFILE_DIR / f"{self.profile_id}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=False) + "\n")
        return p

    def rescaled(self, scale: float) -> ManagerProfile:
        """The same beliefs at a different ``belief_scale`` — what a calibration sweep varies.

        Deltas are stored already-scaled (so a consumer needs no context to read the file), which
        makes rescaling a multiply rather than a rebuild. Clipped at the cap, so a large sweep step
        cannot walk a belief past the ceiling ``__post_init__`` enforces.
        """
        if self.belief_scale <= 0:
            raise ValueError("cannot rescale a profile whose belief_scale is 0")
        r = float(scale) / float(self.belief_scale)
        beliefs = {k: float(np.clip(v * r, -MAX_PICK_DELTA, MAX_PICK_DELTA))
                   for k, v in self.beliefs.items()}
        return replace(self, beliefs=beliefs, belief_scale=float(scale))

    def summary(self) -> dict:
        d = np.asarray(list(self.beliefs.values()), float)
        by_reason: dict[str, int] = {}
        for r in self.avoid.values():
            by_reason[r] = by_reason.get(r, 0) + 1
        return {
            "profile_id": self.profile_id, "season": int(self.season),
            "n_beliefs": int(len(self.beliefs)),
            "n_nonzero": int(np.count_nonzero(d)) if d.size else 0,
            "belief_scale": float(self.belief_scale),
            "mean_abs_delta": float(np.abs(d).mean()) if d.size else 0.0,
            "max_abs_delta": float(np.abs(d).max()) if d.size else 0.0,
            "n_avoid": int(len(self.avoid)), "avoid_by_reason": by_reason,
            "policy_source": self.policy_source, "n_policy": int(len(self.policy)),
            "beliefs_are_stated_not_backtested": True,
        }


def load_profile(path: Path | str) -> ManagerProfile:
    return ManagerProfile.from_dict(json.loads(Path(path).read_text()))


def available_profiles(directory: Path | str = PROFILE_DIR) -> list[Path]:
    d = Path(directory)
    return sorted(d.glob("*.json")) if d.is_dir() else []


def default_profile(season: int | None = None,
                    directory: Path | str = PROFILE_DIR) -> ManagerProfile | None:
    """The single profile on disk for ``season``, or ``None`` when there is none.

    Returns ``None`` rather than raising because a repo with no profile is the normal state for
    every user but the one who wrote one — but a room that *asks* for a ``fitted_manager`` seat and
    gets no profile **does** raise, in :func:`~fantasy_quant.draft.personalities.make_room_pick_fn`.
    *An inert personality still completes a legal draft*, which is this repo's most-repeated failure
    mode, so the loud error belongs where the seat is actually requested.
    """
    found = [load_profile(p) for p in available_profiles(directory)]
    if season is not None:
        found = [f for f in found if int(f.season) == int(season)]
    if not found:
        return None
    if len(found) > 1:
        raise ValueError(
            f"{len(found)} profiles for season={season} in {directory}: "
            f"{[f.profile_id for f in found]} — pass one explicitly rather than letting a "
            f"filesystem ordering decide whose beliefs a room drafts on")
    return found[0]


# ==================================================================================================
# building a profile from an elicitation workbook
# ==================================================================================================
#: The workbook columns :mod:`steps.mm1_elicitation_board` writes and this reader consumes.
WORKBOOK_COLS = ("Player", "Pos", "Team", "Personal Value", "Value Score",
                 "Confidence (1-5)", "Notes — what you actually believe")

BELIEF_SHEET = "Belief board"


def read_belief_workbook(path: Path | str, sheet: str = BELIEF_SHEET) -> pd.DataFrame:
    """The filled-in elicitation workbook as a frame, with the two-row banner header collapsed.

    Row 1 of the sheet is the colour-band group header (``IDENTITY`` / ``YOUR TAKE`` / …) and row 2
    is the real header, so a naive read gives a frame whose columns are the *bands*.
    """
    raw = pd.read_excel(path, sheet_name=sheet, header=None)
    header = [str(c) for c in raw.iloc[1].tolist()]
    df = raw.iloc[2:].reset_index(drop=True)
    df.columns = header
    missing = [c for c in WORKBOOK_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: workbook is missing {missing} — regenerate it with "
                         f"steps/mm1_elicitation_board.py rather than hand-editing the header")
    return df.dropna(subset=["Player"]).reset_index(drop=True)


def build_profile(workbook: pd.DataFrame, *, profile_id: str, season: int,
                  board: pd.DataFrame | None = None,
                  belief_scale: float = 4.0,
                  blank_note_means_avoid: bool = True,
                  avoid_teams: tuple[str, ...] = (),
                  team_exceptions: tuple[str, ...] = (),
                  source: str = "", asof: str = "") -> ManagerProfile:
    """Turn a filled workbook into a :class:`ManagerProfile`.

    ``board`` (optional) is the ADP board the workbook was generated from; joining to it recovers
    each player's ``gsis_id`` so beliefs survive a name change or a display-name difference. Rows it
    cannot resolve fall back to :func:`name_key`, which is how team defenses key.

    ``blank_note_means_avoid`` implements the elicitation contract *this* subject stated: a row he
    left un-annotated is a player he does not want, whatever the dropdown says. It is a **parameter,
    not a constant**, because it is a property of how one human filled one sheet — another subject's
    blank may mean "I ran out of time", and baking one person's convention into the reader is the
    hardcoded-label defect this repo has already paid for four times.

    ``avoid_teams`` / ``team_exceptions`` express a stated allegiance rule ("no Packers, except
    Kraft") as a hard filter. Exceptions are matched on player name.
    """
    df = workbook.copy()
    df["Value Score"] = pd.to_numeric(df["Value Score"], errors="coerce")
    df["Confidence (1-5)"] = pd.to_numeric(df["Confidence (1-5)"], errors="coerce")
    # `Value Score` is a spreadsheet formula over `Personal Value`; recompute it from the words so a
    # workbook opened in something that did not evaluate formulas still reads correctly.
    from_words = df["Personal Value"].map(lambda v: VALUE_SCORE.get(str(v).strip()))
    df["score"] = pd.to_numeric(from_words, errors="coerce").fillna(df["Value Score"])
    df["nkey"] = [name_key(n, p) for n, p in zip(df["Player"], df["Pos"], strict=True)]

    key = df["nkey"].copy()
    if board is not None and not board.empty:
        b = board.copy()
        b["nkey"] = [name_key(n, p) for n, p in zip(b["name"], b["position"], strict=True)]
        lut = {k: g for k, g in zip(b["nkey"], b.get("gsis_id", pd.Series(dtype=object)),
                                    strict=True) if isinstance(g, str) and g}
        key = df["nkey"].map(lambda k: lut.get(k, k))
    df["key"] = key
    if df["key"].duplicated().any():
        dup = df.loc[df["key"].duplicated(), "Player"].tolist()[:5]
        raise ValueError(f"duplicate profile keys for {dup} — two rows would silently overwrite "
                         f"one belief, so the workbook has to be fixed rather than deduplicated")

    has_note = df["Notes — what you actually believe"].notna() & (
        df["Notes — what you actually believe"].astype(str).str.strip() != "")
    conf = df["Confidence (1-5)"].map(confidence_mult)
    raw = float(belief_scale) * df["score"].fillna(0.0) * conf
    deltas = raw.clip(-MAX_PICK_DELTA, MAX_PICK_DELTA)

    avoid: dict[str, str] = {}
    if blank_note_means_avoid:
        for k in df.loc[~has_note, "key"]:
            avoid[str(k)] = "no_interest"
    if avoid_teams:
        exc = {name_key(n) for n in team_exceptions}
        team_hit = df["Team"].astype(str).str.upper().isin([t.upper() for t in avoid_teams])
        for k, n in zip(df.loc[team_hit, "key"], df.loc[team_hit, "Player"], strict=True):
            if name_key(n) in exc:
                continue
            avoid[str(k)] = "team_rule"

    # An avoided player's belief is not merely unused, it is contradictory — a positive delta on a
    # player the seat will never consider reads, to anyone inspecting the file, as an opinion the
    # model holds and does not act on. Drop it and record the count.
    beliefs = {str(k): float(v) for k, v in zip(df["key"], deltas, strict=True)
               if str(k) not in avoid and abs(float(v)) > 1e-9}
    overridden = int(sum(1 for k, v in zip(df["key"], deltas, strict=True)
                         if str(k) in avoid and abs(float(v)) > 1e-9))

    labels = {str(k): f"{n} ({pp})" for k, n, pp in zip(df["key"], df["Player"], df["Pos"],
                                                       strict=True)
              if str(k) in beliefs or str(k) in avoid}
    return ManagerProfile(
        profile_id=profile_id, season=int(season), beliefs=beliefs, avoid=avoid,
        belief_scale=float(belief_scale), source=source, asof=asof, labels=labels,
        notes={
            "n_rows": int(len(df)),
            "n_annotated": int(has_note.sum()),
            "blank_note_means_avoid": bool(blank_note_means_avoid),
            "avoid_teams": list(avoid_teams),
            "team_exceptions": list(team_exceptions),
            "beliefs_dropped_by_avoid": overridden,
            "unrated_players": "neutral — a player never listed was never declined",
        })


# ==================================================================================================
# applying a profile to a board
# ==================================================================================================
def profile_deltas(board: pd.DataFrame, profile: ManagerProfile,
                   key: str = "player_key") -> np.ndarray:
    """Per-board-row belief in **picks**, positive = drafted earlier. Unrated rows give ``0.0``.

    Resolves on the board's own id column first and falls back to :func:`name_key`, so the same
    profile lines up against a simulator board (``player_key``), a raw ADP board (``gsis_id``) and a
    team defense (no id at all) without the caller knowing which it holds.
    """
    out = np.zeros(len(board), float)
    if not profile.beliefs or board.empty:
        return out
    ids = (board[key].astype(str).to_numpy() if key in board.columns
           else np.array([""] * len(board)))
    nk = _board_name_keys(board)
    for i in range(len(board)):
        v = profile.beliefs.get(ids[i])
        if v is None:
            v = profile.beliefs.get(nk[i])
        if v is not None:
            out[i] = float(v)
    return out


def avoid_mask(board: pd.DataFrame, profile: ManagerProfile,
               key: str = "player_key") -> np.ndarray:
    """``True`` where this manager has declared he will not draft the player."""
    out = np.zeros(len(board), bool)
    if not profile.avoid or board.empty:
        return out
    ids = (board[key].astype(str).to_numpy() if key in board.columns
           else np.array([""] * len(board)))
    nk = _board_name_keys(board)
    for i in range(len(board)):
        out[i] = (ids[i] in profile.avoid) or (nk[i] in profile.avoid)
    return out


def personal_adp(board: pd.DataFrame, profile: ManagerProfile, *, adp_col: str = "adp",
                 key: str = "player_key") -> np.ndarray:
    """The board **as this manager sees it**: ``adp − belief``, floored just above pick 0.

    ★ This is the T24 seam reused, and the distinction matters. T24 built a per-seat private board
    as ``adp + κ·adp_stdev·ε`` and measured it **harmful** — but in its *noise* form, where the draw
    at the top of the board is the same size as the gaps it perturbs and therefore destroys an
    ordering that was already correct. A **deterministic, stated** offset is a different object: it
    moves a named player in a named direction for a written reason. *The seam is reusable; the
    finding is not transferable* — which is why this ships as its own function with its own bar
    rather than as a κ.
    """
    adp = pd.to_numeric(board[adp_col], errors="coerce").to_numpy(float)
    return np.clip(adp - profile_deltas(board, profile, key=key), 0.5, None)


def _board_name_keys(board: pd.DataFrame) -> np.ndarray:
    name_col = next((c for c in ("player_name", "name", "player") if c in board.columns), None)
    pos_col = next((c for c in ("pos", "position") if c in board.columns), None)
    if name_col is None:
        return np.array([""] * len(board))
    if pos_col is None:
        return np.array([name_key(n) for n in board[name_col]])
    return np.array([name_key(n, p)
                     for n, p in zip(board[name_col], board[pos_col], strict=True)])
