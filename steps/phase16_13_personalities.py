"""Phase 16.13 + 16.14 runner — enrich the mock board, then read the five headline personalities.

    uv run python steps/phase16_13_personalities.py [--season 2026] [--n-drafts 12]

Two done-bars, on the real live board rather than a fixture:

**16.13** the enriched board carries the frozen Phase-5 distribution + Phase-4 value fields for the
players those contracts cover, and the shortfall is *reported* — the players missing a distribution
should be exactly the ones nothing could have projected (kickers, defenses), not a silent hole.

**16.14** the five personalities are legible: each drafts a pool measurably skewed toward the thing
it says it likes, autopilot reproduces pure ADP order, and nobody reaches further than its stated
ceiling. Validation here is **face validity + the unit tests in `tests/test_personalities.py`** —
there is deliberately no Brier gate (user decision, 2026-07-23): this is a realism/UX feature, and
a personality set is judged by whether a practice draft feels like a real room, not by whether it
predicts the average manager better than 11.1 (it will not — 11.1 *is* the average manager).

Everything read here is read-only w.r.t. the frozen value/optimizer/cost stack.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from fantasy_quant.data.sources.adp import adp_asof
from fantasy_quant.draft.enrichment import DIST_COLS, enrich_board, enrichment_coverage
from fantasy_quant.draft.opponent_model import _ADP_SCALE, ALL_FEATURES, OpponentModel
from fantasy_quant.draft.personalities import (
    HEADLINERS,
    Personality,
    make_opponent_pick_fn,
    personalities,
    pos_z,
)
from fantasy_quant.draft.simulator import board_player_key, simulate_draft

DB = Path("data/fantasy_quant.duckdb")
OUT = Path("analysis/phase16_13_personalities.json")
COEF_JSON = Path("analysis/phase11_opponent_model.json")

#: The signals the readout profiles, with short display labels. ``upside``/``floor`` are the
#: level-controlled shape signals the personalities actually tilt on; the raw ``q90``/``q10`` are
#: kept alongside them precisely as the **contrast** — see the note printed under the table.
PROFILE: dict[str, str] = {
    "upside": "upside", "floor": "floor", "durability": "durab", "boom_prob": "boom",
    "bust_prob": "bust", "games_played_mean": "games(raw)", "q90": "q90(raw)", "q10": "q10(raw)",
    "vbd": "vbd", "rookie": "rookie", "cos": "cos",
}


def _model() -> OpponentModel:
    coef = json.loads(COEF_JSON.read_text())["coefficients"]
    return OpponentModel(feature_cols=list(ALL_FEATURES),
                         beta=np.array([coef[c] for c in ALL_FEATURES]))


def _z_board(board: pd.DataFrame) -> pd.DataFrame:
    """The board with each profiled signal replaced by its within-position z — the same units the
    personalities tilt in, so the readout is scale-free and comparable across signals."""
    z = board.copy()
    pos = board["position"].to_numpy()
    for c in PROFILE:
        if c in board.columns:
            z[c] = pos_z(board[c], pos)
    return z


def _profile(board, zboard, pers, *, n_teams, rounds, n_drafts, model, hype=None) -> dict:
    """Pool ``n_drafts`` seeded drafts and report what this personality's room actually took.

    Pooled, because a single draft cannot separate a 1–2-round reach from the choice softmax's own
    noise — measured, the sign of the difference flips between seeds. Same discipline the rest of
    the repo applies to a one-season result.
    """
    keys = board_player_key(board).astype(str)
    rows, mixes, reaches = [], [], []
    for s in range(n_drafts):
        st = simulate_draft(board, n_teams=n_teams, rounds=rounds, seed=s,
                            opponent_pick_fn=make_opponent_pick_fn(model, pers, hype=hype))
        log = st.pick_log().query("not is_you")
        rows.append(zboard[keys.isin(set(log["player_key"]))][list(PROFILE)].mean())
        mixes.append(log[log["round"] <= 3]["pos"].value_counts())
        # how far ahead of his ADP each player went: + = the room reached for him
        reaches.append(float((log["adp"] - log["overall_pick"]).mean()))
    prof = pd.concat(rows, axis=1).mean(axis=1)
    mix = pd.concat(mixes, axis=1).sum(axis=1).fillna(0)
    return {
        "signal_z": {k: round(float(v), 4) for k, v in prof.items()},
        "early_pos_mix": {k: int(mix.get(k, 0)) for k in ("RB", "WR", "QB", "TE")},
        "mean_adp_minus_pick": round(float(np.mean(reaches)), 3),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--teams", type=int, default=10)
    ap.add_argument("--rounds", type=int, default=15)
    ap.add_argument("--n-drafts", type=int, default=12)
    args = ap.parse_args()

    con = duckdb.connect(str(DB), read_only=True)
    model = _model()

    # ===== 16.13 — the enrichment ==============================================================
    print(f"=== 16.13 — enriching the {args.season} board (read-only, frozen contracts) ===")
    raw = adp_asof(con, args.season, pd.Timestamp.today().date(), teams=args.teams)
    if raw.empty:
        raise SystemExit(f"no {args.season} FFC board at teams={args.teams} — nothing to enrich")
    board = enrich_board(con, args.season, raw)
    cov = enrichment_coverage(board)
    print(f"  board: {cov['n_rows']} players")
    for c, v in cov.items():
        if c != "n_rows":
            print(f"    {c:20s} {v:.1%}")
    gap = board[board["q90"].isna()]["position"].value_counts().to_dict()
    print(f"  no Phase-5 distribution: {gap}")
    skill_gap = {k: v for k, v in gap.items() if k in ("QB", "RB", "WR", "TE")}
    print(f"  ... of which skill players: {skill_gap or 'none'}  "
          f"(kickers/defenses carry no projection at all — that shortfall is structural)")
    assert cov["q90"] > 0.75, "the frozen distribution should cover most of a draftable board"

    # -- why `safe_floor` does not weight durability: the two intents are opposed on this board ---
    # Reported, not assumed. `durability` is level-residualized games-played (T17 made the raw
    # column a real forecast and, in the same move, a level proxy). At a fixed projected level it
    # runs AGAINST the floor, so a "safe" manager has to pick one; ours picks the floor.
    shp = board.dropna(subset=["durability", "floor", "bust_prob"])
    tension = {a: float(np.corrcoef(shp["durability"], shp[a])[0, 1])
               for a in ("floor", "bust_prob", "upside")}
    print(f"\n  durability vs the other shape signals (n={len(shp)}): "
          + "  ".join(f"{k} {v:+.3f}" for k, v in tension.items()))
    print("    ↑ floor and durability are OPPOSED at a fixed level, so a floor-buying manager\n"
          "      cannot also be an above-average durability buyer. The weight still earns its\n"
          "      place — see the A/B below — it just cannot win that argument outright.")

    # ===== 16.14 — the personalities ===========================================================
    beta_adp = float(model.beta[list(ALL_FEATURES).index("adp_s")])
    print(f"\n=== 16.14 — the five headline personalities (β_adp_s = {beta_adp:+.4f}) ===")
    print("  reach ceilings, stated in picks and converted through the model's own ADP term:")
    P = personalities()
    for name in HEADLINERS:
        mrp = P[name].max_reach_picks
        cap = P[name].reach_cap(beta_adp)
        print(f"    {name:15s} max_reach_picks={('none' if mrp is None else f'{mrp:.0f}'):>5s}"
              f"   cap={('uncapped' if cap is None else f'{cap:.3f} utility'):>16s}"
              f"   hype_gain={P[name].hype_gain:.1f}")

    zboard = _z_board(board)
    kw = dict(n_teams=args.teams, rounds=args.rounds, n_drafts=args.n_drafts, model=model)
    print(f"\n  pooling {args.n_drafts} drafts per personality "
          f"({args.teams} teams x {args.rounds} rounds) ...")
    prof = {name: _profile(board, zboard, P[name], **kw) for name in HEADLINERS}
    # a homer with a favourite team, to show the fandom channel that was inert before 16.14
    fav_team = board["team"].value_counts().index[0]
    homer_fan = Personality("homer_fan", scale={"fandom": 2.5}, signal_weights={"cos": 0.35},
                            hype_gain=2.5, fav_teams=(fav_team,),
                            max_reach_picks=P["homer"].max_reach_picks)
    prof[f"homer({fav_team} fan)"] = _profile(board, zboard, homer_fan, **kw)

    print("\n  drafted-pool signal profile (mean within-position z of what each room took):")
    print("  " + f"{'personality':20s}" + "".join(f"{lbl:>10s}" for lbl in PROFILE.values()))
    for name, p in prof.items():
        print(f"  {name:20s}" + "".join(f"{p['signal_z'][c]:>+10.3f}" for c in PROFILE))
    print("  ↑ note the q90(raw)/games(raw) columns do NOT track upside/durab — within position\n"
          "    they are collinear with the projected level (quantiles ~0.98; games +0.46…+0.90\n"
          "    once T17 was fixed), so they measure quality, not shape. That is the whole reason\n"
          "    `upside`/`floor`/`durability` exist; see enrichment.residual_shape.")

    print("\n  first-3-round positional mix / mean (ADP − pick), + = the room reached:")
    for name, p in prof.items():
        mix = " ".join(f"{k}={p['early_pos_mix'][k]:3d}" for k in ("RB", "WR", "QB", "TE"))
        print(f"  {name:22s} {mix}   reach {p['mean_adp_minus_pick']:+.2f}")

    # -- does the durability weight MOVE anything? the A/B, not a comparison to balanced ----------
    # `durability` was a no-op for its whole first life: it was weighted in `signal_weights` but
    # missing from `simulator.PASSTHROUGH_COLS`, so `signal_bonus` skipped it and the room still
    # drafted legally (the third time this bug class has landed — cf. `fandom`, `rookie`). The
    # check that catches it is the weight against ITSELF-OFF. Comparing to `balanced` cannot do it:
    # floor and durability are opposed, so this manager sits below balanced on durability whether
    # the weight is on (-0.123) or off (-0.174) at n=80 -- the gap to balanced is ~0 and flips sign
    # with the seed, while the A/B gain is a stable +0.05.
    safe_off = Personality("safe_floor_no_durability",
                           signal_weights={k: v for k, v in P["safe_floor"].signal_weights.items()
                                           if k != "durability"},
                           temperature=P["safe_floor"].temperature,
                           hype_gain=P["safe_floor"].hype_gain,
                           max_reach_picks=P["safe_floor"].max_reach_picks)
    ab_off = _profile(board, zboard, safe_off, **kw)
    durab_gain = (prof["safe_floor"]["signal_z"]["durability"]
                  - ab_off["signal_z"]["durability"])
    print(f"\n  durability A/B (safe_floor with vs without the weight, {args.n_drafts} drafts):")
    print(f"    durability z {ab_off['signal_z']['durability']:+.3f} -> "
          f"{prof['safe_floor']['signal_z']['durability']:+.3f}   (gain {durab_gain:+.3f})")
    print(f"    floor z      {ab_off['signal_z']['floor']:+.3f} -> "
          f"{prof['safe_floor']['signal_z']['floor']:+.3f}   "
          f"— what the durability tilt costs him, exactly as the −0.34 opposition predicts")

    # -- the face-validity done-bar -------------------------------------------------------------
    up, safe, bal = prof["upside_chaser"], prof["safe_floor"], prof["balanced"]
    checks = {
        "upside_chases_ceiling": up["signal_z"]["upside"] > bal["signal_z"]["upside"],
        "upside_over_safe_on_shape": up["signal_z"]["upside"] > safe["signal_z"]["upside"],
        "safe_buys_floor": safe["signal_z"]["floor"] > bal["signal_z"]["floor"],
        "safe_over_upside_on_floor": safe["signal_z"]["floor"] > up["signal_z"]["floor"],
        "safe_avoids_bust_tail": safe["signal_z"]["bust_prob"] < bal["signal_z"]["bust_prob"],
        # a weight must MOVE something, not merely run (the 16.14 inert-`fandom` lesson)
        "durability_weight_moves_the_pool": durab_gain > 0.02,
        "homer_chases_changed_situations":
            prof["homer"]["signal_z"]["cos"] > bal["signal_z"]["cos"],
    }
    print("\n  face validity:")
    for k, v in checks.items():
        print(f"    {'PASS' if v else 'FAIL'}  {k}")

    # autopilot must be exactly the deterministic ADP autopicker — an equality, not a tendency
    auto = simulate_draft(board, n_teams=args.teams, rounds=args.rounds, seed=0,
                          opponent_pick_fn=make_opponent_pick_fn(model, P["autopilot"]))
    ref = simulate_draft(board, n_teams=args.teams, rounds=args.rounds, seed=0, noise=0.0)
    auto_ok = list(auto.pick_log()["player_key"]) == list(ref.pick_log()["player_key"])
    print(f"    {'PASS' if auto_ok else 'FAIL'}  autopilot_is_pure_adp_order")
    checks["autopilot_is_pure_adp_order"] = auto_ok

    con.close()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "season": args.season, "teams": args.teams, "rounds": args.rounds,
        "n_drafts_pooled": args.n_drafts,
        "enrichment_coverage": cov,
        "missing_distribution_by_position": gap,
        "beta_adp_s": beta_adp,
        "adp_scale": _ADP_SCALE,
        "reach_ceilings": {n: {"picks": P[n].max_reach_picks,
                               "utility_cap": P[n].reach_cap(beta_adp),
                               "hype_gain": P[n].hype_gain} for n in HEADLINERS},
        "profiles": prof,
        "durability_tension": tension,
        "durability_ab": {"with": prof["safe_floor"]["signal_z"]["durability"],
                          "without": ab_off["signal_z"]["durability"], "gain": durab_gain,
                          "floor_with": prof["safe_floor"]["signal_z"]["floor"],
                          "floor_without": ab_off["signal_z"]["floor"],
                          "vs_balanced": (prof["safe_floor"]["signal_z"]["durability"]
                                          - bal["signal_z"]["durability"])},
        "face_validity": checks,
        "validation_note": ("face validity + unit tests only — no corpus Brier gate. A personality "
                            "set is a realism feature; 11.1 already owns 'predicts the average "
                            "manager', and deviating from it is the entire point here."),
    }, indent=2, default=float))
    print(f"\nwrote {OUT}")
    assert all(checks.values()), "a face-validity check failed — see the table above"
    missing = [c for c in DIST_COLS if c not in board.columns]
    assert not missing, f"enrichment did not attach {missing}"
    print("\nPhase 16.13 + 16.14 — all checks PASS.")


if __name__ == "__main__":
    main()
