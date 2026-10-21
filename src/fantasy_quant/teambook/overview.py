"""Short written overviews for the top of every Team Book tab, built from the book's own numbers.

Each tab gets two to four plain sentences that summarize what the tables below it show: how good a
unit was, what it did differently from the rest of the league, and which players drove it. The
text is rule based so it is free, reproducible and updates with the weekly live-season export.

★ **Every claim is read off the book.** A sentence that names a rank, a player or a change from last
season gets it from the same metrics, players and trends the page draws, so the overview can never
disagree with the tables under it. Sentences whose facts are missing are skipped, not guessed.

★ **Wording varies by team.** Each sentence has a few interchangeable phrasings and the choice is a
stable hash of team, season and tab, so the same page always reads the same way but neighbouring
teams do not all read alike.
"""

from __future__ import annotations

import hashlib
import re

from fantasy_quant.teambook import metrics as M

#: A full stop that ends a sentence — not the one in an initial ("C.J.") or in "St. Brown".
SENTENCE_END = re.compile(r"(?<=[a-z0-9%)])(?<!\bSt)\.(?= [A-Z0-9]|$)")

TABS = ("overview", "offense", "defense", "special", "players", "coaching", "trends", "notes")

#: The five efficiency measures a defense is judged on in the defense overview.
DEF_KEY = ("def_epa_per_play", "def_pass_epa", "def_rush_epa", "def_success_rate",
           "def_explosive_rate")
OFF_KEY = ("epa_per_play", "pass_epa", "rush_epa", "success_rate", "explosive_rate")

#: How a metric reads as a noun inside a sentence ("the 2nd highest {noun} in the league").
NOUN = {
    "snaps_per_game": "offensive snaps per game", "dropbacks_per_game": "dropbacks per game",
    "epa_per_play": "EPA per play", "pass_epa": "EPA per dropback", "rush_epa": "EPA per rush",
    "pass_oe_mean": "pass rate over expected", "share_under_center": "under center rate",
    "share_singleback": "singleback usage", "share_i_form": "I formation usage",
    "share_empty": "empty formation usage", "share_pistol": "pistol usage",
    "share_p11": "11 personnel usage", "share_p12": "12 personnel usage",
    "share_p13": "13 personnel usage", "share_p21": "21 personnel usage",
    "share_p22": "22 personnel usage", "share_p10": "10 personnel usage",
    "te_mean": "number of tight ends on the field", "wr_mean": "number of receivers on the field",
    "motion_rate": "pre-snap motion rate", "qb_under_center_ftn": "under center rate",
    "backfield_mean": "number of backs in the backfield",
    "def_epa_per_play": "EPA allowed per play", "def_pass_epa": "EPA allowed per dropback",
    "def_rush_epa": "EPA allowed per rush", "def_explosive_rate": "explosive play rate allowed",
    "takeaways_per_game": "takeaways per game", "share_base": "base defense usage",
    "share_nickel": "nickel usage", "share_dime": "dime usage",
    "dl_mean": "number of defensive linemen on the field",
    "lb_mean": "number of linebackers on the field", "man_share": "man coverage rate",
    "share_cover_0": "Cover 0 rate", "share_cover_1": "Cover 1 rate",
    "share_cover_2": "Cover 2 rate", "share_2_man": "2-Man rate",
    "share_cover_3": "Cover 3 rate", "share_cover_4": "Cover 4 rate",
    "share_cover_6": "Cover 6 rate", "proxy_two_high_share": "two-high safety rate",
    "rushers_mean": "number of pass rushers", "box_mean": "number of defenders in the box",
    "share_box_8plus": "eight man box rate", "ftn_blitz_rate": "blitz rate",
    "ftn_rushers_mean": "number of pass rushers", "ftn_box_mean": "number of defenders in the box",
    "ftn_box_8plus": "eight man box rate", "fourth_go_rate": "fourth down go rate",
    "two_point_rate": "two point attempt rate", "rz_stall_rate": "red zone stall rate",
    "fg_pct": "field goal percentage", "fg_pct_long": "field goal percentage from 50 plus",
    "fg_dist_mean": "average field goal distance", "punt_dist_mean": "average punt distance",
    "opp_pass_rate": "opponent pass rate",
}
NUMBER_WORDS = {0: "none", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}
POS_NAMES = {"qb": "quarterback", "rb": "running backs", "wr": "receivers", "te": "tight ends",
             "ol": "offensive line", "dl": "defensive line", "lb": "linebackers",
             "db": "secondary"}


# --- small helpers -----------------------------------------------------------------------------
def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def noun(key: str) -> str:
    if key in NOUN:
        return NOUN[key]
    label = M.BY_KEY[key].label
    return label if label[:2].isupper() else label[0].lower() + label[1:]


