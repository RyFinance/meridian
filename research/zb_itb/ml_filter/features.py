"""Feature builder. Every feature for trade day D uses only data with bar END <= D 09:00 ET (intraday) or daily rows dated < D."""
import numpy as np, pandas as pd
C = "research/zb_itb/verify/yf_cache/"
H = pd.Timedelta(hours=1)
def ld(f, utc=False):
    d = pd.read_parquet(C + f if not utc else f); d.index = d.index.tz_convert("America/New_York"); return d
class Data:
    def __init__(s):
        s.zb = ld("ZB_F_60m.parquet").Close; s.zn = ld("ZN_F_60m.parquet").Close
        s.es = ld("research/zb_itb/ml_filter/ES_F_60m.parquet", utc=True).Close
        s.itb = pd.read_parquet(C + "ITB_1d.parquet").Close; s.tlt = pd.read_parquet(C + "TLT_1d.parquet").Close
        s.itb.index = pd.to_datetime(s.itb.index).normalize(); s.tlt.index = pd.to_datetime(s.tlt.index).normalize()
        t = pd.read_csv("research/zb_itb/verify/f3_trades_canonical.csv", index_col=0, parse_dates=True)
        s.tr = t; s.days = list(t.index)
    def truncate(s, D):
        """Copy containing only what is knowable at 09:00 ET on D (used by the leakage test)."""
        c = object.__new__(Data); cut = L(D) + pd.Timedelta(hours=9)
        for k in ("zb", "zn", "es"): x = getattr(s, k); setattr(c, k, x[x.index + H <= cut])
        c.itb = s.itb[s.itb.index < D]; c.tlt = s.tlt[s.tlt.index < D]
        c.tr = s.tr[s.tr.index < D].copy(); c.days = list(c.tr.index)  # NB: day D's own row (m, g) removed; prev rows kept
        return c
def asof(s, T, used, tol=3):
    """last close of a bar that has ENDED by T (start+1h<=T), no staler than tol hours; records bar end."""
    x = s[s.index + H <= T]
    if len(x) == 0 or (T - (x.index[-1] + H)) > pd.Timedelta(hours=tol): return np.nan
    used.append(x.index[-1] + H); return x.iloc[-1]
def exact(s, start, used):
    if start not in s.index: return np.nan
    used.append(start + H); return s.loc[start]
def L(t): return t if t.tzinfo else t.tz_localize("America/New_York")
def mfun(dat, D, prev):
    """canonical m (exact bars, same as f3_canonical) + path segments for ZB/ZN/ES. returns dict."""
    used = []; out = {}; Dn = D; D = L(D); prev = L(prev)
    t0, t4 = prev + pd.Timedelta(hours=15), D + pd.Timedelta(hours=8)   # bar starts -> closes at 16:00 prev, 09:00 D
    out["m"] = np.log(exact(dat.zb, t4, used) / exact(dat.zb, t0, used))
    cal = L(Dn - pd.Timedelta(days=1))
    Ts = [prev + pd.Timedelta(hours=16), cal + pd.Timedelta(hours=20), D + pd.Timedelta(hours=2), D + pd.Timedelta(hours=8), D + pd.Timedelta(hours=9)]
    for nm, s in (("zb", dat.zb), ("zn", dat.zn), ("es", dat.es)):
        c = [asof(s, T, used) if i not in (0, 4) or nm != "zb" else asof(s, T, used, tol=1) for i, T in enumerate(Ts)]
        out[nm + "_tot"] = np.log(c[4] / c[0])
        if nm == "zb":
            for i in range(4): out[f"seg{i+1}"] = np.log(c[i+1] / c[i])
    return out, used
def day_features(dat, D, prev, mhist):
    """mhist: m values (Series indexed by date) for days strictly before D (computed with the same truncated data)."""
    f, used = mfun(dat, D, prev); m = f["m"]; d = np.sign(m); out = {"m": m, "d": d}
    out["absm"] = abs(m) * 1e4
    mhist = pd.Series(mhist.values, index=pd.DatetimeIndex(mhist.index), dtype=float)
    h = mhist[mhist.index < D].dropna().abs().iloc[-60:]
    out["absm_z"] = (abs(m) - h.mean()) / h.std() if len(h) >= 30 else np.nan
    for i in range(1, 5): out[f"seg{i}"] = f[f"seg{i}"] * d * 1e4                 # direction-aligned
    out["zn_agree"] = float(np.sign(f["zn_tot"]) == d) if np.isfinite(f["zn_tot"]) else np.nan
    out["zn_al"] = f["zn_tot"] * d * 1e4; out["es_al"] = f["es_tot"] * d * 1e4
    c = dat.itb[dat.itb.index < D]; r = np.log(c).diff().dropna()               # daily rows dated < D only
    out["ret5_al"] = np.log(c.iloc[-1] / c.iloc[-6]) * d * 1e4; out["ret20_al"] = np.log(c.iloc[-1] / c.iloc[-21]) * d * 1e4
    out["vol5"] = r.iloc[-5:].std() * 1e4; out["vol20"] = r.iloc[-20:].std() * 1e4
    t = np.log(dat.tlt[dat.tlt.index < D]).diff().dropna(); j = pd.concat([r, t], axis=1, join="inner").iloc[-60:]
    out["corr60"] = j.iloc[:, 0].corr(j.iloc[:, 1])
    for k in range(1, 5): out[f"dow{k}"] = float(D.dayofweek == k)
    out["postholiday"] = float(np.busday_count(prev.date(), D.date()) > 1)
    out["long"] = float(d > 0)
    pt = dat.tr[(dat.tr.index < D) & dat.tr.g_off.notna()]
    out["prev_net"] = (pt.g_off.iloc[-1] - 0.0004) * 1e4 if len(pt) else np.nan   # prev trade exit 10:30 on an earlier day
    out["prev_win"] = float(out["prev_net"] > 0) if len(pt) else np.nan
    return out, used
def build_all(dat, days=None, start=1):
    days = days or dat.days; rows = {}; maxend = {}; mh = {}
    for i in range(start, len(days)):
        D, prev = days[i], days[i-1]
        f, used = day_features(dat, D, prev, pd.Series(mh)) if False else day_features(dat, D, prev, pd.Series(mh, dtype=float))
        mh[D] = f["m"]; rows[D] = f; maxend[D] = max(used) if used else pd.NaT
    return pd.DataFrame(rows).T, pd.Series(maxend)
