import numpy as np, pandas as pd
from pathlib import Path

R = Path('/Users/rytty/CCP/quant_v7/research/btc_ah')
OUT = R / 'swing'
END = pd.Timestamp('2026-08-10')
DEV_END = pd.Timestamp('2023-06-30')
START = pd.Timestamp('2020-08-10')  # one day before first signal (needs prior close)
TICKS = ['MSTR', 'MARA', 'RIOT', 'CLSK', 'HUT', 'CIFR', 'WULF', 'IREN', 'COIN', 'BTBT', 'IBIT', 'BITO']
MINERS = ['MARA', 'RIOT', 'CLSK', 'HUT', 'CIFR', 'WULF', 'IREN', 'BTBT']
HOLDS = [1, 2, 3, 5, 10]
ENTRIES = ['open', 'close']
THRS = [0.03, 0.05, 0.08]
FAMS = ['btc', 'gap']

# ---------- calendar (MSTR daily index, sealed at END) ----------
mstr = pd.read_parquet(R / 'tickers/MSTR_1d.parquet')
mstr.index = pd.to_datetime(mstr.index)
mstr = mstr[mstr.index <= END]
cal = mstr.index[mstr.index >= START]
L = len(cal)
is_dev = (cal <= DEV_END)

# ---------- BTC 1m (UTC), sealed at END ----------
b = pd.read_parquet('/Users/rytty/CCP/BTC-Acum/data/btc_usd_1m_candles_polymarket_arb.parquet',
                    columns=['timestamp', 'close'])
b = b[b.timestamp < pd.Timestamp('2026-08-11', tz='UTC')].sort_values('timestamp')
bt = b.timestamp.dt.tz_localize(None).values.astype('datetime64[ns]')
bc = b.close.values


def px_at(tg):
    # close of the last 1m bar whose close time <= tg (bar opening at tg-1min)
    q = tg - np.timedelta64(1, 'm')
    i = np.searchsorted(bt, q, side='right') - 1
    ic = np.clip(i, 0, None)
    ok = (i >= 0) & (bt[ic] >= q - np.timedelta64(10, 'm'))
    return np.where(ok, bc[ic], np.nan)


def et_to_utc(hh, mm):
    naive = pd.DatetimeIndex(cal) + pd.Timedelta(hours=hh, minutes=mm)
    loc = naive.tz_localize('America/New_York', nonexistent='shift_forward', ambiguous='NaT')
    return loc.tz_convert('UTC').tz_localize(None).values.astype('datetime64[ns]')


P16 = px_at(et_to_utc(16, 0))
P0925 = px_at(et_to_utc(9, 25))
m = np.full(L, np.nan)
m[1:] = P0925[1:] / P16[:-1] - 1  # 16:00 ET prior session -> 09:25 ET today


def load(t):
    d = pd.read_parquet(R / f'tickers/{t}_1d.parquet')
    d.index = pd.to_datetime(d.index)
    d = d[d.index <= END].reindex(cal)
    adj = d['adj close'].values / d['close'].values
    o = d.open.values * adj            # adjusted 09:30 open
    c = d['adj close'].values          # adjusted 16:00 close
    ro, rc = d.open.values, d.close.values  # raw, for the $5 cost tier
    cprev = pd.Series(c).shift(1).values
    gap = o / cprev - 1
    ms, gs = pd.Series(m), pd.Series(gap)
    cov = gs.rolling(250, min_periods=120).cov(ms).shift(1)   # past days only
    var = ms.rolling(250, min_periods=120).var().shift(1)
    beta = (cov / var).values
    r = gap - beta * m
    D = dict(o=o, c=c, ro=ro, rc=rc, gap=gap, r=r, beta=beta)
    D['g'], D['rt'] = {}, {}
    for N in HOLDS:
        g_o = pd.Series(c).shift(-(N - 1)).values / o - 1          # open t -> close t+N-1
        g_c = pd.Series(c).shift(-N).values / c - 1                # close t -> close t+N
        D['g'][('open', N)] = g_o
        D['g'][('close', N)] = g_c
        D['rt'][('open', N)] = 2 * np.where(ro < 5, 0.0010, 0.0003)  # round trip, 3bp/side (10bp if <$5)
        D['rt'][('close', N)] = 2 * np.where(rc < 5, 0.0010, 0.0003)
    return D


D = {t: load(t) for t in TICKS}


