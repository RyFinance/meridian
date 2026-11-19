import pandas as pd, numpy as np, sys
BASE = '/Users/rytty/CCP/quant_v7'
OUTD = BASE + '/research/btc_ah/options_daily'
CUT = pd.Timestamp('2026-08-10')          # sealed holdout starts after this date
DEV_END = pd.Timestamp('2022-06-30')
BTC = '/Users/rytty/CCP/BTC-Acum/data/btc_usd_1m_candles_polymarket_arb.parquet'
PATHS = {'MSTR': BASE + '/data/lse/options_mstr/MSTR.parquet',
         'IBIT': BASE + '/data/lse/options_ibit/IBIT.parquet'}

# ---------- BTC features (ET clock) ----------
b = pd.read_parquet(BTC, columns=['timestamp', 'open', 'close'])
b['et'] = b['timestamp'].dt.tz_convert('America/New_York').dt.tz_localize(None)
b = b[b.et < CUT + pd.Timedelta(days=1)]            # nothing dated after 2026-08-10 (ET)
b = b.drop_duplicates('et', keep='last').set_index('et').sort_index()
grid = pd.date_range(b.index[0].normalize(), b.index[-1], freq='1min')
BO = b['open'].reindex(grid).ffill(limit=5)
BC = b['close'].reindex(grid).ffill(limit=5)
days = pd.bdate_range('2017-08-14', CUT)
F = pd.DataFrame(index=days)
F['o1500'] = BO.reindex(days + pd.Timedelta(hours=15)).values
F['c1559'] = BC.reindex(days + pd.Timedelta(hours=15, minutes=59)).values   # 16:00 close
F['o0930'] = BO.reindex(days + pd.Timedelta(hours=9, minutes=30)).values
F['c0929'] = BC.reindex(days + pd.Timedelta(hours=9, minutes=29)).values    # known pre-open
F['lh'] = F.c1559 / F.o1500 - 1                       # 15:00-16:00 ET move
F['sess'] = F.c1559 / F.o0930 - 1                     # 09:30-16:00 ET move
F['off_in'] = F.c0929 / F.c1559.shift(1) - 1          # prior 16:00 -> today 09:29
F['off_out'] = F.off_in.shift(-1)                     # today 16:00 -> next day 09:29

# ---------- options ----------
def load_opts(U):
    df = pd.read_parquet(PATHS[U])
    df = df[df.ts < pd.Timestamp('2026-08-11', tz='UTC')]          # holdout cut
    df['d'] = df.ts.dt.tz_localize(None).dt.normalize()
    df = df[df.volume > 0].copy()
    df['exp'] = pd.to_datetime(df.expiry)
    df['dte'] = (df.exp - df.d).dt.days
    df = df[(df.dte >= 0) & (df.dte <= 60)].copy()
    df['K'] = df.strike.round(3)
    df['typ'] = df.opt_type.astype(str)
    return df[['d', 'exp', 'typ', 'K', 'dte', 'open', 'high', 'low', 'close']].reset_index(drop=True)

def parity_spot(df):
    s = df[df.dte.between(2, 30)]
    pv = s.pivot_table(index=['d', 'exp', 'K'], columns='typ', values='close', aggfunc='last')
    pv = pv.dropna(subset=['C', 'P']).reset_index()
    pv['diff'] = (pv.C - pv.P).abs()
    best = pv.loc[pv.groupby(['d', 'exp'])['diff'].idxmin()].copy()
    best['S'] = best.K + best.C - best.P
    return best.groupby('d').S.median()

def pick(byday, d, typ, lo, hi, target, tol=0.05):
    g = byday.get(d)
    if g is None: return None
    g = g[(g.typ == typ) & (g.dte >= lo) & (g.dte <= hi)]
    if g.empty: return None
    g = g[g.dte == g.dte.min()]                       # shortest eligible expiry
    i = (g.K - target).abs().idxmin()
    K, exp = g.loc[i, 'K'], g.loc[i, 'exp']
    if abs(K / target - 1) > tol: return None
    return exp, K

def pick_in_exp(byday, d, typ, exp, target):
    g = byday.get(d)
    if g is None: return None
    g = g[(g.typ == typ) & (g.exp == exp)]
    if g.empty: return None
    i = (g.K - target).abs().idxmin()
    K = g.loc[i, 'K']
    if abs(K / target - 1) > 0.10: return None
    return K

# ---------- costs / fills ----------
def hs(p): return max(0.03, 0.025 * p)
def fb(p): return p + hs(p)
def fs(p): return p - hs(p)

def trade_single(e, x):                       # e,x = (o,h,l,c) entry/exit bars, long option
    out = {}
    for name, pe, px in [('p', e[3], x[0]), ('w', e[1], x[2])]:   # primary: close->open; worst: high in, low out
        cost = 100 * fb(pe) + 0.65
        proc = 100 * fs(px) - 0.65
        out[name] = proc / cost - 1
    out['prem'] = e[3]
    return out

