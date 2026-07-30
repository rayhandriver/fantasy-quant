"""Phase 17 done-bar — League-Format Fidelity (17.1–17.4).

    uv run python steps/phase17_formats.py [--season 2026]

Five gates, in the order the BUILD_PLAN states them:

* **G1 solver == brute force** on every shipped format (17.1). Checked against an *exhaustive*
  optimum, never against the other greedy — two greedies that share a bug agree perfectly.
* **G2 superflex drafts QBs early** (17.1, the phase's headline face-validity bar). Run on the live
  board, so it exercises the real value chain rather than synthetic points.
* **G3 the default format did not move** — replacement ranks, the default `RuleSet`, `RosterSlots`
  and `LeagueFormat` all reproduce their pre-17 values. Phase 17 is a *config generalization*; if
  the lockbox-validated case moves, it is not one.
* **G4 the settings contract round-trips** presets and a fully custom league, and rejects what the
  engine cannot play (17.3).
* **G5 keepers remove supply and cost picks** (17.4).

⚠ Non-default formats are **not lockbox-validated**. They are unit-tested for correctness and
face-validity; no out-of-sample claim from `findings.md` §"LOCKBOX EVALUATION" transfers to them.
`LeagueSettings.lockbox_validated()` is the programmatic form of that sentence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from fantasy_quant.backtest.metrics import replacement_ranks
from fantasy_quant.backtest.scoring import DEFAULT_RULESET, RuleSet, ruleset_from_preset
from fantasy_quant.data.db import connect
from fantasy_quant.draft.config import Keeper, LeagueSettings
from fantasy_quant.draft.simulator import RosterSlots, simulate_draft
from fantasy_quant.simulation.season import LeagueFormat, lineup_points_matrix

POS = ("QB", "RB", "WR", "TE", "K", "DST")
FORMATS = {
    "default": RosterSlots(),
    "superflex": RosterSlots(superflex=1),
    "two_flex": RosterSlots(flex=2),
    "2qb_superflex": RosterSlots(qb=2, superflex=1),
    "no_k_dst_3flex": RosterSlots(k=0, dst=0, flex=3),
}
#: The pre-17 baseline. Hard-coded rather than recomputed: a regression guard that derives its own
#: expectation from the code it guards cannot fail.
BASELINE_RANKS = {"QB": 10, "RB": 24, "WR": 24, "TE": 12, "K": 10, "DST": 10}


def _gate(name: str, ok: bool, **detail) -> dict:
    print(f"  {'PASS' if ok else 'FAIL'}  {name}  {detail}")
    return {"gate": name, "pass": bool(ok), **detail}


def _brute(points, positions, slots: RosterSlots) -> float:
    plan: list[tuple[str, ...]] = []
    for p, n in slots.base_demand().items():
        plan += [(p,)] * n
    for count, elig in slots.flex_groups():
        plan += [tuple(elig)] * count
    best = 0.0

    def rec(si: int, used: int, tot: float) -> None:
        nonlocal best
        if si == len(plan):
            best = max(best, tot)
            return
        rec(si + 1, used, tot)
        for i in range(len(points)):
            if not (used >> i) & 1 and positions[i] in plan[si]:
                rec(si + 1, used | (1 << i), tot + points[i])

    rec(0, 0, 0.0)
    return best


def g1_solver(rng) -> dict:
    worst, bad = 0.0, 0
    for slots in FORMATS.values():
        for _ in range(40):
            pts = rng.uniform(0, 30, size=8)
            pos = [POS[int(rng.integers(0, len(POS)))] for _ in range(8)]
            got = float(np.ravel(lineup_points_matrix(pts[:, None], pos, slots))[0])
            err = abs(got - _brute(pts, pos, slots))
            worst = max(worst, err)
            bad += err > 1e-9
    return _gate("G1 solver == brute force (all formats)", bad == 0,
                 formats=list(FORMATS), n_per_format=40, worst_abs_err=round(worst, 12))


def g2_superflex_drafts_qbs_early(con, season: int) -> dict:
    """Face validity: under superflex replacement levels, QBs climb the value board.

    Measured on the **value board**, not on a simulated draft — the board is what a draft consumes,
    and it isolates 17.1's replacement change from every behavioural knob in the room.
    """
    from fantasy_quant.draft.config import DraftConfig, LeagueSetup
    from fantasy_quant.draft.optimizer import assemble_value

    out: dict[str, float] = {}
    for label, slots in (("one_qb", RosterSlots()), ("superflex", RosterSlots(superflex=1))):
        # `rounds` has to cover the roster, and a superflex adds a starter — caught by
        # `LeagueSetup.validate` the first time this gate ran, which is the validation working.
        cfg = DraftConfig(league=LeagueSetup(slots=slots, rounds=slots.total))
        vi = assemble_value(con, int(season), cfg)
        vi = vi.dropna(subset=["base_value"]).sort_values("base_value", ascending=False)
        top50 = vi.head(50)
        out[f"{label}_qb_in_top50"] = int((top50["pos"] == "QB").sum())
        qb = vi[vi["pos"] == "QB"]
        out[f"{label}_best_qb_rank"] = int(vi.index.get_indexer([qb.index[0]])[0] + 1) if len(qb) \
            else -1
    ok = (out["superflex_qb_in_top50"] > out["one_qb_qb_in_top50"]
          and out["superflex_best_qb_rank"] <= out["one_qb_best_qb_rank"])
    return _gate("G2 superflex lifts QBs on the value board", ok, season=int(season), **out)


def g3_default_unchanged() -> dict:
    ranks = replacement_ranks(RosterSlots(), 10)
    checks = {
        "replacement_ranks": ranks == BASELINE_RANKS,
        "flex_groups": RosterSlots().flex_groups() == ((1, ("RB", "WR", "TE")),),
        "starters_9_total_15": (RosterSlots().starters, RosterSlots().total) == (9, 15),
        "full_ppr_preset_is_default": ruleset_from_preset("full_ppr") == DEFAULT_RULESET,
        "default_ruleset_untouched": RuleSet() == DEFAULT_RULESET,
        "default_settings_rebuild": (LeagueSettings().roster_slots() == RosterSlots()
                                     and LeagueSettings().league_format() == LeagueFormat()
                                     and LeagueSettings().ruleset() == DEFAULT_RULESET),
        "default_is_lockbox_validated": LeagueSettings().lockbox_validated(),
    }
    return _gate("G3 the default format did not move", all(checks.values()),
                 ranks=ranks, checks=checks)


def g4_settings_contract() -> dict:
    ok_custom = True
    try:
        s = LeagueSettings(n_teams=12, superflex=1, scoring_preset="te_premium",
                           playoff_teams=8, rounds=16)
        s.validate()
        ok_custom = (not s.lockbox_validated()
                     and s.roster_slots().superflex == 1
                     and s.ruleset().offense.te_rec_bonus == 0.5
                     and replacement_ranks(s.roster_slots(), 12)["QB"] == 24)
    except Exception:                                        # noqa: BLE001 — a fail is the result
        ok_custom = False

    rejected = {}
    for label, kwargs in {
        "odd_teams": dict(n_teams=11),
        "bad_bracket": dict(playoff_teams=5),
        "unknown_preset": dict(scoring_preset="nope"),
        "typo_override": dict(scoring_overrides={"rec_typo": 1.0}),
        "rounds_below_roster": dict(rounds=3),
        "keeper_out_of_range": dict(keepers=(Keeper("x", team=1, round=99),)),
    }.items():
        try:
            LeagueSettings(**kwargs).validate()
            rejected[label] = False
        except ValueError:
            rejected[label] = True
    return _gate("G4 settings round-trip + reject the unplayable",
                 ok_custom and all(rejected.values()),
                 custom_league_ok=ok_custom, rejected=rejected)


def g5_keepers() -> dict:
    n = 200
    board = pd.DataFrame({"player_name": [f"P{i}" for i in range(n)],
                          "position": [POS[i % len(POS)] for i in range(n)],
                          "adp": np.arange(1, n + 1, dtype=float)})
    keeps = (Keeper("P0", team=1, round=1), Keeper("P5", team=1, round=2),
             Keeper("P3", team=4, round=1))
    st = simulate_draft(board, n_teams=10, rounds=15, seed=1, keepers=keeps)
    drafted = [e for e in st.log if not e.get("keeper")]
    names = {e["player_name"] for e in drafted}
    plain = simulate_draft(board, n_teams=10, rounds=15, seed=1)
    ok = (len(drafted) == 150 - len(keeps)
          and not {"P0", "P5", "P3"} & names
          and all(len(r) == 15 for r in st.rosters)
          and [e["player_name"] for e in plain.log]
          == [e["player_name"] for e in simulate_draft(board, n_teams=10, rounds=15,
                                                       seed=1, keepers=()).log])
    return _gate("G5 keepers remove supply and cost picks", ok,
                 picks_made=len(drafted), forfeited=len(keeps),
                 kept_redrafted=sorted({"P0", "P5", "P3"} & names))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--out", default="analysis/phase17_formats.json")
    args = ap.parse_args()

    rng = np.random.default_rng(17)
    print("Phase 17 — League-Format Fidelity\n")
    gates = [g1_solver(rng), g3_default_unchanged(), g4_settings_contract(), g5_keepers()]
    try:
        gates.insert(1, g2_superflex_drafts_qbs_early(connect(), args.season))
    except Exception as exc:                                 # noqa: BLE001 — report, never stop
        gates.insert(1, _gate("G2 superflex lifts QBs on the value board", False,
                              error=str(exc)[:300]))

    out = {"season": int(args.season), "gates": gates,
           "all_pass": all(g["pass"] for g in gates),
           "lockbox_validated_default": LeagueSettings().lockbox_validated(),
           "note": ("Non-default formats are supported and correctness-tested but NOT "
                    "lockbox-validated; no out-of-sample claim transfers to them.")}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2, default=float))
    print(f"\nALL PASS: {out['all_pass']}   -> {args.out}")


if __name__ == "__main__":
    main()
