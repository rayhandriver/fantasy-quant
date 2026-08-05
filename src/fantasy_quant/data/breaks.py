"""Phase 0.13.0 — the **break map**: what a column *means* in each season, probed not asserted.

Every rate this repo computes over a multi-season column silently assumes the column was encoded
the same way throughout. That assumption is false, and T50 is the proof: from 2023 the
participation vendor stopped emitting ``NULL`` on non-pass plays and started emitting ``False``
and ``0``. Measured in the store:

===============  =============================  ==============================
season           ``was_pressure``               ``number_of_pass_rushers``
===============  =============================  ==============================
2022             null .6223 / False .2677       null .5731 / zero .0014
2023             null .0000 / False **.8523**   null .0280 / zero **.4762**
===============  =============================  ==============================

The unconditional fill rate reads **0.38 → 1.00** across that boundary and the mean number of pass
rushers reads **4.219 → 2.188**, a 48 % collapse that looks like a league-wide scheme revolution
and is entirely an encoding change: conditional on being a real dropback the mean is **4.234 →
4.289**, i.e. flat.

★ **The detector is the conservation, not the level.** A re-encoding moves probability mass out of
NULL and into one particular in-domain value, so ``Δnull ≈ −Δvalue``. A genuine trend moves a
distribution around without touching the null share, and a genuine coverage improvement raises fill
without concentrating on a single value. Requiring the two deltas to *cancel* is what separates
them, and it is why this module never needs to be told which columns or which seasons to look at —
the two motivating breaks below were both found by :func:`detect_breaks` with no column named.

★ **Classify the break; do not smooth it.** :data:`KNOWN_BREAKS` records the ones we have examined
and accepted. A normalization that made the discontinuity vanish without recording it would be the
same defect as the gate that cannot see it — so the map's job is to *label* seasons, and the
callers' job is to route their denominators through the label (:func:`sentinel_exclusion_sql`).

★ **Floors fall out of the same probe (T49).** A column that is entirely NULL in 2016-2017 and
populated from 2018 is not "missing data", it is a column whose upstream floor is 2018 — which is
exactly the case for ``defense_man_zone_type`` and ``defense_coverage_type``, whose *table* floor
is registered as 2016. :meth:`BreakMap.floor` reads that off the probe, so a per-column floor is a
measurement rather than a second hand-maintained list.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field

import pandas as pd

from fantasy_quant import config
from fantasy_quant.data import db

log = logging.getLogger(__name__)

# The newest season that has actually been played. Anything past it is fixtures, not facts.
NEWEST_COMPLETE_SEASON = max(config.STATS_SEASONS)

STATUS_OBSERVED = "observed"
STATUS_SENTINEL = "sentinel"
STATUS_ABSENT = "absent"

# A column with more distinct values than this has no meaningful "modal value", and probing it is
# a full scan for nothing. Keys, ids, timestamps and the 22-man player lists all land here.
MAX_CARDINALITY = 64

# Detection thresholds. Calibrated against the two measured breaks above, which collapse the null
# share by 0.62 and 0.55 and conserve to within 0.038 and 0.070 respectively — so the tolerance is
# loose enough to catch the messier of the two and tight enough that mass must genuinely move into
# ONE value rather than spread out across the distribution.
MIN_NULL_COLLAPSE = 0.20
CONSERVATION_TOL = 0.15

# ★ A floor transition only means something if the column becomes *materially* populated. Without
# this, pbp's rare-event columns (`tackle_for_loss_2_player_id`, `lateral_punt_returner_*`) report
# an `appears` for going from 0 to 2 non-null rows in 400,000 — technically a transition, and
# useless. 0.1 % of rows separates every real floor found in this store (the smallest is
# `defense_coverage_type` at 38 %) from every artefact.
MIN_PRESENCE = 0.001

# Column names that are never worth probing: identifiers, join keys and ingest bookkeeping.
SKIP_COLUMNS = frozenset({
    "season", "week", "game_id", "play_id", "gsis_id", "player_id", "pulled_at",
    "old_game_id", "nflverse_game_id", "players_on_play",
    "offense_players", "defense_players", "offense_names", "defense_names",
    "offense_numbers", "defense_numbers", "offense_positions", "defense_positions",
})


@dataclass(frozen=True)
class ColumnSeason:
    """One (table, column, season) cell of the map: how the column was encoded that season."""

    table: str
    column: str
    season: int
    n_rows: int
    null_share: float
    status: str
    sentinel_value: str | None = None
    shares: dict[str, float] = field(default_factory=dict)   # non-null value -> share of rows

    def share(self, value: str) -> float:
        return self.shares.get(value, 0.0)


@dataclass(frozen=True)
class Break:
    """A discontinuity in what a column means, located at the first season of the NEW regime."""

    table: str
    column: str
    season: int
    kind: str                     # null_to_sentinel | sentinel_to_null | appears | disappears
    value: str | None
    null_before: float
    null_after: float
    value_before: float
    value_after: float
    residual: float               # Δnull + Δvalue; 0.0 = mass exactly conserved

    def key(self) -> tuple[str, str, int]:
        return (self.table, self.column, self.season)

    def describe(self) -> str:
        if self.kind == "null_to_sentinel":
            return (f"{self.table}.{self.column} @{self.season}: null "
                    f"{self.null_before:.4f}->{self.null_after:.4f} while value {self.value!r} "
                    f"{self.value_before:.4f}->{self.value_after:.4f} "
                    f"(residual {self.residual:+.4f})")
        return (f"{self.table}.{self.column} @{self.season}: {self.kind} "
                f"(null {self.null_before:.4f}->{self.null_after:.4f})")


# ---------------------------------------------------------------------------------------------
# Breaks we have examined and accepted. Recording one does NOT make its rates safe — it makes the
# gate stop reporting it as news, and obliges every rate over that column to gate its denominator.
# An UNCLASSIFIED break fails `encoding_break_gate`; that asymmetry is the whole design.
# ---------------------------------------------------------------------------------------------
KNOWN_BREAKS: tuple[dict, ...] = (
    {"table": "participation", "column": "was_pressure", "season": 2023,
     "kind": "null_to_sentinel", "value": "false",
     "note": "T50 — non-pass plays moved from NULL to False. Gate the denominator on dropbacks."},
    {"table": "participation", "column": "number_of_pass_rushers", "season": 2023,
     "kind": "null_to_sentinel", "value": "0.0",
     "note": "T50 — non-pass plays moved from NULL to 0. A naive mean reads 4.22->2.19; the mean "
             "conditional on a real dropback is flat at 4.23->4.29."},
    # ★ Found by the detector, NOT by the ticket. T50 was opened on two columns; the same
    # re-encoding hit a third, and it is the one that matters most for the questions this data was
    # ingested to answer — box stacking is the RB question. Verified 2026-08-03: the 2024 rows with
    # defenders_in_box = 0 are kickoffs/punts/XP/FG/no_play/kneels/spikes, i.e. exactly the
    # non-scrimmage set that was NULL in 2022. A naive box mean reads 6.37 -> 4.87 across the
    # break; conditional on a scrimmage play it reads 6.37 -> 6.10, so the naive number overstates
    # a real, modest decline by roughly five times.
    {"table": "participation", "column": "defenders_in_box", "season": 2023,
     "kind": "null_to_sentinel", "value": "0.0",
     "severity": "benign",
     "note": "T50, third column — non-scrimmage plays moved from NULL to 0. Zero defenders in the "
             "box is not a light box, it is not a scrimmage play."},
    {"table": "ftn_charting", "column": "read_thrown", "season": 2023,
     "kind": "null_to_sentinel", "value": "0",
     "severity": "benign",
     "note": "T50, fourth column and a second vendor. Verified: the 2022 NULLs are runs/punts/"
             "kneels, the 2023 '0's are no_play/kickoff/punt/XP — the same non-dropback set."},

    # -- real-world changes, not vendor artefacts. The detector cannot tell these apart from an
    #    encoding change and should not try: both are discontinuities a pooled rate must respect.
    {"table": "injuries", "column": "report_status", "season": 2016,
     "kind": "sentinel_to_null", "value": "Probable",
     "severity": "benign",
     "note": "★ NOT a data defect — the NFL ABOLISHED the 'Probable' designation after the 2015 "
             "season. 2,702 Probable rows in 2015, zero after. Any injury-designation rate pooled "
             "across 2015/2016 is comparing two different label sets."},

    # -- live degradations. Recorded so the gate stops calling them news, NOT because they are
    #    acceptable. Each carries a register entry.
    {"table": "pfr_rec", "column": "td", "season": 2024,
     "kind": "disappears", "value": None, "severity": "defect",
     "note": "T51 — receiving TDs are 518/518 populated through 2023 and 0/523 from 2024. The "
             "ngs_air_yards failure again, in a table T47 already flags as ingested-and-unread."},
    {"table": "pfr_rush", "column": "td", "season": 2024,
     "kind": "disappears", "value": None, "severity": "defect",
     "note": "T51 — rushing TDs, same shape, same seasons."},

    # -- known structural facts about the store, already ticketed elsewhere.
    {"table": "depth_charts_all", "column": "depth_order", "season": 2025,
     "kind": "disappears", "value": None, "severity": "benign",
     "note": "The two-grain depth-chart mess: 2025 rows are the 554k snapshot series, which "
             "carries a different schema. 0.13.7 reconciles it."},
    {"table": "depth_charts_all", "column": "formation", "season": 2025,
     "kind": "disappears", "value": None, "severity": "benign", "note": "As depth_order."},
    {"table": "depth_charts_all", "column": "game_type", "season": 2025,
     "kind": "disappears", "value": None, "severity": "benign", "note": "As depth_order."},
    {"table": "adp_snapshots", "column": "bye", "season": 2025,
     "kind": "disappears", "value": None, "severity": "benign",
     "note": "FFC stopped emitting bye/start_date. Byes come from `schedules` since T44."},
    {"table": "adp_snapshots", "column": "start_date", "season": 2025,
     "kind": "disappears", "value": None, "severity": "benign", "note": "As bye."},
    {"table": "weekly_rosters", "column": "status_description_abbr", "season": 2016,
     "kind": "sentinel_to_null", "value": "A01", "severity": "benign",
     "note": "Coverage hole at the start of the series (2015 fully populated, 2016 half NULL). "
             "Zero-reader table; recorded rather than chased."},
)

# The kinds that can silently corrupt a rate, and therefore fail the gate when unclassified.
# `appears` is deliberately NOT among them: a column starting to be populated is a FLOOR, it is
# news the register wants rather than a defect, and failing on all 19 historical floors would
# leave the gate permanently red and therefore ignored.
BREAKING_KINDS = frozenset({"null_to_sentinel", "sentinel_to_null", "disappears"})


class BreakMap:
    """The probed map, plus the two questions callers actually ask of it."""

    def __init__(self, cells: Sequence[ColumnSeason], breaks: Sequence[Break]):
        self.cells = list(cells)
        self.breaks = list(breaks)
        self._by_key = {(c.table, c.column, c.season): c for c in self.cells}
        self._seasons: dict[tuple[str, str], list[int]] = defaultdict(list)
        for c in self.cells:
            self._seasons[(c.table, c.column)].append(c.season)

    # -- the two questions -------------------------------------------------------------------
    def status(self, table: str, column: str, season: int) -> str:
        cell = self._by_key.get((table, column, season))
        return cell.status if cell else STATUS_OBSERVED

    def sentinel_value(self, table: str, column: str, season: int) -> str | None:
        cell = self._by_key.get((table, column, season))
        return cell.sentinel_value if cell else None

    def floor(self, table: str, column: str, min_presence: float = MIN_PRESENCE) -> int | None:
        """T49 — the first season the column is **materially** populated: its per-COLUMN floor.

        Materiality is the same rule the detector uses, and for the same reason: pbp's rare-event
        columns (``tackle_for_loss_2_player_id``) first carry a non-NULL in whatever season that
        rare event first happened, which is a fact about football rather than about the feed. A
        floor is a claim that the column is *usable* from a season, not that a row exists.
        """
        seen = [c.season for c in self.cells
                if c.table == table and c.column == column
                and c.status != STATUS_ABSENT and (1.0 - c.null_share) >= min_presence]
        return min(seen) if seen else None

    def sentinel_seasons(self, table: str, column: str) -> list[int]:
        return sorted(c.season for c in self.cells
                      if c.table == table and c.column == column
                      and c.status == STATUS_SENTINEL)

    # -- reporting ---------------------------------------------------------------------------
    def unclassified(self) -> list[Break]:
        """Breaks of a corrupting kind that nobody has examined — the gate's failure set."""
        known = {(b["table"], b["column"], b["season"]) for b in KNOWN_BREAKS}
        return [b for b in self.breaks
                if b.kind in BREAKING_KINDS and b.key() not in known]

    def stale_classifications(self) -> list[dict]:
        """Registered breaks the probe no longer finds — a classification is a claim about the
        store, and one that has stopped being true is as wrong as a missing one."""
        seen = {b.key() for b in self.breaks}
        return [k for k in KNOWN_BREAKS
                if (k["table"], k["column"], k["season"]) not in seen]

    def floors(self) -> dict[tuple[str, str], int]:
        out = {}
        for (table, column) in self._seasons:
            f = self.floor(table, column)
            if f is not None:
                out[(table, column)] = f
        return out

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame([
            {"table": c.table, "column": c.column, "season": c.season, "n_rows": c.n_rows,
             "null_share": c.null_share, "status": c.status,
             "sentinel_value": c.sentinel_value}
            for c in self.cells
        ]).sort_values(["table", "column", "season"]).reset_index(drop=True)

    def to_dict(self) -> dict:
        return {
            "n_cells": len(self.cells),
            "n_breaks": len(self.breaks),
            "breaks": [
                {"table": b.table, "column": b.column, "season": b.season, "kind": b.kind,
                 "value": b.value, "null_before": round(b.null_before, 4),
                 "null_after": round(b.null_after, 4),
                 "value_before": round(b.value_before, 4),
                 "value_after": round(b.value_after, 4),
                 "residual": round(b.residual, 4),
                 "classified": b.key() in {(k["table"], k["column"], k["season"])
                                           for k in KNOWN_BREAKS}}
                for b in self.breaks
            ],
            "floors": {f"{t}.{c}": s for (t, c), s in sorted(self.floors().items())},
        }


