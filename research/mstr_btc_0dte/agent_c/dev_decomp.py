"""DEV ONLY: is corr(u, oc) a BTC under-reaction or just generic gap reversal? oc ~ btc_off + gap (OLS t-stats)."""
import numpy as np, pandas as pd
from pathlib import Path
H = Path(__file__).parent
P = pd.read_parquet(H / "panel.parquet"); P = P[(P.date <= "2022-12-31")].dropna(subset=["u"])
def ols(y, X):
    X = np.column_stack([np.ones(len(y))] + X); b, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ b; s2 = e @ e / (len(y) - X.shape[1]); se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X))); return b / se
rows = []
for tk, s in P.groupby("tk"):
    t = ols(s.oc.values, [s.btc_off.values, s.gap.values])
    rows.append(dict(tk=tk, n=len(s), corr_neg_gap_oc=(-s.gap).corr(s.oc), corr_u_oc=s.u.corr(s.oc),
                     t_btc_off=t[1], t_gap=t[2], corr_neg_gap_oc_when_btc_flat=(-s.gap[s.btc_off.abs() < .01]).corr(s.oc[s.btc_off.abs() < .01])))
print(pd.DataFrame(rows).set_index("tk").round(3).to_string())
