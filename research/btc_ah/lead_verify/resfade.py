"""Independent check of the residual-gap fade (lead). Data <= 2026-08-10 only.
btc_off = ln(BTC last 1m close before 09:25 ET / last close before 16:00 ET prev session).
gap = ln(open_t / close_{t-1}); beta = rolling 250-session OLS of gap on btc_off using PAST days only (shifted).
res = gap - beta*btc_off. Trade: -sign(res) * ln(close/open) when |res| > thr, minus cost per side (MOO/MOC)."""
import sys, numpy as np, pandas as pd
CUT = pd.Timestamp("2026-08-10")
T = "/Users/rytty/CCP/quant_v7/research/btc_ah/tickers/"
b = pd.read_parquet("/Users/rytty/CCP/BTC-Acum/data/btc_usd_1m_candles_polymarket_arb.parquet", columns=["timestamp", "close"])
b["ts"] = b.timestamp.dt.tz_convert("America/New_York").dt.tz_localize(None)
b = b[b.ts < CUT + pd.Timedelta(days=1)].set_index("ts").close.sort_index()
def px_before(ts):  # last close strictly before ts
    i = b.index.searchsorted(ts) - 1
    return b.iloc[i] if i >= 0 and (ts - b.index[i]) < pd.Timedelta(minutes=30) else np.nan
def load(t):
    d = pd.read_parquet(T + f"{t}_1d.parquet"); d = d[d.index <= CUT].copy()
    f = d["adj close"] / d["close"]
    for c in ["open", "close"]: d[c] = d[c] * f
    d["dvol"] = d["close"] * d["volume"] / f
    return d
cache = {}
def btc_off(dates):
    out = []
    for i, dt in enumerate(dates):
        if i == 0: out.append(np.nan); continue
        k = (dates[i-1], dt)
        if k not in cache: cache[k] = np.log(px_before(dt + pd.Timedelta(hours=9, minutes=25)) / px_before(dates[i-1] + pd.Timedelta(hours=16)))
        out.append(cache[k])
    return np.array(out)
def run(t, thr=0.0, cost=0.0010, mindv=5e6, start="2022-07-01"):
    d = load(t); d["btc"] = btc_off(list(d.index)); d["gap"] = np.log(d.open / d.close.shift())
    d["oc"] = np.log(d.close / d.open)
    cov = (d.gap * d.btc).rolling(250, min_periods=120).mean() - d.gap.rolling(250, min_periods=120).mean() * d.btc.rolling(250, min_periods=120).mean()
    d["beta"] = (cov / d.btc.rolling(250, min_periods=120).var(ddof=0)).shift()
    d["res"] = d.gap - d.beta * d.btc
    d["dv"] = d.dvol.rolling(20).median().shift()
    x = d[(d.index >= start) & d.res.notna() & d.btc.notna() & (d.res.abs() > thr) & (d.dv > mindv)]
    pnl = -np.sign(x.res) * x.oc - 2 * cost
    raw = -np.sign(x.gap) * x.oc - 2 * cost  # raw gap fade (no BTC)
    return x, pnl, raw
def st(p): return f"n {len(p):4d} mean {p.mean()*1e4:+6.1f}bp t {p.mean()/p.std()*np.sqrt(len(p)):+5.2f} win {(p>0).mean():.2f}"
if __name__ == "__main__":
    names = ["MARA", "RIOT", "CLSK", "HUT", "CIFR", "WULF", "IREN", "BTBT", "COIN", "MSTR", "HOOD"]
    allp = []
    for t in names:
        x, p, r = run(t)
        if len(p) < 50: continue
        allp.append(p.rename(t))
        print(f"{t:5s} beta~{x.beta.median():.2f} RES {st(p)} | RAW {st(r)} | 2026 {p[p.index>='2026'].mean()*1e4:+.0f}bp")
    P = pd.concat(allp, axis=1); basket = P.mean(axis=1)
    print("BASKET (eq-wt across names, per day):", st(basket))
    for y, g in basket.groupby(basket.index.year): print(y, st(g))
