import pandas as pd, numpy as np
from univ import *
P=pd.read_pickle('panel.pkl'); S=pd.read_pickle('sig.pkl'); MC=pd.read_pickle('mcap.pkl')
SIGDAYS=S.dropna().index
CUT=SIGDAYS[int(len(SIGDAYS)*0.55)]   # first day of check half
def beta_roll(gap,m,win=120,minp=60):
    """past-only OLS slope of gap on m (with intercept) over previous `win` obs; value at t uses data up to t-1."""
    x=m; y=gap
    ok=x.notna()&y.notna()
    xx=x.where(ok); yy=y.where(ok)
    n=ok.astype(float).rolling(win,min_periods=minp).sum()
    mx=xx.rolling(win,min_periods=minp).mean(); my=yy.rolling(win,min_periods=minp).mean()
    cxy=(xx*yy).rolling(win,min_periods=minp).mean()-mx*my
    vx=(xx*xx).rolling(win,min_periods=minp).mean()-mx*mx
    return (cxy/vx).shift(1)
def build_name(t,sig='ES'):
    p=P[t].join(S[[sig]].rename(columns={sig:'m'}),how='inner').dropna(subset=['m'])
    p=p[p.index.isin(SIGDAYS)] if sig=='ES' else p
    p['beta']=beta_roll(p.gap,p.m)
    # trade A: sign(m) from official open -> 10:30 bar close
    p['dA']=np.sign(p.m); p['gA']=p.dA*p.r_a
    # trade B: at 10:30 enter on sign(beta*m - gap); exit close
    p['sB']=p.beta*p.m-p.gap
    p['gB']=np.sign(p.sB)*p.r_b
    # variant B2: uses total move through 10:30
    p['sB2']=p.beta*p.m-p.mv1030
    p['gB2']=np.sign(p.sB2)*p.r_b
    # news-day filter: skip B if |gap| > 3x past-60d std of gap
    sd=p.gap.rolling(60,min_periods=30).std().shift(1)
    p['quiet']=(p.gap.abs()<3*sd)
    p['t']=t
    return p
def stats(x,label=''):
    x=pd.Series(x).dropna()
    if len(x)<5: return dict(label=label,n=len(x))
    return dict(label=label,n=len(x),mean_bp=x.mean()*1e4,t=x.mean()/x.std()*np.sqrt(len(x)),win=(x>0).mean())
def split(x):
    return x[x.index<CUT], x[x.index>=CUT]
