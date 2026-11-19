import pandas as pd, numpy as np, pickle, itertools, warnings
warnings.filterwarnings("ignore")
us=pd.read_pickle("us_panel.pkl"); sig=pickle.load(open("eu_sig.pkl","rb"))
# label check: pc vs daily close
for t in ["ASML.AS","ULVR.L"]:
    d=pd.read_pickle(f"cache/{t}_1d.pkl"); d.index=d.index.tz_localize(None).normalize()
    s=sig[t]; prev=s.pc.shift(-1)  # pc of next day = last bar close of this day's session
    c=pd.concat([d.Close,prev],axis=1).dropna().iloc[-300:]
    print("label check",t,"max rel diff last60m vs daily close:",(c.iloc[:,0]/c.iloc[:,1]-1).abs().median(),(c.iloc[:,0]/c.iloc[:,1]-1).abs().max())
dates=us.index
SIDE={"AMAT":2,"LRCX":5,"KLAC":5,"LLY":2,"BA":2,"ORCL":2,"CRM":2,"TPR":5,"RL":5,"CPRI":10,"EL":5,"GM":2,"F":2,"GE":2,"HON":2,"PG":2,"CL":5,"GIS":5,"KHC":5,"DOW":5,"LYB":5,"MRK":2,"PFE":2,"FCX":5,"XOM":2,"CVX":2,"SPY":2,"JPM":2,"WMT":2,"COST":2,"NFLX":2,"ADBE":2,"UNH":2}
CL={ "semis":(["ASML.AS"],["AMAT","LRCX","KLAC"]),
 "obesity":(["NOVO-B.CO"],["LLY"]),
 "aero":(["AIR.PA"],["BA"]),
 "software":(["SAP.DE"],["ORCL","CRM"]),
 "luxury":(["MC.PA","RMS.PA","KER.PA"],["TPR","RL","CPRI","EL"]),
 "autos":(["VOW3.DE","STLAM.MI","BMW.DE"],["GM","F"]),
 "industrial":(["SIE.DE"],["GE","HON"]),
 "household":(["ULVR.L"],["PG","CL"]),
 "food":(["NESN.SW"],["GIS","KHC"]),
 "chem":(["BAS.DE"],["DOW","LYB"]),
 "pharma":(["AZN.L"],["MRK","PFE"]),
 "mining":(["RIO.L"],["FCX"]),
 "energy_ctrl":(["SHEL.L"],["XOM","CVX"])}
# EU signals
idx=sig["^STOXX50E"]
def rets(t):
    s=sig[t]; return pd.DataFrame({"A":s.p1/s.pc-1,"B":s.p1/s.op-1})
R={t:rets(t) for t in sig}
RES={}
for t in sig:
    if t=="^STOXX50E": continue
    out={}
    for k in "AB":
        x=R[t][k]; m=R["^STOXX50E"][k].reindex(x.index)
        df=pd.concat([x,m],axis=1,keys=["x","m"]).dropna()
        cov=df.x.rolling(60,min_periods=30).cov(df.m); var=df.m.rolling(60,min_periods=30).var()
        beta=(cov/var).shift(1)   # past only
        out[k]=(df.x-beta*df.m)
    RES[t]=pd.DataFrame(out)
split=dates[int(len(dates)*0.55)]
print("sample",dates[0].date(),dates[-1].date(),"split",split.date())
EXITS={"1030":"x1030","1130":"x1130","cl":"xcl"}
def uret(t,ex):
    p=us[t]; return (p[EXITS[ex]]/p["ent"]-1)
def stats(x):
    x=x.dropna()
    if len(x)<8: return dict(n=len(x),m=np.nan,t=np.nan,w=np.nan)
    return dict(n=len(x),m=x.mean()*1e4,t=x.mean()/x.std(ddof=1)*np.sqrt(len(x)),w=(x>0).mean())
def sigser(names,k,filt):
    # composite signal per day
    r=pd.concat([R[n][k] for n in names],axis=1).reindex(dates)
    rs=pd.concat([RES[n][k] for n in names],axis=1).reindex(dates)
    if filt=="all": s=r.mean(axis=1)
    else:
        th={"r1":0.01,"r2":0.02}[filt]
        s=r.where(rs.abs()>th,0.0).where(r.notna()).mean(axis=1) # names without big move count as 0, but need >=1 big
        s=s.where((rs.abs()>th).any(axis=1))
    return s
def trades(names,peers,k,filt,ex,flip=1,peer_override=None):
    s=sigser(names,k,filt); s=s[s!=0]
    pr=pd.concat([uret(p,ex) for p in peers],axis=1).mean(axis=1)
    cost=2*np.mean([SIDE[p] for p in peers])*1e-4
    g=np.sign(s)*flip*pr.reindex(s.index)
    return (g-cost).dropna(), g.dropna()
rows=[]
for c,(names,peers) in CL.items():
    for k in "AB":
        for filt in ["all","r1","r2"]:
            for ex in EXITS:
                n,_=trades(names,peers,k,filt,ex)
                d=stats(n[n.index<split]); ch=stats(n[n.index>=split])
                rows.append(dict(cluster=c,sig=k,filt=filt,ex=ex,**{"d_"+a:b for a,b in d.items()},**{"c_"+a:b for a,b in ch.items()}))
T=pd.DataFrame(rows); T.to_csv("cluster_grid.csv",index=False)
pd.set_option("display.width",250); pd.set_option("display.max_rows",500)
print("=== top dev per cluster (n_dev>=25) ===")
best=[]
for c in CL:
    t=T[(T.cluster==c)&(T.d_n>=25)].sort_values("d_t",ascending=False)
    best.append(t.iloc[0])
print(pd.DataFrame(best).round(2).to_string())
print("=== all-days sign, ex=1030 (A and B) ===")
print(T[(T.filt=="all")&(T.ex=="1030")].round(2).to_string())
print("count variants:",len(T), "dev t>2:",(T.d_t>2).sum(),"of",len(T), " neg dev t<-2:",(T.d_t<-2).sum())
T.to_pickle("T.pkl")
