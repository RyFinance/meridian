# BTC 16:00->09:25 ET move vs open gap / open->close / open->first-hour, for BTC-linked tickers.
# Sealed holdout: every series is filtered to <= 2026-08-10 right after loading.
import numpy as np, pandas as pd, glob, os, sys
from datetime import time

D = "/Users/rytty/CCP/quant_v7/research/btc_ah/tickers"
CUT = pd.Timestamp("2026-08-10")
DEV_CUT = pd.Timestamp("2022-06-30")
COST_SIDE_NORMAL = 0.0003   # 3 bp per side
COST_SIDE_LOW = 0.0010      # 10 bp per side for names under $5 (raw open)

# ---------- BTC 1m ----------
btc = pd.read_parquet("/Users/rytty/CCP/BTC-Acum/data/btc_usd_1m_candles_polymarket_arb.parquet",
                      columns=["timestamp", "close"])
btc["ts"] = btc["timestamp"].dt.tz_convert("America/New_York").dt.tz_localize(None)
btc = btc[btc["ts"] < CUT + pd.Timedelta(days=1)].sort_values("ts").reset_index(drop=True)
TS = btc["ts"].values
CL = btc["close"].values.astype(float)


def last_px_before(targets):
    """Close of the last 1m bar that opened strictly before target (known at target). NaN if stale > 15 min."""
    t = np.asarray(targets, dtype="datetime64[ns]")
    idx = np.searchsorted(TS, t, side="left") - 1
    px = np.full(len(t), np.nan)
    ok = idx >= 0
    bar = np.where(ok, TS[np.clip(idx, 0, None)], np.datetime64("NaT"))
    fresh = ok & ((t - bar) <= np.timedelta64(15, "m"))
    px[fresh] = CL[idx[fresh]]
    return px


# ---------- master US trading calendar (MSTR daily, full history) ----------
cal = pd.read_parquet(f"{D}/MSTR_1d.parquet").index
cal = pd.DatetimeIndex(cal[(cal <= CUT) & (cal >= pd.Timestamp("2017-08-17"))])
p16 = last_px_before(cal + pd.Timedelta(hours=16))       # 16:00 ET on each day
p0925 = last_px_before(cal + pd.Timedelta(hours=9, minutes=25))
Bcal = np.full(len(cal), np.nan)
Bcal[1:] = np.log(p0925[1:] / p16[:-1])                  # 16:00 prev day -> 09:25 today
Bser = pd.Series(Bcal, index=cal)
print("BTC move obs:", np.isfinite(Bcal).sum(), "from", cal[1].date(), "to", cal[-1].date(), flush=True)

ERA = os.environ.get("ERA") == "1"   # sensitivity: drop pre-2020-08-11 rows (pre-BTC-pivot history)
SUF = "_era" if ERA else ""
TICKERS = ["MARA", "RIOT", "CLSK", "HUT", "CIFR", "WULF", "IREN", "COIN", "HOOD", "BTBT",
           "IBIT", "BITO", "BITX", "MSTU", "MSTX", "MSTR"]  # MSTR = benchmark (not in variant count)
COUNT_TICKERS = [t for t in TICKERS if t != "MSTR"]


def load_daily(t):
    x = pd.read_parquet(f"{D}/{t}_1d.parquet")
    x = x[(x.index <= CUT)].sort_index()
    f = x["adj close"] / x["close"]
    return pd.DataFrame({"rawO": x["open"], "O": x["open"] * f, "C": x["adj close"]}, index=x.index)


def daily_features(t):
    x = load_daily(t)
    pos = cal.get_indexer(x.index)
    rows = []
    for d, p in zip(x.index, pos):
        if p < 1 or not np.isfinite(Bcal[p]):
            continue
        prev = cal[p - 1]
        if prev not in x.index:
            continue
        rows.append((d, Bcal[p], np.log(x.loc[d, "O"] / x.loc[prev, "C"]),
                     np.log(x.loc[d, "C"] / x.loc[d, "O"]), x.loc[d, "C"] / x.loc[d, "O"] - 1,
                     x.loc[d, "rawO"]))
    df = pd.DataFrame(rows, columns=["date", "B", "g", "oc_log", "oc", "rawO"]).set_index("date")
    df = df.replace([np.inf, -np.inf], np.nan).dropna()
    return df


