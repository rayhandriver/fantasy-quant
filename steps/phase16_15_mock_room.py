"""Phase 16.15 — the mock room: seat composition, hype coupling, and the app selector contract.

    uv run python steps/phase16_15_mock_room.py

Done when: a mock draft runs against a **named, realistic, user-tunable** room of personalities;
the shared 16.9 narrative shock is expressed through the seats that would actually chase it; and
the Phase-14 selector has a contract to call. Everything here is read-only with respect to the
frozen value / distribution / optimizer / cost-report stack — the room only decides who picks.

Three things are checked, in the order they can go wrong:

1. **Mechanics** — the room drafts a legal board, every seat is the personality it was assigned,
   and ``autopilot`` seats still reproduce ADP order exactly.
2. **The calibration is preserved** — per-seat ``hype_gain`` is normalized to room-mean 1, so
   composition redistributes the 16.9 shock without rescaling it. A room whose mean gain drifts
   from 1 has silently moved a parameter 16.9 fitted against the realized depth profile.
3. **The shock rides the right seats** — with a shared hype draw in play, a seat's share of the
   hyped players rises **monotonically in its own gain**. This is the substep's actual claim, and it
   is an A/B against the same room with the hype channel off, not a comparison to a different room.

★ Check 3 is stated as a **rank correlation across all nine seats**, not as a
chasers-minus-autopickers gap. The gap version passes on a room where the story routes to the
*wrong* seats, because the autopickers' share of hyped players **falls** when the channel opens
(they get sniped by whoever is chasing) — so the gap widens whether or not the intended seats are
the ones chasing. A bar that only looks at the two ends of the room cannot see the middle of the
room going backwards.

★ **And the honest headline: at the shipped shock size this is a NULL — Phase 16's fifth.** The
16.9 draw is ~1.5 ADP picks; against a softmax over 40 candidates that moves a seat's hyped-player
share by ≤0.04, with a rank correlation to seat gain of +0.07, i.e. nothing. Amplify the same
shock x10 and the correlation is +0.91. So the coupling is **built correctly and waiting on a
signal worth routing** — 16.9 already reported its own magnitude as unidentified, and 16.15
faithfully routing a null cannot manufacture an effect. The mechanism is what is gated (at
:data:`AMP_GATE`); the shipped-size result is reported, not gated. Same shape as 16.16: the
detector works, reacting to it does not.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy import stats

from fantasy_quant.adp.narrative import NarrativeShock, shock_features
from fantasy_quant.data.sources.adp import adp_asof
from fantasy_quant.draft.enrichment import enrich_board
from fantasy_quant.draft.opponent_model import _ADP_SCALE, ALL_FEATURES, OpponentModel
from fantasy_quant.draft.personalities import (
    DEFAULT_ROOM,
    make_room,
    make_room_pick_fn,
    normalized_hype_gains,
    personalities,
)
from fantasy_quant.draft.simulator import board_player_key, simulate_draft

DB = Path("data/fantasy_quant.duckdb")
COEF_JSON = Path("analysis/phase11_opponent_model.json")
OUT = Path("analysis/phase16_15_mock_room.json")

#: Amplification at which the routing mechanism is gated. The shipped 16.9 shock is ~1.5 ADP picks,
#: which is below the resolution of a softmax over 40 candidates — measured, the per-seat effect at
#: that size is ≤0.04 and its rank correlation with seat gain is noise (+0.07). Sweeping the size
#: (x1 → x40) the correlation climbs +0.07 · +0.53 · +0.84 · +0.91 · +0.95 and then flattens, so
#: x10 (≈15 picks) is the smallest amplification that resolves the mechanism cleanly. Gating here
#: is the same move as Phase 9.5's `winprob_sims≥200`: prove the machinery on a signal big enough
#: to see, and report separately that the shipped signal is not that big.
AMP_GATE: float = 10.0

#: The eligible-redraft manager corpus the hand-set mix is sanity-checked against: complete
#: snake/linear human drafts at ordinary league sizes. Position share is computed from picks alone —
#: no ADP reference — which is why it is usable where the stored per-manager ``avg_reach`` is not
#: (that rests on a pooled ADP board and reports a +91.9-*pick* mean QB reach, a board mismatch
#: rather than a behaviour; see docs/TECH-DEBT.md T18).
CORPUS_SQL = """
WITH elig AS (
    SELECT d.draft_id, d.teams FROM sleeper_drafts d
    WHERE d.status = 'complete' AND d.draft_type IN ('snake', 'linear')
      AND d.is_human AND d.teams BETWEEN 8 AND 14 AND d.rounds BETWEEN 12 AND 20),
