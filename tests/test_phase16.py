"""Unit tests for Phase 16 — Situation-Change Beta Lab. Pure: synthetic panels + the canonical-team
aliasing; no DB/network.

Phase 16.1 mines two PIT situation flags (team change, new starting QB) through the same Phase-6
scorecard machinery. These tests cover the pieces that could go wrong independently of the DB: the
franchise-alias canonicalization (so a relocation never reads as a player changing teams), the
feature-set wiring (situation features *extend*, never replace, the frozen model), and the mining
itself (recovers a planted situation bias, rules out situation noise).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fantasy_quant.adp.panel import PHASE16_FEATURES, SITUATION_FEATURES, _canon_team
from fantasy_quant.adp.scorecard import bias_scorecard
from fantasy_quant.data import db
from fantasy_quant.features import environment
from fantasy_quant.situation import coaches, events, fingerprint


# --------------------------------------------------------------------------------------------
# canonical franchise codes — relocations/abbreviation drift collapse; FA is missing
# --------------------------------------------------------------------------------------------
def test_canon_team_collapses_relocations_and_fa():
    out = _canon_team(pd.Series(["OAK", "LV", "LA", "LAR", "STL", "SD", "KC", "FA"]))
    assert list(out[:7]) == ["LV", "LV", "LAR", "LAR", "LAR", "LAC", "KC"]
    assert pd.isna(out.iloc[7])          # FA → missing (a free agent has no team)


# --------------------------------------------------------------------------------------------
# the feature-set wiring — situation flags append to the pinned frozen model, never fold in
# --------------------------------------------------------------------------------------------
def test_phase16_features_extend_not_replace_frozen():
    assert PHASE16_FEATURES[-len(SITUATION_FEATURES):] == SITUATION_FEATURES
    assert "team_changed" in PHASE16_FEATURES and "new_starting_qb" in PHASE16_FEATURES
    # the frozen softness spec (the first traits) must still be present, unmoved
    assert "prior_games" in PHASE16_FEATURES and "rookie" in PHASE16_FEATURES


# --------------------------------------------------------------------------------------------
# the mining — recover a planted team-change bias, rule out situation noise
# --------------------------------------------------------------------------------------------
def _sit_panel(n_seasons: int = 9, depth: int = 40, planted: float = 0.0, noise: float = 15.0,
               seed: int = 0, null: bool = False, plant_on: str = "team_changed") -> pd.DataFrame:
    """A synthetic alpha panel with all four situation flags as independent random 0/1 columns.
    ``alpha`` = a season-clustered shock (0 in the null) + ``planted``×``plant_on`` + noise."""
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(2014, 2014 + n_seasons):
        shock = 0.0 if null else rng.normal(0, 5)
        for pos in ("QB", "RB", "WR", "TE"):
            for r in range(1, depth + 1):
                flags = {"team_changed": int(rng.random() < 0.15),
                         "new_starting_qb": int(rng.random() < 0.20),
                         "competition_change_roster": int(rng.random() < 0.25),
                         "competition_change_depth": int(rng.random() < 0.30)}
                alpha = shock + planted * flags[plant_on] + rng.normal(0, noise)
                rows.append({
                    "season": s, "gsis_id": f"{s}_{pos}_{r}", "name": f"{pos}{r}", "pos": pos,
                    "adp": float(r), "pos_rank": r, "adp_stdev": float(rng.uniform(1, 15)),
                    "realized_vor": 200.0 - 3 * r + alpha, "alpha": float(alpha),
                    "rookie": int(rng.random() < 0.12), "experience": float(rng.integers(1, 12)),
                    "prior_games": float(rng.integers(0, 18)),
                    "prior_ppg": float(rng.uniform(0, 20)), **flags,
                })
    return pd.DataFrame(rows)


def test_scorecard_flags_planted_team_change_bias():
    sc = bias_scorecard(_sit_panel(planted=30.0, seed=3), features=PHASE16_FEATURES, n_boot=800)
    row = sc.table.set_index("term").loc["team_changed"]
    assert row["coef"] > 12.0            # recovers the +30 planted effect (attenuated by noise)
    assert row["significant"]            # survives FDR + sign stability


def test_scorecard_flags_planted_competition_bias():
    sc = bias_scorecard(_sit_panel(planted=30.0, seed=5, plant_on="competition_change_roster"),
                        features=PHASE16_FEATURES, n_boot=800)
    row = sc.table.set_index("term").loc["competition_change_roster"]
    assert row["coef"] > 12.0
    assert row["significant"]


def test_scorecard_rules_out_situation_noise():
    sc = bias_scorecard(_sit_panel(planted=0.0, seed=4, null=True),
                        features=PHASE16_FEATURES, n_boot=800)
    tbl = sc.table.set_index("term")
    for f in SITUATION_FEATURES:
        assert not tbl.loc[f, "significant"]


# --------------------------------------------------------------------------------------------
# 16.3 / 16.3b — the playcaller reference table
# --------------------------------------------------------------------------------------------
def _coaches(rows) -> pd.DataFrame:
    """Build a table in the frozen schema from (season, team, hc, oc, pc, in_house) tuples."""
    return pd.DataFrame([{"season": s, "team": t, "head_coach": hc, "offensive_coordinator": oc,
                          "play_caller": pc, "hc_calls_plays": int(pc == hc), "in_house": ih,
                          "confidence": "high", "notes": ""}
                         for s, t, hc, oc, pc, ih in rows])[list(coaches.SCHEMA)]


def test_real_table_passes_every_structural_gate():
    """The committed reference table is the artifact 16.4 consumes — gate it directly."""
    df = coaches.load_coaches()
    coaches.assert_coaches_schema(df)
    assert (df["season"] == 2026).sum() == 32, "every 2026 team must be present"
    # whitespace is stripped on ingest (the signed-off file has trailing spaces on 5 name fields)
    for col in ("team", "head_coach", "offensive_coordinator", "play_caller"):
        assert (df[col] == df[col].str.strip()).all()
    # the table's own internal cross-reference must be free of contradictions
    assert not [f for f in coaches.move_graph_check(df) if f.startswith("HARD")]


def test_schema_gate_rejects_playcaller_who_holds_neither_job():
    df = _coaches([(2020, "CLE", "Kevin Stefanski", "Alex Van Pelt", "Somebody Else", 0)])
    with pytest.raises(AssertionError, match="neither HC nor OC"):
        coaches.assert_coaches_schema(df)


def test_schema_gate_rejects_hc_calls_plays_disagreeing_with_play_caller():
    df = _coaches([(2020, "CLE", "Kevin Stefanski", "Alex Van Pelt", "Kevin Stefanski", 0)])
    df.loc[0, "hc_calls_plays"] = 0          # the HC calls plays, but the flag says otherwise
    with pytest.raises(AssertionError, match="hc_calls_plays disagrees"):
        coaches.assert_coaches_schema(df)


def test_move_graph_flags_one_person_calling_plays_for_two_teams():
    df = _coaches([(2021, "NYJ", "Robert Saleh", "Mike LaFleur", "Mike LaFleur", 0),
                   (2021, "GB", "Matt LaFleur", "(none)", "Mike LaFleur", 0)])
    assert any(f.startswith("HARD") and "2 teams" in f for f in coaches.move_graph_check(df))


def test_move_graph_flags_in_house_contradicting_the_tables_own_history():
    """in_house=0 claims a NEW regime, but the prior season names the same play-caller."""
    schotty = "Brian Schottenheimer"
    df = _coaches([(2019, "SEA", "Pete Carroll", schotty, schotty, 1),
                   (2020, "SEA", "Pete Carroll", schotty, schotty, 0)])
    assert any(f.startswith("HARD") and "in_house=0" in f for f in coaches.move_graph_check(df))


def test_move_graph_reports_internal_promotion_as_a_note_not_an_error():
    """in_house=1 with a different prior play-caller is the DEN-2026 shape, not a contradiction."""
    df = _coaches([(2025, "DEN", "Sean Payton", "Joe Lombardi", "Sean Payton", 1),
                   (2026, "DEN", "Sean Payton", "Davis Webb", "Davis Webb", 1)])
    findings = coaches.move_graph_check(df)
    assert findings and all(f.startswith("note") for f in findings)
    assert "internal promotion" in findings[0]


def test_move_graph_flags_one_season_hole_but_not_a_multi_year_absence():
    """A single gap is suspicious; leaving a team and returning years later is not."""
    hole = _coaches([(2020, "CLE", "Kevin Stefanski", "(none)", "Kevin Stefanski", 0),
                     (2022, "CLE", "Kevin Stefanski", "(none)", "Kevin Stefanski", 1)])
    assert any("one-season hole" in f for f in coaches.move_graph_check(hole))
    away = _coaches([(2014, "NE", "Bill Belichick", "Josh McDaniels", "Josh McDaniels", 1),
                     (2025, "NE", "Mike Vrabel", "Josh McDaniels", "Josh McDaniels", 0)])
    assert not [f for f in coaches.move_graph_check(away) if "hole" in f]


def test_regimes_split_a_return_into_two_spells():
    df = _coaches([(2014, "NE", "Bill Belichick", "Josh McDaniels", "Josh McDaniels", 1),
                   (2015, "NE", "Bill Belichick", "Josh McDaniels", "Josh McDaniels", 1),
                   (2025, "NE", "Mike Vrabel", "Josh McDaniels", "Josh McDaniels", 0)])
    reg = coaches.playcaller_regimes(df).set_index("first_season")
    assert list(reg.index) == [2014, 2025]
    assert reg.loc[2014, "n_seasons"] == 2 and reg.loc[2025, "n_seasons"] == 1


def test_new_regimes_catches_external_hires_and_internal_promotions():
    df = _coaches([(2025, "DEN", "Sean Payton", "Joe Lombardi", "Sean Payton", 1),
                   (2026, "DEN", "Sean Payton", "Davis Webb", "Davis Webb", 1),      # promotion
                   (2025, "ATL", "Raheem Morris", "Zac Robinson", "Zac Robinson", 1),
                   (2026, "ATL", "Kevin Stefanski", "Tommy Rees", "Kevin Stefanski", 0),  # hire
                   (2025, "KC", "Andy Reid", "Matt Nagy", "Andy Reid", 1),
                   (2026, "KC", "Andy Reid", "Matt Nagy", "Andy Reid", 1)])          # continuity
    got = coaches.new_regimes(df, 2026).set_index("team")["trigger"].to_dict()
    assert got == {"DEN": "internal_promotion", "ATL": "external"}


def test_coverage_counts_only_prior_seasons():
    df = _coaches([(2024, "ARI", "Jonathan Gannon", "Drew Petzing", "Drew Petzing", 1),
                   (2025, "ARI", "Jonathan Gannon", "Drew Petzing", "Drew Petzing", 1),
                   (2026, "DET", "Dan Campbell", "Drew Petzing", "Drew Petzing", 0),
                   (2026, "SEA", "Mike Macdonald", "Brian Fleury", "Brian Fleury", 0)])
    cov = coaches.coverage(df, 2026).set_index("team")["prior_seasons"].to_dict()
    assert cov == {"DET": 2, "SEA": 0}      # a first-time play-caller has nothing to fingerprint


def _lineage(rows) -> pd.DataFrame:
    return pd.DataFrame([{"play_caller": pc, "season": s, "team": t, "mentor": m,
                          "learned_at": at, "learned_seasons": "2025", "role": "OC",
                          "confidence": "high", "notes": ""}
                         for pc, s, t, m, at in rows],
                        columns=list(coaches.LINEAGE_SCHEMA))


def test_real_lineage_table_covers_every_first_time_playcaller():
    """The fallback is only worth anything if it lands on a real, fingerprint-able regime."""
    df, lin = coaches.load_coaches(), coaches.load_lineage()
    src = coaches.fingerprint_source(df, 2026, lin)
    assert not (src[src["is_new_regime"]]["source"] == "none").any(), "a new regime with no prior"
    for r in lin.itertuples():
        assert (df["play_caller"] == r.mentor).any(), f"mentor {r.mentor} is not a play-caller"


def test_fingerprint_source_prefers_own_history_over_lineage():
    df = _coaches([(2024, "ARI", "Jonathan Gannon", "Drew Petzing", "Drew Petzing", 1),
                   (2025, "DET", "Dan Campbell", "John Morton", "John Morton", 0),
                   (2026, "DET", "Dan Campbell", "Drew Petzing", "Drew Petzing", 0)])
    lin = _lineage([("Drew Petzing", 2026, "DET", "Somebody Else", "ARI")])
    row = coaches.fingerprint_source(df, 2026, lin).set_index("team").loc["DET"]
    assert row["source"] == "own" and row["fingerprint_on"] == "Drew Petzing"


def test_fingerprint_source_falls_back_to_the_mentor_for_a_first_timer():
    """Doyle has never called a play; the prior is Ben Johnson's Bears, not a blank."""
    df = _coaches([(2025, "CHI", "Ben Johnson", "Declan Doyle", "Ben Johnson", 0),
                   (2025, "BAL", "John Harbaugh", "Todd Monken", "Todd Monken", 1),
                   (2026, "BAL", "Jesse Minter", "Declan Doyle", "Declan Doyle", 0)])
    lin = _lineage([("Declan Doyle", 2026, "BAL", "Ben Johnson", "CHI")])
    row = coaches.fingerprint_source(df, 2026, lin).set_index("team").loc["BAL"]
    assert row["source"] == "lineage"
    assert row["fingerprint_on"] == "Ben Johnson" and row["prior_seasons"] == 1
    assert not row["same_team"]                       # he arrives from Chicago...
    assert row["prev_play_caller"] == "Todd Monken"   # ...so continuity disagrees; report both


