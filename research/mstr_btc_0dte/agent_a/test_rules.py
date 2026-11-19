"""ONE-SHOT test of the two frozen rules on TEST (2026-07-16..2026-09-16). Do not iterate on this."""
import numpy as np
import pandas as pd

from common import DEV, TEST, H
from fvgap import summarize, trades

p = pd.read_parquet(H / "fv_panel.parquet")
RULES = {"R1_fade_0800_gt50": ("gap_fv", "08:00", 50, -1), "R2_follow_0800_gt100": ("gap_fv", "08:00", 100, +1)}
rows, allt = [], []
for per, (lo, hi) in {"DEV": DEV, "TEST": TEST}.items():
    q = p[(p.date >= lo) & (p.date <= hi)]
    for name, (gc, hm, thr, sgn) in RULES.items():
        for stress in (1.0, 2.0):
            x = trades(q, gc, hm, thr, stress=stress)
            if sgn > 0:  # follow = flip direction; costs unchanged
                cost = x["gross_bp"] - x["net_bp"]
                x["dir"] = -x["dir"]; x["gross_bp"] = -x["gross_bp"]
                x["net_bp"] = x["gross_bp"] - cost
            s = summarize(x)
            rows.append(dict(period=per, rule=name, stress=stress, days=q.date.nunique(), **s,
                             mean_filled_usd=x.filled_usd.mean() if len(x) else np.nan))
            if stress == 1.0:
                allt.append(x.assign(period=per, rule=name))
r = pd.DataFrame(rows)
pd.set_option("display.width", 250)
print(r.round(2).to_string(index=False))
t = pd.concat(allt)
t.to_csv(H / "rule_trades.csv", index=False)
print(t[t.period == "TEST"][["rule", "date", "gap_fv", "dir", "entry", "open", "gross_bp", "net_bp", "entry_vol", "fillable_usd"]]
      .round(2).to_string(index=False))
r.to_csv(H / "rule_results.csv", index=False)