# ---------------------------------------------------------------------------------------------
# probing
# ---------------------------------------------------------------------------------------------
def probeable_columns(con, table: str, max_cardinality: int = MAX_CARDINALITY) -> list[str]:
    """Columns of ``table`` that have a modal value worth probing.

    Cardinality is measured, not guessed from the type — ``defense_personnel`` is a string with
    3,306 distinct values and ``defenders_in_box`` is a float with nine, and only one of them has
    a meaningful mode.
    """
    if not db.table_exists(con, table):
        return []
    cols = [
        c for (c,) in con.execute(
            "select column_name from information_schema.columns where table_name = ? "
            "order by ordinal_position", [table]
        ).fetchall()
    ]
    cols = [c for c in cols if c not in SKIP_COLUMNS]
    if not cols:
        return []
    sel = ", ".join(f'approx_count_distinct("{c}")' for c in cols)
    counts = con.execute(f'select {sel} from "{table}"').fetchone()
    return [c for c, n in zip(cols, counts, strict=True) if n is not None and n <= max_cardinality]


def probe_column(con, table: str, column: str,
                 max_cardinality: int = MAX_CARDINALITY,
                 max_season: int | None = None) -> list[ColumnSeason]:
    """Per-season null share and value-share distribution for one column."""
    bound = "" if max_season is None else f"and season <= {int(max_season)}"
    rows = con.execute(f"""
        select season,
               cast("{column}" as varchar) as v,
               count(*) as n
        from "{table}"
        where season is not null {bound}
        group by 1, 2
    """).df()
    if rows.empty:
        return []
    out: list[ColumnSeason] = []
    for season, grp in rows.groupby("season"):
        n_rows = int(grp["n"].sum())
        if not n_rows:
            continue
        nulls = int(grp.loc[grp["v"].isna(), "n"].sum())
        null_share = nulls / n_rows
        shares = {
            str(r["v"]): int(r["n"]) / n_rows
            for _, r in grp.loc[grp["v"].notna()].iterrows()
        }
        if len(shares) > max_cardinality:
            continue
        # ★ "absent" means the column carries LITERALLY nothing that season, not "nearly nothing".
        # A near-threshold definition (>= 0.9999) makes every rare event column — pbp's
        # `forced_fumble_player_2_*`, `fumble_recovery_2_*` — flap between absent and observed on
        # a handful of rows a season, and report ~30 breaks that are an artefact of the cutoff
        # rather than facts about the data. A floor is a categorical claim; measure it that way.
        status = STATUS_ABSENT if not shares else STATUS_OBSERVED
        out.append(ColumnSeason(table=table, column=column, season=int(season), n_rows=n_rows,
                                null_share=round(null_share, 6), status=status, shares=shares))
    return sorted(out, key=lambda c: c.season)