def trade_spread(eL, eS, xL, xS):             # long leg/short leg bars; debit spread
    out = {}
    cost_p = 100 * (fb(eL[0]) - fs(eS[0])) + 1.30
    proc_p = 100 * (fs(xL[3]) - fb(xS[3])) - 1.30
    cost_w = 100 * (fb(eL[1]) - fs(eS[2])) + 1.30
    proc_w = 100 * (fs(xL[2]) - fb(xS[1])) - 1.30
    out['p'] = proc_p / cost_p - 1
    out['w'] = proc_w / cost_w - 1
    out['prem'] = eL[0] - eS[0]
    return out

def stats(x):
    x = np.asarray(x, float)
    n = len(x)
    if n < 2: return dict(n=n, mean=np.nan, t=np.nan, win=np.nan)
    sd = x.std(ddof=1)
    return dict(n=n, mean=x.mean(), t=x.mean() / sd * np.sqrt(n) if sd > 0 else np.nan,
                win=(x > 0).mean(), avg_win=x[x > 0].mean() if (x > 0).any() else np.nan,
                avg_loss=x[x <= 0].mean() if (x <= 0).any() else np.nan)

# ---------- rule A: close t -> open t+1 single option, direction = sign of BTC move ----------
def run_a(U, S, df, byday, book, sig, thr, lo, hi, flip):
    rows = []
    for d in F.index[F.index <= CUT]:
        if d not in byday or d not in S.index: continue
        x = F.at[d, sig]
        if not np.isfinite(x) or abs(x) < thr or x == 0: continue
        sgn = np.sign(x) * (-1 if flip else 1)
        typ = 'C' if sgn > 0 else 'P'
        pk = pick(byday, d, typ, lo, hi, S[d])
        if pk is None: continue
        exp, K = pk
        nd = d + pd.offsets.BDay(1)
        ek, xk = (d, exp, typ, K), (nd, exp, typ, K)
        if ek not in book or xk not in book: continue
        r = trade_single(book[ek], book[xk])
        if r['prem'] < 0.10: continue
        rows.append(dict(d=d, ret_p=r['p'], ret_w=r['w']))
    return pd.DataFrame(rows)

# ---------- rule B: overnight BTC shock (>thr) -> defined-risk vertical in reversal direction ----------
def run_b(U, S, df, byday, book, thr, k, lo, hi, flip, width=0.10):
    rows = []
    idx = F.index
    for i, d in enumerate(idx):
        if d > CUT or i + k >= len(idx): break
        x = F.at[d, 'off_in']
        if not np.isfinite(x) or abs(x) < thr: continue
        prev = idx[i - 1]
        if prev not in S.index: continue
        s_est = S[prev] * (1 + x)                     # gap beta ~1 per brief; known pre-open
        bear = x > 0
        if flip: bear = not bear
        typ = 'P' if bear else 'C'
        pk = pick(byday, d, typ, lo, hi, s_est)
        if pk is None: continue
        exp, KL = pk
        tgt = s_est * (1 - width) if typ == 'P' else s_est * (1 + width)
        KS = pick_in_exp(byday, d, typ, exp, tgt)
        if KS is None or KS == KL: continue
        xd = idx[i + k]
        if exp <= xd: continue
        ek = [(d, exp, typ, KL), (d, exp, typ, KS)]
        xkk = [(xd, exp, typ, KL), (xd, exp, typ, KS)]
        if not all(z in book for z in ek + xkk): continue
        r = trade_spread(book[ek[0]], book[ek[1]], book[xkk[0]], book[xkk[1]])
        if r['prem'] < 0.10: continue
        rows.append(dict(d=d, ret_p=r['p'], ret_w=r['w']))
    return pd.DataFrame(rows)

# ---------- driver ----------
data = {}
for U in PATHS:
    df = load_opts(U)
    S = parity_spot(df)
    byday = {d: g for d, g in df.groupby('d')}
    book = dict(zip(zip(df.d, df.exp, df.typ, df.K), zip(df.open, df.high, df.low, df.close)))
    data[U] = (df, S, byday, book)
    print(U, 'rows', len(df), 'days', len(byday), 'spot days', len(S), 'range', S.index.min().date(), S.index.max().date(), flush=True)

# BTC-only: does the move keep going after 16:00?
print('\n== BTC: does 15-16 ET move carry past 16:00? (sign-aligned mean of next 16:00->09:29 move)')
for thr in [0, 0.005, 0.01]:
    m = F[(F.lh.abs() > thr) & F.off_out.notna()]
    al = np.sign(m.lh) * m.off_out
    print(f'  |lh|>{thr:.3f} n={len(m)} mean_aligned={al.mean()*1e4:.1f}bp t={al.mean()/al.std()*np.sqrt(len(al)):.2f} corr={np.corrcoef(m.lh, m.off_out)[0,1]:.3f}')
