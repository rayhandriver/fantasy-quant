"""Phase 10 — season & playoff simulation (the tracked benchmark + tail objective).

``weekly``   — weekly-grain distributions (the Phase-5 deferral): correlated season draws
               (Phase-8 Σ via Iman–Conover) disaggregated to weeks, marginals preserved.
``season``   — league format, round-robin schedule, vectorized optimal lineups, standings.
``playoffs`` — bracket → playoff / championship probabilities (the north-star metric).
``leverage`` — variance as a lever given the standings (add spread when trailing).
"""
