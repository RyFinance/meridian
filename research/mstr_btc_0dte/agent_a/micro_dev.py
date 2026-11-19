"""DEV only: is the 1-minute BTC->MSTR catch-up big enough to pay ext-hours spreads? Buckets by |1.2*BTC_1m - MSTR_1m|."""
import numpy as np, pandas as pd
from common import DEV, load_btc, load_mstr
m = load_mstr(); btc = load_btc()
m = m[(m.date >= DEV[0]) & (m.date <= DEV[1])]
out = []
for d, g in m.groupby("date"):
    s = pd.Series(g.close.values, index=g.end)
    for seg, (a, b) in {"ah": (1601, 1959), "pre_0400_0800": (401, 759), "pre_0800_0929": (800, 928)}.items():
        idx = s.index[(s.index.hour * 100 + s.index.minute >= a) & (s.index.hour * 100 + s.index.minute <= b)]
        one = pd.Timedelta(minutes=1)
        ok = idx[idx.isin(s.index) & (idx - one).isin(s.index)]
        for h in (1, 5):
            okh = ok[(ok + h * one).isin(s.index)]
            if len(okh) == 0: continue
            mp = np.log(s.loc[okh].values / s.loc[okh - one].values); bp = np.log(btc.reindex(okh).values / btc.reindex(okh - one).values)
            mn = np.log(s.loc[okh + h * one].values / s.loc[okh].values)
            out.append(pd.DataFrame(dict(seg=seg, h=h, x=1e4 * (1.2 * bp - mp), y=1e4 * mn)))
o = pd.concat(out).dropna()
for (seg, h), g in o.groupby(["seg", "h"]):
    g = g.assign(q=pd.qcut(g.x.abs(), [0, .5, .9, .99, 1], labels=["<p50", "p50-90", "p90-99", "top1%"]))
    r = g.groupby("q", observed=True).apply(lambda z: pd.Series(dict(n=len(z), med_absx=z.x.abs().median(),
        mean_followed_bp=(np.sign(z.x) * z.y).mean())), include_groups=False)
    print(f"== {seg} hold {h}m"); print(r.round(2).to_string())
