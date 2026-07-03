"""Unit tests for Phase 0.5 — odds math and props parsing (no network)."""

from __future__ import annotations

import numpy as np

from fantasy_quant.markets.odds_ingest import (
    american_to_prob,
    devig,
    fair_two_way,
    implied_team_total,
    parse_props_payload,
)


def test_american_to_prob_known_values():
    assert abs(american_to_prob(+100) - 0.5) < 1e-9
    assert abs(american_to_prob(+150) - 0.4) < 1e-9
    assert abs(american_to_prob(-110) - 0.52380952) < 1e-6


def test_devig_proportional_sums_to_one():
    out = devig([american_to_prob(-110), american_to_prob(-110)])
    assert abs(out.sum() - 1.0) < 1e-12
    assert abs(out[0] - 0.5) < 1e-9


def test_fair_two_way_balanced_market_is_half():
    a, b = fair_two_way([-110], [-110])
    assert abs(a[0] - 0.5) < 1e-9 and abs(a[0] + b[0] - 1.0) < 1e-12


def test_implied_team_total_sign_convention():
    # KC home favored by 4 in a 53-point game -> KC 28.5, opp 24.5
    home, away = implied_team_total([53.0], [4.0])
    assert abs(home[0] - 28.5) < 1e-9
    assert abs(away[0] - 24.5) < 1e-9


def test_parse_props_payload_devigs_over_under():
    events = [{
        "id": "evt1", "commence_time": "2024-09-08T17:00:00Z",
        "home_team": "MIN", "away_team": "NYG",
        "bookmakers": [{
            "key": "draftkings", "last_update": "2024-09-07T12:00:00Z",
            "markets": [{
                "key": "player_reception_yds",
                "outcomes": [
                    {"name": "Over", "description": "Justin Jefferson",
                     "price": 1.91, "point": 85.5},
                    {"name": "Under", "description": "Justin Jefferson",
                     "price": 1.91, "point": 85.5},
                ],
            }],
        }],
    }]
    df = parse_props_payload(events)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["player"] == "Justin Jefferson"
    assert row["line"] == 85.5
    assert abs(row["fair_over_prob"] - 0.5) < 1e-9  # balanced -110-ish -> fair 0.5
    assert not np.isnan(row["fair_over_prob"])