def greedy(mask, N):
    # non-overlapping: next entry must be >= N sessions after the last entry
    acc, last = [], -10**9
    for t in np.flatnonzero(mask):
        if t - last >= N:
            acc.append(t)
            last = t
    return np.array(acc, dtype=int)


def sig_x(fam, d):
    return m if fam == 'btc' else d['r']


def ticker_trades(k, fam, thr, entry, N):
    d = D[k]
    x = sig_x(fam, d)
    g = d['g'][(entry, N)]
    rt = d['rt'][(entry, N)]
    mask = np.isfinite(x) & (np.abs(x) > thr) & np.isfinite(g) & np.isfinite(rt)
    idx = greedy(mask, N)
    return pd.DataFrame({'t': idx, 'tk': k, 's': np.sign(x[idx]), 'g': g[idx], 'rt': rt[idx]})


def basket_trades(fam, thr, entry, N):
    G = np.vstack([D[k]['g'][(entry, N)] for k in MINERS])
    RT = np.vstack([D[k]['rt'][(entry, N)] for k in MINERS])
    Rr = np.vstack([D[k]['r'] for k in MINERS])
    if fam == 'btc':
        x = m.copy()
        ok = np.isfinite(G).sum(0) >= 4
    else:
        with np.errstate(all='ignore'):
            x = np.nanmean(Rr, axis=0)
        ok = (np.isfinite(G).sum(0) >= 4) & (np.isfinite(Rr).sum(0) >= 4)
    mask = np.isfinite(x) & (np.abs(x) > thr) & ok
    idx = greedy(mask, N)
    gb = np.nanmean(G[:, idx], axis=0)
    rtb = np.nanmean(RT[:, idx], axis=0)
    return pd.DataFrame({'t': idx, 'tk': 'BASKET', 's': np.sign(x[idx]), 'g': gb, 'rt': rtb})


def baseline(members, entry, N, period):
    # buy-and-hold over ALL days in the period, equal weight across members
    bl, bs = [], []
    for k in members:
        g = D[k]['g'][(entry, N)]
        rt = D[k]['rt'][(entry, N)]
        ok = np.isfinite(g) & np.isfinite(rt) & period
        bl.append(np.mean((g - rt)[ok]) if ok.any() else np.nan)
        bs.append(np.mean((-g - rt)[ok]) if ok.any() else np.nan)
    return np.nanmean(bl), np.nanmean(bs)  # members with no data in the period are skipped


def stats(T, direction, period, base):
    # T: trades with t,s,g,rt ; direction 'cont' (d=s) or 'rev' (d=-s)
    T = T[is_dev[T['t'].values] if period == 'dev' else ~is_dev[T['t'].values]]
    if len(T) == 0:
        return None
    dd = T['s'].values if direction == 'cont' else -T['s'].values
    net = dd * T['g'].values - T['rt'].values
    flip = -dd * T['g'].values - T['rt'].values
    df = pd.DataFrame({'t': T['t'].values, 'net': net})
    per_date = df.groupby('t')['net'].mean()
    n_d = len(per_date)
    tstat = per_date.mean() / (per_date.std(ddof=1) / np.sqrt(n_d)) if n_d > 1 else np.nan
    nL, nS = (dd > 0).sum(), (dd < 0).sum()
    bL, bS = base
    base_mean = (nL * bL + nS * bS) / (nL + nS)
    lm = net[dd > 0]; sm = net[dd < 0]
    lmean = lm.mean() if len(lm) else np.nan
    smean = sm.mean() if len(sm) else np.nan
    return dict(n=len(net), n_dates=n_d, win=(net > 0).mean(), mean=net.mean(), t=tstat,
                n_long=len(lm), long_mean=lmean, long_excess=lmean - bL if len(lm) else np.nan,
                n_short=len(sm), short_mean=smean, short_excess=smean - bS if len(sm) else np.nan,
                avg_win=net[net > 0].mean() if (net > 0).any() else np.nan,
                avg_loss=net[net <= 0].mean() if (net <= 0).any() else np.nan,
                flip_mean=flip.mean(), drift_base=base_mean, excess=net.mean() - base_mean)


# ---------- grid ----------
rows = []
units = {}
for fam in FAMS:
    for thr in THRS:
        for entry in ENTRIES:
            for N in HOLDS:
                pooled = pd.concat([ticker_trades(k, fam, thr, entry, N) for k in TICKS], ignore_index=True)
                bask = basket_trades(fam, thr, entry, N)
                units[(fam, thr, entry, N, 'POOLED12')] = (pooled, TICKS)
                units[(fam, thr, entry, N, 'MINER_BASKET')] = (bask, MINERS)
                for k in TICKS:
                    units[(fam, thr, entry, N, k)] = (pooled[pooled.tk == k], [k])

