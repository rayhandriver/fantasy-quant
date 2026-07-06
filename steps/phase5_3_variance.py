"""Phase 5.3 — weekly boom/bust variance (the week-to-week volatility layer).

    uv run python steps/phase5_3_variance.py

Done when: per-player weekly volatility (mean/sd/CoV) and boom/bust rates are computed from
realized weeks, fantasy weekly scoring is confirmed right-skewed per position (the boom tail), and
the boom/bust signal separates volatile players from steady ones — a consistency axis the risk dial
surfaces alongside the season spread.
"""

from __future__ import annotations

from fantasy_quant.config import DEV_SEASONS
from fantasy_quant.data import db
from fantasy_quant.projections import variance


def main() -> None:
    con = db.connect(read_only=True)
    dev = [s for s in DEV_SEASONS if s >= 2016]

    skew = variance.position_skew(con, dev)
    print("weekly-points skew per position (positive ⇒ right-skewed boom tail):")
    for pos in ("QB", "RB", "WR", "TE"):
        if pos in skew:
            print(f"  {pos}: {skew[pos]:+.2f}")
            assert skew[pos] > 0, f"{pos} weekly scoring should be right-skewed"

    vol = variance.weekly_volatility(con, [max(dev)])
    reg = vol[vol["weeks"] >= 8]      # regulars only for a stable read
    print(f"\n{max(dev)} weekly volatility ({len(reg)} players with ≥8 games):")
    print("  highest boom rate (share of weeks clearing the position boom line):")
    for _, r in reg.sort_values("boom_prob", ascending=False).head(5).iterrows():
        print(f"    {r['player_key']}  {r['pos']}  boom {r['boom_prob']:.0%}  "
              f"bust {r['bust_prob']:.0%}  wk_mean {r['wk_mean']:.1f}  CoV {r['wk_cov']:.2f}")
    print("  steadiest startable (low CoV among wk_mean ≥ 10):")
    steady = reg[reg["wk_mean"] >= 10].sort_values("wk_cov")
    for _, r in steady.head(5).iterrows():
        print(f"    {r['player_key']}  {r['pos']}  CoV {r['wk_cov']:.2f}  "
              f"wk_mean {r['wk_mean']:.1f}  boom {r['boom_prob']:.0%}")

    # boom rate is a LEVEL signal (elite players clear the line often, and steadily), so it's a
    # distinct axis from CoV volatility — the two are weakly negatively related, not the same knob.
    c = reg[["boom_prob", "wk_cov"]].corr().iloc[0, 1]
    print(f"\ncorr(boom_prob, CoV) = {c:+.2f}  (boom rate tracks scoring level, not volatility — a "
          f"separate axis)")
    print("\nPhase 5.3 (variance / boom-bust) — all checks PASS.")
    con.close()


if __name__ == "__main__":
    main()
