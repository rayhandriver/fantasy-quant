"""T15 step 0 — the repeatable mock-draft harness and the sim/corpus measurement bridge.

The defect T15 exists to fix was found by a **human drafting one mock** (findings.md §"Live mock
draft (2026-07-27)"), and one draft is not a baseline. This module is the A/B harness that has to
exist *before* the model changes: seeded batch rooms on one side, the realized Sleeper corpus on
the other, and — the load-bearing part — **one measurement code path over both**.

★ **The design constraint is that a simulated draft and a realized draft are measured by the same
functions on the same board.** :func:`sim_drift_panel` emits
:data:`~fantasy_quant.adp.drift_panel.PANEL_COLS`, the exact frame
:func:`~fantasy_quant.adp.drift_panel.build_drift_panel` returns for the human corpus, and the sim
drafts the board :func:`~fantasy_quant.adp.boards.resolve_board` hands the corpus panel for that
same season. So ``drift`` is computed against identical ADP numbers on both sides and a difference
in the reach profile cannot be an artifact of board vintage, board size, or a re-derived metric.
This is the 16.15 lesson applied ahead of time: *if the two sides of a comparison are computed by
different code, the comparison measures the code.*

What is deliberately **not** here: any change to how a seat picks. Every pick still goes through
the shipped 11.1 model and 11.3 personalities. This module only runs them repeatedly and measures
the result, so the baseline it writes is a picture of the code as it stands today.

Three things the measurement functions are careful about, each of which was a wrong turn first:

1. **Units are 10-team ADP picks**, not rounds. The panel stores ``drift`` in rounds; every T15
   number that has been written down (round-1 mean 3.3, p90 6.6, autopilot −19.8) is in picks.
   :data:`TEAMS_REF` is the single conversion and it is applied in one place.
2. **Sign follows the panel**: ``drift > 0`` = taken EARLIER than the board said (a reach).
   An ADP-follower in a reaching room therefore shows *negative* mean drift — that is the harvest,
   and it is why bar #3 is about a seat's surplus and not its finish.
3. **Faithfulness is behavioural, not an outcome.** See :func:`pool_rank` — measuring how
   ADP-faithful a seat is by its own |drift| is circular, because a chalk seat surrounded by
   reachers has a large |drift| precisely *because* it stayed faithful.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from fantasy_quant.adp import boards
from fantasy_quant.adp.drift_panel import PANEL_COLS
from fantasy_quant.adp.panel import OFFENSE, _canon_pos
from fantasy_quant.backtest.walkforward import draft_date
from fantasy_quant.draft import enrichment
from fantasy_quant.draft.enrichment import enrich_board
from fantasy_quant.draft.opponent_model import (
    ALL_FEATURES,
    AdpSpec,
    BandSpec,
    OpponentModel,
)
from fantasy_quant.draft.personalities import (
    DEFAULT_ROOM,
    PRIVATE_KAPPA,
    Personality,
    # 16.17: the one place `team -> seat` is computed. `full_room_pick_fn` is a zero-human map.
    SeatMap,
    WidthCurve,
    # T27: the guard now lives in `personalities` (lower in the import graph) so the *interactive*
    # room builder can run it too. Re-exported here because `mock.assert_room_objectives` is the
    # name every existing caller and test uses, and renaming a guard is how you lose one.
    assert_room_objectives,
    make_room,
    make_room_pick_fn,
)
from fantasy_quant.draft.simulator import (
    DraftState,
    RosterSlots,
    _prepare_board,
    board_player_key,
    canon_pos,
    run_to_completion,
)
from fantasy_quant.valuation.value_board import value_board

#: Every reach/fall number in T15 is quoted in **10-team ADP picks**; the drift panel stores rounds.
#: One constant, applied in exactly one helper (:func:`_picks`), so the two never drift apart.
TEAMS_REF: int = 10

#: Where the fitted 11.1 coefficients live (written by ``steps/phase11_opponent_model.py``).
COEF_JSON = Path("analysis/phase11_opponent_model.json")

#: :data:`~fantasy_quant.draft.personalities.DEFAULT_ROOM` is nine seats — it was built to sit
#: *opposite* a human. A fully simulated room needs ten, and the tenth is another ``balanced``
#: because that is the modal fitted manager (the room already runs three). Adding a *different*
#: personality would change the composition the shipped room was validated at, which is a separate
#: question from the one T15 asks; ``--room`` overrides this for anyone who wants to ask it.
DEFAULT_FULL_ROOM: tuple[str, ...] = (*DEFAULT_ROOM, "balanced")


# ------------------------------------------------------------------------------------------------
# inputs: the fitted model and the season's board
# ------------------------------------------------------------------------------------------------
def load_opponent_model(path: Path | str = COEF_JSON) -> OpponentModel:
    """The fitted 11.1 conditional logit, read from its analysis artifact.

    ★ **The specs travel with β.** ``adp_spec``/``band`` are read from the same artifact, because
    they are estimation conditions, not settings: a β fit against curved ADP over a widening
    candidate set means nothing paired with a linear transform and a fixed top-40. An artifact
    written before T15 has neither key and falls back to the historical defaults, which is correct —
    that β *was* fit that way.
    """
    art = json.loads(Path(path).read_text())
    coef = art["coefficients"]
    missing = [c for c in ALL_FEATURES if c not in coef]
    assert not missing, f"{path} is missing fitted coefficients: {missing}"
    model = OpponentModel(feature_cols=list(ALL_FEATURES),
                          beta=np.array([float(coef[c]) for c in ALL_FEATURES]),
                          adp_spec=AdpSpec.from_dict(art.get("adp_spec")),
                          band=BandSpec.from_dict(art.get("band")))
    model.width_curve = WidthCurve.from_dict(art.get("width_curve"))
    # T24 — κ rides with the width curve for the same reason `adp_spec` rides with β: the two were
    # chosen **jointly** (`steps/mock_t24_sweep.py`), because narrowing the flat softmax and handing
    # the deviation back per player are one decision. An artifact written before T24 has neither key
    # and falls back to `base=1.0` / `κ=0`, which is the room those numbers were measured in.
    model.private_kappa = float((art.get("private_board") or {}).get("kappa", PRIVATE_KAPPA))
    return model


def board_vintage(raw: pd.DataFrame, source: str = "") -> str:
    """*Which snapshot* answered — the cache-key component T32 was missing.

    ★ **The date is the identity, and it is sufficient because of how the board is selected.**
    :func:`~fantasy_quant.adp.boards._ffc_board` closes with ``QUALIFY snapshot_date =
    MAX(snapshot_date) OVER ()``, so a resolved board is drawn from exactly **one** snapshot date;
    the ECR path does the same on ``as_of``. There is therefore no such thing as a board that mixes
    vintages, and one date names the content completely for a given
    ``(season, scoring, teams, include_dst)`` cell.

    ``source`` is carried too, and not for cosmetics: an FFC board and an ECR board for the same
    season are *different measurements* (``adp/boards.py``: never pool the two into a headline), and
    2025 flips between them depending on ``allow_ecr``. Two measurements must not share a filename.

    An undated board returns ``"nodate"`` rather than raising — the caller's row-count guard is what
    catches staleness in that case, and a board with no date is a reportable oddity, not a crash.
    """
    if raw.empty:
        return "empty"
    src = str(source or "na")
    if "snapshot_date" not in raw.columns:
        return f"{src}-nodate"
    d = pd.to_datetime(raw["snapshot_date"], errors="coerce").max()
    return f"{src}-{'nodate' if pd.isna(d) else pd.Timestamp(d).strftime('%Y%m%d')}"


def room_board(con, season: int, *, scoring: str = "ppr", teams: int = TEAMS_REF,
               allow_ecr: bool = False, enrich: bool = True, include_dst: bool = True,
               cache_dir: Path | str | None = None,
               asof: str | None = None) -> tuple[pd.DataFrame, str]:
    """The board a simulated room drafts, and the source that answered — ``(board, source)``.

    Deliberately routed through :func:`~fantasy_quant.adp.boards.resolve_board` rather than
    ``adp_asof``: that is the function the realized corpus panel is built against, so the sim and
    the corpus are compared on the *same rows with the same ADP*. ``adp_asof`` would also work but
    applies its own as-of filter, and a board that differs by even a snapshot date reintroduces the
    confound this harness exists to remove.

    ``enrich`` attaches the 16.13 read-only risk/value context the personalities' ``signal_weights``
    consult. Without it ``signal_bonus`` silently skips every weighted signal and the room collapses
    toward the raw fitted β — a materially different room, so it is on by default.

    ``allow_ecr`` is **off** here while it is on in ``build_drift_panel``: the pre-registered
    comparison is FFC-boarded seasons only (``adp/boards.py``: never pool the two into a headline).
    2025 is the only ECR season and the corpus side labels it, so it is reported separately.

    ``include_dst`` (T20) is **on here and off everywhere else** — this is the one board that has
    to produce a legal roster rather than a comparable measurement. It is safe because T21 keeps
    defenses out of the choice model's candidate set, so the fitted β never sees a position it was
    not estimated on; they reach a roster only through
    :meth:`~fantasy_quant.draft.simulator.DraftState.mandatory_needs`. Nothing measured moves:
    ``adp/panel.py`` filters to ``OFFENSE`` before the drift panel is built, so the added rows are
    dropped again on the measurement side.

    ``cache_dir`` memoizes the enriched board per ``(season, scoring, teams, include_dst,
    ENRICH_VERSION, vintage)`` — the flag is part of the key because it changes the rows, and a
    cache hit on a board built under the other setting is exactly the silent-stale-input failure
    this repo keeps finding. The Phase-5 cloud behind
    :func:`~fantasy_quant.draft.enrichment.enrich_board` costs ~10 s warm and was measured at
    ~6 min cold, which is fine once and intolerable once per batch.

    ★ **T32 (fixed 2026-07-30): the vintage is in the key.** It was not, and the omission had a
    standing chore pointed straight at it — ``CLAUDE.md`` §2 mandates a Stage-0 FFC pull whenever
    the latest snapshot is >6 days old, and *that pull could not invalidate this cache*.
    ``ENRICH_VERSION`` covers the enrichment but not its **input**, so a fresh board and a stale
    one were the same filename. Measured live on 2026-07-30, immediately after running the chore:
    :func:`~fantasy_quant.adp.boards.resolve_board` returned **244** rows and this function served
    the cached **223**, with 25 players on the fresh board invisible to every caller. See
    :func:`board_vintage` for what identifies a snapshot, and note the guard below: enrichment is a
    pure column attach (``attach_enrichment`` opens with ``board.copy()``), so a cached board whose
    row count differs from the raw one is stale *by construction* and is rebuilt rather than served.
    That makes the cache self-healing even against an in-place edit that leaves the date alone.

    ``asof`` (VH.0) pins which snapshot answers — see
    :func:`~fantasy_quant.adp.boards._ffc_board`. It needs **no** cache-key change of its own,
    and that is T32's fix paying for itself: the key already carries
    :func:`board_vintage`, which names the snapshot the pinned query actually returned, so a
    pinned board and a live one cannot collide in the cache even though neither knows the other
    exists.
    """
    raw, src = boards.resolve_board(con, int(season), str(scoring), int(teams),
                                    allow_ecr=allow_ecr, include_dst=include_dst, asof=asof)
    if raw.empty:
        return raw, src
    if not enrich:
        return raw, src

    cache = None
    if cache_dir is not None:
        tag = "_dst" if include_dst else ""
        cache = (Path(cache_dir) /
                 f"board_{season}_{scoring}_{teams}{tag}_{enrichment.ENRICH_VERSION}"
                 f"_{board_vintage(raw, src)}.parquet")
        if cache.exists():
            cached = pd.read_parquet(cache)
            if len(cached) == len(raw):
                return attach_proj_points(con, int(season), cached, n_teams=int(teams)), src
    board = enrich_board(con, int(season), raw, n_teams=int(teams))
    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        board.to_parquet(cache)
    return attach_proj_points(con, int(season), board, n_teams=int(teams)), src


def attach_proj_points(con, season: int, board: pd.DataFrame, *, n_teams: int = TEAMS_REF,
                       as_of=None) -> pd.DataFrame:
    """Attach ``proj_points`` — the consensus projection, the number a human reads first (T27).

    ★ **Why this is applied here and not folded into** :data:`~fantasy_quant.draft.enrichment.
    VALUE_COLS`, which would be the tidier home: adding a column there changes the enriched board's
    content and therefore has to bump ``ENRICH_VERSION``, invalidating every cached board. That is
    the *correct* discipline for a column a model consumes — a stale cache under a new definition is
    the failure this repo keeps finding — but ``proj_points`` is **display-only**: nothing in
    ``draft/`` weights it, and :func:`~fantasy_quant.draft.optimizer.assemble_value` reads it from
    ``value_board`` directly rather than from the board. So it is attached *outside* the cache
    boundary, where a wrong value cannot be silently persisted, and every cached board keeps its
    ~6-minute cold rebuild.

    Applied to both the cache-hit and the freshly-built path, so a caller cannot get a board that
    has it only sometimes — which would be worse than not having it at all.
    """
    if board.empty or "proj_points" in board.columns:
        return board
    out = board.copy()
    vb = value_board(con, int(season), as_of or draft_date(con, int(season)), n_teams=int(n_teams))
    if vb.empty:
        return out
    proj = (pd.Series(pd.to_numeric(vb["proj_points"], errors="coerce").to_numpy(float),
                      index=vb["player_key"].astype(str)).groupby(level=0).first())
    out["proj_points"] = board_player_key(out).astype(str).map(proj).astype(float)
    return out


# ------------------------------------------------------------------------------------------------
# a fully simulated room
# ------------------------------------------------------------------------------------------------
def full_room(mix: Sequence[str] | None = None, *, n_teams: int = TEAMS_REF,
              seed: int | None = None, fav_teams: tuple[str, ...] = ()) -> tuple[Personality, ...]:
    """A room with a personality in **every** seat (default :data:`DEFAULT_FULL_ROOM`).

    Thin over :func:`~fantasy_quant.draft.personalities.make_room` — same shuffle-under-seed
    semantics, so a personality is never confounded with a draft slot across a batch.
    """
    return make_room(tuple(mix or DEFAULT_FULL_ROOM), n_opponents=int(n_teams), seed=seed,
                     fav_teams=fav_teams)


def full_room_pick_fn(model: OpponentModel, room: Sequence[Personality], *,
                      hype: np.ndarray | None = None, normalize_hype: bool = True,
                      risk=None, **kw):
    """``pick(state, team) -> board label`` for a room where **every** seat is a personality.

    ★ **16.17 — this is now literally one call.** It used to be a verbatim copy of
    :func:`~fantasy_quant.draft.personalities.make_room_pick_fn` differing in a single line: that
    builder mapped ``team -> seat`` by skipping ``state.your_team`` (nine opponents opposite a
    human), while here there is no human and the mapping is the identity. Its own docstring said
    the two "differ only in the ``team -> seat`` mapping they were split over" — a
    :class:`~fantasy_quant.draft.personalities.SeatMap` with **zero** human seats is that
    observation carried to its conclusion, and the duplicated body is deleted rather than left
    beside the general one (the T18/F.5 rule: a second copy is how the two drift apart).

    ``require_objectives=False`` preserves this function's own contract exactly — a
    ``portfolio_ce`` seat with no ``risk`` falls back to the behavioral path here rather than
    raising, because :func:`simulate_room_draft` already runs
    :func:`~fantasy_quant.draft.personalities.assert_room_objectives` before calling it and some
    ADP-only harnesses legitimately have no value index.
    """
    return make_room_pick_fn(model, tuple(room), hype=hype, normalize_hype=normalize_hype,
                             risk=risk, require_objectives=False,
                             seat_map=SeatMap(tuple(room)), **kw)


def simulate_room_draft(board: pd.DataFrame, room: Sequence[Personality], model: OpponentModel, *,
                        n_teams: int = TEAMS_REF, rounds: int = 15, seed: int = 0,
                        hype: np.ndarray | None = None,
                        slots: RosterSlots | None = None, **kw) -> DraftState:
    """One seeded snake draft in which all ``n_teams`` seats are personalities.

    ★ **16.17 — the room is now declared, not worked around.** ``run_to_completion`` used to route
    ``your_team`` to ``your_pick_fn``, so this harness had to point that seat back at its own room
    function by hand — otherwise one seat in every batch draft would silently be chalk, which is
    exactly the behaviour bar #3 measures. ``human_teams=frozenset()`` says the true thing instead
    (*this room has no human*), and every seat goes through ``opponent_pick_fn``. ``your_team``
    stays 0 so the pick log's ``is_you`` column is unchanged — the batch artifacts are differenced
    on it.
    """
    if len(room) != n_teams:
        raise ValueError(f"room has {len(room)} seats for {n_teams} teams")
    assert_room_objectives(room, kw.get("risk"))
    b = _prepare_board(board)
    pick = full_room_pick_fn(model, room, hype=hype, **kw)
    state = DraftState(
        board=b, n_teams=n_teams, rounds=rounds, slots=slots or RosterSlots(),
        your_team=0, rng=np.random.default_rng(seed), noise=0.0,
        available=set(b.index), rosters=[[] for _ in range(n_teams)],
        human_teams=frozenset(),
    )
    return run_to_completion(state, opponent_pick_fn=pick)


# ------------------------------------------------------------------------------------------------
# the bridge: a simulated draft, in the realized corpus's own frame
# ------------------------------------------------------------------------------------------------
def sim_drift_panel(state: DraftState, *, season: int, draft_id: str,
                    board_source: str = boards.FFC, scoring: str = "ppr",
                    board_teams: int = TEAMS_REF, start_ts: pd.Timestamp | None = None,
                    stdev: pd.Series | None = None, seed: int = 0,
                    room: Sequence[Personality] | None = None) -> pd.DataFrame:
    """A finished simulated draft as a drift panel — :data:`PANEL_COLS`, plus sim-only extras.

    Every derived column repeats :func:`~fantasy_quant.adp.drift_panel.build_drift_panel`'s
    arithmetic exactly (offense filter first, then centering, so the draft mean is taken over the
    same rows on both sides). The extras — ``seat_personality``, ``seed`` — are appended, never
    substituted, so a function that reads only ``PANEL_COLS`` cannot tell the two apart.

    **One honest asymmetry, and it favours neither side:** every simulated pick is on the board by
    construction, whereas the corpus panel inner-joins and keeps only *boarded* picks. The corpus
    therefore drops late-round picks of unboarded players; the sim has none to drop. Both sides are
    "boarded picks only", which is the comparison T15 quotes.
    """
    log = pd.DataFrame(state.log)
    if log.empty:
        return pd.DataFrame(columns=[*PANEL_COLS, "seat_personality", "seed"])

    out = pd.DataFrame({
        "season": int(season),
        "draft_id": str(draft_id),
        "teams": int(state.n_teams),
        "scoring": str(scoring),
        "start_ts": pd.Timestamp(start_ts) if start_ts is not None else pd.NaT,
        # the sim drafts the board on the board's own date, so there is no board/draft gap to model
        "days_to_board": 0.0,
        "pick_no": log["overall_pick"].astype(int),
        "round": log["round"].astype(int),
        # corpus draft_slot is 1-based; simulator teams are 0-based and team 0 picks first
        "draft_slot": log["team"].astype(int) + 1,
        "gsis_id": log["player_key"].astype(str),
        "name": log["player_name"].astype(str),
        "pos": _canon_pos(log["pos"]),
        "adp": pd.to_numeric(log["adp"], errors="coerce"),
        "board_teams": int(board_teams),
        "board_source": str(board_source),
    })
    out["seat_personality"] = (
        pd.Series([room[t].name for t in log["team"]], index=out.index) if room is not None
        else pd.Series(pd.NA, index=out.index, dtype="object"))
    out["seed"] = int(seed)

    key = out["gsis_id"]
    out["adp_stdev"] = key.map(stdev).astype(float) if stdev is not None else np.nan

    # --- offense filter BEFORE centering, matching build_drift_panel's order ---------------------
    out = out[out["pos"].isin(OFFENSE)].copy()
    out["slot_rounds"] = out["pick_no"] / out["teams"]
    out["adp_rounds"] = out["adp"] / out["board_teams"]
    out["drift"] = out["adp_rounds"] - out["slot_rounds"]
    out["drift_centered"] = out["drift"] - out.groupby("draft_id")["drift"].transform("mean")
    out = out.dropna(subset=["drift"])
    return out[[*PANEL_COLS, "seat_personality", "seed"]].reset_index(drop=True)


def batch_drafts(board: pd.DataFrame, room: Sequence[Personality], model: OpponentModel, *,
                 season: int, seeds: Iterable[int], n_teams: int = TEAMS_REF,
                 rounds: int = 15, board_source: str = boards.FFC, scoring: str = "ppr",
                 start_ts: pd.Timestamp | None = None, hype_fn=None,
                 **kw) -> tuple[pd.DataFrame, pd.DataFrame]:
    """``len(seeds)`` seeded drafts, as ``(drift_panel, pick_log)`` from **one** pass.

    ``hype_fn(seed) -> np.ndarray | None`` supplies the per-draft 16.9 narrative draw; the default
    (``None``) runs the room with the hype channel closed, which is the right baseline because 16.15
    measured the shipped shock as a null and T15's defect is ~10x larger than it.

    ★ **Two frames because the panel cannot answer a roster question.** The drift panel is
    offense-only by construction — that is what makes it comparable to the human corpus — so it
    drops every K and DST and cannot see whether a seat finished able to field a lineup. T23 was
    invisible to every panel-based bar for exactly that reason. The log is every pick at every
    position, and :func:`roster_legality` reads it.
    """
    stdev = None
    if "stdev" in board.columns:
        stdev = pd.Series(pd.to_numeric(board["stdev"], errors="coerce").to_numpy(),
                          index=board_player_key(board).astype(str)).groupby(level=0).first()

    seats = {i: p.name for i, p in enumerate(room)}
    frames, logs = [], []
    for s in seeds:
        st = simulate_room_draft(board, room, model, n_teams=n_teams, rounds=rounds, seed=int(s),
                                 hype=hype_fn(int(s)) if hype_fn is not None else None, **kw)
        draft_id = f"sim-{season}-{int(s):04d}"
        frames.append(sim_drift_panel(
            st, season=season, draft_id=draft_id, board_source=board_source,
            scoring=scoring, board_teams=n_teams, start_ts=start_ts, stdev=stdev, seed=int(s),
            room=room))
        log = st.pick_log()
        if not log.empty:
            log = log.assign(season=int(season), draft_id=draft_id, seed=int(s),
                             seat_personality=log["team"].map(seats))
            logs.append(log)
    if not frames:
        return (pd.DataFrame(columns=[*PANEL_COLS, "seat_personality", "seed"]), pd.DataFrame())
    return (pd.concat(frames, ignore_index=True),
            pd.concat(logs, ignore_index=True) if logs else pd.DataFrame())


def batch_drift_panel(board: pd.DataFrame, room: Sequence[Personality], model: OpponentModel, *,
                      season: int, seeds: Iterable[int], **kw) -> pd.DataFrame:
    """:func:`batch_drafts`' panel half — the signature every T15/16.14R step already calls."""
    return batch_drafts(board, room, model, season=season, seeds=seeds, **kw)[0]