n_variants = 0
for key, (T, members) in units.items():
    fam, thr, entry, N, unit = key
    for period in ['dev', 'check']:
        pmask = is_dev if period == 'dev' else ~is_dev
        base = baseline(members, entry, N, pmask)
        for direction in ['cont', 'rev']:
            st = stats(T, direction, period, base)
            n_variants += 1
            if st is None:
                continue
            rows.append(dict(fam=fam, thr=thr, entry=entry, N=N, unit=unit, dir=direction, period=period, **st))

res = pd.DataFrame(rows)
res.to_csv(OUT / 'all_rules.csv', index=False)
print('rule-unit-direction-period rows:', len(res), 'variants(unit x rule x dir):', n_variants // 2)

sel_pool = res[(res.unit.isin(['POOLED12', 'MINER_BASKET'])) & (res.period == 'dev')]
sel_pool = sel_pool[(sel_pool.n_dates >= 30) & (sel_pool['mean'] > 0) & (sel_pool.excess > 0)]
pd.set_option('display.width', 250)
pd.set_option('display.max_columns', 30)
cols = ['fam', 'thr', 'entry', 'N', 'unit', 'dir', 'n', 'n_dates', 'win', 'mean', 't', 'flip_mean', 'drift_base', 'excess', 'long_excess', 'short_excess']
print('\nDEV candidates passing n>=30, mean>0, excess>0 (pooled+basket):', len(sel_pool))
print(sel_pool.sort_values('t', ascending=False)[cols].head(15).to_string(index=False))
top = sel_pool.sort_values('t', ascending=False).head(3)
top.to_csv(OUT / 'dev_top3.csv', index=False)
print('\nDEV top 3:')
print(top[cols].to_string(index=False))

# check results for the top 3 (only after selection is frozen)
chk = []
for _, r0 in top.iterrows():
    sub = res[(res.fam == r0.fam) & (res.thr == r0.thr) & (res.entry == r0.entry) & (res.N == r0.N) & (res.unit == r0.unit)]
    chk.append(sub)
chk = pd.concat(chk)
print('\nDEV vs CHECK for top 3 (and flip control inside):')
print(chk[['fam', 'thr', 'entry', 'N', 'unit', 'dir', 'period', 'n', 'n_dates', 'win', 'avg_win', 'avg_loss', 'mean', 't', 'flip_mean', 'drift_base', 'excess', 'n_long', 'long_excess', 'n_short', 'short_excess']].to_string(index=False))
chk.to_csv(OUT / 'top3_dev_check.csv', index=False)

# per-year for top 3
yr_rows = []
for _, r0 in top.iterrows():
    key = (r0.fam, r0.thr, r0.entry, r0.N, r0.unit)
    T = units[key][0]
    dd = T['s'].values if r0.dir == 'cont' else -T['s'].values
    net = dd * T['g'].values - T['rt'].values
    yrs = pd.Series(cal[T['t'].values].year)
    dfy = pd.DataFrame({'year': yrs.values, 'net': net})
    g = dfy.groupby('year')['net'].agg(['count', 'mean', lambda s: (s > 0).mean()]).reset_index()
    g.columns = ['year', 'n', 'mean_net', 'win']
    g['rule'] = f"{r0.fam}{r0.thr}_{r0.entry}_N{r0.N}_{r0.unit}_{r0.dir}"
    yr_rows.append(g)
yr = pd.concat(yr_rows)
yr.to_csv(OUT / 'top3_per_year.csv', index=False)
print('\nPER YEAR:')
print(yr.to_string(index=False))

# per-ticker diagnostic for top 3 (check period only)
pt = res[(res.unit.isin(TICKS)) & (res.period == 'check')]
ptrows = []
for _, r0 in top.iterrows():
    sub = pt[(pt.fam == r0.fam) & (pt.thr == r0.thr) & (pt.entry == r0.entry) & (pt.N == r0.N) & (pt.dir == r0.dir)]
    ptrows.append(sub)
ptrows = pd.concat(ptrows)
print('\nPER TICKER (check) for top-3 specs:')
print(ptrows[['fam', 'thr', 'entry', 'N', 'unit', 'dir', 'n', 'mean', 't', 'excess']].to_string(index=False))
