import numpy as np, pandas as pd, warnings; warnings.filterwarnings("ignore")
from scipy import stats as st
from research.zb_itb.verify.f3_canonical import build, ld
CAL='/Users/rytty/CCP/polymarket_arb/state/cache/economic_calendar.csv'
c=pd.read_csv(CAL,low_memory=False); c=c[(c.region_code=='US')&(c.date>='2024-05-01')&(c.date<='2026-10-16')]
c=c[c.actual.notna()]
T={'starts':r'^Housing Starts$|^Housing Starts [A-Z]{3}$','newhome':r'^New Home Sales( [A-Z]{3})?$','existing':r'^Existing Home Sales( [A-Z]{3})?$',
 'pending':r'^Pending Home Sales MoM','constr':r'^Construction Spending MoM','nahb':r'^NAHB','cs':r'Case-Shiller Home Price YoY'}
ev={}
for k,p in T.items():
    m=c[c.event.str.contains(p,regex=True)]
    ev[k]=pd.to_datetime(sorted(set(m.date)))
# drop 2026-03-19 permits-oddities not needed. print counts
for k,v in ev.items(): print(k,len(v))
DEV_END=pd.Timestamp('2025-06-30')
e=ld("ITB_60m.parquet"); s=ld("SPY_60m.parquet")
def days(e):
    e=e.copy(); e['D']=e.index.normalize().tz_localize(None); e['t']=e.index.strftime('%H:%M'); return e
def tab(e):
    e=days(e); rows={}
    for D,g in e.groupby('D'):
        gg=g.set_index('t')
        if '09:30' not in gg.index or '15:30' not in gg.index or '10:30' not in gg.index or '11:30' not in gg.index: continue
        L=lambda a,b: np.log(b/a)
        rows[D]=dict(b0930=L(gg.loc['09:30','Open'],gg.loc['09:30','Close']), b1030=L(gg.loc['10:30','Open'],gg.loc['10:30','Close']),
          b1130=L(gg.loc['11:30','Open'],gg.loc['11:30','Close']), p1130=L(gg.loc['11:30','Open'],gg.loc['15:30','Close']),
          p1030=L(gg.loc['10:30','Open'],gg.loc['15:30','Close']), rng0930=np.log(gg.loc['09:30','High']/gg.loc['09:30','Low']))
    return pd.DataFrame(rows).T
X=tab(e); XS=tab(s)
Z=build("ITB","ZB_F_60m.parquet"); Z=Z.dropna(subset=['d'])
Z['net']=Z.g_off-0.0004
X=X.join(Z[['d','net','g_off']])
R10=sorted(set().union(*[set(ev[k]) for k in ['newhome','existing','pending','constr','nahb']]))
R830=set(ev['starts']); R9=set(ev['cs']); R10=set(R10)
X['r10']=X.index.isin(R10); X['r830']=X.index.isin(R830); X['r9']=X.index.isin(R9)
X['dev']=X.index<=DEV_END
print("days",len(X),"r10",X.r10.sum(),"r830",X.r830.sum(),"both",(X.r10&X.r830).sum())
def tt(x):
    x=pd.Series(x).dropna(); n=len(x)
    if n<3: return (n,np.nan,np.nan)
    return n,x.mean()*1e4,x.mean()/(x.std()/np.sqrt(n))
def line(lab,x): n,m,t=tt(x); print(f"  {lab:34s} n={n:3d} mean={m:7.1f}bp t={t:5.2f}")
COST=0.0004
def mom(df,sig,tgt,name):
    s_=np.sign(df[sig]); r=(s_*df[tgt]-COST)
    line(name+" net(mom)",r); line(name+" gross",s_*df[tgt]); line(name+" FLIP net",-s_*df[tgt]-COST)
    return r
print("\n=== (a) 10:00 releases, ITB")
sets={'ALL10':X.r10,'newhome':X.index.isin(ev['newhome']),'existing':X.index.isin(ev['existing']),'pending':X.index.isin(ev['pending']),'constr':X.index.isin(ev['constr']),'nahb':X.index.isin(ev['nahb']),'ALL10_pure(no 0830/cs)':X.r10&~X.r830&~X.r9}
for k,m in sets.items():
    d=X[m]; print(k)
    mom(d,'b1030','p1130','10:30bar->11:30..close')
    mom(d,'b1030','b1130','10:30bar->11:30bar')
    mom(d,'b0930','p1030','09:30bar->10:30..close')
