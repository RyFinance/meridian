"""Round 9 COT -> ITB weekly test. Writes nothing outside this folder."""
import os, numpy as np, pandas as pd
from math import sqrt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = '/Users/rytty/CCP/quant_v7'
CUT = pd.Timestamp('2026-10-16')
DEV_END = pd.Timestamp('2016-12-31')
COST = 0.0004  # 2 bp per side, round trip 4 bp per traded week

def load_px(path):
    d = pd.read_parquet(path)
    d.index = pd.to_datetime(d.index)
    d = d[d.index <= CUT].sort_index()
    adj = d['Adj Close'] / d['Close']
    return pd.DataFrame({'aopen': d['Open'] * adj, 'aclose': d['Adj Close']})

ITB = load_px(f'{ROOT}/research/zb_itb/verify/yf_cache/ITB_1d.parquet')
SPY = load_px(f'{ROOT}/research/zb_itb/verify/yf_cache/SPY_1d.parquet')
ZB = load_px(f'{ROOT}/research/zb_itb/verify/yf_cache/ZB_F_1d.parquet')
ZN = load_px(f'{HERE}/ZN_F_1d.parquet')

# ---- COT (legacy format: noncommercial = speculators) ----
cot = pd.read_parquet(f'{ROOT}/data/lse/cot/cot.parquet')
cot['date'] = pd.to_datetime(cot['date'])
cot['release'] = pd.to_datetime(cot['release_date']).fillna(cot['date'] + pd.Timedelta(days=3))
cot = cot[cot['symbol'].isin(['ZB', 'ZN'])].copy()
cot['net'] = cot['noncomm_long'] - cot['noncomm_short']

def build_signals(c):
    c = c.sort_values('date').set_index('date')
    dnet = c['net'].diff()
    mu_l = c['net'].shift(1).rolling(52).mean(); sd_l = c['net'].shift(1).rolling(52).std()
    mu_c = dnet.shift(1).rolling(52).mean();     sd_c = dnet.shift(1).rolling(52).std()
    out = pd.DataFrame({'z_lvl': (c['net'] - mu_l) / sd_l,
                        'z_chg': (dnet - mu_c) / sd_c,
                        'release': c['release'],
                        'oi_chg': c['open_interest'].pct_change()})
    return out

SIG = {s: build_signals(cot[cot.symbol == s]) for s in ['ZB', 'ZN']}

def trade_week(anchor):
    """Release Friday (anchor) -> Monday open entry (anchor+3d), Friday close exit (anchor+7d)."""
    idx = ITB.index
    e = idx[idx >= anchor + pd.Timedelta(days=3)]
    x = idx[idx <= anchor + pd.Timedelta(days=7)]
    if len(e) == 0 or len(x) == 0: return None
    e, x = e[0], x[-1]
    if e > x or (x - e).days < 3 or e > CUT: return None
    return e, x

def leg_ret(px, e, x):
    if e not in px.index or x not in px.index: return np.nan
    return px.loc[x, 'aclose'] / px.loc[e, 'aopen'] - 1

rows = []
for s, sig in SIG.items():
    bondpx = ZB if s == 'ZB' else ZN
    for t, r in sig.dropna(subset=['z_lvl', 'z_chg']).iterrows():
        tw = trade_week(r.release)
        if tw is None: continue
        e, x = tw
        rows.append({'contract': s, 'sig_date': t, 'entry': e, 'exit': x,
                     'z_lvl': r.z_lvl, 'z_chg': r.z_chg, 'oi_chg': r.oi_chg,
                     'itb': leg_ret(ITB, e, x), 'spy': leg_ret(SPY, e, x), 'bond': leg_ret(bondpx, e, x)})
W = pd.DataFrame(rows)
src = {s: W[W.contract == s].reset_index(drop=True) for s in ['ZB', 'ZN']}

def pos_of(df, zcol, k, d):
    z = df[zcol].values
    return np.where(z >= k, 1, np.where(z <= -k, -1, 0)) * d

def stat(x):
    x = np.asarray(x, dtype=float); x = x[~np.isnan(x)]; n = len(x)
    if n < 2: return dict(n=n, mean=np.nan, t=np.nan, hit=np.nan)
    m = x.mean(); sd = x.std(ddof=1)
    return dict(n=n, mean=m * 1e4, t=m / (sd / sqrt(n)) if sd > 0 else np.nan, hit=(x > 0).mean())

def in_period(entries, per):
    e = pd.to_datetime(entries).values
    if per == 'dev': return e <= np.datetime64(DEV_END)
    if per == 'check': return e > np.datetime64(DEV_END)
    return np.ones(len(e), bool)

RULES = []
for c in ['ZB', 'ZN']:
    for k in [1.0, 1.5]:
        RULES += [(c, 'z_lvl', k, 1, f'LVL {c} |z|>={k} mom'), (c, 'z_lvl', k, -1, f'LVL {c} |z|>={k} contra'),
                  (c, 'z_chg', k, 1, f'CHG {c} |dz|>={k} cont'), (c, 'z_chg', k, -1, f'CHG {c} |dz|>={k} rev')]

results = []
for c, zcol, k, d, label in RULES:
    df = src[c]
    pos = pos_of(df, zcol, k, d)
    gross = pos * df['itb'].values
    net = gross - np.abs(pos) * COST
    spy_net = pos * df['spy'].values - np.abs(pos) * COST
    bond_dir = np.sign(df['bond'].values) * pos  # >0 means the signal called the bond move right
    for per in ['dev', 'check']:
        m = in_period(df['entry'], per) & (pos != 0)
        st = stat(net[m]); flip = stat(-gross[m] - np.abs(pos[m]) * COST)
        plc = stat(spy_net[m])
        results.append(dict(rule=label, per=per, n=st['n'], net_bp=st['mean'], t=st['t'], hit=st['hit'],
                            flip_bp=flip['mean'], flip_t=flip['t'], spy_bp=plc['mean'], spy_t=plc['t'],
                            bond_call_hit=(bond_dir[m] > 0).mean() if m.sum() else np.nan))
R = pd.DataFrame(results)
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
print(R.round(2).to_string(index=False))

print('\nITB weekly buy-and-hold (same weeks, no costs):')
for c in ['ZB', 'ZN']:
    df = src[c]
    for per in ['dev', 'check']:
        m = in_period(df['entry'], per)
        print(f'  {c} weeks {per}:', {k: round(v, 2) for k, v in stat(df['itb'].values[m]).items()})

print('\nweeks: ZB dev/check', int(in_period(src['ZB'].entry, 'dev').sum()), int(in_period(src['ZB'].entry, 'check').sum()),
      '| ZN dev/check', int(in_period(src['ZN'].entry, 'dev').sum()), int(in_period(src['ZN'].entry, 'check').sum()))
print('first/last ZB signal date:', src['ZB'].sig_date.min().date(), src['ZB'].sig_date.max().date(),
      '| last exit:', src['ZB'].exit.max().date())
print('OI jump weeks (|dOI|>5%): ZB', int((SIG['ZB'].oi_chg.abs() > 0.05).sum()), '| ZN', int((SIG['ZN'].oi_chg.abs() > 0.05).sum()))

W.to_pickle(f'{HERE}/weeks.pkl'); R.to_pickle(f'{HERE}/results.pkl')
