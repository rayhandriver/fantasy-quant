"""Session DATA-1 / **B4** — the four motivating questions, each answered from one query.

    uv run python steps/phase0_12_4_questions.py

★ **This is the headline bar, and it encodes the rule the whole session is built on:**

    *A source is not ingested until the question that motivated it returns an answer.*

The user asked four specific things — the position-group micro-detail he sees discussed and could
never check: **opponent box stacking for RBs**, **coverage schemes faced by WRs**, **usage of 1-3
TE personnel sets**, and **play-calling tempo**. A session that lands ten seasons of parquet and
declares victory has proven nothing; each question has to come back with real numbers, on real
players, from one query against the store.

Each answer below prints a DEV-season sample. ⚠ **Ingest all seasons, analyse DEV only** — the
tables carry 2016-2025 because loading 2023/2024 does not spend the lockbox, but *building a
feature on them does*, so these readouts are pointed at DEV and the wall stays at the modelling
step. No feature is built here; that is M-1 and beyond.

Writes ``analysis/phase0_12_4_questions.json``.
"""

from __future__ import annotations

import json

from fantasy_quant.config import DEV_SEASONS, PROJECT_ROOT
from fantasy_quant.data import db

OUT_JSON = PROJECT_ROOT / "analysis" / "phase0_12_4_questions.json"
SEASON = 2022          # the most recent DEV season
WEEK = 8


def q1_box_faced_by_rb(con, season: int = SEASON, week: int = WEEK):
    """(i) **Box counts faced, per RB, per week.** Was this back running into stacked fronts?"""
    return con.execute("""
        select w.position, p.gsis_id, any_value(w.player_display_name) as player,
               p.team, p.season, p.week,
               p.snaps, p.run_snaps,
               round(p.box_faced_mean, 3)      as box_faced_mean,
               round(p.box_faced_mean_run, 3)  as box_faced_mean_run,
               p.snaps_box_8plus,
               round(p.snaps_box_8plus / nullif(p.snaps, 0), 3) as stacked_box_rate
        from participation_player_week p
        join weekly w
          on w.gsis_id = p.gsis_id and w.season = p.season and w.week = p.week
        where p.season = ? and p.week = ? and w.position = 'RB' and p.snaps >= 15
        group by all
        order by p.snaps desc
        limit 12
    """, [season, week]).df()


def q2_coverage_faced_by_wr(con, season: int = SEASON, week: int = WEEK):
    """(ii) **Man/zone share faced, per WR, per week.** Which receivers saw man coverage?"""
    return con.execute("""
        select w.position, p.gsis_id, any_value(w.player_display_name) as player,
               p.team, p.season, p.week,
               p.snaps, p.routes,
               p.snaps_vs_man, p.snaps_vs_zone,
               p.man_share_faced,
               round(p.snaps_pressure / nullif(p.pass_snaps, 0), 3) as pressure_rate_on_pass
        from participation_player_week p
        join weekly w
          on w.gsis_id = p.gsis_id and w.season = p.season and w.week = p.week
        where p.season = ? and p.week = ? and w.position = 'WR'
          and (p.snaps_vs_man + p.snaps_vs_zone) >= 10
        group by all
        order by p.routes desc
        limit 12
    """, [season, week]).df()


