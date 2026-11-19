"""Audit 1: independent monthly re-implementation vs final_table.csv, and vs item_returns_monthly (per-month)."""
import numpy as np
import pandas as pd
from audit_lib import OUT, AUD, hist, stats

M = pd.read_parquet(OUT / "sleeves_monthly.parquet")
T = pd.read_csv(OUT / "final_table.csv", index_col=0)
IR = pd.read_parquet(OUT / "item_returns_monthly.parquet")
rows = []
for item, L in [("P1u", 1.0), ("P3", 1.0), ("P4", 1.0), ("P4", 1.5), ("P6a", 1.0), ("P6a", 1.25), ("P6a", 1.5), ("P3", 1.5)]:
    key = f"{item}@{L}"
    r, calls = hist(M, item, L)
    s = stats(r, M["CASH"])
    e = T.loc[key]
    er = IR[key].dropna()
    common = r.index.intersection(er.index)
    d = (r.loc[common] - er.loc[common])
    se = stats(er, M["CASH"])  # engine monthly series through MY stats code
    rows.append({"key": key, "audit_window": f"{s['start']}..{s['end']}", "engine_window": f"{e.start}..{e.end}",
                 "audit_cagr": s["cagr"], "engine_cagr": e.cagr, "d_cagr_pp": 100 * (s["cagr"] - e.cagr),
                 "audit_vol": s["vol"], "engine_vol": e.vol,
                 "audit_sharpe": s["sharpe"], "engine_sharpe": e.sharpe, "engine_sharpe_mystats": se["sharpe"],
                 "audit_maxdd": s["maxdd"], "engine_maxdd": e.maxdd, "d_maxdd_pp": 100 * (s["maxdd"] - e.maxdd),
                 "audit_calls_monthly": calls, "engine_calls_daily": e.calls,
                 "max_abs_monthly_diff": d.abs().max(), "mean_monthly_diff_bp": 1e4 * d.mean()})
df = pd.DataFrame(rows).set_index("key")
df.to_csv(AUD / "a1_reimpl_vs_engine.csv")
pd.set_option("display.width", 250)
print(df.round(5).to_string())
