import pickle, numpy as np, pandas as pd, sys, json
from universe import CLUSTERS, ALL, side_cost
rng = np.random.default_rng(7)
D = pickle.load(open('daily.pkl','rb')); EF = pd.read_pickle('earn_flat.pkl')
cal = D['SPY'].index; cal = cal[cal >= '2023-11-21']
START, END = pd.Timestamp('2024-05-01'), pd.Timestamp('2026-10-16')
T = {}
for t, d in D.items():
    d = d.reindex(cal)
    x = pd.DataFrame(index=cal)
    x['pc'] = d.close.shift(1); x['pm'] = d.pm; x['open'] = d.open; x['c1030'] = d.c1030; x['o1030'] = d.o1030; x['close'] = d.close
    x['pmr'] = x.pm / x.pc - 1; x['gap'] = x.open / x.pc - 1
    for k in (1, 3): x[f'c{k}'] = x.close.shift(-k)
    T[t] = x
spy = T['SPY']
def col(t, c): return T[t][c] if t in T else None
# earnings flags
bmo = EF[(EF.h >= 5) & (EF.h < 9)]
earn_dates = EF.groupby('t').date.apply(lambda s: np.array(sorted(s.unique()), dtype='datetime64[ns]')).to_dict()
def has_earn(t, d, lo=-1, hi=5):
    a = earn_dates.get(t)
    if a is None: return False
    return bool(((a >= (d + pd.Timedelta(days=lo)).to_datetime64()) & (a <= (d + pd.Timedelta(days=hi)).to_datetime64())).any())
# ---- events: cluster-day
events = []
for c, mem in CLUSTERS.items():
    mem = [m for m in mem if m in T]
    byday = bmo[bmo.t.isin(mem)].groupby('date').t.apply(list)
    for d, reps in byday.items():
        if d < START or d > END or d not in cal: continue
        reps = sorted(set(reps))
        peers = [m for m in mem if m not in reps and not has_earn(m, d)]
        if not peers: continue
        events.append(dict(cluster=c, date=d, reps=reps, peers=peers))
print('cluster-day events raw', len(events))
def sig_of(reps, d, kind):
    v = []
    for r in reps:
        x = T[r]
        if kind == 'A': a = x.pmr.get(d); b = spy.pmr.get(d)
        else: a = x.gap.get(d); b = spy.gap.get(d)
        if pd.notna(a) and pd.notna(b): v.append(a - b)
    return np.mean(v) if v else np.nan
def trade(tick, d, tim, hz, s):
    """gross signed return and net for one ticker. tim A: enter open; B: enter o1030."""
    x = T[tick]; e = x.open.get(d) if tim == 'A' else x.o1030.get(d)
    if hz == 'h1':
        if tim == 'B': return np.nan
        out = x.c1030.get(d)
    elif hz == 'day': out = x.close.get(d)
    elif hz == 'd1': out = x.c1.get(d)
    elif hz == 'd3': out = x.c3.get(d)
    if pd.isna(e) or pd.isna(out): return np.nan
    return s * (out / e - 1)
def basket(ticks, d, tim, hz, s, hedge=False):
    g = []; cst = []
    for t in ticks:
        r = trade(t, d, tim, hz, s)
        if pd.isna(r): continue
        if hedge:
            r -= trade('SPY', d, tim, hz, s) if True else 0
        g.append(r); cst.append(2 * side_cost(t))
    if not g: return np.nan, np.nan
    return np.mean(g), np.mean(g) - np.mean(cst) - (0.0004 if hedge else 0)
for ev in events:
    for kind in 'AB': ev['sig' + kind] = sig_of(ev['reps'], ev['date'], kind)
    ev['peerpm'] = np.nanmean([T[p].pmr.get(ev['date'], np.nan) - spy.pmr.get(ev['date'], np.nan) for p in ev['peers']])
    ev['npeer'] = len(ev['peers'])
ev_df = pd.DataFrame(events)
dates_all = sorted(ev_df.date.unique()); cut = dates_all[int(len(dates_all) * 0.55)]
print('dev/check cut date', cut, 'n dates', len(dates_all))
def cl_t(x, g):
    x = np.asarray(x, float); g = np.asarray(g); m = ~np.isnan(x); x, g = x[m], g[m]
    n = len(x)
    if n < 3: return np.nan
    mu = x.mean(); r = x - mu
    se = np.sqrt(sum(r[g == u].sum() ** 2 for u in np.unique(g)))
    return mu / se * n if se > 0 else np.nan
def stats(x, g, scale=1e4):
    x = np.asarray(x, float); m = ~np.isnan(x)
    if m.sum() == 0: return dict(n=0, nd=0, mean=np.nan, t=np.nan, win=np.nan)
    return dict(n=int(m.sum()), nd=len(set(np.asarray(g)[m])), mean=x[m].mean() * scale, t=cl_t(x, g), win=(x[m] > 0).mean())
def fmt(s): return f"n={s['n']:4d} nd={s['nd']:3d} mean={s['mean']:7.1f}bp t={s['t']:5.2f} win={s['win']:.2f}"
# ---- main grid
def run(tim, hz, thr, sel=None, hedge=False):
    k = 'sig' + tim; out = []
    for i, ev in ev_df.iterrows():
        s = ev[k]
        if pd.isna(s) or abs(s) < thr or sel is not None and not sel(ev): out.append((np.nan,) * 3 + (ev.date,)); continue
        g, n = basket(ev.peers, ev.date, tim, hz, np.sign(s), hedge)
        out.append((g, n, s, ev.date))
    return pd.DataFrame(out, columns=['gross', 'net', 'sig', 'date'])
RES = {}
variants = 0
print('\n=== GRID (net bp per cluster-day event; date-clustered t) ===')
for tim in 'AB':
    for thr in (0, .01, .02):
        for hz in (['h1', 'day', 'd1', 'd3'] if tim == 'A' else ['day', 'd1', 'd3']):
            r = run(tim, hz, thr); variants += 1
            dev = r[r.date < cut]; chk = r[r.date >= cut]
            RES[(tim, thr, hz)] = r
            print(f"{tim} thr={thr:.2f} {hz:3s} | DEV {fmt(stats(dev.net, dev.date))} | CHK {fmt(stats(chk.net, chk.date))} | gross dev {dev.gross.mean()*1e4:6.1f} chk {chk.gross.mean()*1e4:6.1f}")
print('variants (timing x thr x horizon):', variants)
pickle.dump(RES, open('res_grid.pkl', 'wb'))
