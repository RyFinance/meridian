"""Attacks 4-7: crash-year concentration, broad-pair composition, costs/liquidity, null/placebo. DEV only.
  PYTHONPATH=. .venv/bin/python -m research.audit_commodity_roll.c_attacks
"""
from __future__ import annotations

import itertools
import json

import numpy as np
import pandas as pd
from scipy import stats

from research.audit_commodity_roll.common import (DEV0, DEV1, OUT, PAIRS, SIX, dump, first_session_flags, fred, nw_ols,
                                                  pair, proj_close, sharpe, strip, yf_raw)

res: dict = {}
PX = {t: proj_close(t) for t in SIX + ["SPY", "GLD", "SLV", "DBA", "DBB"]}
cal = PX["GSG"].loc[DEV0:DEV1].index
R = pd.DataFrame({t: PX[t].reindex(cal).pct_change() for t in PX}).iloc[1:]
SP = {"WTI": fred("DCOILWTICO"), "NG": fred("DHHNGSP"), "BRENT": fred("DCOILBRENTEU"), "HO": fred("DHOILNYH"),
      "RBOB": fred("DGASNYH")}
spot = pd.DataFrame({k: v.reindex(v.index.union(cal)).ffill().reindex(cal) for k, v in SP.items()})
S = spot.pct_change().iloc[1:]
dtb3 = fred("DTB3")
rf = ((dtb3 / 100 / 360).reindex(dtb3.index.union(cal)).ffill().reindex(cal)
      * pd.Series(np.r_[1, np.diff(cal.values).astype("timedelta64[D]").astype(int)], index=cal)).iloc[1:]
w_dbc = {"WTI": .12375, "BRENT": .12375, "HO": .12375, "RBOB": .12375, "NG": .055, "GLD": .08, "SLV": .02, "DBB": .125, "DBA": .225}
w_gsci = {"WTI": .40, "BRENT": .14, "HO": .06, "RBOB": .06, "NG": .08, "GLD": .025, "SLV": .005, "DBB": .08, "DBA": .15}
X_all = pd.concat([S, R[["GLD", "SLV", "DBB", "DBA"]]], axis=1)


def wmix(w):
    cols = list(w)
    ww = pd.Series(w)
    return (X_all[cols].fillna(0) * ww).sum(axis=1) / (X_all[cols].notna() * ww).sum(axis=1)


S["BROAD"] = 0.5 * (wmix(w_dbc) + wmix(w_gsci))
S["TILT_DBC_minus_GSCI"] = wmix(w_dbc) - wmix(w_gsci)
SPOT_FOR = {"crude": "WTI", "natgas": "NG", "broad": "BROAD"}

fs = pd.Series(first_session_flags(cal), index=cal)
per_id = fs.shift(1, fill_value=True).cumsum().reindex(R.index)
per_start = pd.Series(cal[fs.to_numpy()], index=np.arange(1, fs.sum() + 1))


def to_period(x, how="sum"):
    if how == "sum":
        return x.groupby(per_id).sum(min_count=1)
    return (1 + x).groupby(per_id).prod(min_count=1) - 1


COST = {"gross": (0, 0), "base": (10e-4, .01), "stress": (30e-4, .04)}
pairs = {k: {p: pair(PX[a], PX[b], c, bw).reindex(R.index) for p, (a, b) in PAIRS.items()} for k, (c, bw) in COST.items()}
live = pd.DataFrame(pairs["base"]).notna()
book = {k: pd.DataFrame(v).mean(axis=1).dropna() for k, v in pairs.items()}
b = book["base"]
T = len(b) / 252
gate = lambda n: 1.8 / np.sqrt(n / 252)

# ======================= 4. crash-year concentration =======================
cc = {}
yrs = sorted(set(b.index.year))
cc["full"] = {"sharpe": sharpe(b), "ann_mean": float(b.mean() * 252), "gate": gate(len(b))}
cc["leave_one_year_out"] = {}
for y in yrs:
    x = b[b.index.year != y]
    cc["leave_one_year_out"][int(y)] = {"sharpe": sharpe(x), "ann_mean": float(x.mean() * 252), "passes_sharpe_gate": bool(sharpe(x) >= gate(len(x)))}
