import numpy as np, pandas as pd, os
V="research/zb_itb/verify/yf_cache/"; Cc="research/zb_itb/round6/rates2/cache/"
def ld(p):
    d=pd.read_parquet(p); d.index=d.index.tz_convert("America/New_York"); return d
Z={"ZB":ld(V+"ZB_F_60m.parquet"),"ZN":ld(V+"ZN_F_60m.parquet")}
def build(sym,zk):
    z=Z[zk]; f=Cc if os.path.exists(Cc+f"{sym}_60m.parquet") else V
    e=ld(f+f"{sym}_60m.parquet"); e1=pd.read_parquet(f+f"{sym}_1d.parquet")
    e1.index=pd.to_datetime(e1.index).tz_localize(None).normalize()
    first=e[e.index.time==pd.Timestamp("09:30").time()]; days=list(first.index.normalize()); rows=[]
    for i in range(1,len(days)):
        D,pv=days[i],days[i-1]; t0,t1=pv+pd.Timedelta(hours=15),D+pd.Timedelta(hours=8)
        if t0 not in z.index or t1 not in z.index: continue
        m=np.log(z.loc[t1,"Close"]/z.loc[t0,"Close"]); b=first.iloc[i]; dd=pd.Timestamp(D.date())
        en=e1.loc[dd,"Open"] if dd in e1.index else np.nan
        if not np.isfinite(en): continue
        rows.append(dict(date=dd,d=np.sign(m),r=np.log(b.Close/en)))
    r=pd.DataFrame(rows).set_index("date"); return r[r.d!=0]
def tstat(x): return x.mean()/x.std()*np.sqrt(len(x)) if len(x)>2 and x.std()>0 else np.nan
DEV=("2024-05-28","2025-06-30"); CHK=("2025-07-01","2026-10-16")
areas={
"1 bondETF":("LQD VCIT IGIB HYG JNK EMB MUB PFF MBB TLT IEF SHY".split(),+1),
"2 beneficiaries":("MET PRU LNC CRBG SCHW IBKR HOOD".split(),-1),
"3 longdur":("XBI IPO ARKG ARKK VPU IDU NEE DUK SO AWK AEP ARCC MAIN".split(),+1)}
cost={s:1 for s in "LQD HYG TLT IEF".split()}
for s in "MET PRU SCHW IBKR NEE DUK SO XBI VPU".split(): cost[s]=2
for s in "IPO ARKG ARKK LNC CRBG HOOD MAIN IDU AWK AEP ARCC".split(): cost[s]=5 if s in("IPO","LNC","CRBG","MAIN") else 2
c=lambda s:cost.get(s,2)*2e-4
itb=build("ITB","ZB"); itbp=itb.d*itb.r-4e-4
spy={k:build("SPY",k) for k in Z}
out=[]; pn={}
for a,(syms,sg) in areas.items():
    for s in syms:
        for k in Z:
            r=build(s,k); p=sg*r.d*r.r-c(s); pn[(s,k)]=p
            dv=p[DEV[0]:DEV[1]]; ck=p[CHK[0]:CHK[1]]
            fl=-sg*r.d*r.r-c(s)
            sp=sg*spy[k].d*spy[k].r-2e-4
            j=pd.concat([p,itbp],axis=1).dropna()
            out.append(dict(area=a,sym=s,sig=k,cost1w=c(s)*1e4,n=len(p),dev_bp=dv.mean()*1e4,dev_t=tstat(dv),chk_bp=ck.mean()*1e4,chk_t=tstat(ck),all_bp=p.mean()*1e4,all_t=tstat(p),
              flip_bp=fl.mean()*1e4,gross_bp=(p.mean()+c(s))*1e4,spy_t=tstat(sp),corrITB=j.corr().iloc[0,1]))
df=pd.DataFrame(out); df.to_csv("research/zb_itb/round6/rates2/results.csv",index=False)
pd.set_option("display.width",250); print(len(df),"variants")
print(df.round(2).to_string(index=False))
print("ITB ref all",itbp.mean()*1e4,tstat(itbp)); print("SPY placebo ZB t",tstat(spy["ZB"].d*spy["ZB"].r))
a=build("ARKG","ZB");print("ARKG sd bp",a.r.std()*1e4)
print("ZB/ZN sign agree",(Z["ZB"].index.size), (build("ARKG","ZB").d.reindex(build("ARKG","ZN").index)==build("ARKG","ZN").d).mean())