def a(word: str) -> str:
    """``"an eight man box rate"``, ``"a Cover 3 rate"`` — by sound, not spelling."""
    vowel = word[0].lower() in "aeiou" or word.startswith(("8", "11", "18", "eight", "RPO"))
    return f"{'an' if vowel else 'a'} {word}"


def pct(v: float) -> str:
    return f"{round(v * 100)}%"


def num(v: float, digits: int = 1) -> str:
    return f"{v:.{digits}f}".rstrip("0").rstrip(".") if digits else f"{round(v):,}"


class Writer:
    """Holds one team-season's context and the tense and variation rules every tab shares."""

    def __init__(self, book: dict, prev: dict | None, trends: dict, teams: dict, live: bool):
        self.b, self.prev, self.trends, self.teams, self.live = book, prev, trends, teams, live
        self.m = book["metrics"]
        self.nick = book["meta"].get("nick") or book["team"]
        self.season = book["season"]

    # tense: a finished season is told in the past, the live one in the present
    def t(self, past: str, present: str) -> str:
        return present if self.live else past

    def pick(self, tab: str, slot: str, options: list[str]) -> str:
        h = hashlib.md5(f"{self.b['team']}{self.season}{tab}{slot}".encode()).hexdigest()
        return options[int(h, 16) % len(options)]

    def the(self, cap: bool = False) -> str:
        return f"{'The' if cap else 'the'} {self.nick}"

    def rank(self, key: str) -> int | None:
        c = self.m.get(key)
        return c["rank"] if c else None

    def n(self, key: str) -> int:
        return self.m[key]["n"]

    def quality(self, key: str) -> str:
        """Plain words for where a polar metric's rank sits (1 = best)."""
        r, n = self.rank(key), self.n(key)
        r = round(1 + (r - 1) * 31 / max(n - 1, 1))
        if r == 1:
            return "the best in the league"
        if r <= 5:
            return "one of the best in the league"
        if r <= 10:
            return "well above average"
        if r <= 14:
            return "a little above average"
        if r <= 18:
            return "about average"
        if r <= 22:
            return "a little below average"
        if r <= 27:
            return "well below average"
        if r < 32:
            return "one of the worst in the league"
        return "the worst in the league"

    def extreme(self, key: str) -> str:
        """``"the 2nd highest play-action rate in the league"`` for a team's standout metric."""
        meta, c = M.BY_KEY[key], self.m[key]
        r, n = c["rank"], c["n"]
        if meta.polarity:
            top = r <= n / 2
            word = "best" if top else "worst"
        else:
            top = c["z"] is None or c["z"] >= 0
            counts = meta.fmt in ("num1", "num2")
            word = ("most" if top else "fewest") if counts else ("highest" if top else "lowest")
        place = r if top else n - r + 1
        thing = noun(key)
        if place <= 3:
            if thing.startswith("number of ") and word in ("most", "fewest"):
                thing = thing[len("number of "):]
            nth = "" if place == 1 else f"{ordinal(place)} "
            return f"the {nth}{word} {thing} in the league"
        among = {"most": "highest", "fewest": "lowest"}.get(word, word)
        return f"{a(thing)} that was among the {among} in the league"

    def standouts(self, side: str, scheme_only: bool = True, skip=(), k: int = 2) -> list[str]:
        rows = []
        for key, c in self.m.items():
            meta = M.BY_KEY[key]
            if meta.side != side or key in skip or c["z"] is None:
                continue
            if scheme_only and not meta.scheme:
                continue
            edge = min(c["rank"], c["n"] - c["rank"] + 1)
            if abs(c["z"]) >= 1.3 or edge <= 3:
                rows.append((abs(c["z"]), key))
        return [key for _, key in sorted(rows, reverse=True)[:k]]

    def team_name(self, abbr: str, season: int) -> str:
        nick = self.teams.get(abbr, {}).get("nick", abbr)
        return f"the {season} {nick}"


def _join(items: list[str]) -> str:
    tail = " in the league"
    if len(items) > 1 and all(i.endswith(tail) for i in items):
        items = [i[: -len(tail)] for i in items[:-1]] + [items[-1]]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + f" and {items[-1]}"


def _sentences(parts: list[str | None], limit: int = 4) -> str:
    out = [p.strip().replace("..", ".") for p in parts if p]  # a name ending "Jr." ends it
    return " ".join(out[:limit])


