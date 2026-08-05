"""Session DATA-2, second half — 0.13.4 offense · 0.13.5 construction · 0.13.6 ST · 0.13.7 panel.

``tests/test_data2.py`` covers 0.13.0–0.13.3. This file continues it; the split is by substep, not
by kind, so a failure names the substep that owns the fix.
"""

from __future__ import annotations

import duckdb
import pytest

from fantasy_quant.data import registry, teams
from fantasy_quant.situation import construction as ct
from fantasy_quant.situation import defense_fingerprint as dfp
from fantasy_quant.situation import fingerprint
from fantasy_quant.situation import offense_scheme as os_
from fantasy_quant.situation import scheme_panel as sp

# --------------------------------------------------------------------------------------------
# 0.13.4 — the two offensive personnel encodings
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "skill_form, full_form, package",
    [
        ("1 RB, 1 TE, 3 WR", "1 C, 2 G, 1 QB, 1 RB, 2 T, 1 TE, 3 WR", "11"),
        ("1 RB, 2 TE, 2 WR", "1 C, 2 G, 1 QB, 1 RB, 2 T, 2 TE, 2 WR", "12"),
        ("2 RB, 1 TE, 2 WR", "1 C, 2 G, 1 QB, 2 RB, 2 T, 1 TE, 2 WR", "21"),
        ("1 RB, 3 TE, 1 WR", "1 C, 2 G, 1 QB, 1 RB, 2 T, 3 TE, 1 WR", "13"),
        ("1 RB, 0 TE, 4 WR", "1 C, 2 G, 1 QB, 1 RB, 2 T, 0 TE, 4 WR", "10"),
    ],
)
def test_both_offense_encodings_parse_to_the_same_package(skill_form, full_form, package):
    """The 2016-2022 skill-only string and the 2023+ full-22 string must agree.

    This is the offensive twin of 0.13.2's defensive-encoding test, and it is the single
    assumption that lets a personnel share pool across the 2023 seam.
    """
    a = os_.parse_offense_personnel(skill_form)
    b = os_.parse_offense_personnel(full_form)
    assert a["package"] == b["package"] == package
    assert (a["rb"], a["te"], a["wr"]) == (b["rb"], b["te"], b["wr"])
    # the full form names the linemen the skill form leaves implied — that is the whole difference
    assert a["ol"] == 0 and b["ol"] == 5
    assert a["n_men"] == 5 and b["n_men"] == 11


def test_a_kick_unit_gets_no_package():
    """A punt team parses to nonsense skill counts; labelling it '00 personnel' would file a
    special-teams snap in the empty-formation bucket."""
    parsed = os_.parse_offense_personnel("1 C, 1 DE, 2 G, 1 K, 1 LS, 1 P, 4 T")
    assert parsed["package"] is None
    assert parsed["other"] > 0  # provenance, never a filter


def test_a_defensive_string_in_an_offensive_column_is_provenance_not_a_crash():
    parsed = os_.parse_offense_personnel("1 CB, 3 FS, 4 ILB, 1 LS, 1 P, 1 SS")
    assert parsed["package"] is None
    assert parsed["n_skill"] == 0


def test_empty_and_malformed_personnel_return_the_null_shape():
    for bad in (None, "", "   ", 17, "no digits here"):
        parsed = os_.parse_offense_personnel(bad)  # type: ignore[arg-type]
        assert parsed["package"] is None and parsed["n_men"] == 0


def test_every_route_has_a_family_and_every_family_route_is_a_route():
    """The route tree is enumerated, not counted — a vendor adding a 20th route must surface as an
    unlisted string rather than silently joining an 'other' bucket."""
    assert set(os_.ROUTE_FAMILY) == set(os_.ROUTES)
    assert set(os_.ROUTE_FAMILY.values()) == {"deep", "intermediate", "short", "behind_los"}


def test_route_columns_are_unique_and_sql_safe():
    cols = [os_._route_col(r) for r in os_.ROUTES]
    assert len(set(cols)) == len(cols)
    assert all(c.replace("_", "").isalnum() for c in cols)


# --------------------------------------------------------------------------------------------
# 0.13.4 — the FTN guard is a guard, not a docstring (UI-1 lesson 4)
# --------------------------------------------------------------------------------------------


def test_ftn_guard_raises_below_the_floor_and_names_it():
    with pytest.raises(ValueError, match="2022"):
        os_.assert_ftn_backtestable([2019, 2021])


