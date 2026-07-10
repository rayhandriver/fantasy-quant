"""Unit tests for the shared raw-pull cache — the T7 raw-payload archiver (no DB/network)."""

from __future__ import annotations

import datetime as dt

from fantasy_quant.data import cache


def test_archive_text_writes_datestamped_file(tmp_path):
    p = cache.archive_text(tmp_path, "fp_PPR_wr", "<html>board</html>", "html")
    assert p is not None and p.exists()
    assert p.name == f"fp_PPR_wr_{dt.date.today().isoformat()}.html"
    assert p.read_text() == "<html>board</html>"


def test_archive_text_overwrites_within_day(tmp_path):
    cache.archive_text(tmp_path, "ffc_ppr_t10_2026", '{"players": 1}', "json")
    p = cache.archive_text(tmp_path, "ffc_ppr_t10_2026", '{"players": 528}', "json")
    # one file per day, last write wins
    assert len(list(tmp_path.glob("ffc_ppr_t10_2026_*.json"))) == 1
    assert p.read_text() == '{"players": 528}'


def test_archive_text_skips_empty_payload(tmp_path):
    assert cache.archive_text(tmp_path, "empty", "", "html") is None
    assert not list(tmp_path.iterdir())
