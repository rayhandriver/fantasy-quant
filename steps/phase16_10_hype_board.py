"""Phase 16.10 done-bar — the curated hype board.

Three things, in order:

1. **Nominate** — rank the live board by the 16.8 ablation survivors plus 16.11 momentum
   (:func:`~fantasy_quant.adp.hype_board.nominate`). The machine picks *who* to look at.
2. **Annotate** — merge the researched claims in :data:`ANNOTATIONS` below. The human supplies
   *why*, and *how many picks*.
3. **Demonstrate** — show that a hyped player's simulated draft slot actually moves in the stated
   direction once the board is applied through the 16.9 channel.

**The board is written with ``reviewed=false``** and :func:`load_hype_board` refuses unreviewed
rows,
so nothing here can reach a real simulation until a human signs the file. That is the same review
contract as `reference/coaches.csv`, and it is structural rather than advisory.

**Regeneration is safe.** ``--write`` merges onto the existing CSV keyed by ``gsis_id``: any row a
human has edited keeps its ``pick_delta``/``note``/``source``/``confidence``/``reviewed`` verbatim,
and only genuinely new nominations are added. So re-running after the board is signed does not
silently un-sign it. ``--refresh-annotations`` opts into overwriting from :data:`ANNOTATIONS`.

Run:  uv run python steps/phase16_10_hype_board.py [--write] [--k 45]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from fantasy_quant.adp.hype_board import (
    HYPE_COLS,
    HYPE_CSV,
    apply_hype,
    load_hype_board,
    nominate,
    summarize,
)
from fantasy_quant.draft.opponent_model import ALL_FEATURES, CHOICE_TOP_K, OpponentModel

DB = Path("data/fantasy_quant.duckdb")
OUT = Path("analysis/phase16_10_hype_board.json")
COEF_JSON = Path("analysis/phase11_opponent_model.json")

# ================================================================================================
# The curated half. Researched 2026-07-26 against the live preseason coverage; every row is a
# CLAIM, not a measurement. `pick_delta` > 0 means "the room takes him this many picks EARLIER than
# the consensus board says" (the 16.7 sign convention, kept identical end to end).
#
# Rows deliberately carried at pick_delta = 0 are **documented non-claims**: the derivation
# nominated them, research found no directional narrative, and saying so is more useful to the
# reviewer than dropping them silently. They are inert by construction.
# ================================================================================================
ANNOTATIONS: dict[str, dict] = {
    # ---- risers ------------------------------------------------------------------------------
    "00-0035710": dict(  # Daniel Jones, QB IND
        pick_delta=12.0, confidence="high", source="nbcsports.com,footballguys.com",
        note="Two-year $88M deal, locked in as the starter; was QB9 in points/game before the "
             "Achilles tear and QB5 over the first 10 weeks of 2025. Priced QB25 (~144 overall) "
             "while coverage argues he should be a top-10 QB. Largest momentum riser on the live "
             "board (+5.3 picks/wk). Risk that caps it: not yet cleared, and Riley Leonard "
             "is behind him."),
    "BER218265": dict(  # Germie Bernard, WR PIT
        pick_delta=9.0, confidence="high", source="steelersdepot.com,fantasylife.com",
        note="Second-round pick who 'dominated spring workouts'; HC Mike McCarthy said he was "
             "'crushing it' playing all three receiver spots. Classic camp-buzz riser, and the "
             "Steelers WR room (Metcalf, Pittman) leaves a real snap path."),
    "00-0039344": dict(  # Jonathon Brooks, RB CAR
        pick_delta=8.0, confidence="high", source="sports.yahoo.com,fantasylife.com",
        note="Explicit 'hype train gets more steam' training-camp coverage and a 'screaming value' "
             "late-round-RB label. Two right ACL tears and a missed 2025 are exactly the profile a "
             "room talks itself into during August."),
    "BOS677861": dict(  # Denzel Boston, WR CLE
        pick_delta=8.0, confidence="high", source="fantasypros.com,rotoballer.com",
        note="Named in preseason coverage as a receiver expected to 'steam up' boards — cited as "
             "the ideal camp-highlight body type (size + hands). Live momentum agrees (+0.12 "
             "rounds/wk). This is a narrative riser, not a role-change riser."),
    "00-0040676": dict(  # Cam Ward, QB TEN
        pick_delta=8.0, confidence="high", source="si.com,fantasysixpack.net",
        note="Widely flagged as 'the popular sleeper' at QB25: 15.3 ppg over his last month as a "
             "rookie, and Tennessee spent the offseason building around him (Carnell Tate, "
             "Wan'Dale Robinson, O-line). Second-year-QB-leap is the most reliably over-drafted "
             "story in fantasy."),
    "00-0035229": dict(  # T.J. Hockenson, TE MIN
        pick_delta=5.0, confidence="med", source="cbssports.com,fantasylife.com",
        note="Priced TE23 after a 51/438/3 season, with Kyler Murray arriving — and Murray fed "
             "Trey McBride and Zach Ertz heavily in Arizona. 'Sleeper TE' pieces are already "
             "running. Counter-case: age 29 and still short of pre-ACL form."),
    "TAT143045": dict(  # Carnell Tate, WR TEN
        pick_delta=5.0, confidence="high", source="rotoballer.com,cbssports.com",
        note="WR1 of the class off the board at No. 4 overall, and described as having the "
             "clearest path to volume of the rookie trio. Rookie WRs with an alpha role are the "
             "single most reliably reached-for group (16.8 measured rookies at +0.73 rounds)."),
    "TYS405541": dict(  # Jordyn Tyson, WR NO
        pick_delta=5.0, confidence="med", source="rotoballer.com,rotostreetjournal.com",
        note="Called by several outlets the best receiver in the class on tape, first-round pick "
             "despite a serious college injury history — 'most intriguing upside relative to "
             "cost'. Upside framing is what drives a reach; the injury history is what caps it."),
    "LEM694125": dict(  # Makai Lemon, WR PHI
        pick_delta=5.0, confidence="med", source="rotoballer.com,fantasypros.com",
        note="'Most complete receiver in the class' who fell to Philadelphia at 20 — a "
             "landing-spot "
             "steal narrative, which is the specific shape of story that moves an August board. "
             "Live momentum mildly positive (+0.12 rounds/wk)."),
    "PRI206342": dict(  # Jadarian Price, RB SEA
        pick_delta=5.0, confidence="med", source="seahawks.com,cbssports.com",
        note="First-round RB (No. 32) drawing heavy Offensive Rookie of the Year betting action, "
             "with the team's own camp preview asking whether he wins the starting job outright. "
             "An unresolved starting job plus draft capital is a reach magnet."),
    "SAD482340": dict(  # Kenyon Sadiq, TE NYJ
        pick_delta=4.0, confidence="med", source="newyorkjets.com,thejetpress.com",
        note="First-round TE (No. 16) with the highest ceiling in the Jets' rookie class. "
             "Genuinely two-sided: hernia surgery cost him OTAs and minicamp, and the room already "
             "holds Mason Taylor and Jeremy Ruckert. Hyped, but the delta is small for "
             "that reason."),
    "00-0039384": dict(  # Tyrone Tracy Jr., RB NYG
        pick_delta=4.0, confidence="med", source="cbssports.com,fantasypros.com",
        note="Averaged 13.6 ppg once he took the job in 2025 and is the direct handcuff to a "
             "Skattebo backfield with injury questions. Rising on the live series (+0.18 "
             "rounds/wk). Contingent value that a room prices earlier than a projection does."),
    "00-0036550": dict(  # Rashod Bateman, WR BAL
        pick_delta=3.0, confidence="low", source="baltimoreravens.com,cbssports.com",
        note="'Practically free' sleeper pieces are running on the strength of his 9-TD 2024, and "
             "a new Baltimore OC (Declan Doyle) is a reset. But 2025 was a genuine disaster and he "
             "missed OTAs, so the buzz is thin — low confidence, small delta."),
    "LOV121782": dict(  # Jeremiyah Love, RB ARI
        pick_delta=3.0, confidence="med", source="fantasylife.com,si.com",
        note="First rookie off the board, hyped as a top-15 RB. Already priced up (FFC 22.6, "
             "Underdog 24.7) so most of the hype is IN the number — hence a small delta despite "
             "loud coverage. Bear case is live: bottom-6 offense and a crowded backfield."),
    "00-0039139": dict(  # Jahmyr Gibbs, RB DET
        pick_delta=1.0, confidence="med", source="rotowire.com,fantasylife.com",
        note="The 1.01. Consensus was Bijan through May; Gibbs 'inched ahead in June' as the "
             "higher-ceiling play at the same price. A one-pick claim is all the room has to give "
             "at ADP 1.8 — carried mostly because the derivation flagged this pair on ADP "
             "disagreement alone, which is a real cross-check on the nomination."),
    # ---- fallers -----------------------------------------------------------------------------
    "00-0039165": dict(  # Zach Charbonnet, RB SEA
        pick_delta=-10.0, confidence="high", source="cbssports.com,fantasypros.com",
        note="Placed on the PUP list to open 2026 — a minimum four missed games, returning "
             "mid-season at best. This is the clearest faller on the board and the live series "
             "already agrees (−0.08 rounds/wk). Not narrative: a roster fact."),
    "00-0040583": dict(  # Woody Marks, RB HOU
        pick_delta=-5.0, confidence="high", source="fantasylife.com,espn.com",
        note="Houston signed David Montgomery to be the bell cow, pushing Marks back into the "
             "third-down pass-catching role he was drafted for. His high ADP disagreement is the "
             "market still repricing that signing."),
    "00-0036261": dict(  # Brandon Aiyuk, WR SF
        pick_delta=-4.0, confidence="low", source="thefalcoholic.com",
        note="Roster status genuinely unresolved in coverage, and he carries no row on our own "
             "2026 value board — the projection sources do not know what to do with him either. "
             "Fading a player nobody can price is the honest direction, but confidence is low."),
    "00-0037263": dict(  # Tyler Allgeier, RB ARI
        pick_delta=-3.0, confidence="low", source="draftsharks.com,cbssports.com",
        note="⚠ SIGNALS CONFLICT, deliberately left visible. Signed to start in Arizona, then the "
             "Cardinals took Jeremiyah Love at No. 3 — coverage now says timeshare at best, behind "
             "Conner and Benson too. But he is a live momentum RISER (+0.20 rounds/wk), i.e. the "
             "drafting public is moving the other way from the analysis. Small delta in the "
             "direction of the reporting; a reviewer who trusts the market should zero it."),
    "00-0038542": dict(  # Bijan Robinson, RB ATL
        pick_delta=-1.0, confidence="med", source="rotowire.com,fftoday.com",
        note="The other side of the 1.01. Held the consensus top spot through May and has since "
             "ceded it to Gibbs. Pairs with the Gibbs row; both are one-pick claims."),
    # ---- documented non-claims (inert, kept for the reviewer) ---------------------------------
    "00-0037746": dict(  # Brian Robinson Jr., RB ATL
        pick_delta=0.0, confidence="high", source="fantasypros.com,establishtherun.com",
        note="NO CLAIM. Carries the highest ADP disagreement on the entire board (sd 32.7, +5.3 SD "
             "for his depth) — but research says that is *contingency*, not hype: he is the pure "
             "handcuff to a Bijan Robinson who has never missed a game. Some drafters take a "
             "handcuff two rounds early, most never take one, and that bimodality is what a large "
             "standard deviation looks like. A good example of the nomination working and the "
             "narrative reading not supporting a directional claim."),
    "00-0039150": dict(  # Bryce Young, QB CAR
        pick_delta=0.0, confidence="high", source="cbssports.com,fantasylife.com",
        note="NO CLAIM. Second-highest ADP disagreement, but the coverage is uniformly cautious — "
             "'make-or-break', not recommended in 1QB leagues, worst-in-class efficiency "
             "over three "
             "seasons. The spread is a market that cannot agree whether he is startable at all, "
             "which is disagreement without direction."),
    "00-0038977": dict(  # Tank Dell, WR HOU
        pick_delta=0.0, confidence="low", source="",
        note="NO CLAIM. Nominated on ADP disagreement, but the 2026 preseason coverage found for "
             "him was thin and mostly stale. Recorded so the reviewer can see the derivation "
             "surfaced him and the research came back empty."),
    "00-0034837": dict(  # Calvin Ridley, WR TEN
        pick_delta=0.0, confidence="low", source="",
        note="NO CLAIM. Live momentum riser (+0.16 rounds/wk) with no supporting 2026 narrative "
             "found; note that Tennessee drafted Carnell Tate at No. 4, which is target "
             "competition rather than hype. Left inert pending a human read."),
}


def _model() -> OpponentModel:
    coef = json.loads(COEF_JSON.read_text())["coefficients"]
    return OpponentModel(feature_cols=list(ALL_FEATURES),
                         beta=np.array([coef[c] for c in ALL_FEATURES]))


def _build_rows(nom: pd.DataFrame, season: int) -> pd.DataFrame:
    """Derived nominations + curated annotations, in the frozen :data:`HYPE_COLS` order."""
    rows = []
    for r in nom.itertuples():
        ann = ANNOTATIONS.get(r.gsis_id)
        if ann is None:
            continue                      # nominated but not researched -> not a claim, not a row
        rows.append({
            "season": season, "gsis_id": r.gsis_id, "player": r.player,
            "position": r.position, "team": r.team, "adp": round(float(r.adp), 1),
            "pick_delta": float(ann["pick_delta"]),
            "note": ann["note"], "source": ann.get("source", ""),
            "evidence": "derived+web", "confidence": ann.get("confidence", "low"),
            "reviewed": False,
        })
    return pd.DataFrame(rows, columns=HYPE_COLS)


#: Columns a human owns. On regeneration these are carried forward from the existing file rather
#: than reset from ANNOTATIONS, so a reviewed board survives a re-run.
_HUMAN_COLS = ("pick_delta", "note", "source", "confidence", "reviewed")


def _merge_forward(new: pd.DataFrame, path: Path, refresh: bool) -> tuple[pd.DataFrame, dict]:
    if refresh or not path.exists():
        return new, {"kept_existing": 0, "added": int(len(new))}
    old = load_hype_board(path, require_reviewed=False)
    if old.empty:
        return new, {"kept_existing": 0, "added": int(len(new))}
    old_by = {str(g): r for g, r in zip(old["gsis_id"].astype(str),
                                        old.to_dict("records"), strict=False)}
    kept = 0
    out = new.copy()
    for i, g in enumerate(out["gsis_id"].astype(str)):
        prev = old_by.get(g)
        if prev is None:
            continue
        kept += 1
        for c in _HUMAN_COLS:
            out.iat[i, out.columns.get_loc(c)] = prev[c]
    # rows a human added by hand that the derivation no longer nominates are preserved too
    extra = old[~old["gsis_id"].astype(str).isin(set(out["gsis_id"].astype(str)))]
    if not extra.empty:
        out = pd.concat([out, extra[HYPE_COLS]], ignore_index=True)
    return out, {"kept_existing": kept, "added": int(len(out)) - kept,
                 "preserved_hand_added": int(len(extra))}


_HEADER = """\
# Phase 16.10 — curated hype board. ROWS ARE DERIVED (adp/hype_board.py::nominate);
# pick_delta / note / source / confidence / reviewed are CURATED and are yours to edit.
# pick_delta > 0 = the room drafts him EARLIER than the consensus board says, in picks.
# CURATED, NOT BACKTESTED: 16.8 found no per-player drift signal and 16.9 found the narrative
# shock unidentified, so nothing in Phase 16 validates these numbers. The board is opt-in and
# default OFF everywhere; set reviewed=true only for rows you personally stand behind.
# Regenerate with: uv run python steps/phase16_10_hype_board.py --write   (your edits survive)
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--k", type=int, default=45)
    ap.add_argument("--write", action="store_true", help="write reference/hype_board.csv")
    ap.add_argument("--refresh-annotations", action="store_true",
                    help="overwrite curated columns from ANNOTATIONS (discards human edits)")
    args = ap.parse_args()

    con = duckdb.connect(str(DB), read_only=True)
    out: dict = {"season": args.season}

    # ---- 1. nominate --------------------------------------------------------------------------
    print(f"nominating {args.season} hype candidates ...", flush=True)
    nom = nominate(con, args.season, k=args.k)
    out["nomination"] = nom.to_dict("records")
    print(f"  {len(nom)} nominated; {len(ANNOTATIONS)} researched")
    print(nom.head(15)[["player", "position", "adp", "score", "momentum", "rookie",
                        "adp_stdev_z", "vbd_gap_z"]].to_string(index=False))

    # ---- 2. annotate + write ------------------------------------------------------------------
    rows = _build_rows(nom, args.season)
    missing = sorted(set(ANNOTATIONS) - set(nom["gsis_id"]))
    if missing:
        # an annotation whose player is no longer nominated is a real signal: the board moved.
        print(f"\n  ⚠ {len(missing)} annotated players are no longer in the top "
              f"{args.k}: {missing}")
    out["n_rows"] = int(len(rows))
    out["annotated_not_nominated"] = missing

    if args.write:
        merged, mstats = _merge_forward(rows, HYPE_CSV, args.refresh_annotations)
        HYPE_CSV.parent.mkdir(parents=True, exist_ok=True)
        HYPE_CSV.write_text(_HEADER + merged.to_csv(index=False))
        out["merge"] = mstats
        print(f"\nwrote {HYPE_CSV} ({len(merged)} rows) {mstats}")

    board = load_hype_board(HYPE_CSV, args.season, require_reviewed=False)
    out["summary"] = summarize(board)
    print(f"\nboard: {out['summary']}")

    # ---- 3. demonstrate: does a hyped player actually move? -----------------------------------
    # Applied through the 16.9 channel with the review gate BYPASSED, because the point of the
    # done-bar is to prove the mechanism works before a human signs anything. Every production
    # path keeps require_reviewed=True.
    print("\ndemonstrating the apply path (review gate bypassed for the mechanism check) ...",
          flush=True)
    model = _model()
    beta_adp_s = float(model.beta[list(model.feature_cols).index("adp_s")])
    demo = _demonstrate(con, args.season, board, model, beta_adp_s)
    out["demonstration"] = demo

    claims = board[board["pick_delta"] != 0]
    # How much of the board the machine actually nominated, versus rows that exist only because a
    # human went looking. Reported rather than asserted: the residue is the point of the split —
    # a roster transaction like Zach Charbonnet's PUP designation is not in any table we ingest, so
    # no derivation can surface it, and that is exactly where the human budget should go.
    derived = board["gsis_id"].isin(set(nom["gsis_id"]))
    out["provenance"] = {
        "n_rows": int(len(board)),
        "n_nominated_by_derivation": int(derived.sum()),
        "derived_fraction": float(derived.mean()) if len(board) else 0.0,
        "research_only": board.loc[~derived, "player"].tolist(),
    }
    print(f"\nprovenance: {int(derived.sum())}/{len(board)} board rows were machine-nominated; "
          f"research-only: {out['provenance']['research_only']}")

    gates = {
        "board_loads": bool(len(board) > 0),
        "unreviewed_refused": len(load_hype_board(HYPE_CSV, args.season)) == 0,
        "majority_machine_nominated": bool(out["provenance"]["derived_fraction"] >= 0.5),
        "has_directional_claims": bool(len(claims) >= 10),
        "moves_in_expected_direction": demo.get("sign_agreement", 0.0) >= 0.75,
    }
    out["gates"] = gates
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nwrote {OUT}")
    for k, v in gates.items():
        print(f"  {k:>30}: {'PASS' if v else 'FAIL'}")
    print("\n  ⚠ CURATED, NOT BACKTESTED — opt-in and default OFF; the board is written "
          "reviewed=false and the apply path refuses unreviewed rows.")