def test_ftn_guard_refuses_a_dev_only_request():
    """FTN starts in 2022 and DEV ends in 2022, so a DEV-only request is one observation."""
    with pytest.raises(ValueError, match="backtestable"):
        os_.assert_ftn_backtestable([2022])


def test_ftn_guard_allows_descriptive_live_use():
    os_.assert_ftn_backtestable([2024, 2025])  # must not raise


# --------------------------------------------------------------------------------------------
# 0.13.5 — the four franchise vocabularies
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "variant, canonical",
    [
        ("ARZ", "ARI"), ("BLT", "BAL"), ("CLV", "CLE"), ("HST", "HOU"),  # nflverse alternates
        ("GNB", "GB"), ("KAN", "KC"), ("NWE", "NE"), ("SFO", "SF"), ("TAM", "TB"),  # PFR
        ("NOR", "NO"), ("LVR", "LV"), ("SDG", "LAC"),
        ("OAK", "LV"), ("SD", "LAC"), ("STL", "LA"), ("LAR", "LA"), ("SL", "LA"),  # relocations
        ("JAC", "JAX"), ("WSH", "WAS"),
        ("LA", "LA"), ("KC", "KC"),  # already canonical
    ],
)
def test_every_franchise_variant_maps_to_a_pbp_code(variant, canonical):
    """Each of these was found by a join coming up short; the test is what stops the next one."""
    mapped = teams.PBP_ALIAS.get(variant, variant)
    assert mapped == canonical
    assert mapped in teams.PBP_TEAMS


def test_no_alias_target_is_itself_an_alias():
    """A canon that needs two passes is not a canon."""
    for src, dst in teams.PBP_ALIAS.items():
        assert dst not in teams.PBP_ALIAS, f"{src} -> {dst}, but {dst} is itself aliased"


def test_canon_sql_and_pandas_agree():
    con = duckdb.connect()
    codes = [*teams.PBP_ALIAS, *sorted(teams.PBP_TEAMS)]
    con.execute("create table t as select * from (values " +
                ",".join(f"('{c}')" for c in codes) + ") as v(team)")
    sql = {r[0]: r[1] for r in
           con.execute(f"select team, {teams.canon_team_sql('team')} from t").fetchall()}
    for code in codes:
        assert sql[code] == teams.PBP_ALIAS.get(code, code)


def test_the_two_canons_disagree_only_where_documented():
    """The ADP canon says the Rams are LAR; pbp says LA. Pinned, so a future edit is loud."""
    teams.assert_canons_disagree_only_on_la()


def test_nickname_map_is_derived_and_collapses_relocations():
    con = duckdb.connect()
    con.execute("""create table teams_meta as select * from (values
        ('Ravens','BAL'),('49ers','SF'),('Rams','LA'),('Rams','STL'),('Rams','LAR'),
        ('Raiders','OAK'),('Raiders','LV'),('Chargers','SD'),('Chargers','LAC')
    ) as v(team_nick, team_abbr)""")
    m = teams.nickname_map(con)
    assert m["Rams"] == "LA" and m["Raiders"] == "LV" and m["Chargers"] == "LAC"
    assert m["Ravens"] == "BAL" and m["49ers"] == "SF"


def test_nickname_map_raises_on_a_genuine_new_collision():
    con = duckdb.connect()
    con.execute("""create table teams_meta as select * from (values
        ('Ravens','BAL'),('Ravens','CLE')) as v(team_nick, team_abbr)""")
    with pytest.raises(ValueError, match="two different franchises"):
        teams.nickname_map(con)


# --------------------------------------------------------------------------------------------
# 0.13.5 — the position vocabulary, and the contract hazards
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fine, grouped",
    [("CB", "DB"), ("FS", "DB"), ("SS", "DB"), ("S", "DB"),
     ("DE", "DL"), ("DT", "DL"), ("NT", "DL"),
     ("ILB", "LB"), ("MLB", "LB"), ("OLB", "LB"),
     ("C", "OL"), ("G", "OL"), ("T", "OL"),
     ("FB", "RB"), ("K", "ST"), ("P", "ST"), ("LS", "ST")],
)
def test_the_pre_2016_position_vocabulary_maps_to_a_group(fine, grouped):
    """2014-2015 rosters use fine-grained positions. Leaving them unmapped is what made 64
    team-seasons' position shares fail to sum to 1."""
    assert ct.position_group(fine) == grouped


@pytest.mark.parametrize("pos", ["QB", "RB", "WR", "TE", "OL", "DL", "LB", "DB"])
def test_the_post_2016_vocabulary_is_identity(pos):
    assert ct.position_group(pos) == pos


