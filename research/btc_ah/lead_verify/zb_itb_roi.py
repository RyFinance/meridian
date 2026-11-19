"""Annualized ROI for F3 (ITB, 1x capital per trade, 2bp/side) over all data incl. holdout, by period; plus long-only and max drawdown."""
import numpy as np, pandas as pd, yfinance as yf
def get(t):
    d = yf.download(t, period="730d", interval="60m", auto_adjust=False, progress=False)
    d.columns = d.columns.get_level_values(0); d.index = d.index.tz_convert("America/New_York"); return d[d.index <= pd.Timestamp("2026-10-16 23:59", tz="America/New_York")]
zb = get("ZB=F").Close; itb = get("ITB")
def zpx(t):
    s = zb[zb.index <= t - pd.Timedelta(minutes=60)]
    return s.iloc[-1] if len(s) and t - s.index[-1] < pd.Timedelta(hours=4) else np.nan
first = itb[itb.index.time == pd.Timestamp("09:30").time()].copy(); first["day"] = first.index.normalize()
rows = []
days = list(first.day)
for i in range(1, len(days)):
    m = np.log(zpx(days[i] + pd.Timedelta(hours=9)) / zpx(days[i-1] + pd.Timedelta(hours=16)))
    if np.isfinite(m) and m != 0:
        b = first.iloc[i]; rows.append(dict(day=days[i], d=np.sign(m), r=np.log(b.Close / b.Open)))
x = pd.DataFrame(rows).set_index("day")
x["net"] = x.d * x.r - 0.0004; x["long"] = np.where(x.d > 0, x.r - 0.0004, 0.0)
def stats(p, label):
    yrs = (p.index[-1] - p.index[0]).days / 365.25
    eq = np.exp(p.cumsum()); dd = (eq / eq.cummax() - 1).min()
    print(f"{label:28s} {p.index[0].date()}..{p.index[-1].date()} trades {int((p!=0).sum())} | CAGR {(eq.iloc[-1]**(1/yrs)-1)*100:+.0f}% | ann vol {p.std()*np.sqrt(252)*100:.0f}% | Sharpe {p.mean()/p.std()*np.sqrt(252):.2f} | maxDD {dd*100:.0f}%")
stats(x.net, "long/short, all")
stats(x.net[x.index < "2025-07-01"], "long/short, dev")
stats(x.net[(x.index >= "2025-07-01") & (x.index < "2026-08-11")], "long/short, check")
stats(x.net[x.index >= "2026-08-11"], "long/short, holdout")
stats(x.long, "long-only, all")
print("ITB buy&hold same span:", f"{(itb.Close.iloc[-1]/itb.Open.iloc[0]-1)*100:+.0f}% total")