def test_fingerprint_source_marks_the_same_team_promotion_case():
    """DEN 2026: Payton hands the offense to his own QB coach, so lineage == team continuity."""
    df = _coaches([(2025, "DEN", "Sean Payton", "Joe Lombardi", "Sean Payton", 1),
                   (2026, "DEN", "Sean Payton", "Davis Webb", "Davis Webb", 1)])
    lin = _lineage([("Davis Webb", 2026, "DEN", "Sean Payton", "DEN")])
    row = coaches.fingerprint_source(df, 2026, lin).set_index("team").loc["DEN"]
    assert row["source"] == "lineage" and row["same_team"]
    assert row["fingerprint_on"] == row["prev_play_caller"] == "Sean Payton"


def test_fingerprint_source_reports_none_when_there_is_no_prior_at_all():
    df = _coaches([(2025, "SEA", "Mike Macdonald", "Klint Kubiak", "Klint Kubiak", 0),
                   (2026, "SEA", "Mike Macdonald", "Brian Fleury", "Brian Fleury", 1)])
    row = coaches.fingerprint_source(df, 2026, _lineage([])).set_index("team").loc["SEA"]
    assert row["source"] == "none" and pd.isna(row["fingerprint_on"])


# --------------------------------------------------------------------------------------------
# 16.5 — the derived situation-change event board
# --------------------------------------------------------------------------------------------
def _board(rows) -> pd.DataFrame:
    """An event board in the frozen schema from (player, pos, team, prev, evt, adp) tuples."""
    return pd.DataFrame([{"player": p, "position": pos, "team": t, "prev_team": pv,
                          "event_type": e, "mechanism": "unknown", "adp": adp,
                          "new_play_caller": 0, "play_caller": "X", "new_qb": 0, "qb": "Q",
                          "arrivals": "", "departures": "", "evidence": "derived",
                          "confidence": "high", "notes": ""}
                         for p, pos, t, pv, e, adp in rows],
                        columns=list(events.SCHEMA))


