"""The team book: registry, league context, traits, comps, the guard — and, against the real store,
the golden Bears book, the parity of the pbp family with the frozen panel, and the two refactors.

Tests marked ``needs_db`` read ``data/fantasy_quant.duckdb`` and skip where it is absent (CI).
Everything else builds its own data.
"""

from __future__ import annotations

import copy

import duckdb
import numpy as np
import pandas as pd
import pytest

from fantasy_quant.config import DUCKDB_PATH
from fantasy_quant.data import db
from fantasy_quant.teambook import build as B
from fantasy_quant.teambook import metrics as M
from fantasy_quant.teambook import pbp_family as pf
from fantasy_quant.teambook import schema as S

needs_db = pytest.mark.skipif(not DUCKDB_PATH.exists(), reason="project DuckDB store not present")


# --- registry ---------------------------------------------------------------------------------
def test_registry_keys_are_unique_and_sources_known():
    assert len(M.BY_KEY) == len(M.REGISTRY)
    assert {m.source for m in M.REGISTRY} <= set(M.SOURCES)
    assert {m.side for m in M.REGISTRY} <= set(M.SIDES)


def test_floors_follow_the_source_family():
    assert M.BY_KEY["play_action_rate"].floor == 2022
    assert M.BY_KEY["share_cover_3"].floor == 2018
    assert M.BY_KEY["man_share"].floor == 2018
    assert M.BY_KEY["share_p12"].floor <= M.FIRST_SEASON
    assert M.BY_KEY["pass_rate"].floor <= M.FIRST_SEASON


def test_the_broken_empty_formation_column_is_not_registered():
    # offense_formation never takes the value 'EMPTY', so share_empty is 0 for every team-season
    assert "share_empty" not in M.BY_KEY


# --- league context ----------------------------------------------------------------------------
def _frame(**cols) -> pd.DataFrame:
    teams = [f"T{i:02d}" for i in range(len(next(iter(cols.values()))))]
    frame = pd.DataFrame({"team": teams, **cols})
    for key in M.BY_KEY:
        if key not in frame:
            frame[key] = np.nan
    return frame


def test_rank_one_is_best_for_polar_metrics_and_most_for_tendencies():
    ctx = B.league_context(_frame(def_epa_per_play=[0.10, -0.05, 0.02],
                                  share_p12=[0.10, 0.40, 0.25]))
    assert ctx["def_epa_per_play"]["rank"] == {"T00": 3, "T01": 1, "T02": 2}  # lower is better
    assert ctx["share_p12"]["rank"] == {"T00": 3, "T01": 1, "T02": 2}         # most is 1st


def test_a_null_metric_gets_no_context_and_no_zero():
    ctx = B.league_context(_frame(pass_rate=[0.5, 0.6, 0.55]))
    assert "man_share" not in ctx
    assert set(ctx["pass_rate"]["z"]) == {"T00", "T01", "T02"}


def test_traits_pick_the_extremes_and_phrase_them_label_first():
    vals = list(np.linspace(0.4, 0.6, 32))
    ctx = B.league_context(_frame(pass_rate=vals, def_epa_per_play=vals))
    top = B.traits("T31", ctx)
    texts = {t["key"]: t["text"] for t in top}
    assert texts["pass_rate"] == "Pass rate: highest in the league"
    assert texts["def_epa_per_play"] == "EPA / play allowed: worst in the league"
    assert all(t["side"] in B.TRAITS_PER_SIDE for t in top)
    assert B.traits("T15", ctx) == []  # the middle of the league is not a trait


# --- comps -------------------------------------------------------------------------------------
def test_similar_uses_only_shared_metrics_and_skips_the_same_franchise():
    keys = [m.key for m in M.REGISTRY if m.scheme and m.side == "defense"]
    rows = {
        (2025, "AAA"): dict.fromkeys(keys, 1.0),
        (2024, "AAA"): dict.fromkeys(keys, 1.0),           # same franchise: never a comp
        (2024, "BBB"): dict.fromkeys(keys, 1.1),
        (2024, "CCC"): {k: (1.0 if i < 2 else np.nan) for i, k in enumerate(keys)},  # 2 shared
        (2024, "DDD"): dict.fromkeys(keys, -2.0),
    }
    zm = pd.DataFrame.from_dict(rows, orient="index")
    zm.index = pd.MultiIndex.from_tuples(zm.index, names=["season", "team"])
    out = B.similar(zm, 2025, "AAA", "defense")
    assert [r["team"] for r in out] == ["BBB", "DDD"]  # CCC has too few shared metrics
    assert out[0]["shared"] == len(keys)


def test_a_live_season_with_missing_families_still_finds_comps_on_what_it_has():
    keys = [m.key for m in M.REGISTRY if m.scheme and m.side == "defense"]
    ftn = [k for k in keys if M.BY_KEY[k].source == M.FTN]
    live = {k: (0.5 if k in ftn else np.nan) for k in keys}
    zm = pd.DataFrame.from_dict({(2026, "AAA"): live, (2024, "BBB"): dict.fromkeys(keys, 0.4)},
                                orient="index")
    zm.index = pd.MultiIndex.from_tuples(zm.index)
    out = B.similar(zm, 2026, "AAA", "defense")
    assert out and out[0]["shared"] == len(ftn)


