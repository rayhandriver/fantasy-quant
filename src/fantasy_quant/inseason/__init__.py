"""Phase 13 / spine step 7 — the in-season co-pilot.

The draft is over; the season is a fresh sequence of decisions under the same three signals
(value · availability · variance), now re-estimated weekly. This package is the in-season analog of
the draft optimizer:

  · 13.1 :mod:`~fantasy_quant.inseason.reproject` — weekly re-projection: a state-space update of
    every player's per-week scoring level as real results land (the value signal, refreshed).
  · 13.2 :mod:`~fantasy_quant.inseason.lineup` — start/sit under the win-probability objective:
    the lineup that most raises this week's H2H win chance, not the highest projected total
    (leverage — add variance when you're the underdog, protect a lead when you're favored).
  · 13.3 :mod:`~fantasy_quant.inseason.waivers` — waivers / FAAB: how much of a season-long budget
    to bid for a free agent, balancing his marginal value, the option value of holding budget, and
    first-price shading against the field (the availability signal, at the waiver grain).
  · 13.4 :mod:`~fantasy_quant.inseason.streaming` — streaming: the weekly matchup pick over the
    waiver pool (a contextual bandit) — start whichever freely-available unit has the best matchup
    this week (own level + opponent generosity), net of a switch cost, instead of holding one unit.
  · 13.5 :mod:`~fantasy_quant.inseason.trades` — trades: the market-maker searching every opponent
    roster for mutually-beneficial swaps that arbitrage complementary positional surpluses (a
    player is worth his marginal starting-lineup value), tilted to sell high / buy low on the field.

Everything is PIT and reuses the Phase-5 distributions + Phase-10 sim; nothing here trains a model.
"""
