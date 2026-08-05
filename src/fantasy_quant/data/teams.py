"""The **pbp-side** team canon — and the fact that the repo has two of them.

★ **There are two legitimate franchise canons in this store and they disagree on one team.**

* ``adp/panel._TEAM_ALIAS`` is the **ADP-side** canon. The FFC/ECR boards write ``LAR`` for the
  Rams, so it collapses ``LA``/``STL`` → ``LAR``. ``data/reconcile.py`` already imports it, and the
  frozen ADP panel depends on it. It is correct for anything keyed to a fantasy board.
* This module is the **pbp-side** canon. ``pbp`` is already normalized to modern codes and writes
  ``LA`` for the Rams in **every** season 2014-2025 (verified: zero ``LAR``, zero ``STL``, zero
  ``OAK`` rows), so everything derived from ``pbp`` or ``participation`` — ``defense_team_week``,
  ``offense_team_week``, ``team_scheme_*`` — is keyed on ``LA``.

Applying the ADP canon to a pbp-keyed table renames the Rams to ``LAR`` and the join to every other
table in this session silently drops that franchise: 32 teams go in, 31 come out, and no error is
raised because a missing team is just an absent row. *A canon is only canonical within the source
that defines it, and the failure mode of mixing two is a silent shortfall, not an exception.*
:func:`assert_canons_disagree_only_on_la` pins the disagreement so a future edit to either one
surfaces as a test failure instead of a missing team.

⚠ This module deliberately does **not** extend ``_TEAM_ALIAS``. The four roster-only variants
(``BLT``/``CLV``/``HST``/``SL``) never occur in any table ``_canon_team`` reads, so adding them
there would have been a provable no-op — but its *targets* are the ADP codes, which are the wrong
answer here.
"""

from __future__ import annotations

import pandas as pd

#: Every franchise-code variant in the store → the code ``pbp`` uses.
#:
#: ★ **The store speaks four franchise vocabularies, not two**, each from a different upstream:
#:
#: 1. **pbp / participation** — the 32 modern codes. The target of this map.
#: 2. **nflverse alternates** (``ARZ``/``BLT``/``CLV``/``HST``/``SL``) — ``weekly_rosters``,
#:    ``snaps``.
#: 3. **PFR codes** (``GNB``/``KAN``/``LVR``/``NOR``/``NWE``/``SDG``/``SFO``/``TAM``) —
#:    ``draft_picks``, which is a PFR scrape.
#: 4. **OTC nicknames** ("Ravens", "49ers") — ``contracts``. Handled by :func:`nickname_map`,
#:    which *derives* them from ``teams_meta`` rather than hand-listing 32 more strings.
#:
#: Each was found the same way: a join came up short and the shortfall had a pattern. The count
#: matters because "we normalized the team codes" was true of two of the four.
PBP_ALIAS: dict[str, str] = {
    # relocations (pbp back-fills these to the modern franchise)
    "OAK": "LV", "SD": "LAC", "STL": "LA", "LAR": "LA", "SL": "LA", "SDG": "LAC",
    # nflverse alternate spellings
    "JAC": "JAX", "ARZ": "ARI", "WSH": "WAS", "BLT": "BAL", "CLV": "CLE", "HST": "HOU",
    # PFR codes
    "GNB": "GB", "KAN": "KC", "LVR": "LV", "NOR": "NO", "NWE": "NE", "SFO": "SF", "TAM": "TB",
}

#: The 32 modern codes as ``pbp`` writes them.
PBP_TEAMS: frozenset[str] = frozenset({
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN", "DET", "GB", "HOU",
    "IND", "JAX", "KC", "LA", "LAC", "LV", "MIA", "MIN", "NE", "NO", "NYG", "NYJ", "PHI",
    "PIT", "SEA", "SF", "TB", "TEN", "WAS",
})


def canon_team(s: pd.Series) -> pd.Series:
    """Canonical **pbp** franchise code for a pandas series of team codes."""
    return s.astype("string").str.upper().replace(PBP_ALIAS)


def canon_team_sql(col: str) -> str:
    """The same mapping as a SQL expression, so one alias table serves both call styles.

    Built from :data:`PBP_ALIAS` rather than written out, because a canon that exists twice is a
    canon that will disagree with itself.
    """
    whens = " ".join(f"when '{k}' then '{v}'" for k, v in PBP_ALIAS.items())
    return f"(case upper({col}) {whens} else upper({col}) end)"


def nickname_map(con) -> dict[str, str]:
    """OTC nickname ("Ravens") → canonical pbp code, **derived from ``teams_meta``**.

    Hand-listing 32 nicknames would be curating what a table we already ingest can answer — the
    16.5 derived-vs-curated rule, whose test is not "is this hard to look up" but "does a feed we
    already have contain it". ``teams_meta`` does.

    ``teams_meta`` carries 36 rows because relocations keep their historical entry, so three
    nicknames map to two or three abbreviations each (Chargers SD+LAC, Raiders OAK+LV, Rams
    STL+LAR+LA). Canonizing each abbreviation first collapses every collision to one modern
    franchise; the raise is there because a *new* collision would be a real change in the league.
    """
    rows = con.execute("select team_nick, team_abbr from teams_meta where team_nick is not null")
    out: dict[str, str] = {}
    for nick, abbr in rows.fetchall():
        code = PBP_ALIAS.get(str(abbr).upper(), str(abbr).upper())
        if nick in out and out[nick] != code:
            raise ValueError(
                f"nickname {nick!r} resolves to two different franchises "
                f"({out[nick]} and {code}) after canonization — reconcile deliberately."
            )
        out[nick] = code
    return out


def assert_canons_disagree_only_on_la() -> None:
    """Pin the one disagreement between the two canons, so a change to either is loud.

    If someone later "fixes" ``_TEAM_ALIAS`` to emit ``LA``, or this module to emit ``LAR``, the
    two become interchangeable and this assertion is what says so — at which point the split can
    be removed deliberately rather than discovered through a missing franchise.
    """
    from fantasy_quant.adp.panel import _TEAM_ALIAS

    adp_targets = {k: v for k, v in _TEAM_ALIAS.items() if isinstance(v, str)}
    shared = set(adp_targets) & set(PBP_ALIAS)
    disagree = {k for k in shared if adp_targets[k] != PBP_ALIAS[k]}
    if disagree != {"STL", "LA"} - (set(adp_targets) ^ set(adp_targets)) and disagree != {"STL"}:
        # the ADP canon maps LA -> LAR; this one has no LA key at all (LA is already canonical),
        # so the only *shared* key that can disagree is STL.
        raise AssertionError(
            f"the two team canons now disagree on {sorted(disagree)}, not on the documented "
            f"{{'STL'}}. Reconcile them deliberately — a silent merge drops a franchise."
        )
    if adp_targets.get("LA") != "LAR" or "LA" in PBP_ALIAS:
        raise AssertionError(
            "the Rams disagreement has moved: the ADP canon must map LA->LAR and the pbp canon "
            "must leave LA alone."
        )
