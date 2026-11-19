#!/usr/bin/env python3
"""MSTR share trade-management sweep keyed on BTC's 16:00 -> 09:25 ET move.

Dev   = stock_1m_dev RTH minutes, 2020-08-12..2023-12-31
Check = mstr_stock_1m_lse.parquet RTH minutes, 2026-04-29..2026-08-10 (holdout cutoff)
Nothing dated after 2026-08-10 is loaded.
"""
import glob
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path('/Users/rytty/CCP/quant_v7')
OUT = ROOT / 'research/btc_ah/shares_mgmt'
BTC_PATH = Path('/Users/rytty/CCP/BTC-Acum/data/btc_usd_1m_candles_polymarket_arb.parquet')
DEV_DIR = ROOT / 'research/mstr_btc_0dte/stock_1m_dev'
LSE_PATH = ROOT / 'research/mstr_btc_0dte/mstr_stock_1m_lse.parquet'
ET = 'America/New_York'
HOLD_END = pd.Timestamp('2026-08-10').date()
DEV_END = pd.Timestamp('2023-12-31').date()
CHK_START = pd.Timestamp('2026-04-29').date()
COST = 0.0006          # 3 bp per side, round trip on the position
NB = 390               # 09:30 .. 15:59 ET minute bars (index 389 = 15:59 bar, closes 16:00)
RTH0 = 9 * 60 + 30
NAN = float('nan')

# ---------------- BTC (bar label = bar open, UTC -> ET naive) ----------------
b = pd.read_parquet(BTC_PATH)
b = b[b['timestamp'] <= pd.Timestamp('2026-08-10 23:59:59', tz='UTC')]
bt = pd.DatetimeIndex(b['timestamp'].dt.tz_convert(ET).dt.tz_localize(None))
bser = pd.Series(b['close'].values, index=bt).sort_index()
bser = bser[~bser.index.duplicated(keep='last')]
BIDX = bser.index


def btc_px(t):
    """Close of the last BTC 1m bar that has closed by time t (label <= t-1min)."""
    t0 = pd.Timestamp(t) - pd.Timedelta(minutes=1)
    i = BIDX.searchsorted(t0, side='right') - 1
    if i < 0 or (t0 - BIDX[i]) > pd.Timedelta(minutes=10):
        return NAN
    return float(bser.iloc[i])


# ---------------- MSTR minutes ----------------
frames = []
for f in sorted(glob.glob(str(DEV_DIR / '*.parquet'))):
    d = pd.read_parquet(f)
    ts = pd.to_datetime(d['time'], utc=True).dt.tz_convert(ET).dt.tz_localize(None)
    frames.append(pd.DataFrame({'ts': ts, 'o': d['open'].values, 'h': d['high'].values,
                                'l': d['low'].values, 'c': d['close'].values}))
dev = pd.concat(frames, ignore_index=True)
lse = pd.read_parquet(LSE_PATH)
# lse ts is naive UTC (volume profile: RTH spike at 13:30-20:00 UTC, none at 09:30 ET)
lts = pd.to_datetime(lse['ts']).dt.tz_localize('UTC').dt.tz_convert(ET).dt.tz_localize(None)
lse = pd.DataFrame({'ts': lts, 'o': lse['open'].values, 'h': lse['high'].values,
                    'l': lse['low'].values, 'c': lse['close'].values})
lse = lse[lse['ts'].dt.date <= HOLD_END]          # sealed holdout cut
m = pd.concat([dev, lse], ignore_index=True)
m['date'] = m['ts'].dt.date
m = m[m['date'] <= HOLD_END]
m['mi'] = m['ts'].dt.hour * 60 + m['ts'].dt.minute - RTH0
m = m[(m['mi'] >= 0) & (m['mi'] < NB)]
m = m.drop_duplicates(['date', 'mi'], keep='last')

days = {}
for d, g in m.groupby('date'):
    O = [NAN] * NB; H = [NAN] * NB; L = [NAN] * NB; C = [NAN] * NB
    for mi, o, h, l, c in zip(g['mi'].values, g['o'].values, g['h'].values, g['l'].values, g['c'].values):
        O[mi] = float(o); H[mi] = float(h); L[mi] = float(l); C[mi] = float(c)
    days[d] = (O, H, L, C)
dates = sorted(days)


def last_finite(arr):
    for i in range(NB - 1, -1, -1):
        if arr[i] == arr[i]:
            return i
    return -1


