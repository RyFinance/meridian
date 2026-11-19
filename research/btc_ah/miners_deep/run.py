"""Miners deep dive: residual-gap down-gap buys / up-gap fades, conditioned on BTC regime, |z|, era, exits.
Sealed holdout: every parquet is read with a pyarrow filter (dates <= 2026-08-10); nothing later is loaded.
Signal timing: residual uses the 09:30 open (the gap). Variants labelled 'I_*' (ideal) enter at that same open,
which is NOT tradable as stated (the decision needs the open). 'V_*' enter at the 10:30 open (decision at 09:30 bar,
next-bar entry) and are the tradable intraday version. Daily-close variants are all ideal (full 2020-2026 history).
"""
import os, numpy as np, pandas as pd, pyarrow.parquet as pq
from datetime import time as dtime

CUT_EXCL = pd.Timestamp("2026-08-11")          # strict upper bound on every read
TK = "/Users/rytty/CCP/quant_v7/research/btc_ah/tickers/"
CA = "/Users/rytty/CCP/quant_v7/research/btc_ah/miners_deep/cache/"
OUT = "/Users/rytty/CCP/quant_v7/research/btc_ah/miners_deep/"
BTCF = "/Users/rytty/CCP/BTC-Acum/data/btc_usd_1m_candles_polymarket_arb.parquet"
UNIV = ["MARA", "RIOT", "CLSK", "HUT", "CIFR", "WULF", "IREN", "BTBT", "BTDR", "APLD", "GLXY", "HIVE", "CORZ"]
DEV = (pd.Timestamp("2020-08-11"), pd.Timestamp("2023-12-31"))
CHK = (pd.Timestamp("2024-01-01"), pd.Timestamp("2026-08-10"))
Y26 = (pd.Timestamp("2026-01-01"), pd.Timestamp("2026-08-10"))
W_DEV = (pd.Timestamp("2024-08-01"), pd.Timestamp("2025-06-30"))   # intraday-only within-window dev
W_CHK = (pd.Timestamp("2025-07-01"), pd.Timestamp("2026-08-10"))   # intraday-only within-window check
COST_SIDE, COST_LOW = 0.0003, 0.0010


def src(t, kind):
    p = CA + f"{t}_{kind}.parquet"
    if os.path.exists(p) and pq.ParquetFile(p).metadata.num_rows > 0:
        return p
    p = TK + f"{t}_{kind}.parquet"
    return p if os.path.exists(p) else None


def read_tidy(path, dcol):
    df = pq.read_table(path, filters=[(dcol, "<", CUT_EXCL)]).to_pandas()
    if dcol in df.columns:
        df = df.set_index(dcol)
    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_convert("America/New_York").tz_localize(None)
    return df.sort_index()


# ---------- BTC 1m (UTC filter; only bars before 2026-08-11 00:00 UTC are read) ----------
btc = pq.read_table(BTCF, columns=["timestamp", "close"],
                    filters=[("timestamp", "<", pd.Timestamp("2026-08-11", tz="UTC"))]).to_pandas()
btc["ts"] = btc.timestamp.dt.tz_convert("America/New_York").dt.tz_localize(None)
btc = btc.sort_values("ts")
TS, CL = btc.ts.values, btc.close.values.astype(float)


def px_before(targets):
    """Close of the last 1m bar that STARTED before target (known at target). NaN if older than 15 min."""
    t = np.asarray(targets, dtype="datetime64[ns]")
    idx = np.searchsorted(TS, t, side="left") - 1
    ok = idx >= 0
    bar = TS[np.clip(idx, 0, None)]
    fresh = ok & ((t - bar) <= np.timedelta64(15, "m"))
    out = np.full(len(t), np.nan)
    out[fresh] = CL[idx[fresh]]
    return out


