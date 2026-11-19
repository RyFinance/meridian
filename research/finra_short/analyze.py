import numpy as np,pandas as pd
from load import *
O=px['Open'][SV.columns].reindex(SV.index); SPYO=px['Open']['SPY'].reindex(SV.index)
SVR=SV/TV
mu=SVR.shift(1).rolling(20,min_periods=15).mean(); sd=SVR.shift(1).rolling(20,min_periods=15).std()
Z=(SVR-mu)/sd
idx=SV.index; DEV=idx<'2025-01-01'
COST=0.0020  # 4 sides x 5bp per LS cohort
def fwd(h): return O.shift(-(1+h))/O.shift(-1)-1
def nw(u,L):  # u: demeaned score series (already /N scaled handled by caller)
    n=len(u); g0=(u*u).sum(); s=g0
    for l in range(1,L+1): s+=2*(1-l/(L+1))*(u[l:]*u[:-l]).sum()
    return s
def tstat_mean(x,L):
    x=np.asarray(x,float); x=x[~np.isnan(x)]; n=len(x)
    if n<10: return np.nan
    m=x.mean(); v=nw(x-m,L)/n**2
    return m/np.sqrt(v) if v>0 else np.nan
def per(mask): return mask
def ls_series(S,h,flip=False):
    R=fwd(h); rk=S.rank(axis=1,pct=True); n=S.notna().sum(1)
    lo=(rk<=0.1); hi=(rk>0.9)
    lg=(R.where(lo)).mean(1); st=(R.where(hi)).mean(1)
    ok=R.notna().sum(1)>300
    ls=(lg-st).where(ok&(n>300)).rename('ls')
    if flip: ls=-ls
    dec=pd.DataFrame({d:R.where((rk>d/10)&(rk<=(d+1)/10)).mean(1) for d in range(10)})
    # turnover: fraction of today's long/short names not in yesterday's
    def to(m): 
        p=m.shift(1); return 1-((m&p).sum(1)/m.sum(1))
    tov=(to(lo)+to(hi))/2
    return ls,lg,st,dec,tov
rows=[];yr=[];out=[]
def rep(name,ls,h,tov):
    r={'v':name}
    for tag,m in (('dev',DEV),('chk',~DEV)):
        x=ls[m].dropna(); 
        if len(x)==0: continue
        g=x.mean()*1e4; ng=(x.mean()-COST)*1e4
        no=x.iloc[::h]
        r[tag]=dict(n=len(x),gross_bp=g,net_bp=ng,t_g=tstat_mean(x,h),t_n=tstat_mean(x-COST,h),
            t_nonov=tstat_mean(no,0) if len(no)>10 else np.nan,ann_g=x.mean()*252/h*100,ann_n=(x.mean()-COST)*252/h*100,
            flip_net_bp=(-x.mean()-COST)*1e4,tov=tov[m].mean())
    rows.append(r)
res={}
for sname,S in (('raw',SVR),('z20',Z)):
    for h in (1,5,20):
        ls,lg,st,dec,tov=ls_series(S,h); nm=f'H1 {sname} h{h}'
        rep(nm,ls,h,tov); res[nm]=(ls,lg,st,dec)
        yr.append((nm,{y:ls[ls.index.year==y].mean()*252/h*100 for y in range(2022,2027)}))
        # h=1 netted-turnover cost
        if h==1: r=rows[-1]; r['netted_net_bp']={t:(ls[m].mean()-COST*tov[m].mean())*1e4 for t,m in (('dev',DEV),('chk',~DEV))}
import json
print('=== H1 (LS lowest-minus-highest decile; bp per cohort; ann in %) ===')
for r in rows:
    print(r['v']); 
    for t in('dev','chk'): print('  ',t,{k:round(v,2) for k,v in r[t].items()})
    if 'netted_net_bp' in r: print('   netted',r['netted_net_bp'])
print('--- per-year gross ann % (LS)'); 
for nm,d in yr: print(nm,{k:round(v,1) for k,v in d.items()})
print('--- decile mean fwd return bp (dev | chk), D0 lowest SVR')
for nm,(ls,lg,st,dec) in res.items():
    print(nm,'dev',(dec[DEV].mean()*1e4).round(1).tolist(),'chk',(dec[~DEV].mean()*1e4).round(1).tolist())
# long/short legs vs universe
# H2
print('=== H2 events ===')
ew=lambda h: fwd(h).mean(1)
H2=[]
for h in range(1,6):
    R=fwd(h); AR=R.sub(R.mean(1),axis=0)
    for sg,ev in (('z>2',Z>2),('z<-2',Z<-2)):
        d={'v':f'H2 {sg} h{h}'}
        for tag,m in (('dev',DEV),('chk',~DEV)):
            E=ev.loc[m]; A=AR.loc[m].where(E)
            valid=A.notna().sum().sum(); 
            s=A.sum(1); n=A.notna().sum(1)
            Nn=n.sum(); mean=s.sum()/Nn
            u=(s-mean*n).values; v=nw(u,h)/Nn**2
            t=mean/np.sqrt(v)
            sign=1 if sg=='z>2' else -1
            d[tag]=dict(N=int(Nn),AR_bp=mean*1e4,t=t,net_if_long_bp=mean*1e4-10,net_if_short_bp=-mean*1e4-10)
        H2.append(d); print(d['v'],{t:{k:round(x,2) for k,x in d[t].items()} for t in('dev','chk')})
# H3
print('=== H3 market-level ===')
SPYr=SPYO.shift(-2)/SPYO.shift(-1)-1; SPYc=px['Close']['SPY'].reindex(idx).pct_change()
for nm,agg in (('vw',SV.sum(1)/TV.sum(1)),('ew',SVR.mean(1))):
    z=(agg-agg.shift(1).rolling(20).mean())/agg.shift(1).rolling(20).std()
    for tag,m in (('dev',DEV),('chk',~DEV)):
        d=pd.DataFrame({'z':z,'r':SPYr,'c':SPYc})[m].dropna()
        X=d['z']-d['z'].mean(); b=(X*(d['r']-d['r'].mean())).sum()/(X**2).sum()
        e=(d['r']-d['r'].mean())-b*X; score=(X*e).values
        v=nw(score,1)/(X**2).sum()**2; 
        # tradable sign strategy: long SPY next day if z<0 else short -> skip; report corr
        print('H3',nm,tag,'n',len(d),'slope bp per 1z',round(b*1e4,2),'t',round(b/np.sqrt(v),2),'corr',round(d['z'].corr(d['r']),3),'contemp corr',round(d['z'].corr(d['c']),3))
