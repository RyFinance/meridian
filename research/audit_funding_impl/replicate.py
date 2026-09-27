"""Independent re-implementation of the frozen rule from PLAN.md text (no import of research.crypto_funding_xs).
Inputs: reports/audit_funding_impl/{klines_dev,funding_dev}.parquet (already truncated at 2022-12-31)."""
from __future__ import annotations
import numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports/audit_funding_impl"
START, END = pd.Timestamp("2020-01-01"), pd.Timestamp("2022-12-31")
DAY = np.int64(86_400_000)


def load():
    K = pd.read_parquet(OUT / "klines_dev.parquet")
    F = pd.read_parquet(OUT / "funding_dev.parquet")
    assert K.day.max() <= END and F.ts.max() < END + pd.Timedelta(days=1)
    return K, F


def panels(K, F, fund_mode="raw"):
    """fund_mode: 'raw' = calc_time as stored; 'hour' = calc_time rounded to the nearest hour (removes the 0-47 ms jitter)."""
    days = pd.date_range(START - pd.Timedelta(days=100), END, freq="D")
    syms = sorted(K.sym.unique())
    piv = lambda c: K.pivot(index="day", columns="sym", values=c).reindex(index=days, columns=syms)
    O, H, L, C, V = (piv(c) for c in ("open", "high", "low", "close", "qv"))
    first = K.groupby("sym").day.min().reindex(syms)
    dms = (days.values.astype("datetime64[ms]").astype(np.int64))
    SIG = pd.DataFrame(np.nan, index=days, columns=syms); NS = SIG.copy(); FUND = pd.DataFrame(0.0, index=days, columns=syms)
    for s, g in F.groupby("sym"):
        if s not in SIG.columns:
            continue
        t = g.t.to_numpy(np.int64)
        if fund_mode == "hour":
            t = ((t + 1_800_000) // 3_600_000) * 3_600_000
        o = np.argsort(t, kind="stable"); t = t[o]; r = g.rate.to_numpy()[o]
        cs = np.concatenate([[0.0], np.cumsum(r)])
        # count/sum of settlements with t in [a, b): searchsorted left on both ends
        lo = np.searchsorted(t, dms - 7 * DAY, "left"); hi = np.searchsorted(t, dms, "left")
        n = hi - lo; ssum = cs[hi] - cs[lo]
        SIG[s] = np.where(n >= 10, ssum / 7.0, np.nan); NS[s] = n
        # paid while held on day t: t in (d, d+1d]
        a = np.searchsorted(t, dms, "right"); b = np.searchsorted(t, dms + DAY, "right")
        FUND[s] = cs[b] - cs[a]
    return dict(O=O, H=H, L=L, C=C, V=V, SIG=SIG, NS=NS, FUND=FUND, first=first, days=days)


def build_weights(P, top_n=100, q=0.2, min_univ=25, shuffle_rng=None):
    days = pd.date_range(START, END, freq="D")
    O, C, V, SIG = P["O"], P["C"], P["V"], P["SIG"]
    syms = list(O.columns)
    Varr = V.to_numpy(); idx = {d: i for i, d in enumerate(P["days"])}
    first = P["first"].to_numpy().astype("datetime64[ns]")
    W = np.full((len(days), len(syms)), np.nan); nU = np.zeros(len(days), int)
    for j, d in enumerate(days):
        i = idx[d]
        win = Varr[i - 30:i]                           # rows t-30 .. t-1
        cnt = np.sum(~np.isnan(win), axis=0)
        with np.errstate(all="ignore"):
            med = np.nanmedian(np.where(cnt[None, :] > 0, win, 0), axis=0)
        med = np.where(cnt >= 15, med, np.nan)
        prev_ok = ~np.isnan(C.iloc[i - 1].to_numpy())
        hist_ok = (np.datetime64(d, "ns") - first) >= np.timedelta64(60, "D")
        sig = SIG.iloc[i].to_numpy()
        el = prev_ok & hist_ok & ~np.isnan(sig) & ~np.isnan(med)
        cand = np.where(el)[0]
        # top-N by median volume, ties -> earlier column (stable sort on -med)
        order = cand[np.argsort(-med[cand], kind="stable")][:top_n]
        n = len(order); nU[j] = n
        if n < min_univ:
            continue
        s = sig[order].copy()
        if shuffle_rng is not None:
            s = shuffle_rng.permutation(s)
        # ascending rank, ties by column order
        o2 = order[np.lexsort((order, s))]
        k = max(1, int(np.floor(q * n)))
        w = np.zeros(len(syms)); w[o2[:k]] = 0.5 / k; w[o2[-k:]] = -0.5 / k
        W[j] = w
    return pd.DataFrame(W, index=days, columns=syms), pd.Series(nU, index=days)


def daily(P, W, cost=7e-4, delist=0.0, drift_turnover=False, fund=None):
    O, C = P["O"].reindex(W.index), P["C"].reindex(W.index)
    F = (fund if fund is not None else P["FUND"]).reindex(W.index)
    live = W.notna().all(axis=1)
    Wf = W.fillna(0.0)
    r = C / O - 1
    miss = r.isna() & (Wf != 0)
    price = (Wf * r.fillna(0)).sum(axis=1) - (miss * Wf.abs()).sum(axis=1) * delist
    fnd = -(Wf * F.fillna(0)).sum(axis=1)
    if drift_turnover:
        drifted = (Wf * (1 + r.fillna(0))).shift(1).fillna(0.0)
        turn = (Wf - drifted).abs().sum(axis=1)
    else:
        turn = Wf.diff().abs().sum(axis=1); turn.iloc[0] = Wf.iloc[0].abs().sum()
    out = pd.DataFrame({"price": price, "fund": fnd, "turn": turn, "cost": turn * cost})
    out["net"] = out.price + out.fund - out.cost
    return out[live]


def sharpe(x):
    x = pd.Series(x).dropna(); return float(x.mean() / x.std(ddof=1) * np.sqrt(365))
