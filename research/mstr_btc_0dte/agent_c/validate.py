"""VALIDATION (2023-01..2026-08), run ONCE for the frozen candidates in frozen_candidates.json."""
import json, numpy as np, pandas as pd
from pathlib import Path
from bt import trades, stats, per_year
H = Path(__file__).parent
F = json.loads((H / "frozen_candidates.json").read_text())
P = pd.read_parquet(H / "panel.parquet"); V = P[(P.date >= "2023-01-01")]
days = pd.DatetimeIndex(sorted(V.date.unique()))
pd.set_option("display.width", 250)
res = {}
for cid, c in F["candidates"].items():
    T = trades(V, c["names"], c["k"], c["mode"], c["btc_min"]); s = stats(T, days); res[cid] = s
    print(f"\n{cid} open->close:", {k: round(float(v), 2) for k, v in s.items()})
    print(per_year(T, days).round(2).T.to_string())
    print("by name (net bp/trade, n):", T.groupby("tk").net.agg(lambda x: round(1e4 * x.mean(), 1)).to_dict(), T.tk.value_counts().to_dict())
    print("long/short net bp/trade:", T.groupby("side").net.agg(lambda x: round(1e4 * x.mean(), 1)).to_dict())
    T.to_csv(H / f"val_trades_{cid}.csv", index=False)
    # descriptive: open->10:30 horizon on days with hourly data
    V2 = V[V.o1030.notna()]; d2 = pd.DatetimeIndex(sorted(V2.date.unique()))
    T2 = trades(V2, c["names"], c["k"], c["mode"], c["btc_min"], horizon="o1030")
    print(f"{cid} open->10:30 (descriptive, {d2.min().date()}..):", {k: round(float(v), 2) for k, v in stats(T2, d2).items() if k in ("trades", "gross_bp", "net_bp", "t", "sharpe")})
json.dump({k: {a: float(b) for a, b in v.items()} for k, v in res.items()}, open(H / "validation_results.json", "w"), indent=1)
# descriptive per-name validation correlations
def tc(r, n): return r * np.sqrt((n - 2) / (1 - r * r))
rows = []
for tk, s in V.groupby("tk"):
    s2 = s.dropna(subset=["u"]); s3 = s2.dropna(subset=["o1030"])
    rows.append(dict(tk=tk, n=len(s), gap_beta=np.polyfit(s.btc_off, s.gap, 1)[0], corr_gap=s.btc_off.corr(s.gap),
                     corr_off_oc=s.btc_off.corr(s.oc), t1=tc(s.btc_off.corr(s.oc), len(s)), hit_off=(np.sign(s.btc_off) == np.sign(s.oc)).mean(),
                     corr_u_oc=s2.u.corr(s2.oc), t2=tc(s2.u.corr(s2.oc), len(s2)), hit_u=(np.sign(s2.u) == np.sign(s2.oc)).mean(),
                     wcorr_z_oc=s2.z.clip(-2, 2).corr(s2.oc.clip(s2.oc.quantile(.01), s2.oc.quantile(.99))),
                     corr_off_1030=s3.btc_off.corr(s3.o1030), corr_u_1030=s3.u.corr(s3.o1030), n1030=len(s3)))
R = pd.DataFrame(rows).set_index("tk").round(3); print("\nvalidation per-name (descriptive):"); print(R.to_string()); R.to_csv(H / "val_per_name.csv")
