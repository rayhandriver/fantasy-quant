"""Phase 2.3 — props-implied projection: repackage the sharp betting market as fantasy points.

Season player props (e.g. "Justin Jefferson receiving yards O/U 1275") are a real-money, often
sharper-than-ADP forecast of a player's production. For a symmetric −110/−110 over/under the **line
is ≈ the market's expected value**, so a de-vig'd set of a player's season props maps straight to
projected fantasy points via the :class:`RuleSet` — the market's own projection, in our currency.

**Data reality (the documented paid gap — see findings 0.5):** historical **preseason** player props
and season win-totals are **not available for free** — the-odds-api serves props live-only, and
nflverse `import_win_totals` returns empty. The free `game_lines` are gameday-dated lines, so they
carry **no pre-draft signal**. So :func:`season_props_projection` no-ops (returns an empty frame →
the VBD `rank_fn` falls back to ADP) until a props source is wired in (``ODDS_API_KEY`` for live,
or add a paid historical archive). The math below is built and unit-tested, so once props land,
``vbd_rank_fn(season_props_projection)`` backtests through the Phase-1 harness unchanged.
"""

from __future__ import annotations

import pandas as pd

from fantasy_quant.backtest.scoring import DEFAULT_RULESET, RuleSet

# season-prop columns → the market's expected season totals (already de-vig'd upstream).
_PROP_COLS = ("pass_yds", "pass_tds", "interceptions", "rush_yds", "rush_tds",
              "receptions", "rec_yds", "rec_tds")


def props_projection(props: pd.DataFrame, ruleset: RuleSet | None = None) -> pd.DataFrame:
    """De-vig'd **season** prop expectations → projected fantasy points, per the ruleset.

    ``props`` carries ``player_key``, ``pos`` and any subset of :data:`_PROP_COLS` (expected season
    totals). Returns ``(player_key, pos, proj_points)``. Pure — the unit-test target.
    """
    r = (ruleset or DEFAULT_RULESET).offense
    if props.empty:
        return pd.DataFrame(columns=["player_key", "pos", "proj_points"])

    def col(c: str) -> pd.Series:
        return pd.to_numeric(props[c], errors="coerce").fillna(0) if c in props.columns \
            else pd.Series(0.0, index=props.index)

    points = (col("pass_yds") * r.pass_yd + col("pass_tds") * r.pass_td
              + col("interceptions") * r.interception
              + col("rush_yds") * r.rush_yd + col("rush_tds") * r.rush_td
              + col("rec_yds") * r.rec_yd + col("rec_tds") * r.rec_td
              + col("receptions") * r.rec)
    return pd.DataFrame({"player_key": props["player_key"], "pos": props["pos"],
                         "proj_points": points.to_numpy()})


def props_available(con) -> bool:
    """Whether a historical **season props** source is loaded (currently False — the paid gap)."""
    tables = {t[0] for t in con.execute("SHOW TABLES").fetchall()}
    for t in ("season_props", "props"):
        if t in tables and con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] > 0:
            return True
    return False


def season_props_projection(con, season: int, as_of=None,
                            ruleset: RuleSet | None = None) -> pd.DataFrame:
    """Projection from stored season props for ``season``, PIT as-of the draft date.

    Returns an **empty** frame while the props table is absent/empty (the documented free-data gap),
    which makes ``vbd_rank_fn(season_props_projection)`` fall back to ADP — an honest no-op.
    """
    if not props_available(con):
        return pd.DataFrame(columns=["player_key", "pos", "proj_points"])
    aod = pd.to_datetime(as_of).date().isoformat() if as_of else f"{int(season)}-09-01"
    props = con.execute(
        f"SELECT * FROM season_props WHERE season = {int(season)} "
        f"AND snapshot_date <= DATE '{aod}'"
    ).df()
    return props_projection(props, ruleset)
