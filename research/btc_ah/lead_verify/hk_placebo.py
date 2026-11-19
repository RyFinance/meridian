"""Is Boyaa's 'BTC residual' fade just a generic thin-HK-stock gap fade? Same rule on z-scored RAW gap, Boyaa vs unrelated HK small caps. <= 2026-08-10."""
import numpy as np, pandas as pd, yfinance as yf
CUT = "2026-08-10"
T = ["0434.HK", "1723.HK", "0327.HK", "1357.HK", "2018.HK", "0772.HK", "0285.HK", "0136.HK", "1478.HK", "0981.HK"]
d = yf.download(T, start="2017-08-01", end="2026-08-11", auto_adjust=True, progress=False, group_by="ticker")
for t in T:
    x = d[t].dropna(); x = x[x.index <= CUT]
    g = np.log(x.Open / x.Close.shift()); oc = np.log(x.Close / x.Open)
    z = (g - g.rolling(120).mean().shift()) / g.rolling(120).std().shift()
    m = z.abs() >= 1.0
    p = (-np.sign(g) * oc - 0.0020)[m].dropna()
    for nm, s in [("dev<2023", p[p.index < "2023"]), ("chk>=2023", p[p.index >= "2023"])]:
        print(f"{t} {nm:9s} n {len(s):4d} mean {s.mean()*1e4:+6.0f}bp t {s.mean()/s.std()*np.sqrt(len(s)):+5.2f}", end=" | ")
    print(f"zero-range days {(x.High==x.Low).mean():.0%}")
