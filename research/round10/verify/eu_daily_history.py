"""Independent long-history check of the EU-peer lead (daily data, 2010-2026).
Signal = cluster mean of European OPENING-GAP residuals (ln Open_t/Close_{t-1} minus past-only beta x ^STOXX50E gap), known at 03:00 ET.
Trade US peer basket open->close on the same date in the sign of the residual when |residual| > tau. 5 bp/side (10 for CPRI-heavy luxury)."""
import numpy as np, pandas as pd, yfinance as yf
from pathlib import Path
C = Path("research/round10/verify/cache"); C.mkdir(exist_ok=True)
CL = {"luxury": (["MC.PA", "RMS.PA", "KER.PA"], ["TPR", "RL", "CPRI", "EL"]), "autos": (["VOW3.DE", "BMW.DE", "MBG.DE"], ["GM", "F"]),
      "chem": (["BAS.DE", "BAYN.DE"], ["DOW", "LYB"])}
def px(t):
    f = C / f"{t}.parquet"
    if f.exists(): return pd.read_parquet(f)
    d = yf.download(t, start="2009-01-01", end="2026-10-17", auto_adjust=True, progress=False); d.columns = d.columns.get_level_values(0); d.to_parquet(f); return d
sx = px("^STOXX50E"); sgap = np.log(sx.Open / sx.Close.shift())
res = {}
for name, (eu, us) in CL.items():
    rs = []
    for t in eu:
        d = px(t); g = np.log(d.Open / d.Close.shift()); s = sgap.reindex(g.index)
        b = (g.rolling(250, min_periods=120).cov(s) / s.rolling(250, min_periods=120).var()).shift()
        rs.append((g - b * s).rename(t))
    sig = pd.concat(rs, axis=1).mean(axis=1)
    oc = pd.concat([np.log(px(t).Close / px(t).Open).rename(t) for t in us], axis=1).mean(axis=1)
    res[name] = pd.DataFrame({"sig": sig, "oc": oc}).dropna()
cost = 0.0012
for tau in [0.005, 0.01, 0.015]:
    pooled = []
    for name, df in res.items():
        x = df[df.sig.abs() > tau]; p = np.sign(x.sig) * x.oc - cost; pooled.append(p.rename(name))
    P = pd.concat(pooled).sort_index()
    def row(s): return f"n {len(s):4d} {s.mean()*1e4:+5.1f}bp t {s.mean()/s.std()*np.sqrt(len(s)):+.2f}" if len(s) > 5 else "n/a"
    print(f"tau {tau:.3f}: " + " | ".join(f"{a}-{b}: {row(P[(P.index >= a) & (P.index <= b + '-12-31')])}" for a, b in [("2010", "2014"), ("2015", "2019"), ("2020", "2023"), ("2024", "2026")]))
    for name in res:
        s = P[P.index.isin(res[name].index)] if False else pd.concat(pooled)[lambda q: q.name == name] if False else None
    for p in pooled:
        print(f"    {p.name:7s} 2010-23 {row(p[p.index < '2024'])} | 2024-26 {row(p[p.index >= '2024'])}")
