"""Portfolio backtest of the under-reaction rule, open->close, net of costs."""
import numpy as np, pandas as pd
from pathlib import Path
H = Path(__file__).parent
SLIP_OPEN = {True: 5e-4, False: 15e-4}; SLIP_CLOSE = {True: 3e-4, False: 8e-4}; COMM = 0.005
def trades(P, names, k=1.0, mode="ls", btc_min=0.0, horizon="oc"):
    """mode: 'ls' long z>k & short z<-k; 'long' long z>k only; 'cond' long z>k only when btc_off>btc_min,
    short z<-k only when btc_off<-btc_min (under-reaction to the BTC move in either direction)."""
    s = P[P.tk.isin(names)].dropna(subset=["z", horizon, "dvol20"]).copy()
    if mode == "ls": side = np.where(s.z > k, 1, np.where(s.z < -k, -1, 0))
    elif mode == "long": side = np.where(s.z > k, 1, 0)
    elif mode == "cond": side = np.where((s.z > k) & (s.btc_off > btc_min), 1, np.where((s.z < -k) & (s.btc_off < -btc_min), -1, 0))
    if mode != "cond" and btc_min > 0: side = np.where(s.btc_off.abs() > btc_min, side, 0)
    s["side"] = side; s = s[s.side != 0].copy()
    exit_px = s.Open * np.exp(s[horizon])
    gross = s.side * (exit_px / s.Open - 1)
    cost = s.large.map(SLIP_OPEN) + s.large.map(SLIP_CLOSE) + COMM / s.Open + COMM / exit_px
    s["gross"] = gross; s["net"] = gross - cost; s["cost"] = cost
    s["notional"] = np.minimum(1e5, 0.01 * s.dvol20); s["pnl"] = s.net * s.notional
    return s
def stats(T, all_days):
    d = T.groupby("date").net.mean().reindex(all_days).fillna(0.0)
    dg = T.groupby("date").gross.mean().reindex(all_days).fillna(0.0)
    dp = T.groupby("date").pnl.sum().reindex(all_days).fillna(0.0)
    n = len(d); m = d.mean(); sd = d.std(); act = (d != 0)
    eq = d.cumsum(); dd = (eq - eq.cummax()).min()
    return dict(days=n, active=int(act.sum()), trades=len(T), gross_bp=1e4 * dg.mean(), net_bp=1e4 * m,
                net_bp_active=1e4 * d[act].mean() if act.any() else np.nan, t=m / sd * np.sqrt(n) if sd > 0 else np.nan,
                sharpe=m / sd * np.sqrt(252) if sd > 0 else np.nan, maxdd_pct=100 * dd, cost_bp_trade=1e4 * T.cost.mean(),
                pnl_usd=dp.sum(), avg_notional=T.notional.mean(), pct_capped=100 * (T.notional < 1e5).mean(),
                hit=(T.net > 0).mean())
def per_year(T, all_days):
    d = T.groupby("date").net.mean().reindex(all_days).fillna(0.0)
    return d.groupby(d.index.year).agg(lambda x: pd.Series(dict(net_bp=1e4 * x.mean(), t=x.mean() / x.std() * np.sqrt(len(x)) if x.std() > 0 else np.nan))
                                       .to_dict()).apply(pd.Series) if False else pd.DataFrame({
        "net_bp": d.groupby(d.index.year).mean() * 1e4,
        "t": d.groupby(d.index.year).apply(lambda x: x.mean() / x.std() * np.sqrt(len(x)) if x.std() > 0 else np.nan),
        "active": (d != 0).groupby(d.index.year).sum()})
