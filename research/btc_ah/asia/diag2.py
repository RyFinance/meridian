import sys; sys.path.insert(0, "/Users/rytty/CCP/quant_v7/research/btc_ah/asia")
import numpy as np, pandas as pd
from lib import build, stats, RT, TK
rows = []
for s in ["0434_HK", "1723_HK", "3350_T", "3825_T", "8698_T", "8473_T", "9449_T"]:
    o = build(s); era = o["era"].iloc[0]; cut = o["cut"].iloc[0]
    W = 120; mp = 60
    beta = (o["g"].rolling(W, min_periods=mp).cov(o["m"]) / o["m"].rolling(W, min_periods=mp).var()).shift(1)
    resid = o["g"] - beta * o["m"]
    for label, mask_clean in [("all", pd.Series(True, index=o.index)), ("clean", o["clean"])]:
        for fam, sig in [("raw_gap_fade(no BTC)", -np.sign(o["g"])), ("resid_fade", -np.sign(resid)),
                         ("raw_gap_follow", np.sign(o["g"]))]:
            for thr in [0.0, 0.01]:
                ok = (o["g"].abs() >= thr) & o["g"].notna() & mask_clean & (o.index >= era)
                if fam.startswith("resid"): ok = ok & resid.notna()
                d = (sig * ok).fillna(0)
                gross = d * (o["C"] / o["O"] - 1)
                net = gross[d != 0] - RT
                dev = net[o.index[d != 0] < cut]; chk = net[o.index[d != 0] >= cut]
                rows.append((s, label, fam, thr, stats(dev), stats(chk)))
for r in rows:
    print(r[0], r[1], r[2], "gap>=", r[3], "dev(n,bp,t,win)", r[4], "chk", r[5])
