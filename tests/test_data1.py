"""Session DATA-1 (Phase 0.12) — offline unit tests. No network, no live store.

Everything here runs against an in-memory DuckDB or a synthetic frame. The network paths (the
release loader, the actual ingests) are exercised by the ``steps/phase0_12_*`` done-bars.

★ Several tests below exist to **make a guard fail**. That is deliberate and it is the session's
recurring method: UI-1's lesson 4 (*a docstring is not a guard*) and T31's warning (*assert the
control can produce a known difference before trusting it to show none*). A gate that has never
been seen to fail is a gate nobody has tested — it is a comment with a function signature.
"""

from __future__ import annotations

import duckdb
import pandas as pd
import pytest

from fantasy_quant.data import registry, validate
from fantasy_quant.data.sources import nflverse_release as nr
from fantasy_quant.data.sources import participation as pt
from fantasy_quant.data.sources import small


# --------------------------------------------------------------------------------------------
# B0 — the store fingerprint, and the proof that it can fail
# --------------------------------------------------------------------------------------------
@pytest.fixture
def con():
    c = duckdb.connect(":memory:")
    c.execute("create table t as select * from (values (1, 'a'), (2, 'b')) v(x, y)")
    c.execute("create table u as select * from (values (10.0)) v(z)")
    return c


def test_fingerprint_is_stable_across_calls(con):
    assert validate.table_fingerprint(con, "t") == validate.table_fingerprint(con, "t")


def test_fingerprint_detects_a_changed_value(con):
    before = validate.fingerprint_store(con)
    con.execute("update t set y = 'CHANGED' where x = 1")
    gate = validate.compare_fingerprints(before, validate.fingerprint_store(con), allowances={})
    assert not gate["passed"]
    assert gate["changed"][0]["table"] == "t"
    assert "y" in gate["changed"][0]["columns_changed"]


def test_fingerprint_detects_an_added_row(con):
    before = validate.fingerprint_store(con)
    con.execute("insert into t values (3, 'c')")
    gate = validate.compare_fingerprints(before, validate.fingerprint_store(con), allowances={})
    assert not gate["passed"]
    assert gate["changed"][0]["n_rows"] == [2, 3]


def test_fingerprint_detects_a_dropped_table(con):
    before = validate.fingerprint_store(con)
    con.execute("drop table u")
    gate = validate.compare_fingerprints(before, validate.fingerprint_store(con), allowances={})
    assert not gate["passed"]
    assert gate["missing_tables"] == ["u"]


def test_fingerprint_allows_a_new_table(con):
    before = validate.fingerprint_store(con)
    con.execute("create table v as select 1 as a")
    gate = validate.compare_fingerprints(before, validate.fingerprint_store(con), allowances={})
    assert gate["passed"]          # additive is the session; new tables are never a failure
    assert gate["new_tables"] == ["v"]


def test_allowance_permits_only_the_named_retype(con):
    """The DOUBLE->INT allowance must cover the declared cast and nothing else."""
    before = validate.fingerprint_store(con)
    con.execute("alter table u alter z type INTEGER")
    rule = {"u": {"retyped_columns": ["z"], "reason": "test"}}
    assert validate.compare_fingerprints(before, validate.fingerprint_store(con), rule)["passed"]


def test_allowance_does_not_cover_an_unnamed_column(con):
    """An allowance is not a blanket pardon — this is the UI-1 'unclassified leaf' rule."""
    before = validate.fingerprint_store(con)
    con.execute("update t set y = 'CHANGED' where x = 1")
    rule = {"t": {"retyped_columns": ["x"], "reason": "test"}}
    assert not validate.compare_fingerprints(before, validate.fingerprint_store(con),
                                             rule)["passed"]


def test_allowance_does_not_cover_a_row_count_change(con):
    before = validate.fingerprint_store(con)
    con.execute("insert into u values (11.0)")
    rule = {"u": {"retyped_columns": ["z"], "reason": "test"}}
    assert not validate.compare_fingerprints(before, validate.fingerprint_store(con),
                                             rule)["passed"]


# --------------------------------------------------------------------------------------------
# B6 — upstream floors are assertions
# --------------------------------------------------------------------------------------------
@pytest.mark.parametrize("tag,season", [("ftn_charting", 2019), ("pbp_participation", 2014),
                                        ("pfr_advstats", 2017)])
