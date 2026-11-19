import pandas as pd, numpy as np, pickle, warnings
warnings.filterwarnings("ignore")
src=open("an.py").read()
# reuse defs
ns={}
exec(src.split("rows=[]")[0],ns)
us,sig,R,RES,dates,split,CL,SIDE=[ns[k] for k in "us sig R RES dates split CL SIDE".split()]
# A2: prev close from daily official close
for t in sig:
    d=pd.read_pickle(f"cache/{t}_1d.pkl"); d.index=pd.DatetimeIndex(d.index.tz_localize(None).normalize()) if d.index.tz is not None else d.index
    s=sig[t]
    # prev session's daily close = daily Close at the last daily date < D
    dc=d["Close"]
    pcd=pd.Series([dc[dc.index<D].iloc[-1] if (dc.index<D).any() else np.nan for D in s.index],index=s.index)
    R[t]["C"]=s.p1/pcd-1
# daily US gap: prev close -> 09:30 open
for t in R:
    if t=="^STOXX50E":continue
    pass
# beta residual for C
for t in RES:
    x=R[t]["C"]; m=R["^STOXX50E"]["C"].reindex(x.index)
    df=pd.concat([x,m],axis=1,keys=["x","m"]).dropna()
    beta=(df.x.rolling(60,min_periods=30).cov(df.m)/df.m.rolling(60,min_periods=30).var()).shift(1)
    RES[t]["C"]=df.x-beta*df.m
# US gap
d1={}
for t in us.columns.levels[0]:
    dd=pd.read_pickle(f"cache/{t}_1d.pkl"); dd.index=pd.DatetimeIndex(dd.index.tz_localize(None).normalize()) if dd.index.tz is not None else dd.index
    d1[t]=dd["Close"].shift(1).reindex(us.index)
gap={t:us[t]["ent"]/d1[t]-1 for t in d1}
def ols(y,x):
    df=pd.concat([y,x],axis=1).dropna()
    if len(df)<30: return (len(df),np.nan,np.nan)
    X=df.iloc[:,1].values; Y=df.iloc[:,0].values
    xm=X-X.mean(); b=(xm*Y).sum()/(xm**2).sum(); e=Y-Y.mean()-b*xm
    se=np.sqrt((e**2).sum()/(len(df)-2)/(xm**2).sum()); return (len(df),b,b/se)
PAIRS=[(e,u,c) for c,(es,ps) in CL.items() for e in es for u in ps]
rows=[]
for e,u,c in PAIRS:
    for k in "ACB":
        x=RES[e][k].reindex(dates)
        y=(us[u]["x1030"]/us[u]["ent"]-1)
        y2=(us[u]["x1130"]/us[u]["ent"]-1)
        for per,mask in [("dev",dates<split),("chk",dates>=split)]:
            n,b,t=ols(y[mask],x[mask]); _,bg,tg=ols(gap[u][mask],x[mask])
            big=x.where(x.abs()>0.02)
            nb,bb,tb=ols(y[mask],big[mask].fillna(0).where(big[mask].notna()))
            rows.append(dict(c=c,eu=e,us=u,sig=k,per=per,n=n,b1030=b,t1030=t,bgap=bg,tgap=tg,nbig=nb,bbig=bb,tbig=tb))
P=pd.DataFrame(rows); P.to_pickle("P.pkl")
pd.set_option("display.width",250); pd.set_option("display.max_rows",500)
W=P.pivot_table(index=["c","eu","us","sig"],columns="per",values=["b1030","t1030","bgap","tgap","tbig"])
print(W.round(2).to_string())
