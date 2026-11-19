import numpy as np, pandas as pd, glob, sys
sys.path.insert(0,'.')
from research.zb_itb.verify.f3_canonical import build
S=['DHI','LEN','PHM','TOL','KBH']; V='research/zb_itb/verify/vault/'
sig=build('ITB')[['d','m']]
rows={}
for s in S:
    x=pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(V+f'{s}_1m_*.parquet'))])
    x['ts']=x.ts.dt.tz_localize('UTC').dt.tz_convert('America/New_York'); x=x.drop_duplicates('ts').set_index('ts').sort_index()
    x['D']=x.index.normalize().tz_localize(None); x['t']=x.index.strftime('%H:%M')
    reg=x[(x.t>='09:30')&(x.t<'16:00')]
    cl=reg.groupby('D').close.last()
    def at(t,col): 
        y=x[x.t==t]; return y.set_index('D')[col]
    df=pd.DataFrame({'pc':cl.shift(1),'o':at('09:30','open'),'e31':at('09:30','close'),'e35':at('09:34','close'),'x':at('10:29','close')})
    # require exact bars; prior-close must be previous trading day in sig index
    rows[s]=df
P={k:pd.concat({s:rows[s][k] for s in S},axis=1) for k in ['pc','o','e31','e35','x']}
gap=np.log(P['o']/P['pc']); 
ok=sig.d.notna()&(sig.d!=0); idx=sig.index[ok]
gap=gap.reindex(sig.index); m=sig.m
# rolling beta, past-only, 120d
beta=pd.DataFrame(index=sig.index,columns=S,dtype=float)
for s in S:
    for i in range(len(sig)):
        if i<30: continue
        lo=max(0,i-120); y=gap[s].iloc[lo:i]; xx=m.iloc[lo:i]; k=y.notna()&xx.notna()
        if k.sum()<30: continue
        xv=xx[k]; beta.iloc[i,beta.columns.get_loc(s)]=(xv*y[k]).sum()/(xv*xv).sum()  # no-intercept
res=gap-beta.mul(m,axis=0)
d=sig.d
def rt(entry): return np.log(P['x'].reindex(sig.index)/P[entry].reindex(sig.index))
C=0.0003
def run(entry,mode,rng=None):
    r=rt(entry); out={}
    for D in sig.index:
        if not (d[D]==d[D] and d[D]!=0): continue
        rr=res.loc[D]; g=r.loc[D]
        if rr.isna().any() or g.isna().any(): continue
        sc=d[D]*rr
        lag=sc.idxmin(); lead=sc.idxmax()
        if mode=='lag': v=d[D]*g[lag]-2*C
        elif mode=='lead': v=d[D]*g[lead]-2*C
        elif mode=='rand': v=d[D]*g[rng.choice(S)]-2*C
        elif mode=='ew': v=d[D]*g.mean()-2*C
        elif mode=='ls': v=0.5*d[D]*(g[lag]-g[lead])-2*C
        elif mode=='ls_full': v=d[D]*(g[lag]-g[lead])-4*C   # $1 each leg
        elif mode=='lag2': v=d[D]*g[sc.nsmallest(2).index].mean()-2*C
        elif mode=='flip': v=-d[D]*g[lag]-2*C
        elif mode.startswith('name_'): v=d[D]*g[mode[5:]]-2*C
        out[D]=v
    return pd.Series(out)
def st(p):
    n=len(p); mu=p.mean(); t=mu/p.std()*np.sqrt(n); return f"n={n} mean={mu*1e4:6.1f}bp t={t:5.2f} Sh={mu/p.std()*np.sqrt(252):5.2f}"
dev=lambda p:p[p.index<='2025-06-30']; chk=lambda p:p[p.index>='2025-07-01']
rng=np.random.default_rng(0)
res_tab=[]
variants=[('lag','e31'),('lag','e35'),('lead','e31'),('ew','e31'),('ew','e35'),('ls','e31'),('ls_full','e31'),('ls','e35'),('lag2','e31'),('flip','e31')]+[('name_'+s,'e31') for s in S]
print("residual coverage",res.dropna().shape[0])
for mode,e in variants:
    p=run(e,mode)
    print(f"{mode:8s}{e}  ALL {st(p)} | DEV {st(dev(p))} | CHK {st(chk(p))}")
# random pick: average over 200 draws
for e in ['e31']:
    ts=[];ms=[]
    for k in range(200):
        p=run(e,'rand',np.random.default_rng(k)); ts.append(p.mean()/p.std()*np.sqrt(len(p))); ms.append(p.mean()*1e4)
    print("rand pick mean of means %.1fbp (sd %.1f) mean t %.2f"%(np.mean(ms),np.std(ms),np.mean(ts)))
# unconditional baseline: d x ew at 09:31 gross
print("sig days",int(ok.sum()))
for k in ['pc','o','e31','e35','x']: print(k,P[k].reindex(sig.index).loc[idx].notna().sum().to_dict())
print("gap valid",gap.loc[idx].notna().sum().to_dict(),"beta valid",beta.loc[idx].notna().sum().to_dict())
