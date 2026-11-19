"""Audit 3b: break-even trend haircut. TSMOM excess reduced by h %/yr (0 .. full-minus-post-2012) on the full window;
for each answer item: Sharpe vs P3@1.0 hurdle and bootstrap P(maxDD > tolerance) (24m blocks, 20y, 10,000 paths)."""
import numpy as np
import pandas as pd
from audit_lib import OUT, AUD, hist, stats, boot

M = pd.read_parquet(OUT / "sleeves_monthly.parquet")
ITEMS = [("P4", 1.5, 0.25), ("P4", 1.25, 0.25), ("P6a", 1.0, 0.35), ("P6a", 1.25, 0.50), ("P6a", 1.5, 0.50)]
rows = []
for h_ann in [0, 1, 2, 3, 4, 5, 6, 7.19]:
    h = h_ann / 1200
    Mh = M.copy()
    Mh["X_TREND"] = M["X_TREND"] - h
    Mh["TREND"] = M["TREND"] - h * (1 + M["FXR"])
    for item, L, tol in ITEMS:
        r, _ = hist(Mh, item, L)
        s = stats(r, Mh["CASH"])
        p3, _ = hist(Mh, "P3", 1.0, f"{r.index[0]:%Y-%m}", f"{r.index[-1]:%Y-%m}")
        hur = stats(p3, Mh["CASH"])["sharpe"]
        bb = boot(Mh.loc[r.index[0]:r.index[-1]], item, L, P=10000, seed=20260928)
        p = bb[f"p_dd{int(tol*100)}"]
        rows.append({"haircut_pct_yr": h_ann, "net_trend_excess_pct_yr": 12.25 - h_ann - 2.0, "key": f"{item}@{L}",
                     "tol": tol, "sharpe": s["sharpe"], "hurdle": hur, "sharpe_pass": s["sharpe"] >= hur,
                     "p_dd_tol": p, "dd_pass": p < 0.10, "eligible": (s["sharpe"] >= hur) and p < 0.10,
                     "hist_maxdd": s["maxdd"], "cagr": s["cagr"]})
df = pd.DataFrame(rows)
df.to_csv(AUD / "a3b_haircut_grid.csv", index=False)
print(df.round(4).to_string())
