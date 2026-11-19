"""Audit 2: rebuild sleeves from the frozen snapshot proc files (own code) and diff against sleeves_monthly.parquet.
Also sanity checks: FX direction, T-bill lag, hedge sign, gold splice, trend construction, P5 look-ahead."""
import numpy as np
import pandas as pd
from audit_lib import SNAP, OUT, AUD, me

P = SNAP / "proc"
rd = lambda f: (lambda x: x.set_axis(me(x.index)))(pd.read_parquet(P / f"{f}.parquet"))
eq, fx, rt, bd, gd, tr = (rd(f) for f in ["eq_monthly", "fx_monthly", "rates_monthly", "bond_monthly", "gold_monthly",
                                          "trend_monthly"])
M = pd.read_parquet(OUT / "sleeves_monthly.parquet")
ix = M.index
S = fx["USDCAD"].reindex(ix)
fxr = S.pct_change()                              # CAD per USD up -> USD asset gains in CAD
tb_prev = rt["tbill_cad"].shift(1).reindex(ix)    # yield at end of t-1 (annual, decimal)
cash = tb_prev / 12
rfu = rt["rf_usd_ret"].reindex(ix)
mr = (rt["policy_cad"].shift(1).reindex(ix) + 0.015) / 12
us = eq["US_usd"].reindex(ix)
ca = eq["CA_usd"].reindex(ix).fillna(us)
dx = eq["DXNA_usd"].reindex(ix).fillna(us)
em = eq["EM_usd"].reindex(ix).fillna(dx)
wts = dict(US=.45, CA=.25, DXNA=.25, EM=.05)
comp = pd.DataFrame(dict(US=us, CA=ca, DXNA=dx, EM=em))
eqc = sum(wts[k] * ((1 + comp[k]) * (1 + fxr) - 1) for k in wts)
wht = (0.45 * 0.15 * eq["US_dp"].reindex(ix).ffill() + 0.25 * 0.10 * 0.03 + 0.05 * 0.10 * 0.025) / 12
A = pd.DataFrame(index=ix)
A["EQ_G_margin"] = eqc - 0.002 / 12
A["EQ_G_tfsa"] = eqc - 0.002 / 12 - wht
A["BOND"] = 0.6 * bd["CA10_ret"].reindex(ix) + 0.4 * (bd["US10_ret"].reindex(ix) + cash - rfu) - 0.001 / 12
g = pd.concat([gd["gold_usd_wb_avg"].loc[:"2000-07-31"], gd["gold_usd_gcf_me"].loc["2000-08-31":]]).reindex(ix)
A["GOLD"] = (g / g.shift(1)) * (1 + fxr) - 1 - 0.0025 / 12
x = tr["tsmom_excess"].reindex(ix)
A["TREND"] = (1 + rfu + x - 0.02 / 12) * (1 + fxr) - 1
A["X_TREND"] = x - 0.02 / 12
A["CASH"] = cash
A["MRATE"] = mr
rows = []
for c in A:
    d = (A[c] - M[c]).dropna()
    rows.append({"col": c, "n": len(d), "first": f"{M[c].first_valid_index():%Y-%m}",
                 "last": f"{M[c].last_valid_index():%Y-%m}", "max_abs_diff": d.abs().max(),
                 "nan_mismatch": int((A[c].isna() != M[c].isna()).sum())})
chk = pd.DataFrame(rows).set_index("col")
print(chk.to_string())

# --- sanity checks
notes = {}
# FX direction: USDCAD 2026-08 ~1.386 CAD per USD (so it is CAD per USD, not USD per CAD)
notes["USDCAD_last"] = float(S.iloc[-1])
# 2008-10: CAD collapsed; USD asset in CAD should beat USD return
notes["fxr_2008_10"] = float(fxr.loc["2008-10"].iloc[0])
# hedged EQ_GH: +(rf_cad - rf_usd). Check sign with own formula on US leg
eqgh_us = us + cash - rfu - 0.001 / 12
hed = 0.45 * eqgh_us + 0.25 * ca * 0 + 0.25 * (dx + cash - rfu - 0.001 / 12) + 0.05 * (em + cash - rfu - 0.001 / 12) \
    + 0.25 * ((1 + ca) * (1 + fxr) - 1)
notes["EQ_GH_margin_maxdiff"] = float((hed - 0.002 / 12 - M["EQ_GH_margin"]).abs().max())
# gold splice month
notes["gold_2000_07_08_09"] = M["GOLD"].loc["2000-07":"2000-09"].round(4).tolist()
# vol of gold pre/post splice (monthly-average smoothing)
notes["gold_vol_1985_2000"] = float(M["GOLD"].loc["1985":"2000-07"].std() * np.sqrt(12))
notes["gold_vol_2000_2026"] = float(M["GOLD"].loc["2000-09":].std() * np.sqrt(12))
# P5 look-ahead: weight at t must equal inverse-vol of months t-36..t-1
w = pd.read_csv(OUT / "p5_weights.csv", index_col=0, parse_dates=True)
w.index = me(w.index)
cols = ["EQ_G_tfsa", "BOND", "GOLD", "TREND"]
t0 = pd.Timestamp("2008-10-31")
win = M[cols].loc[:t0].iloc[-37:-1]
inv = 1 / win.std()
notes["p5_w_2008_10_audit"] = (inv / inv.sum()).round(6).tolist()
notes["p5_w_2008_10_engine"] = w.loc[t0].round(6).tolist()
win2 = M[cols].loc[:t0].iloc[-36:]
inv2 = 1 / win2.std()
notes["p5_w_if_lookahead"] = (inv2 / inv2.sum()).round(6).tolist()
# trend: X_TREND and TREND consistency: TREND - (1+fxr)(rf+X) = fxr
d = M["TREND"] - ((1 + M["RF_USD"] + M["X_TREND"]) * (1 + M["FXR"]) - 1)
notes["trend_identity_maxdiff"] = float(d.abs().max())
# overlay FX translation ignored: size of the omitted term x*fxr
notes["X_TREND_fx_term_ann_mean_bp"] = float(1e4 * 12 * (M["X_TREND"] * M["FXR"]).mean())
for k, v in notes.items():
    print(k, v)
chk.to_csv(AUD / "a2_sleeve_rebuild.csv")
pd.Series({k: str(v) for k, v in notes.items()}).to_csv(AUD / "a2_sanity_notes.csv")
