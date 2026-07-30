"""Phase 1.4 — the PAR metric scorer (the simple headline number for the harness).

**Points-above-replacement (PAR):** a drafted roster's realized optimal-lineup season total minus
what a roster of freely-available *replacement-level* players would have scored. It turns the raw
starter-point totals from 1.3 into a comparable "value added over streaming replacements" number.

**Replacement level (the PLAN.md open question, resolved here):** the "last reliably-started player"
per slot in a 10-team, 9-starter league (QB/2RB/2WR/TE/FLEX+K+DST). Dedicated starters league-wide
are ``n_teams x slot``; the FLEX is split across RB/WR/TE in proportion to their dedicated demand
(2:2:1). So the replacement **ranks** are QB10, RB24, WR24, TE12, K10, DST10, and each replacement
**level** is that rank's realized season points. Adjustable via ``slots`` / ``n_teams``.

Secondary metrics: **expected wins** (all-play win% x weeks — schedule-independent) and the implied
**final standing**. (A full schedule/playoff simulation is Phase 10; this is the cheap proxy.)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from fantasy_quant.backtest import scoring
from fantasy_quant.backtest.scoring import RuleSet
from fantasy_quant.backtest.walkforward import Realized, roster_season_points
from fantasy_quant.draft.simulator import RosterSlots

_OFF_CANON = {"QB": "QB", "RB": "RB", "WR": "WR", "TE": "TE", "FB": "RB", "HB": "RB"}


# --------------------------------------------------------------------------------------------
# replacement levels
# --------------------------------------------------------------------------------------------
def replacement_ranks(slots: RosterSlots, n_teams: int = 10) -> dict[str, int]:
    """League-wide started count per position = the replacement rank (last starter).

    Each flex group's slots are allocated across the positions it makes *newly* eligible, in
    proportion to their dedicated demand. For the default RB/WR/TE flex that is the original rule,
    unchanged and bit-identical.

    **17.1 — why a superflex is allocated entirely to QB.** Groups are processed
    most-restrictive-first, and a superflex differs from the base flex **only** by admitting QB —
    RB/WR/TE depth was already priced by the narrower group. So the marginal effect of adding a
    superflex falls on quarterbacks, and the slots go there. This is the line that makes a superflex
    board draft QBs early: in a 10-team league it moves QB replacement from **QB10 to QB20**, i.e.
    from "the last starter" to "the last *second* starter", which is where the scarcity actually is.
    The old proportional-to-demand rule would have handed QB **1/6** of the superflex slot and left
    replacement at ~QB12 — a format the engine claims to support, priced as if it were 1-QB.

    *(Deliberate simplification, stated rather than hidden: a superflex is occasionally filled by a
    third RB rather than a second QB. Pricing that needs realized points, which would make this
    function impure — it is called from `projections/distribution.py` with no DB in scope. The
    residual error is small next to the QB10 → QB20 move it captures.)*
    """
    ded = {"QB": slots.qb, "RB": slots.rb, "WR": slots.wr, "TE": slots.te,
           "K": slots.k, "DST": slots.dst}
    started = {pos: float(n_teams * d) for pos, d in ded.items()}
    seen: set[str] = set()
    for count, eligible in slots.flex_groups():
        fresh = [p for p in eligible if p not in seen]
        seen |= set(eligible)
        share_over = fresh or list(eligible)
        weight_total = sum(ded[p] for p in share_over if p in ded) or 1
        for p in share_over:
            if p in started:
                started[p] += n_teams * count * ded[p] / weight_total
    return {pos: max(1, int(round(v))) for pos, v in started.items()}


@dataclass
class ReplacementLevels:
    by_pos: dict            # pos -> {"rank": int, "level": float}  (season points)
    roster_total: float     # a full replacement roster's season total
    n_teams: int

    def level(self, pos: str) -> float:
        return self.by_pos[pos]["level"]


def _season_totals(con, season: int, ruleset: RuleSet | None) -> dict[str, np.ndarray]:
    """Descending realized season-point totals per position (QB/RB/WR/TE from weekly, K, DST)."""
    off = scoring.weekly_points(con, season, ruleset).copy()
    off["cpos"] = off["position"].map(_OFF_CANON)
    off_tot = off.dropna(subset=["cpos"]).groupby(["gsis_id", "cpos"])["points"].sum().reset_index()
    out = {p: np.sort(off_tot.loc[off_tot["cpos"] == p, "points"].to_numpy())[::-1]
           for p in ("QB", "RB", "WR", "TE")}
    k = scoring.kicker_weekly_points(con, season, ruleset)
    d = scoring.dst_weekly_points(con, season, ruleset)
    out["K"] = np.sort(k.groupby("gsis_id")["points"].sum().to_numpy())[::-1]
    out["DST"] = np.sort(d.groupby("team")["points"].sum().to_numpy())[::-1]
    return out


def replacement_levels(con, season: int, slots: RosterSlots | None = None, n_teams: int = 10,
                       ruleset: RuleSet | None = None) -> ReplacementLevels:
    """Per-position replacement level (season points at the replacement rank) + the replacement
    roster's season total (FLEX = the best flex-eligible replacement level)."""
    slots = slots or RosterSlots()
    ranks = replacement_ranks(slots, n_teams)
    totals = _season_totals(con, season, ruleset)
    by_pos = {}
    for pos, rank in ranks.items():
        vals = totals[pos]
        level = float(vals[min(rank - 1, len(vals) - 1)]) if len(vals) else 0.0
        by_pos[pos] = {"rank": rank, "level": level}
    roster_total = (slots.qb * by_pos["QB"]["level"] + slots.rb * by_pos["RB"]["level"]
                    + slots.wr * by_pos["WR"]["level"] + slots.te * by_pos["TE"]["level"]
                    + slots.k * by_pos["K"]["level"] + slots.dst * by_pos["DST"]["level"])
    # Each flex group contributes its own best replacement level (17.1) — a superflex is worth the
    # best of QB/RB/WR/TE, which in practice is the QB, so a superflex roster's replacement bar is
    # correctly higher than a 1-QB one's. Single-FLEX default is unchanged.
    for count, eligible in slots.flex_groups():
        roster_total += count * max(by_pos[p]["level"] for p in eligible if p in by_pos)
    return ReplacementLevels(by_pos, float(roster_total), n_teams)