cal = read_tidy(TK + "MSTR_1d.parquet", "Date").index
cal = pd.DatetimeIndex(sorted(pd.to_datetime(cal.unique())))
cal = cal[cal >= pd.Timestamp("2017-08-17")]
p16 = px_before(cal + pd.Timedelta(hours=16))
p0925 = px_before(cal + pd.Timedelta(hours=9, minutes=25))
Bcal = np.full(len(cal), np.nan)
Bcal[1:] = np.log(p0925[1:] / p16[:-1])          # 16:00 prev session -> 09:25 today
B_s = pd.Series(Bcal, index=cal)
S16 = pd.Series(p16, index=cal)
# regime known at 16:00 of prior session, used on day D (shift 1)
above_D = (S16 > S16.rolling(50, min_periods=50).mean()).astype(float).where(S16.notna()).shift(1)
r16 = np.log(S16 / S16.shift())
v20 = r16.rolling(20, min_periods=15).std()
volhi_D = (v20 > v20.rolling(250, min_periods=120).median()).astype(float).where(v20.notna()).shift(1)
print("calendar", cal[0].date(), cal[-1].date(), "BTC move obs", int(np.isfinite(Bcal).sum()), flush=True)


def daily_feats(t):
    p = src(t, "1d")
    if p is None:
        return None
    x = read_tidy(p, "Date")
    f = x["adj close"] / x["close"]
    pos = cal.get_indexer(x.index)
    d = pd.DataFrame({"pos": pos, "O": x["open"] * f, "C": x["adj close"], "H": x["high"] * f,
                      "L": x["low"] * f, "rawO": x["open"], "f": f}, index=x.index)
    d = d[d.pos >= 1].copy()
    prev = cal[d.pos.values - 1]
    d["Cprev"] = pd.Series(x["adj close"]).reindex(prev).values
    d["Bt"] = B_s.reindex(d.index).values
    d["up_reg"] = above_D.reindex(d.index).values
    d["volhi"] = volhi_D.reindex(d.index).values
    d = d.dropna(subset=["O", "C", "Cprev", "Bt"])
    d = d[(d.O > 0) & (d.C > 0) & (d.Cprev > 0)]
    d["gap"] = np.log(d.O / d.Cprev)
    d["gap_s"] = d.O / d.Cprev - 1
    g, b = d.gap, d.Bt
    cov = (g * b).rolling(250, min_periods=120).mean() - g.rolling(250, min_periods=120).mean() * b.rolling(250, min_periods=120).mean()
    var = b.rolling(250, min_periods=120).var(ddof=0)
    beta = (cov / var).shift(1)                      # past-only beta
    d["beta"] = beta
    d["res"] = g - beta * b
    d["z"] = d.res / d.res.rolling(250, min_periods=120).std(ddof=0).shift(1)   # z vs own past residuals
    d["t"] = t
    return d


def intraday(t, d):
    p = src(t, "60m")
    if p is None:
        return None
    h = read_tidy(p, "Datetime")
    if len(h) == 0:
        return None
    h = h.assign(date=h.index.normalize(), tm=h.index.time)
    def pick(tm, col):
        s = h[h.tm == tm].set_index("date")[col]
        return s[~s.index.duplicated()]
    cols = {}
    for name, tm in [("930", dtime(9, 30)), ("1030", dtime(10, 30)), ("1230", dtime(12, 30))]:
        cols["O" + name] = pick(tm, "open"); cols["H" + name] = pick(tm, "high"); cols["L" + name] = pick(tm, "low")
    cols["C1530"] = pick(dtime(15, 30), "close"); cols["L1530"] = pick(dtime(15, 30), "low"); cols["H1530"] = pick(dtime(15, 30), "high")
    df = pd.DataFrame(cols)
    df = df.dropna(subset=["O930", "O1030", "O1230", "C1530"])
    f = d["f"].reindex(df.index)
    for c in df.columns:
        df[c] = df[c] * f
    return df


