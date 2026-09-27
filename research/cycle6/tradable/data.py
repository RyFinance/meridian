"""Snapshot-only loaders for the variants. Every path is resolved inside the frozen view (engine io.resolve).

Builds, on the BOOK's monthly holding-period grid (engine panel convention):
  R  : holding-period return per vehicle -- ETF total return in its listing currency (Yahoo Adj Close);
       micro future: excess-return proxy = the frozen paper instrument series named in the spec (``proxy``);
  U  : unit notional -- ETF as-traded close on its first session of the month (split-adjusted Close x product of
       later split ratios); future: multiplier x level at month-end h-1 (FX spot in USD per unit, or the
       sizing-only level series);
  dy : cash distributions / previous split-adjusted Close summed over the holding period (ETF ex-dates);
  first_month / availability: ETF available in h iff it has a price in calendar month h-1 and a holding-period
       return in h (no backfill); future available in h iff h >= its ``from`` month and its proxy return and
       sizing level exist;
  g, L : USD/CAD (CAD per USD) holding-period change and month-end h-1 level; r: USD 3m T-bill and CAD 3m rate at
       month-end h-1 (annual decimals).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.cycle6.engine import io as eio
from research.cycle6.engine import panel


def period_sum(daily: pd.DataFrame) -> pd.DataFrame:
    """Sum of daily values over the net holding period labelled m (days 2..end of m plus day 1 of m+1)."""
    per = panel.to_period_index(daily.index)
    months = panel.month_range_of(daily)
    fd = panel.first_day_mask(daily)
    x = daily.fillna(0.0)
    tot = x.groupby(per).sum().reindex(months, fill_value=0.0)
    first = x.where(fd, 0.0).groupby(per).sum().reindex(months, fill_value=0.0)
    return tot - first + first.shift(-1).fillna(0.0)


def first_session_value(daily: pd.DataFrame) -> pd.DataFrame:
    fd = panel.first_day_mask(daily)
    per = panel.to_period_index(daily.index)
    return daily.where(fd).groupby(per).first().reindex(panel.month_range_of(daily))


def raw_close(close: pd.DataFrame, splits: pd.DataFrame) -> pd.DataFrame:
    """As-traded close = split-adjusted close x product of split ratios dated after the day."""
    out = close.copy()
    for v in close.columns:
        if v not in splits.columns:
            continue
        s = splits[v].dropna()
        s = s[s != 0]
        f = pd.Series(1.0, index=close.index)
        for d, ratio in s.items():
            f[close.index < d] *= float(ratio)
        out[v] = close[v] * f
    return out


def load_market(params: dict, root) -> dict:
    d = params["data"]
    etfs = [v for v, m in params["vehicles"].items() if m["kind"] == "etf"]
    futs = {v: m for v, m in params["vehicles"].items() if m["kind"] == "future"}
    adj = eio.read_wide(root, d["etf_adjclose"], etfs).dropna(how="all")
    close = eio.read_wide(root, d["etf_close"], etfs).reindex(adj.index)
    splits = eio.read_wide(root, d["etf_splits"])
    divs = eio.read_wide(root, d["etf_dividends"]).reindex(columns=etfs)
    daily_tr = adj.pct_change(fill_method=None)
    daily_tr = daily_tr.where(adj.notna() & adj.shift(1).notna())
    first_px = adj.apply(lambda s: s.first_valid_index())
    for v in etfs:                                   # first priced day: return 0 (entry at that close, no backfill)
        if pd.notna(first_px.get(v)):
            daily_tr.loc[first_px[v], v] = 0.0
    R_etf = panel.net_period_returns(daily_tr)
    priced = adj.notna().groupby(panel.to_period_index(adj.index)).any().reindex(R_etf.index, fill_value=False)
    U_etf = first_session_value(raw_close(close, splits))
    dyd = (divs.reindex(close.index).fillna(0.0) / close.shift(1)).where(close.notna())
    DY = period_sum(dyd.reindex(columns=etfs))
    months = R_etf.index
    # futures proxies + sizing
    R_f, U_f = {}, {}
    spot = eio.read_long(root, d["fx_spot_monthly"])
    spot = spot.pivot(index="date", columns="market_id", values="value")
    spot_m = panel.month_end_sample(spot)
    lev = eio.read_wide(root, d["sizing_levels"])
    lev_m = panel.month_end_sample(lev)
    for v, m in futs.items():
        pr = eio.read_wide(root, m["proxy"]["path"], [m["proxy"]["market_id"]]).dropna(how="all")
        R_f[v] = panel.net_period_returns(pr)[m["proxy"]["market_id"]]
        src = spot_m if m["sizing"]["source"] == "fx_spot" else lev_m
        U_f[v] = float(m["multiplier"]) * src[m["sizing"]["series"]].shift(1)
    fx = eio.read_wide(root, d["usdcad"], ["USDCAD"]).dropna()
    fx_ret = fx.pct_change(fill_method=None)
    g = panel.net_period_returns(fx_ret)["USDCAD"]
    L = panel.month_end_sample(fx["USDCAD"]).shift(1)
    tb = eio.read_series(root, d["tbill"])
    r_usd = panel.month_end_sample(tb).shift(1)
    cad = eio.read_series(root, d["cad_rate"])
    r_cad = panel.month_end_sample(cad).shift(1)
    allm = months
    for s in list(R_f.values()) + list(U_f.values()) + [g, L, r_usd, r_cad]:
        allm = allm.union(s.index)
    allm = pd.period_range(allm.min(), allm.max(), freq="M")
    R = pd.concat([R_etf.reindex(allm), pd.DataFrame(R_f).reindex(allm)], axis=1)
    U = pd.concat([U_etf.reindex(allm), pd.DataFrame(U_f).reindex(allm)], axis=1)
    DY = DY.reindex(allm)
    priced = priced.reindex(allm, fill_value=False)
    status = params.get("_vehicle_status", {})

    def available(v: str, h: pd.Period) -> bool:
        m = params["vehicles"][v]
        if status.get(v, "OK") != "OK":
            return False
        if h not in R.index or pd.isna(R.at[h, v]) or pd.isna(U.at[h, v]):
            return False
        if m["kind"] == "etf":
            return bool(priced.at[h - 1, v]) if (h - 1) in priced.index else False
        return h >= pd.Period(m["from"], "M")

    first_month = {}
    for v in params["vehicles"]:
        ok = [h for h in allm if available(v, h)]
        first_month[v] = str(ok[0]) if ok else None
    return {"R": R, "U": U, "dy": DY, "g": g.reindex(allm), "L": L.reindex(allm),
            "r": {"USD": r_usd.reindex(allm), "CAD": r_cad.reindex(allm)},
            "available": available, "first_month": first_month, "months": allm}


def paper_instrument_returns(params: dict, root) -> pd.DataFrame:
    """Holding-period paper excess returns per BOOK instrument (diagnostic decomposition only)."""
    frames = []
    for ref in params["data"]["paper_panels"]:
        w = eio.read_wide(root, ref["path"]).dropna(how="all")
        r = panel.net_period_returns(w)
        if ref.get("prefix"):
            r.columns = [f"{ref['prefix']}{c}" for c in r.columns]
        frames.append(r)
    return pd.concat(frames, axis=1)


def vehicle_status(root, membership) -> dict:
    from pathlib import Path
    p = Path(membership)
    if not eio._inside(Path(root), p) or not p.exists():
        raise eio.SnapshotPathError("membership (vehicle universe) must lie inside the snapshot root")
    u = pd.read_csv(p)
    return dict(zip(u["vehicle"].astype(str), u["data_status"].astype(str)))
