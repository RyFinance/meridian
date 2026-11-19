exec(open('analyze.py').read().split("RES = {}")[0])
import warnings; warnings.filterwarnings('ignore')
def split(r): return r[r.date < cut], r[r.date >= cut]
# dose-response, timing A, signed gross return of peer basket in units of per-1%-reporter-move
for hz in ('h1', 'day', 'd1'):
    r = run('A', hz, 0).join(ev_df[['cluster', 'peerpm']]).dropna(subset=['gross', 'peerpm'])
    r['s'] = r.sig * 100; r['y'] = r.gross * 1e4 * np.sign(r.sig)  # y: gross in bp signed; use y_raw = signed by sign -> regress raw (unsigned) peer ret on sig
    r['raw'] = r.gross * np.sign(r.sig) * 1e4   # = peer return in raw (unsigned) terms
    r['pp'] = r.peerpm * 100
    for nm, rr in (('ALL', r), ('DEV', r[r.date < cut]), ('CHK', r[r.date >= cut])):
        X = np.c_[np.ones(len(rr)), rr.s, rr.pp]; b = np.linalg.lstsq(X, rr.raw, rcond=None)[0]
        res = rr.raw - X @ b; g = rr.date.values
        XtXi = np.linalg.inv(X.T @ X); meat = sum(np.outer(X[g == u].T @ res[g == u], X[g == u].T @ res[g == u]) for u in np.unique(g))
        V = XtXi @ meat @ XtXi; se = np.sqrt(np.diag(V))
        print(f'{hz:3s} {nm} n={len(rr)} slope on reporter sig (bp per 1% reporter move) {b[1]:6.2f} (t {b[1]/se[1]:5.2f}) | on peer own pm {b[2]:6.2f} (t {b[2]/se[2]:5.2f})')
# terciles of |sig| (cutpoints from DEV)
r = run('A', 'day', 0); q = r.sig.abs()[r.date < cut].quantile([1/3, 2/3]).values
for lab, m in (('small', r.sig.abs() < q[0]), ('mid', (r.sig.abs() >= q[0]) & (r.sig.abs() < q[1])), ('big', r.sig.abs() >= q[1])):
    a, b = split(r[m]); print(f'|sig| {lab:5s} (cuts {q[0]*100:.1f}/{q[1]*100:.1f}%) day gross DEV {fmt(stats(a.gross,a.date))} | CHK {fmt(stats(b.gross,b.date))}')
# per cluster, A thr=.01 day, gross + net, all sample
r = run('A', 'day', .01).join(ev_df[['cluster']]).dropna(subset=['gross'])
print('\nper-cluster A thr1% day (dev+check pooled):')
for c, g in r.groupby('cluster'):
    if len(g) >= 8: print(f'  {c:18s} n={len(g):3d} gross {g.gross.mean()*1e4:6.1f} net {g.net.mean()*1e4:6.1f} win {np.mean(g.net>0):.2f}')
# ITB correlation: date-level P&L of primary rule vs ITB rule
itb = pd.read_csv('../../zb_itb/verify/f3_trades_canonical.csv', parse_dates=['date']).set_index('date')
itbnet = (itb.g_off - 0.0004).dropna()
for key in (('A', .01, 'day'), ('A', 0, 'h1')):
    r = run(*[key[0], key[2], key[1]]).dropna(subset=['net']) if False else run(key[0], key[2], key[1]).dropna(subset=['net'])
    dl = r.groupby('date').net.mean()
    j = pd.concat([dl, itbnet], axis=1, join='inner').dropna()
    full = pd.concat([dl, itbnet], axis=1).fillna(0)
    print(f'ITB corr {key}: overlap days {len(j)} corr {j.corr().iloc[0,1]:.3f} ; zero-filled full-calendar corr {full.corr().iloc[0,1]:.3f}')