feat, ideal_intra = {}, {}
for t in UNIV:
    d = daily_feats(t)
    if d is None or len(d) < 150:
        print("skip", t, "no daily/short"); continue
    feat[t] = d
    iv = intraday(t, d)
    if iv is not None and len(iv) > 0:
        ideal_intra[t] = iv
    print(f"{t:5s} daily {len(d):5d} {d.index.min().date()}..{d.index.max().date()} "
          f"| 60m days {0 if t not in ideal_intra else len(ideal_intra[t])}", flush=True)


def trades_daily(t, d, dirn, zthr, reg, vol):
    m = d.res.notna() & d.z.notna() & (d.gap_s.abs() <= 0.15)
    if dirn == "down_buy":
        m &= d.res < 0; sign = 1.0
    else:
        m &= d.res > 0; sign = -1.0
    m &= d.z.abs() >= zthr
    if reg == "above": m &= d.up_reg == 1
    if reg == "below": m &= d.up_reg == 0
    if vol == "hi": m &= d.volhi == 1
    if vol == "lo": m &= d.volhi == 0
    x = d[m]
    cost = np.where(x.rawO < 5, 2 * COST_LOW, 2 * COST_SIDE)
    r = x.C / x.O - 1
    out = pd.DataFrame({"date": x.index, "t": t, "sign": sign,
                        "net": sign * r.values - cost, "flip": -sign * r.values - cost,
                        "gross_worst": np.nan})
    return out


def trades_intra(t, d, iv, dirn, zthr, reg, vol, ex):
    dd = d.join(iv, how="inner")
    m = dd.res.notna() & dd.z.notna() & (dd.gap_s.abs() <= 0.15)
    if dirn == "down_buy":
        m &= dd.res < 0; sign = 1.0
    else:
        m &= dd.res > 0; sign = -1.0
    m &= dd.z.abs() >= zthr
    if reg == "above": m &= dd.up_reg == 1
    if reg == "below": m &= dd.up_reg == 0
    if vol == "hi": m &= dd.volhi == 1
    if vol == "lo": m &= dd.volhi == 0
    x = dd[m]
    en, ex_p = EXITS[ex]
    entry = x[en]; exitp = x[ex_p]
    cost = np.where(x.rawO < 5, 2 * COST_LOW, 2 * COST_SIDE)
    r = exitp / entry - 1
    # worst fill: long buys at entry-bar high, sells at exit-bar low; shorts reversed
    e_w = x[en.replace("O", "H")] if sign > 0 else x[en.replace("O", "L")]
    x_w = x[ex_p.replace("O", "L")] if sign > 0 else x[ex_p.replace("O", "H")]
    if ex == "D_close":
        pass
    rw = x_w / e_w - 1
    return pd.DataFrame({"date": x.index, "t": t, "sign": sign,
                         "net": sign * r.values - cost, "flip": -sign * r.values - cost,
                         "net_worst": sign * rw.values - cost})


EXITS = {
    "I_1030": ("O930", "O1030"),    # ideal: enter 09:30 open, exit 10:30 open
    "I_1230": ("O930", "O1230"),    # ideal: enter 09:30 open, exit 12:30 open (12:00 is not on the 60m grid)
    "I_close": ("O930", "C1530"),   # ideal: enter 09:30 open, exit 16:00 close
    "V_1230": ("O1030", "O1230"),   # valid: decision on 09:30 bar, enter 10:30 open, exit 12:30 open
    "V_close": ("O1030", "C1530"),  # valid: decision on 09:30 bar, enter 10:30 open, exit 16:00 close
}

# ---------- build all trades ----------
rows = []
for dirn in ["down_buy", "up_short"]:
    for zthr in [0.0, 1.0, 2.0]:
        for reg in ["all", "above", "below"]:
            for vol in ["all", "hi", "lo"]:
                v = f"{dirn}|z>={zthr:g}|btc_{reg}|vol_{vol}"
                parts = [trades_daily(t, feat[t], dirn, zthr, reg, vol) for t in feat]
                tr = pd.concat(parts)
                tr["variant"], tr["exit"] = v, "D_close"
                rows.append(tr)
                for ex in EXITS:
                    parts = [trades_intra(t, feat[t], ideal_intra[t], dirn, zthr, reg, vol, ex)
                             for t in ideal_intra]
                    tr = pd.concat([p for p in parts if len(p)])
                    tr["variant"], tr["exit"] = v, ex
                    rows.append(tr)