# ---------------- per-day features (all known before 09:25 / 09:31) ----------------
ROWS = []
for di, D in enumerate(dates):
    O, H, L, C = days[D]
    if O[0] != O[0] or O[1] != O[1]:
        continue
    period = 'dev' if D <= DEV_END else ('chk' if D >= CHK_START else None)
    if period is None:
        continue
    tD = pd.Timestamp(D)
    P = (tD - pd.offsets.BDay(1)).date()             # previous weekday (16:00 BTC reference)
    bp = btc_px(pd.Timestamp(P) + pd.Timedelta(hours=16))
    b925 = btc_px(tD + pd.Timedelta(hours=9, minutes=25))
    b930 = btc_px(tD + pd.Timedelta(hours=9, minutes=30))
    b1000 = btc_px(tD + pd.Timedelta(hours=10))
    if not all(x == x for x in (bp, b925, b930, b1000)):
        continue
    gap = NAN
    if P in days:
        Pc = days[P][3]
        li = last_finite(Pc)
        if li >= 0:
            gap = O[0] / Pc[li] - 1
    prior = dates[max(0, di - 10):di]
    rng = []
    for x in prior:
        Ox, Hx, Lx, Cx = days[x]
        li = last_finite(Cx)
        hs = [v for v in Hx if v == v]; ls = [v for v in Lx if v == v]
        if li >= 0 and hs and ls:
            rng.append((max(hs) - min(ls)) / Cx[li])
    atr = float(np.mean(rng)) if len(rng) >= 5 else NAN
    ROWS.append(dict(date=D, period=period, year=D.year, dow=tD.dayofweek,
                     btc_move=b925 / bp - 1, btc30=b1000 / b930 - 1, gap=gap, atr=atr,
                     O=O, H=H, L=L, C=C))

# gap beta fitted on DEV only
dv = [r for r in ROWS if r['period'] == 'dev' and r['gap'] == r['gap']]
BETA = sum(r['gap'] * r['btc_move'] for r in dv) / sum(r['btc_move'] ** 2 for r in dv)
for r in ROWS:
    r['resid'] = r['gap'] - BETA * r['btc_move'] if r['gap'] == r['gap'] else NAN
    r['lastC'] = last_finite(r['C'])
DEV_ABS = np.array([abs(r['btc_move']) for r in ROWS if r['period'] == 'dev'])
QS = np.quantile(DEV_ABS, [0.25, 0.5, 0.75])
print(f'days: dev={sum(r["period"]=="dev" for r in ROWS)} chk={sum(r["period"]=="chk" for r in ROWS)} '
      f'beta(dev)={BETA:.3f} |BTC| quartile cuts={np.round(QS*100,2)}%', flush=True)


# ---------------- rule components ----------------
def sign_base(r, dname):
    if dname == 'with':
        x = r['btc_move']
    elif dname == 'against':
        x = -r['btc_move']
    else:  # conv: converge MSTR open back to beta*BTC (overshoot -> short, undershoot -> long)
        x = -r['resid'] if r['resid'] == r['resid'] else NAN
    if x != x or x == 0:
        return 0
    return int(np.sign(x))


def entry_of(entry, r, s, worst):
    O, H, L, C = r['O'], r['H'], r['L'], r['C']
    e = None
    if entry == 'E0931':
        e = 1
    elif entry in ('OR5', 'OR15'):
        n = 5 if entry == 'OR5' else 15
        hs = [v for v in H[:n] if v == v]; ls = [v for v in L[:n] if v == v]
        if not hs or not ls:
            return None
        orh, orl = max(hs), min(ls)
        for k in range(n, NB - 1):
            c = C[k]
            if c != c:
                continue
            if (s > 0 and c > orh) or (s < 0 and c < orl):
                e = k + 1
                break
    elif entry in ('PB05', 'PB10'):
        p = 0.005 if entry == 'PB05' else 0.01
        ref = O[0]
        for k in range(1, NB - 1):
            c = C[k]
            if c != c:
                continue
            if (s > 0 and c <= ref * (1 - p)) or (s < 0 and c >= ref * (1 + p)):
                e = k + 1
                break
    elif entry == 'CONF31':   # enter 10:01 only if BTC 09:30->10:00 agrees with trade side
        if r['btc30'] == r['btc30'] and int(np.sign(r['btc30'])) == s:
            e = 31
    if e is None or e >= NB or O[e] != O[e]:
        return None
    P = (H[e] if s > 0 else L[e]) if worst else O[e]
    if P != P:
        return None
    return e, P


