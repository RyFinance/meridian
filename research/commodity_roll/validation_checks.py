"""Additional binding validation criteria V1-V6 for commodity_roll (research/commodity_roll/VALIDATION_UNLOCK.md).

Definitions follow the independent audit (research/audit_commodity_roll/b_beta.py, c_attacks.py). Every price and
FRED series is truncated at the window end immediately after loading, so a dev run never touches later data.

  PYTHONPATH=. .venv/bin/python -m research.commodity_roll.validation_checks dev
  PYTHONPATH=. .venv/bin/python -m research.commodity_roll.validation_checks validation   (needs the registered unlock)
"""
from __future__ import annotations

import io
import json
import sys

import numpy as np
import pandas as pd

from research.commodity_roll import core
from research.struct_common import ROOT, registered, sharpe

OUT = ROOT / "reports" / "commodity_roll"
RAW = OUT / "raw"
UNLOCK = "research/commodity_roll/VALIDATION_UNLOCK.md"
WINDOWS = {"dev": ("2006-07-21", "2016-12-30"), "validation": ("2017-01-03", "2026-09-17")}
SPOT_FOR = {"crude": "WTI", "natgas": "NG", "broad": "AVG_DBC_GSCI"}
FRED_IDS = {"WTI": "DCOILWTICO", "NG": "DHHNGSP", "BRENT": "DCOILBRENTEU", "HO": "DHOILNYH", "RBOB": "DGASNYH"}
W_DBC = {"WTI": .12375, "BRENT": .12375, "HO": .12375, "RBOB": .12375, "NG": .055, "GLD": .08, "SLV": .02,
         "DBB": .125, "DBA": .225}
W_GSCI = {"WTI": .40, "BRENT": .14, "HO": .06, "RBOB": .06, "NG": .08, "GLD": .025, "SLV": .005, "DBB": .08, "DBA": .15}
NW_LAGS = 4
EXCL_2020 = ("2020-03-01", "2020-06-30")      # V6: periods opened by the first session of Mar-Jun 2020
SEED, DRAWS = 20260923, 5000


def px(t: str, end: str) -> pd.Series:
    for d in (ROOT / "data" / "commodity_roll", ROOT / "data" / "multiasset" / "etf"):
        p = d / f"{t}.parquet"
        if p.exists():
            x = pd.read_parquet(p)
            x["date"] = pd.to_datetime(x["date"])
            x = x[x["date"] <= pd.Timestamp(end)]
            return x.set_index("date")["close"].sort_index().astype(float)
    raise FileNotFoundError(t)


def fred(sid: str, end: str) -> pd.Series:
    x = pd.read_csv(io.StringIO((RAW / f"fred_{sid}_to_20260917.csv").read_text()))
    x.columns = ["date", "v"]
    x["date"] = pd.to_datetime(x["date"])
    x = x[x["date"] <= pd.Timestamp(end)]
    v = pd.to_numeric(x["v"], errors="coerce")
    s = pd.Series(v.to_numpy(), index=x["date"]).dropna().sort_index()
    if sid != "DTB3":
        s = s.where(s > 0).ffill()             # non-positive spot prints (WTI 2020-04-20) -> last positive price
    return s


def first_session_flags(idx: pd.DatetimeIndex) -> np.ndarray:
    per = idx.to_period("M")
    return np.r_[True, per[1:] != per[:-1]]


def nw_ols(y, X, lags=NW_LAGS):
    import statsmodels.api as sm
    df = pd.concat([pd.Series(y, name="y"), pd.DataFrame(X)], axis=1).dropna()
    m = sm.OLS(df.iloc[:, 0], sm.add_constant(df.iloc[:, 1:])).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    return {"n": len(df), "alpha": float(m.params["const"]), "alpha_t": float(m.tvalues["const"]),
            "beta": float(m.params.iloc[1]), "beta_t": float(m.tvalues.iloc[1]), "r2": float(m.rsquared)}


