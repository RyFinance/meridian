"""Verify START vs END labeling of CL=F/NG=F 60m bars against 5m bars (overlap window)."""
import pandas as pd, numpy as np
C = "research/zb_itb/round5/oil_second_order/cache/"
def ld(f):
    d = pd.read_parquet(C + f); d.index = d.index.tz_convert("America/New_York"); return d
for sym in ["CL_F", "NG_F"]:
    h, m = ld(f"{sym}_60m.parquet"), ld(f"{sym}_5m.parquet")
    m = m.dropna(subset=["High", "Low"]).sort_index()
    res = {"start": [0, 0], "end": [0, 0]}
    for L in h.index[h.index >= m.index.min() + pd.Timedelta(hours=1)][:800]:
        if L.hour < 1: continue
        b = h.loc[L]
        s = m[(m.index >= L) & (m.index < L + pd.Timedelta(hours=1))]
        e = m[(m.index > L - pd.Timedelta(hours=1)) & (m.index <= L)]
        for k, w in [("start", s), ("end", e)]:
            if len(w) < 6: continue
            res[k][1] += 1
            if abs(w.High.max() - b.High) < 1e-6 and abs(w.Low.min() - b.Low) < 1e-6: res[k][0] += 1
    print(sym, {k: f"{v[0]}/{v[1]} match" for k, v in res.items()})
    # the 08:00 and 15:00 bars must exist
    idx = h.index
    print(sym, "bars at 08:00:", int((idx.time == pd.Timestamp("08:00").time()).sum()), "at 15:00:", int((idx.time == pd.Timestamp("15:00").time()).sum()), "total", len(h))
# equity 60m labeling: 09:30 bar open should equal daily open
for sym in ["SPY", "XLU"]:
    e, d = ld(f"{sym}_60m.parquet"), ld(f"{sym}_1d.parquet")
    b = e[e.index.time == pd.Timestamp("09:30").time()]
    dd = d.copy(); dd.index = dd.index.tz_localize(None).normalize()
    j = b.copy(); j.index = j.index.normalize()
    j = j.join(dd[["Open"]].rename(columns={"Open": "dOpen"}), how="inner")
    print(sym, "09:30 60m Open == daily Open:", round(float((abs(j.Open - j.dOpen) < 0.02).mean()), 3), "n", len(j))
