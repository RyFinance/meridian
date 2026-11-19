"""1-year forward Monte Carlo for the live plan: block-bootstrap actual trade P&L (10-day blocks), scaled so the mean
edge is the backtest's, half of it (expected live), or a quarter (pessimistic). ITB alone and 2/3 ITB + 1/3 RKT."""
import numpy as np, pandas as pd
from research.zb_itb.verify.f3_canonical import build
rng = np.random.default_rng(7)
r = build(); t = r[r.d.notna() & (r.d != 0)]; itb = (t.g_off - 0.0004)
k = build("RKT"); k = k[k.d.notna() & (k.d != 0)]; rkt = (k.g_off.where(k.entry_off.notna(), k.g_h1) - 0.001).reindex(itb.index).fillna(0)
mix = (2 * itb + rkt) / 3
def sim(x, keep, n=252, B=10, N=20000):
    x = x.values; mu = x.mean(); y = x - mu * (1 - keep)           # shrink the edge, keep the noise
    out = np.empty((N, 2))
    for i in range(N):
        idx = np.concatenate([np.arange(s, s + B) % len(y) for s in rng.integers(0, len(y), n // B + 1)])[:n]
        eq = np.exp(np.cumsum(y[idx])); out[i] = (eq[-1] - 1, (eq / np.maximum.accumulate(eq) - 1).min())
    return out
print("1-year outcomes from $10,000 (20k simulated years):")
for lab, x in [("ITB", itb), ("2/3 ITB + 1/3 RKT", mix)]:
    for keep, kl in [(1, "backtest edge"), (0.5, "half edge (expected)"), (0.25, "quarter edge"), (0, "NO edge")]:
        o = sim(x, keep); ret, dd = o[:, 0], o[:, 1]
        print(f"  {lab:18s} {kl:22s} median {np.median(ret)*100:+5.0f}% | 5th..95th {np.quantile(ret,.05)*100:+4.0f}%..{np.quantile(ret,.95)*100:+4.0f}% | P(loss) {np.mean(ret<0)*100:4.1f}% | median maxDD {np.median(dd)*100:.0f}% | P(maxDD>20%) {np.mean(dd<-.2)*100:.0f}%")
