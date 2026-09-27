"""Extra descriptive diagnostics (no re-specification): sign test, trimmed mean, refunding months,
Good-Friday month-ends, M's own excess Sharpe by sub-period, placebo-position scale.
  PYTHONPATH=. .venv/bin/python -m research.audit_tsy.d_extra"""
import json
import numpy as np, pandas as pd
from scipy import stats
from research.audit_tsy.common import OUT, WINDOWS, book, hold_mask, irx_rf, sharpe, tr_from_raw, yf_raw
from research.forward import nyse
raw = yf_raw("TLT"); irx = yf_raw("IRX")["Close"]; tr = tr_from_raw(raw); rf_all = irx_rf(raw.index, irx)
res = {}
for tag in ("dev", "val"):
    T = pd.read_csv(OUT / f"c_months_{tag}.csv", index_col=0)
    am, wx = T["active_month"], T["win_ex"]
    n, k = len(am), int((am > 0).sum())
    kw = int((wx > 0).sum())
    res[tag] = {
        "sign_test_active_months": {"pos": k, "n": n, "p_one_sided": float(stats.binomtest(k, n, 0.5, alternative="greater").pvalue)},
        "sign_test_window_excess": {"pos": kw, "n": n, "p_one_sided": float(stats.binomtest(kw, n, 0.5, alternative="greater").pvalue)},
        "trimmed5_mean_active_bp": float(stats.trim_mean(am, 0.05) * 1e4),
        "median_active_bp": float(am.median() * 1e4),
        "wilcoxon_active_p_one_sided": float(stats.wilcoxon(am, alternative="greater").pvalue),
    }
    mon = pd.PeriodIndex(T.index, freq="M").month
    ref = np.isin(mon, [2, 5, 8, 11])
    res[tag]["refunding_months_FebMayAugNov_window_ex_bp"] = [float(wx[ref].mean() * 1e4), int(ref.sum())]
    res[tag]["other_months_window_ex_bp"] = [float(wx[~ref].mean() * 1e4), int((~ref).sum())]
    res[tag]["december_window_ex_bp"] = [float(wx[mon == 12].mean() * 1e4), int((mon == 12).sum())]
# Good Friday on the last weekday of a month (bond market open/early close, NYSE shut)
gf = []
for y in range(2003, 2027):
    g = nyse._easter(y) - pd.Timedelta(days=2)
    g = pd.Timestamp(g)
    last_wd = (g + pd.offsets.BMonthEnd(0))
    if g == last_wd:
        per = g.to_period("M")
        Tm = pd.read_csv(OUT / ("c_months_dev.csv" if y <= 2014 else "c_months_val.csv"), index_col=0)
        gf.append({"month": str(per), "window_ret_pct": round(float(Tm.loc[str(per), "win_ret"]) * 100, 2)})
res["good_friday_month_ends"] = gf
# M's own excess Sharpe (not active) by sub-period
idx_all = raw.index
for a, b in (("2003", "2008"), ("2009", "2014"), ("2015", "2020"), ("2021", "2026-08-31")):
    idx = idx_all[(idx_all >= a) & (idx_all <= (b if "-" in b else b + "-12-31"))]
    r = tr.reindex(idx).fillna(0); r.iloc[0] = 0
    m, act = book(r, rf_all.reindex(idx).fillna(0), hold_mask(idx), 2e-4)
    tlt_ex = (r - rf_all.reindex(idx).fillna(0))
    res.setdefault("subperiod", {})[f"{a}-{b[:4]}"] = {"M_excess_sharpe_base": sharpe(m), "M_ann_excess": float(m.mean() * 252),
                                                     "active_sharpe_base": sharpe(act), "TLT_ann_excess": float(tlt_ex.mean() * 252)}
# 2026 YTD and last 36 months
T = pd.read_csv(OUT / "c_months_val.csv", index_col=0)
res["last_36_months"] = {"window_ex_mean_bp": float(T["win_ex"].iloc[-36:].mean() * 1e4),
                         "t": float(T["win_ex"].iloc[-36:].mean() / T["win_ex"].iloc[-36:].std() * 6),
                         "active_mean_bp": float(T["active_month"].iloc[-36:].mean() * 1e4)}
res["2026_ytd_window_sum_pct"] = float(T.loc["2026-01":"2026-08", "win_ret"].sum() * 100)
(OUT / "d_extra.json").write_text(json.dumps(res, indent=1, default=str))
print(json.dumps(res, indent=1, default=str))