print("dev/check ALL10")
for lab,m in [('dev',X.dev),('check',~X.dev)]:
    print(lab); mom(X[X.r10&m],'b1030','p1130','10:30bar->11:30..close')
print("CONTROL non-release days (no r10/r830/r9)")
nr=X[~X.r10&~X.r830&~X.r9]; mom(nr,'b1030','p1130','10:30bar->11:30..close'); mom(nr,'b1030','b1130','10:30bar->11:30bar')
print("CONTROL SPY on ALL10 days")
XS2=XS.copy(); XS2['r10']=XS2.index.isin(R10); d=XS2[XS2.r10]; mom(d,'b1030','p1130','SPY 10:30bar->11:30..close')
# placebo: random day sets of same size from non-release days
rng=np.random.default_rng(0); n10=int(X.r10.sum()); vals=[]
pool=nr
for _ in range(2000):
    d=pool.sample(n10,random_state=int(rng.integers(1e9))); vals.append((np.sign(d.b1030)*d.p1130).mean())
real=(np.sign(X[X.r10].b1030)*X[X.r10].p1130).mean()
print(f"  placebo perm: real gross mean {real*1e4:.1f}bp, placebo mean {np.mean(vals)*1e4:.1f}, p(two-sided)={np.mean(np.abs(vals)>=abs(real)):.3f}")
print("\n=== (b) ZB rule (net, 4bp RT) by day type")
line("all days",X.net)
for k,m in [('08:30 starts days',X.r830),('10:00 release days',X.r10),('10:00 release pure',X.r10&~X.r830&~X.r9),('CS 09:00 days',X.r9),('non-release',~X.r10&~X.r830&~X.r9)]:
    line(k,X[m].net); 
    if (X[m].dev).sum()>0:
        line("   dev",X[m&X.dev].net); line("   check",X[m&~X.dev].net)
def welch(a,b,lab):
    a,b=a.dropna(),b.dropna(); r=st.ttest_ind(a,b,equal_var=False); print(f"  diff {lab}: {(a.mean()-b.mean())*1e4:.1f}bp  Welch t={r.statistic:.2f} p={r.pvalue:.3f}")
nrm=~X.r10&~X.r830&~X.r9
welch(X[X.r830].net,X[nrm].net,'0830 vs non'); welch(X[X.r10].net,X[nrm].net,'10:00 vs non')
for k in ['newhome','existing','pending','constr','nahb']:
    m=X.index.isin(ev[k]); line(f"ZB rule on {k} days",X[m].net)
print("\n=== (c) first-hour vol (09:30 bar)")
X['abs0930']=X.b0930.abs()
for k,m in [('08:30 days',X.r830),('10:00 days',X.r10),('CS days',X.r9),('non-release',nrm)]:
    print(f"  {k:12s} n={m.sum():3d} mean|ret|={X[m].abs0930.mean()*1e4:6.1f}bp  mean range={X[m].rng0930.mean()*1e4:6.1f}bp  sd={X[m].b0930.std()*1e4:6.1f}")
for k,m in [('08:30',X.r830),('10:00',X.r10),('CS',X.r9)]:
    for col in ['abs0930','rng0930']:
        r=st.mannwhitneyu(X[m][col],X[nrm][col]); print(f"  MWU {k} vs non {col}: p={r.pvalue:.3f}")
print("\n=== skip/double on 10:00 days: ZB rule gross/net (above) and sizing sim")
base=X.net.dropna()
for lab,w in [('skip',0.0),('double',2.0),('half',0.5)]:
    sc=np.where(X.r10,w,1.0); r=(X.g_off*sc-COST*sc).dropna()
    print(f"  {lab:7s} total={r.sum()*1e4:8.0f}bp mean={r.mean()*1e4:5.1f}bp Sharpe-ish t={r.mean()/(r.std()/np.sqrt(len(r))):.2f}")
r=X.net.dropna(); print(f"  base    total={r.sum()*1e4:8.0f}bp mean={r.mean()*1e4:5.1f}bp t={r.mean()/(r.std()/np.sqrt(len(r))):.2f}")