def sim_exit(spec, r, e, P, s, atr):
    """Return gross fractional return (sign-adjusted) for one trade. Stops checked before targets
    within a bar (conservative). Gap-through fills at the bar open."""
    O, H, L, C = r['O'], r['H'], r['L'], r['C']
    kind = spec[0]
    last = r['lastC']

    def rest(px):
        return s * (px / P - 1)

    if kind == 'time':
        k = spec[1]
        if k >= NB - 1:
            return rest(C[last])
        if O[k] == O[k] and k <= last:
            return rest(O[k])
        j = max(i for i in range(k + 1) if C[i] == C[i]) if any(C[i] == C[i] for i in range(k + 1)) else last
        return rest(C[j])

    if kind in ('fix', 'be'):
        a, bb = spec[1], spec[2]
    elif kind == 'atr':
        a, bb = spec[1] * atr, spec[2] * atr
    if kind in ('fix', 'atr', 'be'):
        sl = P * (1 - s * a); tp = P * (1 + s * bb)
    if kind == 'trail':
        x = spec[1]
    if kind == 'half':
        R, x = spec[1], spec[2]
        sl = P * (1 - s * R); tp1 = P * (1 + s * R)
    t0 = spec[3] if kind == 'be' else None

    half_done = False; half_ret = 0.0; be_on = False
    F = P
    fav = H if s > 0 else L
    adv = L if s > 0 else H

    def finish(px):
        if kind == 'half' and half_done:
            return 0.5 * half_ret + 0.5 * rest(px)
        return rest(px)

    def beyond(x, lvl):   # adverse crossing
        return x <= lvl if s > 0 else x >= lvl

    def beyond_fav(x, lvl):
        return x >= lvl if s > 0 else x <= lvl

    for k in range(e, NB):
        if O[k] != O[k] or fav[k] != fav[k] or adv[k] != adv[k]:
            continue
        if kind == 'trail':
            stop = F * (1 - s * x)
        elif kind == 'half':
            if half_done:
                stop = max(P, F * (1 - x)) if s > 0 else min(P, F * (1 + x))
            else:
                stop = sl
        elif kind == 'be':
            stop = P if be_on else sl
        else:
            stop = sl
        if beyond(O[k], stop):
            return finish(O[k])
        if beyond(adv[k], stop):
            return finish(stop)
        if kind in ('fix', 'atr', 'be'):
            if beyond_fav(O[k], tp):
                return finish(O[k])
            if beyond_fav(fav[k], tp):
                return finish(tp)
        if kind == 'half' and not half_done:
            if beyond_fav(O[k], tp1):
                half_done = True; half_ret = rest(O[k])
            elif beyond_fav(fav[k], tp1):
                half_done = True; half_ret = rest(tp1)
        F = max(F, fav[k]) if s > 0 else min(F, fav[k])
        if kind == 'be' and not be_on and beyond_fav(fav[k], P * (1 + s * t0)):
            be_on = True
    return finish(C[last])


def run(dname, entry, ex, flip=False, worst=False):
    out = []
    for r in ROWS:
        sb = sign_base(r, dname)
        if sb == 0:
            continue
        s = -sb if flip else sb
        if ex[0] == 'atr' and r['atr'] != r['atr']:
            continue
        ent = entry_of(entry, r, s, worst)
        if ent is None:
            continue
        e, P = ent
        g = sim_exit(ex, r, e, P, s, r['atr'])
        out.append((r['date'], r['period'], r['year'], r['dow'], abs(r['btc_move']), s, g - COST))
    return pd.DataFrame(out, columns=['date', 'period', 'year', 'dow', 'absb', 's', 'net'])


def stats(t):
    n = len(t)
    if n < 2:
        return dict(n=n, wr=NAN, mean=NAN, t=NAN, aw=NAN, al=NAN)
    x = t['net'].values
    sd = x.std(ddof=1)
    w = x[x > 0]; lo = x[x <= 0]
    return dict(n=n, wr=float((x > 0).mean()), mean=float(x.mean() * 1e4),
                t=float(x.mean() / sd * np.sqrt(n)) if sd > 0 else NAN,
                aw=float(w.mean() * 1e4) if len(w) else NAN,
                al=float(lo.mean() * 1e4) if len(lo) else NAN)


FILTERS = {
    'Q1_smallBTC': lambda d: d['absb'] <= QS[0],
    'Q2': lambda d: (d['absb'] > QS[0]) & (d['absb'] <= QS[1]),
    'Q3': lambda d: (d['absb'] > QS[1]) & (d['absb'] <= QS[2]),
    'Q4_bigBTC': lambda d: d['absb'] > QS[2],
    'Mon': lambda d: d['dow'] == 0, 'Tue': lambda d: d['dow'] == 1, 'Wed': lambda d: d['dow'] == 2,
    'Thu': lambda d: d['dow'] == 3, 'Fri': lambda d: d['dow'] == 4,
}

