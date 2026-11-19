"""Build per-name daily panel + futures overnight signals. All bar labels START (verified in label_check.py)."""
import pandas as pd, numpy as np, os
from univ import *
NY='America/New_York'
def ld(t,iv):
    f=f'cache/{t}_{iv}.pkl'
    if not os.path.exists(f): return None
    d=pd.read_pickle(f)
    if d.index.tz is None: d.index=d.index.tz_localize(NY)
    d.index=d.index.tz_convert(NY); return d
# master calendar from SPY 60m (09:30 bars)
spy=ld('SPY','60m'); days=sorted(set(spy.index[spy.index.time==pd.Timestamp('09:30').time()].normalize()))
# futures signals: ln(bar 08:00 close / bar 15:00 close prev session). 08:00 start bar closes at 09:00.
sig={}
for f,n in [('ES=F','ES'),('NQ=F','NQ'),('RTY=F','RTY')]:
    z=ld(f,'60m'); c=z.Close; rows={}
    for i in range(1,len(days)):
        D,P=days[i],days[i-1]; t0,t1=P+pd.Timedelta(hours=15),D+pd.Timedelta(hours=8)
        if t0 in c.index and t1 in c.index: rows[D]=np.log(c[t1]/c[t0])
    sig[n]=pd.Series(rows)
S=pd.DataFrame(sig); S.index=S.index.tz_localize(None)
S.to_pickle('sig.pkl'); print('signal days',S.dropna().shape, S.index.min(), S.index.max())
def panel(t):
    h=ld(t,'60m'); d=ld(t,'1d')
    if h is None or d is None: return None
    d=d.copy(); d.index=d.index.tz_localize(None).normalize(); d=d[~d.index.duplicated()]
    d=d.dropna(subset=['Open','Close','Adj Close'])
    f=d['Adj Close']/d['Close']
    out=pd.DataFrame(index=d.index)
    out['O']=d.Open; out['Cl']=d.Close
    out['gap']=np.log(d.Open*f/(d['Adj Close'].shift(1)))   # dividend/split-adjusted open gap
    out['adv']=(d.Close*d.Volume).rolling(60,min_periods=20).median().shift(1)  # past-only $ADV
    out['dv']=d.Close*d.Volume
    hh=h.copy(); hh['D']=hh.index.normalize().tz_localize(None)
    b0=hh[hh.index.time==pd.Timestamp('09:30').time()].set_index('D')
    b1=hh[hh.index.time==pd.Timestamp('10:30').time()].set_index('D')
    out['o0h']=b0.Open; out['c1030']=b0.Close; out['o1030']=b1.Open
    out=out.dropna(subset=['O','c1030','Cl'])
    out['r_a']=np.log(out.c1030/out.O)          # trade A raw: MOO -> 10:30
    out['r_b']=np.log(out.Cl/out.o1030)         # trade B raw: 10:30 -> close
    out['mv1030']=out.gap+np.log(out.o1030/out.O)  # total move prev close -> 10:30 entry
    return out
P={}
for t in sorted(set(SMALL+LARGE+ETFS)):
    p=panel(t)
    if p is not None and len(p)>200: P[t]=p
    else: print('skip',t)
pd.to_pickle(P,'panel.pkl'); print(len(P),'names')
