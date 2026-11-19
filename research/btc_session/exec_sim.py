"""EXEC_PREREG.md: simulate the 17:00->18:00 ET after-hours ETF trade on real 1-minute prints."""
import sys, numpy as np, pandas as pd
from pathlib import Path
from research.forward import nyse
H = Path(__file__).parent
COMM = 0.0035
def bars(f):
    m = pd.read_parquet(H / f)
    m = m.set_index(pd.to_datetime(m.ts).dt.tz_localize("UTC").dt.tz_convert("America/New_York").dt.tz_localize(None)).sort_index()
    return m[~m.index.duplicated()]
def sim(m, notional=10_000):
    rows = []
    for d in sorted(set(m.index.normalize())):
        if d.weekday() > 4 or not nyse.is_session(d.date()): continue
        def w(a, b): return m[(m.index >= d + pd.Timedelta(a)) & (m.index <= d + pd.Timedelta(b))]
        pre_in = w("16:30:00", "16:59:00"); pre_out = w("17:30:00", "17:59:00")
        if pre_in.empty or pre_out.empty: continue
        win_in = w("17:00:00", "17:04:00"); b_in5 = w("17:05:00", "17:09:00")
        ref = pre_in.close.iloc[-1]; lim = ref - 0.01
        if len(win_in) and win_in.low.min() <= lim: buy, how_in = lim, "limit"
        elif len(b_in5): buy, how_in = b_in5.high.iloc[0] + 0.01, "chase"
        else: continue
        win_out = w("18:00:00", "18:04:00"); b_out5 = w("18:05:00", "18:15:00")
        ref2 = pre_out.close.iloc[-1]; lim2 = ref2 + 0.01
        if len(win_out) and win_out.high.max() >= lim2: sell, how_out = lim2, "limit"
        elif len(b_out5): sell, how_out = b_out5.low.iloc[0] - 0.01, "chase"
        else: continue
        sh = int(notional // buy)
        net = ((sell - buy) * sh - 2 * COMM * sh) / (buy * sh)
        # market variant
        b0 = w("17:00:00", "17:00:00"); s0 = w("18:00:00", "18:00:00")
        mk = ((s0.low.iloc[0] - 0.01) / (b0.high.iloc[0] + 0.01) - 1 - 2 * COMM / buy) if len(b0) and len(s0) else np.nan
        mid = np.log(ref2 / ref)
        rows.append(dict(d=d, buy=buy, sell=sell, net=net, market=mk, ref_ret=mid, how_in=how_in, how_out=how_out))
    return pd.DataFrame(rows).set_index("d")
if __name__ == "__main__":
    for f in sys.argv[1:]:
        t = sim(bars(f)); t.to_csv(H / f.replace(".parquet", "_exec.csv"))
        x = t.net
        print(f"{f}: n={len(t)} limit-rule net {x.mean()*1e4:+.2f}bp/trade t={x.mean()/x.std()*np.sqrt(len(x)):+.2f} win={(x>0).mean():.2f} total {x.sum()*100:+.2f}% "
              f"| market-orders net {t.market.mean()*1e4:+.2f}bp | price move (16:59->17:59 prints) {t.ref_ret.mean()*1e4:+.2f}bp | implied cost {(t.ref_ret-x).mean()*1e4:+.2f}bp")
        print("   entry fills:", t.how_in.value_counts().to_dict(), " exit fills:", t.how_out.value_counts().to_dict())
        print("   by month net bp:", (t.net.groupby(t.index.to_period("M")).mean()*1e4).round(1).to_dict())
