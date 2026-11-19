"""Dev-only selection per name over 2 signs x 3 exits; report check for the dev-selected variant. Also by-year first-hour view."""
import pandas as pd, numpy as np
R = pd.read_csv("research/zb_itb/round5/oil_second_order/results_clean.csv")
R = R.drop_duplicates(subset=["signal", "name", "exit", "sign"])
N = R[R.role == "name"].copy()
pd.set_option("display.width", 250)
best = []
for (sig, nm), g in N.groupby(["signal", "name"]):
    g = g.sort_values("dev_t", ascending=False)
    top = g.iloc[0]
    # hypothesis-sign variant at 10:30 (the brief's primary spec) for reference
    hyp = g[(g.sign == "-d") & (g.exit == "10:30")].iloc[0]
    best.append(dict(signal=sig, group=top.group, name=nm, dev_pick=f"{top.sign}@{top.exit}", dev_mean=round(top.dev_mean, 1), dev_t=round(top.dev_t, 2),
                     chk_mean=round(top.chk_mean, 1), chk_t=round(top.chk_t, 2), chk_win=round(top.chk_win, 1),
                     spec_chk_mean=round(hyp.chk_mean, 1), spec_chk_t=round(hyp.chk_t, 2), cost=top.cost))
B = pd.DataFrame(best)
print(B.to_string(index=False))
print("name variants (2 signs x 3 exits x names):", len(N))
print("name variants with |chk t|>=2:", int((N.chk_t.abs() >= 2).sum()), "| with chk t>=2 and sign -d:", int(((N.chk_t >= 2) & (N.sign == "-d")).sum()))
print("check mean across dev-picked names (equal weight):", round(B.chk_mean.mean(), 2), "t-ish mean of chk_t:", round(B.chk_t.mean(), 2))
