"""Independent re-implementation: Boyaa residual fade. m = BTC log move from HK close (08:00 UTC prev day) to 01:29 UTC (open 01:30).
beta/std rolling W=250 past-only; fade if |z|>=thr; 20bp RT. <= 2026-08-10."""
import numpy as np, pandas as pd, yfinance as yf
CUT = pd.Timestamp("2026-08-10")
b = pd.read_parquet("/Users/rytty/CCP/BTC-Acum/data/btc_usd_1m_candles_polymarket_arb.parquet", columns=["timestamp", "close"])
b = b[b.timestamp < pd.Timestamp("2026-08-10 09:00", tz="UTC")].set_index("timestamp").close.sort_index()
def px(t):
    i = b.index.searchsorted(t) - 1
    return b.iloc[i] if i >= 0 and t - b.index[i] < pd.Timedelta(minutes=30) else np.nan
x = yf.download("0434.HK", start="2017-08-01", end="2026-08-11", auto_adjust=True, progress=False)
x.columns = x.columns.get_level_values(0); x = x[x.index <= CUT]
dates = list(x.index)
m = [np.nan] + [np.log(px(pd.Timestamp(dates[i]).tz_localize("UTC") + pd.Timedelta(hours=1, minutes=29)) / px(pd.Timestamp(dates[i-1]).tz_localize("UTC") + pd.Timedelta(hours=8))) for i in range(1, len(dates))]
x["m"] = m; x["g"] = np.log(x.Open / x.Close.shift()); x["oc"] = np.log(x.Close / x.Open)
for W in [120, 250]:
    r = x.g.rolling(W, min_periods=60); mm = x.m.rolling(W, min_periods=60)
    beta = ((x.g * x.m).rolling(W, min_periods=60).mean() - r.mean() * mm.mean()) / mm.var(ddof=0)
    res = x.g - beta.shift() * x.m
    z = (res - res.rolling(W, min_periods=60).mean().shift()) / res.rolling(W, min_periods=60).std().shift()
    zr = (x.g - x.g.rolling(W, min_periods=60).mean().shift()) / x.g.rolling(W, min_periods=60).std().shift()
    for thr in [0.5, 1.0]:
        for nm, zz, sg in [("RESID", z, res), ("RAW  ", zr, x.g)]:
            p = (-np.sign(sg) * x.oc - 0.002)[zz.abs() >= thr].dropna()
            out = [f"{lab} n {len(s)} {s.mean()*1e4:+.0f}bp t {s.mean()/s.std()*np.sqrt(len(s)):+.2f}" for lab, s in [("dev", p[p.index < "2023"]), ("chk", p[p.index >= "2023"])]]
            print(f"W{W} z>={thr} {nm} " + " | ".join(out))

print("--- realistic 60bp RT, W120 resid, check period by side/year ---")
W = 120; r = x.g.rolling(W, min_periods=60); mm = x.m.rolling(W, min_periods=60)
beta = ((x.g * x.m).rolling(W, min_periods=60).mean() - r.mean() * mm.mean()) / mm.var(ddof=0)
res = x.g - beta.shift() * x.m
z = (res - res.rolling(W, min_periods=60).mean().shift()) / res.rolling(W, min_periods=60).std().shift()
print("median beta 2023+:", round(beta[beta.index >= "2023"].median(), 2), " pre-2023:", round(beta[beta.index < "2023"].median(), 2))
for thr in [0.5, 1.0]:
    sel = (z.abs() >= thr) & (x.index >= "2023-01-01")
    gross = (-np.sign(res) * x.oc)[sel].dropna()
    for side, s in [("both", gross), ("long-only(down res)", gross[res[sel] < 0]), ("short-only", gross[res[sel] > 0])]:
        s = s - 0.006
        print(f"z>={thr} {side:20s} n {len(s)} {s.mean()*1e4:+.0f}bp t {s.mean()/s.std()*np.sqrt(len(s)):+.2f} win {(s>0).mean():.2f}")
    s = gross - 0.006
    print("   per-year:", {y: f"{g.mean()*1e4:+.0f}({len(g)})" for y, g in s.groupby(s.index.year)})
print("price 2026 median HK$", round(x.Close[x.index >= "2026"].median(), 2), " median HK$ turnover/day (M):", round((x.Close*x.Volume)[x.index >= "2026"].median()/1e6, 1))
