import numpy as np, pandas as pd, os, glob, warnings; warnings.filterwarnings("ignore")
V="research/zb_itb/verify/yf_cache/"; M="research/zb_itb/round5/rate_universe/cache/"; O="research/zb_itb/round5/rate_universe/"
def ld(p):
    d=pd.read_parquet(p); d.index=d.index.tz_convert("America/New_York"); return d
Z={k:ld(V+f) for k,f in [("ZB","ZB_F_60m.parquet"),("ZN","ZN_F_60m.parquet")]}
def sig(z,days):
    out={}
    for i in range(1,len(days)):
        D,p=days[i],days[i-1]; t0,t1=p+pd.Timedelta(hours=15),D+pd.Timedelta(hours=8)
        out[D]=np.sign(np.log(z.loc[t1,"Close"]/z.loc[t0,"Close"])) if (t0 in z.index and t1 in z.index) else np.nan
    return pd.Series(out)
def build(s):
    f=M+s+"_60m.parquet"; g=M+s+"_1d.parquet"
    if not os.path.exists(f): f=V+s+"_60m.parquet"; g=V+s+"_1d.parquet"
    e=ld(f); d1=pd.read_parquet(g); d1.index=pd.to_datetime(d1.index).tz_localize(None)
    first=e[e.index.time==pd.Timestamp("09:30").time()]; days=list(first.index.normalize())
    df=pd.DataFrame(index=[d.tz_localize(None) for d in days])
    for k in Z:
        sg=sig(Z[k],days); df[k]=[sg.get(d,np.nan) for d in days]
    df["entry"]=[d1.Open.get(d,np.nan) for d in df.index]; df["exit"]=first.Close.values
    df["r"]=np.log(df.exit/df.entry)
    return df.dropna(subset=["r"])
UNI="RKT UWMC PFSI COOP AGNC NLY MTG RDN ESNT FNF FAF MTH MHO CCS LGIH DFH BLDR MAS OC TREX FBIN MHK SHW POOL LOW HD WHR INVH AMH MAA ESS UDR CPT SUI ELS O PLD XLRE NAIL REZ MORT ARKK IJT VBK ITB XHB SPY".split()
UNI+= ["DHI","LEN","PHM","TOL","KBH","NVR","TLT"]
two=set("HD LOW SHW PLD O XLRE ARKK ITB XHB AGNC NLY INVH AMH BLDR MAS POOL FNF SPY DHI LEN PHM TLT IWM MHK".split()); ten=set("NAIL REZ".split())
cost=lambda s:(2 if s in two else 10 if s in ten else 5)/1e4
DEV=("2024-05-28","2025-06-30"); CHK=("2025-07-01","2026-10-16")
def st(x):
    x=x.dropna()
    if len(x)<5: return (len(x),np.nan,np.nan,np.nan)
    return (len(x),x.mean()*1e4,x.mean()/x.std()*np.sqrt(len(x)),(x>0).mean())
UNI=[s for s in UNI if os.path.exists(M+s+'_60m.parquet') or os.path.exists(V+s+'_60m.parquet')]
D={s:build(s) for s in UNI}
rows=[]; net={}
for s,df in D.items():
    for k in ["ZB","ZN","AGR"]:
        d=df.ZB.where(df.ZB==df.ZN) if k=="AGR" else df[k]
        d=d.where(d!=0); g=d*df.r; n=g-2*cost(s); net[(s,k)]=n
        for nm,(a,b) in [("dev",DEV),("chk",CHK)]:
            n_,m,t,w=st(n[a:b]); fl=st((-g-2*cost(s))[a:b])
            rows.append(dict(sym=s,sig=k,per=nm,n=n_,mean=m,t=t,win=w,gross=g[a:b].mean()*1e4,flip_mean=fl[1],flip_t=fl[2]))
R=pd.DataFrame(rows); R.to_csv(O+"all_results.csv",index=False)
P=R.pivot(index=["sym","sig"],columns="per",values=["n","mean","t","win","flip_mean"]); P.columns=[a+"_"+b for a,b in P.columns]
P=P.reset_index()
pd.set_option("display.width",250)
for k in ["ZB","ZN","AGR"]:
    print(k); print(P[P.sig==k].sort_values("t_dev",ascending=False)[["sym","n_dev","mean_dev","t_dev","win_dev","flip_mean_dev","n_chk","mean_chk","t_chk","win_chk","flip_mean_chk"]].round(2).to_string(index=False))
import pickle; pickle.dump((D,net),open(O+"d.pkl","wb"))