def test_committed_event_board_passes_its_schema_gate():
    """The real file on disk — the artifact 16.6 will render."""
    df = events.load_events()
    events.assert_events_schema(df)
    assert len(df) >= 100, "the board should be an exhaustive frame, not a tracker recap"
    assert df["team"].nunique() >= 28


def test_committed_board_covers_the_top_of_the_draft():
    """The failure that motivated deriving this file: the hand-built version had no row for the
    two highest-ADP players in the league, both of whom have a changed backfield."""
    df = events.load_events().sort_values("adp")
    assert df["adp"].min() < 5.0, "no event among the very first picks — the frame has a hole"
    tc = df[df["event_type"] == "team_change"]
    assert tc["adp"].min() < 20.0, "a first-round team change is missing"


def test_event_schema_rejects_a_self_move():
    df = _board([("A", "RB", "KC", "KC", "team_change", 10.0)])
    with pytest.raises(ValueError, match="prev_team == team"):
        events.assert_events_schema(df)


def test_event_schema_rejects_a_team_change_with_no_prior_team():
    df = _board([("A", "RB", "KC", None, "team_change", 10.0)])
    with pytest.raises(ValueError, match="no prev_team"):
        events.assert_events_schema(df)


def test_event_schema_rejects_an_unknown_event_type():
    df = _board([("A", "RB", "KC", "SEA", "vibes", 10.0)])
    with pytest.raises(ValueError, match="unknown event_type"):
        events.assert_events_schema(df)