def test_unknown_position_is_none_not_silently_grouped():
    for bad in (None, "", "  ", "XYZ", 3):
        assert ct.position_group(bad) is None  # type: ignore[arg-type]


def test_every_group_target_is_a_declared_position_group():
    assert set(ct._POSITION_TO_GROUP.values()) <= set(ct.POSITION_GROUPS)


def test_group_case_sql_matches_the_python_mapping():
    con = duckdb.connect()
    positions = [*ct._POSITION_TO_GROUP, "XYZ"]
    con.execute("create table r as select * from (values " +
                ",".join(f"('{p}')" for p in positions) + ") as v(position)")
    sql = {r[0]: r[1] for r in
           con.execute(f"select position, {ct._group_case('r.position')} from r").fetchall()}
    for pos in positions:
        assert sql[pos] == ct.position_group(pos)


def test_contract_season_counts_a_duplicated_contract_once():
    """`contracts` has no unique key — up to 9 byte-identical rows. A naive sum multiplies a
    player's money by his duplicate count, worst for the expensive veterans who repeat most."""
    con = duckdb.connect()
    con.execute("""create table contracts as select * from (values
        ('00-1', 2022, 4.0, 40.0, 10.0, 2.0, 0.05, 'QB', 1),
        ('00-1', 2022, 4.0, 40.0, 10.0, 2.0, 0.05, 'QB', 1),
        ('00-1', 2022, 4.0, 40.0, 10.0, 2.0, 0.05, 'QB', 1)
    ) as v(gsis_id, year_signed, years, value, apy, guaranteed, apy_cap_pct,
           position, otc_id)""")
    ct.build_contract_season(con)
    rows = con.execute(f"""select count(*), sum(apy) from {ct.CONTRACT_SEASON_TABLE}
                           where season = 2023""").fetchone()
    assert rows == (1, 10.0)


def test_contract_season_takes_the_most_recently_signed_deal_in_force():
    """An extension leaves two nominal windows over the same season; the newer one is in force."""
    con = duckdb.connect()
    con.execute("""create table contracts as select * from (values
        ('00-1', 2021, 5.0, 50.0, 10.0, 2.0, 0.05, 'QB', 1),
        ('00-1', 2023, 4.0, 200.0, 50.0, 9.0, 0.20, 'QB', 2)
    ) as v(gsis_id, year_signed, years, value, apy, guaranteed, apy_cap_pct,
           position, otc_id)""")
    ct.build_contract_season(con)
    apy = con.execute(f"""select apy from {ct.CONTRACT_SEASON_TABLE}
                          where season = 2024 and gsis_id = '00-1'""").fetchone()[0]
    assert apy == 50.0


def test_contract_season_drops_the_year_zero_junk_rows():
    """1,121 rows carry year_signed = 0; a window from year zero is in force for every season."""
    con = duckdb.connect()
    con.execute("""create table contracts as select * from (values
        ('00-9', 0, 4.0, 40.0, 10.0, 2.0, 0.05, 'QB', 1)
    ) as v(gsis_id, year_signed, years, value, apy, guaranteed, apy_cap_pct,
           position, otc_id)""")
    ct.build_contract_season(con)
    assert con.execute(f"select count(*) from {ct.CONTRACT_SEASON_TABLE}").fetchone()[0] == 0


def test_unknown_pick_value_curve_raises():
    with pytest.raises(ValueError, match="unknown pick-value curve"):
        ct.build_team_construction(object(), curve="not_a_curve")  # type: ignore[arg-type]


# --------------------------------------------------------------------------------------------
# 0.13.7 — the panel: what may be zero, and what must be null
# --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("col", ["man_share", "share_cover_3", "blitz_rate", "share_p11"])
def test_a_football_column_must_be_null_below_its_floor(col):
    assert sp.measures_football(col)


@pytest.mark.parametrize("col", ["charted_share", "man_zone_denom", "rushers_denom",
                                 "pressure_denom", "off_snaps", "n_picks"])
def test_a_coverage_column_may_be_zero_below_its_floor(col):
    """'None of this team's snaps were charted in 2016' is TRUE, and it is the column that
    explains the nulls beside it. Nulling it would throw that away."""
    assert not sp.measures_football(col)


@pytest.mark.parametrize("col", ["season", "week", "team", "head_coach", "roof", "pulled_at"])
def test_keys_are_never_metrics(col):
    assert not sp.is_metric(col)


