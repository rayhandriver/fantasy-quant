"""The app's one seam onto the engine — connection, board build, draft lifecycle.

Everything expensive is cached here and nowhere else, and every number comes from
:mod:`fantasy_quant.draft.session`. No Streamlit widget code lives in this module: it is importable
and testable without a Streamlit runtime, which is what lets Session K1's bar B1 be checked at all
(a test can call these functions and compare against ``steps/mock_draft.py`` directly).

★ **The live season is the point.** ``app/streamlit_app.py`` — the app this replaces — offered a
season selector over ``DEV_SEASONS`` only, so the one thing a drafter needs (this year's board) was
the one thing it could not show. :func:`live_season` reads what the store actually boards.
"""

from __future__ import annotations

import pickle
import secrets
from pathlib import Path

import numpy as np

from fantasy_quant.adp import boards
from fantasy_quant.data import db
from fantasy_quant.draft import session
from fantasy_quant.draft.config import DraftConfig, LeagueSettings
from fantasy_quant.draft.personalities import SeatMap
from fantasy_quant.draft.simulator import DraftState, _apply_pick, _prepare_board, pick_by_adp

#: Shared with ``steps/mock_draft.py`` so a CLI draft and an app draft are the *same object* —
#: which is what makes "export from the app, resume in the CLI" work and bar B1 checkable.
STATE_PATH = Path("data/interim/mock/draft_state.pkl")
CACHE_DIR = Path("analysis/cache")


def connect():
    """A read-only handle on the store. Cached by the caller (``@st.cache_resource``)."""
    return db.connect(read_only=True)


def live_season(con, *, scoring: str = "ppr", teams: int = 10) -> int:
    """The newest season the store actually has a board for — the season a drafter wants.

    Asks :func:`~fantasy_quant.adp.boards.resolve_board` rather than trusting a constant, because
    the answer changes when the Stage-0 chore banks a new series and a hardcoded year is how the
    old app ended up unable to show the current one.
    """
    seasons = con.execute(
        "SELECT DISTINCT season FROM adp_snapshots WHERE source='ffc' ORDER BY season DESC"
    ).df()["season"].astype(int).tolist()
    for s in seasons:
        board, _ = boards.resolve_board(con, int(s), scoring, int(teams),
                                        allow_ecr=False, include_dst=True)
        if not board.empty:
            return int(s)
    raise LookupError("the store has no FFC board for any season")


def boarded_seasons(con, *, scoring: str = "ppr", teams: int = 10) -> list[int]:
    """Every season with a resolvable board, newest first — the season selector's options."""
    seasons = con.execute(
        "SELECT DISTINCT season FROM adp_snapshots WHERE source='ffc' ORDER BY season DESC"
    ).df()["season"].astype(int).tolist()
    out = []
    for s in seasons:
        board, _ = boards.resolve_board(con, int(s), scoring, int(teams),
                                        allow_ecr=False, include_dst=True)
        if not board.empty:
            out.append(int(s))
    return out


def build(con, season: int, settings: LeagueSettings | None = None,
          config: DraftConfig | None = None, *, asof: str | None = None) -> dict:
    """The ``(board, value_index, risk)`` build — :func:`session.build_board`, with the 17.3
    settings threaded in so the board a user reads is the board *their* league produces.

    ``settings`` is what un-orphans Phase 17: ``teams`` sizes the board and the replacement levels
    the value index is computed against, so a superflex league's QBs lift here rather than in a
    caption. When it is ``None`` the engine defaults apply, which is the lockbox case.

    ``asof`` (T41) pins the ADP vintage. **No app screen passes it** — it exists so a bar sheet can
    re-run itself on the board a committed sheet was measured on, which is the difference between
    reporting that the world moved and proving the code did not.
    """
    settings = settings or LeagueSettings()
    config = config or config_from(settings)
    return session.build_board(con, season=int(season), teams=int(settings.n_teams),
                               config=config, cache_dir=CACHE_DIR, asof=asof)


def config_from(settings: LeagueSettings) -> DraftConfig:
    """A :class:`DraftConfig` carrying the user's league — the object every seat optimizes under."""
    return DraftConfig(league=settings.league_setup())


# ------------------------------------------------------------------------------------------------
# draft lifecycle — the same DraftState the CLI pickles
# ------------------------------------------------------------------------------------------------
#: The seat the T34 report was made from, and the sequence the frozen defaults produced on the
#: 2026-07-30 board — kept as data so :mod:`steps.session_k1_5_app` can assert the *measurement*
#: default still means what every committed bar sheet assumes it means.
T34_REFERENCE = {
    "seat": 6, "seed": 7, "room_seed": None, "board": "2026 FFC (07-30)",
    "first_five": ["Jahmyr Gibbs", "Ja'Marr Chase", "Jonathan Taylor", "Christian McCaffrey",
                   "James Cook III"],
}


def draw_seeds() -> tuple[int, int]:
    """A fresh ``(seed, room_seed)`` from OS entropy — **the app's default, and only the app's**.

    ★ **T34 — a measurement default and a human default are different objects.** ``seed=7`` with
    ``room_seed=None`` froze *both* sources of variation at once: the pick RNG
    (``DraftState.rng``) and the seating (``room_seed=None`` keeps ``REALISTIC_ROOM``'s listed
    order, so the same personality sat in the same chair every time). A user re-drafting his slot
    got the identical room, the identical picks and the identical story — and practising against
    one frozen draft is worse than not practising.

    The fix is not to make the engine random; the engine was never the problem, and the
    personalities were sampling correctly the whole time. It is that **the app inherited the CLI's
    default because the CLI's was the only one that existed.** ``steps/`` keeps ``--seed 7``: T24's
    sweep, 16.17's 1,014-triple mapping check and every committed bar sheet are differenced against
    it. So the entropy draw lives here, on the app's side of the seam, and the drawn values are
    returned in ``meta`` so any draft can still be replayed exactly.
    """
    return secrets.randbelow(1_000_000), secrets.randbelow(1_000_000)