def q3_personnel_snap_share(con, season: int = SEASON, week: int = WEEK):
    """(iii) **Each TE's and WR's snap share WITHIN 11 / 12 / 13 personnel.**

    The question no public site answers, because it needs the on-field record: not "how often does
    this team use 12 personnel" but "when they do, is *this* tight end the one out there".
    """
    return con.execute("""
        with team_pers as (
            select season, week, team,
                   sum(snaps_p11) as t11, sum(snaps_p12) as t12, sum(snaps_p13) as t13
            from participation_player_week
            where season = ? and week = ?
            group by 1, 2, 3
        )
        select w.position, p.gsis_id, any_value(w.player_display_name) as player,
               p.team, p.season, p.week,
               p.snaps_p11, p.snaps_p12, p.snaps_p13,
               -- a team's personnel snap totals count 11 players per snap, so the share of the
               -- grouping this player was on the field for divides by the team's plays in it
               round(p.snaps_p11 / nullif(t.t11 / 11.0, 0), 3) as share_of_team_11,
               round(p.snaps_p12 / nullif(t.t12 / 11.0, 0), 3) as share_of_team_12,
               round(p.snaps_p13 / nullif(t.t13 / 11.0, 0), 3) as share_of_team_13
        from participation_player_week p
        join weekly w
          on w.gsis_id = p.gsis_id and w.season = p.season and w.week = p.week
        join team_pers t
          on t.season = p.season and t.week = p.week and t.team = p.team
        where p.season = ? and p.week = ? and w.position in ('TE', 'WR') and p.snaps >= 15
        group by all
        order by p.snaps_p12 desc
        limit 12
    """, [season, week, season, week]).df()


def q4_neutral_pace(con, season: int = SEASON, week: int = WEEK):
    """(iv) **Neutral-script seconds per play, per team, per week.** Play-calling tempo.

    "Neutral" matters: a team trailing by 20 runs a hurry-up and a team leading by 20 bleeds the
    clock, so raw pace mostly measures the scoreboard. Restricted to one-score games in the first
    three quarters, the number is about how the offense *wants* to play.
    """
    return con.execute("""
        with plays as (
            select season, week, posteam as team, drive, game_id,
                   game_seconds_remaining,
                   lag(game_seconds_remaining) over (
                       partition by game_id, posteam, drive order by play_id
                   ) as prev_secs
            from pbp
            where season = ? and week = ? and season_type = 'REG'
              and play_type in ('pass', 'run')
              and qtr <= 3
              and abs(score_differential) <= 8      -- one-score, i.e. script-neutral
        )
        select season, week, team,
               count(*)                                    as neutral_plays,
               round(avg(prev_secs - game_seconds_remaining), 2) as sec_per_play_neutral
        from plays
        where prev_secs is not null
          and prev_secs - game_seconds_remaining between 0 and 60   -- drop clock-stop artifacts
        group by 1, 2, 3
        having count(*) >= 10
        order by sec_per_play_neutral
        limit 12
    """, [season, week]).df()


QUESTIONS = [
    ("i.  box counts faced, per RB, per week", q1_box_faced_by_rb, "opponent box stacking"),
    ("ii. man/zone share faced, per WR, per week", q2_coverage_faced_by_wr, "coverage schemes"),
    ("iii. snap share WITHIN 11/12/13 personnel", q3_personnel_snap_share, "1-3 TE sets"),
    ("iv. neutral-script seconds per play, per team", q4_neutral_pace, "play-calling tempo"),
]


def main() -> dict:
    con = db.connect(read_only=True)
    answers, ok = [], True
    for label, fn, asked_as in QUESTIONS:
        df = fn(con)
        answered = len(df) > 0 and not df.isna().all().all()
        ok &= answered
        answers.append({
            "question": label,
            "user_asked_about": asked_as,
            "n_rows": len(df),
            "answered": bool(answered),
            "sample": json.loads(df.head(8).to_json(orient="records")),
        })
        print(f"\n{'=' * 78}\n{label}   ({asked_as})\n{'=' * 78}")
        print(df.to_string(index=False))

    result = {
        "bar": "B4 — the four motivating questions are answerable, end to end",
        "rule": "a source is not ingested until the question that motivated it returns an answer",
        "season_sampled": SEASON,
        "week_sampled": WEEK,
        "analysed_on": "DEV" if SEASON in DEV_SEASONS else "NON-DEV",
        "passed": bool(ok),
        "answers": answers,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True, default=str))
    print(f"\nB4 {'PASS' if ok else 'FAIL'} — {sum(a['answered'] for a in answers)}/4 answered")
    return result


if __name__ == "__main__":
    raise SystemExit(0 if main()["passed"] else 1)
