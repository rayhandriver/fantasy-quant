"""Session K1 done-bar — the app, the CLI, and the six pre-registered bars.

    uv run python steps/session_k1_app.py            # every bar
    uv run python steps/session_k1_app.py --only b1  # one of them

Writes ``analysis/session_k1_app.json``.

★ **What makes B1 a real bar here and not a tautology.** The unit tests assert that the app and the
CLI resolve to the *same functions* — the structural claim. This step asserts the *behavioural* one
the structure is supposed to buy: it runs ``steps/mock_draft.py`` as a **subprocess**, exactly as a
human would, parses the numbers off its stdout, and compares them to the numbers the app's own entry
points produce in-process. Two genuinely different paths into the engine, one set of numbers.

The app is also **booted for real** (twice, two ways): Streamlit's ``AppTest`` runs the script and
lets us assert on what rendered, and a headless server is started and driven over HTTP so that a
failure which only appears under the real runtime — a cache decorator misuse, a widget key clash —
cannot hide behind a green test suite.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import engine  # noqa: E402

from fantasy_quant.adp import boards  # noqa: E402
from fantasy_quant.backtest.scoring import (  # noqa: E402,E501
    DEFAULT_RULESET,
    RuleSet,
    ruleset_from_preset,
)
from fantasy_quant.data import db, validate  # noqa: E402
from fantasy_quant.draft import session  # noqa: E402
from fantasy_quant.draft.config import LeagueSettings  # noqa: E402
from fantasy_quant.draft.simulator import (  # noqa: E402
    RosterSlots,
    _apply_pick,
    _prepare_board,
    board_player_key,
    pick_by_adp,
)
from fantasy_quant.simulation.season import LeagueFormat  # noqa: E402

OUT = Path("analysis/session_k1_app.json")
APP = Path("app/main.py")
SEASON_DEFAULT = 2026
SEED, ROOM_SEED, SEATS = 7, 1, "3,7"


def _con():
    return db.connect(read_only=True)


# ------------------------------------------------------------------------------------------------
# B2 — T32: the board we serve is the board the store resolved
# ------------------------------------------------------------------------------------------------
def bar_b2(con, season: int) -> dict:
    raw, src = boards.resolve_board(con, season, "ppr", 10, allow_ecr=False, include_dst=True)
    served, _ = engine.build(con, season)["board"], None
    have = set(board_player_key(served).astype(str))
    missing = [str(n) for k, n in zip(board_player_key(raw).astype(str),
                                      raw["name"].astype(str), strict=False) if k not in have]
    gate = validate.board_vintage_gate(f"board_vintage_{season}", n_served=len(served),
                                       n_resolved=len(raw), missing=missing)
    return {"bar": "B2 — the served board covers the resolved board (T32)",
            "pass": bool(gate["passed"]), "season": season, "source": src,
            "vintage": session.mock.board_vintage(raw, src),
            "n_resolved": len(raw), "n_served": len(served), "n_missing": len(missing),
            "missing_examples": missing[:8], "gate": gate}


# ------------------------------------------------------------------------------------------------
# B1 — the app and the CLI produce the same numbers
# ------------------------------------------------------------------------------------------------
_ROSTER_ROW = re.compile(
    r"^\s+(\d+)\s+(T\d+)\s+(\S[\S ]*?)\s{2,}(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s*"
    r"(?:<-- you)?\s*$")


def _cli_summary(text: str) -> pd.DataFrame:
    """Parse the CLI's ``=== FINAL ROSTERS ===`` table back out of its stdout."""
    rows = []
    started = False
    for line in text.splitlines():
        if "FINAL ROSTERS" in line:
            started = True
            continue
        if not started:
            continue
        if line.strip().startswith("(") or not line.strip():
            if rows:
                break
            continue
        m = _ROSTER_ROW.match(line)
        if m:
            rows.append({"rank": int(m.group(1)), "team": int(m.group(2)[1:]),
                         "who": m.group(3).strip(), "starters": float(m.group(4)),
                         "proj": float(m.group(5)), "startable": float(m.group(6)),
                         "capital": float(m.group(7))})
    return pd.DataFrame(rows)


def _cli_picks(text: str) -> list[str]:
    """Every player name in the CLI's own pick log, in order."""
    out = []
    for line in text.splitlines():
        m = re.match(r"^\s+\d+\.\d+\s+T\d+\s+\S[\S ]*?\s{2,}(\S[\S ]*?)\s{2,}\S+\s+\(ADP",
                     line)
        if m:
            out.append(m.group(1).strip())
    return out


