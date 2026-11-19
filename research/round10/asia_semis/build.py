import pandas as pd, numpy as np
C='cache/'
asia=['000660.KS','005930.KS','2330.TW','8035.T','6857.T','6920.T']
us=['MU','NVDA','AMD','AVGO','AMAT','LRCX','KLAC','MRVL','SMH','SOXX','SPY','XLP','TER','TSM']
def ld(t,iv): return pd.read_pickle(C+f'{t}_{iv}.pkl')
# ---- Asia daily returns, indexed by local calendar date
A={}
for t in asia:
    d=ld(t,'1d'); d.index=pd.to_datetime(d.index.tz_localize(None).normalize())
    d=d[d['Close']>0]
    A[t]=d['Close']
Aret=pd.DataFrame({t:s.pct_change() for t,s in A.items()})   # return prev Asia close -> close on D
# ---- SOX prior-session return
sox=ld('^SOX','1d'); sox.index=pd.to_datetime(sox.index.tz_localize(None).normalize())
soxr=sox['Close'].pct_change().dropna()
# for each Asia date t, SOX return of last US session strictly before t (US date < t)
def prev_us(dates):
    idx=soxr.index.searchsorted(dates,side='left')-1
    return pd.Series(soxr.values[idx],index=dates)
resid={};beta={}
for t in asia:
    r=Aret[t].dropna()
    x=prev_us(r.index)
    b=pd.Series(np.nan,index=r.index)
    W=250
    cov=(r*x).rolling(W,min_periods=120).mean()-r.rolling(W,min_periods=120).mean()*x.rolling(W,min_periods=120).mean()
    var=(x**2).rolling(W,min_periods=120).mean()-x.rolling(W,min_periods=120).mean()**2
    bt=(cov/var).shift(1)   # uses pairs strictly before t
    resid[t]=r-bt*x; beta[t]=bt
Res=pd.DataFrame(resid)
# z-scores with past-only std (60d, shifted)
def z(df): return df/df.rolling(60,min_periods=30).std().shift(1)
Zr=z(Aret); Zs=z(Res)
# composite: equal-weight of z-scores, need >=4 available
def comp(Z):
    return Z.mean(axis=1).where(Z.notna().sum(axis=1)>=4)
Zr['COMP']=comp(Zr[asia]); Zs['COMP']=comp(Zs[asia])
Rr=Aret.copy(); Rr['COMP']=Aret.mean(axis=1).where(Aret.notna().sum(axis=1)>=4)
Rs=Res.copy(); Rs['COMP']=Res.mean(axis=1).where(Res.notna().sum(axis=1)>=4)
# ---- US 60m -> per-day open, c1030, c1130, close
rows={}
for t in us:
    d=ld(t,'60m'); idx=d.index.tz_convert('America/New_York')
    d.index=idx; d['date']=idx.normalize().tz_localize(None); d['hm']=idx.strftime('%H:%M')
    g=d.groupby('date')
    o=d[d.hm=='09:30'].set_index('date')['Open']
    c1=d[d.hm=='09:30'].set_index('date')['Close']
    c2=d[d.hm=='10:30'].set_index('date')['Close']
    cl=d[d.hm=='15:30'].set_index('date')['Close']
    pc=ld(t,'1d'); pc.index=pd.to_datetime(pc.index.tz_localize(None).normalize())
    df=pd.DataFrame({'o':o,'x1030':c1,'x1130':c2,'xcl':cl}).dropna(subset=['o'])
    df['prevclose']=pc['Close'].shift(1).reindex(df.index)
    rows[t]=df
import pickle
pickle.dump(dict(Rr=Rr,Rs=Rs,Zr=Zr,Zs=Zs,US=rows,Aret=Aret,beta=pd.DataFrame(beta)),open('panel.pkl','wb'))
print(Zr.describe().T[['count','mean','std']])
print(rows['MU'].tail(3)); print(rows['MU'].shape, rows['MU'].index[0])
print(pd.DataFrame(beta).describe().T)
