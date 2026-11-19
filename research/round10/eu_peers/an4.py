import pandas as pd, numpy as np, warnings
warnings.filterwarnings("ignore")
ns={}; exec(open("an3.py").read().split("rows=[]")[0],ns)
globals().update(ns)
RND=["JPM","WMT","COST","NFLX","ADBE","UNH"]
def trade(c,k,ex,tau,peers=None,flip=1,hedge=False,cost_override=None):
    names,pp=CL[c]; peers=peers or pp
    s=cluster_sig(names,k); m=s.abs()>tau
    y=basket(peers,ex)
    if hedge: y=y-ur("SPY",ex)
    cost=(cost_override if cost_override is not None else 2*np.mean([SIDE[p] for p in peers]))*1e-4
    return (flip*np.sign(s[m])*y[m]-cost).dropna()
def rep(x):
    d=x[x.index<split]; c=x[x.index>=split]
    a=st(d); b=st(c); return f"dev n{a[0]} {a[1]:+.1f}bp t{a[2]:.2f} w{a[3]:.2f} | chk n{b[0]} {b[1]:+.1f}bp t{b[2]:.2f} w{b[3]:.2f}"
itb=pd.read_csv("../../zb_itb/verify/f3_trades_canonical.csv",index_col=0,parse_dates=True)
itb=(itb["g_off"]-0.0004).dropna()
cands=[("autos","B","1130",0.0),("autos","A","1030",0.01),("semis","B","1030",0.02),("pharma","B","1130",0.01),("luxury","B","cl",0.0),("luxury","A","cl",0.01),("obesity","B","cl",0.0),("chem","C","cl",0.01)]
for c,k,ex,tau in cands:
    print(f"\n### {c} sig{k} exit{ex} tau{tau}")
    r=trade(c,k,ex,tau); print(" rule      ",rep(r))
    print(" flip      ",rep(trade(c,k,ex,tau,flip=-1)))
    print(" SPY plcb  ",rep(trade(c,k,ex,tau,peers=["SPY"],cost_override=4)))
    print(" random6   ",rep(trade(c,k,ex,tau,peers=RND,cost_override=4)))
    print(" SPY-hedged",rep(trade(c,k,ex,tau,hedge=True,cost_override=2*np.mean([SIDE[p] for p in CL[c][1]])+4)))
    j=pd.concat([r,itb],axis=1,keys=["r","i"]).dropna()
    print(" corr w ITB rule: %.3f (n=%d)"%(j.r.corr(j.i),len(j)))
# pooled generic test over all non-control clusters
print("\n### POOLED all 12 non-control clusters, sig B / C / A, exit 1030/1130, tau 0.01, equal-weight by day")
for k in "ABC":
  for ex in ["1030","1130","cl"]:
    for tau in [0.0,0.01]:
        ser=[trade(c,k,ex,tau) for c in CL if c!="energy_ctrl"]
        x=pd.concat(ser).groupby(level=0).mean()
        print(k,ex,tau,rep(x))
print("\n### gross (no cost) pooled sig C tau 0.01 exit 1030:")
ser=[trade(c,"C","1030",0.01,cost_override=0) for c in CL if c!="energy_ctrl"]; print(rep(pd.concat(ser).groupby(level=0).mean()))
# partial repricing: slope gap vs slope open->exit, pooled per cluster (sig C)
print("\n### slope on residual C: gap (prev close->open) vs open->1030 vs open->close (dev+chk all), bp per 1% euro residual")
for c,(names,peers) in CL.items():
    s=cluster_sig(names,"C")
    g=pd.concat([gap[p] for p in peers],axis=1).mean(axis=1)
    y1=basket(peers,"1030"); y2=basket(peers,"cl")
    _,bg,tg=ols(g,s); _,b1,t1=ols(y1,s); _,b2,t2=ols(y2,s)
    print(f"{c:12s} gap {bg*100:5.1f}bp (t{tg:5.1f})  open->10:30 {b1*100:5.1f}bp (t{t1:4.1f})  open->close {b2*100:5.1f}bp (t{t2:4.1f})")
