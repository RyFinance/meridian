"""Extra: convexity (up/down spot betas), robustness of the spot-hedged alpha to crash years / top months,
and per-year alpha. DEV only.
  PYTHONPATH=. .venv/bin/python -m research.audit_commodity_roll.d_extra
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from research.audit_commodity_roll.common import OUT, dump, nw_ols, strip

m = pd.read_csv(OUT / "book_monthly_vs_spot.csv", index_col=0)      # rebalance-period book (base) & matched spot composite
y, x = m["book"], m["spot_comp"]
res = {}
# convexity: Henriksson-Merton style split
X = pd.DataFrame({"spot": x, "down_part": np.minimum(x, 0)})
o = nw_ols(y, X)
res["hm_convexity"] = strip(o)
res["hm_note"] = "down_part coef < 0 => extra gain in down months beyond linear beta (put-like convexity)"
X2 = pd.DataFrame({"spot": x, "spot_sq": x ** 2})
res["quadratic"] = strip(nw_ols(y, X2))
# spot-alpha robustness
lin = nw_ols(y, x.rename("spot"))
beta = lin["spot"]["coef"]
h = y - beta * x                                              # full-sample-beta hedged monthly series
res["spot_hedged_full"] = {"alpha_ann": lin["const"]["coef"] * 12, "t": lin["const"]["t"], "beta": beta}
# drop top-k months of the hedged series
for k in (3, 6, 12):
    hh = h.drop(h.sort_values(ascending=False).index[:k])
    res[f"spot_hedged_ex_top{k}"] = {"alpha_ann": float(hh.mean() * 12), "t": float(hh.mean() / hh.std() * np.sqrt(len(hh)))}
# re-estimate on subsamples (need period start dates: book_monthly_vs_spot index is period id; map via dev_daily)
dd = pd.read_csv(OUT / "book_base_daily_mine.csv", index_col=0, parse_dates=True).iloc[:, 0]
per = dd.index.to_period("M")
# period ids in b_beta start at first session of each month; recover year of each period from ordering
years = pd.Series(sorted(set(per)), dtype=object)
first_months = [p for p in years]
# book_monthly_vs_spot drops the first partial period -> align by position from the end
ym = pd.Series([p.year for p in first_months][-len(y):], index=y.index)
res["period_years_check"] = {"first": int(ym.iloc[0]), "last": int(ym.iloc[-1]), "n": len(ym)}
sub = {}
for nm, ex in {"ex_2006": [2006], "ex_2008": [2008], "ex_2006_2008": [2006, 2008], "ex_2008_2009": [2008, 2009],
               "ex_2006_2008_2015": [2006, 2008, 2015], "ex_2014_2015": [2014, 2015], "2010_2016_only": list(range(2006, 2010))}.items():
    keep = ~ym.isin(ex)
    oo = nw_ols(y[keep], x[keep].rename("spot"))
    sub[nm] = {"alpha_ann": oo["const"]["coef"] * 12, "alpha_t": oo["const"]["t"], "beta": oo["spot"]["coef"],
               "raw_mean_ann": float(y[keep].mean() * 12), "raw_t": float(y[keep].mean() / y[keep].std() * np.sqrt(keep.sum())),
               "n": int(keep.sum())}
res["spot_alpha_subsamples"] = sub
res["spot_alpha_by_year"] = {int(yr): {"hedged_sum": float(h[ym == yr].sum()), "raw_sum": float(y[ym == yr].sum()),
                                       "spot_comp_sum": float(x[ym == yr].sum())} for yr in sorted(set(ym))}
dump("d_extra.json", res)
print(json.dumps(res, indent=1, default=float))
