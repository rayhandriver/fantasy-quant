"""Unit tests for Phase 0.6 — RSS parsing and the injuries_asof PIT guard (no network)."""

from __future__ import annotations

import datetime as dt

import duckdb
import pandas as pd

from fantasy_quant.news.ingest import injuries_asof, parse_rss

_RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <title>NFL</title>
  <item>
    <title>Star WR questionable with hamstring</title>
    <link>https://example.com/a</link>
    <description>He is a game-time decision.</description>
    <guid>guid-a</guid>
    <pubDate>Wed, 25 Jun 2025 12:00:00 GMT</pubDate>
  </item>
  <item>
    <title>RB activated from IR</title>
    <link>https://example.com/b</link>
    <description>Back to practice.</description>
    <pubDate>Thu, 26 Jun 2025 09:30:00 GMT</pubDate>
  </item>
</channel></rss>"""


def test_parse_rss_extracts_items():
    df = parse_rss(_RSS, "espn")
    assert len(df) == 2
    assert set(df["source"]) == {"espn"}
    first = df.iloc[0]
    assert first["title"] == "Star WR questionable with hamstring"
    assert first["guid"] == "guid-a"
    assert first["link"] == "https://example.com/a"
    # missing <guid> falls back to the link
    assert df.iloc[1]["guid"] == "https://example.com/b"


def test_injuries_asof_is_point_in_time():
    con = duckdb.connect(":memory:")
    con.execute(
        """
        CREATE TABLE injuries AS
        SELECT * FROM (VALUES
            (2023, '00-0001', 'Questionable', TIMESTAMP '2023-10-18 15:00:00'),
            (2023, '00-0002', 'Out',          TIMESTAMP '2023-10-25 20:00:00'),
            (2023, '00-0003', 'Doubtful',     TIMESTAMP '2023-11-01 18:00:00')
        ) AS t(season, gsis_id, report_status, date_modified)
        """
    )
    asof = injuries_asof(con, dt.datetime(2023, 10, 25, 12, 0, tzinfo=dt.UTC), season=2023)
    assert len(asof) == 1  # only the 10-18 report is filed before mid-day 10-25
    latest = pd.to_datetime(asof["date_modified"], utc=True).max()
    assert latest <= pd.Timestamp("2023-10-25 12:00:00", tz="UTC")
