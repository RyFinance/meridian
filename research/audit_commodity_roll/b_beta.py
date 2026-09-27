"""Attack 3 (central): is the book a disguised short-commodity bet? Roll-free spot proxies, Samuelson effect,
beta-neutral 'pure roll' diagnostic. DEV only.
  PYTHONPATH=. .venv/bin/python -m research.audit_commodity_roll.b_beta
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from research.audit_commodity_roll.common import (DEV0, DEV1, OUT, PAIRS, SIX, dump, first_session_flags, fred, nw_ols,
                                                  pair, proj_close, sharpe, strip)

res: dict = {}
PX = {t: proj_close(t) for t in SIX}
for t in ("SPY", "GLD", "SLV", "DBA", "DBB"):
    PX[t] = proj_close(t)
cal = PX["GSG"].loc[DEV0:DEV1].index                       # book calendar (all six share NYSE Arca sessions)

# ---------- roll-free spot proxies (FRED, requested only to 2016-12-30), put on the ETF calendar ----------
SP = {s: fred(s) for s in ("DCOILWTICO", "DHHNGSP", "DCOILBRENTEU", "DHOILNYH", "DGASNYH")}
spot = pd.DataFrame({k: v.reindex(v.index.union(cal)).ffill().reindex(cal) for k, v in SP.items()})
spot.columns = ["WTI", "NG", "BRENT", "HO", "RBOB"]
rf_d = (fred("DTB3") / 100 / 360).reindex(fred("DTB3").index.union(cal)).ffill().reindex(cal)  # daily cash accrual
rf = rf_d * pd.Series(np.r_[1, np.diff(cal.values).astype("timedelta64[D]").astype(int)], index=cal)

R = pd.DataFrame({t: PX[t].reindex(cal).pct_change() for t in PX}).iloc[1:]
S = spot.pct_change().iloc[1:]
rf = rf.iloc[1:]
# broad roll-free-ish proxy, DBC-index weights (energy spot from FRED; gold/silver physical ETFs; metals & ags via
# futures ETFs DBB/DBA = NOT roll-free, disclosed). Energy-only version available from 2006-07.
w_dbc = {"WTI": .12375, "BRENT": .12375, "HO": .12375, "RBOB": .12375, "NG": .055, "GLD": .08, "SLV": .02,
         "DBB": .125, "DBA": .225}
w_gsci = {"WTI": .40, "BRENT": .14, "HO": .06, "RBOB": .06, "NG": .08, "GLD": .025, "SLV": .005, "DBB": .08, "DBA": .15}
X_all = pd.concat([S, R[["GLD", "SLV", "DBB", "DBA"]]], axis=1)


def wmix(w, X):
    cols = [c for c in w if c in X]
    ww = pd.Series({c: w[c] for c in cols})
    avail = X[cols].notna()
    num = (X[cols].fillna(0) * ww).sum(axis=1)
    den = (avail * ww).sum(axis=1)
    return num / den


S["BROAD_DBCw"] = wmix(w_dbc, X_all)
S["BROAD_GSCIw"] = wmix(w_gsci, X_all)
S["ENERGY_DBCw"] = wmix({k: w_dbc[k] for k in ("WTI", "BRENT", "HO", "RBOB", "NG")}, X_all)
S["AVG_DBC_GSCI"] = 0.5 * (S["BROAD_DBCw"] + S["BROAD_GSCIw"])
SPOT_FOR = {"crude": "WTI", "natgas": "NG", "broad": "AVG_DBC_GSCI"}

# ---------- pairs (own code), gross and base ----------
pairs = {k: {p: pair(PX[a], PX[b], c, bw).reindex(R.index) for p, (a, b) in PAIRS.items()}
         for k, (c, bw) in {"gross": (0, 0), "base": (10e-4, .01)}.items()}
live = pd.DataFrame(pairs["base"]).notna()
book = {k: pd.DataFrame(v).mean(axis=1) for k, v in pairs.items()}

# rebalance periods: day i belongs to the period opened by the last first-session strictly before i
fs = pd.Series(first_session_flags(cal), index=cal)
per_id = fs.shift(1, fill_value=True).cumsum().reindex(R.index)


def to_period(x: pd.Series | pd.DataFrame, how="sum"):
    if how == "sum":
        return x.groupby(per_id).sum(min_count=1)
    return (1 + x).groupby(per_id).prod(min_count=1) - 1


def dimson(y, x, name, lags=(-1, 0, 1)):
    X = pd.DataFrame({f"{name}_{l:+d}": x.shift(-l) for l in lags})   # shift(-1) = t+1 value (ETF closes after spot)
    o = nw_ols(y, X)
    o["beta_sum"] = float(sum(o[c]["coef"] for c in X.columns))
    return o


# ---------- 3a. per pair & book: daily (Dimson) and rebalance-month regressions on roll-free spot ----------
reg = {}
Sp_m = to_period(S, "prod")
R_m = to_period(R, "prod")
rf_m = to_period(rf, "prod")
for p in PAIRS:
    y = pairs["gross"][p].dropna()
    ym = to_period(pairs["gross"][p]).loc[lambda s: s.notna()]
    ym = ym.iloc[1:]                                                  # drop partial first period
    xm = Sp_m[SPOT_FOR[p]].reindex(ym.index)
    d = strip(dimson(y, S[SPOT_FOR[p]].reindex(y.index), SPOT_FOR[p]))
    m = nw_ols(ym, xm.rename(SPOT_FOR[p]))
    reg[p] = {"spot_proxy": SPOT_FOR[p], "daily_dimson": d, "daily_alpha_ann": d["const"]["coef"] * 252,
              "monthly": strip(m), "monthly_alpha_ann": m["const"]["coef"] * 12, "monthly_alpha_t": m["const"]["t"],
              "raw_mean_ann_monthly": float(ym.mean() * 12), "raw_t_monthly": float(ym.mean() / ym.std() * np.sqrt(len(ym))),
              "n_months": int(len(ym)),
              "beta_x_mean_spot_ann": float(m[SPOT_FOR[p]]["coef"] * xm.mean() * 12)}
    if p == "broad":   # energy-only & separate-sector versions (sector tilt; see attack 5)
        for alt in ("ENERGY_DBCw", "WTI", "BROAD_GSCIw", "BROAD_DBCw"):
            mm = nw_ols(ym, Sp_m[alt].reindex(ym.index).rename(alt))
            reg[p][f"monthly_on_{alt}"] = {"alpha_ann": mm["const"]["coef"] * 12, "alpha_t": mm["const"]["t"],
                                           "beta": mm[alt]["coef"], "beta_t": mm[alt]["t"], "r2": mm["r2"]}

# book on book-matched spot composite (average of live pairs' spot proxies) and on separate spots
for k in ("gross", "base"):
    b = book[k].dropna()
    comp = pd.concat([S[SPOT_FOR[p]].where(live[p]) for p in PAIRS], axis=1).mean(axis=1).reindex(b.index)
    bm = to_period(book[k]).dropna().iloc[1:]
    compm = pd.concat([Sp_m[SPOT_FOR[p]].where(to_period(live[p].astype(float)).reindex(Sp_m.index) > 0)
                       for p in PAIRS], axis=1).mean(axis=1).reindex(bm.index)
    d = strip(dimson(b, comp, "spotcomp"))
    m = nw_ols(bm, compm.rename("spotcomp"))
    # separate spots, zero-filled before a pair is live, scaled by 1/n_live (exact book composition)
    nl = live.sum(axis=1)
    Xsep = pd.DataFrame({p: (S[SPOT_FOR[p]] * live[p] / nl) for p in PAIRS}).reindex(b.index)
    Xsep_m = to_period(Xsep).reindex(bm.index)
    msep = nw_ols(bm, Xsep_m)
    dsep = nw_ols(b, Xsep)
    reg[f"book_{k}"] = {"daily_dimson_on_spot_composite": d, "daily_alpha_ann": d["const"]["coef"] * 252,
                        "daily_alpha_t": d["const"]["t"],
                        "monthly_on_spot_composite": strip(m), "monthly_alpha_ann": m["const"]["coef"] * 12,
                        "monthly_alpha_t": m["const"]["t"],
                        "monthly_on_separate_spots": strip(msep), "monthly_sep_alpha_ann": msep["const"]["coef"] * 12,
                        "daily_on_separate_spots_alpha_ann": dsep["const"]["coef"] * 252, "daily_sep_alpha_t": dsep["const"]["t"],
                        "raw_mean_ann": float(bm.mean() * 12), "raw_t_monthly": float(bm.mean() / bm.std() * np.sqrt(len(bm))),
                        "n_months": int(len(bm))}
    if k == "base":
        pd.DataFrame({"book": bm, "spot_comp": compm}).to_csv(OUT / "book_monthly_vs_spot.csv")

# ---------- 3b. director's front basket, matched front basket, long-leg basket, SPY ----------
spy_ex = (R["SPY"] - rf)
fb_dir = R[["USO", "UNG", "GSG"]].mean(axis=1)                     # director: all three whenever available
fb_match = pd.concat([R[b].where(live[p]) for p, (a, b) in PAIRS.items()], axis=1).mean(axis=1)
lb_match = pd.concat([R[a].where(live[p]) for p, (a, b) in PAIRS.items()], axis=1).mean(axis=1)
lb_all = R[["USL", "UNL", "DBC"]].mean(axis=1)
bb = book["base"].dropna()
alt = {}
for nm, x in {"front_basket_director": fb_dir, "front_basket_matched": fb_match, "long_basket_matched": lb_match,
              "long_basket_all": lb_all}.items():
    X = pd.DataFrame({"spy_ex": spy_ex, nm: x}).reindex(bb.index).fillna(0)
    o = nw_ols(bb, X)
    bmm = to_period(book["base"]).dropna().iloc[1:]
    Xm = to_period(pd.DataFrame({"spy_ex": spy_ex, nm: x}).fillna(0)).reindex(bmm.index)
    om = nw_ols(bmm, Xm)
    resid = o["resid"]
    alt[nm] = {"daily_beta": o[nm]["coef"], "daily_beta_t": o[nm]["t"], "beta_spy": o["spy_ex"]["coef"],
               "daily_alpha_ann": o["const"]["coef"] * 252, "daily_alpha_t": o["const"]["t"],
               "resid_plus_alpha_sharpe": sharpe(resid + o["const"]["coef"]),
               "monthly_beta": om[nm]["coef"], "monthly_alpha_ann": om["const"]["coef"] * 12, "monthly_alpha_t": om["const"]["t"]}
    # beta-matched short of the proxy alone
    bm_short = (o[nm]["coef"] * x).reindex(bb.index).fillna(0)
    alt[nm]["beta_matched_proxy_only_sharpe"] = sharpe(bm_short)
    alt[nm]["beta_matched_proxy_only_ann"] = float(bm_short.mean() * 252)
res["book_vs_etf_baskets_base"] = alt

# ---------- 3c. Samuelson effect: leg vols, leg betas to spot, implied net beta ----------
sam = {}
for p, (a, b) in PAIRS.items():
    idx = pairs["gross"][p].dropna().index
    ym = to_period(pairs["gross"][p]).dropna().iloc[1:]
    la, lb_, sp = R_m[a].reindex(ym.index), R_m[b].reindex(ym.index), Sp_m[SPOT_FOR[p]].reindex(ym.index)
    oa, ob = nw_ols(la, sp.rename("s")), nw_ols(lb_, sp.rename("s"))
    oab = nw_ols(la, lb_.rename("front"))
    ra, rb = R[a].reindex(idx), R[b].reindex(idx)
    sam[p] = {"long": a, "short": b,
              "vol_long_daily_ann": float(ra.std() * np.sqrt(252)), "vol_short_daily_ann": float(rb.std() * np.sqrt(252)),
              "vol_long_monthly_ann": float(la.std() * np.sqrt(12)), "vol_short_monthly_ann": float(lb_.std() * np.sqrt(12)),
              "vol_spot_monthly_ann": float(sp.std() * np.sqrt(12)),
              "corr_legs_daily": float(ra.corr(rb)), "corr_legs_monthly": float(la.corr(lb_)),
              "beta_long_to_spot_m": oa["s"]["coef"], "beta_short_to_spot_m": ob["s"]["coef"],
              "implied_net_beta_to_spot": oa["s"]["coef"] - ob["s"]["coef"],
              "beta_long_on_short_m (min-var hedge ratio)": oab["front"]["coef"],
              "beta_long_on_short_daily": float(np.cov(ra, rb)[0, 1] / rb.var()),
              "implied_pair_beta_to_short_leg_daily": float(np.cov(ra, rb)[0, 1] / rb.var() - 1),
              "vol_ratio_daily": float(ra.std() / rb.std()),
              "pair_vol_ann_daily": float(pairs["gross"][p].std() * np.sqrt(252)),
              "spot_mean_ann_over_pair_life_monthly": float(sp.mean() * 12),
              "short_leg_mean_ann": float(lb_.mean() * 12), "long_leg_mean_ann": float(la.mean() * 12)}
    # level decomposition: log(ETF/spot) = cumulative roll+collateral-fees drag; log ratio of legs cancels spot
    i1 = idx[-1]
    st = pairs["gross"][p].dropna().index[0]
    prev = PX[a].loc[:st].index[-2]                   # start from close before first return
    yrs = (i1 - prev).days / 365.25
    spot_lvl = spot[SPOT_FOR[p]] if SPOT_FOR[p] in spot else None
    dec = {"years": yrs,
           "log_ratio_long_over_short_ann": float(np.log(PX[a].loc[i1] / PX[a].loc[prev] / (PX[b].loc[i1] / PX[b].loc[prev])) / yrs)}
    if spot_lvl is not None:
        ls = np.log(spot_lvl.loc[i1] / spot_lvl.loc[prev])
        dec["log_long_minus_log_spot_ann"] = float((np.log(PX[a].loc[i1] / PX[a].loc[prev]) - ls) / yrs)
        dec["log_short_minus_log_spot_ann"] = float((np.log(PX[b].loc[i1] / PX[b].loc[prev]) - ls) / yrs)
        dec["log_spot_change_ann"] = float(ls / yrs)
        dec["spot_start_end"] = [float(spot_lvl.loc[prev]), float(spot_lvl.loc[i1])]
    dec["half_var_diff_ann (log-vs-arith gap)"] = float(0.5 * (R[b].reindex(idx).var() - R[a].reindex(idx).var()) * 252)
    sam[p]["level_decomposition"] = dec
res["samuelson"] = sam

# ---------- 3d. 'pure roll' descriptive diagnostics: beta-neutral / vol-matched pairs (excess of cash) ----------
def hedged_pair(a, b, h_series, cost=0.0, borrow=0.0):
    """long 1 of a, short h of b, reset monthly at first-session close; h taken from h_series at that date.
    Returned as excess of cash: r = L*(ra-rf) - S*(rb-rf) - borrow."""
    j = pd.concat([R[a], R[b], rf], axis=1, keys=["a", "b", "rf"]).dropna()
    j = j.loc[j.index >= max(PX[a].index[0], PX[b].index[0])]
    out = pd.Series(np.nan, index=j.index)
    L = Sx = np.nan
    fs_ = first_session_flags(j.index)
    prev = None
    for i, d in enumerate(j.index):
        if not np.isnan(L):
            ra, rb, rr = j["a"].iat[i], j["b"].iat[i], j["rf"].iat[i]
            dd = (d - prev).days
            pnl = L * (ra - rr) - Sx * (rb - rr) - Sx * borrow * dd / 365
            L *= 1 + ra
            Sx *= 1 + rb
            out.iat[i] = pnl
        h = h_series.get(d, np.nan) if hasattr(h_series, "get") else h_series
        if (fs_[i] or np.isnan(L)) and np.isfinite(h):
            if not np.isnan(L):
                out.iat[i] -= cost * (abs(1 - L) + abs(h - Sx))
            L, Sx = 1.0, float(h)
        prev = d
    return out.dropna()


def pit_ratio(a, b, kind, look=252):
    """point-in-time hedge ratio at each date using the trailing `look` sessions up to t (inclusive of t's close,
    since the hedge is set at t's close)."""
    x = pd.concat([R[a], R[b]], axis=1, keys=["a", "b"]).dropna()
    if kind == "beta":
        h = x["a"].rolling(look, min_periods=200).cov(x["b"]) / x["b"].rolling(look, min_periods=200).var()
    else:
        h = x["a"].rolling(look, min_periods=200).std() / x["b"].rolling(look, min_periods=200).std()
    return h


def tstat(x, lags=None):
    import statsmodels.api as sm
    x = pd.Series(x).dropna()
    n = len(x)
    lags = lags if lags is not None else int(np.floor(4 * (n / 100) ** (2 / 9)))
    m = sm.OLS(x.to_numpy(), np.ones(n)).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    return float(m.tvalues[0])


pure = {}
bn_series = {}
for p, (a, b) in PAIRS.items():
    idx = pairs["gross"][p].dropna().index
    ra, rb = R[a].reindex(idx), R[b].reindex(idx)
    h_is_beta = float(np.cov(ra, rb)[0, 1] / rb.var())
    h_is_vol = float(ra.std() / rb.std())
    variants = {"dollar_neutral_h1": 1.0, "insample_beta": h_is_beta, "insample_vol": h_is_vol,
                "pit_beta_252": pit_ratio(a, b, "beta"), "pit_vol_252": pit_ratio(a, b, "vol")}
    pure[p] = {"h_insample_beta": h_is_beta, "h_insample_vol": h_is_vol}
    for vn, h in variants.items():
        for ck, (c, bw) in {"gross": (0, 0), "base": (10e-4, .01)}.items():
            s = hedged_pair(a, b, h, c, bw).loc[DEV0:DEV1]
            if vn.startswith("pit"):
                s = s.loc[s.index > h.dropna().index[0]]
            sm = to_period(s.reindex(R.index)).dropna()
            pure[p][f"{vn}_{ck}"] = {"sharpe": sharpe(s), "ann_mean": float(s.mean() * 252), "nw_t_daily": tstat(s),
                                     "nw_t_monthly": tstat(sm.iloc[1:]), "first": str(s.index[0].date()), "n": len(s)}
            bn_series[(p, vn, ck)] = s
res["pure_roll_pairs"] = pure

bookpure = {}
for vn in ("dollar_neutral_h1", "insample_beta", "insample_vol", "pit_beta_252", "pit_vol_252"):
    for ck in ("gross", "base"):
        P = pd.DataFrame({p: bn_series[(p, vn, ck)] for p in PAIRS}).loc[DEV0:DEV1]
        bk = P.mean(axis=1).dropna()
        bkm = to_period(bk.reindex(R.index)).dropna().iloc[1:]
        comp = pd.concat([S[SPOT_FOR[p]].where(P[p].notna()) for p in PAIRS], axis=1).mean(axis=1)
        compm = to_period(comp.reindex(R.index)).reindex(bkm.index)
        m = nw_ols(bkm, compm.rename("spotcomp"))
        bookpure[f"{vn}_{ck}"] = {"sharpe": sharpe(bk), "ann_mean": float(bk.mean() * 252), "nw_t_daily": tstat(bk),
                                  "nw_t_monthly": tstat(bkm), "years": len(bk) / 252,
                                  "residual_beta_to_spotcomp_m": m["spotcomp"]["coef"],
                                  "residual_beta_t": m["spotcomp"]["t"],
                                  "alpha_after_spot_ann": m["const"]["coef"] * 12, "alpha_after_spot_t": m["const"]["t"]}
        if vn == "pit_beta_252" and ck == "base":
            bk.to_csv(OUT / "book_pit_beta_neutral_base_daily.csv")
res["pure_roll_book"] = bookpure
res["regressions_on_spot"] = reg
dump("b_beta.json", res)
print(json.dumps(res, indent=1, default=float)[:20000])