T = pd.concat(rows, ignore_index=True)
print("trade rows", len(T), "variants", T.variant.nunique(), "exits", T.exit.nunique(), flush=True)
T.to_parquet(OUT + "trades.parquet")


def sample_mask(T):
    dt = T.date
    return {
        "dev": (dt >= DEV[0]) & (dt <= DEV[1]),
        "check": (dt >= CHK[0]) & (dt <= CHK[1]),
        "y2026": (dt >= Y26[0]) & (dt <= Y26[1]),
        "w_dev": (dt >= W_DEV[0]) & (dt <= W_DEV[1]),
        "w_chk": (dt >= W_CHK[0]) & (dt <= W_CHK[1]),
    }


def stats(x, col="net"):
    if len(x) == 0:
        return dict(n=0)
    day = x.groupby("date")[col].mean()
    nd = len(day)
    tday = day.mean() / day.std(ddof=1) * np.sqrt(nd) if nd > 2 and day.std(ddof=1) > 0 else np.nan
    fday = x.groupby("date")["flip"].mean()
    ftday = fday.mean() / fday.std(ddof=1) * np.sqrt(len(fday)) if len(fday) > 2 and fday.std(ddof=1) > 0 else np.nan
    w, l = x[col][x[col] > 0], x[col][x[col] <= 0]
    return dict(n=len(x), n_days=nd, win=(x[col] > 0).mean(), mean_bp=x[col].mean() * 1e4, t_day=tday,
                avg_win_bp=w.mean() * 1e4 if len(w) else np.nan, avg_loss_bp=l.mean() * 1e4 if len(l) else np.nan,
                flip_mean_bp=x.flip.mean() * 1e4, flip_t_day=ftday)


res = []
for (v, ex), g in T.groupby(["variant", "exit"]):
    masks = sample_mask(g)
    for sname, mk in masks.items():
        if ex == "D_close" and sname in ("w_dev", "w_chk"):
            continue
        if ex != "D_close" and sname == "dev":
            continue   # intraday exists only from 2024-08: no dev sample for those exits
        s = stats(g[mk.loc[g.index]])
        res.append(dict(variant=v, exit=ex, sample=sname, **s))
    for yr in range(2020, 2027):
        s = stats(g[g.date.dt.year == yr])
        res.append(dict(variant=v, exit=ex, sample=f"y{yr}", **s))
R = pd.DataFrame(res)
R.to_csv(OUT + "variants_stats.csv", index=False)
print("variant x exit combos", R[["variant", "exit"]].drop_duplicates().shape[0], "stat rows", len(R), flush=True)

pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
def tbl(sample, ex=None, n=None):
    q = R[(R["sample"] == sample) & (R.n > 0)]
    if ex is not None: q = q[q.exit.isin(ex)]
    return q
D_ = tbl("dev", ["D_close"]).sort_values("t_day", ascending=False)
print("\nDAILY-CLOSE, dev (2020-08..2023-12) top 12 by t_day:")
print(D_[["variant", "n", "n_days", "win", "mean_bp", "t_day", "flip_mean_bp"]].head(12).to_string(index=False, float_format=lambda x: f"{x:.3f}"))
I_ = tbl("w_dev", list(EXITS)[:]).sort_values("t_day", ascending=False)
print("\nINTRADAY within-window dev (2024-08..2025-06) top 12 by t_day:")
print(I_[["variant", "exit", "n", "n_days", "win", "mean_bp", "t_day", "flip_mean_bp"]].head(12).to_string(index=False, float_format=lambda x: f"{x:.3f}"))
R.to_pickle(OUT + "R.pkl")
print("done")