def bar_b1(con, season: int) -> dict:
    """Run the CLI as a subprocess and the app in-process; compare the numbers."""
    root = Path(__file__).resolve().parents[1]
    run = lambda *a: subprocess.run(                                     # noqa: E731
        [sys.executable, "steps/mock_draft.py", *a], cwd=root, capture_output=True, text=True,
        timeout=1800)

    start = run("start", "--seats", SEATS, "--seed", str(SEED), "--room-seed", str(ROOM_SEED),
                "--season", str(season))
    if start.returncode:
        return {"bar": "B1", "pass": False, "reason": start.stderr[-800:]}
    finish = run("finish")
    if finish.returncode:
        return {"bar": "B1", "pass": False, "reason": finish.stderr[-800:]}
    cli_tab = _cli_summary(finish.stdout)
    # the WHOLE draft, not just the picks before the first human turn: `finish` autodrafts every
    # human seat by ADP, which is exactly what the loop below does, so all 150 picks are comparable
    # and a divergence anywhere in the draft has to show up.
    log = run("log", "--n", "999")
    cli_log = _cli_picks(log.stdout) if not log.returncode else _cli_picks(start.stdout)

    # --- the same draft, through the app's own entry points ------------------------------------
    built = engine.build(con, season)
    seats = session.parse_seats(SEATS)
    state, meta = engine.start_draft(built, human_seats=seats, settings=LeagueSettings(),
                                     season=season, seed=SEED, room_seed=ROOM_SEED)
    session.advance(state, meta, built["risk"])
    while not state.is_done() and state.available:
        t = state.team_on_clock()
        _apply_pick(state, t, int(pick_by_adp(state, t, noise=0.0)))
        session.advance(state, meta, built["risk"])
    app_log = [str(p["player_name"]) for p in state.log]
    sm = session.seat_map_from(meta)
    app_tab = session.summary_table(state, sm, built["value_index"])

    merged = cli_tab.merge(app_tab, on="team", suffixes=("_cli", "_app"))
    diffs = {}
    for col in ("rank", "starters", "proj", "startable", "capital"):
        d = float(np.abs(merged[f"{col}_cli"] - merged[f"{col}_app"]).max()) if len(merged) else -1
        diffs[col] = d
    who_ok = bool(len(merged)) and (merged["who_cli"] == merged["who_app"]).all()
    # the CLI rounds to whole points on screen, so agreement is asserted at display precision
    numbers_ok = all(v <= 0.5 for v in diffs.values() if v >= 0) and len(merged) == state.n_teams
    # the CLI's `log` truncates each name to 23 chars for its column, so compare on that prefix
    picks_ok = bool(cli_log) and [n[:23] for n in app_log] == [n[:23] for n in cli_log]
    first_diff = next((i for i, (x, y) in enumerate(zip(app_log, cli_log, strict=False))
                       if x[:23] != y[:23]), None)

    return {"bar": "B1 — app and CLI produce identical numbers from the same seed",
            "pass": bool(numbers_ok and who_ok and picks_ok),
            "n_teams_matched": int(len(merged)), "who_matches": who_ok,
            "picks_match": picks_ok, "n_picks_app": len(app_log), "n_picks_cli": len(cli_log),
            "first_differing_pick": first_diff, "max_abs_diff": diffs,
            "note": ("The CLI ran as a subprocess and was parsed off stdout; the app ran "
                     "in-process through app/engine.py. Different entry points, one engine."),
            "cli_summary": cli_tab.to_dict("records"),
            "app_summary": app_tab.round(4).to_dict("records")}


# ------------------------------------------------------------------------------------------------
# B3 / B6 — the settings contract
# ------------------------------------------------------------------------------------------------
def bar_b3() -> dict:
    s = LeagueSettings()
    lockbox = {"roster_slots": s.roster_slots() == RosterSlots(),
               "league_format": s.league_format() == LeagueFormat(),
               "ruleset": s.ruleset() == DEFAULT_RULESET,
               "lockbox_validated": s.lockbox_validated() is True}
    sflex = LeagueSettings(superflex=1, rounds=16)
    non_default = {"lockbox_validated_is_false": sflex.lockbox_validated() is False,
                   "superflex_slot_set": sflex.roster_slots().superflex == 1,
                   "still_playable": _playable(sflex)}
    refused = _playable(LeagueSettings(n_teams=11)) is False
    return {"bar": "B3 — settings round-trip; the banner tells the truth both ways",
            "pass": bool(all(lockbox.values()) and all(non_default.values()) and refused),
            "lockbox_case": lockbox, "superflex_case": non_default,
            "odd_team_count_refused": refused}