DIRS = ['with', 'against', 'conv']
ENTRIES = ['E0931', 'OR5', 'OR15', 'PB05', 'PB10', 'CONF31']
EXITS = [('fix', 0.005, 0.01), ('fix', 0.005, 0.02), ('fix', 0.01, 0.01), ('fix', 0.01, 0.02),
         ('fix', 0.01, 0.03), ('fix', 0.02, 0.03),
         ('atr', 0.5, 1.0), ('atr', 1.0, 2.0),
         ('trail', 0.01), ('trail', 0.02),
         ('half', 0.01, 0.01), ('half', 0.01, 0.02),
         ('time', 60), ('time', 150), ('time', 389),
         ('be', 0.01, 0.02, 0.005), ('be', 0.01, 0.02, 0.01)]


def exname(ex):
    k = ex[0]
    if k == 'fix': return f'SL{ex[1]*100:g}%/TP{ex[2]*100:g}%'
    if k == 'atr': return f'SL{ex[1]:g}ATR/TP{ex[2]:g}ATR'
    if k == 'trail': return f'trail{ex[1]*100:g}%'
    if k == 'half': return f'half@+{ex[1]*100:g}%+trail{ex[2]*100:g}%'
    if k == 'time': return {60: 'time10:30', 150: 'time12:00', 389: 'time16:00'}[ex[1]]
    if k == 'be': return f'SL{ex[1]*100:g}%/TP{ex[2]*100:g}%/BE@{ex[3]*100:g}%'


CACHE = {}


def get(dname, entry, ex, flip, worst=False):
    key = (dname, entry, ex, flip, worst)
    if key not in CACHE:
        CACHE[key] = run(dname, entry, ex, flip, worst)
    return CACHE[key]


def evaluate(dname, entry, ex, filt=None, worst=False):
    tN = get(dname, entry, ex, False, worst)
    tF = get(dname, entry, ex, True, worst)
    if filt:
        tN = tN[FILTERS[filt](tN)]; tF = tF[FILTERS[filt](tF)]
    res = dict(rule=f'{dname}|{entry}|{exname(ex)}' + (f'|{filt}' if filt else '') + ('|WORSTFILL' if worst else ''))
    for per in ('dev', 'chk'):
        s_ = stats(tN[tN.period == per])
        f_ = stats(tF[tF.period == per])
        for k, v in s_.items():
            res[f'{per}_{k}'] = v
        res[f'{per}_flip_mean'] = f_['mean']; res[f'{per}_flip_t'] = f_['t']; res[f'{per}_flip_wr'] = f_['wr']
    yrs = tN[tN.period == 'dev'].groupby('year')['net'].mean() * 1e4
    res['dev_by_year_bp'] = ' '.join(f'{y}:{v:+.0f}' for y, v in yrs.items())
    return res


if __name__ == '__main__':
    base = []
    for dname in DIRS:
        for entry in ENTRIES:
            for ex in EXITS:
                base.append(evaluate(dname, entry, ex))
    B = pd.DataFrame(base)
    print(f'base variants tested: {len(B)}', flush=True)
    B.to_csv(OUT / 'base_grid.csv', index=False)

    cand = B[B['dev_n'] >= 50].sort_values('dev_t', ascending=False).head(10)
    fl = []
    for _, row in cand.iterrows():
        parts = row['rule'].split('|')
        dname, entry = parts[0], parts[1]
        ex = next(x for x in EXITS if exname(x) == parts[2])
        for filt in FILTERS:
            fl.append(evaluate(dname, entry, ex, filt=filt))
    F_ = pd.DataFrame(fl)
    print(f'filter variants tested: {len(F_)}', flush=True)
    F_.to_csv(OUT / 'filter_grid.csv', index=False)

    ALL = pd.concat([B, F_], ignore_index=True)
    ALL.to_csv(OUT / 'all_results.csv', index=False)
    print(f'TOTAL tested rules: {len(ALL)} (plus {len(ALL)} flip controls computed)')
    cols = ['rule', 'dev_n', 'dev_wr', 'dev_mean', 'dev_t', 'dev_aw', 'dev_al',
            'chk_n', 'chk_wr', 'chk_mean', 'chk_t', 'dev_flip_mean', 'dev_flip_t', 'chk_flip_mean', 'chk_flip_t']
    pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30)
    pd.set_option('display.max_colwidth', 60)
    top = ALL[ALL['dev_n'] >= 50].sort_values('dev_t', ascending=False)
    print('\nTop 12 by dev t (n>=50):')
    print(top[cols].head(12).round(3).to_string(index=False))
    print('\nDev-positive-mean count:', int((ALL['dev_mean'] > 0).sum()),
          ' dev t>2:', int((ALL['dev_t'] > 2).sum()),
          ' dev t>3:', int((ALL['dev_t'] > 3).sum()))
    print('Best base variant by dev t:')
    print(B[cols].sort_values('dev_t', ascending=False).head(5).round(3).to_string(index=False))
