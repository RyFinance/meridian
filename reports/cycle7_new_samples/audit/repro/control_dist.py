import sys, numpy as np, pandas as pd, json
sys.path.insert(0, "/Users/rytty/CCP/quant_v7/reports/cycle7_new_samples/audit/repro")
import repro_carry_fx_em as r
from pvalue import sharpe
daily, fr, us = r.load()
b = pd.read_csv("/Users/rytty/CCP/quant_v7/reports/cycle7_new_samples/runs/CARRY-FX__FX-EM/control.csv")
res = []
for s in range(20260926, 20260926 + 20):
    df, _, _ = r.run("norm", seed=s, daily=daily, fr=fr, us=us)
    res.append({"seed": s, "ctrl_mean_ann": df.control.mean()*12, "ctrl_vol_ann": df.control.std()*np.sqrt(12),
                "active_sharpe": sharpe(df.active)})
d = pd.DataFrame(res); d.to_csv("/Users/rytty/CCP/quant_v7/reports/cycle7_new_samples/audit/repro/control_seed_dist.csv", index=False)
print(d.describe().loc[["mean","std","min","max"]])
print("builder ctrl mean_ann", b.net.mean()*12, "vol_ann", b.net.std()*np.sqrt(12))