# ------------------------------------------------------------------------------------------------
# measurement — every function below runs unchanged on a sim panel or a corpus panel
# ------------------------------------------------------------------------------------------------
def _picks(rounds_value: pd.Series) -> pd.Series:
    """Rounds -> 10-team ADP picks. The only place :data:`TEAMS_REF` is applied."""
    return rounds_value * TEAMS_REF


def reach_profile(panel: pd.DataFrame, *, max_round: int = 15) -> pd.DataFrame:
    """Per round: how far from the board the room drafted, in 10-team ADP picks.

    This is the table T15 quotes and bar #1 is stated against. ``mean``/``p90`` are of **|drift|**
    (the magnitude of the deviation, reaches and falls together) because that is how the corpus
    figures already written down were computed; the signed mean is reported alongside so a room
    that reaches and a room that falls are still distinguishable.
    """
    if panel.empty:
        return pd.DataFrame(columns=["round", "n", "mean_abs", "p90_abs", "mean_signed"])
    p = panel[panel["round"] <= max_round]
    d = _picks(p["drift"])
    g = pd.DataFrame({"round": p["round"], "abs": d.abs(), "signed": d}).groupby("round")
    out = pd.DataFrame({
        "n": g.size(),
        "mean_abs": g["abs"].mean(),
        "p90_abs": g["abs"].quantile(0.90),
        "mean_signed": g["signed"].mean(),
    }).reset_index()
    return out


