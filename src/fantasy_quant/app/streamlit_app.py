"""Personalization spine · step 4 — the MVP draft app (Streamlit, Autopilot + Co-pilot).

    uv sync --extra ui
    uv run streamlit run src/fantasy_quant/app/streamlit_app.py

The shareable front door for the league (PERSONALIZATION §7/§8). Two decisions get you a team
(archetype + seat); a handful of Co-pilot dials (risk λ, must/never lists, reach/wait tilts) do
the rest. It always shows your personalized roster **beside the pure-value baseline** and the
honest cost of the difference — the direct-indexing deliverable. No LLM in the loop.

Season is a parameter over the DEV seasons (lockbox 2023/24 and the 2025 holdout stay out); a
scraped 2026 ADP board drops straight in when it lands.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from fantasy_quant.backtest.walkforward import draft_date, preseason_board
from fantasy_quant.config import DEV_SEASONS
from fantasy_quant.data import db
from fantasy_quant.draft.config import ARCHETYPES, DraftConfig, LeagueSetup
from fantasy_quant.draft.optimizer import assemble_value
from fantasy_quant.valuation.cost_report import personalization_cost
from fantasy_quant.valuation.utility import DEFAULT_LAMBDA

N_TEAMS = 10
ARCHETYPE_WHY = {
    "bpa": "Best player available — pure value, no positional lean.",
    "zero_rb": "Fade RB early, load WR/TE, take RB value late.",
    "hero_rb": "One anchor RB, then pivot to receivers.",
    "elite_te": "Pay up early for a difference-making tight end.",
    "late_qb": "Wait on QB in a 1-QB league, then pounce on value.",
}


@st.cache_resource
def get_con():
    return db.connect(read_only=True)


@st.cache_data(show_spinner=False)
def load_pickers(season: int) -> pd.DataFrame:
    """Draftable players for the season's PIT board → the pick lists (label ⇄ player_key)."""
    con = get_con()
    board = preseason_board(con, season, draft_date(con, season))
    gsis = board["gsis_id"] if "gsis_id" in board.columns else None
    key = board["name"] if gsis is None else gsis.where(gsis.notna(), board["name"])
    df = pd.DataFrame({"key": key, "name": board["name"], "pos": board["position"],
                       "adp": pd.to_numeric(board["adp"], errors="coerce")})
    df = df.dropna(subset=["adp"]).sort_values("adp").reset_index(drop=True)
    adp_txt = df["adp"].round().astype(int).astype(str)
    df["label"] = df["name"] + " — " + df["pos"] + " (ADP " + adp_txt + ")"
    return df


@st.cache_data(show_spinner="Assembling the value signal (consensus→VBD, risk-dialed)…")
def load_value_index(season: int, risk_lambda: float) -> pd.DataFrame:
    con = get_con()
    cfg = DraftConfig(league=LeagueSetup(n_teams=N_TEAMS), risk_lambda=risk_lambda)
    return assemble_value(con, season, cfg)


def _keys(labels, lookup: dict[str, str]) -> list[str]:
    return [lookup[x] for x in labels]


def main() -> None:
    st.set_page_config(page_title="Fantasy-Quant · Draft", page_icon="🏈", layout="wide")
    st.title("🏈 Fantasy-Quant — personalized draft")
    st.caption("Build the team you want; see what wanting it costs versus the value-optimal team "
               "from your seat. Value = consensus→VBD (risk-dialed) · availability = ADP.")

    # ---- sidebar: Autopilot (2 decisions) + Co-pilot (a few dials) ----------------------------
    with st.sidebar:
        st.header("Autopilot")
        season = st.selectbox("Season", list(DEV_SEASONS)[::-1], index=0,
                              help="DEV seasons only; 2026 slots in once its ADP is scraped.")
        slot = st.number_input("Your draft slot", 1, N_TEAMS, 5)
        archetype = st.selectbox("Archetype", ARCHETYPES,
                                 format_func=lambda a: a.replace("_", "-"))
        st.caption(ARCHETYPE_WHY[archetype])

        picks = load_pickers(season)
        label_to_key = dict(zip(picks["label"], picks["key"], strict=False))
        options = picks["label"].tolist()

        st.header("Co-pilot")
        lam = st.slider("Risk dial λ (variance penalty)", 0.0, 0.03, DEFAULT_LAMBDA, 0.005,
                        help="0 = chase upside (risk-neutral). Higher favors safe floors.")
        st.caption("Set to 0.01 (balanced). Raise for a money league; lower to swing for ceilings.")
        must = st.multiselect("Must draft (secure within a 2-round reach)", options)
        never = st.multiselect("Never draft (hard refusal)", options)
        reach = st.multiselect("Reach ~1 round early on", options)
        wait = st.multiselect("Willing to wait ~1 round on", options)
        go = st.button("Build my team", type="primary", width="stretch")

    if not go:
        st.info("Set your archetype and seat (Autopilot), add any preferences (Co-pilot), then "
                "**Build my team**.")
        return

    tilts = {label_to_key[x]: 1.5 for x in reach}
    tilts.update({label_to_key[x]: -1.5 for x in wait})
    try:
        cfg = DraftConfig(
            league=LeagueSetup(n_teams=N_TEAMS, draft_slot=int(slot)),
            archetype=archetype, risk_lambda=lam,
            must_draft=[(k, 2.0) for k in _keys(must, label_to_key)],
            never_draft=set(_keys(never, label_to_key)),
            tilts=tilts,
        )
    except ValueError as e:
        st.error(f"That combination doesn't work: {e}")
        return

    vi = load_value_index(season, lam)
    with st.spinner("Drafting your team and its benchmark…"):
        rep = personalization_cost(get_con(), season, cfg, value_index=vi, k_drafts=4)

    # ---- headline --------------------------------------------------------------------------
    c1, c2, c3 = st.columns(3)
    c1.metric("Benchmark value", f"{rep.benchmark_value:.0f}", help="Unconstrained, same seat & λ")
    c2.metric("Your team value", f"{rep.personalized_value:.0f}")
    c3.metric("Personalization cost", f"{rep.cost_points:.1f} pts", f"{rep.cost_pct:+.1%}",
              delta_color="inverse", help="Projected value given up vs the benchmark")

    for r in rep.secured.itertuples(index=False):
        if r.secured_frac < 1.0:
            st.warning(f"**{r.name}** was only secured in {r.secured_frac:.0%} of mock drafts — "
                       f"ADP is too early to reliably reach within your budget.")

    # ---- always show personalized beside the baseline (guardrail §8) -----------------------
    left, right = st.columns(2)
    left.subheader("Your team")
    left.dataframe(rep.personalized_roster, hide_index=True, width="stretch")
    right.subheader("Benchmark (pure value)")
    right.dataframe(rep.benchmark_roster, hide_index=True, width="stretch")

    # ---- what each preference cost ---------------------------------------------------------
    if not rep.per_constraint.empty:
        st.subheader("What each preference cost")
        show = rep.per_constraint.assign(
            cost=lambda d: d["cost_points"].round(1),
            share=lambda d: (d["cost_pct"] * 100).round(1))
        st.dataframe(show[["name", "cost", "share"]].rename(
            columns={"name": "preference", "cost": "cost (pts)", "share": "cost (% of benchmark)"}),
            hide_index=True, width="stretch")
        st.caption("Positive = the preference cost you value; negative = it happened to help. "
                   "Leave-one-out; a projected draft-day gap, not a realized-season claim.")


if __name__ == "__main__":
    main()