# --- the tabs ----------------------------------------------------------------------------------
def overview_tab(w: Writer) -> str:
    meta, rec = w.b["meta"], w.b["meta"].get("record")
    s1 = None
    if rec:
        record = f"{rec['w']}-{rec['l']}" + (f"-{rec['t']}" if rec["t"] else "")
        pf, pa = meta["points_for"], meta["points_against"]
        score = (f"outscored opponents {num(pf, 0)} to {num(pa, 0)}" if pf >= pa
                 else f"were outscored {num(pa, 0)} to {num(pf, 0)}")
        if w.live:
            s1 = (f"The {w.nick} are {record} through week {w.b['status']['through_week']} of the "
                  f"{w.season} season and have {score.replace('were ', 'been ')}.")
        else:
            s1 = f"The {w.nick} went {record} in {w.season} and {score}."
    off, dfn = w.rank("epa_per_play"), w.rank("def_epa_per_play")
    s2 = s3 = None
    if off and dfn:
        if off <= 10 and dfn <= 10:
            s2 = w.t(f"Both sides of the ball were strong, with the offense {ordinal(off)} in EPA "
                     f"per play and the defense {ordinal(dfn)} in EPA allowed.",
                     f"Both sides of the ball have been strong, with the offense {ordinal(off)} "
                     f"in EPA per play and the defense {ordinal(dfn)} in EPA allowed.")
        elif off >= 23 and dfn >= 23:
            s2 = w.t(f"Neither side held up, as the offense ranked {ordinal(off)} in EPA per play "
                     f"and the defense {ordinal(dfn)} in EPA allowed.",
                     f"Neither side has held up so far, with the offense {ordinal(off)} in EPA "
                     f"per play and the defense {ordinal(dfn)} in EPA allowed.")
        elif off + 8 <= dfn:
            s2 = w.t(f"The offense carried the team, ranking {ordinal(off)} in EPA per play while "
                     f"the defense finished {ordinal(dfn)} in EPA allowed.",
                     f"The offense has been carrying the team, ranking {ordinal(off)} in EPA per "
                     f"play while the defense sits {ordinal(dfn)} in EPA allowed.")
        elif dfn + 8 <= off:
            s2 = w.t(f"The defense did most of the work, finishing {ordinal(dfn)} in EPA allowed "
                     f"while the offense ranked {ordinal(off)} in EPA per play.",
                     f"The defense has done most of the work, ranking {ordinal(dfn)} in EPA "
                     f"allowed while the offense sits {ordinal(off)} in EPA per play.")
        else:
            s2 = w.t(f"The offense ranked {ordinal(off)} in EPA per play and the defense "
                     f"{ordinal(dfn)} in EPA allowed, so neither side stood out much.",
                     f"The offense ranks {ordinal(off)} in EPA per play and the defense "
                     f"{ordinal(dfn)} in EPA allowed, so neither side has stood out much yet.")
        if rec and meta.get("games"):
            win = (rec["w"] + rec["t"] / 2) / meta["games"]
            if win >= 0.65 and (off + dfn) / 2 > 17:
                s3 = w.t("That record was better than the underlying numbers, which suggests a "
                         "few close games went their way.",
                         "That record is better than the underlying numbers, which suggests a "
                         "few close games have gone their way.")
            elif win <= 0.35 and (off + dfn) / 2 < 13:
                s3 = w.t("The record undersells them, since teams with numbers like these usually "
                         "win more often.",
                         "The record undersells them so far, since teams with numbers like these "
                         "usually win more often.")
    picks = w.standouts("offense", k=1) + w.standouts("defense", k=1)
    s4 = None
    if picks:
        phrases = [w.extreme(k) for k in picks]
        lead = w.pick("overview", "id", [
            w.t("What set them apart was", "What sets them apart is"),
            w.t("Their most distinctive traits were", "Their most distinctive traits are")
            if len(phrases) > 1 else w.t("Their most distinctive trait was",
                                         "Their most distinctive trait is"),
        ])
        s4 = f"{lead} {_join(phrases)}."
    return _sentences([s1, s2, s3, s4])


def count(k: int) -> str:
    return "all five" if k == 5 else f"{NUMBER_WORDS[k]} of the five"


