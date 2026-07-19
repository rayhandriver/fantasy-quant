"""Phase 15 — multi-format support (best-ball, DFS; dynasty is roadmap).

Each format re-applies the engine's value + distribution + covariance machinery under a different
set of
rules. Best-ball (15.2) is pure draft + variance (no in-season management); DFS (15.3) is a
salary-capped,
field-relative, single-slate game. See the module docstrings for each format's contract and
done-bar.
"""