m = F[F.off_in.abs() > 0.04].dropna(subset=['off_in'])
print(f'  overnight |off_in|>4%: n={len(m)} (up {int((m.off_in>0).sum())}, down {int((m.off_in<0).sum())})')

results = []
TRADES = {}
def record(tag, U, rule_fn, flip_fn=None):
    out = rule_fn(False)
    dev = out[out.d <= DEV_END]; chk = out[out.d > DEV_END]
    fl = flip_fn(True) if flip_fn else None
    fchk = fl[fl.d > DEV_END] if fl is not None else None
    rec = dict(rule=tag, inst=U)
    for nm, sub in [('dev', dev), ('chk', chk)]:
        for col in ['ret_w', 'ret_p']:
            st = stats(sub[col]) if len(sub) else dict(n=0, mean=np.nan, t=np.nan, win=np.nan)
            rec[f'{nm}_n'] = st['n']; rec[f'{nm}_{col}_mean'] = st['mean']; rec[f'{nm}_{col}_t'] = st['t']
        if len(sub):
            rec[f'{nm}_win'] = stats(sub.ret_w)['win']
    if fchk is not None and len(fchk):
        rec['flip_chk_n'] = len(fchk); rec['flip_chk_mean_w'] = fchk.ret_w.mean(); rec['flip_chk_win'] = (fchk.ret_w > 0).mean()
    yr = out.assign(y=out.d.dt.year).groupby('y').ret_w.agg(['count', 'mean'])
    rec['per_year'] = '; '.join(f'{y}:{int(r["count"])}/{r["mean"]*100:+.0f}%' for y, r in yr.iterrows())
    rec['all_n'] = len(out); rec['all_mean_w'] = out.ret_w.mean() if len(out) else np.nan
    rec['all_win'] = (out.ret_w > 0).mean() if len(out) else np.nan
    if fl is not None: rec['flip_all_mean_w'] = fl.ret_w.mean() if len(fl) else np.nan; rec['flip_all_n'] = len(fl)
    rec['dev_ret_p_median'] = dev.ret_p.median() if len(dev) else np.nan
    rec['chk_ret_p_median'] = chk.ret_p.median() if len(chk) else np.nan
    rec['chk_ret_w_median'] = chk.ret_w.median() if len(chk) else np.nan
    rec['chk_win_p'] = (chk.ret_p > 0).mean() if len(chk) else np.nan
    rec['chk_ret_p_t'] = stats(chk.ret_p)['t'] if len(chk) else np.nan
    rec['dev_ret_p_t'] = stats(dev.ret_p)['t'] if len(dev) else np.nan
    if fl is not None and len(fl):
        rec['flip_all_mean_p'] = fl.ret_p.mean(); rec['flip_chk_mean_p'] = fl[fl.d > DEV_END].ret_p.mean() if (fl.d > DEV_END).any() else np.nan
    TRADES[tag + ' | ' + U] = (out, fl)
    results.append(rec)
    return out

n_variants = 0
for U in PATHS:
    df, S, byday, book = data[U]
    for sig in ['lh', 'sess']:
        for thr in [0.0, 0.005, 0.01]:
            for lo, hi in [(2, 10), (2, 5), (6, 10)]:
                tag = f'A {sig} thr{thr*100:.1f}% dte{lo}-{hi} close->next open'
                record(tag, U,
                       lambda fl, sig=sig, thr=thr, lo=lo, hi=hi: run_a(U, S, df, byday, book, sig, thr, lo, hi, fl),
                       lambda fl, sig=sig, thr=thr, lo=lo, hi=hi: run_a(U, S, df, byday, book, sig, thr, lo, hi, fl))
                n_variants += 1
    for thr in [0.03, 0.04, 0.05]:
        for k in [1, 2, 4]:
            tag = f'B off_in>{thr*100:.0f}% reversal vertical open->close t+{k}'
            record(tag, U,
                   lambda fl, thr=thr, k=k: run_b(U, S, df, byday, book, thr, k, 3, 10, fl),
                   lambda fl, thr=thr, k=k: run_b(U, S, df, byday, book, thr, k, 3, 10, fl))
            n_variants += 1

R = pd.DataFrame(results)
R.to_csv(OUTD + '/variants.csv', index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 60)
print(f'\nvariants (primary rules, each with flip control): {n_variants}')
cols = ['rule', 'inst', 'dev_n', 'dev_ret_w_mean', 'dev_ret_w_t', 'chk_n', 'chk_ret_w_mean', 'chk_ret_w_t', 'chk_win', 'chk_ret_p_mean', 'flip_chk_mean_w', 'all_n']
print(R[cols].to_string(float_format=lambda v: f'{v:.3f}'))
R.to_pickle(OUTD + '/variants.pkl')
import pickle; pickle.dump(TRADES, open(OUTD + '/trades.pkl', 'wb'))