def offense_tab(w: Writer) -> str:
    s1 = s2 = s3 = s4 = None
    if w.rank("epa_per_play"):
        bad = sum(1 for k in OFF_KEY if (w.rank(k) or 0) >= 25)
        good = sum(1 for k in OFF_KEY if w.rank(k) and w.rank(k) <= 8)
        if good >= 4:
            s1 = w.t(f"The {w.nick} had one of the most efficient offenses in the league, "
                     f"ranking in the top eight in {count(good)} main efficiency measures.",
                     f"The {w.nick} have one of the most efficient offenses in the league so "
                     f"far, ranking in the top eight in {count(good)} main efficiency measures.")
        elif bad >= 3:
            s1 = w.t(f"The {w.nick} offense struggled, ranking 25th or worse in "
                     f"{count(bad)} main efficiency measures.",
                     f"The {w.nick} offense has struggled, ranking 25th or worse in "
                     f"{count(bad)} main efficiency measures.")
        else:
            s1 = w.t(f"The {w.nick} offense was {w.quality('epa_per_play')} by EPA per play.",
                     f"The {w.nick} offense has been {w.quality('epa_per_play')} by EPA per "
                     "play so far.")
            pr, rr = w.rank("pass_epa"), w.rank("rush_epa")
            if pr and rr and abs(pr - rr) >= 12:
                better, worse = ("passing", "running") if pr < rr else ("running", "passing")
                s1 = s1[:-1] + w.t(f", and it was much better {better} the ball than "
                                   f"{worse} it.",
                                   f", and it has been much better {better} the ball than "
                                   f"{worse} it.")
    proe = w.rank("pass_oe_mean")
    if proe:
        n = w.n("pass_oe_mean")
        if proe <= 6:
            s2 = w.t("They threw more than almost anyone relative to the situation, even when "
                     "the score did not call for it.",
                     "They have thrown more than almost anyone relative to the situation, even "
                     "when the score has not called for it.")
        elif proe > n - 6:
            s2 = w.t("They were one of the most run-heavy teams in the league, passing less "
                     "often than game situations would predict.",
                     "They have been one of the most run-heavy teams in the league, passing "
                     "less often than game situations would predict.")
        else:
            s2 = w.t("Their run and pass mix stayed close to what game situations called for.",
                     "Their run and pass mix has stayed close to what game situations call for.")
    picks = w.standouts("offense", skip=("pass_rate", "pass_rate_neutral", "pass_oe_mean",
                                         "early_down_pass_rate"), k=2)
    if picks:
        s3 = w.pick("offense", "id", [
            w.t("Schematically, they stood out for ", "Schematically, they stand out for "),
            w.t("Their biggest outliers in how they lined up were ",
                "Their biggest outliers in how they line up are "),
        ]) + _join([w.extreme(k) for k in picks]) + "."
    off = w.b["players"]["offense"]
    qbs = sorted((p for p in off if p["position"] == "QB" and (p.get("pass_att") or 0) > 0),
                 key=lambda p: -(p.get("pass_att") or 0))
    rec = sorted(off, key=lambda p: -(p.get("targets") or 0))
    if qbs and rec and (rec[0].get("targets") or 0) > 0:
        qb, top = qbs[0]["name"], rec[0]
        share = top.get("target_share") or 0
        if share >= 0.25:
            s4 = w.t(f"{qb} ran the passing game and leaned heavily on {top['name']}, who drew "
                     f"{pct(share)} of the targets.",
                     f"{qb} has run the passing game and leaned heavily on {top['name']}, who "
                     f"has drawn {pct(share)} of the targets.")
        else:
            s4 = w.t(f"{qb} ran the passing game, with {top['name']} leading the team in "
                     "targets.",
                     f"{qb} has run the passing game, with {top['name']} leading the team in "
                     "targets.")
    return _sentences([s1, s2, s3, s4])


def _pass_rush_names(w: Writer) -> str | None:
    rushers = sorted((p for p in w.b["players"]["defense"] if (p.get("sacks") or 0) >= 2),
                     key=lambda p: -(p.get("sacks") or 0))
    if not rushers:
        return None
    prev = {}
    if w.prev:
        prev = {p["gsis_id"]: p for p in w.prev["players"]["defense"]}
    def prior(p):
        return (prev.get(p["gsis_id"]) or {}).get("sacks") or 0

    def unexpected(p):
        return (w.prev is not None and (p["gsis_id"] not in prev or prior(p) <= 2)) or (
            (p.get("snap_share") or 1) < 0.6)

    established = [p for p in rushers if prior(p) >= 6]
    star = max(established, key=prior) if established else rushers[0]
    others = [p for p in rushers if p is not star and (p.get("sacks") or 0) >= 3
              and unexpected(p)]
    surprise = others[0] if others else None
    if surprise is None:
        return w.t(f"{star['name']} led the way with {num(star['sacks'])} sacks.",
                   f"{star['name']} has led the way with {num(star['sacks'])} sacks.")
    snaps = surprise.get("snap_share") or 0
    sacks = num(surprise["sacks"])
    if w.prev and surprise["gsis_id"] not in prev:
        detail = (f" while playing only {pct(snaps)} of the snaps" if snaps < 0.6 else "")
        detail += ", after not being a regular on this defense last season"
    elif snaps < 0.6:
        detail = f" despite playing only {pct(snaps)} of the snaps"
    else:
        detail = ", after doing little as a pass rusher a year ago"
    if established:
        return w.t(f"{star['name']} was as productive as expected, but the bigger surprise was "
                   f"{surprise['name']}, who had {sacks} sacks{detail}.",
                   f"{star['name']} has been as productive as expected, but the bigger surprise "
                   f"is {surprise['name']}, who has {sacks} sacks{detail}.")
    return w.t(f"{star['name']} led the team with {num(star['sacks'])} sacks, and "
               f"{surprise['name']} added {sacks}{detail}.",
               f"{star['name']} leads the team with {num(star['sacks'])} sacks, and "
               f"{surprise['name']} has added {sacks}{detail}.")


