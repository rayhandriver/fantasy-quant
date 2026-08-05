"""Session DATA-2 (Phase 0.13) — offline unit tests. No network, no live store.

★ The recurring method of this repo, applied to a detector: **assert the control can produce a
known difference before trusting it to show none** (T31). So the tests below plant a sentinel and
require it to be found, plant a *genuine* backfill and require it NOT to be, and — for the gate —
show the old whole-table instrument passing on the very data the new per-season one fails.

A gate that has never been seen to fail is a comment with a function signature.
"""

from __future__ import annotations

import duckdb
import pandas as pd
import pytest

from fantasy_quant.data import breaks, validate


def cell(season: int, null_share: float, shares: dict[str, float],
         table: str = "t", column: str = "c", n_rows: int = 10_000) -> breaks.ColumnSeason:
    status = breaks.STATUS_ABSENT if not shares else breaks.STATUS_OBSERVED
    return breaks.ColumnSeason(table, column, season, n_rows, null_share, status, None, shares)


# --------------------------------------------------------------------------------------------
# B1 — the detector as a control
# --------------------------------------------------------------------------------------------
def test_detects_a_planted_null_to_sentinel_break():
    """The T50 shape: mass leaves NULL and lands entirely on one in-domain value."""
    series = [
        cell(2021, 0.60, {"1": 0.20, "2": 0.20}),
        cell(2022, 0.60, {"1": 0.20, "2": 0.20}),
        cell(2023, 0.00, {"0": 0.60, "1": 0.20, "2": 0.20}),
    ]
    found = breaks.detect_breaks(series)
    assert len(found) == 1
    b = found[0]
    assert b.kind == "null_to_sentinel"
    assert b.season == 2023
    assert b.value == "0"
    assert abs(b.residual) < 0.01      # mass conserved exactly


def test_ignores_a_genuine_backfill():
    """Coverage doubles at the same season — but spreads across many values, so it is real.

    This is the negative control, and it is the whole reason the detector keys on *conservation*
    rather than on the null share alone. Without it the gate fires on every backfill and gets
    switched off, which is how a gate stops protecting anything.
    """
    series = [
        cell(2021, 0.60, {"a": 0.10, "b": 0.10, "c": 0.10, "d": 0.10}),
        cell(2022, 0.10, {"a": 0.22, "b": 0.23, "c": 0.22, "d": 0.23}),
    ]
    assert breaks.detect_breaks(series) == []


def test_ignores_a_pure_trend():
    """The distribution moves a lot; the null share does not. That is football, not encoding."""
    series = [
        cell(2021, 0.30, {"man": 0.50, "zone": 0.20}),
        cell(2022, 0.30, {"man": 0.15, "zone": 0.55}),
    ]
    assert breaks.detect_breaks(series) == []


def test_a_floor_is_reported_as_appears_not_as_a_sentinel():
    series = [
        cell(2016, 1.0, {}),
        cell(2017, 1.0, {}),
        cell(2018, 0.62, {"MAN": 0.15, "ZONE": 0.23}),
    ]
    found = breaks.detect_breaks(series)
    assert [b.kind for b in found] == ["appears"]
    assert found[0].season == 2018
    assert found[0].kind not in breaks.BREAKING_KINDS   # a floor is news, not a defect


def test_a_trace_populated_season_is_not_a_floor():
    """pbp's rare-event columns first carry a row whenever that rare event first happened.

    Two non-NULL rows in 400,000 is a fact about football, not about the feed, and treating it as
    a floor produced ~30 spurious breaks before `MIN_PRESENCE` existed.
    """
    series = [
        cell(2015, 1.0, {}),
        cell(2016, 1.0 - 0.000005, {"x": 0.000005}),
        cell(2017, 1.0, {}),
    ]
    assert breaks.detect_breaks(series) == []


# --------------------------------------------------------------------------------------------
# the map's two questions
# --------------------------------------------------------------------------------------------
@pytest.fixture
def synth_con():
    """A table carrying a planted null->sentinel break at 2021."""
    def value(season: int, i: int):
        if i % 10 >= 4:
            return i % 7
        return None if season < 2021 else -1

    con = duckdb.connect(":memory:")
    rows = [{"season": season, "c": value(season, i)}
            for season in range(2018, 2024) for i in range(500)]
    con.register("t", pd.DataFrame(rows))
    con.execute("create table synth as select * from t")
    return con