# ---------------------------------------------------------------------------------------------
# detection — pure, so it can be unit-tested on a planted break (B1)
# ---------------------------------------------------------------------------------------------
def detect_breaks(cells: Sequence[ColumnSeason], *,
                  min_null_collapse: float = MIN_NULL_COLLAPSE,
                  conservation_tol: float = CONSERVATION_TOL,
                  min_presence: float = MIN_PRESENCE) -> list[Break]:
    """Find encoding discontinuities in a probed series. **Nothing here names a column.**

    Two families:

    * ``null_to_sentinel`` / ``sentinel_to_null`` — the null share moves sharply and **one**
      in-domain value moves sharply the other way, and the two cancel to within
      ``conservation_tol``. That cancellation is the whole discriminator: a real improvement in
      coverage raises fill without piling onto a single value, and a real trend moves values
      around without touching the null share.
    * ``appears`` / ``disappears`` — the column goes from entirely-NULL to populated or back. That
      is a floor, not a re-encoding, and it is reported separately so the two never get conflated.
    """
    by_col: dict[tuple[str, str], list[ColumnSeason]] = defaultdict(list)
    for c in cells:
        by_col[(c.table, c.column)].append(c)

    found: list[Break] = []
    for (table, column), series in by_col.items():
        series = sorted(series, key=lambda c: c.season)
        for prev, cur in zip(series, series[1:], strict=False):
            prev_material = (1.0 - prev.null_share) >= min_presence
            cur_material = (1.0 - cur.null_share) >= min_presence
            if prev.status == STATUS_ABSENT and cur_material:
                found.append(Break(table, column, cur.season, "appears", None,
                                   prev.null_share, cur.null_share, 0.0, 0.0, 0.0))
                continue
            if prev_material and cur.status == STATUS_ABSENT:
                found.append(Break(table, column, cur.season, "disappears", None,
                                   prev.null_share, cur.null_share, 0.0, 0.0, 0.0))
                continue
            if prev.status == STATUS_ABSENT or cur.status == STATUS_ABSENT:
                continue   # a trace-populated season on either side: not a floor, not a break

            d_null = cur.null_share - prev.null_share
            if abs(d_null) < min_null_collapse:
                continue
            # the single value that moved furthest against the null share
            candidates = set(prev.shares) | set(cur.shares)
            if not candidates:
                continue
            best, best_delta = None, 0.0
            for v in candidates:
                d_val = cur.share(v) - prev.share(v)
                if -d_null * d_val > 0 and abs(d_val) > abs(best_delta):
                    best, best_delta = v, d_val
            if best is None:
                continue
            if abs(best_delta) < min_null_collapse * 0.5:
                continue
            residual = d_null + best_delta
            if abs(residual) > conservation_tol:
                continue
            kind = "null_to_sentinel" if d_null < 0 else "sentinel_to_null"
            found.append(Break(table, column, cur.season, kind, best,
                               prev.null_share, cur.null_share,
                               prev.share(best), cur.share(best), residual))
    return sorted(found, key=lambda b: (b.table, b.column, b.season))