def _playable(s: LeagueSettings) -> bool:
    try:
        s.validate()
        s.roster_slots()
    except (ValueError, AssertionError):
        return False
    return True


def bar_b6() -> dict:
    """A cosmetic scoring change must not split ``cached_distribution``'s key."""
    same = ruleset_from_preset("full_ppr")
    return {"bar": "B6 — the default preset returns RuleSet() itself (cache-key safety)",
            "pass": bool(same == RuleSet() and same.name == RuleSet().name
                         and LeagueSettings().ruleset() == RuleSet()
                         and ruleset_from_preset("half_ppr") != RuleSet()),
            "full_ppr_is_default_ruleset": same == RuleSet(),
            "name_preserved": same.name == RuleSet().name,
            "half_ppr_differs": ruleset_from_preset("half_ppr") != RuleSet(),
            "why": ("RuleSet is serialized into cached_distribution's cache key; a cosmetic name "
                    "difference would force a silent nine-season rebuild, so the app's scoring "
                    "dropdown requires explicit confirmation before it can change.")}


# ------------------------------------------------------------------------------------------------
# B4 — any k of n, on the real board with the real room
# ------------------------------------------------------------------------------------------------
def bar_b4(con, season: int, ks=(0, 1, 4, 9, 10)) -> dict:
    built = engine.build(con, season)
    need = RosterSlots().base_demand()
    supply = session.mock.board_supply(built["board"])
    rows = []
    for k in ks:
        seats = list(range(k))
        mix = None if k <= 5 else ",".join(["balanced"] * (10 - k))
        state, meta = engine.start_draft(built, human_seats=seats, settings=LeagueSettings(),
                                         season=season, seed=5, room_seed=2,
                                         room_arg=mix or "realistic")
        session.advance(state, meta, built["risk"])
        while not state.is_done() and state.available:
            t = state.team_on_clock()
            _apply_pick(state, t, int(pick_by_adp(state, t, noise=0.0)))
            session.advance(state, meta, built["risk"])
        short = 0
        avoidable = 0
        for t in range(state.n_teams):
            counts = state.roster(t)["pos"].value_counts()
            for pos, want in need.items():
                if int(counts.get(pos, 0)) < want:
                    short += 1
                    # a board that carries fewer than n_teams*want of a position cannot serve
                    # every seat — that shortfall is the board's, not the pick policy's (T20/T23)
                    if supply.get(pos, 0) >= state.n_teams * want:
                        avoidable += 1
        rows.append({"k": k, "complete": bool(state.is_done() or not state.available),
                     "n_picks": len(state.log), "seat_slots_short": short,
                     "avoidable_short": avoidable})
    return {"bar": "B4 — a k-of-n draft completes and fields a legal lineup, k in {0,1,4,9,10}",
            "pass": all(r["complete"] and r["avoidable_short"] == 0 for r in rows),
            "board_supply": {k: int(v) for k, v in supply.items()}, "runs": rows}


# ------------------------------------------------------------------------------------------------
# B5 — every rendered `why` line equals the engine's number
# ------------------------------------------------------------------------------------------------
def bar_b5(con, season: int, n_players: int = 40) -> dict:
    """The chain is an identity on stored quantities, checked player by player on the live board."""
    built = engine.build(con, season)
    # the **prepared** board — `player_key`/`player_name`/`pos` are `_prepare_board`'s, and it is
    # the frame both surfaces actually hand to `explain_chain` (the CLI passes `state.board`).
    board, vi = _prepare_board(built["board"]), built["value_index"]
    idx = vi.drop_duplicates("player_key").set_index(vi["player_key"].astype(str))
    checked, bad = 0, []
    for _, r in board.head(n_players).iterrows():
        key = str(r["player_key"])
        if key not in idx.index:
            continue
        entries = session.explain_chain(board[board["player_key"] == key], vi,
                                        str(r["player_name"]), lam=built["lam"])
        if not entries or not entries[0]["ok"]:
            continue
        by = {row["label"]: row["value"] for row in entries[0]["rows"]}
        v = idx.loc[key]
        lam_var = next(x for k, x in by.items() if k.startswith("- lambda*Var"))
        repl = next(x for k, x in by.items() if k.startswith("- replacement CE"))
        ok = (abs(lam_var + (float(v["mean"]) - float(v["ce_value"]))) < 1e-9
              and abs(repl + (float(v["ce_value"]) - float(v["ce_vbd"]))) < 1e-9
              and abs(by["= BASE_VALUE — what seats optimize"] - float(v["ce_vbd"])) < 1e-9
              and abs(by["consensus projection (PROJ)"] - float(v["proj_points"])) < 1e-9)
        checked += 1
        if not ok:
            bad.append(str(r["player_name"]))
    return {"bar": "B5 — every `why` line is an identity read from the frozen contracts",
            "pass": bool(checked and not bad), "n_checked": checked, "n_mismatched": len(bad),
            "mismatched": bad[:8],
            "note": ("lambda*Var is printed as mean - ce_value and replacement as "
                     "ce_value - ce_vbd, so the panel cannot drift from the stack it explains.")}