def block_p(x, block, draws=DRAWS, seed=SEED):
    x = np.asarray(x, float)
    n, cx = len(x), x - x.mean()
    rng = np.random.default_rng(seed)
    nb, cnt = -(-n // block), 0
    for _ in range(draws // 500):
        idx = (rng.integers(0, n, size=(500, nb))[:, :, None] + np.arange(block)).reshape(500, -1)[:, :n] % n
        cnt += np.sum(cx[idx].mean(axis=1) >= x.mean())
    return float((cnt + 1) / (draws + 1))


def registered_pairs(w, cost_key):
    """Exactly research.commodity_roll.core.book, on prices truncated at the window end."""
    cost, borrow = core.COSTS[cost_key]
    parts = {k: core.pair_returns(px(a, w[1]), px(b, w[1]), cost, borrow) for k, (a, b) in core.PAIRS.items()}
    P = pd.DataFrame(parts).loc[w[0]:w[1]]
    for k in P:
        d = parts[k].loc[w[0]:w[1]].index
        first = d[first_session_flags(d)] if len(d) else d
        # core.book marks the first session of each month via groupby-min; identical to first_session_flags
        P.loc[:first[0] if len(first) else d[-1], k] = np.nan
    return P, P.mean(axis=1, skipna=True).dropna()


def run(mode: str) -> dict:
    w = WINDOWS[mode]
    if mode == "validation" and not registered(UNLOCK):
        raise SystemExit("validation locked")
    end = w[1]
    gsg = px("GSG", end)
    cal = gsg.loc[w[0]:end].index
    cal_ext = gsg.loc[str((pd.Timestamp(w[0]) - pd.Timedelta(days=550)).date()):end].index   # V2 hedge warm-up
    tick = ["USL", "USO", "UNL", "UNG", "DBC", "GSG", "GLD", "SLV", "DBA", "DBB"]
    PXS = {t: px(t, end) for t in tick}
    R_ext = pd.DataFrame({t: PXS[t].reindex(cal_ext).pct_change() for t in tick}).iloc[1:]
    R = R_ext.loc[cal[1]:]
    spot = pd.DataFrame({k: (lambda v: v.reindex(v.index.union(cal_ext)).ffill().reindex(cal_ext))(fred(s, end))
                         for k, s in FRED_IDS.items()})
    S_ext = spot.pct_change().iloc[1:]
    dtb3 = fred("DTB3", end) / 100 / 360
    rf_ext = dtb3.reindex(dtb3.index.union(cal_ext)).ffill().reindex(cal_ext) * pd.Series(
        np.r_[1, np.diff(cal_ext.values).astype("timedelta64[D]").astype(int)], index=cal_ext)
    rf_ext = rf_ext.iloc[1:]
    X_all = pd.concat([S_ext, R_ext[["GLD", "SLV", "DBB", "DBA"]]], axis=1)

    def wmix(wt):
        cols = list(wt)
        ww = pd.Series(wt)
        return (X_all[cols].fillna(0) * ww).sum(axis=1) / (X_all[cols].notna() * ww).sum(axis=1)

    S_ext["AVG_DBC_GSCI"] = 0.5 * (wmix(W_DBC) + wmix(W_GSCI))
    S, rf = S_ext.loc[R.index], rf_ext.loc[R.index]

    fs = pd.Series(first_session_flags(cal), index=cal)
    per_id = fs.shift(1, fill_value=True).cumsum().reindex(R.index)
    # returns after the j-th first session (j = 1, 2, ...) carry period id j + 1
    per_open = pd.Series(cal[fs.to_numpy()], index=range(2, int(fs.sum()) + 2))

    def to_period(x, how="sum"):
        return x.groupby(per_id).sum(min_count=1) if how == "sum" else (1 + x).groupby(per_id).prod(min_count=1) - 1

    Pb, book = registered_pairs(w, "base")
    live = Pb.notna().reindex(R.index).fillna(False)
    bm = to_period(book.reindex(R.index)).dropna().iloc[1:]
    Sp_m = to_period(S, "prod")
    compm = pd.concat([Sp_m[SPOT_FOR[p]].where(to_period(live[p].astype(float)).reindex(Sp_m.index) > 0)
                       for p in core.PAIRS], axis=1).mean(axis=1).reindex(bm.index)
    res = {"mode": mode, "window": list(w), "n_days": len(book), "n_months": len(bm),
           "book_base_sharpe": sharpe(book), "book_base_ann": float(book.mean() * 252)}

    # V1: monthly alpha on the matched roll-free spot composite
    v1 = nw_ols(bm, compm.rename("spot"))
    res["V1"] = {**v1, "alpha_ann": v1["alpha"] * 12, "pass": bool(v1["alpha"] > 0 and v1["alpha_t"] >= 2.0)}

    # V2: rolling-252-day vol-matched pairs, base costs, excess of cash
    def hedged_pair(a, b, h, cost=10e-4, borrow=0.01):
        j = pd.concat([R_ext[a], R_ext[b], rf_ext], axis=1, keys=["a", "b", "rf"]).dropna()
        j = j.loc[j.index >= max(PXS[a].index[0], PXS[b].index[0])]
        out = pd.Series(np.nan, index=j.index)
        L = Sx = np.nan
        fl = first_session_flags(j.index)
        prev = None
        for i, d in enumerate(j.index):
            if not np.isnan(L):
                ra, rb, rr = j["a"].iat[i], j["b"].iat[i], j["rf"].iat[i]
                pnl = L * (ra - rr) - Sx * (rb - rr) - Sx * borrow * (d - prev).days / 365
                L *= 1 + ra
                Sx *= 1 + rb
                out.iat[i] = pnl
            hh = h.get(d, np.nan)
            if (fl[i] or np.isnan(L)) and np.isfinite(hh):
                if not np.isnan(L):
                    out.iat[i] -= cost * (abs(1 - L) + abs(hh - Sx))
                L, Sx = 1.0, float(hh)
            prev = d
        return out.dropna()

    v2p = {}
    for p, (a, b) in core.PAIRS.items():
        x = pd.concat([R_ext[a], R_ext[b]], axis=1, keys=["a", "b"]).dropna()
        h = x["a"].rolling(252, min_periods=200).std() / x["b"].rolling(252, min_periods=200).std()
        s = hedged_pair(a, b, h).loc[w[0]:w[1]]
        v2p[p] = s.loc[s.index > h.dropna().index[0]]
    v2 = pd.DataFrame(v2p).mean(axis=1).dropna()
    res["V2"] = {"sharpe": sharpe(v2), "ann_mean": float(v2.mean() * 252), "pass": bool(v2.mean() > 0)}

    # V3: no short rebate (lose cash yield on the short notional) on top of the registered 1% borrow
    v3 = pd.DataFrame({p: Pb[p] - rf.reindex(Pb.index).where(Pb[p].notna()) for p in core.PAIRS}).mean(axis=1).dropna()
    res["V3"] = {"sharpe": sharpe(v3), "ann_mean": float(v3.mean() * 252), "pass": bool(v3.mean() > 0)}

    # V4: top-5% months share < 50% and >= 2 of 3 pairs with positive spot-hedged alpha (base pairs, monthly)
    k = max(1, int(round(0.05 * len(bm))))
    top_share = float(bm.sort_values(ascending=False).iloc[:k].sum() / bm.sum()) if bm.sum() > 0 else float("inf")
    pair_alpha = {}
    for p in core.PAIRS:
        ym = to_period(Pb[p].reindex(R.index)).dropna().iloc[1:]
        o = nw_ols(ym, Sp_m[SPOT_FOR[p]].reindex(ym.index).rename("spot"))
        pair_alpha[p] = {"alpha_ann": o["alpha"] * 12, "alpha_t": o["alpha_t"], "beta": o["beta"]}
    npos = sum(v["alpha_ann"] > 0 for v in pair_alpha.values())
    res["V4"] = {"k_months": k, "top5pct_share": top_share, "pair_spot_alpha": pair_alpha, "n_pairs_positive": npos,
                 "pass": bool(top_share < 0.5 and npos >= 2)}

    # V5: block bootstrap p < 0.025 at 21- and 63-day blocks (daily base book)
    p21, p63 = block_p(book.to_numpy(), 21), block_p(book.to_numpy(), 63)
    res["V5"] = {"p_block21": p21, "p_block63": p63, "pass": bool(p21 < 0.025 and p63 < 0.025)}

    # V6: V1 excluding periods opened by the first session of Mar-Jun 2020 (disclosed prior knowledge of 2020)
    opened = per_open.reindex(bm.index)
    keep = ~((opened >= pd.Timestamp(EXCL_2020[0])) & (opened <= pd.Timestamp(EXCL_2020[1])))
    v6 = nw_ols(bm[keep], compm[keep].rename("spot"))
    res["V6"] = {**v6, "alpha_ann": v6["alpha"] * 12, "n_excluded": int((~keep).sum()),
                 "pass": bool(v6["alpha"] > 0 and v6["alpha_t"] >= 1.65)}

    # descriptive only: USO changed to multi-month holdings in Apr-May 2020
    desc = {}
    for nm, m in {"pre_2020_05": opened < pd.Timestamp("2020-05-01"), "post_2020_05": opened >= pd.Timestamp("2020-05-01")}.items():
        if m.sum() >= 12:
            o = nw_ols(bm[m], compm[m].rename("spot"))
            desc[nm] = {"n_months": int(m.sum()), "alpha_ann": o["alpha"] * 12, "alpha_t": o["alpha_t"],
                        "mean_ann": float(bm[m].mean() * 12)}
    res["descriptive_uso_regime"] = desc
    res["descriptive_by_year"] = {int(y): float(g.sum()) for y, g in book.groupby(book.index.year)}
    res["descriptive_pair_sharpe"] = {p: sharpe(Pb[p].dropna()) for p in core.PAIRS}
    res["all_V_pass"] = bool(all(res[f"V{i}"]["pass"] for i in range(1, 7)))
    (OUT / f"{mode}_validation_checks.json").write_text(json.dumps(res, indent=2, default=float))
    return res


if __name__ == "__main__":
    r = run(sys.argv[1] if len(sys.argv) > 1 else "dev")
    print(json.dumps({k: (v if not isinstance(v, dict) or "pass" not in v else {kk: vv for kk, vv in v.items()
                      if not isinstance(vv, dict)}) for k, v in r.items()}, indent=1, default=float))
