"""Attack 1 + 2: independent reproduction and data integrity (DEV only).
  PYTHONPATH=. .venv/bin/python -m research.audit_commodity_roll.a_reproduce
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.audit_commodity_roll.common import (DEV0, DEV1, OUT, PAIRS, SIX, book, dump, pair, proj_close, sharpe,
                                                  yf_raw)

COSTS = {"gross": (0.0, 0.0), "base": (10e-4, 0.010), "stress": (30e-4, 0.040)}
res: dict = {}

# ---------- 1. reproduction from project adjusted closes and from yfinance raw close + dividends ----------
px_proj = {t: proj_close(t) for t in SIX}
raw = {t: yf_raw(t) for t in SIX}
px_raw = {}
for t in SIX:
    h = raw[t]
    tr = ((h["Close"] + h["Dividends"]) / h["Close"].shift() - 1).fillna(0.0)
    px_raw[t] = (1 + tr).cumprod()                       # own total-return index from unadjusted-for-dividends close

dev = pd.read_csv(OUT.parent / "commodity_roll" / "dev_daily.csv", index_col=0, parse_dates=True)
rep = {}
for src, PX in (("project_adj", px_proj), ("yf_close_plus_div", px_raw)):
    rep[src] = {}
    for k, (c, b) in COSTS.items():
        parts = {p: pair(PX[a], PX[s], c, b) for p, (a, s) in PAIRS.items()}
        # live from the day after the first rebalance: pair() already starts the day after the first session
        bk = book(parts)
        d = pd.concat([bk, dev[k]], axis=1, keys=["mine", "director"]).dropna()
        rep[src][k] = {"sharpe_mine": sharpe(bk), "ann_mean_mine": float(bk.mean() * 252),
                       "sharpe_director": sharpe(dev[k]), "n_mine": len(bk), "n_director": int(dev[k].notna().sum()),
                       "corr": float(d.corr().iloc[0, 1]), "max_abs_diff": float((d.mine - d.director).abs().max()),
                       "date_max_diff": str((d.mine - d.director).abs().idxmax().date()),
                       "n_days_diff_gt_1bp": int(((d.mine - d.director).abs() > 1e-4).sum())}
        if k == "base" and src == "project_adj":
            rep[src]["per_pair_sharpe"] = {p: sharpe(s.loc[DEV0:DEV1]) for p, s in parts.items()}
            rep[src]["per_pair_first"] = {p: str(s.loc[DEV0:DEV1].index[0].date()) for p, s in parts.items()}
            pd.DataFrame(parts).loc[DEV0:DEV1].to_csv(OUT / "pairs_base_daily.csv")
            bk.to_csv(OUT / "book_base_daily_mine.csv")
        if k == "gross" and src == "project_adj":
            pd.DataFrame(parts).loc[DEV0:DEV1].to_csv(OUT / "pairs_gross_daily.csv")
res["reproduction"] = rep

# ---------- 2. data integrity ----------
integ = {}
for t in SIX:
    h = raw[t].loc[:DEV1]
    p = px_proj[t]
    r = p.pct_change().dropna()
    z = (r == 0)
    runs = z.groupby((~z).cumsum()).sum()
    vol = h["Volume"]
    dvol = h["Volume"] * h["Close"]
    big = r[r.abs() > 0.15]
    sp = h["Stock Splits"][h["Stock Splits"] != 0]
    around = {}
    for d in sp.index:
        i = h.index.get_loc(d)
        seg = h["Close"].iloc[max(0, i - 2): i + 3]
        around[str(d.date())] = {"ratio": float(sp.loc[d]),
                                 "split_adj_close_returns_around": [round(float(v), 4) for v in seg.pct_change().dropna()]}
    yr = dvol.groupby(dvol.index.year)
    integ[t] = {
        "first": str(p.index[0].date()), "rows_dev": int(len(p)),
        "zero_return_days": int(z.sum()), "longest_zero_run": int(runs.max()),
        "zero_volume_days": int((vol == 0).sum()),
        "abs_ret_gt_15pct": {str(d.date()): round(float(v), 4) for d, v in big.items()},
        "splits_in_dev": around,
        "dividends_in_dev": {str(d.date()): float(v) for d, v in h["Dividends"][h["Dividends"] != 0].items()},
        "median_daily_dollar_volume_by_year_$m": {int(y): round(float(g.median()) / 1e6, 3) for y, g in yr},
        "median_daily_share_volume_by_year": {int(y): int(g.median()) for y, g in vol.groupby(vol.index.year)},
        "zero_volume_days_by_year": {int(y): int((g == 0).sum()) for y, g in vol.groupby(vol.index.year)},
    }
    # stale close on rebalance days: zero volume on a first session
    fs = pd.Series(h.index.to_period("M"), index=h.index)
    first = fs.ne(fs.shift())
    integ[t]["rebalance_days_zero_volume"] = int(((vol == 0) & first).sum())
    integ[t]["rebalance_days_volume_lt_1000sh"] = int(((vol < 1000) & first).sum())
res["integrity"] = integ

# gaps: dates in one leg but not the other (joined with dropna)
gaps = {}
for p_, (a, s) in PAIRS.items():
    ia, is_ = px_proj[a].loc[DEV0:].index, px_proj[s].loc[DEV0:].index
    start = max(ia[0], is_[0])
    gaps[p_] = {"dates_only_in_long": int(len(ia[ia >= start].difference(is_))),
                "dates_only_in_short": int(len(is_[is_ >= start].difference(ia)))}
res["calendar_mismatch"] = gaps
dump("a_reproduce.json", res)
import json
print(json.dumps(res, indent=1)[:9000])