def ols(y, X):
    X = np.column_stack([np.ones(len(y))] + X)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    dof = max(len(y) - X.shape[1], 1)
    s2 = resid @ resid / dof
    cov = s2 * np.linalg.pinv(X.T @ X)
    se = np.sqrt(np.diag(cov))
    return beta, beta / se


def tstat(x):
    x = np.asarray(x, float)
    n = len(x)
    if n < 3 or x.std(ddof=1) == 0:
        return np.nan
    return x.mean() / (x.std(ddof=1) / np.sqrt(n))


def summarize(net):
    net = np.asarray(net, float)
    n = len(net)
    if n == 0:
        return dict(n=0)
    w = net[net > 0]
    l = net[net <= 0]
    return dict(n=n, win=(net > 0).mean(), mean_bp=net.mean() * 1e4, t=tstat(net),
                avgwin_bp=w.mean() * 1e4 if len(w) else np.nan,
                avgloss_bp=l.mean() * 1e4 if len(l) else np.nan)


RULE_SIGN = {
    "BTC_follow": lambda B, e: np.sign(B),
    "BTC_fade": lambda B, e: -np.sign(B),
    "Res_follow": lambda B, e: np.sign(e),
    "Res_fade": lambda B, e: -np.sign(e),
}


def run_ticker(t, exit_kind, feat, dev_mask, chk_mask, beta, cost_side, ret, ):
    """feat: DataFrame with B, e, rawO. ret: exit return aligned to feat index (simple)."""
    out = []
    for rule, fn in RULE_SIGN.items():
        pos = fn(feat["B"].values, feat["e"].values)
        pos = np.where(pos == 0, 0.0, pos)
        gross = pos * ret
        cost = 2 * cost_side
        net_all = np.where(pos != 0, gross - cost, np.nan)
        for sample, m in [("dev", dev_mask), ("check", chk_mask)]:
            mm = m & (pos != 0)
            net = net_all[mm]
            flip_net = (-gross[mm]) - cost[mm] if isinstance(cost, np.ndarray) else (-gross[mm] - cost)
            s = summarize(net)
            fs = summarize(flip_net)
            drift = summarize(ret[m])
            out.append(dict(exit=exit_kind, ticker=t, rule=rule, sample=sample, **s,
                            flip_mean_bp=fs.get("mean_bp", np.nan), flip_t=fs.get("t", np.nan),
                            drift_mean_bp=drift.get("mean_bp", np.nan), beta=beta))
    return out


