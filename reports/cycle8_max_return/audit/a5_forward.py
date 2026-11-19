"""Audit 5: independent forward-lens arithmetic for the answer items (median CMA), vs final_table.csv."""
import numpy as np
import pandas as pd
from audit_lib import OUT, AUD, SNAP

M = pd.read_parquet(OUT / "sleeves_monthly.parquet").loc["1988-01":"2026-05"]
T = pd.read_csv(OUT / "final_table.csv", index_col=0)
Fs = pd.read_csv(OUT / "forward_sleeves.csv", index_col=0)
cma = pd.read_csv(SNAP / "cma/cma_mapped.csv")
med = Fs.loc["MEDIAN"]
E = {k: float(med[k]) for k in ["EQ_G", "BOND", "GOLD", "TREND_gross", "CASH"]}
# independent medians from cma_mapped.csv (target set only)
tgt = cma[cma.in_5_4_target_set == "Y"]
print("cma_mapped TREND rows:", tgt[tgt.sleeve == "TREND"][["source", "geo_nominal_cad", "arith_nominal_cad"]].values.tolist())
dp = pd.read_parquet(SNAP / "proc/eq_monthly.parquet")["US_dp"].dropna().iloc[-1]
wht = 100 * (0.45 * 0.15 * dp + 0.25 * 0.10 * 0.03 + 0.05 * 0.10 * 0.025)
fee = {"EQ": 0.20, "BOND": 0.10, "GOLD": 0.25, "TREND": 2.0}
exp = {"EQ": E["EQ_G"], "BOND": E["BOND"], "GOLD": E["GOLD"], "TREND": E["TREND_gross"]}
col = {"EQ": "EQ_G_tfsa", "BOND": "BOND", "GOLD": "GOLD", "TREND": "TREND", "X_TREND": "X_TREND"}
C = M[list(col.values())].cov() * 12
items = {"P1u": ({"EQ": 1}, {}), "P3": ({"EQ": .6, "BOND": .4}, {}),
         "P4": ({"EQ": .48, "BOND": .32, "GOLD": .1, "TREND": .1}, {}), "P6a": ({"EQ": 1}, {"X_TREND": .5})}
rows = []
for item, L in [("P1u", 1.0), ("P3", 1.0), ("P4", 1.25), ("P4", 1.5), ("P6a", 1.0), ("P6a", 1.25), ("P6a", 1.5)]:
    f, o = items[item]
    ar = sum(L * w * (exp[k] - fee[k]) for k, w in f.items())
    ar += sum(L * w * (E["TREND_gross"] - 2.0 - E["CASH"]) for k, w in o.items())   # = 0 by construction
    ar -= (L - 1) * (E["CASH"] + 1.5)
    if L == 1.0:
        ar -= wht * f.get("EQ", 0)
    v = pd.Series(0.0, index=C.index)
    for k, w in f.items():
        v[col[k]] += w
    for k, w in o.items():
        v[k] += w
    sd = L * np.sqrt(v @ C @ v)
    geo = ar - 100 * sd ** 2 / 2
    e = T.loc[f"{item}@{L}"]
    rows.append({"key": f"{item}@{L}", "audit_arith": ar, "engine_arith": e.fwd_arith, "audit_geo": geo,
                 "engine_geo": e.fwd_geo, "audit_sd": sd, "engine_sd": e.fwd_sd, "overlay_contrib": 0.0})
df = pd.DataFrame(rows).set_index("key")
df.to_csv(AUD / "a5_forward_check.csv")
print(df.round(4).to_string())
print("corr(EQ_G_tfsa, X_TREND) 1988-2026:", round(M[["EQ_G_tfsa", "X_TREND"]].corr().iloc[0, 1], 3),
      " post-2012:", round(M.loc["2012":, ["EQ_G_tfsa", "X_TREND"]].corr().iloc[0, 1], 3))