def test_floor_raises_below_the_floor(tag, season):
    with pytest.raises(ValueError, match=str(nr.SEASON_FLOORS[tag])):
        nr.assert_season_floor(tag, [season])


@pytest.mark.parametrize("tag,season", [("ftn_charting", 2022), ("pbp_participation", 2016),
                                        ("pfr_advstats", 2018)])
def test_floor_is_silent_at_and_above_the_floor(tag, season):
    """A guard that always throws is not a guard."""
    nr.assert_season_floor(tag, [season])


def test_unknown_tag_has_no_floor_and_does_not_raise():
    nr.assert_season_floor("some_tag_with_no_declared_floor", [1970])


# --------------------------------------------------------------------------------------------
# B7 — PIT classes and backtestability are assertions
# --------------------------------------------------------------------------------------------
def test_retrospective_table_can_never_be_a_draft_feature():
    with pytest.raises(ValueError, match="retrospective"):
        registry.assert_pit_class_for_draft_feature("qbr_season", lagged=True)


def test_in_season_weekly_is_illegal_unlagged_and_legal_lagged():
    with pytest.raises(ValueError, match="lag"):
        registry.assert_pit_class_for_draft_feature("participation", lagged=False)
    registry.assert_pit_class_for_draft_feature("participation", lagged=True)


def test_preseason_table_is_always_legal():
    registry.assert_pit_class_for_draft_feature("schedules", lagged=False)


def test_ftn_is_not_backtestable_and_weekly_is():
    with pytest.raises(ValueError, match="backtestable=False"):
        registry.assert_backtestable("ftn_charting")
    registry.assert_backtestable("weekly")


def test_undeclared_table_raises_rather_than_defaulting_permissively():
    with pytest.raises(KeyError):
        registry.spec("no_such_table")


def test_every_registry_entry_declares_a_valid_pit_class():
    for s in registry.REGISTRY:
        assert s.pit_class in registry.PIT_CLASSES, s.table


def test_ftn_floor_leaves_exactly_one_dev_season():
    """The reason FTN ships backtestable=False is arithmetic, so assert the arithmetic."""
    from fantasy_quant.config import DEV_SEASONS

    overlap = set(range(registry.spec("ftn_charting").floor, 2026)) & set(DEV_SEASONS)
    assert len(overlap) == 1


# --------------------------------------------------------------------------------------------
# fill-rate gate — the ngs_air_yards failure mode
# --------------------------------------------------------------------------------------------
def test_fill_rate_gate_catches_a_silently_emptied_column():
    """`ngs_air_yards` went to 0.00 in 2023 and nothing noticed. This is what notices."""
    base = {"ngs": {"ngs_air_yards": 0.95, "avg_separation": 0.99}}
    now = {"ngs": {"ngs_air_yards": 0.00, "avg_separation": 0.99}}
    gate = validate.fill_rate_gate(None, now, base)
    assert not gate["passed"]
    assert gate["degraded"][0]["column"] == "ngs_air_yards"


def test_fill_rate_gate_tolerates_small_movement():
    base = {"ngs": {"a": 0.95}}
    assert validate.fill_rate_gate(None, {"ngs": {"a": 0.93}}, base)["passed"]


def test_fill_rate_gate_says_so_when_it_has_no_baseline():
    gate = validate.fill_rate_gate(None, {"ngs": {"a": 0.5}}, None)
    assert gate["passed"] and "baseline" in gate["status"]


# --------------------------------------------------------------------------------------------
# 0.12.3 — participation normalization
# --------------------------------------------------------------------------------------------
def _raw_participation() -> pd.DataFrame:
    return pd.DataFrame({
        "nflverse_game_id": ["2016_01_CAR_DEN", "2016_01_SD_KC", "2016_02_OAK_LA"],
        "old_game_id": ["a", "b", "c"],
        "play_id": pd.array([51, 36, 77], dtype="int32"),
        "possession_team": ["DEN", "SD", "LA"],
        "offense_personnel": ["1 RB, 1 TE, 3 WR", "", None],
        "defense_personnel": ["4-3", "", None],
        "offense_formation": ["SHOTGUN", "", None],
        "defenders_in_box": [6.0, None, None],
        "number_of_pass_rushers": [4.0, None, None],
        "players_on_play": ["00-1;00-2", "", None],
        "offense_players": ["00-1;00-2", "", None],
        "defense_players": ["00-3", "", None],
        "n_offense": pd.array([11, 0, 0], dtype="int32"),
        "n_defense": pd.array([11, 0, 0], dtype="int32"),
        "ngs_air_yards": [5.0, None, None],
        "time_to_throw": [2.5, None, None],
        "was_pressure": [True, None, None],
        "route": ["GO", "", None],
        "defense_man_zone_type": ["ZONE_COVERAGE", "", None],
        "defense_coverage_type": ["COVER_3", "", None],
    })


