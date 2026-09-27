"""Instrument-free check: 10y yield change over M's window vs the exposure-matched (average 3-session) change.
Date-level LSE US10Y (bonds) and CBOE ^TNX; the dates are TLT sessions. Timing of the yield fixes differs
from the 16:00 ET ETF close, so this is a direction/size check, not a replication.
  PYTHONPATH=. .venv/bin/python -m research.audit_tsy.f_yield_active"""
import json, re
import numpy as np, pandas as pd
from research.audit_tsy.common import OUT, yf_raw
tnx = yf_raw("TNX")["Close"]
obs = {}
for f in sorted(OUT.glob("lse_US10Y_raw_*.txt")):
    for d, v in re.findall(r'"date":"(\d{4}-\d{2}-\d{2})","value":([-0-9.]+)', f.read_text()):
        obs[pd.Timestamp(d)] = float(v)
lse = pd.Series(obs).sort_index()
T = pd.concat([pd.read_csv(OUT / "c_months_dev.csv", index_col=0, parse_dates=["d4", "dl"]),
               pd.read_csv(OUT / "c_months_val.csv", index_col=0, parse_dates=["d4", "dl"])])
raw_idx = yf_raw("TLT").index
res = {}
for nm, y in (("lse_us10y", lse), ("cboe_tnx", tnx)):
    yy = y.reindex(raw_idx).ffill()
    dy = yy.diff() * 100                          # bp per TLT session
    out = {}
    for per, (a, b) in {"dev": ("2003-01", "2014-12"), "val": ("2015-01", "2026-08"), "post_pub_2019-10": ("2019-10", "2026-08")}.items():
        sub = T.loc[a:b]
        mean_daily = dy.loc[a:pd.Period(b).end_time].mean()
        w = sub[f"d10y_{'lse' if nm=='lse_us10y' else 'tnx'}_bp"].dropna()
        ex = w - 3 * mean_daily
        out[per] = {"n": int(len(w)), "window_dy_bp": float(w.mean()), "avg_3session_dy_bp": float(3 * mean_daily),
                    "excess_dy_bp": float(ex.mean()), "t": float(ex.mean() / ex.std() * np.sqrt(len(ex))),
                    "share_windows_yield_down": float((w < 0).mean())}
    res[nm] = out
(OUT / "f_yield_active.json").write_text(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))