for nm, ex in {"ex_2008": [2008], "ex_2014_2015": [2014, 2015], "ex_2008_2014_2015": [2008, 2014, 2015],
               "ex_2006": [2006], "ex_2006_2008": [2006, 2008], "ex_2006_2008_2015": [2006, 2008, 2015],
               "only_2009_2013": [2006, 2007, 2008, 2014, 2015, 2016]}.items():
    x = b[~b.index.year.isin(ex)]
    xm = to_period(x.reindex(R.index)).dropna()
    cc[nm] = {"sharpe": sharpe(x), "ann_mean": float(x.mean() * 252), "gate": gate(len(x)),
              "passes_sharpe_gate": bool(sharpe(x) >= gate(len(x))),
              "monthly_t": float(xm.mean() / xm.std() * np.sqrt(len(xm)))}
# since all three pairs live (2010-01-05 on)
x = b.loc["2010-01-05":]
cc["all_three_live_2010_2016"] = {"sharpe": sharpe(x), "ann_mean": float(x.mean() * 252), "gate": gate(len(x))}
x = b.loc[:"2010-01-04"]
cc["pre_2010_partial_book"] = {"sharpe": sharpe(x), "ann_mean": float(x.mean() * 252)}

bm = to_period(b.reindex(R.index)).dropna().iloc[1:]
comp_m = pd.concat([to_period(S[SPOT_FOR[p]], "prod").where(to_period(live[p].astype(float)) > 0) for p in PAIRS],
                   axis=1).mean(axis=1).reindex(bm.index)
up, dn = bm[comp_m > 0], bm[comp_m <= 0]
cc["conditional_on_spot_composite"] = {
    "up_months": {"n": len(up), "mean_monthly": float(up.mean()), "t": float(up.mean() / up.std() * np.sqrt(len(up)))},
    "down_months": {"n": len(dn), "mean_monthly": float(dn.mean()), "t": float(dn.mean() / dn.std() * np.sqrt(len(dn)))}}
big_dn = bm[comp_m < comp_m.quantile(0.1)]
cc["conditional_on_spot_composite"]["worst_decile_spot_months"] = {"n": len(big_dn), "sum": float(big_dn.sum()),
                                                                    "share_of_total_pnl": float(big_dn.sum() / bm.sum())}
k = max(1, int(round(0.05 * len(bm))))
top = bm.sort_values(ascending=False).iloc[:k]
cc["top5pct_months"] = {"k": k, "months": {str(per_start[i].date()): round(float(v), 4) for i, v in top.items()},
                        "share_of_total_pnl": float(top.sum() / bm.sum()),
                        "total_pnl_sum": float(bm.sum()), "ex_top5pct_mean_ann": float(bm.drop(top.index).mean() * 12),
                        "ex_top5pct_t": float(bm.drop(top.index).mean() / bm.drop(top.index).std() * np.sqrt(len(bm) - k))}
npos = int((bm > 0).sum())
cc["sign_test_monthly"] = {"n": len(bm), "positive": npos, "frac": npos / len(bm),
                           "p_one_sided": float(stats.binomtest(npos, len(bm), 0.5, alternative="greater").pvalue)}
# per pair sign tests and monthly t
cc["per_pair_monthly"] = {}
for p in PAIRS:
    pm = to_period(pairs["base"][p]).dropna().iloc[1:]
    n_ = int((pm > 0).sum())
    cc["per_pair_monthly"][p] = {"n": len(pm), "pos": n_, "sign_p": float(stats.binomtest(n_, len(pm), .5, alternative="greater").pvalue),
                                 "mean_ann": float(pm.mean() * 12), "t": float(pm.mean() / pm.std() * np.sqrt(len(pm))),
                                 "median_monthly": float(pm.median())}