def test_build_break_map_marks_the_sentinel_seasons(synth_con):
    bm = breaks.build_break_map(synth_con, tables=["synth"], max_season=None)
    assert bm.sentinel_seasons("synth", "c") == [2021, 2022, 2023]
    assert bm.status("synth", "c", 2020) == breaks.STATUS_OBSERVED
    assert bm.status("synth", "c", 2021) == breaks.STATUS_SENTINEL
    # ⚠ "-1.0", not "-1": a nullable integer column is float-typed before the varchar cast, so the
    # sentinel's string form carries the decimal. Pinned deliberately — the same gotcha put "0"
    # rather than "0.0" in the first draft of KNOWN_BREAKS, where it would have silently matched
    # nothing. The probe and `sentinel_exclusion_sql` cast identically, so the round trip holds.
    assert bm.sentinel_value("synth", "c", 2021) == "-1.0"


def test_sentinel_exclusion_sql_removes_only_the_sentinel_seasons(synth_con):
    bm = breaks.build_break_map(synth_con, tables=["synth"], max_season=None)
    excl = breaks.sentinel_exclusion_sql(bm, "synth", "c")
    kept = synth_con.execute(
        f"select season, count(*) from synth where c is not null and {excl} group by 1 order by 1"
    ).fetchall()
    # 300 real values a season throughout; the 200 planted sentinels drop out from 2021 only
    assert dict(kept) == {2018: 300, 2019: 300, 2020: 300, 2021: 300, 2022: 300, 2023: 300}


def test_sentinel_exclusion_sql_is_a_noop_for_an_unaffected_column(synth_con):
    bm = breaks.build_break_map(synth_con, tables=["synth"], max_season=None)
    assert breaks.sentinel_exclusion_sql(bm, "synth", "no_such_column") == "true"


def test_max_season_keeps_the_live_season_out_of_the_map(synth_con):
    bm = breaks.build_break_map(synth_con, tables=["synth"], max_season=2022)
    assert max(c.season for c in bm.cells) == 2022


# --------------------------------------------------------------------------------------------
# T50 — the gate, and the proof that the old one is blind to what the new one catches
# --------------------------------------------------------------------------------------------
def test_whole_table_gate_is_blind_to_a_mid_history_collapse():
    """★ Prove the trap is real FIRST (B2's discipline, at unit scale).

    `pfr_rec.td` is fully populated for six seasons and empty for two. Averaged over the whole
    table that is 0.74 — an unremarkable number — so the drop-detecting whole-table gate passes.
    """
    base = {"pfr_rec": {"td": 0.7448}}
    now = {"pfr_rec": {"td": 0.7448}}
    assert validate.fill_rate_gate(None, now, base)["passed"]


def test_per_season_gate_catches_what_the_whole_table_gate_missed():
    base = {"pfr_rec": {"td": {2022: 1.0, 2023: 1.0, 2024: 1.0}}}
    now = {"pfr_rec": {"td": {2022: 1.0, 2023: 1.0, 2024: 0.0}}}
    gate = validate.fill_rate_gate_by_season(now, base)
    assert not gate["passed"]
    assert gate["moved"][0]["season"] == 2024
    assert gate["moved"][0]["direction"] == "drop"


def test_per_season_gate_is_two_sided():
    """A *rise* is the null->sentinel signature, and the old gate applauded it by construction."""
    base = {"participation": {"was_pressure": {2022: 0.38, 2023: 0.38}}}
    now = {"participation": {"was_pressure": {2022: 0.38, 2023: 1.00}}}
    gate = validate.fill_rate_gate_by_season(now, base)
    assert not gate["passed"]
    assert gate["moved"][0]["direction"] == "rise"


def test_per_season_gate_forgives_a_move_a_classified_break_explains():
    class _Map:
        breaks = [breaks.Break("participation", "was_pressure", 2023,
                               "null_to_sentinel", "false", 0.62, 0.0, 0.27, 0.85, -0.04)]

    base = {"participation": {"was_pressure": {2022: 0.38, 2023: 0.38}}}
    now = {"participation": {"was_pressure": {2022: 0.38, 2023: 1.00}}}
    assert validate.fill_rate_gate_by_season(now, base, break_map=_Map())["passed"]


def test_per_season_gate_says_so_when_it_has_no_baseline():
    gate = validate.fill_rate_gate_by_season({"t": {"c": {2020: 0.5}}}, None)
    assert gate["passed"] and "baseline" in gate["status"]