def start_draft(built: dict, *, human_seats: list[int], room_arg: str | None = "realistic",
                settings: LeagueSettings | None = None, seed: int | None = None,
                room_seed: int | None = None, auto: list[int] | None = None,
                fav: tuple[str, ...] = (), season: int = 2026) -> tuple[DraftState, dict]:
    """``(state, meta)`` for a fresh draft — the app's equivalent of ``mock_draft.py start``.

    Identical construction to the CLI's, deliberately down to ``noise=5.0`` and the ``meta`` keys,
    because the two surfaces write and read the *same* state file. A field added on one side and
    not the other is how a resumed draft would quietly change rooms.

    ⚠ **T34 — ``seed=None`` and ``room_seed=None`` mean "draw one" here, and the drawn values go
    into ``meta``.** Both are always concrete by the time a draft exists, so "randomize" and "lock
    to a seed" are the same code path with a different source for two integers, and the app can
    show a user the seeds his draft actually ran on. Pass them explicitly to reproduce a draft; a
    caller that wants the measurement defaults asks for them by number (see :data:`T34_REFERENCE`).
    """
    settings = settings or LeagueSettings()
    drawn_seed, drawn_room = draw_seeds()
    seed = drawn_seed if seed is None else int(seed)
    room_seed = drawn_room if room_seed is None else int(room_seed)
    n_teams, rounds = int(settings.n_teams), int(settings.rounds)
    auto = sorted(set(auto or []))
    if set(auto) - set(human_seats):
        raise ValueError("autopicked seats must be seats you drive")
    mix = session.room_mix(room_arg, n_humans=len(human_seats), n_teams=n_teams)
    # ★★ T55 — **the season goes to the seat map, or 16.18's PIT gate is inert on the one path a
    # human uses.** `make_room` degrades a `requires_profile` seat to `balanced` on a season the
    # profile does not describe (T54), and it can only do that if it is told the season. This call
    # omitted it, so the 2026 belief board was seated in every historical mock the app can start —
    # and the season selector offers **fifteen** of them, two of which (2023, 2024) are lockbox
    # seasons. The leak is graded and therefore quiet: the seat fires on whoever is still on that
    # year's board, so it reads as a mild opinion rather than as a defect. Same shape as T22 and
    # T35 before it — *a guard that does not run on the path a human uses is not a guard.*
    sm = SeatMap.of(n_teams, human_teams=human_seats, mix=mix, seed=room_seed, fav_teams=fav,
                    season=int(season))
    primary = human_seats[0] if human_seats else 0
    meta = {"your_team": primary, "human_teams": list(human_seats), "auto": auto,
            "room": [p.name for p in sm.room()], "teams": n_teams, "rounds": rounds,
            "fav": list(fav), "seed": int(seed),
            # T34 — the seating draw, stored beside the pick draw because a draft is only
            # replayable if BOTH are recorded. `seat_map_from` rebuilds the room from the *names*
            # in seat order, so this key is for display and for starting the same draft again.
            "room_seed": int(room_seed), "season": int(season),
            # 17.3 — carried so the odds tab simulates the user's bracket, not the default one
            "league_format": settings.league_format(), "ruleset": settings.ruleset()}
    b = _prepare_board(built["board"])
    st = DraftState(board=b, n_teams=n_teams, rounds=rounds, slots=settings.roster_slots(),
                    your_team=primary, rng=np.random.default_rng(int(seed)), noise=5.0,
                    available=set(b.index), rosters=[[] for _ in range(n_teams)],
                    human_teams=frozenset(human_seats), seat_roles=sm.roles())
    return st, meta


def make_pick(st: DraftState, meta: dict, team: int, board_index: int, risk=None) -> list[dict]:
    """Apply one human pick, then run the room to the next seat you drive."""
    if team not in st.human_teams:
        raise ValueError(f"T{team + 1} is not one of your seats")
    if team != st.team_on_clock():
        raise ValueError(f"T{team + 1} is not on the clock — T{st.team_on_clock() + 1} is")
    _apply_pick(st, team, int(board_index))
    return session.advance(st, meta, risk)


def autopick(st: DraftState, meta: dict, team: int, risk=None) -> list[dict]:
    """Hand the seat on the clock to the ADP autopicker for one pick (14.J's ``--auto`` seam)."""
    idx = pick_by_adp(st, team, noise=0.0)
    _apply_pick(st, team, int(idx))
    return session.advance(st, meta, risk)


def export_state(st: DraftState, meta: dict, vi=None, risk=None,
                 path: Path | str = STATE_PATH) -> Path:
    """Write the draft where ``steps/mock_draft.py`` reads it, so the CLI can resume this draft.

    Streamlit reruns top-to-bottom per interaction, so the app's live state is ``st.session_state``
    rather than this file. The pickle is an explicit export — which is also what makes an app draft
    and a CLI draft comparable objects rather than two lookalikes.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(pickle.dumps({"state": st, "meta": meta, "vi": vi, "risk": risk}))
    return p


def import_state(path: Path | str = STATE_PATH) -> dict:
    """Read a draft written by the app or the CLI — ``{state, meta, vi, risk}``."""
    p = Path(path)
    if not p.exists():
        raise LookupError("no draft to resume")
    return pickle.loads(p.read_bytes())