def test_event_schema_rejects_a_duplicated_player():
    df = _board([("A", "RB", "KC", "SEA", "team_change", 10.0),
                 ("A", "RB", "KC", "SEA", "team_change", 10.0)])
    with pytest.raises(ValueError, match="twice"):
        events.assert_events_schema(df)


def test_event_schema_rejects_schema_drift():
    df = _board([("A", "RB", "KC", "SEA", "team_change", 10.0)]).drop(columns=["notes"])
    with pytest.raises(ValueError, match="schema drift"):
        events.assert_events_schema(df)


def test_room_churn_attributes_a_mover_to_both_rooms():
    """A traded player is an arrival in the room he joins and a departure from the one he left —
    that is what makes his old teammate an event."""
    moves = _board([("Mover", "RB", "KC", "SEA", "team_change", 20.0)])
    arr, dep = events._room_churn(moves, pd.DataFrame(columns=["player", "position", "prev_team"]))
    assert arr[("KC", "RB")] == ["Mover"]
    assert dep[("SEA", "RB")] == ["Mover"]


def test_room_churn_counts_a_rookie_as_an_arrival_only():
    moves = _board([("Rook", "WR", "NO", None, "new_to_league", 80.0)])
    arr, dep = events._room_churn(moves, pd.DataFrame(columns=["player", "position", "prev_team"]))
    assert arr[("NO", "WR")] == ["Rook"]
    assert dep == {}