def defense_tab(w: Writer) -> str:
    s1 = s2 = s3 = s4 = None
    ranks = {k: w.rank(k) for k in DEF_KEY if w.rank(k)}
    if not ranks:
        return ""
    bad = {k: r for k, r in ranks.items() if r >= 25}
    good = {k: r for k, r in ranks.items() if r <= 8}
    sack_bright = False
    if len(bad) >= 3:
        cut = ordinal(min(bad.values()))
        count = "all five" if len(bad) == 5 else f"{NUMBER_WORDS[len(bad)]} of the five"
        s1 = w.t(f"The {w.nick} had one of the worst defenses in the league, ranking {cut} or "
                 f"worse in {count} main efficiency measures.",
                 f"The {w.nick} have one of the worst defenses in the league this season, "
                 f"ranking {cut} or worse in {count} main efficiency measures.")
        polar = [(c["rank"], k) for k, c in w.m.items()
                 if M.BY_KEY[k].side == "defense" and M.BY_KEY[k].polarity and k not in DEF_KEY]
        best = min(polar) if polar else None
        if best and best[0] <= 10:
            sack_bright = best[1] == "def_sack_rate"
            what = "the pass rush" if sack_bright else noun(best[1])
            s2 = w.t(f"Their one bright spot was {what}, which ranked {ordinal(best[0])} in "
                     f"{noun(best[1])}.",
                     f"Their one bright spot has been {what}, which ranks {ordinal(best[0])} in "
                     f"{noun(best[1])}.") if sack_bright else w.t(
                     f"Their one bright spot was {what}, where they ranked {ordinal(best[0])}.",
                     f"Their one bright spot has been {what}, where they rank "
                     f"{ordinal(best[0])}.")
    elif len(good) >= 3:
        cut = ordinal(max(good.values()))
        count = "all five" if len(good) == 5 else f"{NUMBER_WORDS[len(good)]} of the five"
        s1 = w.t(f"The {w.nick} had one of the best defenses in the league, ranking {cut} or "
                 f"better in {count} main efficiency measures.",
                 f"The {w.nick} have one of the best defenses in the league this season, "
                 f"ranking {cut} or better in {count} main efficiency measures.")
        worst = max((r, k) for k, r in ranks.items())
        if worst[0] >= 20:
            s2 = w.t(f"The one weak spot was {noun(worst[1])}, where they ranked "
                     f"{ordinal(worst[0])}.",
                     f"The one weak spot has been {noun(worst[1])}, where they rank "
                     f"{ordinal(worst[0])}.")
    else:
        s1 = w.t(f"The {w.nick} defense was {w.quality('def_epa_per_play')} by EPA allowed per "
                 "play.",
                 f"The {w.nick} defense has been {w.quality('def_epa_per_play')} by EPA allowed "
                 "per play so far.")
        pr, rr = w.rank("def_pass_epa"), w.rank("def_rush_epa")
        if pr and rr and abs(pr - rr) >= 10:
            better, worse = ("pass", "run") if pr < rr else ("run", "pass")
            s2 = w.t(f"It was much better against the {better} than the {worse}, ranking "
                     f"{ordinal(min(pr, rr))} and {ordinal(max(pr, rr))}.",
                     f"It has been much better against the {better} than the {worse}, "
                     f"ranking {ordinal(min(pr, rr))} and {ordinal(max(pr, rr))}.")
    if s2 is None:
        polar = [(c["rank"], k) for k, c in w.m.items()
                 if M.BY_KEY[k].side == "defense" and M.BY_KEY[k].polarity]
        if len(polar) >= 2:
            (br, bk), (wr, wk) = min(polar), max(polar)
            if br > 12 and wr - br >= 10:
                s2 = w.t(f"Even its strongest area, {noun(bk)}, only ranked {ordinal(br)}, and "
                         f"it was {ordinal(wr)} in {noun(wk)}.",
                         f"Even its strongest area, {noun(bk)}, only ranks {ordinal(br)}, and it "
                         f"is {ordinal(wr)} in {noun(wk)}.")
            elif wr < 18:
                where = (w.t("where it led the league", "where it leads the league")
                         if br == 1 else w.t(f"where it ranked {ordinal(br)}",
                                             f"where it ranks {ordinal(br)}"))
                s2 = w.t(f"Its strongest area was {noun(bk)}, {where}, and it had no real weak "
                         "spot.",
                         f"Its strongest area has been {noun(bk)}, {where}, and it has no real "
                         "weak spot.")
            elif wr - br >= 10:
                s2 = w.t(f"Its strongest area was {noun(bk)}, where it ranked {ordinal(br)}, and "
                         f"its weakest was {noun(wk)}, where it ranked {ordinal(wr)}.",
                         f"Its strongest area has been {noun(bk)}, where it ranks {ordinal(br)}, "
                         f"and its weakest has been {noun(wk)}, where it ranks {ordinal(wr)}.")
    s3 = _pass_rush_names(w)
    picks = w.standouts("defense", k=1)
    if picks:
        s4 = w.pick("defense", "id", [
            w.t("In terms of scheme, they had ", "In terms of scheme, they have "),
            w.t("Schematically, they had ", "Schematically, they have "),
        ]) + w.extreme(picks[0]) + "."
    else:
        rows = [(abs(c["z"]), k) for k, c in w.m.items() if M.BY_KEY[k].side == "defense"
                and M.BY_KEY[k].scheme and c["z"] is not None]
        if rows:
            key = max(rows)[1]
            c = w.m[key]
            high = c["z"] >= 0
            place = c["rank"] if high else c["n"] - c["rank"] + 1
            s4 = w.t(f"Their scheme was fairly conventional, and the closest thing to a "
                     f"signature was {a(noun(key))} that ranked {ordinal(place)} "
                     f"{'highest' if high else 'lowest'} in the league.",
                     f"Their scheme has been fairly conventional, and the closest thing to a "
                     f"signature is {a(noun(key))} that ranks {ordinal(place)} "
                     f"{'highest' if high else 'lowest'} in the league.")
    return _sentences([s1, s2, s3, s4])


