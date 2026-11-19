import numpy as np, pandas as pd
C = "/Users/rytty/CCP/quant_v7/research/btc_ah/asia/cache"
OUT = "/Users/rytty/CCP/quant_v7/research/btc_ah/asia"
CUT = pd.Timestamp("2026-08-10 23:59:59")   # sealed holdout: nothing after 2026-08-10
RT = 0.0020                                  # 10 bp per side
# name: (region, BTC-era start). Metaplanet 2024-04 per brief; Remixpoint start unverified (proxy 2024-01).
TK = {"3350_T": ("JP", "2024-04-01"), "3825_T": ("JP", "2024-01-01"),
      "8698_T": ("JP", "2017-08-11"), "8473_T": ("JP", "2017-08-11"), "9449_T": ("JP", "2017-08-11"),
      "0434_HK": ("HK", "2017-08-11"), "1723_HK": ("HK", "2017-08-11")}
MIN2 = pd.Timedelta(minutes=2)

# ---- BTC 1m: load and filter immediately
b = pd.read_parquet("/Users/rytty/CCP/BTC-Acum/data/btc_usd_1m_candles_polymarket_arb.parquet", columns=["timestamp", "close"])
t = b["timestamp"].dt.tz_convert("UTC").dt.tz_localize(None)
keep = (t <= CUT).to_numpy()
btc = pd.Series(b["close"].to_numpy()[keep], index=pd.DatetimeIndex(t[keep])).sort_index()
btc = btc[~btc.index.duplicated(keep="last")]
del b, t
print("BTC rows after filter", len(btc), "last bar", btc.index.max())

def px(x):
    """Last BTC close known strictly before x: minute bar starting at x-2min closes at x-1min."""
    return np.asarray(btc.asof(pd.DatetimeIndex(x) - MIN2), dtype=float)

def load_daily(s):
    d = pd.read_parquet(f"{C}/{s}_1d.parquet")
    d.index = pd.DatetimeIndex(d.index)
    if d.index.tz is not None:
        d.index = d.index.tz_localize(None)
    d = d[d.index <= CUT]
    f = d["Adj Close"] / d["Close"]
    o = pd.DataFrame({"O": d["Open"] * f, "H": d["High"] * f, "L": d["Low"] * f, "C": d["Adj Close"],
                      "rC": d["Close"], "rH": d["High"], "rL": d["Low"]}).dropna(subset=["O", "C"])
    return o

def build_daily(s):
    reg, era = TK[s]
    o = load_daily(s)
    dates = o.index
    Pd = pd.DatetimeIndex(np.r_[np.array(["NaT"], dtype="datetime64[ns]"), dates.values[:-1]])
    if reg == "JP":
        add = np.where(Pd >= pd.Timestamp("2024-11-05"), 6.5 * 3600, 6.0 * 3600)  # close 15:30 JST (06:30 UTC) since Nov 2024; 15:00 before
        ct = Pd + pd.to_timedelta(add, unit="s")
        ot = dates                       # 09:00 JST = 00:00 UTC
    else:
        ct = Pd + pd.Timedelta(hours=8)  # 16:00 HKT = 08:00 UTC
        ot = dates + pd.Timedelta(minutes=90)  # 09:30 HKT = 01:30 UTC
    o["m"] = np.log(px(ot) / px(ct))     # BTC move prior close -> just before open
    o["prevC"] = o["C"].shift(1)
    o["g"] = np.log(o["O"] / o["prevC"]) # open gap (adjusted)
    o["ret"] = o["C"] / o["C"].shift(1) - 1
    o["era"] = pd.Timestamp(era)
    return o

