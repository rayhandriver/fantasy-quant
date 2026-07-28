"""T15 step 0 — the mock-draft A/B harness and the frozen "before" picture.

    uv run python steps/t15_0_baseline.py                 # season-matched bar + 2026 readout
    uv run python steps/t15_0_baseline.py --seeds 200     # more drafts (a draft costs ~0.55 s)
    uv run python steps/t15_0_baseline.py --seasons 2026  # readout only, skips the matched bar

Done when: the simulated room's reach profile and the realized human corpus's are measured **by the
same code on the same boards**, over enough seeded drafts to be a baseline rather than an anecdote,
and the result is written to ``analysis/t15_baseline.json`` so the post-fix comparison cannot drift.

★ **This step changes no model.** It exists because the T15 defect was found by a human drafting
*one* mock, and step 1 must not be evaluated against one draft. Everything here runs the shipped
11.1 β and 11.3 personalities unmodified; what is new is that it runs them 50+ times per season and
measures the output in the corpus's own frame (:func:`fantasy_quant.draft.mock.sim_drift_panel`).

**The comparison is season-matched.** The sim drafts the board
:func:`~fantasy_quant.adp.boards.resolve_board` gives the corpus panel for that same season, so a
difference in the reach curve cannot be an artifact of board vintage. 2026 is reported alongside as
the readout for the live board the user actually drafts against — its hype/fandom channel has no
pre-2026 analog, which is stated rather than silently pooled.

**Boards are FFC-only for the pre-registered numbers.** 2025 is ECR-boarded (FFC published nothing)
and ``adp/boards.py`` is explicit that the two are never pooled into a headline. The prior T15 table
did pool them (1,420 drafts); this step reports the FFC-only figure (1,144 drafts) as the bar and
the pooled figure alongside so the two reconcile.

Four things are measured, in the order they were understood:

1. **The reach profile by round** (bar #1) — mean and p90 |drift| in 10-team ADP picks. The corpus
   curve grows monotonically; the simulated one is flat. :func:`~.mock.profile_trend` reduces that
   to one number a fix has to move.
2. **The elite fall profile** (bar #2) — where consensus top-12 players actually land.
3. **Harvest vs faithfulness** (bar #3) — what a seat takes home given how far it strayed from the
   board, binned on **fixed** ``pool_rank`` edges so both populations are read off the same row.
4. **The faithfulness distribution itself** — added after (3) showed the quantile form of bar #3
   was comparing a robot to a person. See the finding below.

★ **The finding this step produced, which reframes the fix.** At *matched* faithfulness the
simulated harvest is roughly right — a genuinely chalk human seat (``pool_rank`` 1–2, n=19) harvests
**+17.6** picks against the simulated ``autopilot``'s **+20.7**, well inside the corpus spread
(sd 17.0). What is wrong is **who is in the room**: real managers are a continuum with median
``pool_rank`` ~7.6 and **54 %** of seats in the 2–8 band, while the simulated room is **bimodal** —
``autopilot`` at 1.16 and every other personality past 7, with essentially nobody in between. The
room has no moderate drafters. So the target for step 1 is not only "make reaches smaller early",
it is "make the *distribution* of deviation look like a human population" — which is exactly what a
depth-varying ``adp_s`` would do and a uniform shrink would not.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import pandas as pd

from fantasy_quant.adp import boards
from fantasy_quant.adp.drift_panel import build_drift_panel, summarize
from fantasy_quant.draft import mock

DB = Path("data/fantasy_quant.duckdb")
OUT = Path("analysis/t15_baseline.json")
CACHE = Path("analysis/cache")

#: Seasons with both a realized human corpus and an FFC board — the like-for-like bar.
MATCHED_SEASONS: tuple[int, ...] = (2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024)

#: The live board, reported separately: it is what the user drafts against, and it is the only
#: season with a 16.5 situation board / 16.10 hype channel, so it is never pooled with the bar.
READOUT_SEASON: int = 2026


def _records(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> JSON-safe records (Interval bin labels become strings)."""
    out = df.copy()
    for c in out.columns:
        if not pd.api.types.is_numeric_dtype(out[c]):
            out[c] = out[c].astype(str)
    return json.loads(out.to_json(orient="records"))