def test_room_churn_counts_a_producer_who_left_the_draftable_pool():
    """Retirements and unsigned veterans vacate opportunity exactly like a trade does."""
    gone = pd.DataFrame([{"player": "Retiree", "position": "RB", "prev_team": "GB"}])
    arr, dep = events._room_churn(_board([]), gone)
    assert dep[("GB", "RB")] == ["Retiree"]
    assert arr == {}


def test_merge_annotations_overlays_research_without_touching_derived_facts():
    derived = _board([("A.J. Brown", "WR", "NE", "PHI", "team_change", 13.6)])
    ann = pd.DataFrame([{"player": "A.J. Brown", "mechanism": "trade", "confidence": "med",
                         "notes": "terms here"}])
    out, orphan = events.merge_annotations(derived, ann)
    row = out.iloc[0]
    assert row["mechanism"] == "trade" and row["confidence"] == "med"
    assert row["notes"] == "terms here" and row["evidence"] == "derived+web"
    assert row["team"] == "NE" and row["prev_team"] == "PHI"   # derivation still owns who/where
    assert orphan == []


def test_merge_annotations_reports_research_the_derivation_did_not_confirm():
    """An annotation matching no derived row is a finding, not something to drop silently."""
    derived = _board([("Real", "WR", "NE", "PHI", "team_change", 13.6)])
    ann = pd.DataFrame([{"player": "Ghost", "mechanism": "trade", "confidence": "low",
                         "notes": "stale"}])
    out, orphan = events.merge_annotations(derived, ann)
    assert orphan == ["Ghost"]
    assert len(out) == 1 and out.iloc[0]["evidence"] == "derived"


def test_merge_annotations_leaves_blank_annotation_fields_alone():
    derived = _board([("A", "WR", "NE", "PHI", "team_change", 13.6)])
    ann = pd.DataFrame([{"player": "A", "mechanism": "", "confidence": "low", "notes": "  "}])
    out, _ = events.merge_annotations(derived, ann)
    assert out.iloc[0]["mechanism"] == "unknown"   # empty must not erase the derived default
    assert out.iloc[0]["notes"] == ""
    assert out.iloc[0]["confidence"] == "low"


# ================================================================================================
# Phase 16.4 — scheme fingerprints + transport
# ================================================================================================
def _tend(rows) -> pd.DataFrame:
    """Synthetic (team, season, week) tendencies: rows of (season, team, week, pass, rush)."""
    out = []
    for season, team, week, ps, rs in rows:
        out.append({"team": team, "season": season, "week": week,
                    "pass_plays": ps, "rush_plays": rs,
                    "ed_pass": ps // 2, "ed_plays": (ps + rs) // 2,
                    "rz_pass": ps // 5, "rz_rush": rs // 5,
                    "air_yards": ps * 8.0, "pass_atts": ps})
    return pd.DataFrame(out)


def _usage(rows) -> pd.DataFrame:
    """Synthetic player-weeks: rows of (season, team, week, gsis, pos, targets, carries)."""
    return pd.DataFrame([
        {"gsis_id": g, "player": g, "position": p, "team": t, "season": s, "week": w,
         "targets": tg, "carries": ca}
        for s, t, w, g, p, tg, ca in rows])


# --- week selection -----------------------------------------------------------------------------
def test_resolve_weeks_counts_played_weeks_not_calendar_weeks():
    """A bye must not shift a boundary: 'first 9' means nine games, not 'through week 9'."""
    played = [1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12]        # week 8 is the bye
    assert fingerprint.resolve_weeks(("first", 9), played) == [1, 2, 3, 4, 5, 6, 7, 9, 10]
    assert fingerprint.resolve_weeks(("last", 3), played) == [10, 11, 12]
    assert fingerprint.resolve_weeks(("weeks", 9, 12), played) == [9, 10, 11, 12]


