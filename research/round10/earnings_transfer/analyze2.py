exec(open('analyze.py').read().split("RES = {}")[0])
import warnings; warnings.filterwarnings('ignore')
def split(r): return r[r.date < cut], r[r.date >= cut]
def show(name, r, col='net'):
    a, b = split(r); print(f"{name:46s} DEV {fmt(stats(a[col], a.date))} | CHK {fmt(stats(b[col], b.date))}")
# ---- sanity: timing of earnings & signal
sA = ev_df.sigA; sB = ev_df.sigB
print('corr(reporter pm abn, reporter gap abn) =', round(sA.corr(sB), 3), ' n', sA.notna().sum())
# reporter |pm| on event day vs its typical non-event day
ev_abs, base_abs = [], []
for r in set(sum(ev_df.reps, [])):
    x = (T[r].pmr - spy.pmr)[(T[r].index >= START) & (T[r].index <= END)]
    ed_ = set(bmo[bmo.t == r].date)
    ev_abs += list(x[x.index.isin(ed_)].abs().dropna()); base_abs += list(x[~x.index.isin(ed_)].abs().dropna())
print(f'reporter mean |pm abn| event days {np.mean(ev_abs)*100:.2f}%  vs other days {np.mean(base_abs)*100:.2f}%  (n {len(ev_abs)})')
# how much of the reporter's gap is already in peers' premarket?
print('median |sigA|', round(sA.abs().median()*100,2), '%  mean peer pm abn x sign(sig) (bp):', round((ev_df.peerpm*np.sign(sA)).mean()*1e4,1),
      ' peer open-gap abn x sign:', 'see below')
# ---- primary + flip + SPY placebo + random non-peer + non-event day
PRIM = ('A', .01, 'day')
def spy_pl(tim, hz, thr):
    out = []
    for i, ev in ev_df.iterrows():
        s = ev['sig' + tim]
        if pd.isna(s) or abs(s) < thr: out.append((np.nan, np.nan, ev.date)); continue
        g = trade('SPY', ev.date, tim, hz, np.sign(s)); out.append((g, g - 0.0004, ev.date))
    return pd.DataFrame(out, columns=['gross', 'net', 'date'])
def rand_nonpeer(tim, hz, thr, draws=40):
    out = []
    for i, ev in ev_df.iterrows():
        s = ev['sig' + tim]
        if pd.isna(s) or abs(s) < thr: out.append((np.nan, np.nan, ev.date)); continue
        pool = [t for t in ALL if t in T and t not in CLUSTERS[ev.cluster] and not has_earn(t, ev.date) and t not in ev.peers]
        res = []
        for _ in range(draws):
            pick = list(rng.choice(pool, size=min(len(ev.peers), len(pool)), replace=False))
            res.append(basket(pick, ev.date, tim, hz, np.sign(s)))
        res = np.array(res, float); out.append((np.nanmean(res[:, 0]), np.nanmean(res[:, 1]), ev.date))
    return pd.DataFrame(out, columns=['gross', 'net', 'date'])
# non-event days: same reporters, same cluster, random non-earnings days with |sig|>=thr; peers traded in sign direction
def nonevent(tim, hz, thr, K=15):
    out = []
    cl_ev = {c: set(g.date) for c, g in ev_df.groupby('cluster')}
    for i, ev in ev_df.iterrows():
        s0 = ev['sig' + tim]
        if pd.isna(s0) or abs(s0) < thr: out.append((np.nan, np.nan, ev.date)); continue
        mem = CLUSTERS[ev.cluster]
        cand = [d for d in cal if START <= d <= END and not any(has_earn(m, d, -2, 6) for m in mem)]
        sg = []
        for d in cand:
            s = sig_of(ev.reps, d, tim)
            if pd.notna(s) and abs(s) >= thr: sg.append((d, s))
        if not sg: out.append((np.nan, np.nan, ev.date)); continue
        idx = rng.choice(len(sg), size=min(K, len(sg)), replace=False); res = []
        for j in idx:
            d, s = sg[j]; res.append(basket(ev.peers, d, tim, hz, np.sign(s)))
        res = np.array(res, float); out.append((np.nanmean(res[:, 0]), np.nanmean(res[:, 1]), ev.date))
    return pd.DataFrame(out, columns=['gross', 'net', 'date'])
for key in [('A', .01, 'day'), ('A', 0, 'h1'), ('A', .01, 'd1'), ('A', .02, 'day'), ('B', .01, 'day')]:
    tim, thr, hz = key
    print(f"\n##### {key}")
    r = run(tim, hz, thr); show('peers, signal direction (net)', r)
    show('peers, signal direction (GROSS)', r, 'gross')
    fl = r.copy(); fl['net'] = -r.gross - (r.gross - r.net); show('FLIP (opposite dir, net)', fl)
    show('SPY placebo same signal (net 4bp)', spy_pl(tim, hz, thr))
    show('random NON-peer basket same day (net)', rand_nonpeer(tim, hz, thr))
    show('random NON-peer basket same day (GROSS)', rand_nonpeer(tim, hz, thr), 'gross')
    show('same peers on NON-event days (net)', nonevent(tim, hz, thr))
    show('same peers on NON-event days (GROSS)', nonevent(tim, hz, thr), 'gross')
    rh = run(tim, hz, thr, hedge=True); show('peers SPY-hedged (net incl SPY leg cost)', rh)
