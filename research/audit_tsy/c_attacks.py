"""Attacks 4 (concentration), 5 (hidden exposures), 6 (decay), 7 (multiple testing), shift-null re-run.

  PYTHONPATH=. .venv/bin/python -m research.audit_tsy.c_attacks
"""
from __future__ import annotations

import json
import re
from math import exp, log

import numpy as np
import pandas as pd
import statsmodels.api as sm

from research.audit_tsy.common import OUT, WINDOWS, book, hold_mask, irx_rf, month_pos, sharpe, tr_from_raw, yf_raw

raw = yf_raw("TLT")
spy = yf_raw("SPY")
vix = yf_raw("VIX")["Close"]
tnx = yf_raw("TNX")["Close"]                      # CBOE 10y yield (x1), date level
irx = yf_raw("IRX")["Close"]
tlt_r = tr_from_raw(raw)
spy_r = tr_from_raw(spy)

# LSE US10Y (bonds dataset), date level, stitched from 6 pulls (the 2 first ones truncated)
obs = {}
for f in sorted(OUT.glob("lse_US10Y_raw_*.txt")):
    for d, v in re.findall(r'"date":"(\d{4}-\d{2}-\d{2})","value":([-0-9.]+)', f.read_text()):
        obs[pd.Timestamp(d)] = float(v)
us10 = pd.Series(obs).sort_index()

res: dict = {"us10y_lse_obs": int(len(us10)), "us10y_span": [str(us10.index.min().date()), str(us10.index.max().date())]}
all_idx = raw.index
rf_all = irx_rf(all_idx, irx)


def nw_t(x: pd.Series, lags: int = 3) -> float:
    x = x.dropna()
    m = sm.OLS(x.to_numpy(), np.ones(len(x))).fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    return float(m.tvalues[0])


def month_table(a: str, b: str) -> pd.DataFrame:
    idx = all_idx[(all_idx >= a) & (all_idx <= b)]
    r = tlt_r.reindex(idx).fillna(0); r.iloc[0] = 0
    rf = rf_all.reindex(idx).fillna(0)
    e = hold_mask(idx)
    m, act = book(r, rf, e, 2e-4)
    mg, actg = book(r, rf, e, 0.0)
    per = idx.to_period("M")
    mp = month_pos(idx)
    rows = []
    for p in sorted(set(per)):
        s = idx[per == p]
        d4, d3, dl = s[-4], s[-3], s[-1]
        pos = all_idx.get_loc(dl)
        nxt = all_idx[pos + 1] if pos + 1 < len(all_idx) else None
        win = s[-3:]
        i4 = all_idx.get_loc(d4)
        rows.append({
            "month": p, "d4": d4, "dl": dl,
            "win_ret": float(np.prod(1 + tlt_r.reindex(win)) - 1),
            "win_ex": float(np.prod(1 + tlt_r.reindex(win)) - 1 - rf.reindex(win).sum()),
            "s_n2": float(tlt_r[s[-3]]), "s_n1": float(tlt_r[s[-2]]), "s_n0": float(tlt_r[s[-1]]),
            "s_4th": float(tlt_r[s[-4]]),
            "next_first": float(tlt_r[nxt]) if nxt is not None else np.nan,
            "spy_win": float(np.prod(1 + spy_r.reindex(win)) - 1),
            "d10y_lse_bp": float((us10.get(dl, np.nan) - us10.get(d4, np.nan)) * 100),
            "d10y_tnx_bp": float((tnx.get(dl, np.nan) - tnx.get(d4, np.nan)) * 100),
            "tlt_trail21": float(np.prod(1 + tlt_r.iloc[i4 - 20:i4 + 1]) - 1),
            "vix_d4": float(vix.get(d4, np.nan)),
            "irx_chg126_bp": float((irx.asof(d4) - irx.asof(d4 - pd.Timedelta(days=182))) * 100),
            "active_month": float(act[per == p].sum()),
            "active_month_gross": float(actg[per == p].sum()),
            "qend": p.month in (3, 6, 9, 12),
        })
    return pd.DataFrame(rows).set_index("month"), act


def summ(x: pd.Series) -> dict:
    x = x.dropna()
    return {"n": int(len(x)), "mean_bp": float(x.mean() * 1e4), "t": float(x.mean() / x.std() * np.sqrt(len(x))) if len(x) > 2 else None}


