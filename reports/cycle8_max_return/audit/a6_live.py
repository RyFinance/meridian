"""Audit 6: simulated TREND sleeve / P6a vs live products, in CAD (adjusted-close month-end, snapshot view).

Live combos (monthly rebalanced, no trading costs, ETF fees are inside the prices):
  L1 = XEQT + 0.5 x (DBMF - US T-bill)            [TFSA-infeasible overlay approximation; DBMF CAD-translated]
  L2 = VT(CAD) + 0.5 x (DBMF - US T-bill)
  L3 = 0.5 XEQT + 0.5 RSST(CAD)                    [real one-ticket-ish implementation: 100% eq + 50% MF]
  L4 = XEQT + 0.5 x (KMLM - US T-bill)
Compared with the engine's P6a@1.0 monthly returns and a sim re-built on the same months:
  S1 = EQ_G_tfsa + 0.5 X_TREND (monthly-rebalanced, no costs) -- equals the engine P6a@1.0 up to costs.
Excess overlay in CAD terms: 0.5 * ((1+r_fund)(1+fxr) - (1+rf_usd)(1+fxr)) = 0.5 (r_fund - rf_usd)(1+fxr).
"""
import numpy as np
import pandas as pd
from audit_lib import SNAP, OUT, AUD, me, stats

M = pd.read_parquet(OUT / "sleeves_monthly.parquet")
IR = pd.read_parquet(OUT / "item_returns_monthly.parquet")
px = pd.read_parquet(SNAP / "proc/etf_monthly_adj.parquet")
px.index = me(px.index)
ret = px.pct_change()
# drop each fund's partial first month (inception month): first return is month after first price -> it is the
# first FULL month only if the first price is the inception month's end; skip one more month to be safe
first = px.apply(lambda s: s.first_valid_index())
for c in ret:
    ret.loc[:first[c] + pd.offsets.MonthEnd(1), c] = np.nan
fxr, rfu, cash = M["FXR"], M["RF_USD"], M["CASH"]
cad = lambda t: (1 + ret[t]) * (1 + fxr.reindex(ret.index)) - 1
xs = lambda t: (ret[t] - rfu.reindex(ret.index)) * (1 + fxr.reindex(ret.index))

S_trend = M["TREND"]
S_eq = M["EQ_G_tfsa"]
S1 = S_eq + 0.5 * M["X_TREND"]
P6 = IR["P6a@1.0"]
P1 = IR["P1u@1.0"]
series = {
    "SIM_TREND_cad": S_trend, "DBMF_cad": cad("DBMF"), "KMLM_cad": cad("KMLM"), "CTA_cad": cad("CTA"),
    "AQMIX_cad": cad("AQMIX"), "RSST_cad": cad("RSST"),
    "SIM_EQ_G_tfsa": S_eq, "XEQT": ret["XEQT.TO"], "VT_cad": cad("VT"),
    "SIM_P6a@1.0_engine": P6, "SIM_P1u@1.0_engine": P1, "SIM_eq+0.5xtrend_nocost": S1,
    "L1_XEQT+0.5(DBMF-rf)": ret["XEQT.TO"] + 0.5 * xs("DBMF"),
    "L2_VT+0.5(DBMF-rf)": cad("VT") + 0.5 * xs("DBMF"),
    "L3_0.5XEQT+0.5RSST": 0.5 * ret["XEQT.TO"] + 0.5 * cad("RSST"),
    "L4_XEQT+0.5(KMLM-rf)": ret["XEQT.TO"] + 0.5 * xs("KMLM"),
}
S = pd.DataFrame(series)
S.index.name = "date"
S.to_csv(AUD / "a6_live_series.csv")
pairs = [  # (live, sim, window start)
    ("DBMF_cad", "SIM_TREND_cad", None), ("KMLM_cad", "SIM_TREND_cad", None), ("CTA_cad", "SIM_TREND_cad", None),
    ("AQMIX_cad", "SIM_TREND_cad", None), ("XEQT", "SIM_EQ_G_tfsa", None), ("VT_cad", "SIM_EQ_G_tfsa", None),
    ("L1_XEQT+0.5(DBMF-rf)", "SIM_P6a@1.0_engine", None), ("L2_VT+0.5(DBMF-rf)", "SIM_P6a@1.0_engine", None),
    ("L2_VT+0.5(DBMF-rf)", "SIM_P6a@1.0_engine", "2019-06"),
    ("L3_0.5XEQT+0.5RSST", "SIM_P6a@1.0_engine", None), ("L4_XEQT+0.5(KMLM-rf)", "SIM_P6a@1.0_engine", None),
    ("L1_XEQT+0.5(DBMF-rf)", "SIM_P1u@1.0_engine", None), ("L3_0.5XEQT+0.5RSST", "SIM_P1u@1.0_engine", None),
    ("XEQT", "SIM_P1u@1.0_engine", None),
]
rows = []
for live, sim, a in pairs:
    d = S[[live, sim]].dropna()
    if a:
        d = d.loc[a:]
    sl, ss = stats(d[live], cash), stats(d[sim], cash)
    te = (d[live] - d[sim]).std() * np.sqrt(12)
    rows.append({"live": live, "sim": sim, "window": f"{sl['start']}..{sl['end']}", "months": sl["months"],
                 "live_cagr": sl["cagr"], "sim_cagr": ss["cagr"], "gap_pp": 100 * (sl["cagr"] - ss["cagr"]),
                 "live_vol": sl["vol"], "sim_vol": ss["vol"], "live_sharpe": sl["sharpe"], "sim_sharpe": ss["sharpe"],
                 "live_maxdd": sl["maxdd"], "sim_maxdd": ss["maxdd"], "corr": d.corr().iloc[0, 1], "te": te})
df = pd.DataFrame(rows)
df.to_csv(AUD / "a6_live_vs_sim.csv", index=False)
pd.set_option("display.width", 250)
print(df.round(4).to_string())
