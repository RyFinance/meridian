"""Cycle 9 item 1: pooled live trend evidence (FRAMEWORK Part A, estimators E1/E2, windows W1/W2, episodes).

Reads the frozen cycle-9 live panel (included funds only) + frozen cycle-8 inputs (RF, SPY/IEF proxies, AQR TSMOM).

usage: python -m research.cycle9.live_trend --live <cycle9 view>/live --proc8 <cycle8 view>/proc --out reports/cycle9/live_trend
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.amendment4 import calib
from research.amendment4.ci import calibrated_ci
from research.cycle8.engine import metrics as MX

SEED = 20260929
EPISODES = {"2008": ("2008-01", "2008-12"), "2018": ("2018-01", "2018-12"), "2020 Feb-Mar": ("2020-02", "2020-03"),
            "2020": ("2020-01", "2020-12"), "2022": ("2022-01", "2022-12"), "2023-2025": ("2023-01", "2025-12")}


def nw_var_mean(x: np.ndarray) -> float:
    """HAC (Bartlett) variance of the sample mean with the A4 bandwidth."""
    x = np.asarray(x, float)
    n = len(x)
    L = calib.stat_lags(n)
    return float(calib.nw_lrv(x - x.mean(), L) / n)


def sharpe_hac_var(x: np.ndarray) -> float:
    """Delta-method HAC variance of the monthly Sharpe ratio (Lo 2002 style with a Bartlett long-run covariance)."""
    x = np.asarray(x, float)
    n = len(x)
    mu, sd = x.mean(), x.std(ddof=1)
    z = np.column_stack([x - mu, (x - mu) ** 2 - sd ** 2])
    L = calib.stat_lags(n)
    S = z.T @ z / n
    for l in range(1, L + 1):
        w = 1 - l / (L + 1)
        G = z[l:].T @ z[:-l] / n
        S += w * (G + G.T)
    g = np.array([1 / sd, -mu / (2 * sd ** 3)])
    return float(g @ S @ g / n)


def fund_stats(x: pd.Series, spy: pd.Series, ief: pd.Series, total: pd.Series) -> dict:
    x = x.dropna()
    t = total.reindex(x.index)
    w = np.r_[1.0, (1 + t.values).cumprod()]
    n = len(x)
    return {"first": f"{x.index[0]:%Y-%m}", "last": f"{x.index[-1]:%Y-%m}", "months": n,
            "cagr_net": w[-1] ** (12 / n) - 1, "excess_ann": x.mean() * 12, "vol": x.std() * np.sqrt(12),
            "sharpe": x.mean() / x.std() * np.sqrt(12), "maxdd": MX.drawdowns(w).max(),
            "corr_spy": x.corr(spy.reindex(x.index)), "corr_ief": x.corr(ief.reindex(x.index))}


def e1_series(panel: pd.DataFrame) -> pd.Series:
    n = panel.notna().sum(1)
    return panel.mean(1).where(n >= 3).dropna()


def e2(panel: pd.DataFrame) -> dict:
    mus, vs, shs, vss = [], [], [], []
    for c in panel:
        x = panel[c].dropna().values
        mus.append(x.mean()); vs.append(nw_var_mean(x))
        shs.append(x.mean() / x.std(ddof=1)); vss.append(sharpe_hac_var(x))
    mus, vs, shs, vss = map(np.array, (mus, vs, shs, vss))
    return {"mu_iv_ann": float((mus / vs).sum() / (1 / vs).sum() * 12),
            "sharpe_iv_ann": float((shs / vss).sum() / (1 / vss).sum() * np.sqrt(12)),
            "mu_ew_funds_ann": float(mus.mean() * 12), "sharpe_ew_funds_ann": float(shs.mean() * np.sqrt(12))}


def bootstrap(panel: pd.DataFrame, B=5000, block=12, seed=SEED) -> dict:
    """Stationary bootstrap over calendar months, all funds jointly; returns 95% intervals for E1 and E2."""
    rng = np.random.default_rng(seed)
    P = panel.values
    n = len(P)
    idx = MX.stationary_indices(n, n, B, block, rng)
    e1m, e1s, ivm, ivs = [], [], [], []
    for b in range(B):
        Q = P[idx[b]]
        cnt = np.isfinite(Q).sum(1)
        e = np.where(cnt >= 3, np.nanmean(np.where(np.isfinite(Q), Q, np.nan), 1), np.nan)
        e = e[np.isfinite(e)]
        if len(e) > 12:
            e1m.append(e.mean() * 12); e1s.append(e.mean() / e.std(ddof=1) * np.sqrt(12))
        mus, ws, shs = [], [], []
        for j in range(Q.shape[1]):
            x = Q[:, j][np.isfinite(Q[:, j])]
            if len(x) < 24:
                continue
            v = x.var(ddof=1) / len(x)
            mus.append(x.mean()); ws.append(1 / v); shs.append(x.mean() / x.std(ddof=1))
        if ws:
            ws = np.array(ws)
            ivm.append((np.array(mus) * ws).sum() / ws.sum() * 12)
            ivs.append((np.array(shs) * ws).sum() / ws.sum() * np.sqrt(12))
    q = lambda a: [float(np.quantile(a, 0.025)), float(np.quantile(a, 0.975))]
    return {"e1_mean_ci": q(e1m), "e1_sharpe_ci": q(e1s), "iv_mean_ci": q(ivm), "iv_sharpe_ci": q(ivs)}


def cum(x: pd.Series, a, b):
    s = x.loc[a:b].dropna()
    return float((1 + s).prod() - 1) if len(s) else np.nan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", required=True)
    ap.add_argument("--proc8", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    live, proc8, out = Path(a.live), Path(a.proc8), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    ex = pd.read_csv(live / "panel_monthly_excess.csv", index_col=0, parse_dates=True)
    tot = pd.read_csv(live / "panel_monthly_total.csv", index_col=0, parse_dates=True)
    for df in (ex, tot):
        df.index = df.index.to_period("M").to_timestamp("M")
    rates = pd.read_parquet(proc8 / "rates_monthly.parquet")
    rf = rates["rf_usd_ret"]
    etf = pd.read_parquet(proc8 / "etf_monthly_adj.parquet")
    etf.index = pd.DatetimeIndex(etf.index).to_period("M").to_timestamp("M")
    eqm = pd.read_parquet(proc8 / "eq_monthly.parquet")["US_usd"]
    bnd = pd.read_parquet(proc8 / "bond_monthly.parquet")["US10_ret"]
    spy = etf["SPY"].pct_change().combine_first(eqm)          # SPY where it exists, Ken French market before
    ief = etf["IEF"].pct_change().combine_first(bnd)          # IEF where it exists, US 10Y par bond before
    ts = pd.read_parquet(proc8 / "trend_monthly.parquet")["tsmom_excess"]
    ts.index = ts.index.to_period("M").to_timestamp("M")

    rows = {c: fund_stats(ex[c], spy, ief, tot[c]) for c in ex}
    F = pd.DataFrame(rows).T
    E1 = e1_series(ex)
    E1n = ex.notna().sum(1).reindex(E1.index)
    ci = calibrated_ci(E1.values, level=0.95, q=12, seed=SEED)
    s1 = {"live_era": f"{E1.index[0]:%Y-%m}..{E1.index[-1]:%Y-%m}", "months": len(E1),
          "mean_excess_ann": E1.mean() * 12, "vol": E1.std() * np.sqrt(12),
          "sharpe": E1.mean() / E1.std() * np.sqrt(12), "sharpe_a4_ci95": ci["sharpe_ann"][:2],
          "corr_spy": E1.corr(spy.reindex(E1.index)), "corr_ief": E1.corr(ief.reindex(E1.index)),
          "funds_min": int(E1n.min()), "funds_max": int(E1n.max())}
    s2 = e2(ex)
    bs = bootstrap(ex)
    # windows: W2 balanced panel of funds with >= 120 months
    longf = [c for c in ex if ex[c].notna().sum() >= 120]
    if longf:
        a0 = max(ex[c].first_valid_index() for c in longf)
        b0 = min(ex[c].last_valid_index() for c in longf)
        if (b0.to_period("M") - a0.to_period("M")).n + 1 < 36:
            longf = sorted(ex, key=lambda c: -ex[c].notna().sum())[:5]
            a0 = max(ex[c].first_valid_index() for c in longf)
            b0 = min(ex[c].last_valid_index() for c in longf)
        W2 = ex.loc[a0:b0, longf]
        w2 = {"window": f"{a0:%Y-%m}..{b0:%Y-%m}", "funds": longf, "ew_mean_excess_ann": W2.mean(1).mean() * 12,
              "ew_sharpe": W2.mean(1).mean() / W2.mean(1).std() * np.sqrt(12),
              "per_fund_sharpe": {c: W2[c].mean() / W2[c].std() * np.sqrt(12) for c in longf}}
    else:
        w2 = {}
    # comparisons with AQR TSMOM on identical months
    def comp(idx):
        t = ts.reindex(idx).dropna()
        return {"aqr_gross_excess_ann": t.mean() * 12, "aqr_gross_sharpe": t.mean() / t.std() * np.sqrt(12),
                "aqr_minus2_excess_ann": t.mean() * 12 - 0.02,
                "aqr_minus2_sharpe": (t.mean() - 0.02 / 12) / t.std() * np.sqrt(12), "months": len(t)}
    comps = {"E1_live_era": comp(E1.index)}
    if w2:
        comps["W2"] = comp(W2.index)
    for c in ex:
        comps[f"fund:{c}"] = comp(ex[c].dropna().index)
    # episodes (cumulative excess and total return)
    ep = {}
    for name, (x0, x1) in EPISODES.items():
        ep[name] = {"E1_excess_cum": cum(E1, x0, x1), "AQR_gross_excess_cum": cum(ts, x0, x1),
                    "SPY_cum": cum(spy, x0, x1), "IEF_cum": cum(ief, x0, x1),
                    "funds_live": int(ex.loc[x0:x1].notna().any().sum())}
        for c in ex:
            ep[name][f"fund:{c}"] = cum(ex[c], x0, x1)
    # pre/post 2012 split of E1 (descriptive)
    split = {k: {"months": len(v), "mean_excess_ann": v.mean() * 12,
                 "sharpe": v.mean() / v.std() * np.sqrt(12) if len(v) > 2 else np.nan}
             for k, v in {"pre2012": E1.loc[:"2011-12"], "post2012": E1.loc["2012-01":]}.items()}
    F.to_csv(out / "per_fund.csv")
    E1.rename("e1_excess").to_frame().assign(n_funds=E1n).to_csv(out / "e1_monthly.csv")
    json.dump({"E1": s1, "E2": s2, "bootstrap": bs, "W2": w2, "comparisons": comps, "episodes": ep,
               "E1_split_2012": split}, open(out / "summary.json", "w"), indent=1, default=float)
    print(json.dumps({"E1": s1, "E2": s2, "bootstrap": bs}, indent=1, default=float))


if __name__ == "__main__":
    main()
