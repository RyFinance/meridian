import pandas as pd, numpy as np, warnings
warnings.filterwarnings("ignore")
ns={}; exec(open("an4.py").read().split("itb=pd.read_csv")[0],ns)
globals().update(ns)
itb=pd.read_csv("../../zb_itb/verify/f3_trades_canonical.csv",index_col=0,parse_dates=True); itb=(itb["g_off"]-0.0004).dropna()
FAM=["luxury","autos","chem"]
def ser(k,ex,tau,flip=1,peers_fn=None,cost=None,hedge=False):
    out=[]
    for c in FAM:
        names,pp=CL[c]; s=cluster_sig(names,k); m=s.abs()>tau
        peers=peers_fn(c) if peers_fn else pp
        y=basket(peers,ex)
        if hedge: y=y-ur("SPY",ex)
        cs=(cost if cost is not None else 2*np.mean([SIDE[p] for p in peers]))*1e-4
        out.append((flip*np.sign(s[m])*y[m]-cs).dropna())
    return pd.concat(out).groupby(level=0).mean()
print("== family luxury+autos+chem: pooled (equal-weight per day) net; rows k,ex,tau")
res=[]
for k in "ABC":
  for ex in ["1030","1130","cl"]:
    for tau in [0.005,0.01,0.015,0.02,0.03]:
        x=ser(k,ex,tau); d=st(x[x.index<split]); c=st(x[x.index>=split]); g=ser(k,ex,tau,cost=0)
        gd=st(g[g.index<split]); gc=st(g[g.index>=split])
        res.append((k,ex,tau,*d,*c,gd[1],gc[1]))
R_=pd.DataFrame(res,columns="k ex tau n_d mu_d t_d w_d n_c mu_c t_c w_c gross_d gross_c".split())
pd.set_option("display.width",250); pd.set_option("display.max_rows",200)
print(R_.round(2).to_string())
print("variants",len(R_),"dev t>2:",(R_.t_d>2).sum())
R_.to_pickle("R_.pkl")
