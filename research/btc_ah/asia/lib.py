import numpy as np, pandas as pd
C = "/Users/rytty/CCP/quant_v7/research/btc_ah/asia/cache"
CUT = pd.Timestamp("2026-08-10 23:59:59")
RT = 0.0020
TK = {"3350_T": ("JP", "2024-04-01"), "3825_T": ("JP", "2024-01-01"),
      "8698_T": ("JP", "2017-08-11"), "8473_T": ("JP", "2017-08-11"), "9449_T": ("JP", "2017-08-11"),
      "0434_HK": ("HK", "2017-08-11"), "1723_HK": ("HK", "2017-08-11")}
b = pd.read_parquet("/Users/rytty/CCP/BTC-Acum/data/btc_usd_1m_candles_polymarket_arb.parquet", columns=["timestamp", "close"])
t = b["timestamp"].dt.tz_convert("UTC").dt.tz_localize(None)
keep = (t <= CUT).to_numpy()
btc = pd.Series(b["close"].to_numpy()[keep], index=pd.DatetimeIndex(t[keep])).sort_index()
btc = btc[~btc.index.duplicated(keep="last")]
del b, t
def px(x):
    return np.asarray(btc.asof(pd.DatetimeIndex(x) - pd.Timedelta(minutes=2)), dtype=float)
def build(s):
    reg, era = TK[s]
    d = pd.read_parquet(f"{C}/{s}_1d.parquet"); d.index = pd.DatetimeIndex(d.index)
    if d.index.tz is not None: d.index = d.index.tz_localize(None)
    d = d[d.index <= CUT]
    f = d["Adj Close"] / d["Close"]
    o = pd.DataFrame({"O": d["Open"] * f, "H": d["High"] * f, "L": d["Low"] * f, "C": d["Adj Close"],
                      "rC": d["Close"], "rH": d["High"], "rL": d["Low"]}).dropna(subset=["O", "C"])
    dates = o.index
    Pd = pd.DatetimeIndex(np.r_[np.array(["NaT"], dtype="datetime64[ns]"), dates.values[:-1]])
    if reg == "JP":
        ct = Pd + pd.to_timedelta(np.where(Pd >= pd.Timestamp("2024-11-05"), 6.5 * 3600, 6.0 * 3600), unit="s"); ot = dates
    else:
        ct = Pd + pd.Timedelta(hours=8); ot = dates + pd.Timedelta(minutes=90)
    o["m"] = np.log(px(ot) / px(ct))
    o["g"] = np.log(o["O"] / o["C"].shift(1))
    o["clean"] = (o["rH"] > o["rL"]) & (o["O"] <= o["H"] * (1 + 1e-6)) & (o["O"] >= o["L"] * (1 - 1e-6))
    o["ret"] = o["C"] / o["C"].shift(1) - 1
    o["era"] = pd.Timestamp(era)
    o["cut"] = pd.Timestamp(era) + 0.6 * (dates.max() - pd.Timestamp(era))
    return o
def stats(net):
    n = len(net)
    if n < 2: return (n, np.nan, np.nan, np.nan)
    mu, sd = net.mean(), net.std(ddof=1)
    return (n, round(mu * 1e4, 1), round(mu / sd * np.sqrt(n), 2), round((net > 0).mean(), 3))