# --- the guard ---------------------------------------------------------------------------------
def _book() -> dict:
    return {"team": "CHI", "season": 2025,
            "status": {"complete": True, "through_week": 18, "participation": True,
                       "unavailable": {}},
            "meta": {"record": {"w": 11, "l": 6, "t": 0}, "games": 17},
            "coaching": {}, "traits": [], "weekly": [],
            "players": {"offense": [{"name": "A", "snap_share": 0.9}], "defense": []},
            "metrics": {"pass_rate": {"v": 0.55, "rank": 24, "n": 32, "pct": 0.28, "z": -0.5,
                                      "median": 0.57}}}


def test_the_guard_passes_a_sane_book():
    S.assert_book_sane(_book())


@pytest.mark.parametrize("mutate, message", [
    (lambda b: b["metrics"]["pass_rate"].update(v=1.4), "not a share"),
    (lambda b: b["metrics"]["pass_rate"].update(rank=33), "rank"),
    (lambda b: b["metrics"].update(play_action_rate={"v": 0.3, "rank": 1, "n": 32, "pct": 1.0,
                                                     "z": 1, "median": 0.2})
     or b.update(season=2019), "below its 2022 floor"),
    (lambda b: b["status"]["unavailable"].update(pbp="x"), "marked unavailable"),
    (lambda b: b["meta"].update(games=16), "record"),
    (lambda b: b["metrics"].update(bogus={"v": 1, "rank": 1, "n": 1, "pct": 1, "z": 0,
                                          "median": 1}), "unregistered"),
])
def test_the_guard_refuses_impossible_books(mutate, message):
    book = copy.deepcopy(_book())
    mutate(book)
    with pytest.raises(S.BookError, match=message):
        S.assert_book_sane(book)


# --- the pbp family on a synthetic store --------------------------------------------------------
def _synthetic_store(charted: bool) -> duckdb.DuckDBPyConnection:
    rng = np.random.default_rng(0)
    n = 200
    pbp = pd.DataFrame({
        "season": 2025, "season_type": "REG", "week": rng.integers(1, 3, n),
        "game_id": [f"g{w}" for w in rng.integers(1, 3, n)], "play_id": np.arange(n),
        "posteam": "CHI", "defteam": "GB", "play_type": rng.choice(["pass", "run"], n),
        "qb_dropback": 0, "epa": rng.normal(0, 1, n), "success": rng.integers(0, 2, n),
        "yards_gained": rng.integers(-3, 25, n), "score_differential": 0,
        "game_seconds_remaining": 1800, "pass_oe": rng.normal(0, 5, n), "down": 1,
        "shotgun": rng.integers(0, 2, n), "no_huddle": 0, "sack": 0, "interception": 0,
        "fumble_lost": 0,
    })
    pbp["qb_dropback"] = (pbp["play_type"] == "pass").astype(int)
    ftn = pd.DataFrame({
        "game_id": pbp["game_id"], "play_id": pbp["play_id"], "ftn_play_id": pbp["play_id"],
        "is_motion": True, "is_play_action": False, "is_rpo": False, "is_screen_pass": False,
        "n_offense_backfield": 1, "qb_location": "S", "n_blitzers": 0, "n_pass_rushers": 4,
        "n_defense_box": 6,
    })
    con = duckdb.connect()
    con.register("pbp_df", pbp)
    con.execute("create table pbp as select * from pbp_df")
    con.register("ftn_df", ftn if charted else ftn.iloc[0:0])
    con.execute("create table ftn_charting as select * from ftn_df")
    return con


def test_pbp_family_rates_are_ratios_over_the_seasons_plays():
    con = _synthetic_store(charted=True)
    off = pf.offense(con, 2025).set_index("team").loc["CHI"]
    pbp = con.execute("select * from pbp").df()
    assert off["pass_rate"] == pytest.approx((pbp["play_type"] == "pass").mean())
    assert off["snaps_per_game"] == pytest.approx(len(pbp) / pbp["game_id"].nunique())
    assert off["motion_rate"] == 1.0


def test_ftn_rates_are_null_when_nothing_was_charted_never_zero():
    con = _synthetic_store(charted=False)
    off = pf.offense(con, 2025).set_index("team").loc["CHI"]
    dfn = pf.defense(con, 2025).set_index("team").loc["GB"]
    for v in (off["motion_rate"], off["play_action_rate"], dfn["ftn_blitz_rate"]):
        assert pd.isna(v)
    assert off["pass_rate"] > 0  # the pbp half is unaffected


# --- against the real store ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def con():
    c = db.connect(read_only=True)
    yield c
    c.close()


@pytest.fixture(scope="module")
def chi_2025(con):
    return B.build_season_books(con, 2025)