def elite_fall_profile(panel: pd.DataFrame, *, adp_cut: float = 12.0,
                       fall_past: float = 10.0) -> dict:
    """How far the consensus elite actually fall — bar #2's measurement.

    ``adp_cut`` is in board picks (ADP <= 12 is "a consensus top-12 player"); the returned slots are
    in 10-team picks so a 12-team draft's pick 20 is not compared to a 10-team draft's pick 20.
    """
    if panel.empty:
        return {"n": 0}
    e = panel[pd.to_numeric(panel["adp"], errors="coerce") <= adp_cut]
    if e.empty:
        return {"n": 0}
    slot = _picks(e["slot_rounds"])
    return {
        "n": int(len(e)),
        "mean_slot": float(slot.mean()),
        "p95_slot": float(slot.quantile(0.95)),
        "max_slot": float(slot.max()),
        f"share_past_{int(fall_past)}": float((slot > fall_past).mean()),
    }


# ------------------------------------------------------------------------------------------------
# T24 — the signed companion: WHERE the consensus elite land, not how far anyone strayed
# ------------------------------------------------------------------------------------------------
#: ADP bands the landing profile reports, in board picks. The first is "the consensus top two" —
#: the band the 2026-07-28 objection was about, and the one a round-indexed width curve cannot
#: distinguish from the rest of round 1.
LANDING_BANDS: tuple[tuple[float, float], ...] = ((0.0, 2.5), (2.5, 4.5), (4.5, 6.5), (6.5, 10.5))

