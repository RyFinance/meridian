"""Audit summary table (numbers copied from a3/a3b outputs and final_table.csv)."""
import pandas as pd
from audit_lib import AUD
a3 = pd.read_csv(AUD / "a3_trend_dependence.csv")
T = pd.read_csv(AUD.parent / "out/final_table.csv", index_col=0)
rows = []
for key, tol, verdict in [("P4@1.5", 25, "SURVIVES (marginal Sharpe under full haircut; substitute P4@1.25 differs 0.03pp fwd)"),
                          ("P6a@1.0", 35, "WEAKENED (fails both tests at post-2012 trend premium; break-even haircut 4-5%/yr)"),
                          ("P6a@1.5", 50, "FAILS robustness (b12=10.2%, 30y=12.2%, 2%/yr haircut flips; P6a@1.25 holds to ~6%/yr)")]:
    r = {"answer": key, "tol": tol, "verdict": verdict,
         "engine_p_dd": T.loc[key, f"p_dd{tol}_20y"], "engine_b12_p_dd": T.loc[key, f"b12_p_dd{tol}_20y"],
         "engine_30y_p_dd": T.loc[key, f"p_dd{tol}_30y"], "hist_maxdd_daily": T.loc[key, "maxdd_daily"]}
    for v in ("full", "post12", "haircut"):
        x = a3[(a3.variant == v) & (a3.key == key)].iloc[0]
        r[f"{v}_sharpe"], r[f"{v}_hurdle"], r[f"{v}_p_dd"] = x.sharpe, x.hurdle_p3, x[f"p_dd{tol}"]
    rows.append(r)
df = pd.DataFrame(rows)
df.to_csv(AUD / "a9_verdicts.csv", index=False)
print(df.round(4).T.to_string())
