"""Phase 12 — news / NLP pipeline: pure unit tests (no project DB).

The load-bearing behaviours: (12.1) the injury feed dedupes to one row per player-week, the depth
feed
signs promotions positive / demotions negative, and the as-of filter is PIT (no future-stamped
event);
(12.2) the deterministic rules extractor maps decisive phrasings to the right signal, the structured
injury mapping prices a status (and refines a Questionable by practice), and the LLM seam is used
only
when a live client is passed and falls back to rules on a bad payload; (12.4) the news level-shift
knocks
a designated player toward zero and leaves everyone else untouched. Event-study / forecast-gain
integration
is exercised by the step done-bars (they need realized weekly points), like the other phases.
"""

from __future__ import annotations

import duckdb
import pandas as pd
import pytest

from fantasy_quant.news import sources
from fantasy_quant.news.extract import (
    ExtractedSignal,
    extract_signal,
    rules_extract,
    structured_injury_signal,
)
from fantasy_quant.news.validate import news_level_shift


# ------------------------------------------------------------------------------------------------
# 12.2 — extraction
# ------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("text,expected", [
    ("star RB ruled out for Sunday", "injury_out"),
    ("placed on injured reserve", "injury_out"),
    ("listed as doubtful with an ankle", "injury_out"),
    ("questionable, game-time decision", "injury_questionable"),
    ("activated off injured reserve, will play", "injury_return"),
    ("named the starter, moves to a workhorse role", "role_up"),
    ("benched, moving to a committee", "role_down"),
    ("threw for 3 touchdowns", "none"),
    ("", "none"),
])
def test_rules_extract(text, expected):
    assert rules_extract(text).signal_type == expected


def test_rules_extract_severity_sign():
    assert rules_extract("ruled out for the game").severity < 0
    assert rules_extract("activated and will play").severity > 0
    assert rules_extract("no news here").severity == 0.0


def test_structured_injury_signal():
    assert structured_injury_signal("Out").signal_type == "injury_out"
    assert structured_injury_signal("Out").severity == pytest.approx(-1.0)
    assert structured_injury_signal("Doubtful").severity == pytest.approx(-0.75)
    # a Questionable who did not practice is priced more severe than one who practiced full.
    dnp = structured_injury_signal("Questionable", "Did Not Practice")
    full = structured_injury_signal("Questionable", "Full Participation")
    assert dnp.severity < full.severity


def test_extracted_signal_rejects_bad_type():
    with pytest.raises(ValueError):
        ExtractedSignal("teleported", 0.0, 0.5, "rules")


class _FakeClient:
    """A live LLM client that always returns a fixed structured signal."""
    def __init__(self, payload=None, available=True):
        self._payload = payload or {"player_name": "X", "signal_type": "role_up",
                                    "severity": 0.7, "confidence": 0.9}
        self._available = available

    def available(self):
        return self._available

    def extract(self, text):
        return self._payload


def test_extract_signal_uses_client_when_available():
    s = extract_signal("some fuzzy headline", client=_FakeClient())
    assert s.source == "claude" and s.signal_type == "role_up" and s.player_name == "X"


def test_extract_signal_falls_back_when_unavailable():
    s = extract_signal("ruled out for the game", client=_FakeClient(available=False))
    assert s.source == "rules" and s.signal_type == "injury_out"


def test_extract_signal_falls_back_on_bad_payload():
    bad = _FakeClient(payload={"signal_type": "not_a_type"})   # invalid → rules fallback
    s = extract_signal("benched, now a backup", client=bad)
    assert s.source == "rules" and s.signal_type == "role_down"


# ------------------------------------------------------------------------------------------------
# 12.4 — the news level-shift (13.1 slot filler), pure
# ------------------------------------------------------------------------------------------------
def test_news_level_shift():
    levels = {"a": 12.0, "b": 10.0, "c": 8.0}
    desig = {"a": "Out", "b": "Questionable"}
    mult = {"Out": 0.0, "Questionable": 0.5, "Probable": 1.0}
    shift = news_level_shift(levels, desig, mult)
    # Out knocks a's level fully toward 0; Questionable halves b; c (undesignated) absent.
    assert shift["a"] == pytest.approx(-12.0)
    assert shift["b"] == pytest.approx(-5.0)
    assert "c" not in shift
    # a full-availability (mult>=1) status produces no shift.
    assert news_level_shift({"a": 9.0}, {"a": "Probable"}, mult) == {}


# ------------------------------------------------------------------------------------------------
# 12.1 — the PIT news stream on an in-memory fixture
# ------------------------------------------------------------------------------------------------
def _fixture_con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    injuries = pd.DataFrame({
        "gsis_id": ["p1", "p1", "p2", "p3"],
        "season": [2021, 2021, 2021, 2021],
        "week": [5, 5, 6, 7],           # p1 has two reports in week 5 → dedupe to the later one
        "team": ["AAA", "AAA", "BBB", "CCC"],
        "position": ["RB", "RB", "WR", "TE"],
        "report_status": ["Questionable", "Out", "Doubtful", "Questionable"],
        "report_primary_injury": ["knee", "knee", "ankle", "hamstring"],
        "practice_status": ["Limited", "Did Not Practice", None, "Full"],
        "date_modified": pd.to_datetime(
            ["2021-10-06", "2021-10-08", "2021-10-14", "2021-10-21"], utc=True),
    })
    con.register("_inj", injuries)
    con.execute("CREATE TABLE injuries AS SELECT * FROM _inj")
    depth = pd.DataFrame({
        "gsis_id": ["p1", "p1", "p2", "p2"],
        "season": [2021, 2021, 2021, 2021],
        "week": [4, 5, 4, 5],
        "club_code": ["AAA", "AAA", "BBB", "BBB"],
        "position": ["RB", "RB", "WR", "WR"],
        "depth_team": [1, 2, 3, 2],     # p1 demoted 1→2, p2 promoted 3→2
    })
    con.register("_dep", depth)
    con.execute("CREATE TABLE depth_charts AS SELECT * FROM _dep")
    return con


def test_injury_events_dedupe_and_map():
    con = _fixture_con()
    inj = sources.injury_events(con, [2021])
    assert inj.duplicated(["player_key", "season", "week"]).sum() == 0
    # p1 week-5 keeps the LATER report (Out), not the earlier Questionable.
    p1 = inj[(inj["player_key"] == "p1") & (inj["week"] == 5)].iloc[0]
    assert p1["status"] == "Out" and p1["magnitude"] == pytest.approx(1.0)


def test_depth_events_sign():
    con = _fixture_con()
    dep = sources.depth_events(con, [2021])
    demo = dep[(dep["player_key"] == "p1") & (dep["status"] == "demotion")]
    promo = dep[(dep["player_key"] == "p2") & (dep["status"] == "promotion")]
    assert len(demo) == 1 and demo.iloc[0]["magnitude"] < 0   # 1→2 is a demotion
    assert len(promo) == 1 and promo.iloc[0]["magnitude"] > 0  # 3→2 is a promotion


def test_injury_events_pit_asof():
    con = _fixture_con()
    # as-of just after p2's week-6 report: p3's week-7 report (later) must not appear.
    past = sources.injury_events(con, [2021], as_of="2021-10-15")
    assert set(past["player_key"]) == {"p1", "p2"}
    assert (pd.to_datetime(past["event_ts"]) <= pd.Timestamp("2021-10-15", tz="UTC")).all()