def test_unresolved_partial_regime_is_dropped_not_guessed():
    t = _tend([(2021, "CAR", w, 30, 20) for w in range(1, 18)])
    assert fingerprint.regime_season_weeks(t, 2021, "CAR", "Joe Brady") is None
    # the same team-season under a different caller is a normal, complete regime
    assert len(fingerprint.regime_season_weeks(t, 2021, "CAR", "Someone Else")) == 17


def test_partial_window_keys_all_exist_in_the_real_coaches_table():
    """A typo'd key would silently do nothing — the row would be used whole and look fine."""
    df = coaches.load_coaches()
    have = {(int(r.season), str(r.team), str(r.play_caller)) for r in df.itertuples()}
    for key in (*fingerprint.PARTIAL_WEEKS, *fingerprint.UNRESOLVED_PARTIAL):
        assert key in have, f"{key} is not a row in reference/coaches.csv"


def test_coverage_gate_catches_a_silent_join_failure():
    """The LA/LAR regression guard: a dropped regime with no reason is a join bug, not a coach."""
    rst = pd.DataFrame([{"play_caller": "X", "team": "LAR", "season": 2018, "weeks": None,
                         "n_weeks": 0, "partial": False, "dropped": True, "drop_reason": ""}])
    with pytest.raises(AssertionError, match="did not join"):
        fingerprint.assert_regime_coverage(rst)
    rst.loc[0, "drop_reason"] = "stated reason"
    fingerprint.assert_regime_coverage(rst)          # explained drops are fine


# --- the profile --------------------------------------------------------------------------------
def test_team_season_profile_computes_shares_and_concentration():
    t = _tend([(2020, "KC", w, 40, 20) for w in (1, 2)])
    u = _usage([(2020, "KC", w, g, p, tg, ca) for w in (1, 2) for g, p, tg, ca in
                [("wr1", "WR", 10, 0), ("wr2", "WR", 6, 0), ("wr3", "WR", 4, 0),
                 ("te1", "TE", 5, 0), ("rb1", "RB", 5, 15), ("rb2", "RB", 0, 5)]])
    p = fingerprint.team_season_profile(t, u, 2020, "KC")
    assert p["pass_rate"] == pytest.approx(40 / 60)
    assert p["plays_pg"] == pytest.approx(60.0)
    assert p["team_adot"] == pytest.approx(8.0)
    assert p["wr1_tgt_share"] == pytest.approx(10 / 30)      # 30 team targets per week
    assert p["wr2_tgt_share"] == pytest.approx(6 / 30)
    assert p["rb1_carry_share"] == pytest.approx(15 / 20)
    assert p["rb_tgt_share"] == pytest.approx(5 / 30)
    # HHI of target shares: (10..6,4,5,5)/30 squared and summed
    assert p["carry_hhi"] == pytest.approx((15 / 20) ** 2 + (5 / 20) ** 2)
    assert 0 < p["tgt_hhi"] <= 1


def test_profile_restricted_to_a_window_sees_only_those_weeks():
    """The whole point of PARTIAL_WEEKS: a coach is scored on his own games, not his successor's."""
    t = _tend([(2020, "CHI", 1, 40, 10), (2020, "CHI", 2, 10, 40)])
    u = _usage([(2020, "CHI", 1, "wr1", "WR", 10, 0), (2020, "CHI", 2, "wr1", "WR", 1, 0),
                (2020, "CHI", 1, "rb1", "RB", 0, 10), (2020, "CHI", 2, "rb1", "RB", 0, 40)])
    whole = fingerprint.team_season_profile(t, u, 2020, "CHI")
    first = fingerprint.team_season_profile(t, u, 2020, "CHI", weeks=[1])
    assert first["pass_rate"] == pytest.approx(0.8) and whole["pass_rate"] == pytest.approx(0.5)
    assert first["weeks"] == 1.0 and whole["weeks"] == 2.0


# --- shrinkage ----------------------------------------------------------------------------------
def _rp(n_by_caller: dict[str, int], value: float = 2.0) -> pd.DataFrame:
    rows = []
    for pc, n in n_by_caller.items():
        for i in range(n):
            r = {"play_caller": pc, "team": "AAA", "season": 2014 + i,
                 "partial": False, "n_weeks": 17}
            for c in fingerprint.METRICS:
                r[c] = value + (0.1 if i % 2 else -0.1)      # a little within-caller noise
            rows.append(r)
    return pd.DataFrame(rows)


