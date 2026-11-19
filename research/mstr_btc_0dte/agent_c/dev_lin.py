"""DEV ONLY: linear-weight version (w = clip(z,-2,2)/2) per name and per set; checks whether the dev
correlations survive costs and whether they are outlier-driven (winsorized corr)."""
import numpy as np, pandas as pd
from pathlib import Path
from bt import SLIP_OPEN, SLIP_CLOSE, COMM
H = Path(__file__).parent
P = pd.read_parquet(H / "panel.parquet"); P = P[P.date <= "2022-12-31"].dropna(subset=["z", "dvol20"])
days = pd.DatetimeIndex(sorted(P[P.date >= "2019-06-01"].date.unique()))
P["w"] = P.z.clip(-2, 2) / 2
P["gross"] = P.w * (np.exp(P.oc) - 1)
P["cost"] = P.w.abs() * (P.large.map(SLIP_OPEN) + P.large.map(SLIP_CLOSE) + COMM / P.Open + COMM / P.Close)
P["net"] = P.gross - P.cost
def st(x):
    d = x.groupby("date").net.sum().reindex(days).fillna(0) / max(1, x.tk.nunique())
    g = x.groupby("date").gross.sum().reindex(days).fillna(0) / max(1, x.tk.nunique())
    return pd.Series(dict(n=len(x), gross_bp=g.mean() * 1e4, net_bp=d.mean() * 1e4, t_net=d.mean() / d.std() * np.sqrt(len(d)),
                          t_gross=g.mean() / g.std() * np.sqrt(len(g)),
                          wcorr=x.z.clip(-2, 2).corr(x.oc.clip(x.oc.quantile(.01), x.oc.quantile(.99))),
                          long_net_bp=1e4 * x.net[x.w > 0].mean(), short_net_bp=1e4 * x.net[x.w < 0].mean()))
print(P.groupby("tk").apply(st).round(2).to_string())
for nm, names in {"all_ex_mstr": [t for t in P.tk.unique() if t != "MSTR"], "coin_hood": ["COIN", "HOOD"],
                  "coin_hood_wulf_clsk_hut": ["COIN", "HOOD", "WULF", "CLSK", "HUT"]}.items():
    print(nm, st(P[P.tk.isin(names)]).round(2).to_dict())