# ------------------------------------------------------------------------------------------------
# the app actually runs — twice, two ways
# ------------------------------------------------------------------------------------------------
def bar_apptest() -> dict:
    """Run the app script under Streamlit's own test runtime and assert on what rendered.

    ⚠ **Amended in Session K1.5, and the amendment is disclosed rather than quiet.** This bar used
    to require ``at.get("tab")`` to be non-empty. 14.K **deleted the tabs on purpose** — they were
    T35, executing every body on every rerun — so the old condition would now fail for the exact
    reason the session succeeded. The tab count was only ever a proxy for *something rendered*, and
    the replacement says that directly: no uncaught exception, and the page produced elements.
    ``steps/session_k1_5_app.py::bar_b1`` is where "one page body per rerun" is asserted.
    """
    try:
        from streamlit.testing.v1 import AppTest
    except ImportError as exc:
        return {"bar": "APP — renders under AppTest", "pass": False, "reason": str(exc)}
    at = AppTest.from_file(str(APP), default_timeout=600)
    at.run()
    rendered = len(at.get("dataframe")) + len(at.get("markdown")) + len(at.button)
    return {"bar": "APP — the script renders with no uncaught exception",
            "pass": bool(not at.exception and rendered),
            "n_exceptions": len(at.exception),
            "exceptions": [str(e.value)[:400] for e in at.exception][:4],
            "n_elements_rendered": rendered,
            "n_dataframes": len(at.get("dataframe")),
            "title": at.title[0].value if at.title else None}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


#: How the app can be launched. **The console script is FIRST because it is what the README, the
#: module docstring and `PROJECT.md` tell a human to type**, and the first version of this bar ran
#: only `python -m streamlit` — which puts the cwd on `sys.path` and therefore made the app's own
#: `from app import ...` work when the documented command did not. The app shipped broken and this
#: bar reported PASS. *A guard that does not run on the path a human uses is not a guard* (T27);
#: here the "path" was literally `sys.path`. Both are checked now, and neither is optional.
LAUNCHERS: tuple[tuple[str, list[str]], ...] = (
    ("console_script", ["streamlit"]),                      # uv run streamlit run app/main.py
    ("python_m", [sys.executable, "-m", "streamlit"]),      # python -m streamlit run app/main.py
)


def bar_imports() -> dict:
    """★ Does the entry point **import** when run as a bare script from an arbitrary directory?

    **This bar exists because the app shipped broken and every other bar said PASS** (2026-07-30).
    ``streamlit run app/main.py`` executes the file with ``app/`` on ``sys.path`` — not the repo
    root — so ``from app import engine, views`` raised ``ModuleNotFoundError`` for the first human
    who opened it. Three checks had missed it:

    * the **unit tests** import ``app.engine`` under pytest's ``pythonpath = ["src", "."]``;
    * ``AppTest`` runs in *this* process, where the done-bar has already inserted the repo root;
    * :func:`bar_server` booted a server and fetched ``/`` — but **Streamlit does not run the
      script until a browser opens a websocket session**, so ``curl`` gets the same 6.6 kB HTML
      shell whether the script imports or not. That bar was measuring "the server starts", while
      its name claimed "the app runs".

    So the harshest honest check is the cheapest one: run the file as a plain script, from a
    directory that is not the repo, with ``PYTHONPATH`` scrubbed. If the imports resolve, Streamlit
    prints its bare-mode warning and exits 0; if they do not, this fails the way the user did.

    *Every layer of the test pyramid shared one assumption — that the repo root is importable — and
    the assumption was false in exactly the configuration a human uses.*
    """
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    root = Path(__file__).resolve().parents[1]
    r = subprocess.run([sys.executable, str((root / APP).resolve())],
                       cwd=tempfile.gettempdir(), env=env, capture_output=True, text=True,
                       timeout=600)
    out = (r.stdout or "") + (r.stderr or "")
    return {"bar": "APP — the entry point imports as a bare script from an arbitrary cwd",
            "pass": bool(r.returncode == 0 and "ModuleNotFoundError" not in out),
            "returncode": r.returncode,
            "module_not_found": "ModuleNotFoundError" in out,
            "cwd_used": tempfile.gettempdir(), "pythonpath_scrubbed": True,
            "output_tail": out[-800:] if r.returncode else ""}


