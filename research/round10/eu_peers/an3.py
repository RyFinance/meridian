import pandas as pd, numpy as np, pickle, warnings
warnings.filterwarnings("ignore")
ns={}; exec(open("an2.py").read().split("PAIRS=")[0].replace("src=open","src=open"),ns)
globals().update({k:ns[k] for k in "us sig R RES dates split CL SIDE gap ols".split()})
EX={"1030":"x1030","1130":"x1130","cl":"xcl"}
def ur(t,ex): return us[t][EX[ex]]/us[t]["ent"]-1
def cluster_sig(names,k): return pd.concat([RES[n][k] for n in names],axis=1).reindex(dates).mean(axis=1)
def basket(peers,ex): return pd.concat([ur(p,ex) for p in peers],axis=1).mean(axis=1)
def st(x):
    x=x.dropna(); n=len(x)
    if n<8: return (n,np.nan,np.nan,np.nan)
    return (n,x.mean()*1e4,x.mean()/x.std(ddof=1)*np.sqrt(n),(x>0).mean())
rows=[]
for c,(names,peers) in CL.items():
    cost=2*np.mean([SIDE[p] for p in peers])*1e-4
    for k in "ABC":
        s=cluster_sig(names,k)
        for ex in EX:
            y=basket(peers,ex); ys=ur("SPY",ex)
            for tau in [0.0,0.005,0.01,0.02]:
                m=s.abs()>tau
                g=np.sign(s[m])*y[m]
                net=g-cost
                for per,mask in [("dev",dates<split),("chk",dates>=split)]:
                    n,mu,t,w=st(net[net.index[mask[dates.get_indexer(net.index)]]])
                    rows.append(dict(c=c,k=k,ex=ex,tau=tau,per=per,n=n,mu=mu,t=t,w=w))
Q=pd.DataFrame(rows).pivot_table(index=["c","k","ex","tau"],columns="per",values=["n","mu","t","w"])
Q.columns=[f"{a}_{b}" for a,b in Q.columns]; Q=Q.reset_index(); Q.to_pickle("Q.pkl")
pd.set_option("display.width",250); pd.set_option("display.max_rows",1000)
print("variants",len(Q))
good=Q[(Q.n_dev>=30)].sort_values("t_dev",ascending=False)
print(good.groupby("c").head(2).round(2).to_string())
print("dev t>2:",(Q.t_dev>2).sum(),"; of those check t>1.65:",((Q.t_dev>2)&(Q.t_chk>1.65)).sum())
print(Q[(Q.t_dev>2)].round(2).to_string())