p AS (
    SELECT p.picked_by AS mgr, p.position FROM sleeper_draft_picks p JOIN elig e USING (draft_id)
    WHERE p.picked_by IS NOT NULL)
SELECT mgr, count(*) AS n,
       sum(CASE WHEN position = 'QB' THEN 1 ELSE 0 END) * 1.0 / count(*) AS qb,
       sum(CASE WHEN position = 'RB' THEN 1 ELSE 0 END) * 1.0 / count(*) AS rb,
       sum(CASE WHEN position = 'TE' THEN 1 ELSE 0 END) * 1.0 / count(*) AS te
FROM p GROUP BY mgr HAVING count(*) >= 30
"""


def _model() -> OpponentModel:
    coef = json.loads(COEF_JSON.read_text())["coefficients"]
    return OpponentModel(feature_cols=list(ALL_FEATURES),
                         beta=np.array([coef[c] for c in ALL_FEATURES]))


def _hype_vector(board: pd.DataFrame, n_teams: int, seed: int) -> np.ndarray:
    """One shared 16.9 narrative draw for a draft, on the prepared board's row order."""
    feats = shock_features(board.rename(columns={"position": "pos"}), board_teams=n_teams)
    return NarrativeShock().draw(feats, np.random.default_rng(seed))


def _loud_share(board, room, model, *, n_teams, rounds, n_drafts, amp: float | None,
                n_loud: int = 25):
    """Per-seat share of picks that were **this draft's hyped players**.

    The shock is a zero-mean utility offset, so a *positive* draw is the one that pulls a player
    early — "the room is talking about him this August". For each draft the top ``n_loud`` positive
    draws are the story, and each seat's loud share is the fraction of its picks that came from it.

    ``amp`` scales the calibrated 16.9 draw: ``1.0`` is the shipped size, ``None`` closes the
    channel entirely. The control must still label the **same** players loud — with no channel,
    every seat's loud share should be whatever the board hands it, regardless of its ``hype_gain``.
    (Passing a zero *vector* instead of ``None`` is not a control: ``argsort`` on zeros labels the
    top ``n_loud`` rows by board order, i.e. by ADP, which the autopick seats take by construction.
    That mistake reads as a large fake effect on exactly the seats it should say nothing about.)
    """
    keys = board_player_key(board).astype(str)
    hit = np.zeros(len(room))
    tot = np.zeros(len(room))
    for s in range(n_drafts):
        shock = _hype_vector(board, n_teams, seed=1000 + s)
        loud = set(keys.iloc[np.argsort(-shock)[:n_loud]])
        st = simulate_draft(board, n_teams=n_teams, rounds=rounds, seed=s,
                            opponent_pick_fn=make_room_pick_fn(
                                model, room, hype=None if amp is None else float(amp) * shock))
        log = st.pick_log().query("not is_you")
        seats = np.where(log["team"].to_numpy() > st.your_team,
                         log["team"].to_numpy() - 1, log["team"].to_numpy())
        is_loud = log["player_key"].astype(str).isin(loud).to_numpy()
        for seat, ld in zip(seats, is_loud, strict=True):
            tot[seat] += 1
            hit[seat] += float(ld)
    return hit / np.maximum(tot, 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--teams", type=int, default=10)
    ap.add_argument("--rounds", type=int, default=15)
    ap.add_argument("--n-drafts", type=int, default=24)
    args = ap.parse_args()

    con = duckdb.connect(str(DB), read_only=True)
    model = _model()

    print(f"=== 16.15 — the mock room ({args.teams}-team, {args.rounds} rounds) ===")
    room = make_room(n_opponents=args.teams - 1)
    gains = normalized_hype_gains(room)
    print(f"  default room ({len(room)} seats): {', '.join(p.name for p in room)}")
    print("\n  seat            raw gain   normalized   (mean must be 1.000 — 16.9's calibration)")
    for p, g in zip(room, gains, strict=True):
        print(f"  {p.name:15s} {p.hype_gain:8.2f} {g:12.3f}")
    print(f"  {'MEAN':15s} {np.mean([p.hype_gain for p in room]):8.2f} {gains.mean():12.3f}")

    # -- the corpus face-validity check on the hand-set mix ---------------------------------------
    d = con.execute(CORPUS_SQL).df()
    corpus = {"n_managers": int(len(d)), "qb_share_median": float(d["qb"].median()),
              "rb_share_median": float(d["rb"].median()),
              "rb_light_share": float((d["rb"] < 0.20).mean()),
              "te_heavy_share": float((d["te"] > 0.12).mean())}
    print(f"\n  corpus check ({corpus['n_managers']} eligible-redraft managers, >=30 picks):")
    print(f"    median QB share {corpus['qb_share_median']:.3f} · RB share "
          f"{corpus['rb_share_median']:.3f} · RB-light managers {corpus['rb_light_share']:.1%}")
    print("    -> RB-light is ~1 manager in 60, so no `zero_rb` seat sits in the default room;\n"
          "       it stays one override away. The mix is hand-set: a manager's tendency is\n"
          "       observable, his personality is a latent label the corpus does not carry.")

    raw = adp_asof(con, args.season, pd.Timestamp.today().date(), teams=args.teams)
    if raw.empty:
        raise SystemExit(f"no {args.season} FFC board at teams={args.teams}")
    board = enrich_board(con, args.season, raw)
    print(f"\n  board: {len(board)} players (read-only enrichment — frozen stack untouched)")

    # -- 1. mechanics -----------------------------------------------------------------------------
    st = simulate_draft(board, n_teams=args.teams, rounds=args.rounds, seed=0,
                        opponent_pick_fn=make_room_pick_fn(model, room))
    log = st.pick_log().query("not is_you")
    drafted_legally = len(log) == (args.teams - 1) * args.rounds
    print(f"\n  mechanics: {len(log)} opponent picks over {args.rounds} rounds "
          f"({'PASS' if drafted_legally else 'FAIL'})")

    # an autopilot seat must still be the deterministic ADP autopicker inside a mixed room
    auto_seats = [i for i, p in enumerate(room) if p.name == "autopilot"]
    auto_reach = []
    for i in auto_seats:
        team = i + 1 if i >= st.your_team else i
        sub = log[log["team"] == team]
        auto_reach.append(float((sub["adp"] - sub["overall_pick"]).mean()))
    tilting = [i for i, p in enumerate(room) if p.hype_gain > 1.0]
    tilt_reach = []
    for i in tilting:
        team = i + 1 if i >= st.your_team else i
        sub = log[log["team"] == team]
        tilt_reach.append(float((sub["adp"] - sub["overall_pick"]).mean()))
    print(f"    autopilot seats mean (ADP − pick) {np.mean(auto_reach):+.2f}  vs "
          f"tilting seats {np.mean(tilt_reach):+.2f}  (+ = reached)")

    # -- 2/3. the hype coupling: does the shock ride the seats that would chase it? ----------------
    # Measured in ADP picks, because "0.05 utility" is not a quantity anyone can judge.
    beta_adp = abs(float(model.beta[list(ALL_FEATURES).index("adp_s")]))
    per_pick = beta_adp / _ADP_SCALE
    shock_sd = float(np.std([_hype_vector(board, args.teams, 1000 + s) for s in range(20)]))
    print(f"\n  the calibrated 16.9 shock is sd {shock_sd:.4f} utility = "
          f"{shock_sd / per_pick:.2f} ADP picks")

    print(f"\n  hype coupling ({args.n_drafts} drafts per arm, shared per-draft shock) ...")
    off = _loud_share(board, room, model, n_teams=args.teams, rounds=args.rounds,
                      n_drafts=args.n_drafts, amp=None)
    on = _loud_share(board, room, model, n_teams=args.teams, rounds=args.rounds,
                     n_drafts=args.n_drafts, amp=1.0)
    big = _loud_share(board, room, model, n_teams=args.teams, rounds=args.rounds,
                      n_drafts=args.n_drafts, amp=AMP_GATE)
    hi_ix = [i for i, p in enumerate(room) if p.hype_gain > 1.0]
    lo_ix = [i for i, p in enumerate(room) if p.hype_gain == 0.0]
    print("    share of each seat's picks that were that draft's hyped players:")
    print(f"      {'seat':18s}{'gain':>6s}{'off':>9s}{'shipped':>10s}{'delta':>8s}"
          f"{f'x{AMP_GATE:g}':>10s}{'delta':>8s}")
    for i, p in enumerate(room):
        print(f"      {p.name + '#' + str(i):18s}{gains[i]:6.2f}{off[i]:9.3f}{on[i]:10.3f}"
              f"{on[i] - off[i]:+8.3f}{big[i]:10.3f}{big[i] - off[i]:+8.3f}")
    gap_on = float(np.mean(on[hi_ix]) - np.mean(on[lo_ix]))
    gap_off = float(np.mean(off[hi_ix]) - np.mean(off[lo_ix]))

    # ★ the bar is the whole room ranked, not the two ends of it — see the module docstring.
    rho_ship = float(stats.spearmanr(on - off, gains).statistic)
    rho_gate = float(stats.spearmanr(big - off, gains).statistic)
    rho_ctrl = float(stats.spearmanr(off, gains).statistic)
    print(f"    spearman(delta, seat gain):  shipped size {rho_ship:+.3f}   "
          f"x{AMP_GATE:g} {rho_gate:+.3f}   control (gain vs channel-OFF share) {rho_ctrl:+.3f}")
    print(f"    largest per-seat move at the shipped size: {np.abs(on - off).max():.3f} "
          f"(vs {np.abs(big - off).max():.3f} at x{AMP_GATE:g})")

    checks = {
        "room_drafts_a_legal_board": drafted_legally,
        "gains_normalized_to_mean_one": abs(float(gains.mean()) - 1.0) < 1e-9,
        "autopilot_seats_do_not_reach": np.mean(auto_reach) < np.mean(tilt_reach),
        # The MECHANISM is what this substep owns, so that is what is gated: given a shock large
        # enough to resolve against softmax noise, the story must reach each seat in proportion to
        # the gain it was assigned. Stated as an OPPOSITION (the 16.14 lesson) and across EVERY
        # seat (the 16.15 lesson) — a two-ended gap passed a build that routed the story backwards.
        "mechanism_routes_in_proportion_to_gain": rho_gate >= 0.8,
        "mechanism_needs_the_open_channel": rho_gate > abs(rho_ctrl),
        # NOT gated: whether the *shipped-size* shock moves the room. It does not, and that is
        # 16.9's null propagating rather than a defect here — see the JSON's `shipped_size_verdict`.
    }
    print("\n  face validity:")
    for k, v in checks.items():
        print(f"    {'PASS' if v else 'FAIL'}  {k}")

    con.close()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "season": args.season, "teams": args.teams, "rounds": args.rounds,
        "n_drafts": args.n_drafts,
        "default_room": list(DEFAULT_ROOM),
        "seat_gains": {f"{p.name}#{i}": {"raw": p.hype_gain, "normalized": float(g)}
                       for i, (p, g) in enumerate(zip(room, gains, strict=True))},
        "corpus_check": corpus,
        "shock_sd_utility": shock_sd,
        "shock_sd_adp_picks": shock_sd / per_pick,
        "amp_gate": AMP_GATE,
        "loud_share_channel_off": {f"{p.name}#{i}": float(off[i]) for i, p in enumerate(room)},
        "loud_share_shipped_size": {f"{p.name}#{i}": float(on[i]) for i, p in enumerate(room)},
        "loud_share_amplified": {f"{p.name}#{i}": float(big[i]) for i, p in enumerate(room)},
        "chaser_minus_autopicker_on": gap_on,
        "chaser_minus_autopicker_off": gap_off,
        "spearman_delta_vs_gain_shipped": rho_ship,
        "spearman_delta_vs_gain_amplified": rho_gate,
        "spearman_channel_off_vs_gain": rho_ctrl,
        "max_seat_move_shipped": float(np.abs(on - off).max()),
        "max_seat_move_amplified": float(np.abs(big - off).max()),
        "shipped_size_verdict": (
            "NULL at the shipped shock size, and it is 16.9's null rather than a 16.15 defect. "
            f"The calibrated draw is {shock_sd / per_pick:.2f} ADP picks; the largest per-seat "
            f"change in hyped-player share is {np.abs(on - off).max():.3f} and its rank "
            f"correlation with seat gain is {rho_ship:+.3f} — inside the softmax's own noise. "
            f"Amplified x{AMP_GATE:g} the same measurement gives {rho_gate:+.3f}, so the routing "
            "is built correctly and is waiting on a signal worth routing. 16.9 already reported "
            "its own size as unidentified; nothing here re-opens it. Phase 16's FIFTH null."),
        "available_personalities": sorted(personalities()),
        "face_validity": checks,
        "selector_contract": (
            "Phase 14 calls make_room(mix, n_opponents=n_teams-1, seed=..., fav_teams=...) and "
            "passes the result to make_room_pick_fn(model, room, hype=...). The UI needs only the "
            "personality names (available_personalities) and one seat count; everything else is "
            "defaulted. Full spec incl. the honesty rules: docs/PLAYER-VIEW.md §9."),
        "validation_note": (
            "face validity + unit tests only — no Brier gate (decided 2026-07-23). A room is a "
            "realism feature; 11.1 already owns 'predicts the average manager'."),
    }, indent=2, default=float))
    print(f"\nwrote {OUT}")
    assert all(checks.values()), "a face-validity check failed — see the table above"
    print("\nPhase 16.15 (mock room) — all checks PASS.")


if __name__ == "__main__":
    main()
