"""Sensitivity: bucket spread, roll-week exclusion, per-year breakdown. Folder-local."""
import os, numpy as np, pandas as pd
from math import sqrt
HERE = os.path.dirname(os.path.abspath(__file__))
W = pd.read_pickle(f'{HERE}/weeks.pkl')
ROOT = '/Users/rytty/CCP/quant_v7'
cot = pd.read_parquet(f'{ROOT}/data/lse/cot/cot.parquet'); cot['date'] = pd.to_datetime(cot['date'])
cot = cot[cot.symbol.isin(['ZB','ZN'])].copy()
cot['net'] = cot.noncomm_long - cot.noncomm_short
cot['oi_chg'] = cot.groupby('symbol').open_interest.pct_change()
roll = {}
for s in ['ZB','ZN']:
    c = cot[cot.symbol==s].sort_values('date').set_index('date')
    roll[s] = c.oi_chg.abs() > 0.05
DEV_END = np.datetime64('2016-12-31')
COST = 0.0004

def welch(a, b):
    a=np.asarray(a); b=np.asarray(b)
    if len(a)<2 or len(b)<2: return np.nan
    return (a.mean()-b.mean())/sqrt(a.var(ddof=1)/len(a)+b.var(ddof=1)/len(b))

print('== Bucket spread: mean ITB Mon-open->Fri-close return (bp) when z>=1 minus z<=-1 ==')
for s in ['ZB','ZN']:
    df = W[W.contract==s].reset_index(drop=True)
    for zc in ['z_lvl','z_chg']:
        for per in ['dev','check']:
            m = (df.entry.values <= DEV_END) if per=='dev' else (df.entry.values > DEV_END)
            hi = df.loc[m & (df[zc]>=1.0),'itb']; lo = df.loc[m & (df[zc]<=-1.0),'itb']
            print(f'{s} {zc} {per}: hi n={len(hi)} mean={hi.mean()*1e4:6.1f}  lo n={len(lo)} mean={lo.mean()*1e4:6.1f}  diff={(hi.mean()-lo.mean())*1e4:7.1f} welch_t={welch(hi,lo):5.2f}')

print('\n== Roll-clean sensitivity (drop signal weeks with |dOI|>5%), change rules k=1.0 ==')
for s in ['ZB','ZN']:
    df = W[W.contract==s].reset_index(drop=True)
    flag = roll[s].reindex(pd.to_datetime(df.sig_date)).fillna(False).values
    for d,name in [(1,'cont'),(-1,'rev')]:
        pos = np.where(df.z_chg>=1,1,np.where(df.z_chg<=-1,-1,0))*d
        pos = np.where(flag, 0, pos)
        for per in ['dev','check']:
            m = ((df.entry.values <= DEV_END) if per=='dev' else (df.entry.values > DEV_END)) & (pos!=0)
            x = pos[m]*df.itb.values[m] - COST
            t = x.mean()/(x.std(ddof=1)/sqrt(len(x))) if len(x)>1 else np.nan
            print(f'{s} CHG {name} roll-clean {per}: n={len(x)} net_bp={x.mean()*1e4:7.1f} t={t:5.2f}')

print('\n== Per-year net bp for LVL ZB |z|>=1 mom (+) and contra (-), ITB ==')
df = W[W.contract=='ZB'].reset_index(drop=True)
pos = np.where(df.z_lvl>=1,1,np.where(df.z_lvl<=-1,-1,0))
net = pos*df.itb.values - np.abs(pos)*COST
yr = pd.to_datetime(df.entry).dt.year
tab = pd.DataFrame({'yr':yr,'mom_net':np.where(pos!=0, net, np.nan)}).dropna()
g = tab.groupby('yr').mom_net.agg(['size','mean'])
g['mean']*=1e4
print(g.round(1).to_string())
print('positive-mom years:', int((g['mean']>0).sum()), 'of', len(g))