# variance ratio (daily vs monthly vol) -- negative autocorrelation from thin/stale legs
cc["vol_daily_ann"] = float(b.std() * np.sqrt(252))
cc["vol_monthly_ann"] = float(bm.std() * np.sqrt(12))
cc["variance_ratio_monthly_over_daily"] = float((bm.var() / 21) / b.var())
cc["daily_autocorr_lag1_book"] = float(b.autocorr(1))
cc["daily_autocorr_lag1_pairs"] = {p: float(pairs["base"][p].dropna().autocorr(1)) for p in PAIRS}
cc["monthly_sharpe_ann"] = float(bm.mean() / bm.std() * np.sqrt(12))
res["4_concentration"] = cc

# ---- contango-regime dependence (descriptive): front ETF drag vs spot over prior 63 sessions ----
reg_dep = {}
for p, (a, s_) in PAIRS.items():
    if p == "broad":
        continue
    drag = (np.log1p(R[s_]) - np.log1p(S[SPOT_FOR[p]])).rolling(63).sum()       # realized roll+fees drag, trailing
    d_at = drag.groupby(per_id).last().shift(1)                                     # known at period start
    pm = to_period(pairs["gross"][p]).dropna().iloc[1:]
    z = pd.concat([pm, d_at.reindex(pm.index)], axis=1, keys=["ret", "drag"]).dropna()
    hi, lo = z[z.drag < z.drag.median()], z[z.drag >= z.drag.median()]      # more negative drag = steeper contango
    reg_dep[p] = {"steep_contango_half_mean_ann": float(hi.ret.mean() * 12), "flat_or_backwardation_half_mean_ann": float(lo.ret.mean() * 12),
                  "corr_prior_drag_next_ret": float(z.corr().iloc[0, 1]), "n": len(z)}
res["4b_contango_regime"] = reg_dep

# ======================= 5. broad pair composition =======================
bp = to_period(pairs["gross"]["broad"]).dropna().iloc[1:]
Sm = to_period(S, "prod")
Rm = to_period(R, "prod")
comp = {}
sec = pd.concat([Sm[["WTI", "NG"]], Rm[["GLD", "DBB", "DBA", "SPY"]]], axis=1).reindex(bp.index)
m1 = nw_ols(bp, sec)
comp["monthly_on_sectors_2007plus"] = strip(m1)
comp["monthly_on_sectors_alpha_ann"] = m1["const"]["coef"] * 12
m2 = nw_ols(bp, pd.concat([Sm["BROAD"], Sm["TILT_DBC_minus_GSCI"]], axis=1).reindex(bp.index))
comp["monthly_on_avgspot_and_tilt"] = strip(m2)
m3 = nw_ols(bp, Rm[["USO"]].reindex(bp.index))
comp["monthly_on_USO"] = strip(m3)
m4 = nw_ols(bp, Sm[["WTI"]].reindex(bp.index))
comp["monthly_on_WTI_spot"] = strip(m4)
# how much of broad-pair variance is sector tilt vs level: partial R2 of tilt
m5 = nw_ols(bp, Sm[["BROAD"]].reindex(bp.index))
comp["r2_level_only"] = m5["r2"]
comp["r2_level_plus_tilt"] = m2["r2"]
comp["tilt_contribution_ann"] = float(m2["TILT_DBC_minus_GSCI"]["coef"] * Sm["TILT_DBC_minus_GSCI"].reindex(bp.index).mean() * 12)
comp["level_contribution_ann"] = float(m2["BROAD"]["coef"] * Sm["BROAD"].reindex(bp.index).mean() * 12)
comp["broad_pair_mean_ann"] = float(bp.mean() * 12)
# 2006 H2 anatomy (only the broad pair is live)
w = slice("2006-07-24", "2006-12-29")
comp["2006H2"] = {"DBC": float((1 + R["DBC"].loc[w]).prod() - 1), "GSG": float((1 + R["GSG"].loc[w]).prod() - 1),
                  "WTI_spot": float((1 + S["WTI"].loc[w]).prod() - 1), "NG_spot": float((1 + S["NG"].loc[w]).prod() - 1),
                  "GLD": float((1 + R["GLD"].loc[w]).prod() - 1), "USO": float((1 + R["USO"].loc[w]).prod() - 1),
                  "energy_spot_DBCw": float((1 + (0.225 * S["WTI"] + .225 * S["BRENT"] + .225 * S["HO"] + .225 * S["RBOB"] + .1 * S["NG"]).loc[w]).prod() - 1),
                  "broad_pair_sum": float(pairs["gross"]["broad"].loc[w].sum())}