def test_shrinkage_pulls_toward_the_league_and_never_overshoots():
    fp = fingerprint.fingerprints(_rp({"Short": 1, "Long": 12}))
    fingerprint.assert_fingerprints_sane(fp)
    for c in fingerprint.METRICS:
        for _, row in fp.iterrows():
            assert abs(row[c]) <= abs(row[f"{c}_raw"]) + 1e-9
            assert 0.0 <= row[f"{c}_w"] <= 1.0


def test_a_longer_tenure_keeps_more_of_its_own_signal():
    fp = fingerprint.fingerprints(_rp({"Short": 1, "Long": 12})).set_index("play_caller")
    for c in fingerprint.METRICS:
        assert fp.at["Long", f"{c}_w"] > fp.at["Short", f"{c}_w"]
        assert abs(fp.at["Long", c]) > abs(fp.at["Short", c])


def test_fingerprints_can_be_grouped_per_spell_instead_of_per_caller():
    rp = _rp({"A": 2})
    rp.loc[1, "team"] = "BBB"
    assert len(fingerprint.fingerprints(rp)) == 1
    assert len(fingerprint.fingerprints(rp, by=("play_caller", "team"))) == 2


# --- transport ----------------------------------------------------------------------------------
def _src(rows) -> pd.DataFrame:
    """rows of (team, play_caller, source, fingerprint_on, same_team, prev_play_caller)."""
    df = pd.DataFrame([
        {"team": t, "play_caller": pc, "source": s, "fingerprint_on": on, "prior_seasons": 3,
         "same_team": st, "prev_play_caller": prev, "is_new_regime": True}
        for t, pc, s, on, st, prev in rows])
    df["same_team"] = df["same_team"].astype("boolean")
    return df


def test_transport_reports_both_priors_only_where_they_disagree():
    fp = fingerprint.fingerprints(_rp({"Mentor": 4, "Outgoing": 4}))
    zs = pd.DataFrame([{"season": 2025, "team": "BAL", **{c: 0.0 for c in fingerprint.METRICS}},
                       {"season": 2025, "team": "DEN", **{c: 0.0 for c in fingerprint.METRICS}}])
    src = _src([("BAL", "Rookie", "lineage", "Mentor", False, "Outgoing"),
                ("DEN", "Promoted", "lineage", "Mentor", True, "Mentor")])
    tr = fingerprint.transport(fp, zs, src, 2026).set_index("team")
    assert tr.at["BAL", "alt_prior_on"] == "Outgoing"     # lineage ≠ continuity → two readings
    assert pd.isna(tr.at["DEN", "alt_prior_on"])          # same-building promotion → one reading


def test_transport_stays_silent_for_a_team_with_no_source():
    fp = fingerprint.fingerprints(_rp({"Someone": 3}))
    zs = pd.DataFrame([{"season": 2025, "team": "XXX", **{c: 0.0 for c in fingerprint.METRICS}}])
    src = _src([("XXX", "Nobody", "none", None, None, "Prev")])
    tr = fingerprint.transport(fp, zs, src, 2026)
    assert not tr.iloc[0]["fingerprinted"]
    assert np.isnan(tr.iloc[0]["pass_rate_in"])
    fingerprint.assert_transport_honest(tr, src)          # silence is the correct behaviour


def test_transport_gate_rejects_a_fingerprint_without_a_source():
    src = _src([("XXX", "Nobody", "none", None, None, "Prev")])
    tr = pd.DataFrame([{"team": "XXX", "source": "none", "fingerprinted": True}])
    with pytest.raises(AssertionError, match="no source"):
        fingerprint.assert_transport_honest(tr, src)


# --- the player board ---------------------------------------------------------------------------
class _FakeCon:
    """Stand-in for the DuckDB connection: one canned ADP board."""
    def __init__(self, board):
        self._board = board

    def execute(self, sql, params=None):
        self._df = self._board
        return self

    def df(self):
        return self._df