def test_encoding_gate_fails_on_an_unclassified_break():
    unknown = breaks.Break("mystery_table", "mystery_col", 2023,
                           "null_to_sentinel", "0", 0.60, 0.0, 0.0, 0.60, 0.0)
    bm = breaks.BreakMap([], [unknown])
    gate = validate.encoding_break_gate(None, bm)
    assert not gate["passed"]
    assert "mystery_table" in gate["unclassified"][0]


def test_encoding_gate_fails_on_a_stale_classification():
    """A registered break the probe no longer finds is a claim that stopped being true."""
    bm = breaks.BreakMap([], [])
    gate = validate.encoding_break_gate(None, bm)
    assert not gate["passed"]
    assert gate["stale_classifications"]


def test_every_known_break_names_a_kind_the_gate_can_act_on():
    for k in breaks.KNOWN_BREAKS:
        assert k["kind"] in breaks.BREAKING_KINDS, k
        assert k.get("note"), k


# --------------------------------------------------------------------------------------------
# 0.13.1 — the defensive regime table (T48)
# --------------------------------------------------------------------------------------------
def _row(**kw):
    base = {"season": 2026, "team": "TB", "head_coach": "Todd Bowles",
            "defensive_coordinator": "(none)", "play_caller": "Todd Bowles",
            "hc_calls_defense": 1, "in_house": 1, "confidence": "high", "notes": ""}
    return {**base, **kw}


def test_the_shipped_defensive_table_passes_its_own_gate():
    from fantasy_quant.situation import defense_coaches as dc

    df = dc.load_defense_coaches()
    dc.assert_defense_schema(df)
    assert df[df["season"] == 2026]["team"].nunique() == 32
    # The historical half is what 0.13.8 actually fingerprints; asserting only 2026 would let the
    # table silently revert to the pre-0.13.1b state and still pass.
    assert df["season"].min() == 2014 and len(df) > 100


def test_schema_gate_rejects_a_playcaller_who_is_neither_hc_nor_dc():
    """The row would name nobody — the failure the offensive table's Monken case taught.

    Note the coordinator is a REAL name here. With the ``(none)`` sentinel the same shape is
    legal — see the title-less test below — so this fixture has to carry a coordinator for the
    rule to be under test at all.
    """
    from fantasy_quant.situation import defense_coaches as dc

    bad = pd.DataFrame([_row(defensive_coordinator="Anthony Weaver",
                             play_caller="Some Other Person", hc_calls_defense=0)])
    with pytest.raises(AssertionError, match="neither HC nor DC"):
        dc.assert_defense_schema(bad[list(dc.SCHEMA)])


def test_schema_gate_allows_a_titleless_playcaller_when_there_is_no_coordinator():
    """NE 2018: no coordinator on staff, and the linebackers coach called the defense.

    ★ The rule that rejects a third name has to make room for the case where the second name does
    not exist — otherwise the table can only record this regime by inventing a title for it, and
    an invented title is precisely what the Monken rule exists to keep out.
    """
    from fantasy_quant.situation import defense_coaches as dc

    ok = pd.DataFrame([_row(season=2018, team="NE", head_coach="Bill Belichick",
                            defensive_coordinator=dc.NO_COORDINATOR,
                            play_caller="Brian Flores", hc_calls_defense=0, in_house=1)])
    dc.assert_defense_schema(ok[list(dc.SCHEMA)])  # must not raise

    shipped = dc.load_defense_coaches()
    ne18 = shipped[(shipped["season"] == 2018) & (shipped["team"] == "NE")]
    assert len(ne18) == 1
    assert ne18.iloc[0]["play_caller"] == "Brian Flores"
    assert ne18.iloc[0]["defensive_coordinator"] == dc.NO_COORDINATOR


def test_schema_gate_rejects_a_flag_that_disagrees_with_the_playcaller():
    """A wrong flag is worse than a missing one, because a consumer will believe it."""
    from fantasy_quant.situation import defense_coaches as dc

    bad = pd.DataFrame([_row(play_caller="Anthony Weaver",
                             defensive_coordinator="Anthony Weaver",
                             hc_calls_defense=1)])
    with pytest.raises(AssertionError, match="disagrees"):
        dc.assert_defense_schema(bad[list(dc.SCHEMA)])


def test_move_graph_flags_one_person_calling_two_defenses():
    from fantasy_quant.situation import defense_coaches as dc

    df = pd.DataFrame([_row(team="TB"), _row(team="ATL", head_coach="Todd Bowles")])
    findings = dc.move_graph_check(df[list(dc.SCHEMA)])
    assert any(f.startswith("HARD:") and "two teams" in f or "2 teams" in f for f in findings)


