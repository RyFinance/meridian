import pandas as pd, numpy as np, warnings
warnings.filterwarnings("ignore")
ns={}; exec(open("an5.py").read().split('print("== family')[0],ns)
globals().update(ns)
RND=["JPM","WMT","COST","NFLX","ADBE","UNH"]
SWAP={"luxury":["GM","F"],"autos":["CPRI","EL"],"chem":["TPR","RL"]}
def rep(x):
    d=x[x.index<split]; c=x[x.index>=split]; a=st(d); b=st(c); al=st(x)
    return f"dev n{a[0]} {a[1]:+.1f}bp t{a[2]:.2f} w{a[3]:.2f} | chk n{b[0]} {b[1]:+.1f}bp t{b[2]:.2f} w{b[3]:.2f} | all n{al[0]} {al[1]:+.1f} t{al[2]:.2f}"
for k,ex,tau in [("C","1030",0.02),("C","1030",0.015),("C","cl",0.02),("A","cl",0.03),("A","1030",0.015)]:
    print(f"\n### FAMILY sig{k} exit{ex} tau{tau}")
    r=ser(k,ex,tau); print(" rule      ",rep(r))
    print(" flip      ",rep(ser(k,ex,tau,flip=-1)))
    print(" SPY plcb  ",rep(ser(k,ex,tau,peers_fn=lambda c:["SPY"],cost=4)))
    print(" random6   ",rep(ser(k,ex,tau,peers_fn=lambda c:RND,cost=4)))
    print(" xcluster  ",rep(ser(k,ex,tau,peers_fn=lambda c:SWAP[c])))
    print(" SPY-hedged",rep(ser(k,ex,tau,hedge=True,cost=12)))
    j=pd.concat([r,itb],axis=1,keys=["r","i"]).dropna(); print(" corr ITB %.3f n=%d"%(j.r.corr(j.i),len(j)))
print("\n### per-cluster, C, 1030, tau .015")
for c in FAM:
    names,pp=CL[c]; s=cluster_sig(names,"C"); m=s.abs()>0.015
    for p in pp:
        y=ur(p,"1030")[m]; x=(np.sign(s[m])*y-2*SIDE[p]*1e-4).dropna()
        print(f" {c:8s} {p:5s}",rep(x))