def test_normalize_derives_season_and_week_from_the_game_id():
    df = pt.normalize_participation(_raw_participation())
    assert df["season"].tolist() == [2016, 2016, 2016]
    assert df["week"].tolist() == [1, 1, 2]


def test_normalize_canonicalizes_era_accurate_team_codes():
    """The LA/LAR lesson — 16.4 silently deleted a whole coaching tenure on exactly this."""
    df = pt.normalize_participation(_raw_participation())
    assert df["possession_team"].tolist() == ["DEN", "LAC", "LAR"]
    assert df["possession_team_raw"].tolist() == ["DEN", "SD", "LA"]   # the era code is kept


def test_normalize_treats_empty_strings_as_missing():
    """An empty string counts as present in `count(col)`, so every fill rate would lie."""
    df = pt.normalize_participation(_raw_participation())
    assert df["offense_personnel"].isna().sum() == 2
    assert df["route"].isna().sum() == 2


def test_normalize_adds_the_2023_drift_columns_as_explicit_nulls():
    """20-col seasons union onto the 26-col superset; a dropped column is never silent."""
    df = pt.normalize_participation(_raw_participation())
    for c in pt.DRIFT_COLS_2023:
        assert c in df.columns
        assert df[c].isna().all()


def test_normalize_makes_play_id_join_compatible():
    df = pt.normalize_participation(_raw_participation())
    assert df["play_id"].dtype == "int64"


def test_pass_play_columns_are_the_ones_with_a_conditional_denominator():
    """B5 — route/coverage at ~0.38 is the pass-play share, not 62 % missing."""
    assert "route" in pt.PASS_PLAY_COLS
    assert "defense_man_zone_type" in pt.PASS_PLAY_COLS
    assert "offense_personnel" not in pt.PASS_PLAY_COLS


# --------------------------------------------------------------------------------------------
# 0.12.6 — the small-source declarations
# --------------------------------------------------------------------------------------------
def test_every_small_source_declares_a_grain_and_a_pit_class():
    for s in small.SMALL_SOURCES:
        assert s.grain and s.pit_class in registry.PIT_CLASSES, s.table


def test_every_small_source_is_in_the_registry():
    for s in small.SMALL_SOURCES:
        assert s.table in registry.BY_TABLE, s.table


def test_sources_without_a_unique_row_key_say_so():
    """`contracts` and `trades` genuinely have no row key; that is declared, not papered over."""
    by = {s.table: s for s in small.SMALL_SOURCES}
    assert by["contracts"].key_unique is False
    assert by["trades"].key_unique is False
    assert by["schedules"].key_unique is True


def test_bye_weeks_derives_one_bye_per_team():
    con = duckdb.connect(":memory:")
    # 5 teams over 5 weeks: each week exactly one team is idle and the other four pair up, so
    # every team has exactly one bye. (An even team count leaves an unpairable remainder once a
    # bye is removed, which is a fixture bug that looks exactly like a function bug.)
    rows = []
    teams = [f"T{i:02d}" for i in range(5)]
    for wk in range(1, 6):
        idle = teams[wk - 1]
        playing = [t for t in teams if t != idle]
        for i in range(0, len(playing), 2):
            rows.append((2024, wk, "REG", playing[i], playing[i + 1]))
    con.execute("create table schedules (season int, week int, game_type varchar, "
                "home_team varchar, away_team varchar)")
    con.executemany("insert into schedules values (?, ?, ?, ?, ?)", rows)
    byes = small.bye_weeks(con, 2024)
    assert len(byes) == 5
    assert byes.groupby("team").size().eq(1).all()
    assert set(byes["bye_week"]) == {1, 2, 3, 4, 5}
