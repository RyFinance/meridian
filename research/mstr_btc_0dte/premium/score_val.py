"""Score the frozen premium-momentum validation (M1, M2) against the pre-registered criteria in CANDIDATES.md.
net_stress = 2*net_base - gross  (stress multiplies both cost and carry; cost+carry = gross - net_base)."""
import pandas as pd, numpy as np
from pathlib import Path

H0 = Path(__file__).parent

def score(fn):
    t = pd.read_csv(H0 / fn, parse_dates=["entry", "exit"])
    bad = t.net.isna()
    if bad.any():
        print(f"  [note] dropping {bad.sum()} NaN row(s): {t.loc[bad, ['entry','exit']].to_dict('records')}")
    t = t[~bad].copy()
    t["net2"] = 2 * t.net - t.gross
    t["yr"] = t.entry.dt.year
    out = {"n": len(t), "years": round((t.entry.max() - t.entry.min()).days / 365.25, 2)}
    for col, lbl in [("net", "base"), ("net2", "stress2x")]:
        x = t[col]
        out[f"{lbl}_win"] = round((x > 0).mean(), 3)
        out[f"{lbl}_mean_bp"] = round(x.mean() * 1e4, 1)
        out[f"{lbl}_t"] = round(x.mean() / x.std() * np.sqrt(len(x)), 2)
        out[f"{lbl}_total"] = round(x.sum(), 3)
    yr = t.groupby("yr").net.agg(["sum", "count"])
    yrs = (t.entry.max() - t.entry.min()).days / 365.25
    yearly = {int(k): (round(v["sum"], 3), int(v["count"])) for k, v in yr.iterrows()}
    return out, yearly

for name in ["M1", "M2"]:
    out, yearly = score(f"val_{name}.csv")
    print(f"== {name} ==")
    for k, v in out.items():
        print(f"  {k}: {v}")
    print("  per-year (net sum, n):")
    for y, (s, n) in yearly.items():
        flag = "  <-- FAIL (< -20%)" if s < -0.20 else ""
        print(f"    {y}: {s:+.3f}  n={n}{flag}")