def _measure(panel: pd.DataFrame, label: str) -> dict:
    """Every bar, computed on one panel — identical call for sim and corpus."""
    prof = mock.reach_profile(panel)
    return {
        "label": label,
        "n_picks": int(len(panel)),
        "n_drafts": int(panel["draft_id"].nunique()) if not panel.empty else 0,
        "reach_profile": _records(prof),
        "profile_trend": mock.profile_trend(prof),
        "elite_fall": mock.elite_fall_profile(panel),
        "harvest_curve": _records(mock.harvest_curve(panel)),
        "faithfulness_profile": _records(mock.faithfulness_profile(panel)),
        "faithfulness": mock.faithfulness_summary(panel),
        "faithful_harvest_quantile": mock.faithful_harvest(panel),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", type=int, default=100,
                    help="seeded drafts per season (T15 asks for >=50; a draft costs ~0.55 s)")
    ap.add_argument("--seasons", default="matched",
                    help="'matched', 'all', or a comma list of seasons")
    ap.add_argument("--teams", type=int, default=10)
    ap.add_argument("--rounds", type=int, default=15)
    ap.add_argument("--room", default=None, help="comma list overriding DEFAULT_FULL_ROOM")
    ap.add_argument("--room-seed", type=int, default=11,
                    help="shuffles personalities across draft slots so seat != personality")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    if args.seasons == "matched":
        seasons = list(MATCHED_SEASONS)
    elif args.seasons == "all":
        seasons = [*MATCHED_SEASONS, READOUT_SEASON]
    else:
        seasons = [int(s) for s in args.seasons.split(",")]

    con = duckdb.connect(str(DB), read_only=True)
    model = mock.load_opponent_model()
    mix = tuple(x.strip() for x in args.room.split(",")) if args.room else None
    room = mock.full_room(mix, n_teams=args.teams, seed=args.room_seed)
    print(f"room ({args.teams} seats): {[p.name for p in room]}")

    # ---- the realized human corpus, measured by the same functions ------------------------------
    corpus = build_drift_panel(con)
    ffc = corpus[corpus["board_source"] == boards.FFC]
    print(f"corpus: {len(corpus)} picks / {corpus['draft_id'].nunique()} drafts "
          f"({len(ffc)} / {ffc['draft_id'].nunique()} on FFC boards)")

    # ---- the simulated room, one batch per season -----------------------------------------------
    sim_frames, board_meta = [], {}
    for season in seasons:
        board, src = mock.room_board(con, season, teams=args.teams, cache_dir=CACHE)
        if board.empty:
            print(f"  {season}: no FFC board — skipped")
            continue
        panel = mock.batch_drift_panel(
            board, room, model, season=season, seeds=range(args.seeds),
            n_teams=args.teams, rounds=args.rounds, board_source=src)
        board_meta[season] = {"board_rows": int(len(board)), "source": src,
                              "sim_drafts": int(args.seeds)}
        sim_frames.append(panel)
        print(f"  {season}: board {len(board):>4} rows ({src}) -> "
              f"{args.seeds} drafts, {len(panel)} boarded picks")
    if not sim_frames:
        raise SystemExit("no season produced a board — nothing to baseline")
    sim = pd.concat(sim_frames, ignore_index=True)

    matched = [s for s in seasons if s in MATCHED_SEASONS]
    sim_matched = sim[sim["season"].isin(matched)]
    corpus_matched = ffc[ffc["season"].isin(matched)]

    result = {
        "generated": pd.Timestamp.utcnow().isoformat(),
        "config": {"seeds": args.seeds, "teams": args.teams, "rounds": args.rounds,
                   "room": [p.name for p in room], "room_seed": args.room_seed,
                   "seasons": seasons, "matched_seasons": matched},
        "boards": board_meta,
        "corpus_all_sources": summarize(corpus),
        "corpus": _measure(corpus_matched, "corpus (FFC, season-matched)"),
        "sim": _measure(sim_matched, "sim (season-matched)"),
        "personalities": _records(mock.personality_table(sim_matched)),
    }
    if not sim_matched.empty and not corpus_matched.empty:
        result["bar1_profile"] = _records(mock.compare_profiles(sim_matched, corpus_matched))

    # the live board, kept out of the bar on purpose (no pre-2026 hype/situation analog)
    readout = sim[sim["season"] == READOUT_SEASON]
    if not readout.empty:
        result["readout_2026"] = _measure(readout, f"sim ({READOUT_SEASON} live board)")
        result["readout_2026"]["personalities"] = _records(mock.personality_table(readout))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2))

    # ---- report ---------------------------------------------------------------------------------
    print(f"\n=== BAR 1 — reach profile, 10-team ADP picks ({len(matched)} matched seasons) ===")
    if "bar1_profile" in result:
        print(pd.DataFrame(result["bar1_profile"]).round(2).to_string(index=False))
    ct, stz = result["corpus"]["profile_trend"], result["sim"]["profile_trend"]
    print(f"\n  shape (Spearman round vs mean|drift|):  corpus {ct:+.3f}   sim {stz:+.3f}"
          "   <- the corpus curve rises; a flat sim is the defect")

    print("\n=== BAR 2 — where consensus top-12 players land (10-team picks) ===")
    for k in ("corpus", "sim"):
        e = result[k]["elite_fall"]
        print(f"  {result[k]['label']:<32} mean {e['mean_slot']:>5.1f}  p95 {e['p95_slot']:>5.1f}  "
              f"past pick 10 {e['share_past_10']:>6.1%}  (n={e['n']})")

    print("\n=== BAR 3 — harvest vs faithfulness, at matched pool_rank ===")
    for k in ("corpus", "sim"):
        print(f"  -- {result[k]['label']}")
        print(pd.DataFrame(result[k]["harvest_curve"]).round(2).to_string(index=False))

    print("\n=== THE ROOM'S POPULATION — how far seats stray from the board ===")
    for k in ("corpus", "sim"):
        f = result[k]["faithfulness"]
        print(f"  {result[k]['label']:<32} median pool_rank {f['median_pool_rank']:>5.2f}  "
              f"moderate(2-8) {f['moderate_share']:>6.1%}  chalk(<2) {f['chalk_share']:>6.1%}")
    print("  ^ the simulated room is bimodal — robots or extremists, no moderate drafters.")

    print("\n=== PER-PERSONALITY (sim) ===")
    print(pd.DataFrame(result["personalities"]).round(2).to_string(index=False))
    print(f"\nwrote {args.out}")
    con.close()


if __name__ == "__main__":
    main()
