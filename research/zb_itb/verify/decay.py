"""Is the edge decaying? Rolling gap beta (how much of the overnight ZB move ITB's open already prices) vs rolling first-hour edge."""
import numpy as np, pandas as pd
from research.zb_itb.verify.f3_canonical import build
r = build(); t = r[r.d.notna() & (r.d != 0)].copy()
t["gap_off"] = t.gap; t["net"] = t.g_off - 0.0004; t["fh"] = np.log(t.exit / t.entry_off)
for a, b in [("2024-05", "2024-12"), ("2025-01", "2025-06"), ("2025-07", "2025-12"), ("2026-01", "2026-06"), ("2026-07", "2026-10")]:
    g = t[(t.index >= a) & (t.index < (pd.Period(b, "M") + 1).start_time)]
    beta_gap = np.polyfit(g.m, g.gap_off, 1)[0]; beta_fh = np.polyfit(g.m, g.fh, 1)[0]
    print(f"{a}..{b}: n {len(g):3d} | open-gap beta to ZB move {beta_gap:+.2f} | first-hour beta to ZB move {beta_fh:+.2f} | net {g.net.mean()*1e4:+.1f}bp t {g.net.mean()/g.net.std()*np.sqrt(len(g)):+.2f}")
w = t.net.rolling(120).mean() * 1e4
print("rolling-120-trade mean net (bp): min %.1f, last %.1f, quartiles %s" % (w.min(), w.iloc[-1], np.round(w.quantile([.25, .5, .75]).values, 1)))
print("worst 5 days (net bp):", (t.net.nsmallest(5) * 1e4).round(0).to_dict())
