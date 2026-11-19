import sys; sys.path.insert(0, "/Users/rytty/CCP/quant_v7/research/btc_ah/asia")
import numpy as np, pandas as pd
from lib import build, stats
o=build("0434_HK"); era=o["era"].iloc[0]; cut=o["cut"].iloc[0]
for W,thr in [(250,0.0),(120,0.0),(250,0.5),(120,1.0)]:
    mp=max(20,W//2)
    beta=(o["g"].rolling(W,min_periods=mp).cov(o["m"])/o["m"].rolling(W,min_periods=mp).var()).shift(1)
    resid=o["g"]-beta*o["m"]; z=resid/resid.shift(1).rolling(W,min_periods=mp).std()
    d=(-np.sign(resid)*((z.abs()>=thr)&resid.notna()&(resid!=0))).fillna(0)
    gross=(d*(o["C"]/o["O"]-1))[d!=0]
    idx=o.index[d!=0]
    yr=pd.Series(gross.values-0.0,index=idx).groupby(idx.year)
    ystr=" ".join(f"{y}:{v.mean()*1e4:+.0f}({len(v)})" for y,v in yr)
    dv=gross[idx<cut]; ck=gross[idx>=cut]
    print(f"W={W} |z|>={thr} gross dev {dv.mean()*1e4:.1f}bp n{len(dv)} | chk {ck.mean()*1e4:.1f}bp n{len(ck)}")
    print("   net@20bpRT chk", stats(ck-0.002), " net@40bpRT chk", stats(ck-0.004), " breakeven RT bp (chk)", round(ck.mean()*1e4,1))
    print("   years(gross bp):", ystr)
