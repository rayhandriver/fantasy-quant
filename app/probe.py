"""Per-page execution counters — the instrument bar **B1** reads, and nothing else.

★ **Why a counter and not a timer.** T35's claim is not "tabs are slow", it is *"``st.tabs``
executes every tab body on every rerun"* — a statement about **how many times a function runs**,
which a wall-clock measurement can only ever imply. A timer would also pass the moment the cost
page happened to be cheap, and T35's real cost is not today's wasted milliseconds but that a
timer-driven rerun (14.M) would multiply them by every tick. So the bar counts calls, and the
counter is the cheapest honest instrument for that: one dict increment per page body.

It stays in the shipped code rather than being patched in by the test, because a probe that only
exists under the test measures the test. This is the same reasoning as ``bar_imports`` in Session
K1 — *a guard that does not run on the path a human uses is not a guard.*
"""

from __future__ import annotations

from collections import Counter

#: page name -> number of times its body has executed in this process.
PAGE_RUNS: Counter[str] = Counter()


def ran(page: str) -> None:
    """Record that ``page``'s body executed. Called once, first thing, by each page body."""
    PAGE_RUNS[str(page)] += 1


def reset() -> None:
    PAGE_RUNS.clear()


def snapshot() -> dict[str, int]:
    return dict(PAGE_RUNS)