def test_coverage_labels_a_first_time_playcaller():
    """The done-bar is 'the first-timers are labelled', not 'everyone has history'."""
    from fantasy_quant.situation import defense_coaches as dc

    df = pd.DataFrame([
        _row(season=2024, team="TB"),
        _row(season=2026, team="ATL", head_coach="New Person", play_caller="New Person"),
        _row(season=2026, team="TB"),
    ])
    cov = dc.coverage(df[list(dc.SCHEMA)], 2026)
    first = dict(zip(cov["team"], cov["first_time"], strict=True))
    assert first["ATL"] is True or first["ATL"] == True   # noqa: E712
    assert not first["TB"]


# --------------------------------------------------------------------------------------------
# 0.13.1 — the audit as a control, and the regimes the research DELETED
# --------------------------------------------------------------------------------------------
def test_pbp_audit_fires_on_a_planted_wrong_head_coach():
    """★ The shipped table's audit returns EMPTY, which is only meaningful if it can be non-empty.

    The step reports that audit as vacuous-by-construction (head_coach is auto-filled from the
    same scaffold it is checked against), so this test is where the instrument is shown to work:
    plant a head coach who did not coach that team that season and require a MISMATCH verdict.
    """
    from fantasy_quant.situation.coaches import audit_against_pbp

    scaffold = pd.DataFrame([{"season": 2019, "team": "ATL", "head_coach": "Dan Quinn",
                              "games": 16, "interim": ""}])
    good = pd.DataFrame([_row(season=2019, team="ATL", head_coach="Dan Quinn",
                              defensive_coordinator="Dan Quinn", play_caller="Dan Quinn")])
    assert audit_against_pbp(good, scaffold).empty

    planted = pd.DataFrame([_row(season=2019, team="ATL", head_coach="Kyle Shanahan",
                                 defensive_coordinator="Kyle Shanahan",
                                 play_caller="Kyle Shanahan")])
    out = audit_against_pbp(planted, scaffold)
    assert len(out) == 1 and out.iloc[0]["verdict"] == "MISMATCH"


@pytest.mark.parametrize(("season", "team", "absent_caller"), [
    (2016, "NYJ", "Todd Bowles"),     # Kacy Rodgers called it
    (2022, "NYJ", "Robert Saleh"),    # Ulbrich called it, all four seasons
    (2024, "ATL", "Raheem Morris"),   # Jimmy Lake called it
    (2024, "ARI", "Jonathan Gannon"),  # Rallis called it, with "complete faith"
    (2025, "NYJ", "Aaron Glenn"),     # Glenn said publicly he would not call plays
    (2021, "MIA", "Brian Flores"),    # Josh Boyer had full control
    (2025, "WAS", "Dan Quinn"),       # Whitt's majority; the split season is DROPPED
])
def test_a_head_coaching_tenure_is_not_a_playcalling_regime(season, team, absent_caller):
    """★ Seven rows the research DELETED. Each is a defensive head coach whose team-season a
    title-keyed (or intuition-keyed) table would have credited to him, and did not."""
    from fantasy_quant.situation import defense_coaches as dc

    df = dc.load_defense_coaches()
    hit = df[(df["season"] == season) & (df["team"] == team)
             & (df["play_caller"] == absent_caller)]
    assert hit.empty, f"{absent_caller} should have no {team} {season} play-calling row"


def test_lineage_mentors_are_themselves_playcallers_in_the_table():
    """A fallback that resolves to nobody is worse than no fallback: 0.13.8 would silently get
    an empty prior instead of staying silent. Three 2026 first-timers have no mentor row for
    exactly this reason and must NOT be given one."""
    from fantasy_quant.situation import defense_coaches as dc

    coaches = dc.load_defense_coaches()
    lineage = dc.load_defense_lineage()
    dc.assert_lineage_schema(lineage, coaches)

    cov = dc.coverage(coaches, 2026)
    first_timers = set(cov[cov["first_time"]]["play_caller"])
    assert set(lineage["play_caller"]) <= first_timers, "a mentor row for someone with own history"
    assert first_timers - set(lineage["play_caller"]) == {"Chris O'Leary", "Sean Duggan",
                                                          "Zak Kuhr"}