def special_tab(w: Writer) -> str:
    s1 = s2 = s3 = s4 = None
    go = w.rank("fourth_go_rate")
    if go:
        n = w.n("fourth_go_rate")
        v = w.m["fourth_go_rate"]["v"]
        if go <= 6:
            s1 = w.t(f"The {w.nick} were one of the most aggressive teams on fourth down, going "
                     f"for it on {pct(v)} of their short-yardage chances in normal situations.",
                     f"The {w.nick} have been one of the most aggressive teams on fourth down, "
                     f"going for it on {pct(v)} of their short-yardage chances so far.")
        elif go > n - 6:
            s1 = w.t(f"The {w.nick} were one of the most conservative teams on fourth down, "
                     f"going for it on only {pct(v)} of their short-yardage chances.",
                     f"The {w.nick} have been one of the most conservative teams on fourth down, "
                     f"going for it on only {pct(v)} of their short-yardage chances.")
        else:
            s1 = w.t(f"The {w.nick} were about average in how often they went for it on fourth "
                     "down.",
                     f"The {w.nick} have been about average in how often they go for it on "
                     "fourth down.")
    fg = w.rank("fg_pct")
    if fg:
        v = w.m["fg_pct"]["v"]
        s2 = w.t(f"Their kickers made {pct(v)} of field goals, which was {w.quality('fg_pct')}.",
                 f"Their kickers have made {pct(v)} of field goals, which is "
                 f"{w.quality('fg_pct')}.")
    caps = [(w.m[f"cap_share_{g}"]["z"] or 0, g) for g in POS_NAMES if f"cap_share_{g}" in w.m]
    if caps:
        z, g = max(caps)
        if z >= 1:
            share = w.m[f"cap_share_{g}"]["v"]
            article = "the " if g in ("qb", "ol", "dl", "db") else ""
            s3 = (f"On the roster side, they put an unusually large share of their salary cap "
                  f"into {article}{POS_NAMES[g]}, about {pct(share)} of the money on the books.")
        else:
            s3 = "Their salary cap was spread across positions in a fairly typical way."
    cont = w.m.get("continuity_offense")
    if cont and cont["z"] is not None and abs(cont["z"]) >= 1:
        s4 = (f"The offense also {'brought back' if cont['z'] > 0 else 'turned over'} more "
              f"of its roster than most, with {pct(cont['v'])} of its snaps going to players "
              "who were on the team the year before.")
    else:
        ages = [(w.m[f"age_{g}"]["z"] or 0, g) for g in POS_NAMES if f"age_{g}" in w.m]
        if ages:
            z, g = max(ages, key=lambda t: abs(t[0]))
            if abs(z) >= 1.3:
                group = {"qb": "quarterbacks", "ol": "offensive line", "dl": "defensive line",
                         "db": "secondary"}.get(g, POS_NAMES[g])
                verb = "was" if g in ("ol", "dl", "db") else "were"
                s4 = (f"Their {group} {verb} among the "
                      f"{'oldest' if z > 0 else 'youngest'} in the league.")
    return _sentences([s1, s2, s3, s4])