all_rows, reg_rows, year_rows = [], [], []
for t in TICKERS:
    f = daily_features(t)
    if ERA:
        f = f[f.index >= pd.Timestamp("2020-08-11")]
    if len(f) < 60:
        print("skip", t, len(f)); continue
    short = f.index[0] > pd.Timestamp("2020-08-31")  # less than ~2 yrs of pre-cut history: use first half as dev
    if short:
        cut_i = len(f) // 2
        dev = np.zeros(len(f), bool); dev[:cut_i] = True
        dev_date_hi = f.index[cut_i - 1]
    else:
        dev = np.asarray(f.index <= DEV_CUT)
    chk = ~dev
    # gap beta estimated on dev only
    # beta uses dev rows from 2020-08-11 on (BTC-treasury era; 2017-20 gap/BTC link is absent for MSTR and diluted for others)
    bm = dev & np.asarray(f.index >= pd.Timestamp("2020-08-11"))
    if bm.sum() < 60:
        bm = dev
    bcoef, _ = ols(f["g"].values[bm], [f["B"].values[bm]])
    beta = bcoef[1]
    e = f["g"].values - beta * f["B"].values
    f = f.assign(e=e)
    cost = np.where(f["rawO"].values < 5, COST_SIDE_LOW, COST_SIDE_NORMAL)
    f["cost"] = cost
    # regressions on dev and check
    for sample, m in [("dev", dev), ("check", chk)]:
        bb, tt = ols(f["oc_log"].values[m], [f["B"].values[m], f["e"].values[m]])
        gb, gt = ols(f["g"].values[m], [f["B"].values[m]])
        reg_rows.append(dict(ticker=t, sample=sample, n=m.sum(), gap_beta=gb[1], gap_beta_t=gt[1],
                             oc_on_B_coef=bb[1], oc_on_B_t=tt[1], oc_on_e_coef=bb[2], oc_on_e_t=tt[2]))
    # daily close exit
    ret_c = f["oc"].values
    # cost per row (vector) via explicit loop-free rules
    for rule, fn in RULE_SIGN.items():
        pos = fn(f["B"].values, f["e"].values)
        gross = pos * ret_c
        net = np.where(pos != 0, gross - 2 * cost, np.nan)
        for sample, m in [("dev", dev), ("check", chk)]:
            mm = m & (pos != 0)
            s = summarize(net[mm])
            flip = summarize((-gross - 2 * cost)[mm])
            all_rows.append(dict(exit="close", ticker=t, rule=rule, sample=sample, **s,
                                 flip_mean_bp=flip.get("mean_bp", np.nan), flip_t=flip.get("t", np.nan),
                                 drift_mean_bp=summarize(ret_c[m]).get("mean_bp", np.nan), beta=beta,
                                 sample_start=str(f.index[m][0].date()), sample_end=str(f.index[m][-1].date())))
        if rule == "BTC_follow" or True:
            # per-year (dev+check combined) for every rule, for later use
            yrs = f.index.year
            for y in np.unique(yrs):
                my = (yrs == y) & (pos != 0)
                if my.sum() == 0: continue
                ss = summarize(net[my])
                year_rows.append(dict(exit="close", ticker=t, rule=rule, year=int(y), **ss))
    # 60m first-hour exit: entry = 09:30 bar open, exit = 09:30 bar close (= 10:30 price)
    p = f"{D}/{t}_60m.parquet"
    if os.path.exists(p):
        h = pd.read_parquet(p)
        h = h[h.index <= CUT + pd.Timedelta(days=1)]
        h = h[h.index.time == time(9, 30)]
        h = h.assign(date=h.index.normalize()).set_index("date")
        h = h[~h.index.duplicated()]
        h = h[(h["open"] > 0) & (h["close"] > 0)]
        ret_h = (h["close"] / h["open"] - 1).rename("ret_h")
        j = f.join(ret_h, how="inner")
        if len(j) >= 60:
            half = j.index[len(j) // 2]
            devh = (j.index < half).astype(bool)
            chkh = ~devh
            for rule, fn in RULE_SIGN.items():
                pos = fn(j["B"].values, j["e"].values)
                gross = pos * j["ret_h"].values
                net = np.where(pos != 0, gross - 2 * j["cost"].values, np.nan)
                for sample, m in [("dev", devh), ("check", chkh)]:
                    mm = m & (pos != 0)
                    s = summarize(net[mm])
                    flip = summarize((-gross - 2 * j["cost"].values)[mm])
                    all_rows.append(dict(exit="first_hour", ticker=t, rule=rule, sample=sample, **s,
                                         flip_mean_bp=flip.get("mean_bp", np.nan), flip_t=flip.get("t", np.nan),
                                         drift_mean_bp=summarize(j["ret_h"].values[m]).get("mean_bp", np.nan),
                                         beta=beta, sample_start=str(j.index[m][0].date()),
                                         sample_end=str(j.index[m][-1].date())))
                    if sample == "dev" and False:
                        pass
                yrs = j.index.year
                for y in np.unique(yrs):
                    my = (yrs == y) & (pos != 0)
                    if my.sum() == 0: continue
                    year_rows.append(dict(exit="first_hour", ticker=t, rule=rule, year=int(y),
                                          **summarize(net[my])))
    print(t, "daily n=", len(f), "short" if short else "long", "beta=%.3f" % beta,
          "dev/check", int(dev.sum()), int(chk.sum()), flush=True)

R = pd.DataFrame(all_rows)
R.to_csv(f"{D}/variants_all{SUF}.csv", index=False)
pd.DataFrame(reg_rows).to_csv(f"{D}/regressions{SUF}.csv", index=False)
pd.DataFrame(year_rows).to_csv(f"{D}/per_year_all{SUF}.csv", index=False)
print("variant rows:", len(R), "tickers:", R.ticker.nunique())
print("n dev/check rows", R.groupby("sample").size().to_dict())