res["5_broad_composition"] = comp

# ======================= 6. costs, borrow, liquidity =======================
cst = {}
turn = {}
for p, (a, s_) in PAIRS.items():
    j = pd.concat([PX[a], PX[s_]], axis=1, keys=["l", "s"]).dropna().loc[:DEV1]
    r_ = j.pct_change().fillna(0)
    ff = first_session_flags(j.index)
    L = Sx = 1.0
    tv = []
    for i in range(1, len(j)):
        L *= 1 + r_["l"].iat[i]
        Sx *= 1 + r_["s"].iat[i]
        if ff[i]:
            tv.append(abs(1 - L) + abs(1 - Sx))
            L = Sx = 1.0
    turn[p] = {"mean_monthly_traded_notional": float(np.mean(tv)), "annual_traded_notional": float(np.mean(tv) * 12)}
cst["turnover"] = turn
grid = {}
for c in (0, 10e-4, 30e-4, 50e-4, 100e-4, 200e-4):
    for bw in (0, .01, .02, .04, .06, .08):
        bb = pd.DataFrame({p: pair(PX[a], PX[s_], c, bw).reindex(R.index) for p, (a, s_) in PAIRS.items()}).mean(axis=1).dropna()
        grid[f"cost{c*1e4:.0f}bp_borrow{bw*100:.0f}pct"] = {"sharpe": round(sharpe(bb), 4), "ann_mean": round(float(bb.mean() * 252), 5),
                                                             "passes_sharpe_gate": bool(sharpe(bb) >= gate(len(bb)))}
cst["grid"] = grid
# break-evens (linear in cost/borrow)
g0 = book["gross"].mean() * 252
avg_turn = np.mean([turn[p]["annual_traded_notional"] for p in PAIRS])
cst["gross_mean_ann"] = float(g0)
cst["breakeven_per_side_cost_bp_at_1pct_borrow"] = float((g0 - 0.01) / avg_turn * 1e4)
cst["breakeven_borrow_pct_at_10bp"] = float((g0 - 10e-4 * avg_turn) * 100)
# borrow that drives Sharpe below gate at 10bp
from scipy.optimize import brentq


def sr_at(bw, c=10e-4):
    bb = pd.DataFrame({p: pair(PX[a], PX[s_], c, bw).reindex(R.index) for p, (a, s_) in PAIRS.items()}).mean(axis=1).dropna()
    return sharpe(bb) - gate(len(bb))


cst["borrow_where_sharpe_hits_gate_at_10bp"] = float(brentq(sr_at, 0.0, 0.05))
cst["borrow_where_sharpe_hits_gate_at_30bp"] = float(brentq(lambda x: sr_at(x, 30e-4), 0.0, 0.05))
# no short rebate: short proceeds earn nothing -> lose T-bill yield on short notional
nr = {}
for p, (a, s_) in PAIRS.items():
    nr[p] = pairs["base"][p] - rf.where(pairs["base"][p].notna())
bnr = pd.DataFrame(nr).mean(axis=1).dropna()
cst["no_short_rebate_base"] = {"sharpe": sharpe(bnr), "ann_mean": float(bnr.mean() * 252), "passes_sharpe_gate": bool(sharpe(bnr) >= gate(len(bnr))),
                               "avg_tbill_over_dev": float(rf.loc[DEV0:].mean() * 252)}