#: Landing thresholds, in 10-team picks: what share of a band cleared pick 4 / 6 / 10.
LANDING_PAST: tuple[float, ...] = (4.0, 6.0, 10.0)

#: How far above the corpus's own share the simulated share of top-tier players falling past
#: :data:`LANDING_GATE_PAST` may sit. Same construction as :data:`ELITE_PAST10_MAX` — a corpus
#: quantile plus a stated margin, so the gate fails on a defect rather than on sampling noise.
LANDING_GATE_PAST: float = 4.0
LANDING_GATE_MARGIN: float = 0.05


def landing_profile(panel: pd.DataFrame, *, bands: Sequence[tuple[float, float]] = LANDING_BANDS,
                    past: Sequence[float] = LANDING_PAST) -> pd.DataFrame:
    """Where players of a given ADP actually get taken, in 10-team picks — bar #1's signed half.

    ★ **Why this exists at all.** Round-1 mean |reach| reads **2.91 simulated vs 2.87 corpus** — a
    clean pass — while the consensus #2 lands at a median pick of 4 and clears pick 4 42 % of the
    time against a realized 12 %. *A reach and a fall have the same absolute value and cancel inside
    the mean*, so an |drift| bar is structurally blind to a one-sided defect. This is T15's *"an
    aggregate metric cannot see an impossible event"* one level down: there the aggregation was over
    drafts, here it is over **direction**, inside a metric that already passes.

    Runs unchanged on a simulated panel and on the human corpus: ``slot_rounds`` is picks ÷ that
    draft's own team count, so a 12-team room's pick 12 and a 10-team room's pick 10 are both "the
    end of round 1" rather than being compared as raw pick numbers.
    """
    cols = ["band", "n", "mean_slot", "median_slot", "p90_slot", "p99_slot",
            *[f"past_{int(p)}" for p in past]]
    if panel.empty:
        return pd.DataFrame(columns=cols)
    adp = pd.to_numeric(panel["adp"], errors="coerce")
    slot = _picks(panel["slot_rounds"])
    rows = []
    for lo, hi in bands:
        s = slot[(adp > lo) & (adp <= hi)].dropna()
        if s.empty:
            continue
        row = {"band": f"{lo:g}-{hi:g}", "n": int(len(s)), "mean_slot": float(s.mean()),
               "median_slot": float(s.median()), "p90_slot": float(s.quantile(0.90)),
               "p99_slot": float(s.quantile(0.99))}
        row.update({f"past_{int(p)}": float((s > p).mean()) for p in past})
        rows.append(row)
    return pd.DataFrame(rows, columns=cols)


