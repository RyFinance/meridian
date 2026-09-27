"""Power sensitivity for the five recommended candidates (analytic; no data). Varies the assumed IC.
Output: reports/xsec_scout/power_top5.csv
Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python research/xsec_scout/power_top5.py
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd
from research.xsec_scout.rank_mechanisms import M, power_row

OUT = Path(__file__).resolve().parents[2] / "reports/xsec_scout"
TOP5 = ["C1", "C2", "C3", "U1", "U2"]
rows = []
for m in M:
    if m["id"] not in TOP5:
        continue
    for mult in (0.5, 1.0, 1.5, 2.0):
        mm = dict(m, ic=m["ic"] * mult)
        rows.append({"id": m["id"], "ic": round(mm["ic"], 4), "ic_multiple_of_base": mult, **power_row(mm)})
df = pd.DataFrame(rows)
df.to_csv(OUT / "power_top5.csv", index=False)
pd.set_option("display.width", 250)
print(df[["id", "ic", "n_eff_linear", "periods_total", "gross_spread_ann", "cost_ann", "sharpe_gross", "sharpe_net",
          "t_net_full_history", "dev_years", "power_dev_gate_1.8", "power_dev_gate_2.4", "power_gross_ic_test_t1.8"]].to_string())