def test_counts_are_not_zscored():
    """A z-scored snap count measures pace and schedule, not scheme."""
    for col in ("off_snaps", "def_snaps", "n_rostered", "rushers_denom", "fg_att", "games"):
        assert not sp.is_metric(col)


def test_rates_are_zscored():
    for col in ("blitz_rate", "man_share", "share_nickel", "pass_rate_neutral", "cap_share_wr"):
        assert sp.is_metric(col)


# --------------------------------------------------------------------------------------------
# 0.13.9 — T49: the floor is a property of the COLUMN
# --------------------------------------------------------------------------------------------


def test_man_zone_floor_is_2018_not_the_tables_2016():
    """The whole content of T49: participation's floor is 2016 and man/zone's is 2018, so with
    DEV_SEASONS = 2014-2022 there are FIVE development seasons of man/zone, not seven."""
    assert registry.column_floor("participation", "defense_man_zone_type") == 2018
    assert registry.column_floor("participation", "offense_personnel") == 2016
    assert registry.BY_TABLE["participation"].floor == 2016


def test_column_floor_assertion_names_the_column_and_the_discrepancy():
    with pytest.raises(ValueError, match="per-COLUMN"):
        registry.assert_column_floor("participation", "defense_man_zone_type", 2017)


def test_column_floor_allows_its_own_floor_season():
    registry.assert_column_floor("participation", "defense_man_zone_type", 2018)


def test_a_column_with_no_own_floor_falls_back_to_its_table():
    registry.assert_column_floor("participation", "offense_personnel", 2016)
    with pytest.raises(ValueError):
        registry.assert_column_floor("participation", "offense_personnel", 2015)


@pytest.mark.parametrize("table", [
    "defense_team_week", "defense_player_week", "defense_coverage_week",
    "offense_team_week", "offense_player_week", "team_construction_season",
    "st_team_season", "kicking_env_week", "team_scheme_week", "team_scheme_season",
    "team_scheme_columns", "contract_season",
])
def test_every_data2_table_declares_a_pit_class(table):
    spec = registry.spec(table)
    assert spec.pit_class in registry.PIT_CLASSES
    assert spec.source


def test_the_pit_guard_refuses_an_unlagged_draft_feature():
    """B8, written to fail and verified failing — a guard nobody has seen refuse anything is not
    known to work."""
    with pytest.raises(ValueError, match="leaks"):
        registry.assert_pit_class_for_draft_feature("team_scheme_season", lagged=False)


def test_the_pit_guard_allows_the_lagged_use():
    registry.assert_pit_class_for_draft_feature("team_scheme_season", lagged=True)


# --------------------------------------------------------------------------------------------
# 0.13.8 — descriptive only, as a guard
# --------------------------------------------------------------------------------------------


def test_the_defensive_fingerprint_is_not_wired_into_the_frozen_value_stack():
    """'Descriptive only' as an assertion, not a comment. A future session that wants the wiring
    deletes this deliberately, which is the point."""
    dfp.assert_not_wired_into_the_optimizer()


def test_the_eb_machinery_defaults_to_the_offensive_vector():
    """The `metrics` parameter is additive: every pre-existing caller is unchanged."""
    import inspect
    for fn in (fingerprint.eb_weights, fingerprint.fingerprints,
               fingerprint.assert_fingerprints_sane):
        assert inspect.signature(fn).parameters["metrics"].default == fingerprint.METRICS


def test_the_widened_offensive_vector_is_additive_not_a_replacement():
    """fingerprint.METRICS' 14 are validated and consumed; 0.13.8 adds beside them."""
    assert not set(dfp.OFFENSE_SCHEME_METRICS) & set(fingerprint.METRICS)


def test_defensive_regime_drops_are_only_legitimate_below_the_panel_floor():
    """A reason that is always available is not a reason. This is the guard that replaced
    'no panel row for this team-season', which was true of every possible drop and so
    distinguished a floor from a franchise-code join failure not at all."""
    import pandas as pd
    rp = pd.DataFrame([
        {"play_caller": "X", "team": "LA", "season": 2015, "dropped": True,
         "drop_reason": "season is below the panel floor"},
        {"play_caller": "Y", "team": "LAR", "season": 2022, "dropped": True,
         "drop_reason": "NO PANEL ROW — this is a join failure, not a floor"},
    ])
    with pytest.raises(AssertionError, match="franchise canon"):
        dfp.assert_regime_coverage(rp, panel_floor=2016)
    dfp.assert_regime_coverage(rp[rp["season"] < 2016], panel_floor=2016)
