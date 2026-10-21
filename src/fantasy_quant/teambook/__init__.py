"""The **team book**: every team, every season, one page — offense, defense, players, coaching.

The Bears 2025 position & matchup book was built by hand once; this package is what turns it into a
pipeline. Three layers, each with one job:

* :mod:`~fantasy_quant.teambook.metrics` — the **registry**: what each metric means, which source
  it comes from, the first season it exists, and whether it describes scheme or results.
* :mod:`~fantasy_quant.teambook.pbp_family` — the metrics ``pbp`` + FTN can carry, computed from
  those sources **for every season**, so 2018 and the live season share one definition;
  :mod:`~fantasy_quant.teambook.build` adds the participation-only family from the scheme panel
  and assembles the books.
* :mod:`~fantasy_quant.teambook.inseason` — the same pbp family for a season still being played,
  read straight from the nflverse releases into an in-memory DuckDB (no project store required).

★ **Regular season only.** Fantasy does not count the playoffs, and the frozen
``team_scheme_season`` does include them (CHI 2025: 66.05 snaps/g with, 64.47 without). Every
number here is aggregated over regular-season weeks, which is what the hand-built book used.
"""