def landing_by_player(panel: pd.DataFrame, *, top_n: int = 10,
                      past: Sequence[float] = LANDING_PAST) -> pd.DataFrame:
    """The same measurement per player, for the top ``top_n`` of the board — the eyeball readout.

    The band table is the gate; this is what a human recognises. "Gibbs lands at a median pick of 4"
    is the sentence that opened T24, and no aggregate says it.
    """
    cols = ["name", "adp", "n", "mean_slot", "median_slot", "p90_slot", "max_slot",
            *[f"past_{int(p)}" for p in past]]
    if panel.empty:
        return pd.DataFrame(columns=cols)
    p = panel.assign(_adp=pd.to_numeric(panel["adp"], errors="coerce"),
                     _slot=_picks(panel["slot_rounds"])).dropna(subset=["_adp", "_slot"])
    g = p.groupby(["gsis_id", "name"], sort=False)
    out = pd.DataFrame({
        "adp": g["_adp"].mean(), "n": g.size(), "mean_slot": g["_slot"].mean(),
        "median_slot": g["_slot"].median(), "p90_slot": g["_slot"].quantile(0.90),
        "max_slot": g["_slot"].max(),
        **{f"past_{int(x)}": g["_slot"].apply(lambda s, x=x: float((s > x).mean())) for x in past},
    }).reset_index().drop(columns="gsis_id")
    return out.nsmallest(top_n, "adp")[cols].reset_index(drop=True)


def round1_split(panel: pd.DataFrame, *, rnd: int = 1) -> pd.DataFrame:
    """Mean |drift| in the first vs the second half of a round, in 10-team picks.

    ⚠ **Split by position *within* the round, never by raw pick number.** The corpus runs 8- to
    14-team rooms, so "pick ≤ 5" is the first half of a 10-team round and the first 42 % of a
    12-team one; a raw-pick split silently compares different fractions of the round on the two
    sides. The corpus rises across round 1 and a flat sim is the defect T24 names — that claim is
    only readable once both sides are measured at the same point in the round.
    """
    cols = ["half", "n", "mean_abs", "p90_abs"]
    if panel.empty:
        return pd.DataFrame(columns=cols)
    p = panel[panel["round"] == int(rnd)]
    if p.empty:
        return pd.DataFrame(columns=cols)
    teams = pd.to_numeric(p["teams"], errors="coerce")
    frac = (p["pick_no"] - (int(rnd) - 1) * teams) / teams      # (0, 1] through the round
    d = _picks(p["drift"]).abs()
    rows = []
    for label, mask in (("first_half", frac <= 0.5), ("second_half", frac > 0.5)):
        s = d[mask].dropna()
        if s.empty:
            continue
        rows.append({"half": label, "n": int(len(s)), "mean_abs": float(s.mean()),
                     "p90_abs": float(s.quantile(0.90))})
    return pd.DataFrame(rows, columns=cols)


def gate_elite_landing(sim: pd.DataFrame, corpus: pd.DataFrame, *,
                       band: tuple[float, float] = LANDING_BANDS[0],
                       past: float = LANDING_GATE_PAST,
                       margin: float = LANDING_GATE_MARGIN) -> dict:
    """**Bar #1's signed companion**: consensus-top-tier players must land where they really land.

    Two components, both one-sided in the direction of the defect:

    ``fall``   the share of the top band clearing ``past`` may exceed the corpus's own share by at
               most ``margin``. Falling *less* than reality is not what T24 is about.
    ``shape``  |drift| must **rise** across round 1, as it does in the corpus. A flat round 1 is the
               within-round heterogeneity a round-indexed curve cannot express.

    Stated against the corpus rather than a chosen number, so passing it is a claim about the human
    corpus and not about anyone's taste — the same construction as :func:`gate_elite_fall`.
    """
    key = f"past_{int(past)}"
    s = landing_profile(sim, bands=[band]).set_index("band")
    c = landing_profile(corpus, bands=[band]).set_index("band")
    if s.empty or c.empty:
        return {"pass": False, "reason": "no picks in the top band on one side"}
    b = s.index[0]
    sim_share, corpus_share = float(s.loc[b, key]), float(c.loc[b, key])
    fall_ok = sim_share <= corpus_share + margin

    ss, cs = round1_split(sim), round1_split(corpus)
    shape = {}
    if len(ss) == 2 and len(cs) == 2:
        ss, cs = ss.set_index("half"), cs.set_index("half")
        sim_rise = float(ss.loc["second_half", "mean_abs"] - ss.loc["first_half", "mean_abs"])
        corpus_rise = float(cs.loc["second_half", "mean_abs"] - cs.loc["first_half", "mean_abs"])
        shape = {"sim_rise": sim_rise, "corpus_rise": corpus_rise,
                 "shape_pass": bool(sim_rise > 0) if corpus_rise > 0 else True}
    return {"pass": bool(fall_ok and shape.get("shape_pass", True)),
            "band": str(b), "metric": key, "sim_share": sim_share,
            "corpus_share": corpus_share, "margin": float(margin),
            "sim_median_slot": float(s.loc[b, "median_slot"]),
            "corpus_median_slot": float(c.loc[b, "median_slot"]),
            "fall_pass": bool(fall_ok), "n_sim": int(s.loc[b, "n"]), "n_corpus": int(c.loc[b, "n"]),
            **shape}


# ------------------------------------------------------------------------------------------------
# T23 — roster legality, stated over the WHOLE starting lineup
# ------------------------------------------------------------------------------------------------
def board_supply(board: pd.DataFrame) -> dict[str, int]:
    """How many draftable players a board carries per canonical position."""
    if board.empty:
        return {}
    col = "pos" if "pos" in board.columns else "position"
    return board[col].map(canon_pos).value_counts().to_dict()