def bar_server(timeout_s: int = 240) -> dict:
    """Boot a real headless server **the documented way**, and again via ``-m``; drive both.

    ⚠ **Scope, stated because this bar over-claimed once and let a broken app ship:** it proves the
    server process starts, binds, and serves the HTML shell. It does **not** prove the script runs —
    Streamlit executes the script per *session*, on websocket connect, and an HTTP GET of ``/``
    never opens one. :func:`bar_imports` and :func:`bar_apptest` are what cover script execution.
    """
    runs = {name: _serve(cmd, timeout_s) for name, cmd in LAUNCHERS}
    return {"bar": "APP — a headless server boots and serves, however it is launched "
                   "(does NOT execute the script — see bar_imports)",
            "pass": all(r["pass"] for r in runs.values()),
            **{f"{name}_{k}": v for name, r in runs.items() for k, v in r.items()
               if k != "log_tail"},
            "logs": {name: r["log_tail"] for name, r in runs.items() if r["log_tail"]}}


def _serve(launcher: list[str], timeout_s: int) -> dict:
    port = _free_port()
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.Popen(
        [*launcher, "run", str(APP),
         "--server.headless", "true", "--server.port", str(port),
         "--server.address", "127.0.0.1", "--browser.gatherUsageStats", "false"],
        cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    health, page, deadline = None, None, time.time() + timeout_s
    try:
        while time.time() < deadline:
            if proc.poll() is not None:
                break
            try:
                with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/_stcore/health", timeout=5) as r:
                    health = r.status
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=15) as r:
                    body = r.read().decode("utf-8", "replace")
                page = (r.status, len(body),
                        any(m in body for m in ("ModuleNotFoundError", "Traceback")))
                break
            except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
                time.sleep(2)
    finally:
        proc.terminate()
        try:
            log = proc.communicate(timeout=25)[0] or ""
        except subprocess.TimeoutExpired:
            proc.kill()
            log = proc.communicate()[0] or ""
    # ⚠ the import error this bar exists to catch appears in the SERVED PAGE, not the exit code:
    # Streamlit catches the script's exception, keeps serving, and renders the traceback. So a
    # health check and a 200 are not enough — the page body has to be clean too.
    tb = ("Traceback (most recent call last)" in log or "ModuleNotFoundError" in log
          or (page is not None and page[2]))
    return {"pass": bool(health == 200 and page and page[0] == 200 and not tb),
            "health_status": health, "page_status": page[0] if page else None,
            "page_bytes": page[1] if page else None, "error_on_page_or_log": bool(tb),
            "log_tail": log[-1500:] if (tb or health != 200) else ""}


# ------------------------------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=None,
                    help="default: the live season (the newest board in the store)")
    ap.add_argument("--only", default=None, help="b1|b2|b3|b4|b5|b6|apptest|server")
    a = ap.parse_args()

    con = _con()
    season = a.season or engine.live_season(con)
    print(f"=== SESSION K1 DONE-BAR — season {season} ===\n")

    plan = {
        "b2": lambda: bar_b2(con, season),
        "b3": bar_b3,
        "b6": bar_b6,
        "b5": lambda: bar_b5(con, season),
        "b4": lambda: bar_b4(con, season),
        "b1": lambda: bar_b1(con, season),
        "apptest": bar_apptest,
        "imports": bar_imports,
        "server": bar_server,
    }
    if a.only:
        plan = {a.only: plan[a.only]}

    results = {}
    for name, fn in plan.items():
        print(f"--- {name} ---")
        r = fn()
        results[name] = r
        print(f"  {r['bar']}\n  {'PASS' if r['pass'] else 'FAIL'}")
        for k, v in r.items():
            if k not in ("bar", "pass") and not isinstance(v, (list, dict)) and v != "":
                print(f"    {k}: {v}")
        print()

    report = {"season": season, "seed": SEED, "room_seed": ROOM_SEED, "seats": SEATS,
              "all_pass": all(r["pass"] for r in results.values()), "bars": results}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str))
    con.close()
    print(f"{'ALL BARS PASS' if report['all_pass'] else 'SOME BARS FAILED'} -> {OUT}")


if __name__ == "__main__":
    main()
