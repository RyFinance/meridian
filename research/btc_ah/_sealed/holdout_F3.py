"""ONE-SHOT sealed holdout for F3 (ZB overnight -> ITB 09:30-10:30), 2026-08-11..2026-10-16. Replications reported alongside."""
import numpy as np, pandas as pd, yfinance as yf
S, E = pd.Timestamp("2026-08-11", tz="America/New_York"), pd.Timestamp("2026-10-16 23:59", tz="America/New_York")
def get(t):
    d = yf.download(t, period="730d", interval="60m", auto_adjust=False, progress=False)
    d.columns = d.columns.get_level_values(0); d.index = d.index.tz_convert("America/New_York"); return d[d.index <= E]
zb = get("ZB=F").Close
def zpx(t):
    s = zb[zb.index <= t - pd.Timedelta(minutes=60)]
    return s.iloc[-1] if len(s) and t - s.index[-1] < pd.Timedelta(hours=4) else np.nan
for t, c in {"ITB": 2, "XHB": 2, "LEN": 3, "DHI": 3, "PHM": 3, "TOL": 3, "SPY": 2}.items():
    d = get(t); d["day"] = d.index.normalize(); first = d[d.index.time == pd.Timestamp("09:30").time()]
    days = list(first.day); rows = []
    for i in range(1, len(days)):
        prev, day = days[i-1], days[i]
        if day < S: continue
        m = np.log(zpx(day + pd.Timedelta(hours=9)) / zpx(prev + pd.Timedelta(hours=16)))
        if not np.isfinite(m) or m == 0: continue
        b = first[first.day == day].iloc[0]
        rows.append(dict(day=day, p=np.sign(m) * np.log(b.Close / b.Open) - 2 * c / 1e4))
    p = pd.DataFrame(rows).set_index("day").p
    print(f"{t}{' (PRIMARY)' if t=='ITB' else ''}: n {len(p)} mean {p.mean()*1e4:+.1f}bp t {p.mean()/p.std()*np.sqrt(len(p)):+.2f} win {(p>0).mean():.2f}  [{p.index.min().date()}..{p.index.max().date()}]")