def test_player_board_delta_splits_exactly_into_reversion_plus_scheme():
    """The honesty identity — a reader must be able to see how much of a move is the new coach."""
    board = pd.DataFrame([{"gsis_id": "g1", "player": "Star WR", "position": "WR",
                           "team": "BAL", "adp": 12.0}])
    fp = fingerprint.fingerprints(_rp({"Mentor": 4}))
    prof = pd.DataFrame([{"season": 2025, "team": "BAL",
                          **{c: 0.30 for c in fingerprint.METRICS}}])
    mom = pd.DataFrame([{"season": 2025,
                         **{f"{c}_mean": 0.22 for c in fingerprint.METRICS},
                         **{f"{c}_sd": 0.05 for c in fingerprint.METRICS}}])
    tr = pd.DataFrame([{"team": "BAL", "play_caller": "Rookie", "source": "lineage",
                        "fingerprint_on": "Mentor", "prior_seasons": 4, "fingerprinted": True,
                        "alt_prior_on": "Outgoing"}])
    pb = fingerprint.player_board(_FakeCon(board), tr, fp, prof, mom, 2026)
    assert len(pb) == 1
    row = pb.iloc[0]
    assert row["delta_pp"] == pytest.approx(row["reversion_pp"] + row["scheme_pp"])
    assert row["share_prev"] == pytest.approx(0.30)       # what the team actually did
    assert row["share_league"] == pytest.approx(0.22)     # where any hire regresses it
    assert row["multiplier"] == pytest.approx(row["share_implied"] / row["share_prev"])
    assert row["slot_metric"] == "wr1_tgt_share"          # ADP rank 1 at WR → the WR1 slot


def test_player_board_skips_slots_the_fingerprint_does_not_model():
    """QBs and a fourth receiver have no slot metric — they must be omitted, not defaulted."""
    board = pd.DataFrame([{"gsis_id": "q", "player": "QB", "position": "QB",
                           "team": "BAL", "adp": 30.0}])
    fp = fingerprint.fingerprints(_rp({"Mentor": 4}))
    prof = pd.DataFrame([{"season": 2025, "team": "BAL",
                          **{c: 0.30 for c in fingerprint.METRICS}}])
    mom = pd.DataFrame([{"season": 2025, **{f"{c}_mean": 0.22 for c in fingerprint.METRICS},
                         **{f"{c}_sd": 0.05 for c in fingerprint.METRICS}}])
    tr = pd.DataFrame([{"team": "BAL", "play_caller": "R", "source": "own",
                        "fingerprint_on": "Mentor", "prior_seasons": 4, "fingerprinted": True,
                        "alt_prior_on": pd.NA}])
    assert fingerprint.player_board(_FakeCon(board), tr, fp, prof, mom, 2026).empty


def test_profile_reconciles_with_the_phase3_environment_feature():
    """16.4 re-derives tendencies at week grain so partial regimes can be cut out. The definitions
    must still be the Phase-3.4 ones — an unrestricted team-season has to agree exactly, or the
    fingerprints are quietly measuring something else than the rest of the project."""
    con = db.connect(":memory:")
    con.execute("CREATE TABLE pbp (season INT, week INT, posteam VARCHAR, season_type VARCHAR, "
                "pass INT, rush INT, down INT, yardline_100 INT, air_yards DOUBLE, "
                "pass_attempt INT, qb_epa DOUBLE, epa DOUBLE)")
    rows = []
    for wk in range(1, 5):
        for i in range(30):
            rows.append((2020, wk, "KC", "REG", 1, 0, 1 + i % 3, 50, 8.0, 1, 0.1, 0.1))
        for i in range(20):
            rows.append((2020, wk, "KC", "REG", 0, 1, 1 + i % 3, 50, None, 0, 0.0, 0.05))
    con.executemany("INSERT INTO pbp VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    con.execute("CREATE TABLE game_lines (season INT, game_type VARCHAR, home_team VARCHAR, "
                "away_team VARCHAR, home_score INT, away_score INT, "
                "home_implied_total DOUBLE, away_implied_total DOUBLE)")
    # environment_features asserts its output is finite, so KC needs a scoring row to exist
    con.executemany("INSERT INTO game_lines VALUES (?,?,?,?,?,?,?,?)",
                    [(2020, "REG", "KC", "DEN", 27, 17, 26.5, 20.5)])
    con.execute("CREATE TABLE weekly (gsis_id VARCHAR, player_display_name VARCHAR, "
                "position VARCHAR, recent_team VARCHAR, season INT, week INT, "
                "season_type VARCHAR, targets INT, carries INT)")
    con.executemany("INSERT INTO weekly VALUES (?,?,?,?,?,?,?,?,?)",
                    [("w1", "W One", "WR", "KC", 2020, wk, "REG", 6, 0) for wk in range(1, 5)])

    env = environment.environment_features(con).set_index("team")
    tend, usage = fingerprint.team_week_tendencies(con), fingerprint.player_week_usage(con)
    prof = fingerprint.team_season_profile(tend, usage, 2020, "KC")
    for metric in ("pass_rate", "early_down_pass_rate", "plays_pg"):
        assert prof[metric] == pytest.approx(float(env.at["KC", metric])), metric
    con.close()
