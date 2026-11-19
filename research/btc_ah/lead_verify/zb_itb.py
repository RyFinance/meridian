"""Independent check: ZB=F 16:00->09:00 ET move sign -> housing names 09:30 open -> 10:30 (and -> close). yfinance 60m, <= 2026-08-10. Cost 2bp/side ETFs, 3bp stocks."""
import numpy as np, pandas as pd, yfinance as yf
CUT = pd.Timestamp("2026-08-10 23:59", tz="America/New_York")
def get(t):
    d = yf.download(t, period="730d", interval="60m", auto_adjust=False, progress=False, prepost=False)
    d.columns = d.columns.get_level_values(0); d.index = d.index.tz_convert("America/New_York"); return d[d.index <= CUT]
zb = get("ZB=F").Close
def zpx(t):  # last bar CLOSE whose bar ends <= t (bar start <= t-60m)
    s = zb[zb.index <= t - pd.Timedelta(minutes=60)]
    return s.iloc[-1] if len(s) and t - s.index[-1] < pd.Timedelta(hours=4) else np.nan
names = {"ITB": 2, "XHB": 2, "LEN": 3, "DHI": 3, "PHM": 3, "TOL": 3, "KBH": 3, "NVR": 3, "XLU": 2, "KRE": 2, "SPY": 2}
for t, c in names.items():
    d = get(t); d["day"] = d.index.normalize()
    first = d[d.index.time == pd.Timestamp("09:30").time()]
    days = list(first.day); rows = []
    for i in range(1, len(days)):
        prev, day = days[i-1], days[i]
        m = np.log(zpx(day + pd.Timedelta(hours=9)) / zpx(prev + pd.Timedelta(hours=16)))
        if not np.isfinite(m) or m == 0: continue
        b = first[first.day == day].iloc[0]; dd = d[d.day == day]
        rows.append(dict(day=day, s=np.sign(m), h1=np.log(b.Close / b.Open), cl=np.log(dd.Close.iloc[-1] / b.Open)))
    r = pd.DataFrame(rows).set_index("day")
    out = []
    for col in ["h1", "cl"]:
        p = r.s * r[col] - 2 * c / 1e4
        dev, chk = p[p.index < "2025-07-01"], p[p.index >= "2025-07-01"]
        out.append(f"{col}: dev {dev.mean()*1e4:+5.1f}bp t{dev.mean()/dev.std()*np.sqrt(len(dev)):+.2f} | chk {chk.mean()*1e4:+5.1f}bp t{chk.mean()/chk.std()*np.sqrt(len(chk)):+.2f} n{len(chk)} win {(chk>0).mean():.2f}")
    print(f"{t:4s} " + "  ||  ".join(out))