# spread estimates from daily OHLC (Corwin-Schultz 2012; Abdi-Ranaldo 2017), days with volume>0
def cs_spread(h):
    H, Lw = np.log(h["High"]), np.log(h["Low"])
    beta = (H - Lw) ** 2 + (H.shift(-1) - Lw.shift(-1)) ** 2
    gamma = (np.maximum(H, H.shift(-1)) - np.minimum(Lw, Lw.shift(-1))) ** 2
    k = 3 - 2 * np.sqrt(2)
    alpha = (np.sqrt(2 * beta) - np.sqrt(beta)) / k - np.sqrt(gamma / k)
    s = 2 * (np.exp(alpha) - 1) / (1 + np.exp(alpha))
    return s.clip(lower=0)


def ar_spread(h):
    c = np.log(h["Close"])
    eta = (np.log(h["High"]) + np.log(h["Low"])) / 2
    v = 4 * (c - eta) * (c - eta.shift(-1))
    return v


liq = {}
for t in SIX:
    h = yf_raw(t).loc[DEV0:DEV1]
    h = h[(h["Volume"] > 0) & (h["High"] > h["Low"])]
    cs = cs_spread(h)
    ar = ar_spread(h)
    liq[t] = {}
    for y, g in h.groupby(h.index.year):
        csy = cs.reindex(g.index).dropna()
        ary = ar.reindex(g.index).dropna()
        liq[t][int(y)] = {"cs_spread_bp_mean": round(float(csy.mean() * 1e4), 1),
                          "ar_spread_bp": round(float(np.sqrt(max(ary.mean(), 0)) * 1e4), 1),
                          "median_dollar_vol_$k": round(float((g["Volume"] * g["Close"]).median() / 1e3), 1)}
cst["spread_estimates_by_year"] = liq
res["6_costs"] = cst

# ======================= 7. null / placebo =======================
nul = {}
x = b.to_numpy()
n = len(x)
cx = x - x.mean()