# --------------------------------------------------------------------------------------------
# 0.13.2 — the one canonical grouping function, and what it must not throw away
# --------------------------------------------------------------------------------------------
def test_both_defense_personnel_encodings_parse_to_the_same_buckets():
    """★ `defense_personnel` is TWO encodings, not one. A parser that reads only the aggregated
    form drops the position-level form silently — the rows are not missing, they are shaped
    differently, which is the harder failure to see."""
    from fantasy_quant.situation.defense_scheme import parse_defense_personnel as p

    aggregated = p("4 DL, 2 LB, 5 DB")
    detailed = p("3 CB, 2 DE, 2 DT, 1 FS, 1 OLB, 1 LB, 1 SS")
    assert (aggregated["dl"], aggregated["lb"], aggregated["db"]) == (4, 2, 5)
    assert (detailed["dl"], detailed["lb"], detailed["db"]) == (4, 2, 5)
    assert aggregated["package"] == detailed["package"] == "nickel"


def test_a_two_way_player_does_not_disqualify_the_snap():
    """★ JAX 2025: `2 CB, 2 DE, 2 DT, 1 FS, 1 MLB, 1 OLB, 1 SS, 1 WR` is an ordinary defensive
    snap with a WR-listed cornerback on the field. Treating an offensive token as proof of a kick
    unit deleted 55 of 78 defensive snaps for that team-week. `other` is provenance, never a filter.
    """
    from fantasy_quant.situation.defense_scheme import parse_defense_personnel as p

    snap = p("2 CB, 2 DE, 2 DT, 1 FS, 1 MLB, 1 OLB, 1 SS, 1 WR")
    assert snap["other"] == 1 and snap["n_men"] == 11
    assert snap["db"] == 4 and snap["package"] == "base"   # still a classifiable defensive snap


@pytest.mark.parametrize(("text", "package"), [
    ("4 DL, 3 LB, 4 DB", "base"),
    ("4 DL, 2 LB, 5 DB", "nickel"),
    ("4 DL, 1 LB, 6 DB", "dime"),
    ("3 DL, 1 LB, 7 DB", "quarter"),
    ("5 DL, 3 LB, 3 DB", "heavy"),
])
def test_package_is_keyed_to_the_secondary(text, package):
    """Substitution happens in the secondary, so DB count is the primary axis — the league's own
    vocabulary rather than a naming we invented."""
    from fantasy_quant.situation.defense_scheme import parse_defense_personnel as p

    assert p(text)["package"] == package


def test_empty_and_garbage_personnel_are_not_silently_classified():
    from fantasy_quant.situation.defense_scheme import parse_defense_personnel as p

    for text in (None, "", "   ", "no digits here"):
        out = p(text)
        assert out["package"] is None and out["n_men"] == 0


# --------------------------------------------------------------------------------------------
# 0.13.3 — three tiers, kept apart
# --------------------------------------------------------------------------------------------
def test_the_charted_shell_floor_raises_instead_of_returning_zeros():
    """★ B6: a prose warning is not a guard (UI-1's lesson 4). Asking for a 2016 coverage shell
    must RAISE and name 2018 — returning zeros reads as 'this team never played Cover 3'."""
    from fantasy_quant.data import breaks
    from fantasy_quant.situation import coverage as cov

    class _BM:
        def floor(self, table, column, **kw):
            return 2018

    with pytest.raises(ValueError, match="2018"):
        cov.assert_shell_floor(2016, _BM())
    cov.assert_shell_floor(2018, _BM())   # its own floor season is allowed
    cov.assert_shell_floor(2024, _BM())
    assert breaks.STATUS_ABSENT   # the module the floor claim ultimately comes from


def test_generic_db_is_not_counted_as_a_safety():
    """The roster path's whole risk: `DB` is the generic that covers corners too, and counting it
    would manufacture two-high looks out of nickel personnel."""
    from fantasy_quant.situation import coverage as cov

    assert "DB" not in cov.SAFETY_TOKENS
    assert {"FS", "SS"} <= set(cov.SAFETY_TOKENS)


def test_the_unobtainable_tier_is_named_and_stays_named():
    """DATA-1's do-not-chase rule, made assertable: a session that 'fixes' this by deleting the
    entry has misunderstood the register."""
    from fantasy_quant.situation import coverage as cov

    joined = " ".join(cov.NOT_OBTAINABLE_FREE).lower()
    assert "alignment" in joined and "rotation" in joined
    assert len(cov.NOT_OBTAINABLE_FREE) >= 3
