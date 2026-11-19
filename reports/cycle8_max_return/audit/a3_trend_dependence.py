"""Audit 3/4: dependence of the three answers on the pre-2012 TSMOM record + bootstrap cross-check.

Variants
  full   : engine sleeves, each item's own window (cross-check of engine P(DD), own bootstrap code)
  post12 : only months 2012-01..2026-05 (historical Sharpe and bootstrap drawn only from those months)
  haircut: full window, TSMOM excess reduced every month by (full mean - post-2012 mean) so the full-sample mean
           excess equals the post-2012 mean; TREND and X_TREND rebuilt with the haircut.
Bootstrap: own stationary bootstrap, mean block 24, 240 months, 10,000 paths, month-end margin checks.
Descriptive robustness only; not a change to the preregistered answer.
"""
import numpy as np
import pandas as pd
from audit_lib import OUT, AUD, SNAP, me, hist, stats, boot

M = pd.read_parquet(OUT / "sleeves_monthly.parquet")
T = pd.read_csv(OUT / "final_table.csv", index_col=0)
tr = pd.read_parquet(SNAP / "proc/trend_monthly.parquet")
tr.index = me(tr.index)
x = tr["tsmom_excess"]
full_mean, post_mean, pre_mean = x.mean(), x.loc["2012-01":].mean(), x.loc[:"2011-12"].mean()
h = full_mean - post_mean
print(f"TSMOM mean excess %/yr: full {1200*full_mean:.2f}  pre-2012 {1200*pre_mean:.2f}  post-2012 {1200*post_mean:.2f}"
      f"  haircut {1200*h:.2f}%/yr")
Mh = M.copy()
Mh["X_TREND"] = M["X_TREND"] - h
Mh["TREND"] = M["TREND"] - h * (1 + M["FXR"])

KEYS = [("P3", 1.0), ("P3", 1.25), ("P1u", 1.0), ("P4", 1.0), ("P4", 1.25), ("P4", 1.5), ("P4", 2.0),
        ("P6a", 1.0), ("P6a", 1.25), ("P6a", 1.5)]
PATHS = 10000
rows = []
for var, MM, a, b in [("full", M, None, None), ("post12", M, "2012-01", "2026-05"), ("haircut", Mh, None, None)]:
    for item, L in KEYS:
        r, calls = hist(MM, item, L, a, b)
        s = stats(r, MM["CASH"])
        p3, _ = hist(MM, "P3", 1.0, r.index[0].strftime("%Y-%m"), r.index[-1].strftime("%Y-%m"))
        hurdle = stats(p3, MM["CASH"])["sharpe"]
        Mw = MM.loc[r.index[0]:r.index[-1]]
        bb = boot(Mw, item, L, P=PATHS, mb=24, H=240, seed=20260928)
        row = {"variant": var, "key": f"{item}@{L}", **s, "hurdle_p3": hurdle, "sharpe_pass": s["sharpe"] >= hurdle,
               **bb}
        if var == "full":
            e = T.loc[f"{item}@{L}"]
            row.update({"engine_p_dd25": e.p_dd25_20y, "engine_p_dd35": e.p_dd35_20y, "engine_p_dd50": e.p_dd50_20y})
        rows.append(row)
        print(var, row["key"], {k: round(v, 4) if isinstance(v, float) else v for k, v in row.items()
                                if k in ("cagr", "sharpe", "hurdle_p3", "maxdd", "p_dd25", "p_dd35", "p_dd50",
                                         "engine_p_dd25", "engine_p_dd35", "engine_p_dd50")}, flush=True)
df = pd.DataFrame(rows)
df.to_csv(AUD / "a3_trend_dependence.csv", index=False)
