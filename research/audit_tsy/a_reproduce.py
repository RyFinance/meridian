"""Attack 1a / 2 / 8: independent re-implementation, dividend handling and calendar checks.

  PYTHONPATH=. .venv/bin/python -m research.audit_tsy.a_reproduce
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from research.audit_tsy.common import OUT, ROOT, WINDOWS, book, hold_mask, irx_rf, month_pos, sharpe, tr_from_raw, yf_raw
from research.forward import nyse

res: dict = {}

# ---------------- sources -----------------
proj = pd.read_parquet(ROOT / "data/multiasset/etf/TLT.parquet")
proj = proj.set_index(pd.to_datetime(proj["date"]))["close"].sort_index()
irx_proj = pd.read_parquet(ROOT / "data/multiasset/rates/IRX.parquet")
irx_proj = irx_proj.set_index(pd.to_datetime(irx_proj["date"]))["close"].sort_index()
raw = yf_raw("TLT")
irx_yf = yf_raw("IRX")["Close"]
tr = tr_from_raw(raw)
adj_now = raw["Adj Close"].pct_change()           # Yahoo's own adjusted close, downloaded today

# ---------------- 8. data integrity ----------------
integ = {}
integ["project_duplicates"] = int(proj.index.duplicated().sum())
integ["project_rows"] = int(len(proj))
integ["project_last_row"] = str(proj.index[-1].date())
lo, hi = proj.index[0].date(), pd.Timestamp("2026-08-31").date()
cal = [d for d in nyse.sessions_between(lo, hi)]
cal_idx = pd.DatetimeIndex(pd.to_datetime(cal))
pset = set(proj.loc[:"2026-08-31"].index)
missing = [str(d.date()) for d in cal_idx if d not in pset]
extra = [str(d.date()) for d in proj.loc[:"2026-08-31"].index if d not in set(cal_idx)]
integ["rule_calendar_sessions"] = len(cal_idx)
integ["missing_vs_rule_calendar"] = missing
integ["extra_vs_rule_calendar(unscheduled closures expected)"] = extra
# which month-end windows involve an unscheduled closure or a holiday inside the last 5 weekdays
mp = month_pos(proj.index)
# sessions per month distribution
integ["sessions_per_month_min_max"] = [int(mp["n"].min()), int(mp["n"].max())]
integ["months_with_<18_sessions"] = sorted({str(p) for p, n in zip(mp["per"], mp["n"]) if n < 18})
# yfinance today vs project dates
ydates = set(raw.loc["2003-01-02":"2026-08-31"].index)
integ["yf_today_minus_project_dates"] = sorted(str(d.date()) for d in ydates - pset)
integ["project_minus_yf_today_dates"] = sorted(str(d.date()) for d in pset - ydates)
# stale / zero-return days in project series at month-ends
pr = proj.pct_change()
held = hold_mask(proj.index)
integ["zero_return_days_project_total"] = int((pr == 0).sum())
integ["zero_return_days_on_window_sessions"] = [str(d.date()) for d in pr.index[(pr == 0) & held]]
res["integrity"] = integ

# ---------------- 1a. independent reproduction ----------------
repro = {}
for tag, (a, b) in WINDOWS.items():
    out = {}
    # (i) project close + project rf, my code
    px = proj.loc[a:b]
    r = px.pct_change().fillna(0.0)
    rf = irx_rf(proj.index, irx_proj).reindex(px.index).fillna(0)
    earn = hold_mask(px.index)
    m, act = book(r, rf, earn, 2e-4)
    pd_daily = pd.read_csv(ROOT / f"reports/tsy_month_end/{'dev' if tag == 'dev' else 'validation'}_daily.csv",
                           index_col=0, parse_dates=True)
    out["myimpl_project_prices"] = {"active_sharpe_base": sharpe(act), "active_ann": float(act.mean() * 252),
                                    "max_abs_diff_vs_project_daily_active": float((act - pd_daily["active"]).abs().max())}
    # (ii) yfinance raw close + dividends on ex-date, yfinance IRX (fully independent inputs)
    idx = raw.loc[a:b].index
    r2 = tr.reindex(idx).fillna(0.0)
    r2.iloc[0] = 0.0
    rf2 = irx_rf(raw.index, irx_yf).reindex(idx).fillna(0)
    earn2 = hold_mask(idx)
    for k, cst in (("gross", 0.0), ("base", 2e-4), ("stress", 6e-4)):
        m2, act2 = book(r2, rf2, earn2, cst)
        out[f"yf_raw_plus_div_{k}"] = {"active_sharpe": sharpe(act2), "active_ann": float(act2.mean() * 252),
                                       "M_sharpe": sharpe(m2)}
    # (iii) yfinance Adj Close as downloaded today
    r3 = adj_now.reindex(idx).fillna(0.0); r3.iloc[0] = 0.0
    m3, act3 = book(r3, rf2, earn2, 2e-4)
    out["yf_adjclose_today_base"] = {"active_sharpe": sharpe(act3), "active_ann": float(act3.mean() * 252)}
    # per-window (monthly) comparison of 3-session window return, project vs raw+div
    per = idx.to_period("M")
    wp = ((1 + r.reindex(idx).fillna(0)).where(earn, 1.0)).groupby(per).prod() - 1
    wy = ((1 + r2).where(earn2, 1.0)).groupby(per).prod() - 1
    diff = (wp - wy) * 1e4
    out["window_return_diff_bp_project_minus_rawdiv"] = {"mean": float(diff.mean()), "max_abs": float(diff.abs().max()),
                                                          "n_gt_1bp": int((diff.abs() > 1).sum()),
                                                          "worst": {str(k): round(float(v), 2) for k, v in diff.abs().nlargest(5).items()}}
    out["gross_window_bp_per_month_rawdiv"] = float(wy.mean() * 1e4)
    repro[tag] = out
res["reproduction"] = repro

# ---------------- 2. dividends / ex-dates ----------------
dv = raw["Dividends"]
exd = dv[dv > 0].loc["2003-01-01":"2026-08-31"]
mpr = month_pos(raw.index)
exinfo = mpr.reindex(exd.index)
ex_in_window = exinfo[exinfo["from_end"] <= 2]
divres = {"n_exdates": int(len(exd)),
          "exdate_session_position_counts(k=1 first session)": exinfo["k"].value_counts().sort_index().astype(int).to_dict(),
          "exdates_inside_earning_window": [str(d.date()) for d in ex_in_window.index],
          "exdate_is_next_session_after_window_share": float((exinfo["k"] == 1).mean())}
# adjustment consistency: project adjusted return minus raw+div TR, on ex-dates, day before, others
pr_all = proj.pct_change()
d = (pr_all - tr.reindex(pr_all.index)) * 1e4
isex = pd.Series(pr_all.index.isin(exd.index), index=pr_all.index)
before = isex.shift(-1, fill_value=False)
after = isex.shift(1, fill_value=False)
divres["adj_minus_rawdiv_bp"] = {
    "on_exdates": {"mean": float(d[isex].mean()), "max_abs": float(d[isex].abs().max())},
    "session_before_exdate": {"mean": float(d[before].mean()), "max_abs": float(d[before].abs().max())},
    "session_after_exdate": {"mean": float(d[after].mean()), "max_abs": float(d[after].abs().max())},
    "all_other": {"mean": float(d[~(isex | before | after)].mean()), "max_abs": float(d[~(isex | before | after)].abs().max()),
                  "n_gt_2bp": int((d[~(isex | before | after)].abs() > 2).sum())},
}
big = d[d.abs() > 2].dropna()
divres["days_adj_vs_rawdiv_gt_2bp"] = {str(k.date()): round(float(v), 1) for k, v in big.items()}
# raw price-only window return (dividend ignored entirely): does the effect exist in raw prices?
for tag, (a, b) in WINDOWS.items():
    idx = raw.loc[a:b].index
    rp = raw["Close"].pct_change().reindex(idx).fillna(0)
    rf2 = irx_rf(raw.index, irx_yf).reindex(idx).fillna(0)
    e = hold_mask(idx)
    _, act_p = book(rp, rf2, e, 2e-4)
    # window returns with ex-dates excluded: zero out any earning session that is an ex-date
    r2 = tr.reindex(idx).fillna(0)
    e_noex = e & ~pd.Series(idx.isin(exd.index), index=idx)
    _, act_noex = book(r2, rf2, e_noex, 2e-4)
    # months whose NEXT session is an ex-date vs not
    per = idx.to_period("M")
    wy = ((1 + r2).where(e, 1.0)).groupby(per).prod() - 1
    nxt_ex = {}
    mp2 = month_pos(raw.index)
    firsts = mp2[mp2["k"] == 1].index
    for p in wy.index:
        nf = firsts[firsts > p.end_time]
        nxt_ex[p] = bool(len(nf) and nf[0] in exd.index)
    ne = pd.Series(nxt_ex)
    # return on the ex-date session itself (first session of next month) vs other first sessions
    divres[f"{tag}_price_only_active_sharpe_base"] = sharpe(act_p)
    divres[f"{tag}_exdates_removed_from_window_active_sharpe_base"] = sharpe(act_noex)
    divres[f"{tag}_window_bp_next_session_is_exdate"] = [float(wy[ne].mean() * 1e4), int(ne.sum())]
    divres[f"{tag}_window_bp_next_session_not_exdate"] = [float(wy[~ne].mean() * 1e4), int((~ne).sum())]
res["dividends"] = divres

(OUT / "a_reproduce.json").write_text(json.dumps(res, indent=1, default=str))
print(json.dumps(res, indent=1, default=str)[:6000])