def daily_variants(s, o):
    out = []
    g, m = o["g"], o["m"]
    O, Cc = o["O"], o["C"]
    gross = lambda d: d * (Cc / O - 1)
    # Rule family A: open->close in BTC direction, filtered by |BTC move|
    for thr in [0.0, 0.01, 0.02]:
        d = np.sign(m) * (m.abs() >= thr) * m.notna()
        out.append(("btc_dir", f"|m|>={thr}", d))
    # Families B/C: residual gap follow / fade, rolling past-only beta
    for W in [60, 120, 250]:
        mp = max(20, W // 2)
        beta = (g.rolling(W, min_periods=mp).cov(m) / m.rolling(W, min_periods=mp).var()).shift(1)
        resid = g - beta * m
        rstd = resid.shift(1).rolling(W, min_periods=mp).std()
        z = resid / rstd
        for thr in [0.0, 0.5, 1.0]:
            ok = (z.abs() >= thr) & resid.notna() & (resid != 0)
            d = np.sign(resid) * ok
            out.append(("resid_follow", f"W={W},|z|>={thr}", d))
            out.append(("resid_fade", f"W={W},|z|>={thr}", -d))
    # Family D: limit days (close==high & ret>+10%, or close==low & ret<-10%); trade next day open->close
    up = (o["ret"] > 0.10) & ((o["rC"] - o["rH"]).abs() <= 1e-6 * o["rH"])
    dn = (o["ret"] < -0.10) & ((o["rC"] - o["rL"]).abs() <= 1e-6 * o["rL"])
    flag = (up | dn).shift(1).fillna(False).astype(bool)
    sgn_prev = np.sign(o["ret"]).shift(1).fillna(0)
    out.append(("limit_cont", "next-day, dir=limit dir", sgn_prev * flag))
    out.append(("limit_fade", "next-day, dir=-limit dir", -sgn_prev * flag))
    print(s, "limit-up days", int(up.sum()), "limit-down days", int(dn.sum()))
    res = []
    for fam, par, d in out:
        d = pd.Series(np.asarray(d, dtype=float), index=o.index).fillna(0)
        mask = d != 0
        tr = pd.DataFrame({"date": o.index[mask.values], "gross": (d * (Cc / O - 1))[mask].values})
        res.append((s, fam, par, tr))
    return res

def intraday_variants(s):
    reg, era = TK[s]
    h = pd.read_parquet(f"{C}/{s}_60m.parquet")
    h.index = pd.DatetimeIndex(h.index)
    if h.index.tz is not None:
        h.index = h.index.tz_localize(None)
    h = h[h.index <= CUT].sort_index()
    h = h.dropna(subset=["Open", "Close"])
    lunch = ["03:00"] if reg == "JP" else ["03:30", "04:30"]   # bars straddling the lunch break
    h = h[~h.index.strftime("%H:%M").isin(lunch)]
    h = h[h.index >= pd.Timestamp(era)]
    t = h.index
    bm = pd.Series(np.log(px(t) / px(t - pd.Timedelta(minutes=60))), index=t)   # BTC over [t-60m, t)
    r = h["Close"] / h["Open"] - 1
    ok_split = r.abs() < 0.4
    res = []
    for thr in [0.0, 0.0025, 0.005]:
        sel = (bm.abs() >= thr) & bm.notna() & ok_split
        for fam, sg in [("intra_follow", 1), ("intra_fade", -1)]:
            d = sg * np.sign(bm) * sel
            mask = d != 0
            tr = pd.DataFrame({"date": t[mask.values].normalize(), "gross": (d * r)[mask].values})
            res.append((s, fam, f"|BTC 1h|>={thr}", tr))
    corr = np.corrcoef(bm[ok_split & bm.notna()], r[ok_split & bm.notna()])[0, 1]
    print(s, "intraday bars", int((ok_split & bm.notna()).sum()), "corr(BTC prior hr, stock next hr)", round(corr, 4))
    return res

def met(x):
    n = len(x)
    if n < 2:
        return dict(n=n, mean=np.nan, t=np.nan, win=np.nan, aw=np.nan, al=np.nan)
    mu, sd = x.mean(), x.std(ddof=1)
    return dict(n=n, mean=mu * 1e4, t=mu / sd * np.sqrt(n) if sd > 0 else np.nan,
                win=(x > 0).mean(), aw=x[x > 0].mean() * 1e4 if (x > 0).any() else np.nan,
                al=x[x <= 0].mean() * 1e4 if (x <= 0).any() else np.nan)

# ---- build everything
all_var = []
cut_of = {}
for s in TK:
    o = build_daily(s)
    era = pd.Timestamp(TK[s][1])
    end = o.index.max()
    cut = era + 0.6 * (end - era)
    cut_of[s] = cut
    # gap-beta summary (era only, W=120 full-era rolling beta averaged)
    oe = o[(o.index >= era) & o["m"].notna() & o["g"].notna()]
    if len(oe) > 30:
        cc = np.corrcoef(oe["g"], oe["m"])[0, 1]
        print(s, "era", str(era.date()), "->", str(end.date()), "dev/check cut", str(cut.date()),
              "gap~BTC corr", round(cc, 3), "slope(full era)", round(np.polyfit(oe["m"], oe["g"], 1)[0], 3))
    all_var += daily_variants(s, o)
    all_var += intraday_variants(s)

recs = []
trade_store = []
for s, fam, par, tr in all_var:
    era = pd.Timestamp(TK[s][1])
    cut = cut_of[s]
    tr = tr[tr["date"] >= era].copy()
    tr["ticker"] = s; tr["fam"] = fam; tr["par"] = par
    trade_store.append(tr)
trades = pd.concat(trade_store, ignore_index=True)
trades["net"] = trades["gross"] - RT
trades["flip_net"] = -trades["gross"] - RT
trades["cut"] = trades["ticker"].map(lambda s: cut_of[s])
trades["split"] = np.where(trades["date"] < trades["cut"], "dev", "check")
trades.to_parquet(f"{OUT}/trades_all.parquet")

rows = []
for (s, fam, par), g in trades.groupby(["ticker", "fam", "par"]):
    dv = g[g.split == "dev"]; ck = g[g.split == "check"]
    md, mc = met(dv["net"]), met(ck["net"])
    fd = dv["flip_net"].mean() * 1e4 if len(dv) else np.nan
    fc = ck["flip_net"].mean() * 1e4 if len(ck) else np.nan
    yr = g.groupby(g["date"].dt.year)["net"].agg(["mean", "size"])
    yr = yr[yr["size"] >= 5]
    ystr = " ".join(f"{int(y)}:{v*1e4:+.0f}({int(k)})" for y, (v, k) in yr.iterrows()) if len(yr) else ""
    rows.append(dict(ticker=s, fam=fam, par=par, dev_n=md["n"], dev_bp=md["mean"], dev_t=md["t"], dev_win=md["win"],
                     chk_n=mc["n"], chk_bp=mc["mean"], chk_t=mc["t"], chk_win=mc["win"],
                     flip_dev_bp=fd, flip_chk_bp=fc, avg_win_bp=md["aw"], avg_loss_bp=md["al"], years=ystr))
R = pd.DataFrame(rows)
R.to_csv(f"{OUT}/variants.csv", index=False)
print("TOTAL ticker-variant combos:", len(R), " distinct rule (fam,par):", R[["fam", "par"]].drop_duplicates().shape[0])
pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 60)
cols = ["ticker", "fam", "par", "dev_n", "dev_bp", "dev_t", "chk_n", "chk_bp", "chk_t", "flip_dev_bp", "flip_chk_bp"]
print(R[R.dev_n >= 30].sort_values("dev_t", ascending=False).head(12)[cols].round(2).to_string(index=False))
