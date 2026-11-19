"""Stress the scan survivors: later entries (dodge stale/thin opening prints), higher costs, and the 2024-26 holdout."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, ".")
from research.xmkt_1027.prep import daily
from research.xmkt_1027.scan import st
CANDS = [("FCX", "COPX", "c1300", 1), ("FCX", "COPX", "c1600", 1), ("FCX", "COPX", "c1030", 1), ("EEM", "COPX", "c1300", 1),
         ("DIA", "LABU", "c1030", -1), ("FAS", "LABU", "c1030", -1), ("XLE", "LABU", "c1030", -1), ("TMF", "NAIL", "c1300", 1)]
pd.set_option("display.width", 250)
for s, t, ex, k in CANDS:
    S, T = daily(s), daily(t)
    x = np.sign(np.log(S.pre915 / S.prev)).reindex(T.index)
    print(f"\n{s} pre-mkt ⇒ {t} →{ex[1:]} ({'follow' if k > 0 else 'fade'})   [bp per trade · t · CAGR]")
    for ent in ("o930", "c945", "c1000"):
        g = (k * x * np.log(T[ex] / T[ent])).where(x != 0).dropna()
        line = f"  entry {ent:6s}"
        for c in (6, 15):
            for lab, a, b in (("16-20", "2016", "2021"), ("21-23", "2021", "2024"), ("24-26 HOLDOUT", "2024", "2027")):
                q = g[(g.index >= a) & (g.index < b)] - 2 * c / 1e4; r = st(q)
                if r: line += f" | {c}bp {lab}: {r['bp']:+5.1f} t{r['t']:+.1f} {r['cagr']*100:+4.0f}%"
        print(line)
    # premarket coverage / liquidity
    print(f"  {s} pre-market print days: {S.pre915.notna().mean():.0%} · {t} median RTH volume (shares/day): {T.v.median():,.0f}")
