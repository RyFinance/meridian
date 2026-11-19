"""Step 1: extended-hours BTC->MSTR lead-lag using only minutes where MSTR printed.
Usage: python leadlag.py dev|test"""
import sys

import numpy as np
import pandas as pd

from common import DEV, TEST, H, load_btc, load_mstr, tstat

per = sys.argv[1] if len(sys.argv) > 1 else "dev"
lo, hi = DEV if per == "dev" else TEST
m = load_mstr()
btc = load_btc()
m = m[(m.date >= lo) & (m.date <= hi)]
BETA = 1.2  # fixed, from prior gap-beta work (1.0-1.35)

# ---------- data quality
def sess(hm):
    if 400 <= hm < 800: return "pre_0400_0800"
    if 800 <= hm < 930: return "pre_0800_0930"
    if 930 <= hm < 1600: return "rth"
    if 1600 <= hm < 2000: return "ah_1600_2000"
    return "other"
m = m.assign(s=m.hm.map(sess))
mins = {"pre_0400_0800": 240, "pre_0800_0930": 90, "rth": 390, "ah_1600_2000": 240}
ext_days = m[m.s == "pre_0400_0800"].date.unique()
q = []
for s, n in mins.items():
    g = m[(m.s == s) & m.date.isin(ext_days)]
    nd = len(ext_days)
    vpos = g[g.volume > 0]
    flat = ((g.open == g.high) & (g.high == g.low) & (g.low == g.close)).mean()
    q.append(dict(session=s, days=nd, bars_per_day=len(g) / nd, pct_minutes_with_bar=100 * len(g) / (nd * n),
                  pct_bars_vol0=100 * (g.volume == 0).mean(), med_vol_when_reported=vpos.volume.median(),
                  med_dollar_vol_per_min=(vpos.volume * vpos.close).median(), pct_flat_ohlc=100 * flat))
q = pd.DataFrame(q)
print(f"== {per}: days with ext-hours data {len(ext_days)} / total days {m.date.nunique()}")
print(q.round(1).to_string(index=False))

# ---------- lead-lag on printed minutes
px = {}  # (date) -> Series close indexed by end time
for d, g in m.groupby("date"):
    px[d] = pd.Series(g.close.values, index=g.end)

segs = {"ah_1600_2000": ("16:01", "20:00"), "pre_0400_0800": ("04:01", "08:00"),
        "pre_0800_0929": ("08:00", "09:29"), "rth_0935_1555": ("09:35", "15:55")}
rows, samples = [], []
for name, (a, b) in segs.items():
    for k in (1, 5, 15, 30):
        recs = []
        for d, s in px.items():
            t0 = pd.Timestamp(f"{d.date()} {a}").tz_localize("America/New_York")
            t1 = pd.Timestamp(f"{d.date()} {b}").tz_localize("America/New_York")
            grid = pd.date_range(t0 + pd.Timedelta(minutes=k), t1 - pd.Timedelta(minutes=k), freq=f"{k}min")
            ok = grid[grid.isin(s.index) & (grid + pd.Timedelta(minutes=k)).isin(s.index)
                      & (grid - pd.Timedelta(minutes=k)).isin(s.index)]
            if len(ok) == 0: continue
            mt = s.loc[ok].values; mf = s.loc[ok + pd.Timedelta(minutes=k)].values
            mp = s.loc[ok - pd.Timedelta(minutes=k)].values
            bt = btc.reindex(ok).values; bp = btc.reindex(ok - pd.Timedelta(minutes=k)).values
            bf = btc.reindex(ok + pd.Timedelta(minutes=k)).values
            recs.append(pd.DataFrame(dict(m_next=np.log(mf / mt), m_past=np.log(mt / mp), b_past=np.log(bt / bp),
                                          b_next=np.log(bf / bt))))
        r = pd.concat(recs).dropna()
        gap = BETA * r.b_past - r.m_past
        c = lambda x, y: np.corrcoef(x, y)[0, 1]
        slope = np.polyfit(gap, r.m_next, 1)[0]
        rows.append(dict(seg=name, k=k, n=len(r), corr_btcpast_mnext=c(r.b_past, r.m_next),
                         corr_contemp=c(r.b_next, r.m_next), corr_mpast_mnext=c(r.m_past, r.m_next),
                         corr_catchup_mnext=c(gap, r.m_next), catchup_slope=slope,
                         t_corr_btcpast=c(r.b_past, r.m_next) * np.sqrt(len(r))))
ll = pd.DataFrame(rows)
print("\n== lead-lag (non-overlapping k-min windows; MSTR returns between actual 1m prints)")
print(ll.round(3).to_string(index=False))

# ---------- overnight closed gap (20:00 -> first print after 04:00)
g = []
days = sorted(px)
for i in range(1, len(days)):
    p, d = days[i - 1], days[i]
    sp, sd = px[p], px[d]
    t20 = pd.Timestamp(f"{p.date()} 20:00").tz_localize("America/New_York")
    prev = sp[(sp.index <= t20) & (sp.index > t20 - pd.Timedelta(minutes=30))]
    t4 = pd.Timestamp(f"{d.date()} 04:00").tz_localize("America/New_York")
    first = sd[(sd.index > t4) & (sd.index <= t4 + pd.Timedelta(minutes=15))]
    if prev.empty or first.empty or (d - p).days > 4: continue
    tf = first.index[0]
    rec = dict(date=d, m_gap=np.log(first.iloc[0] / prev.iloc[-1]), b_gap=np.log(btc[tf] / btc[prev.index[-1]]))
    for h in ("04:30", "05:00", "06:00", "08:00", "09:29"):
        th = pd.Timestamp(f"{d.date()} {h}").tz_localize("America/New_York")
        w = sd[(sd.index <= th) & (sd.index > th - pd.Timedelta(minutes=5))]
        rec[f"m_after_{h}"] = np.log(w.iloc[-1] / first.iloc[0]) if len(w) else np.nan
    g.append(rec)
g = pd.DataFrame(g)
g["resid"] = BETA * g.b_gap - g.m_gap
print(f"\n== overnight closed gap: n={len(g)} corr(MSTR gap, BTC gap)={g.m_gap.corr(g.b_gap):.3f} "
      f"slope={np.polyfit(g.b_gap, g.m_gap, 1)[0]:.2f}")
for h in ("04:30", "05:00", "06:00", "08:00", "09:29"):
    col = f"m_after_{h}"; x = g[["resid", col]].dropna()
    print(f"  catch-up resid (1.2*BTCgap - MSTRgap) vs MSTR first-print->{h}: corr={x.resid.corr(x[col]):.3f} n={len(x)}"
          f"  slope={np.polyfit(x.resid, x[col], 1)[0]:.3f}")
ll.to_csv(H / f"leadlag_{per}.csv", index=False); q.to_csv(H / f"quality_{per}.csv", index=False)
g.to_csv(H / f"overnight_gap_{per}.csv", index=False)