@needs_db
def test_the_scheme_panel_refactor_is_bit_identical(con):
    from fantasy_quant.situation import scheme_panel as sp
    with db.deterministic_reads(con):
        new = con.execute(sp.weekly_aggregate_sql()).df().sort_values(["season", "team"])
        old = con.execute(f"select * from {sp.SEASON_TABLE} order by season, team").df()
    pd.testing.assert_frame_equal(new.reset_index(drop=True), old[new.columns],
                                  check_exact=False, rtol=0, atol=1e-12)


@needs_db
def test_the_special_teams_refactor_is_bit_identical(con):
    from fantasy_quant.situation import special_teams as st
    with db.deterministic_reads(con):
        new = con.execute(st.st_team_season_sql()).df().drop(columns="pulled_at")
        old = con.execute(f"select * from {st.ST_TABLE} order by season, team").df()
    new = new.sort_values(["season", "team"]).reset_index(drop=True)
    pd.testing.assert_frame_equal(new, old.drop(columns="pulled_at"), check_exact=False,
                                  rtol=0, atol=1e-12)


@needs_db
def test_the_golden_bears_book(chi_2025):
    """The hand-built CHI 2025 artifact, reproduced by the pipeline (regular season, full PPR)."""
    b = chi_2025["books"]["CHI"]
    m = b["metrics"]
    assert b["meta"]["record"] == {"w": 11, "l": 6, "t": 0}
    assert (b["meta"]["points_for"], b["meta"]["points_against"]) == (441, 415)
    assert b["meta"]["bye_weeks"] == [5]
    assert m["snaps_per_game"]["v"] == pytest.approx(64.4706, abs=1e-4)
    assert m["snaps_per_game"]["rank"] == 2
    assert round(m["pass_rate"]["v"] * 100, 1) == 54.7 and m["pass_rate"]["rank"] == 24
    assert round(m["pass_oe_mean"]["v"], 1) == -3.9 and m["pass_oe_mean"]["rank"] == 22
    # the artifact printed 0.080; the pipeline reads 0.0795 — same rank, within display rounding
    assert m["epa_per_play"]["v"] == pytest.approx(0.080, abs=1e-3)
    assert m["epa_per_play"]["rank"] == 8
    assert round(m["share_p12"]["v"] * 100, 1) == 35.6 and m["share_p12"]["rank"] == 4
    assert round(m["share_under_center"]["v"] * 100, 1) == 47.5
    assert m["share_under_center"]["rank"] == 5
    assert round(m["share_p13"]["v"] * 100, 1) == 8.2 and m["share_p13"]["rank"] == 5
    assert m["play_action_rate"]["rank"] == 2


@needs_db
def test_pbp_family_matches_the_panel_where_both_define_the_number_the_same_way(con):
    from fantasy_quant.situation.scheme_panel import weekly_aggregate_sql
    exact = ("off_snaps", "pass_rate", "shotgun_rate", "no_huddle_rate", "motion_rate",
             "rpo_rate", "ftn_snaps")
    # filtered-denominator rates: the panel re-weights weekly rates by snaps (mean of ratios)
    approx = {"pass_rate_neutral": 0.05, "play_action_rate": 0.03, "screen_rate": 0.01,
              "pass_oe_mean": 0.1, "backfield_mean": 0.02, "epa_per_play": 1e-4}
    for season in range(M.FIRST_SEASON, 2026):
        ours = pf.offense(con, season).set_index("team")
        where = f"season = {season} and week <= {B.reg_weeks(con, season)}"
        panel = con.execute(weekly_aggregate_sql(where)).df().set_index("team")
        for key in exact:
            if panel[key].isna().all():
                continue
            np.testing.assert_allclose(ours[key], panel.loc[ours.index, key], atol=1e-9,
                                       err_msg=f"{key} {season}")
        for key, tol in approx.items():
            d = (ours[key] - panel.loc[ours.index, key]).abs().max()
            assert pd.isna(d) or d < tol, f"{key} {season}: {d}"


@needs_db
def test_participation_floors_agree_with_the_column_register(con):
    reg = con.execute("""select "column", observed_first_season from team_scheme_columns
                         where "table" = 'team_scheme_season'""").df()
    first = dict(zip(reg["column"], reg["observed_first_season"], strict=True))
    for key in M.keys(M.PARTICIPATION):
        assert M.BY_KEY[key].floor == first[key], key


@needs_db
def test_every_historical_season_builds_and_passes_the_guard(con):
    seasons = {s: B.build_season_books(con, s) for s in range(M.FIRST_SEASON, 2026)}
    for s in seasons.values():
        S.assert_season_sane(s["books"])
    B.attach_cross_season(seasons)
    early = seasons[2019]["books"]["CHI"]
    assert "play_action_rate" not in early["metrics"]      # FTN starts in 2022
    assert "ftn" in early["status"]["unavailable"]
    assert "share_cover_3" in early["metrics"]              # charted coverage from 2018
    chi = seasons[2025]["books"]["CHI"]
    assert len(chi["trends"]["pass_rate"]) == 8
    assert all(c["team"] != "CHI" for c in chi["comps"]["offense"])

