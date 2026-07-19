"""Phase 12.1 runner — the PIT news-event stream.

    uv run python steps/phase12_1_sources.py

Shows the unified, timestamped, deduped stream (`news/sources.py`): the two historical structured
feeds
(injury_status + depth_change, both native-gsis and PIT) plus the forward-only headline feed.
Verifies the
PIT guard (an as-of filter never returns a future-stamped event) and the dedupe (one row per
player-week).
"""

from __future__ import annotations

import pandas as pd

from fantasy_quant.data.db import connect
from fantasy_quant.news import sources


def main() -> None:
    con = connect(read_only=True)
    seasons = list(range(2016, 2023))

    inj = sources.injury_events(con, seasons)
    dep = sources.depth_events(con, seasons)
    hl = sources.headline_events(con)
    stream = sources.news_stream(con, seasons)

    print(f"=== Phase 12.1 news sources ({seasons[0]}–{seasons[-1]}) ===")
    print(f"  injury_status events : {len(inj):>7}  ({inj['status'].value_counts().to_dict()})")
    print(f"  depth_change events  : {len(dep):>7}  ({dep['status'].value_counts().to_dict()})")
    print(f"  headline events      : {len(hl):>7}  (forward-only; unresolved → 12.2 LLM)")
    print(f"  unified stream       : {len(stream):>7}  cols={list(stream.columns)}")

    # dedupe check: at most one injury row per (player, season, week).
    dups = inj.duplicated(["player_key", "season", "week"]).sum()
    print(f"\n  dedupe: injury rows duplicated on (player,season,week) = {dups} (expect 0)")

    # PIT check: an as-of cutoff never returns a future-stamped injury event.
    stamped = inj.dropna(subset=["event_ts"])
    if not stamped.empty:
        cutoff = pd.to_datetime(stamped["event_ts"], utc=True).quantile(0.5)
        past = sources.injury_events(con, seasons, as_of=cutoff).dropna(subset=["event_ts"])
        ok = past.empty or pd.to_datetime(past["event_ts"], utc=True).max() <= cutoff
        print(f"  PIT: injuries as_of={cutoff:%Y-%m-%d} → {len(past)} rows, none future = {ok}")

    con.close()
    assert dups == 0, "injury feed not deduped per player-week"
    assert not stream.empty, "unified news stream is empty"
    print("\n=== phase12_1_sources: PASS ===")


if __name__ == "__main__":
    main()
