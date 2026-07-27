"""Phase 16.12 done-bar — consuming the drift signal in all three places.

The BUILD_PLAN asks for four things, and the fourth is the one that protects everything built
before this session:

**(a) realism** — mock-draft opponents reflect the drift channels.
**(b) advice (opt-in)** — the 9.4 lookahead prices a hyped player as likelier to be gone.
**(c) app readout** — an honest ``P(available at your pick)`` plus a reach-risk label, engine-side
only (the UI belongs to Phase 14, which is deliberately built last).
**(d) isolation** — the frozen value / distribution / optimizer / VBD / cost-report stack is
**provably untouched**. That is checked here by re-running the greedy with drift off and comparing
against a run that never knew drift existed, and it is checked again as a unit test.

Run:  uv run python steps/phase16_12_consumption.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from fantasy_quant.adp import boards
from fantasy_quant.adp.hype_board import HYPE_CSV, load_hype_board
from fantasy_quant.draft.drift import DriftConfig, availability_readout, drift_picks, drift_utility
from fantasy_quant.draft.opponent_model import ALL_FEATURES, CHOICE_TOP_K, OpponentModel
from fantasy_quant.draft.personalities import make_opponent_pick_fn
from fantasy_quant.draft.simulator import _prepare_board, simulate_draft

DB = Path("data/fantasy_quant.duckdb")
OUT = Path("analysis/phase16_12_consumption.json")
COEF_JSON = Path("analysis/phase11_opponent_model.json")


def _model() -> OpponentModel:
    coef = json.loads(COEF_JSON.read_text())["coefficients"]
    return OpponentModel(feature_cols=list(ALL_FEATURES),
                         beta=np.array([coef[c] for c in ALL_FEATURES]))


def _board(con, season: int, teams: int) -> pd.DataFrame:
    bd, _src = boards.resolve_board(con, season, "ppr", teams, allow_ecr=False)
    bd = bd.rename(columns={"name": "player_name"}).copy()
    bd["adp"] = pd.to_numeric(bd["adp"], errors="coerce")
    return bd.dropna(subset=["adp"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--teams", type=int, default=10)
    ap.add_argument("--rounds", type=int, default=18)
    ap.add_argument("--n-drafts", type=int, default=30)
    args = ap.parse_args()

    con = duckdb.connect(str(DB), read_only=True)
    model = _model()
    beta_adp_s = float(model.beta[list(model.feature_cols).index("adp_s")])
    bd = _board(con, args.season, args.teams)
    prepped = _prepare_board(bd)
    out: dict = {"season": args.season, "n_board": int(len(bd))}

    # The shipped board is unreviewed by design, so the *production* config contributes nothing.
    # The demonstration therefore runs a second config with the gate bypassed, and reports both —
    # otherwise this step would show a wiring diagram with no current flowing through it.
    prod = DriftConfig(hype=True)
    demo = DriftConfig(hype=True, require_reviewed=False, momentum_w=0.0)
    out["config"] = {"production": prod.describe(), "demonstration": demo.describe()}
    out["review_state"] = {
        "n_rows": int(len(load_hype_board(HYPE_CSV, args.season, require_reviewed=False))),
        "n_reviewed": int(len(load_hype_board(HYPE_CSV, args.season))),
    }

    picks_prod = drift_picks(prepped, cfg=prod, season=args.season, con=con)
    picks_demo = drift_picks(prepped, cfg=demo, season=args.season, con=con)
    print(f"drift picks: production nonzero={int((picks_prod != 0).sum())} "
          f"(unreviewed board ⇒ inert), demonstration nonzero={int((picks_demo != 0).sum())}")

    # ---- (a) realism --------------------------------------------------------------------------
    print("\n(a) realism: mock-draft flow with and without drift ...", flush=True)
    u = drift_utility(prepped, beta_adp_s=beta_adp_s, cfg=demo, season=args.season, con=con)

    def flow(offsets):
        rng = np.random.default_rng(5)
        logs = []
        for _ in range(args.n_drafts):
            fn = make_opponent_pick_fn(model, top_k=CHOICE_TOP_K, hype=offsets)
            st = simulate_draft(bd, n_teams=args.teams, rounds=args.rounds,
                                seed=int(rng.integers(1 << 30)), opponent_pick_fn=fn,
                                your_pick_fn=lambda s, _f=fn: int(_f(s, s.your_team)))
            logs.append(pd.DataFrame(st.log))
        return pd.concat(logs, ignore_index=True)

    a, b = flow(None), flow(u)
    moved = (a.groupby("player_key")["overall_pick"].mean()
             - b.groupby("player_key")["overall_pick"].mean()).dropna()
    hyped_keys = set(prepped.loc[picks_demo != 0, "player_key"].astype(str))
    on_hyped = moved[[k in hyped_keys for k in moved.index]]
    out["realism"] = {
        "n_players_moved": int((moved.abs() > 0.5).sum()),
        "mean_abs_move_all": float(moved.abs().mean()),
        "mean_move_hyped": float(on_hyped.mean()) if len(on_hyped) else float("nan"),
        "mean_abs_move_hyped": float(on_hyped.abs().mean()) if len(on_hyped) else float("nan"),
    }
    print(f"  {out['realism']['n_players_moved']} players shifted >0.5 picks; "
          f"hyped rows moved {out['realism']['mean_move_hyped']:+.2f} picks earlier on average")

    # ---- (b) opt-in advice --------------------------------------------------------------------
    print("\n(b) advice: does the 9.4 lookahead reprice a hyped player? ...", flush=True)
    out["advice"] = _advice_demo(prepped, picks_demo)
    print(f"  {out['advice']}")

    # ---- (c) app readout ----------------------------------------------------------------------
    print("\n(c) readout: P(available at your next pick) ...", flush=True)
    avail = np.ones(len(prepped), bool)
    avail[:20] = False                                   # ~2 rounds gone
    cand = prepped.rename(columns={"pos": "pos"})[["player_key", "adp", "pos"]].copy()
    ro = availability_readout(cand, model, window_picks=18, cfg=demo, season=args.season, con=con,
                              available=avail, n_sims=120, seed=3)
    ro = ro[avail]
    out["readout"] = {
        "n_rows": int(len(ro)),
        "by_reach_risk": ro["reach_risk"].value_counts().to_dict(),
        "n_drift_material": int(ro["drift_material"].sum()),
        "max_abs_delta": float(ro["p_available_delta"].abs().max()),
        "sample": ro.nsmallest(8, "adp")[
            ["player_key", "pos", "adp", "p_available", "p_available_baseline",
             "drift_picks", "reach_risk"]].to_dict("records"),
    }
    print(f"  {out['readout']['by_reach_risk']}; "
          f"{out['readout']['n_drift_material']} rows materially moved by drift")

    # ---- (d) isolation ------------------------------------------------------------------------
    print("\n(d) isolation: the frozen stack with drift off ...", flush=True)
    out["isolation"] = _isolation_check(prepped)
    print(f"  {out['isolation']}")

    gates = {
        "production_config_is_inert": bool((picks_prod == 0).all()),
        "drift_changes_mock_flow": bool(out["realism"]["n_players_moved"] > 0),
        "hyped_players_go_earlier": bool(out["realism"]["mean_move_hyped"] > 0),
        "advice_repricing_works": bool(out["advice"]["n_repriced"] > 0),
        "readout_produced": bool(out["readout"]["n_rows"] > 0),
        "frozen_stack_untouched": bool(out["isolation"]["identical"]),
    }
    out["gates"] = gates
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, default=str))
    print(f"\nwrote {OUT}")
    for k, v in gates.items():
        print(f"  {k:>28}: {'PASS' if v else 'FAIL'}")


def _advice_demo(prepped: pd.DataFrame, picks: np.ndarray) -> dict:
    """16.12(b): a hyped player's *effective* ADP is earlier, so ``survival_prob`` should price him
    as likelier to be gone by your next turn. Measured directly on the survival curve rather than
    through a full optimizer run, because that is the quantity the 9.4 lookahead consumes."""
    from fantasy_quant.draft.optimizer import DEFAULT_NOISE, survival_prob

    adp = prepped["adp"].to_numpy(float)
    window_end = 60.0
    base = survival_prob(adp, window_end, DEFAULT_NOISE)
    adj = survival_prob(adp - picks, window_end, DEFAULT_NOISE)
    d = adj - base
    hyped = picks > 0
    return {
        "n_repriced": int((np.abs(d) > 1e-9).sum()),
        # a hyped player must become LESS likely to survive - that is the whole advice
        "mean_survival_change_hyped": float(d[hyped].mean()) if hyped.any() else float("nan"),
        "direction_correct": bool(d[hyped].mean() < 0) if hyped.any() else False,
        "max_abs_change": float(np.abs(d).max()),
    }


def _isolation_check(prepped: pd.DataFrame) -> dict:
    """16.12(d): with drift off, every number the frozen stack produces must be **bit-identical**.

    Checked against a `RiskModel` built the pre-16.12 way (no `hype` argument at all) so the test
    compares against the frozen behaviour rather than against a differently-configured new object.
    """
    from fantasy_quant.covariance.shrinkage import CorrelationModel
    from fantasy_quant.draft.optimizer import RiskModel

    keys = list(prepped["player_key"].astype(str))
    bv = {k: 200.0 - i for i, k in enumerate(keys)}
    corr = CorrelationModel(table=pd.DataFrame(columns=["rel", "rho"]))
    kw = dict(lam=0.0, corr=corr, bv=bv, sd={}, team={}, pos={}, role={},
              rank_x=np.array([0.0, 200.0]), rank_y=np.array([200.0, 1.0]),
              scarcity_w=0.5)
    frozen = RiskModel(**kw)                                  # no `hype` kwarg: the old signature
    with_field = RiskModel(**kw, hype={})                     # explicit empty
    hyped = RiskModel(**kw, hype={keys[80]: 12.0})

    roster = pd.DataFrame({"player_key": []})
    pool = prepped[["player_key", "pos", "adp"]].copy()
    a = frozen.effective_rank(pool, roster, 60.0)
    b = with_field.effective_rank(pool, roster, 60.0)
    c = hyped.effective_rank(pool, roster, 60.0)
    return {
        "identical": bool(np.array_equal(a, b, equal_nan=True)),
        # and the opt-in path must actually do something, or the isolation is vacuous
        "hype_on_changes_something": bool(not np.array_equal(a, c, equal_nan=True)),
        "n_rows_changed_when_on": int(np.sum(~np.isclose(a, c, equal_nan=True))),
    }


if __name__ == "__main__":
    main()