def players_tab(w: Writer) -> str:
    off, dfn = w.b["players"]["offense"], w.b["players"]["defense"]
    s1 = s2 = s3 = s4 = None
    qbs = sorted((p for p in off if p["position"] == "QB" and (p.get("pass_att") or 0) > 0),
                 key=lambda p: -(p.get("pass_att") or 0))
    if qbs:
        qb = qbs[0]
        if (qb.get("snap_share") or 0) >= 0.85:
            s1 = w.t(f"{qb['name']} played nearly every snap at quarterback and threw for "
                     f"{num(qb.get('pass_yds') or 0, 0)} yards.",
                     f"{qb['name']} has played nearly every snap at quarterback and thrown for "
                     f"{num(qb.get('pass_yds') or 0, 0)} yards.")
        elif len(qbs) > 1:
            s1 = w.t(f"The quarterback job was split, with {qbs[0]['name']} and "
                     f"{qbs[1]['name']} both getting meaningful snaps.",
                     f"The quarterback job has been split, with {qbs[0]['name']} and "
                     f"{qbs[1]['name']} both getting meaningful snaps.")
    rec = sorted(off, key=lambda p: -(p.get("targets") or 0))
    if rec and (rec[0].get("targets") or 0) > 0:
        a = rec[0]
        if (a.get("target_share") or 0) >= 0.22:
            s2 = w.t(f"{a['name']} was the clear top target with {pct(a['target_share'])} of "
                     f"the looks and {num(a.get('rec_yds') or 0, 0)} receiving yards.",
                     f"{a['name']} has been the clear top target with {pct(a['target_share'])} "
                     f"of the looks and {num(a.get('rec_yds') or 0, 0)} receiving yards.")
        elif len(rec) > 1:
            s2 = w.t(f"Targets were spread around, with {a['name']} and {rec[1]['name']} "
                     "leading a group where nobody took more than a fifth of the looks.",
                     f"Targets have been spread around, with {a['name']} and {rec[1]['name']} "
                     "leading a group where nobody has more than a fifth of the looks.")
    rbs = sorted((p for p in off if (p.get("carries") or 0) > 0 and p["position"] != "QB"),
                 key=lambda p: -(p.get("carries") or 0))
    if rbs:
        top = rbs[0]
        # share of the non-quarterback carries: a running quarterback is not a backfield split
        share = (top.get("carries") or 0) / sum(p.get("carries") or 0 for p in rbs)
        if share >= 0.55:
            s3 = w.t(f"{top['name']} handled most of the work in the backfield with "
                     f"{pct(share)} of the carries.",
                     f"{top['name']} has handled most of the work in the backfield with "
                     f"{pct(share)} of the carries.")
        elif len(rbs) > 1:
            s3 = w.t(f"The backfield was a committee led by {top['name']} and {rbs[1]['name']}.",
                     f"The backfield has been a committee led by {top['name']} and "
                     f"{rbs[1]['name']}.")
    sacks = max(dfn, key=lambda p: p.get("sacks") or 0, default=None)
    ints = max(dfn, key=lambda p: p.get("ints") or 0, default=None)
    if sacks and (sacks.get("sacks") or 0) >= 1:
        tail = ""
        if ints and (ints.get("ints") or 0) >= 2 and ints["gsis_id"] != sacks["gsis_id"]:
            tail = f" and {ints['name']} picked off {num(ints['ints'], 0)} passes"
        s4 = w.t(f"On defense, {sacks['name']} led the team with {num(sacks['sacks'])} "
                 f"sacks{tail}.",
                 f"On defense, {sacks['name']} leads the team with {num(sacks['sacks'])} "
                 f"sacks{tail.replace('picked off', 'has picked off')}.")
    return _sentences([s1, s2, s3, s4])


def coaching_tab(w: Writer) -> str:
    c = w.b.get("coaching") or {}
    o, d = c.get("offense") or {}, c.get("defense") or {}
    s1 = s2 = s3 = None
    oc, dc = o.get("play_caller"), d.get("play_caller")
    if oc and dc:
        hc = " as head coach" if o.get("hc_calls") else ""
        s1 = w.t(f"{oc} called the offense{hc} and {dc} called the defense.",
                 f"{oc} is calling the offense{hc} and {dc} is calling the defense.")
    elif oc:
        s1 = w.t(f"{oc} called the offense, and the defensive play caller for this season is "
                 "not in the coaching data.",
                 f"{oc} is calling the offense, and the defensive play caller is not in the "
                 "coaching data.")
    else:
        s1 = ("This staff is not in the coaching data, so the comparisons below are based on "
              "scheme alone.")
    comps = w.b.get("comps") or {}

    def comp_sentence(side: str, own: str | None) -> str | None:
        rows = comps.get(side) or []
        if not rows:
            return None
        top = rows[:2]
        unit = "offense" if side == "offense" else "defense"
        verb = w.t("looked most like", "looks most like")
        same = [r for r in top if own and r.get("play_caller") == own]
        if same and len(same) == len(top):
            names = [w.team_name(r["team"], r["season"]) for r in top]
            joined = _join(names)
            if len(top) > 1:
                return (f"Their {unit} {verb} {joined}, both of which also had {own} calling "
                        "plays.")
            return f"Their {unit} {verb} {joined}, which also had {own} calling plays."
        if len(top) == 2 and top[0]["team"] == top[1]["team"]:
            nick = w.teams.get(top[0]["team"], {}).get("nick", top[0]["team"])
            text = f"Their {unit} {verb} the {top[0]['season']} and {top[1]['season']} {nick}"
            if top[0].get("play_caller") and top[0]["play_caller"] == top[1].get("play_caller"):
                text += f", both under {top[0]['play_caller']}"
            return text + "."
        if len(top) == 2 and top[0].get("play_caller") and \
                top[0]["play_caller"] == top[1].get("play_caller"):
            names = [w.team_name(r["team"], r["season"]) for r in top]
            return f"Their {unit} {verb} {_join(names)}, both under {top[0]['play_caller']}."
        names = [w.team_name(r["team"], r["season"])
                 + (f" under {r['play_caller']}" if r.get("play_caller") else "") for r in top]
        text = f"Their {unit} {verb} {_join(names)}"
        return text + "."
    s2 = comp_sentence("offense", oc)
    s3 = comp_sentence("defense", dc)
    return _sentences([s1, s2, s3])