def block_p(x, block, draws=5000, seed=20260923):
    x = np.asarray(x, float)
    n, cx = len(x), x - x.mean()
    rng = np.random.default_rng(seed)
    nb = -(-n // block)
    cnt = 0
    for _ in range(draws // 500):
        idx = (rng.integers(0, n, size=(500, nb))[:, :, None] + np.arange(block)).reshape(500, -1)[:, :n] % n
        cnt += np.sum(cx[idx].mean(axis=1) >= x.mean())
    return float((cnt + 1) / (draws + 1))


def stationary_p(x, mean_block, draws=3000, seed=7):
    x = np.asarray(x, float)
    n, cx = len(x), x - x.mean()
    rng = np.random.default_rng(seed)
    cnt = 0
    for _ in range(draws):
        idx = np.empty(n, int)
        i = rng.integers(n)
        for j in range(n):
            idx[j] = i
            i = rng.integers(n) if rng.random() < 1 / mean_block else (i + 1) % n
        cnt += cx[idx].mean() >= x.mean()
    return float((cnt + 1) / (draws + 1))


nul["daily_block_bootstrap_p"] = {blk: block_p(x, blk) for blk in (1, 5, 10, 21, 63, 126, 252)}
nul["daily_stationary_bootstrap_p_mean21"] = stationary_p(x, 21, draws=1000)
xm_ = bm.to_numpy()
nul["monthly_block_bootstrap_p"] = {blk: block_p(xm_, blk) for blk in (1, 3, 6, 12)}
nul["iid_t_daily"] = float(x.mean() / x.std(ddof=1) * np.sqrt(n))
nul["nw_t_daily_by_lags"] = {}
import statsmodels.api as sm
for L_ in (0, 5, 10, 21, 63):
    mm = sm.OLS(x, np.ones(n)).fit(cov_type="HAC", cov_kwds={"maxlags": L_}) if L_ else sm.OLS(x, np.ones(n)).fit()
    nul["nw_t_daily_by_lags"][L_] = float(mm.tvalues[0])
mm = sm.OLS(xm_, np.ones(len(xm_))).fit(cov_type="HAC", cov_kwds={"maxlags": 4})
nul["nw_t_monthly_lag4"] = float(mm.tvalues[0])
# sign-flip permutation on monthly book returns
rng = np.random.default_rng(1)
flips = rng.choice([-1, 1], size=(20000, len(xm_)))
nul["monthly_signflip_p"] = float((np.sum((flips * xm_).mean(axis=1) >= xm_.mean()) + 1) / 20001)
# stress series tests
xs = book["stress"].to_numpy()
nul["stress_daily_block21_p"] = block_p(xs, 21)
nul["stress_monthly_t"] = float(to_period(book["stress"].reindex(R.index)).dropna().iloc[1:].pipe(lambda s: s.mean() / s.std() * np.sqrt(len(s))))

# placebo: every ordered dollar-neutral pair among the six ETFs (same monthly-reset mechanics, base costs)
plac = {}
for a, s_ in itertools.permutations(SIX, 2):
    ps = pair(PX[a], PX[s_], 10e-4, .01).loc[DEV0:DEV1]
    plac[f"{a}-{s_}"] = {"sharpe": round(sharpe(ps), 3), "ann_mean": round(float(ps.mean() * 252), 4),
                         "first": str(ps.index[0].date()), "passes_gate": bool(sharpe(ps) >= gate(len(ps))),
                         "long_is_deferred": a in ("USL", "UNL", "DBC"), "short_is_front": s_ in ("USO", "UNG", "GSG")}
nul["placebo_all_ordered_pairs"] = plac
grp = {"registered (deferred-long vs same-commodity front-short)": ["USL-USO", "UNL-UNG", "DBC-GSG"],
       "front-long vs front-short, cross commodity": [f"{a}-{s_}" for a, s_ in itertools.permutations(["USO", "UNG", "GSG"], 2)],
       "deferred-long vs deferred-short, cross commodity": [f"{a}-{s_}" for a, s_ in itertools.permutations(["USL", "UNL", "DBC"], 2)],
       "deferred-long vs front-short, cross commodity": [f"{a}-{s_}" for a in ("USL", "UNL", "DBC") for s_ in ("USO", "UNG", "GSG")
                                                         if (a, s_) not in (("USL", "USO"), ("UNL", "UNG"), ("DBC", "GSG"))],
       "front-long vs deferred-short (reverse, any)": [f"{a}-{s_}" for a in ("USO", "UNG", "GSG") for s_ in ("USL", "UNL", "DBC")]}
nul["placebo_groups"] = {g: {"n": len(v), "n_pass_gate": sum(plac[k]["passes_gate"] for k in v),
                             "median_sharpe": float(np.median([plac[k]["sharpe"] for k in v]))} for g, v in grp.items()}
nul["placebo_note"] = ("cross-commodity spreads carry the difference in the two funds' roll drags plus cross-commodity spot; "
                       "they are not zero-premium placebos")
# same-beta pure short-spot strategy (roll-free) and same-beta short front basket
beta_spot = -0.168   # book monthly beta to its matched spot composite (b_beta.json)
comp_d = pd.concat([S[SPOT_FOR[p]].where(live[p]) for p in PAIRS], axis=1).mean(axis=1).reindex(b.index)
ss = beta_spot * comp_d
nul["same_beta_short_spot"] = {"sharpe": sharpe(ss), "ann_mean": float(ss.mean() * 252), "passes_sharpe_gate": bool(sharpe(ss) >= gate(len(ss))),
                               "block21_p": block_p(ss.to_numpy(), 21)}
fb = pd.concat([R[s_].where(live[p]) for p, (a, s_) in PAIRS.items()], axis=1).mean(axis=1).reindex(b.index)
for bt in (-0.25, -0.168):
    sf = bt * fb
    nul[f"short_front_matched_basket_beta{bt}"] = {"sharpe": sharpe(sf), "ann_mean": float(sf.mean() * 252),
                                                   "passes_sharpe_gate": bool(sharpe(sf) >= gate(len(sf)))}
# spot-hedged book (non-investable): book - beta*spot composite, daily
hb = b - beta_spot * comp_d
nul["book_minus_beta_spot_daily"] = {"sharpe": sharpe(hb), "ann_mean": float(hb.mean() * 252), "block21_p": block_p(hb.to_numpy(), 21)}
res["7_null"] = nul
dump("c_attacks.json", res)
print(json.dumps(res, indent=1, default=float)[:30000])
