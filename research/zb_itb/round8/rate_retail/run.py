import numpy as np, pandas as pd, os, warnings; warnings.filterwarnings("ignore")
V="../../verify/yf_cache/"; Cc="cache/"
def ld(p):
    d=pd.read_parquet(p); d.index=d.index.tz_convert("America/New_York"); return d
z=ld(V+"ZB_F_60m.parquet")
def build(e,e1d):
    first=e[e.index.time==pd.Timestamp("09:30").time()]; days=list(first.index.normalize()); rows=[]
    for i in range(1,len(days)):
        D,prev=days[i],days[i-1]; t0,t1=prev+pd.Timedelta(hours=15),D+pd.Timedelta(hours=8)
        if t0 not in z.index or t1 not in z.index: continue
        m=np.log(z.loc[t1,"Close"]/z.loc[t0,"Close"]); b=first.iloc[i]; dd=pd.Timestamp(D.date())
        off=e1d.loc[dd,"Open"] if dd in e1d.index else np.nan
        rows.append(dict(date=dd,d=np.sign(m),g=np.log(b.Close/off) if off==off and off>0 else np.nan))
    r=pd.DataFrame(rows).set_index("date"); return r[(r.d!=0)].dropna()
def load(s,base):
    e=ld(f"{base}{s}_60m.parquet"); e1=pd.read_parquet(f"{base}{s}_1d.parquet"); e1.index=pd.to_datetime(e1.index).tz_localize(None).normalize()
    return build(e,e1)
G={"housing_tech":"OPEN Z ZG COMP","housing_cons":"RH W WSM ETD LZB","solar":"TAN ENPH RUN SEDG ARRY FSLR","fintech":"SOFI UPST AFRM ALLY COF SYF OMF","smallgrowth":"IWO CVNA"}
THIN={"OPAD","COMP","ETD","LZB"}
cost=lambda s:0.0020 if s in THIN else 0.0010
DEV=("2024-05-28","2025-06-30"); CHK=("2025-07-01","2026-10-16")
def st(p):
    p=p.dropna()
    if len(p)<10: return (len(p),np.nan,np.nan,np.nan)
    return (len(p),p.mean()*1e4,p.mean()/p.std()*np.sqrt(len(p)),(p>0).mean())
itb=load("ITB",V); itb_net=itb.g*itb.d.abs()*0+ (itb.d*itb.g) # g stored raw; apply sign below
def pnl(r,c): return r.d*r.g-c
itbp=pnl(itb,0.0004)
data={}; rows=[]
for g,ss in G.items():
    for s in ss.split():
        if not os.path.exists(f"{Cc}{s}_60m.parquet") or not os.path.exists(f"{Cc}{s}_1d.parquet"): continue
        r=load(s,Cc)
        if len(r)<200: print("skip",s,len(r)); continue
        data[s]=(g,r)
        p=pnl(r,cost(s)); f=-r.d*r.g-cost(s)
        a=p[DEV[0]:DEV[1]]; b=p[CHK[0]:CHK[1]]; fa=f[DEV[0]:DEV[1]]; fb=f[CHK[0]:CHK[1]]
        cd=pd.concat([p,itbp],axis=1).dropna().corr().iloc[0,1]
        gr=(r.d*r.g)
        rows.append(dict(sym=s,grp=g,cb=cost(s)*2e4,n=len(p),dev_bp=st(a)[1],dev_t=st(a)[2],dev_win=st(a)[3],chk_bp=st(b)[1],chk_t=st(b)[2],chk_win=st(b)[3],
                         gross_all_bp=gr.mean()*1e4,flip_dev=st(fa)[1],flip_chk=st(fb)[1],corrITB=cd))
T=pd.DataFrame(rows); pd.set_option("display.width",250)
print(T.round(2).to_string(index=False)); T.to_csv("per_name.csv",index=False)
print("ITB dev",st(itbp[DEV[0]:DEV[1]]),"chk",st(itbp[CHK[0]:CHK[1]]))
# groups
bk={}
print("\nGROUPS (equal weight, net)")
for g in G:
    ps=[pnl(r,cost(s)) for s,(gg,r) in data.items() if gg==g]
    if not ps: continue
    b=pd.concat(ps,axis=1).mean(axis=1); bk[g]=b
    a,c=st(b[DEV[0]:DEV[1]]),st(b[CHK[0]:CHK[1]])
    f=pd.concat([-(r.d*r.g)-cost(s) for s,(gg,r) in data.items() if gg==g],axis=1).mean(axis=1)
    print(g,len(ps),"dev",np.round(a,2),"chk",np.round(c,2),"flipchk",round(st(f[CHK[0]:CHK[1]])[1],1),"corrITB",round(pd.concat([b,itbp],axis=1).dropna().corr().iloc[0,1],2))
# 2-leg on check
def sh(p): return p.mean()/p.std()*np.sqrt(252)
for g,b in bk.items():
    df=pd.concat([itbp,b],axis=1,keys=["i","g"]).dropna(); df=df[CHK[0]:CHK[1]]
    two=df.mean(axis=1)
    print("2leg ITB+",g,"chk n",len(df),"ITB mean %.1f sh %.2f | 2leg mean %.1f sh %.2f | grp sh %.2f"%(df.i.mean()*1e4,sh(df.i),two.mean()*1e4,sh(two),sh(df.g)))