tables = {}
for tag, (a, b) in WINDOWS.items():
    T, act = month_table(a, b)
    tables[tag] = (T, act)
    T.to_csv(OUT / f"c_months_{tag}.csv")
    out = {}
    # ---------- 4. concentration ----------
    am = T["active_month"]
    k = max(1, int(round(0.05 * len(am))))
    top = am.nlargest(k)
    out["active_total"] = float(am.sum())
    out["top5pct_months"] = {"k": k, "months": [str(i) for i in top.index], "share_of_total_active": float(top.sum() / am.sum())}
    rest = am.drop(top.index)
    out["active_sharpe_ex_top5pct_months_(monthly_ann)"] = float(rest.mean() / rest.std() * np.sqrt(12))
    out["active_sharpe_monthly_ann_all"] = float(am.mean() / am.std() * np.sqrt(12))
    out["active_monthly_hac_t"] = nw_t(am)
    out["share_positive_months"] = float((am > 0).mean())
    out["quarter_end"] = {"window_ex": summ(T.loc[T.qend, "win_ex"]), "active": summ(T.loc[T.qend, "active_month"])}
    out["other_months"] = {"window_ex": summ(T.loc[~T.qend, "win_ex"]), "active": summ(T.loc[~T.qend, "active_month"])}
    reg = np.where(T.irx_chg126_bp > 25, "hiking", np.where(T.irx_chg126_bp < -25, "cutting", "flat"))
    out["rate_regime_irx_6m_change"] = {g: {"window_ex": summ(T.loc[reg == g, "win_ex"]), "active": summ(T.loc[reg == g, "active_month"])}
                                        for g in ("hiking", "cutting", "flat")}
    # per-session decomposition (raw TR, not excess)
    out["per_session_mean_bp"] = {c: summ(T[c]) for c in ["s_4th", "s_n2", "s_n1", "s_n0", "next_first"]}
    # by year, and leave-one-year-out active Sharpe (daily)
    yr = act.groupby(act.index.year)
    out["active_by_year_pct"] = {int(y): round(float(g.sum() * 100), 2) for y, g in yr}
    out["leave_one_year_out_active_sharpe"] = {int(y): round(sharpe(act[act.index.year != y]), 3) for y in yr.groups}
    best2 = act.groupby(act.index.year).sum().nlargest(2).index
    out["drop_best_2_years"] = {"years": [int(y) for y in best2], "active_sharpe": sharpe(act[~act.index.year.isin(best2)])}
    # ---------- 5. hidden exposures ----------
    X = T[["spy_win", "d10y_lse_bp", "tlt_trail21", "vix_d4"]].copy()
    y = T["win_ex"] * 1e4
    regs = {}
    for name, cols in {"spy": ["spy_win"], "trail": ["tlt_trail21"], "vix": ["vix_d4"],
                       "spy_trail_vix": ["spy_win", "tlt_trail21", "vix_d4"],
                       "d10y_lse": ["d10y_lse_bp"], "all4": ["spy_win", "d10y_lse_bp", "tlt_trail21", "vix_d4"]}.items():
        d = pd.concat([y.rename("y"), X[cols]], axis=1).dropna()
        Z = d[cols].copy()
        if "vix_d4" in cols:
            Z["vix_d4"] = Z["vix_d4"] - Z["vix_d4"].mean()     # intercept = window return at average VIX
        if "tlt_trail21" in cols:
            Z["tlt_trail21"] = Z["tlt_trail21"] - Z["tlt_trail21"].mean()
        mdl = sm.OLS(d["y"], sm.add_constant(Z)).fit(cov_type="HC1")
        regs[name] = {"n": int(mdl.nobs), "r2": float(mdl.rsquared), "coef": {k: float(v) for k, v in mdl.params.items()},
                      "t": {k: float(v) for k, v in mdl.tvalues.items()}}
    out["regress_window_excess_bp"] = regs
    out["yield_change_in_window_bp"] = {"lse_us10y": summ(T["d10y_lse_bp"] / 1e4), "cboe_tnx": summ(T["d10y_tnx_bp"] / 1e4)}
    out["corr_lse_vs_tnx_window_dy"] = float(T[["d10y_lse_bp", "d10y_tnx_bp"]].corr().iloc[0, 1])
    down, up = T.spy_win < 0, T.spy_win >= 0
    out["tlt_window_when_spy_window_down"] = summ(T.loc[down, "win_ex"])
    out["tlt_window_when_spy_window_up"] = summ(T.loc[up, "win_ex"])
    hi_vix = T.vix_d4 > T.vix_d4.median()
    out["tlt_window_vix_above_median"] = summ(T.loc[hi_vix, "win_ex"])
    out["tlt_window_vix_below_median"] = summ(T.loc[~hi_vix, "win_ex"])
    res[tag] = out

