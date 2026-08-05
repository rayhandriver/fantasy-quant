"""Phase 0.13.1 — build the **historical** half of ``reference/defense_coaches.csv`` (T48).

The 2026 half was drafted, web-verified, corrected and **signed off by the user on 2026-08-03**
(preserved verbatim at ``reference/defense_coaches_2026_signed_off_2026-08-03.csv``). This step adds
what 0.13.8 actually needs: the **prior regimes of those 32 play-callers**, so a defensive scheme
fact can be attributed to a person and a tenure instead of to a team-anonymous season.

★ **The file is GENERATED, never hand-edited** — the 16.5 lesson applied to a curated artefact.
The research lives in :data:`REGIMES` below, where it can be diffed, re-run and argued with; the CSV
is its output. Hand-editing a row would put the artefact and its provenance out of sync, which is
the failure mode 16.5 diagnosed when the situation board was researched by hand and missed 16 of 23
team changes a feed already knew.

★ **``head_coach`` is auto-filled from ``pbp`` (exact, PIT) and each regime also carries the head
coach the researcher EXPECTED.** That redundancy is the point: the scaffold makes the column free,
and the expectation makes the audit meaningful. *A curated row whose head coach disagrees with pbp
is a row about the wrong regime* — which is how the offensive table got 157 rows checked for free.
Auto-filling alone would make the audit vacuous, so both are recorded and compared.

★ **Scope (user decision, 2026-08-03): mirror ``coaches.csv``** — 2026 plus the prior regimes of the
2026 play-callers, *not* a complete defensive staff history of all 32 teams. The rows that scope
omits are regimes nothing will ever fingerprint.

★ **Inclusion rule: the named person called the defense for the MAJORITY of the team's games.**
Seasons that fail it are **excluded and documented in an adjacent row's notes** rather than averaged
— ``fingerprint.py``'s own rule, and the reason five of these entries exist only as prose:

- **NYJ 2015-18** — Kacy Rodgers called it, not Bowles (Bowles covered only part of 2018, during
  Rodgers' illness). The row that *looks* obvious is the one the research deleted.
- **MIA 2020-21** — Josh Boyer had full control; Flores' Miami play-calling is a 2019-only claim,
  and in 2019 the caller was Patrick Graham.
- **NYJ 2025** — Aaron Glenn said publicly he would not call plays; Steve Wilks did, until his
  firing with three games left (15 of 18 ⇒ still a majority).
- **WAS 2024-25** — Joe Whitt Jr. called it in 2024, and in 2025 until Quinn took it off him on
  10 Nov. Quinn's share of 2025 is a minority, so 2025 is **dropped, not split**.
- **ATL 2016 / NO 2015 / ATL 2020(Quinn) / HOU 2025(Ryans)** — each a mid-season handover where the
  2026 play-caller is on the *minority* side.

★ **Four attributions the web check OVERTURNED before they were written.** Every one would have
invented a regime that does not exist: Gannon did **not** call Arizona's defense (Rallis did, with
"complete faith" handed over on day one) · Saleh did **not** call the Jets' defense (Ulbrich did,
all four seasons, and Saleh said so at his hiring) · Morris has **never** called Atlanta's defense
as head coach (Lake 2024, Ulbrich 2025) · Bowles did **not** call the Jets' defense. *The title is
not the job* — the offensive table's Monken lesson, reproduced four times on the first pass.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from fantasy_quant.data import db
from fantasy_quant.situation import defense_coaches as dc
from fantasy_quant.situation.coaches import audit_against_pbp, head_coach_scaffold, move_graph_check

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis" / "phase0_13_1_defense_history.json"
SIGNED_OFF = ROOT / "reference" / "defense_coaches_2026_signed_off_2026-08-03.csv"

NONE = dc.NO_COORDINATOR
UNK = dc.UNKNOWN

#: One entry per **contiguous regime**: the seasons a 2026 play-caller called that team's defense.
#: ``dc_title`` is who held the coordinator title (the play-caller himself unless stated).
#: ``expected_hc`` is the researcher's belief, audited against pbp — a str, or {season: str} when
#: the head coach changed underneath the regime. ``in_house`` applies to the FIRST season only;
#: later seasons of the same regime are 1 by construction.
REGIMES: tuple[dict, ...] = (
    # ---- ARI / Nick Rallis ------------------------------------------------------------------
    dict(play_caller="Nick Rallis", team="ARI", seasons=(2023, 2024, 2025), dc_title=None,
         hc_calls=0, in_house=0, confidence="high", expected_hc="Jonathan Gannon",
         note="★ OVERTURNED A DRAFT ROW: Gannon is a defensive head coach and did NOT call it — "
              "he handed the defense to Rallis on hiring ('complete faith'). Rallis was Gannon's "
              "PHI linebackers coach and came with him, so 2023 is in_house=0."),
    # ---- ATL/NYJ / Jeff Ulbrich -------------------------------------------------------------
    dict(play_caller="Jeff Ulbrich", team="ATL", seasons=(2020,), dc_title=None, hc_calls=0,
         in_house=1, confidence="high", expected_hc="Raheem Morris",
         note="Promoted to DC for the FINAL 11 GAMES of 2020 — a majority, so the season counts to "
              "him. Quinn (HC, fired after week 5) called the first stretch and is excluded; pbp's "
              "coach of record for 2020 is the interim, Morris."),
    dict(play_caller="Jeff Ulbrich", team="NYJ", seasons=(2021, 2022, 2023, 2024), dc_title=None,
         hc_calls=0, in_house=0, confidence="high", expected_hc="Robert Saleh",
         note="★ OVERTURNED A DRAFT ROW: Saleh — himself a former SF play-caller — publicly handed "
              "game-day control to Ulbrich on hiring and never took it back. So these four seasons "
              "belong to Ulbrich and Saleh has NO Jets play-calling regime."),
    dict(play_caller="Jeff Ulbrich", team="ATL", seasons=(2025,), dc_title=None, hc_calls=0,
         in_house=0, confidence="high", expected_hc="Raheem Morris",
         note="Returned to ATL as DC and stated he would call plays on game days."),
    # ---- LAC / Jesse Minter -----------------------------------------------------------------
    dict(play_caller="Jesse Minter", team="LAC", seasons=(2024, 2025), dc_title=None, hc_calls=0,
         in_house=0, confidence="med", expected_hc="Jim Harbaugh",
         note="Followed Jim Harbaugh from Michigan. The two NFL seasons behind the 2026 BAL row."),
    # ---- DEN/CAR / Ejiro Evero --------------------------------------------------------------
    dict(play_caller="Ejiro Evero", team="DEN", seasons=(2022,), dc_title=None, hc_calls=0,
         in_house=0, confidence="med", expected_hc="Nathaniel Hackett",
         note="One season as DEN DC under Hackett before CAR."),
    dict(play_caller="Ejiro Evero", team="CAR", seasons=(2023, 2024, 2025), dc_title=None,
         hc_calls=0, in_house=0, confidence="med",
         expected_hc={2023: "Frank Reich", 2024: "Dave Canales", 2025: "Dave Canales"},
         note="Survived the Reich→Canales head-coaching change, which is why the regime is "
              "continuous while the head coach column is not."),
    # ---- NO/CHI / Dennis Allen --------------------------------------------------------------
    dict(play_caller="Dennis Allen", team="NO", seasons=(2016, 2017, 2018, 2019, 2020, 2021),
         dc_title=None, hc_calls=0, in_house=1, confidence="med", expected_hc="Sean Payton",
         note="⚠ 2015 EXCLUDED: Rob Ryan opened the season as DC and Allen only took over after "
              "Ryan's in-season firing — a minority of games. Allen was on staff in 2015 as a "
              "senior defensive assistant, hence in_house=1 for 2016."),
    dict(play_caller="Dennis Allen", team="NO", seasons=(2022, 2023, 2024), dc_title=UNK,
         hc_calls=1, in_house=1, confidence="high", expected_hc="Dennis Allen",
         note="Kept the calls after promotion to head coach — 'there really is still one voice and "
              "that's mine' — over co-coordinators. ⚠ 2024 is MARGINAL: he was fired after week 9, "
              "so his share is 9 of 17, a majority by one game. The DC title is (unknown) because "
              "New Orleans carried co-coordinators the schema cannot represent; they are "
              "named here "
              "rather than guessed at: Kris Richard and Ryan Nielsen (2022)."),
    dict(play_caller="Dennis Allen", team="CHI", seasons=(2025,), dc_title=None, hc_calls=0,
         in_house=0, confidence="med", expected_hc="Ben Johnson",
         note="A former head coach running his own defense under an offensive head coach."),
    # ---- CIN / Al Golden --------------------------------------------------------------------
    dict(play_caller="Al Golden", team="CIN", seasons=(2025,), dc_title=None, hc_calls=0,
         in_house=0, confidence="med", expected_hc="Zac Taylor",
         note="Arrived from Notre Dame; CIN LB coach 2020-21 but not on the 2024 staff, so 0."),
    # ---- MIA/ARI/DEN / Vance Joseph ---------------------------------------------------------
    dict(play_caller="Vance Joseph", team="MIA", seasons=(2016,), dc_title=None, hc_calls=0,
         in_house=0, confidence="med", expected_hc="Adam Gase",
         note="One season as MIA DC, which is what got him the DEN head-coaching job."),
    dict(play_caller="Vance Joseph", team="ARI", seasons=(2019, 2020, 2021, 2022), dc_title=None,
         hc_calls=0, in_house=0, confidence="med", expected_hc="Kliff Kingsbury",
         note="⚠ His DEN 2017-18 HEAD-COACHING seasons are deliberately absent: Joe Woods held the "
              "coordinator job and the calls. A head-coaching tenure is not a play-calling "
              "regime."),
    dict(play_caller="Vance Joseph", team="DEN", seasons=(2023, 2024, 2025), dc_title=None,
         hc_calls=0, in_house=0, confidence="med", expected_hc="Sean Payton",
         note="Second DEN stint, this time as coordinator."),
    # ---- DET / Kelvin Sheppard --------------------------------------------------------------
    dict(play_caller="Kelvin Sheppard", team="DET", seasons=(2025,), dc_title=None, hc_calls=0,
         in_house=1, confidence="med", expected_hc="Dan Campbell",
         note="Internal promotion from the LB room after Glenn left for the NYJ head job."),
    # ---- PHI / Jonathan Gannon --------------------------------------------------------------
    dict(play_caller="Jonathan Gannon", team="PHI", seasons=(2021, 2022), dc_title=None,
         hc_calls=0, in_house=0, confidence="high", expected_hc="Nick Sirianni",
         note="★ Gannon's ONLY play-calling regime. His 2023-25 ARI head-coaching seasons are not "
              "here because Rallis called that defense — see the ARI entry."),
    # ---- SF/HOU / DeMeco Ryans --------------------------------------------------------------
    dict(play_caller="DeMeco Ryans", team="SF", seasons=(2021, 2022), dc_title=None, hc_calls=0,
         in_house=1, confidence="med", expected_hc="Kyle Shanahan",
         note="Promoted from the SF inside-linebackers room; the regime that produced the "
              "HOU job."),
    dict(play_caller="DeMeco Ryans", team="HOU", seasons=(2023, 2024), dc_title="Matt Burke",
         hc_calls=1, in_house=0, confidence="high", expected_hc="DeMeco Ryans",
         note="⚠ 2025 EXCLUDED and it matters for 2026: after an 0-3 start Ryans RELINQUISHED the "
              "calls to Burke, who then called most of the season. See the HOU 2025 entry — and "
              "note the signed-off 2026 row asserts Burke has held the title 'without the calls', "
              "which 2025 contradicts."),
    dict(play_caller="Matt Burke", team="HOU", seasons=(2025,), dc_title=None, hc_calls=0,
         in_house=1, confidence="high", expected_hc="DeMeco Ryans",
         note="★ NOT a 2026 play-caller in our scope, but included because the majority rule "
              "assigns "
              "2025 to him: dropping it would silently credit the season to Ryans. Burke took over "
              "after week 3 and called the rest."),
    # ---- CIN/IND / Lou Anarumo --------------------------------------------------------------
    dict(play_caller="Lou Anarumo", team="CIN", seasons=(2019, 2020, 2021, 2022, 2023, 2024),
         dc_title=None, hc_calls=0, in_house=1, confidence="med", expected_hc="Zac Taylor",
         note="Six seasons — the longest regime in this file after Spagnuolo. Promoted from the "
              "CIN secondary, hence in_house=1."),
    dict(play_caller="Lou Anarumo", team="IND", seasons=(2025,), dc_title=None, hc_calls=0,
         in_house=0, confidence="med", expected_hc="Shane Steichen", note=""),
    # ---- JAX / Anthony Campanile ------------------------------------------------------------
    dict(play_caller="Anthony Campanile", team="JAX", seasons=(2025,), dc_title=None, hc_calls=0,
         in_house=0, confidence="med", expected_hc="Liam Coen",
         note="First DC job, arriving from the GB linebackers room with Coen."),
    # ---- NYG/KC / Steve Spagnuolo -----------------------------------------------------------
    dict(play_caller="Steve Spagnuolo", team="NYG", seasons=(2015, 2016, 2017), dc_title=None,
         hc_calls=0, in_house=0, confidence="med",
         expected_hc={2015: "Tom Coughlin", 2016: "Ben McAdoo", 2017: "Ben McAdoo"},
         note="Second NYG stint. Survived the Coughlin→McAdoo change."),
    dict(play_caller="Steve Spagnuolo", team="KC", seasons=(2019, 2020, 2021, 2022, 2023, 2024,
                                                            2025), dc_title=None, hc_calls=0,
         in_house=0, confidence="high", expected_hc="Andy Reid",
         note="Seven unbroken seasons — the longest defensive regime in the league and the "
              "single best-conditioned fingerprint subject in this file."),
    # ---- LAR / Chris Shula ------------------------------------------------------------------
    dict(play_caller="Chris Shula", team="LAR", seasons=(2024, 2025), dc_title=None, hc_calls=0,
         in_house=1, confidence="med", expected_hc="Sean McVay",
         note="Internal promotion when Morris left for the ATL head job."),
    # ---- NE/MIN / Brian Flores --------------------------------------------------------------
    dict(play_caller="Brian Flores", team="NE", seasons=(2018,), dc_title=NONE, hc_calls=0,
         in_house=1, confidence="high", expected_hc="Bill Belichick",
         note="★ THE (none) SENTINEL EARNING ITS KEEP: New England carried NO defensive "
              "coordinator "
              "in 2018 after Patricia left for DET. Flores called the defense as linebackers coach "
              "— title-less play-calling, the exact inverse of the Monken case, and a regime that "
              "would be invisible to any table keyed on the DC title."),
    dict(play_caller="Brian Flores", team="MIN", seasons=(2023, 2024, 2025), dc_title=None,
         hc_calls=0, in_house=0, confidence="med", expected_hc="Kevin O'Connell",
         note="⚠ His MIA 2019-21 HEAD-COACHING seasons are absent: Patrick Graham called 2019 and "
              "Josh Boyer had full control of 2020-21. The heavy-blitz identity 0.13.2 should "
              "reproduce belongs to these three seasons."),
    # ---- LAR/LAC/NO / Brandon Staley --------------------------------------------------------
    dict(play_caller="Brandon Staley", team="LAR", seasons=(2020,), dc_title=None, hc_calls=0,
         in_house=0, confidence="med", expected_hc="Sean McVay",
         note="The one season that produced the LAC head-coaching job."),
    dict(play_caller="Brandon Staley", team="LAC", seasons=(2021, 2022, 2023), dc_title=UNK,
         hc_calls=1, in_house=0, confidence="high", expected_hc="Brandon Staley",
         note="Called the defense himself throughout his head-coaching tenure and said so "
              "repeatedly and publicly. ⚠ 2023 ended in an in-season firing (week 15) but his "
              "share is a clear majority. DC title left (unknown) rather than guessed."),
    dict(play_caller="Brandon Staley", team="NO", seasons=(2025,), dc_title=None, hc_calls=0,
         in_house=0, confidence="med", expected_hc="Kellen Moore", note=""),
    # ---- TEN / Dennard Wilson ---------------------------------------------------------------
    dict(play_caller="Dennard Wilson", team="TEN", seasons=(2024, 2025), dc_title=None, hc_calls=0,
         in_house=0, confidence="med", expected_hc="Brian Callahan", note=""),
    # ---- DET / Aaron Glenn ------------------------------------------------------------------
    dict(play_caller="Aaron Glenn", team="DET", seasons=(2021, 2022, 2023, 2024), dc_title=None,
         hc_calls=0, in_house=0, confidence="high", expected_hc="Dan Campbell",
         note="★ His NYJ 2025 head-coaching season is deliberately absent: Glenn said at his "
              "introduction he would NOT call plays, and Steve Wilks called them until being fired "
              "with three games left (15 of 18 — still Wilks' majority). The signed-off 2026 row "
              "has Glenn taking the calls, which would be a CHANGE from 2025, not a continuation."),
    # ---- SF/CHI/DEN/MIA/PHI / Vic Fangio ----------------------------------------------------
    dict(play_caller="Vic Fangio", team="SF", seasons=(2014,), dc_title=None, hc_calls=0,
         in_house=1, confidence="med", expected_hc="Jim Harbaugh",
         note="The last season of his 2011-14 SF regime; earlier seasons are outside the "
              "pbp window."),
    dict(play_caller="Vic Fangio", team="CHI", seasons=(2015, 2016, 2017, 2018), dc_title=None,
         hc_calls=0, in_house=0, confidence="med",
         expected_hc={2015: "John Fox", 2016: "John Fox", 2017: "John Fox", 2018: "Matt Nagy"},
         note="Survived the Fox→Nagy change; the 2018 defense produced the DEN head-coaching job."),
    dict(play_caller="Vic Fangio", team="DEN", seasons=(2019, 2020, 2021), dc_title="Ed Donatell",
         hc_calls=1, in_house=0, confidence="high", expected_hc="Vic Fangio",
         note="★ Kept the calls as head coach for all three seasons — Donatell held the title and "
              "followed him from CHI, and the question of handing play-calling over was asked "
              "publicly and declined. The most fingerprint-able person in this file: five "
              "regimes."),
    dict(play_caller="Vic Fangio", team="MIA", seasons=(2023,), dc_title=None, hc_calls=0,
         in_house=0, confidence="med", expected_hc="Mike McDaniel", note="One season."),
    dict(play_caller="Vic Fangio", team="PHI", seasons=(2024, 2025), dc_title=None, hc_calls=0,
         in_house=0, confidence="med", expected_hc="Nick Sirianni",
         note="The regime the 2026 lineage file leans on most."),
    # ---- MIA/NYG/LV / Patrick Graham --------------------------------------------------------
    dict(play_caller="Patrick Graham", team="MIA", seasons=(2019,), dc_title=None, hc_calls=0,
         in_house=0, confidence="high", expected_hc="Brian Flores",
         note="★ Graham was coordinator AND play-caller in 2019 under Flores — which is why Flores "
              "gets no MIA row. Two 2026 play-callers were on this one staff."),
    dict(play_caller="Patrick Graham", team="NYG", seasons=(2020, 2021), dc_title=None, hc_calls=0,
         in_house=0, confidence="med", expected_hc="Joe Judge", note=""),
    dict(play_caller="Patrick Graham", team="LV", seasons=(2022, 2023, 2024, 2025), dc_title=None,
         hc_calls=0, in_house=0, confidence="med",
         expected_hc={2022: "Josh McDaniels", 2023: "Antonio Pierce", 2024: "Antonio Pierce",
                      2025: "Pete Carroll"},
         note="Four seasons across THREE head coaches — the clearest case in the file for keying a "
              "fingerprint to the coordinator rather than the staff."),
    # ---- BAL/SEA / Mike Macdonald -----------------------------------------------------------
    dict(play_caller="Mike Macdonald", team="BAL", seasons=(2022, 2023), dc_title=None, hc_calls=0,
         in_house=0, confidence="med", expected_hc="John Harbaugh",
         note="Returned from Michigan to run Baltimore's defense."),
    dict(play_caller="Mike Macdonald", team="SEA", seasons=(2024, 2025), dc_title="Aden Durde",
         hc_calls=1, in_house=0, confidence="high", expected_hc="Mike Macdonald",
         note="★ Calls it himself as head coach with Durde holding the title — and in 2025 became "
              "the first head coach to be primary defensive play-caller for a Super Bowl winner."),
    # ---- LAR / Raheem Morris ----------------------------------------------------------------
    dict(play_caller="Raheem Morris", team="LAR", seasons=(2021, 2022, 2023), dc_title=None,
         hc_calls=0, in_house=0, confidence="high", expected_hc="Sean McVay",
         note="★ His ATL 2024-25 HEAD-COACHING seasons are absent — Jimmy Lake called 2024 and "
              "Ulbrich 2025 — and so is ATL 2020, where Ulbrich called the final 11 as DC while "
              "Morris was interim HEAD coach. Morris has exactly one play-calling regime."),
    # ---- ARI/TB / Todd Bowles ---------------------------------------------------------------
    dict(play_caller="Todd Bowles", team="ARI", seasons=(2014,), dc_title=None, hc_calls=0,
         in_house=1, confidence="med", expected_hc="Bruce Arians",
         note="The regime that produced the NYJ head-coaching job."),
    dict(play_caller="Todd Bowles", team="TB", seasons=(2019, 2020, 2021), dc_title=None,
         hc_calls=0, in_house=0, confidence="med", expected_hc="Bruce Arians",
         note="⚠ NYJ 2015-18 EXCLUDED: Kacy Rodgers called those defenses. Bowles took the calls "
              "only temporarily in 2018 during Rodgers' illness — a minority of games, and exactly "
              "the kind of row a title-keyed table would have wrongly credited to the head coach."),
    dict(play_caller="Todd Bowles", team="TB", seasons=(2022, 2023, 2024, 2025), dc_title=UNK,
         hc_calls=1, in_house=1, confidence="high", expected_hc="Todd Bowles",
         note="Kept the calls on promotion to head coach — one of only two head coaches calling a "
              "defense in 2025. DC title is (unknown): Tampa appears to have carried none under "
              "him, but 'appears to' is not a verification, so the weaker sentinel is used."),
    # ---- SF / Robert Saleh ------------------------------------------------------------------
    dict(play_caller="Robert Saleh", team="SF", seasons=(2017, 2018, 2019, 2020), dc_title=None,
         hc_calls=0, in_house=0, confidence="med", expected_hc="Kyle Shanahan",
         note="The regime that produced the NYJ head-coaching job."),
    dict(play_caller="Robert Saleh", team="SF", seasons=(2025,), dc_title=None, hc_calls=0,
         in_house=0, confidence="med", expected_hc="Kyle Shanahan",
         note="⚠ NYJ 2021-24 EXCLUDED — he handed the calls to Ulbrich and never took them back. "
              "Returned to SF as coordinator after the Jets firing."),
    # ---- SEA/ATL/DAL / Dan Quinn ------------------------------------------------------------
    dict(play_caller="Dan Quinn", team="SEA", seasons=(2014,), dc_title=None, hc_calls=0,
         in_house=1, confidence="med", expected_hc="Pete Carroll",
         note="Second season of the 2013-14 regime that produced the ATL head-coaching job."),
    dict(play_caller="Dan Quinn", team="ATL", seasons=(2017,), dc_title="Marquand Manuel",
         hc_calls=1, in_house=1, confidence="low", expected_hc="Dan Quinn",
         note="⚠ THE LEAST CERTAIN ROW IN THE FILE. Quinn took the calls from Richard Smith during "
              "2016 and gave them to Manuel at some point around 2018; sources conflict on whether "
              "2017 was his or Manuel's. 2016 is EXCLUDED outright because an in-season handover "
              "cannot be shown to clear the majority bar. Treat 2017 as unresolved, not as fact."),
    dict(play_caller="Dan Quinn", team="ATL", seasons=(2019,), dc_title=None, hc_calls=1,
         in_house=1, confidence="high", expected_hc="Dan Quinn",
         note="Took the coordinator job himself after firing Manuel — so head coach, coordinator "
              "and play-caller are one person. ⚠ 2020 EXCLUDED: fired after week 5, and Ulbrich "
              "called the final 11 (see the ATL 2020 entry)."),
    dict(play_caller="Dan Quinn", team="DAL", seasons=(2021, 2022, 2023), dc_title=None,
         hc_calls=0, in_house=0, confidence="med", expected_hc="Mike McCarthy",
         note="⚠ WAS 2024-25 EXCLUDED although he is the head coach there: Joe Whitt Jr. called "
              "2024, and called 2025 until Quinn took over on 10 Nov — a minority share. Per the "
              "rule the split season is DROPPED, not averaged and not half-credited."),
)

#: The mentor fallback, for 2026 play-callers with no regime of their own. Deliberately minimal
#: (user decision): a row only where the residue actually needs one AND the mentor is himself a
#: play-caller in this table — otherwise the fallback resolves to nothing, which is worse than
#: silence. Three first-timers (LAC O'Leary, MIA Duggan, NE Kuhr) therefore get NO row and 0.13.8
#: must stay silent on them, exactly as 16.4 stays silent on five offensive first-timers.
LINEAGE: tuple[dict, ...] = (
    dict(play_caller="Jim Leonhard", season=2026, team="BUF", mentor="Vance Joseph",
         learned_at="DEN", learned_seasons="2024-2025",
         role="assistant head coach / defensive pass game coordinator", confidence="med",
         notes="Wisconsin DC 2017-22 (college, not in scope). No NFL play-calling regime."),
    dict(play_caller="Mike Rutenberg", season=2026, team="CLE", mentor="Jeff Ulbrich",
         learned_at="ATL", learned_seasons="2025", role="defensive pass game coordinator",
         confidence="med", notes="First-time DC; one season under the mentor is a thin prior."),
    dict(play_caller="Christian Parker", season=2026, team="DAL", mentor="Vic Fangio",
         learned_at="PHI", learned_seasons="2024-2025", role="defensive backs / pass game "
         "coordinator", confidence="med",
         notes="The Fangio tree, and the mentor with the most regimes in the file."),
    dict(play_caller="Rob Leonard", season=2026, team="LV", mentor="Patrick Graham",
         learned_at="LV", learned_seasons="2022-2025", role="defensive line / run game coordinator",
         confidence="med", notes="Internal promotion; four seasons under the mentor on one staff."),
)

HEADER = """# Phase 0.13.1 defensive play-caller regime table (T48).
# THE SECOND PIECE WITH NO FREE SOURCE.
# ★ GENERATED by steps/phase0_13_1_defense_history.py - NEVER hand-edit a row. The research lives
#   in that step's REGIMES block, where it can be diffed and argued with; this file is its output.
#   (The 16.5 derived-vs-curated lesson applied to a curated artefact: curation still gets a
#   provenance, and a hand-edit would put the artefact and its reasoning out of sync.)
# 2026 rows (32): USER-SIGNED-OFF 2026-08-03 at confidence=high; verbatim copy preserved at
#   reference/defense_coaches_2026_signed_off_2026-08-03.csv. Passed through unchanged.
# Historical rows: Claude-researched + web-verified 2026-08-03. head_coach is auto-filled from
#   pbp.home_coach/away_coach (exact, PIT) AND compared against the researcher's expectation, so
#   the audit is a real check rather than a tautology - a row whose head coach disagrees with pbp
#   is a row about the wrong regime.
# Scope = 2026 plus the PRIOR REGIMES OF THE 2026 PLAY-CALLERS (user decision), not a complete
#   defensive staff history of all 32 teams.
# Inclusion rule = the named person called the defense for the MAJORITY of the team's games.
#   Excluded seasons are documented in an adjacent row's notes and NEVER averaged. Nine seasons are
#   excluded this way; four of them (NYJ 2015-18 Bowles, NYJ 2021-24 Saleh, ATL 2024-25 Morris,
#   ARI 2023-25 Gannon) are regimes a title-keyed table would have invented.
# play_caller is the person who CALLS IT, never the person holding the title (the Monken rule).
#   It cuts BOTH ways here: NE 2018 has a play-caller with no coordinator title at all.
# in_house = the play-caller was already on THIS staff last season. 0 => a transport event.
# (none) = the team carried no DC title that season. (unknown) = there was one, unverified. The
#   two are different claims and are never collapsed.
# confidence: high = an attribution verified against a source this session; med = believed correct
#   and internally consistent, not individually verified; low = must verify before use.
"""


def build_historical(scaffold: pd.DataFrame) -> pd.DataFrame:
    """Expand :data:`REGIMES` to one row per team-season, with ``head_coach`` from pbp."""
    hc_lookup = {(int(r.season), r.team): r.head_coach for r in scaffold.itertuples()}
    rows: list[dict] = []
    for reg in REGIMES:
        for i, season in enumerate(reg["seasons"]):
            key = (season, reg["team"])
            expected = reg["expected_hc"]
            expected_hc = expected[season] if isinstance(expected, dict) else expected
            caller = reg["play_caller"]
            title = reg["dc_title"] if reg["dc_title"] is not None else caller
            rows.append({
                "season": season,
                "team": reg["team"],
                "head_coach": hc_lookup.get(key, "(unknown)"),
                "defensive_coordinator": title,
                "play_caller": caller,
                "hc_calls_defense": reg["hc_calls"],
                # in_house is researched for the regime's FIRST season; later seasons are 1 by
                # construction, because the caller was on that staff calling plays the year before.
                "in_house": reg["in_house"] if i == 0 else 1,
                "confidence": reg["confidence"],
                "notes": reg["note"] if i == 0 else "",
                "_expected_hc": expected_hc,
            })
    return pd.DataFrame(rows).sort_values(["season", "team"]).reset_index(drop=True)


def _quote(value: object) -> str:
    text = "" if value is None else str(value)
    return text


def write_csv(hist: pd.DataFrame, signed_off_lines: list[str], path: Path) -> None:
    """Emit the 2026 sign-off rows verbatim beneath the generated historical ones."""
    with path.open("w", newline="") as fh:
        fh.write(",".join(dc.SCHEMA) + "\n")
        fh.write(HEADER)
        writer = csv.writer(fh, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        for _, row in hist.iterrows():
            writer.writerow([_quote(row[c]) for c in dc.SCHEMA])
        fh.write("# ---- 2026, user-signed-off 2026-08-03, passed through verbatim ----\n")
        for line in signed_off_lines:
            fh.write(line + "\n")


def main() -> None:
    con = db.connect()
    scaffold = head_coach_scaffold(con)
    hist = build_historical(scaffold)

    # ★ The audit that makes the free column worth having: does the researcher's belief about who
    # ran the team match what pbp actually recorded?
    expectation_mismatch = hist[hist["head_coach"] != hist["_expected_hc"]]
    hist = hist.drop(columns=["_expected_hc"])

    signed_off = [ln for ln in SIGNED_OFF.read_text().splitlines()[1:] if not ln.startswith("#")]
    write_csv(hist, signed_off, dc.DEFENSE_COACHES_CSV)

    df = dc.load_defense_coaches()
    dc.assert_defense_schema(df)
    audit = audit_against_pbp(df, scaffold)
    findings = move_graph_check(df)
    cov = dc.coverage(df, 2026)

    lineage = pd.DataFrame(list(LINEAGE))[list(dc.LINEAGE_SCHEMA[:-1]) + ["notes"]]
    lineage.to_csv(dc.DEFENSE_LINEAGE_CSV, index=False)
    lin = dc.load_defense_lineage()
    dc.assert_lineage_schema(lin, df)

    # ⚠ This direct audit is VACUOUS BY CONSTRUCTION and is reported anyway, labelled: head_coach
    # was auto-filled from the scaffold, so it cannot disagree with the scaffold. The check with
    # teeth is `expectation_mismatches` — the researcher's independent belief about who ran each
    # team, compared against pbp. Reporting the auditable row count keeps "agreed on 121 rows"
    # distinguishable from "ran on nothing", which is how a bar that cannot fail hides.
    verdicts = audit["verdict"].value_counts().to_dict() if len(audit) else {}
    first_timers = cov[cov["first_time"]]
    covered = cov[~cov["first_time"]]
    out = {
        "step": "0.13.1 — the defensive regime table",
        "rows": {"total": len(df), "historical": len(hist), "signed_off_2026": len(signed_off)},
        "play_callers": int(df["play_caller"].nunique()),
        "regimes": len(REGIMES),
        "confidence": df["confidence"].value_counts().to_dict(),
        "audit_vs_pbp": {
            "auditable_rows": int(df["season"].isin(dc.PBP_SEASONS).sum()),
            "disagreements": {k: int(v) for k, v in verdicts.items()},
            "vacuous_by_construction": True,
            "note": "head_coach is auto-filled from this same scaffold, so this audit cannot fire; "
                    "expectation_mismatches below is the check with teeth.",
        },
        "expectation_audit": {
            "rows_compared": int(len(hist)),
            "mismatches": expectation_mismatch[
                ["season", "team", "head_coach", "_expected_hc"]].to_dict("records"),
        },
        "move_graph_findings": findings,
        "coverage_2026": {
            "with_prior_history": int(len(covered)),
            "first_time": int(len(first_timers)),
            "first_time_teams": sorted(first_timers["team"].tolist()),
            "median_prior_seasons": float(covered["prior_seasons"].median()),
        },
        "lineage": {"rows": len(lin),
                    "unmentored_first_timers": sorted(
                        set(first_timers["play_caller"]) - set(lin["play_caller"]))},
        "hc_calls_defense_2026": int(df[df["season"] == 2026]["hc_calls_defense"].sum()),
    }
    ANALYSIS.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
