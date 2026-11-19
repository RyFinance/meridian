"""Independent audit stats for the live rule on ITB and NAIL, 2016-26, from raw Alpaca SIP 15-min bars.
Signal: sign(TLT last pre-market print 08:00-09:15 / TLT previous 16:00 close) -- a tradable proxy for the live ZB signal.
Trade d x leg from the 09:30 open to 10:30, 3% stop ignored (conservative on wins and losses alike), only when the
past-only 60d corr(ITB, TLT daily returns) > 0. Written fresh 2026-10-29; shares no code with research/zb_itb."""
import sys, json, numpy as np, pandas as pd
sys.path.insert(0, "."); from research.xmkt_1027.prep import daily

def daily_itb():
    """bars/ITB.parquet stops at 2019-06 (pull bug), so ITB comes from the complete zb_itb/alpaca_check 1m files,
    resampled to the same start-labeled 15-min bars that prep.daily expects."""
    import glob, research.xmkt_1027.prep as P
    m = pd.concat(pd.read_parquet(f) for f in sorted(glob.glob("research/zb_itb/alpaca_check/bars/ITB_*.parquet")))
    b = m.set_index("t").resample("15min").agg({"o": "first", "h": "max", "l": "min", "c": "last", "v": "sum"}).dropna(subset=["o"])
    b = b.reset_index(); b["n"] = 1; b["vw"] = b.c
    orig = P.pd.read_parquet; P.pd.read_parquet = lambda *_a, **_k: b
    try:
        return P.daily("ITB")
    finally:
        P.pd.read_parquet = orig

T, I, N = daily("TLT"), daily_itb(), daily("NAIL")
idx = T.index.intersection(I.index)
d = np.sign(T.pre915 / T.prev - 1).reindex(idx)
rt, ri = T.c1600.pct_change(), I.c1600.pct_change()
corr = rt.rolling(60).corr(ri).shift(1).reindex(idx)          # known before today's open
COST = {"ITB": 2e-4, "NAIL": 5e-4}

def legret(L, entry="o930", exit="c1030", cost=None, sym="ITB", thr=0.0, dd=None):
    L = L.reindex(idx); s = d if dd is None else dd
    g = s * (L[exit] / L[entry] - 1)
    on = (s != 0) & (corr > thr) & L[entry].notna() & L[exit].notna()
    return (g - 2 * (COST[sym] if cost is None else cost)).where(on)

def stats(r, label):
    r = r.dropna(); tr = r[r != 0]
    if len(tr) < 5:
        return {"label": label, "n": int(len(tr))}
    cal = pd.Series(0.0, index=idx[(idx >= r.index.min()) & (idx <= r.index.max())]); cal.loc[r.index] = r
    eq = (1 + cal).cumprod(); yrs = len(cal) / 252; cagr = eq.iloc[-1] ** (1 / yrs) - 1
    dd = eq / eq.cummax() - 1; uw = (dd < 0).astype(int); dur = uw.groupby((uw == 0).cumsum()).sum().max()
    m = (1 + cal).groupby(cal.index.to_period("M")).prod() - 1
    q5, q1 = np.quantile(tr, .05), np.quantile(tr, .01)
    ac = tr.autocorr(1)
    return {"label": label, "n": int(len(tr)), "mean_bp": round(tr.mean() * 1e4, 1), "t": round(tr.mean() / tr.std() * np.sqrt(len(tr)), 2),
            "win": round((tr > 0).mean() * 100, 1), "cagr": round(cagr * 100, 1), "sharpe": round(cal.mean() / cal.std() * np.sqrt(252), 2),
            "maxdd": round(dd.min() * 100, 1), "calmar": round(cagr / -dd.min(), 2), "dd_days": int(dur),
            "worst_day": round(tr.min() * 100, 2), "worst_month": round(m.min() * 100, 1), "best_month": round(m.max() * 100, 1),
            "es95": round(tr[tr <= q5].mean() * 100, 2), "es99": round(tr[tr <= q1].mean() * 100, 2), "ac1": round(ac, 3),
            "pos_months": round((m > 0).mean() * 100, 0)}

out = {}
for sym, L in [("ITB", I), ("NAIL", N)]:
    base = legret(L, sym=sym)
    o = {"full": stats(base, "2016-26")}
    for a, b in [("2016", "2019"), ("2020", "2023"), ("2024", "2026")]:
        o[a + "-" + b[2:]] = stats(base[a:b], a + "-" + b[2:])
    o["no_regime_switch"] = stats(legret(L, sym=sym, thr=-9), "no switch")
    o["long_only"] = stats(base.where(d > 0), "long only")
    sens = {}
    for k, kw in {"exit 10:00": dict(exit="c1000"), "exit 11:30": dict(exit="c1130"), "exit 13:00": dict(exit="c1300"),
                  "exit 16:00": dict(exit="c1600"), "enter 09:45": dict(entry="c945"), "corr > 0.2": dict(thr=0.2),
                  "corr > -0.2": dict(thr=-0.2), "cost 2x": dict(cost=COST[sym] * 2), "cost 4x": dict(cost=COST[sym] * 4)}.items():
        s = stats(legret(L, sym=sym, **kw), k); sens[k] = {x: s.get(x) for x in ("n", "mean_bp", "t", "cagr", "sharpe", "maxdd")}
    o["sensitivity"] = sens
    # placebo: random signs, same days, same regime filter
    rng = np.random.default_rng(7); base_t = o["full"]["t"]; pl = []
    for _ in range(2000):
        rs = pd.Series(rng.choice([-1.0, 1.0], len(idx)), index=idx)
        x = legret(L, sym=sym, dd=rs).dropna(); pl.append(x.mean() / x.std() * np.sqrt(len(x)))
    o["placebo_p"] = float((np.array(pl) >= base_t).mean())
    # Monte Carlo, 1 year forward, half the historical edge: iid vs 20-day block bootstrap of the daily series
    r = base.dropna(); cal = pd.Series(0.0, index=idx[idx >= r.index.min()]); cal.loc[r.index] = r
    cal = cal - cal[cal != 0].mean() / 2 * (cal != 0)                                         # haircut: half the mean edge
    v = cal.values; mc = {}
    for name, B in [("iid", 1), ("block20", 20)]:
        paths = []
        for _ in range(20000):
            st = rng.integers(0, len(v) - B, 252 // B + 1); x = np.concatenate([v[s:s + B] for s in st])[:252]
            e = np.cumprod(1 + x); paths.append((e[-1] - 1, (e / np.maximum.accumulate(e) - 1).min()))
        p = np.array(paths)
        mc[name] = {"median_ret": round(np.median(p[:, 0]) * 100, 1), "p5_ret": round(np.quantile(p[:, 0], .05) * 100, 1),
                    "p_loss": round((p[:, 0] < 0).mean() * 100, 1), "median_dd": round(np.median(p[:, 1]) * 100, 1),
                    "p5_dd": round(np.quantile(p[:, 1], .05) * 100, 1), "p_dd_gt_30": round((p[:, 1] < -.30).mean() * 100, 1),
                    "p_dd_gt_50": round((p[:, 1] < -.50).mean() * 100, 1)}
    o["montecarlo_half_edge"] = mc
    out[sym] = o
ITBr, NAILr = legret(I, sym="ITB").dropna(), legret(N, sym="NAIL").dropna()
out["corr_itb_nail_trades"] = round(ITBr.corr(NAILr.reindex(ITBr.index)), 3)
json.dump(out, open("research/xmkt_1027/audit_1029.json", "w"), indent=1)
print(json.dumps(out, indent=1))