def _demonstrate(con, season: int, board: pd.DataFrame, model, beta_adp_s: float,
                 n_drafts: int = 30, teams: int = 10, rounds: int = 18) -> dict:
    """Draft the same board many times with and without the hype offsets, and compare each hyped
    player's mean draft slot. The question is only whether the channel moves players the way the
    curated rows say — not whether the rows are right, which nothing here can establish.

    **Undrafted players are censored, not dropped**, and that detail is the whole measurement. The
    first version of this check averaged the slots a player *was* taken at, and reported that
    hyping Cam Ward (ADP 167.7, in a 150-pick draft) pushed him **later**. It did not: it made him
    get drafted at all, in rooms where he had previously gone untaken, and every one of those new
    appearances lands near the final pick and drags a conditional mean backwards. Scoring undrafted
    as ``n_picks + 1`` gives every draft a value for every player, so both arms are averaged over
    the same denominator. ``draft_rate`` is reported alongside because for a deep player the hype
    channel legitimately expresses as *more often drafted* rather than *drafted earlier*.

    **18 rounds, not the league-standard 15, and that is a finding rather than a convenience.** At
    150 picks against a 201-deep board, a claim on a player at board rank 171 is not merely hard to
    measure, it is structurally untestable: he is outside the drafted range in most rooms. Measured
    directly, Daniel Jones (+12 picks, rank 171) produced a **bit-identical** 30-draft result at 15
    rounds and only moved once the offset was raised roughly fivefold. So the demonstration runs
    deep enough to contain every claim, and the honest caveat travels with it — *at a standard
    15-round draft several of these curated rows cannot express at all.*
    """
    from fantasy_quant.adp import boards
    from fantasy_quant.draft.personalities import make_opponent_pick_fn
    from fantasy_quant.draft.simulator import _prepare_board, simulate_draft

    bd, _src = boards.resolve_board(con, season, "ppr", teams, allow_ecr=False)
    if bd.empty:
        return {"error": "no board"}
    bd = bd.rename(columns={"name": "player_name"}).copy()
    bd["adp"] = pd.to_numeric(bd["adp"], errors="coerce")
    bd = bd.dropna(subset=["adp"])
    prepped = _prepare_board(bd)
    hype_u = apply_hype(prepped, board, beta_adp_s=beta_adp_s, key="player_key")

    n_picks = teams * rounds
    censored = float(n_picks + 1)
    keys = list(board["gsis_id"].astype(str))

    def run(offsets) -> tuple[pd.Series, pd.Series]:
        rng = np.random.default_rng(11)
        slots = {k: [] for k in keys}
        for _ in range(n_drafts):
            fn = make_opponent_pick_fn(model, top_k=CHOICE_TOP_K, hype=offsets)
            st = simulate_draft(bd, n_teams=teams, rounds=rounds,
                                seed=int(rng.integers(1 << 30)), opponent_pick_fn=fn,
                                your_pick_fn=lambda s, _f=fn: int(_f(s, s.your_team)))
            log = pd.DataFrame(st.log)
            taken = dict(zip(log["player_key"].astype(str), log["overall_pick"], strict=False))
            for k in keys:
                slots[k].append(float(taken.get(k, censored)))
        arr = {k: np.array(v) for k, v in slots.items()}
        mean_slot = pd.Series({k: v.mean() for k, v in arr.items()})
        rate = pd.Series({k: float((v < censored).mean()) for k, v in arr.items()})
        return mean_slot, rate

    base, base_rate = run(None)
    claims = board[board["pick_delta"] != 0]

    # --- the gate runs LEAVE-ONE-IN, and the reason is a property of drafts, not of this code ----
    # A draft has a fixed number of picks, so hype is zero-sum: applying all 20 claims at once
    # makes the hyped players compete with *each other*, and the small claims lose to the large
    # ones. The joint run duly showed Kenyon Sadiq (+4) getting drafted *less* often while Daniel
    # Jones (+12) and Denzel Boston (+8) rose. That crowding-out is correct behaviour and is worth
    # recording for 16.12, but it is not what "does a hype row move this player" is asking, so the
    # per-player check applies one row at a time against the shared baseline.
    rows = []
    for r in claims.itertuples():
        g = str(r.gsis_id)
        if g not in base.index:
            continue
        solo = np.zeros(len(prepped))
        solo[prepped["player_key"].astype(str).to_numpy() == g] = \
            hype_u[prepped["player_key"].astype(str).to_numpy() == g]
        one, one_rate = run(solo)
        # positive shift = drafted earlier (or at all) under hype — the pick_delta sign convention
        rows.append({"player": r.player, "pick_delta": float(r.pick_delta),
                     "slot_base": float(base[g]), "slot_hyped": float(one[g]),
                     "shift": float(base[g] - one[g]),
                     "rate_base": float(base_rate[g]), "rate_hyped": float(one_rate[g])})
    if not rows:
        return {"n_compared": 0}
    d = pd.DataFrame(rows)
    # A one-pick claim at ADP 1.8 is below the simulator's resolution, so sign agreement is scored
    # on the claims large enough to be resolvable and the sub-threshold rows are reported, not
    # quietly counted as failures.
    # a deep player's hype expresses as "drafted at all" before it expresses as "drafted earlier",
    # so the move is scored on the censored slot OR the draft rate, whichever the player has room
    # to show. Both carry the same sign convention.
    d["move"] = np.where(d["shift"].abs() > 1e-9, d["shift"],
                         d["rate_hyped"] - d["rate_base"])
    # A claim is scored only where the simulator can resolve it: a 1-pick claim at ADP 1.8 is below
    # the resolution of any draft, and a row that produced literally no movement is reported as
    # unresolved rather than silently counted as a failure.
    resolvable = d[(d["pick_delta"].abs() >= 3) & (d["move"].abs() > 1e-9)]
    agree = float((np.sign(resolvable["move"]) == np.sign(resolvable["pick_delta"])).mean()) \
        if len(resolvable) else float("nan")
    # ★ the number to carry forward: how many picks of REALIZED movement one stated pick buys.
    # It is well under 1.0, because ADP is only one term in the fitted utility and the top-k filter
    # blunts the rest — so a curated row is a nudge, not a repricing.
    pos = d[d["pick_delta"] > 0]
    elasticity = float(pos["shift"].sum() / pos["pick_delta"].sum()) if len(pos) else float("nan")
    print(d.to_string(index=False))
    return {"n_compared": int(len(d)), "n_resolvable": int(len(resolvable)),
            "n_unresolved": int(len(d) - len(resolvable)),
            "sign_agreement": agree,
            "elasticity_picks_per_claimed_pick": elasticity,
            "mean_abs_shift": float(d["shift"].abs().mean()),
            "corr_delta_shift": float(d["pick_delta"].corr(d["shift"])),
            "corr_delta_rate_shift": float(
                d["pick_delta"].corr(d["rate_hyped"] - d["rate_base"])),
            "rounds": rounds, "n_drafts": n_drafts,
            "censored_at": censored, "rows": d.to_dict("records")}


if __name__ == "__main__":
    main()