def roster_legality(log: pd.DataFrame, *, slots: RosterSlots | None = None,
                    supply: dict[int, dict[str, int]] | None = None,
                    n_teams: int = TEAMS_REF) -> dict:
    """Can every seat field its **whole** starting lineup? Reads the pick log, not the panel.

    ★ **The bar is the contract, not the symptom.** T20 shipped a deadline filter whose done-bar
    was *"60/60 seats finish with ≥1 K and ≥1 DST"* — the two positions that ticket was written
    about. It passed while the same filter left **TE** unguarded and 12.2 % of seats finished
    unable to fill the dedicated TE slot. A guarantee stated as *no unfillable starting slot* has
    to be tested against every slot, so demand comes from :meth:`RosterSlots.base_demand` rather
    than a hand-written list, and a roster change is picked up automatically.

    FLEX is not counted because it is excluded from ``base_demand`` by construction — it is the one
    slot a surplus can flow *into*. ⚠ It does not flow the other way: a seat holding one RB cannot
    fill ``RB/RB``, so RB/WR belong in the demand too. The old exemption was unsound for them as
    well; it was merely never binding, because RB/WR demand is met long before the deadline.

    ★ **Pass ``supply`` or the bar asserts something no code can satisfy.** Historical FFC boards
    are thin at the ends: 2022 carries **5** kickers and **6** defenses for a ten-seat room, 2017
    carries 8 kickers. Half those seats *cannot* finish with a kicker, and no deadline filter can
    conjure one. Measured over 2017–2024 + 2026 the raw illegal share is 23.2 %, of which K (7.8 %)
    and DST (4.4 %) match the supply shortfall to three decimals — i.e. they are **not defects**.
    ``supply`` maps season to :func:`board_supply`, and the ``avoidable`` figures are what a fix is
    accountable for. *A bar that cannot be passed teaches a team to ignore it.*
    """
    need = dict((slots or RosterSlots()).base_demand())
    if log.empty:
        return {"n_seats": 0, "n_illegal": 0, "share_illegal": 0.0, "by_position": {},
                "by_personality": {}, "starter_min": need}
    keys = [k for k in ("season", "draft_id", "team") if k in log.columns]
    # ⚠ `simulator.canon_pos`, NOT `panel._canon_pos` — the panel's canonicaliser is an *offense*
    # one and maps K/DST to NaN, so using it here reports every seat as missing a kicker it
    # actually drafted. A missing entity and a failed join look identical (the `LA`/`LAR` lesson);
    # a legality bar is exactly where that mistake is invisible, because "0 kickers" is plausible.
    counts = (log.assign(_pos=log["pos"].map(canon_pos))
              .groupby(keys)["_pos"].value_counts().unstack(fill_value=0))
    for p in need:
        if p not in counts.columns:
            counts[p] = 0
    short = pd.DataFrame({p: counts[p] < n for p, n in need.items()}, index=counts.index)
    bad = short.any(axis=1)
    out = {"n_seats": int(len(counts)), "n_illegal": int(bad.sum()),
           "share_illegal": float(bad.mean()),
           "by_position": {p: float(short[p].mean()) for p in need},
           "starter_min": need}

    if supply is not None and "season" in log.columns:
        # a season's board serves `floor(available / demand)` seats at that position; the rest are
        # short for a reason no pick policy can fix, so they are excluded from the avoidable count
        seasons = counts.index.get_level_values("season")
        unavoidable = pd.DataFrame(
            {p: [max(0, int(n_teams) - supply.get(int(s), {}).get(p, 0) // n)
                 for s in seasons] for p, n in need.items()}, index=counts.index)
        # within a season, the seats that go short ARE the ones the board could not serve, so a
        # per-position count comparison is exact even though the identity of the seats is not
        by_season = short.groupby(seasons).sum()
        cap = unavoidable.groupby(seasons).max()
        n_draft = counts.groupby(seasons).size() / int(n_teams)
        avoidable = (by_season - cap.mul(n_draft, axis=0)).clip(lower=0)
        out["unavoidable_by_position"] = {p: float(cap[p].mul(n_draft).sum() / len(counts))
                                          for p in need}
        out["avoidable_by_position"] = {p: float(avoidable[p].sum() / len(counts)) for p in need}
        out["share_avoidable"] = float(sum(out["avoidable_by_position"].values()))
    if "seat_personality" in log.columns:
        seat = log.groupby(keys)["seat_personality"].first()
        out["by_personality"] = {str(k): float(v) for k, v in
                                 bad.groupby(seat).mean().sort_values(ascending=False).items()}
    else:
        out["by_personality"] = {}
    return out


def pool_rank(panel: pd.DataFrame) -> pd.Series:
    """For each pick: how many better-ADP players the seat passed over, 1 = best available.

    ★ **This is why bar #3 needs its own measure rather than |drift|.** A chalk seat in a room full
    of reachers records a large |drift| — not because it deviated, but because everyone else did and
    it harvested the fall. Ranking a seat's own choice inside the pool it faced separates *what the
    seat did* from *what was done to it*, and it is computable identically on a simulated and a
    realized draft.

    The pool is reconstructed from the panel itself: at pick ``k`` the still-available boarded
    players are exactly those taken later in that draft. Players nobody drafted are missing, but
    they are missing from the *bottom* of the board (that is why they went undrafted), so they
    cannot displace anyone from the better-ADP count this measures.
    """
    if panel.empty:
        return pd.Series(dtype=float)
    out = pd.Series(np.nan, index=panel.index, dtype=float)
    for _, g in panel.groupby("draft_id", sort=False):
        pick_no = g["pick_no"].to_numpy(float)
        adp = pd.to_numeric(g["adp"], errors="coerce").to_numpy(float)
        # better[i, j] : j is still available at i's turn AND ranks ahead of i on the board
        later = pick_no[None, :] > pick_no[:, None]
        better = adp[None, :] < adp[:, None]
        out.loc[g.index] = 1.0 + (later & better).sum(axis=1)
    return out


def seat_table(panel: pd.DataFrame) -> pd.DataFrame:
    """One row per drafting seat — its behaviour (``pool_rank``) and its outcome (``drift``).

    ``mean_drift_picks`` keeps the panel's sign: **positive = the seat reached**, so the
    value-harvesting chalk seat T15 measured at −19.8 shows up negative. ``harvest_picks`` is the
    same number negated and named for what it is, because "surplus" reading negative is how the
    bar gets misquoted.
    """
    cols = ["draft_id", "season", "draft_slot", "seat_personality", "n_picks",
            "mean_pool_rank", "median_pool_rank", "mean_drift_picks", "harvest_picks",
            "mean_abs_drift_picks"]
    if panel.empty:
        return pd.DataFrame(columns=cols)
    p = panel.copy()
    p["_rank"] = pool_rank(p)
    p["_drift"] = _picks(p["drift"])
    if "seat_personality" not in p.columns:
        p["seat_personality"] = pd.NA
    g = p.groupby(["draft_id", "season", "draft_slot"], dropna=False)
    out = pd.DataFrame({
        "seat_personality": g["seat_personality"].first(),
        "n_picks": g.size(),
        "mean_pool_rank": g["_rank"].mean(),
        "median_pool_rank": g["_rank"].median(),
        "mean_drift_picks": g["_drift"].mean(),
        "mean_abs_drift_picks": g["_drift"].apply(lambda s: s.abs().mean()),
    }).reset_index()
    out["harvest_picks"] = -out["mean_drift_picks"]
    return out[cols]


def faithful_harvest(panel: pd.DataFrame, *, quantile: float = 0.20,
                     min_picks: int = 8) -> dict:
    """Bar #3: what the room's most ADP-faithful seats take home, in 10-team picks.

    "Most faithful" is the lowest-``mean_pool_rank`` ``quantile`` of seats — a behavioural
    definition, so the same threshold means the same thing in a simulated room and in 1,144 realized
    ones. The bar is that the simulated figure matches the corpus figure: a room nobody can beat by
    sitting on the board is a room whose deviations are the wrong size.
    """
    seats = seat_table(panel)
    seats = seats[seats["n_picks"] >= min_picks]
    if seats.empty:
        return {"n_seats": 0}
    cut = float(seats["mean_pool_rank"].quantile(quantile))
    faithful = seats[seats["mean_pool_rank"] <= cut]
    return {
        "n_seats": int(len(seats)),
        "n_faithful": int(len(faithful)),
        "pool_rank_cut": cut,
        "faithful_mean_pool_rank": float(faithful["mean_pool_rank"].mean()),
        "faithful_harvest_picks": float(faithful["harvest_picks"].mean()),
        "faithful_harvest_p90": float(faithful["harvest_picks"].quantile(0.90)),
        "room_harvest_picks": float(seats["harvest_picks"].mean()),
    }


#: Fixed ``mean_pool_rank`` bin edges for :func:`harvest_curve`. **Fixed, not quantile**, and that
#: is the whole point: the simulated room and the human corpus have different faithfulness
#: distributions, so "the most faithful quintile of each" compares a robot to a person and calls it
#: a match. Absolute edges ask the answerable question — *a seat that deviates this much, in either
#: population, takes home how much?*
POOL_RANK_BINS: tuple[float, ...] = (1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 20.0, np.inf)


def harvest_curve(panel: pd.DataFrame, *, bins: Sequence[float] = POOL_RANK_BINS,
                  min_picks: int = 8) -> pd.DataFrame:
    """Harvest (10-team picks) against how ADP-faithful the seat was — bar #3's primary form.

    ★ **Measured 2026-07-27, and it is why the quantile version of this bar is not enough.** The
    corpus's *most faithful* quintile of managers still sits at ``mean_pool_rank`` ~4.3: a real
    chalk drafter passes on four better-ADP players a pick. The simulated ``autopilot`` sits at
    **1.16** — it is more faithful than any sizeable group of humans. So "compare the top quintile
    of each" silently compares two different behaviours, and the gap it reports mixes *how much the
    room reaches* with *how chalky the chalk seat is*. Binning both populations on the same absolute
    edges removes that: read the same row of this table on each side.
    """
    seats = seat_table(panel)
    seats = seats[seats["n_picks"] >= min_picks]
    if seats.empty:
        return pd.DataFrame(columns=["pool_rank_bin", "n_seats", "mean_pool_rank",
                                     "harvest_picks", "harvest_sd"])
    b = pd.cut(seats["mean_pool_rank"], bins=list(bins), right=False)
    g = seats.groupby(b, observed=True)
    return pd.DataFrame({
        "n_seats": g.size(),
        "mean_pool_rank": g["mean_pool_rank"].mean(),
        "harvest_picks": g["harvest_picks"].mean(),
        "harvest_sd": g["harvest_picks"].std(ddof=0),
    }).reset_index(names="pool_rank_bin")


def faithfulness_profile(panel: pd.DataFrame, *, bins: Sequence[float] = POOL_RANK_BINS,
                         min_picks: int = 8) -> pd.DataFrame:
    """What share of seats deviate from the board by how much — the *population* of drafters.

    ★ **Measured 2026-07-27: this is the defect T15 could not see, and it is not "reaches are too
    wide".** Real managers are a continuum — median ``mean_pool_rank`` ~7.6, with 54 % of seats
    between 2 and 8. The simulated room is **bimodal**: ``autopilot`` at 1.16 and everyone else past
    7, with almost nothing in the band where half of real drafters actually live. The room has no
    moderate drafters. That reframes bar #3, because at *matched* faithfulness the harvest is
    roughly right (:func:`harvest_curve`); what is wrong is who is sitting in the room.
    """
    seats = seat_table(panel)
    seats = seats[seats["n_picks"] >= min_picks]
    if seats.empty:
        return pd.DataFrame(columns=["pool_rank_bin", "n_seats", "share"])
    b = pd.cut(seats["mean_pool_rank"], bins=list(bins), right=False)
    g = seats.groupby(b, observed=False).size()
    return pd.DataFrame({"n_seats": g, "share": g / g.sum()}).reset_index(names="pool_rank_bin")


def faithfulness_summary(panel: pd.DataFrame, *, min_picks: int = 8,
                         moderate: tuple[float, float] = (2.0, 8.0)) -> dict:
    """Scalar summary of the seat-faithfulness distribution, incl. the missing-middle share."""
    seats = seat_table(panel)
    seats = seats[seats["n_picks"] >= min_picks]
    if seats.empty:
        return {"n_seats": 0}
    r = seats["mean_pool_rank"]
    lo, hi = moderate
    return {
        "n_seats": int(len(r)),
        "mean_pool_rank": float(r.mean()),
        "median_pool_rank": float(r.median()),
        "p10_pool_rank": float(r.quantile(0.10)),
        "p90_pool_rank": float(r.quantile(0.90)),
        # where the majority of real managers sit; the bimodal sim room is nearly empty here
        "moderate_share": float(((r >= lo) & (r < hi)).mean()),
        "chalk_share": float((r < lo).mean()),
    }


def personality_table(panel: pd.DataFrame) -> pd.DataFrame:
    """Per-personality behaviour across a batch — sim panels only (needs ``seat_personality``)."""
    seats = seat_table(panel)
    seats = seats[seats["seat_personality"].notna()]
    if seats.empty:
        return pd.DataFrame(columns=["seat_personality", "n_seats", "mean_pool_rank",
                                     "mean_drift_picks", "harvest_picks"])
    g = seats.groupby("seat_personality")
    return pd.DataFrame({
        "n_seats": g.size(),
        "mean_pool_rank": g["mean_pool_rank"].mean(),
        "mean_drift_picks": g["mean_drift_picks"].mean(),
        "harvest_picks": g["harvest_picks"].mean(),
    }).reset_index().sort_values("mean_drift_picks", ascending=False)


#: Round buckets the per-personality readout is split on. The last one is separated because a seat's
#: reported reach there is mostly *when it took its K and DST*, not how it drafts.
ROUND_BUCKETS: tuple[tuple[int, int, str], ...] = (
    (1, 3, "R1-3"), (4, 6, "R4-6"), (7, 10, "R7-10"), (11, 13, "R11-13"), (14, 15, "R14-15"))


def personality_buckets(panel: pd.DataFrame, *, value: str = "pool_rank",
                        buckets: Sequence[tuple[int, int, str]] = ROUND_BUCKETS) -> pd.DataFrame:
    """Per-personality ``pool_rank`` by round bucket — **the reporting rule T25 adopted**.

    ★ **Lead with this, not with a 15-round mean reach.** A mean reach over all 15 rounds is
    dominated by late-board ADP noise — Tyler Allgeier at ADP 167 taken at pick 119 scores **+48**
    and means nothing, because nobody else was taking Allgeier at 119 either — and by *when* a seat
    takes its K/DST. Reporting it that way is what produced the 2026-07-28 "the reacher reaches less
    than balanced" objection, which the batch then contradicted overall while revealing a **real**
    inversion confined to rounds 1–3. The bucket split is what makes both facts visible at once.

    ``value="drift_picks"`` gives the same table in reach units, for the cases where picks are the
    question being asked.
    """
    if panel.empty or "seat_personality" not in panel.columns:
        return pd.DataFrame()
    p = panel[panel["seat_personality"].notna()].copy()
    if p.empty:
        return pd.DataFrame()
    p["pool_rank"] = pool_rank(p)
    p["drift_picks"] = _picks(p["drift"])
    edges = [b[0] - 1 for b in buckets] + [buckets[-1][1]]
    p["bucket"] = pd.cut(p["round"], edges, labels=[b[2] for b in buckets])
    out = p.pivot_table(index="seat_personality", columns="bucket", values=value,
                        aggfunc="mean", observed=True)
    out["overall"] = p.groupby("seat_personality")[value].mean()
    return out.sort_values("overall")


def compare_profiles(sim: pd.DataFrame, corpus: pd.DataFrame, *,
                     max_round: int = 15) -> pd.DataFrame:
    """The bar-#1 table: sim vs corpus reach profile side by side, with the gap."""
    s = reach_profile(sim, max_round=max_round).set_index("round")
    c = reach_profile(corpus, max_round=max_round).set_index("round")
    out = pd.DataFrame({
        "corpus_mean": c["mean_abs"], "sim_mean": s["mean_abs"],
        "corpus_p90": c["p90_abs"], "sim_p90": s["p90_abs"],
        "corpus_n": c["n"], "sim_n": s["n"],
    })
    out["mean_gap"] = out["sim_mean"] - out["corpus_mean"]
    out["mean_ratio"] = out["sim_mean"] / out["corpus_mean"]
    return out.reset_index()


def profile_trend(profile: pd.DataFrame) -> float:
    """Spearman rank correlation of ``mean_abs`` with round — the *shape* T15 says is missing.

    The corpus curve rises monotonically (3.3 -> 27.1 picks) and the simulator's is flat, so a
    scalar a fix has to move is more useful here than any single round's number.
    """
    if len(profile) < 3:
        return float("nan")
    return float(profile["round"].corr(profile["mean_abs"], method="spearman"))


# ------------------------------------------------------------------------------------------------
# T15 step 2 — the two judgement-free gates
# ------------------------------------------------------------------------------------------------
#: Bar #2's thresholds, in 10-team picks, taken from the realized corpus rather than from taste:
#: consensus top-12 players land at mean pick 7.8 with **p95 = 17.5**, and 18.9 % fall past pick 10.
#: The gate allows the simulated p95 to reach :data:`ELITE_P95_MAX` and the past-10 share to reach
#: :data:`ELITE_PAST10_MAX` — both a deliberate margin above the corpus so the gate fails on a
#: *defect*, not on sampling noise. Step 0 measured the shipped room at p95 30.0 / 57.9 %.
ELITE_ADP_CUT: float = 12.0
ELITE_P95_MAX: float = 20.0
ELITE_PAST10_MAX: float = 0.30

#: Bar #3's tolerance: how far the simulated harvest may sit from the corpus's, in units of the
#: corpus's **own** between-seat sd inside the same fixed ``pool_rank`` bin. One sd is generous by
#: design — the claim being tested is "an ADP-follower does not harvest more than a human
#: ADP-follower does", not "the two agree to a decimal".
HARVEST_TOL_SDS: float = 1.0


def gate_elite_fall(panel: pd.DataFrame, *, adp_cut: float = ELITE_ADP_CUT,
                    p95_max: float = ELITE_P95_MAX,
                    past10_max: float = ELITE_PAST10_MAX) -> dict:
    """**Bar #2**: consensus elites must not fall past where they realistically fall.

    Judgement-free in the sense that matters — every threshold is a corpus quantile plus a stated
    margin, so passing it is a statement about the human corpus and not about anyone's taste. This
    is the gate the live mock draft would have failed by eye in its first round, and which no
    aggregate metric in the repo could see: *an aggregate scores better-than-baseline, never
    possible.*
    """
    e = elite_fall_profile(panel, adp_cut=adp_cut, fall_past=10.0)
    if not e.get("n"):
        return {"pass": False, "reason": "no elite picks in panel", **e}
    ok = bool(e["p95_slot"] <= p95_max and e["share_past_10"] <= past10_max)
    return {"pass": ok, "p95_slot": e["p95_slot"], "p95_max": float(p95_max),
            "share_past_10": e["share_past_10"], "past10_max": float(past10_max),
            "mean_slot": e["mean_slot"], "n": e["n"]}


def gate_autopilot_surplus(sim: pd.DataFrame, corpus: pd.DataFrame, *,
                           bins: Sequence[float] = POOL_RANK_BINS,
                           tol_sds: float = HARVEST_TOL_SDS, min_seats: int = 10) -> dict:
    """**Bar #3 (as rewritten 2026-07-27)**: an ADP-follower must harvest what a human one does.

    ★ **Compared at matched faithfulness, on fixed bins — never at matched quantiles.** The
    standings half of this bar was withdrawn (a seat taking the best available *should* finish well;
    "don't fight the sharp market"), leaving surplus as the defect. But surplus is only meaningful
    conditional on how far a seat strayed, and the two populations have different distributions of
    that: "the most faithful quintile" is ``pool_rank`` 1.28 in the simulated room and 4.28 in the
    corpus, so a quantile comparison reports a 2.4x gap that is entirely the mismatch. Fixed edges
    ask the answerable question and this gate asks it bin by bin.

    Bins with too few seats on either side are **skipped and reported**, not silently passed.
    """
    s = harvest_curve(sim, bins=bins).set_index("pool_rank_bin")
    c = harvest_curve(corpus, bins=bins).set_index("pool_rank_bin")
    rows, worst = [], 0.0
    for b in s.index.intersection(c.index):
        if int(s.loc[b, "n_seats"]) < min_seats or int(c.loc[b, "n_seats"]) < min_seats:
            rows.append({"bin": str(b), "skipped": "too few seats",
                         "sim_n": int(s.loc[b, "n_seats"]), "corpus_n": int(c.loc[b, "n_seats"])})
            continue
        sd = float(c.loc[b, "harvest_sd"]) or 1.0
        excess = float(s.loc[b, "harvest_picks"]) - float(c.loc[b, "harvest_picks"])
        rows.append({"bin": str(b), "sim_harvest": float(s.loc[b, "harvest_picks"]),
                     "corpus_harvest": float(c.loc[b, "harvest_picks"]), "corpus_sd": sd,
                     "excess_sds": excess / sd, "sim_n": int(s.loc[b, "n_seats"]),
                     "corpus_n": int(c.loc[b, "n_seats"])})
        # one-sided: harvesting *less* than a human is not the defect T15 is about
        worst = max(worst, excess / sd)
    scored = [r for r in rows if "excess_sds" in r]
    return {"pass": bool(scored) and worst <= tol_sds, "worst_excess_sds": worst,
            "tol_sds": float(tol_sds), "n_bins_scored": len(scored), "bins": rows}


def profile_distance(sim: pd.DataFrame, corpus: pd.DataFrame, *, max_round: int = 15,
                     min_round: int = 1) -> float:
    """Bar #1 as **one** number: mean |log(sim ÷ corpus)| of mean|drift| across rounds.

    A ratio, not a difference, because the corpus curve spans 2.9 to 27.1 picks — an absolute error
    metric would be dominated by the late rounds and would happily accept a room that is 4x too wide
    in round 1, which is the defect. Symmetric in log space, so being 2x too narrow late costs what
    being 2x too wide early costs.

    ⚠ **``min_round``/``max_round`` are not a convenience — an unweighted average over all 15
    rounds is the wrong objective and selected the wrong spec once already** (T15 step 2). The late
    rounds are structurally unreachable for a room where every seat drafts the *same* board (real
    round-15 deviation is largely board **disagreement** between managers, not choice noise), so a
    uniform average buys late width by wrecking round 1 — and duly picked an exponent that failed
    the elite-fall gate. Restrict this to the rounds the two populations are actually commensurable
    on, and report the rest as a limitation.
    """
    cmp = compare_profiles(sim, corpus, max_round=max_round).dropna(subset=["mean_ratio"])
    cmp = cmp[cmp["round"] >= int(min_round)]
    r = cmp["mean_ratio"].to_numpy(float)
    r = r[np.isfinite(r) & (r > 0)]
    return float(np.abs(np.log(r)).mean()) if len(r) else float("nan")
