"""G6 with the SSRN first-posting date (estimated) and validation power if the stress leg does not bind."""
import json
import numpy as np, pandas as pd
from scipy import stats
from research.audit_funding_stat.lockpanel import OUT
from research.certify import guards as G

b = pd.read_csv(OUT / "series_dev.csv", index_col=0, parse_dates=True)["base"]
res = {"G6_ssrn_4268371_est_2022-11-01": G.g6_post_publication(b, "2022-11-01"),
       "G6_bis_wp1087_2023-04-04": G.g6_post_publication(b, "2023-04-04")}
T = 1339 / 365; N = stats.norm; pw = {}
for k2 in (1.0, 1.57, 1.84):
    for drag_sr in (0.0, 0.85, 1.44):
        row = {}
        for S in (0.0, 0.3, 0.5, 0.7, 1.0, 1.5, 2.04):
            se = np.sqrt(k2 * (1 + S**2 / 730) / T)
            row[S] = float(N.sf((max(1.645 * se, 0.30, drag_sr) - S) / se))
        pw[f"k2={k2}|stress_threshold_SR={drag_sr}"] = row
res["validation_power_by_stress_threshold"] = pw
(OUT / "extras.json").write_text(json.dumps(res, indent=1, default=str))
print(json.dumps(res, indent=1, default=str))
