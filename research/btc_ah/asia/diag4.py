import sys; sys.path.insert(0, "/Users/rytty/CCP/quant_v7/research/btc_ah/asia")
import numpy as np, pandas as pd
from lib import build, stats, RT
rows=[]
for s in ["3350_T","3825_T","8698_T","8473_T","9449_T","0434_HK","1723_HK"]:
    o=build(s); era=o["era"].iloc[0]; cut=o["cut"].iloc[0]
    oc=np.log(o["C"]/o["O"])
    ok=o["m"].notna()&(o.index>=era)&(o["m"].abs()>=0.01)
    up=oc[ok&(o["m"]>0)]; dn=oc[ok&(o["m"]<0)]
    rows.append((s, len(up), round(up.mean()*1e4,1), len(dn), round(dn.mean()*1e4,1), "dev/chk up-day mean bp:",
                 round(oc[ok&(o["m"]>0)&(o.index<cut)].mean()*1e4,1), round(oc[ok&(o["m"]>0)&(o.index>=cut)].mean()*1e4,1),
                 "down-day:", round(oc[ok&(o["m"]<0)&(o.index<cut)].mean()*1e4,1), round(oc[ok&(o["m"]<0)&(o.index>=cut)].mean()*1e4,1)))
for r in rows: print(*r)
# JP-only pooled btc_dir, |m|>=1%, net of 20bp, dev vs check
T=pd.read_parquet("/Users/rytty/CCP/quant_v7/research/btc_ah/asia/trades_all.parquet")
for thr in ["|m|>=0.0","|m|>=0.01","|m|>=0.02"]:
    g=T[(T.fam=="btc_dir")&(T.par==thr)&(T.ticker.str.endswith("_T"))]
    for sp in ["dev","check"]:
        x=g[g.split==sp]
        print("JP pooled", thr, sp, stats(x["net"]), "tickers", sorted(x.ticker.unique()))
