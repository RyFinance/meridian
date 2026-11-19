"""Oil-basket (18 names, equal weight, pre-set sign -d) and SPY placebo by half-year, 10:30 and close exits."""
import importlib.util, pandas as pd, numpy as np
src = open("research/zb_itb/round5/oil_second_order/study2.py").read().split("rows = []; series = {}")[0]
exec(src)
names = [n for g in GROUPS["oil"].values() for n in g]
out = []
for ex in ["10:30", "close"]:
    M = pd.concat([net_series(n, "CL_F", -1, ex).rename(n) for n in names], axis=1)
    basket = M.mean(axis=1)
    spy = net_series("SPY", "CL_F", -1, ex)
    for lab, s in [("oil basket -d", basket), ("SPY placebo -d", spy)]:
        for per, (a, b) in [("2024H2", ("2024-05-28", "2024-12-31")), ("2025H1", ("2025-01-01", "2025-06-30")),
                            ("2025H2", ("2025-07-01", "2025-12-31")), ("2026", ("2026-01-01", "2026-10-16"))]:
            x = s[(s.index >= a) & (s.index <= b)].dropna()
            out.append(dict(exit=ex, series=lab, period=per, n=len(x), mean_bp=round(x.mean() * 1e4, 1), t=round(x.mean() / x.std() * np.sqrt(len(x)), 2)))
O = pd.DataFrame(out)
print(O.to_string(index=False))