def trends_tab(w: Writer) -> str:
    if not w.trends:
        return ""
    prev_season = w.season - 1

    def at(key: str, season: int):
        for row in w.trends.get(key, []):
            if row[0] == season:
                return row
        return None

    s1 = s2 = s3 = None
    first = min(r[0] for rows in w.trends.values() for r in rows)
    if w.season == first:
        return (f"{w.season} is the first season covered here, so there is no earlier year to "
                f"compare it with. The charts below show how the {w.nick} changed over the "
                "seasons that followed.")
    since = "so far this season" if w.live else f"in {w.season}"
    for key, unit in (("epa_per_play", "offense"), ("def_epa_per_play", "defense")):
        now, then = at(key, w.season), at(key, prev_season)
        if not now or not then:
            continue
        diff = then[3] - now[3]
        s = (f"The {unit} went from {ordinal(then[3])} in {noun(key)} in {prev_season} to "
             f"{ordinal(now[3])} {since}")
        if diff >= 8:
            s += ", a big step forward."
        elif diff <= -8:
            s += ", a big step back."
        elif diff >= 3:
            s += ", a modest improvement."
        elif diff <= -3:
            s += ", a modest decline."
        else:
            s += ", about where it was."
        if unit == "offense":
            s1 = s
        else:
            s2 = s.replace("The defense went", "The defense moved")
    shifts = []
    for key in w.trends:
        meta = M.BY_KEY[key]
        if not meta.scheme:
            continue
        now, then = at(key, w.season), at(key, prev_season)
        if now and then:
            moved = abs(then[3] - now[3])
            shifts.append((moved, key, then, now))
    if shifts:
        moved, key, then, now = max(shifts)
        if moved >= 12:
            fmt = (lambda v: pct(v)) if M.BY_KEY[key].fmt == "pct" else (lambda v: num(v, 2))
            s3 = (f"The biggest change in approach was {noun(key)}, which went from "
                  f"{fmt(then[1])} to {fmt(now[1])}.")
    return _sentences([s1, s2, s3])


def notes_tab(w: Writer) -> str:
    s = w.season
    if w.live:
        return (f"The {s} pages are built from data that nflverse updates every week, so they "
                "will keep changing until the season ends. Personnel, formations, coverage and "
                "pressure numbers are missing for now because that data is only released after "
                "the season.")
    if s < 2022:
        return (f"FTN did not start charting plays until 2022, so play action, motion, RPO and "
                f"screen rates are not available for {s}. Everything else, including personnel, "
                "formations and coverage, is complete for this season.")
    if s == 2022:
        return ("2022 is the first season with every data source available, including FTN's "
                "play design charting. It is also the last season that used the older formation "
                "labels, so singleback and I formation rates still appear here.")
    return (f"Every data source is available for {s}. This season uses the newer formation "
            "labels, which group singleback, I formation and empty sets together as under "
            "center, so those older formation rates are not shown.")


WRITERS = {"overview": overview_tab, "offense": offense_tab, "defense": defense_tab,
           "special": special_tab, "players": players_tab, "coaching": coaching_tab,
           "trends": trends_tab, "notes": notes_tab}


def overviews(book: dict, prev: dict | None, trends: dict, teams: dict) -> dict[str, str]:
    """``{tab: text}`` for one book. ``prev`` is the same team's previous-season book, if any."""
    live = not book["status"]["complete"]
    w = Writer(book, prev, trends, teams, live)
    return {tab: WRITERS[tab](w) for tab in TABS}


def assert_overview_sane(team: str, season: int, texts: dict[str, str]) -> None:
    """Refuse text a template could only produce by filling a slot with nothing."""
    for tab, text in texts.items():
        where = f"{team} {season} {tab}"
        n = len(SENTENCE_END.findall(text))
        if not text or not 1 <= n <= 4:
            raise ValueError(f"{where}: {n} sentences in {text!r}")
        bad = re.search(r"\bNone\b|\bnan\b|in the league in the league|  | ,|\.\.|[{}]", text)
        if bad:
            raise ValueError(f"{where}: {bad.group()!r} in {text!r}")