def base_tables(con) -> list[str]:
    """Base tables only — ``SHOW TABLES`` also lists views, and a view inherits its parent's
    breaks, so probing both reports every finding twice as though they were independent."""
    return [
        t for (t,) in con.execute(
            "select table_name from information_schema.tables where table_type = 'BASE TABLE' "
            "order by table_name"
        ).fetchall()
    ]


def build_break_map(con, tables: Sequence[str] | None = None,
                    max_cardinality: int = MAX_CARDINALITY,
                    max_season: int | None = NEWEST_COMPLETE_SEASON) -> BreakMap:
    """Probe the store and classify. ``tables`` defaults to every base table carrying a season.

    ``max_season`` defaults to the newest **completed** season. A live or future season is
    partially populated by definition — 2026 has fixtures but no scores — and comparing it to a
    finished one reports the calendar as a data break.
    """
    if tables is None:
        tables = [t for t in base_tables(con) if _has_season(con, t)]
    cells: list[ColumnSeason] = []
    for t in tables:
        for col in probeable_columns(con, t, max_cardinality):
            cells.extend(probe_column(con, t, col, max_cardinality, max_season))
    breaks = detect_breaks(cells)

    # a season on the new side of a null->sentinel break is where the column carries a sentinel
    marked: list[ColumnSeason] = []
    onset = {(b.table, b.column): (b.season, b.value)
             for b in breaks if b.kind == "null_to_sentinel"}
    for c in cells:
        hit = onset.get((c.table, c.column))
        if hit and c.season >= hit[0] and c.status == STATUS_OBSERVED:
            marked.append(ColumnSeason(c.table, c.column, c.season, c.n_rows, c.null_share,
                                       STATUS_SENTINEL, hit[1], c.shares))
        else:
            marked.append(c)
    return BreakMap(marked, breaks)


def _has_season(con, table: str) -> bool:
    return bool(con.execute(
        "select count(*) from information_schema.columns "
        "where table_name = ? and column_name = 'season'", [table]
    ).fetchone()[0])


# ---------------------------------------------------------------------------------------------
# routing a denominator through the map
# ---------------------------------------------------------------------------------------------
def sentinel_exclusion_sql(bm: BreakMap, table: str, column: str, alias: str = "") -> str:
    """A SQL predicate that drops sentinel rows, and only in the seasons that carry them.

    Returns ``"true"`` when the column has no sentinel regime, so callers can always ``and`` it in
    without branching — the point being that a caller should not have to know whether a particular
    column happens to be affected.
    """
    seasons = bm.sentinel_seasons(table, column)
    if not seasons:
        return "true"
    value = bm.sentinel_value(table, column, seasons[0])
    p = f"{alias}." if alias else ""
    lo = min(seasons)
    return (f'not ({p}season >= {lo} and cast({p}"{column}" as varchar) '
            f"= '{value}')")