# special episodes
Tv = tables["val"][0]
res["episodes"] = {
    "2020-03_window": {c: (float(Tv.loc[pd.Period("2020-03", "M"), c]) if c != "dl" else str(Tv.loc[pd.Period("2020-03", "M"), c].date()))
                       for c in ["win_ret", "spy_win", "d10y_lse_bp", "active_month", "vix_d4"]},
    "2022_windows_pct": {str(p): round(float(v * 100), 2) for p, v in Tv.loc["2022", "win_ret"].items()},
    "2022_active_months_pct": {str(p): round(float(v * 100), 2) for p, v in Tv.loc["2022", "active_month"].items()},
    "2026_windows_pct": {str(p): round(float(v * 100), 2) for p, v in Tv.loc["2026", "win_ret"].items()},
}

# ---------- 6. decay ----------
allT = pd.concat([tables["dev"][0], tables["val"][0]])
act_all = pd.concat([tables["dev"][1], tables["val"][1]])
blocks = {"2003-2008": ("2003", "2008"), "2009-2014": ("2009", "2014"), "2015-2020": ("2015", "2020"), "2021-2026": ("2021", "2026")}
res["decay"] = {k: {"window_ex": summ(allT.loc[a:b, "win_ex"]), "active_month": summ(allT.loc[a:b, "active_month"]),
                    "active_sharpe_daily": sharpe(act_all.loc[a:b])} for k, (a, b) in blocks.items()}
tt = np.arange(len(allT)) / 120.0      # decades
mdl = sm.OLS(allT["active_month"].to_numpy() * 1e4, sm.add_constant(tt)).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
res["decay"]["trend_active_bp_per_month_per_decade"] = {"coef": float(mdl.params[1]), "t": float(mdl.tvalues[1]),
                                                        "intercept_2003": float(mdl.params[0])}
mdl2 = sm.OLS(allT["win_ex"].to_numpy() * 1e4, sm.add_constant(tt)).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
res["decay"]["trend_window_ex_bp_per_decade"] = {"coef": float(mdl2.params[1]), "t": float(mdl2.tvalues[1])}
# post-publication split (see report for dates): pre/post 2014 already = dev/val.

# ---------- shift null, independent code (np.roll of the earning calendar, same as project semantics) ----------
rng = np.random.default_rng(12345)
for tag, (a, b) in WINDOWS.items():
    idx = all_idx[(all_idx >= a) & (all_idx <= b)]
    r = tlt_r.reindex(idx).fillna(0); r.iloc[0] = 0
    rf = rf_all.reindex(idx).fillna(0)
    e = hold_mask(idx)
    _, act = book(r, rf, e, 2e-4)
    obs_s = sharpe(act)
    sh = []
    for _ in range(2000):
        k = int(rng.integers(5, len(idx) - 5))
        ek = pd.Series(np.roll(e.to_numpy(), k), index=idx)
        sh.append(sharpe(book(r, rf, ek, 2e-4)[1]))
    sh = np.array(sh)
    res.setdefault("shift_null_independent", {})[tag] = {"obs": obs_s, "p": float((np.sum(sh >= obs_s) + 1) / (len(sh) + 1)),
                                                        "q95": float(np.quantile(sh, .95)), "q99": float(np.quantile(sh, .99))}

# ---------- 7. multiple testing ----------
def fisher(ps):
    x = -2 * sum(log(p) for p in ps)
    # chi2 with 4 df survival
    return exp(-x / 2) * (1 + x / 2)


pd_, pv_ = 6 / 1001, 5 / 1001
pf = fisher([pd_, pv_])
res["multiple_testing"] = {
    "fisher_dev_val": pf,
    "bonferroni": {str(n): min(1.0, pf * n) for n in (60, 111, 120, 150, 200, 300)},
    "breakeven_N_for_0.05": 0.05 / pf,
    "dev_p_alone_bonferroni_120": min(1.0, pd_ * 120),
    "val_p_alone_bonferroni_by_n_validations": {str(n): min(1.0, pv_ * n) for n in (5, 10, 12, 15)},
    "t_stat_equivalents": {"dev_active_sharpe_x_sqrtT": 0.664 * np.sqrt(11.99), "val": 0.692 * np.sqrt(11.63)},
}
(OUT / "c_attacks.json").write_text(json.dumps(res, indent=1, default=str))
print(json.dumps(res, indent=1, default=str))