# --------------------------------------------------------------------------------------------
# PAR (primary) + secondary metrics
# --------------------------------------------------------------------------------------------
def par(roster: pd.DataFrame, realized: Realized, replacement: ReplacementLevels,
        slots: RosterSlots | None = None) -> float:
    """Points-above-replacement: the roster's realized optimal-lineup season total minus a
    replacement roster's season total."""
    slots = slots or RosterSlots()
    return roster_season_points(roster, realized, slots) - replacement.roster_total


def expected_wins(weekly_matrix) -> np.ndarray:
    """Schedule-independent **all-play** expected wins per team: each week a team earns the fraction
    of the other teams it outscores (ties count half), summed over weeks. Input: teams x weeks."""
    m = np.asarray(weekly_matrix, dtype=float)
    n = m.shape[0]
    if n < 2:
        return np.zeros(n)
    wins = np.zeros(n)
    for w in range(m.shape[1]):
        col = m[:, w]
        greater = (col[:, None] > col[None, :]).sum(axis=1)
        ties = (col[:, None] == col[None, :]).sum(axis=1) - 1  # exclude self-comparison
        wins += (greater + 0.5 * ties) / (n - 1)
    return wins


def final_standings(weekly_matrix) -> np.ndarray:
    """Implied finish (1 = best) by all-play expected wins."""
    ew = expected_wins(weekly_matrix)
    order = np.argsort(-ew, kind="stable")
    ranks = np.empty(len(ew), dtype=int)
    ranks[order] = np.arange(1, len(ew) + 1)
    return ranks
