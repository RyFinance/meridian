"""Joint power at true net Sharpe 0.7 under Amendment 3 (proposed val gate, floor 0.30) vs total years.
Synthetic only: no data. batch k=2, k_val=2 (Amendment-4 draft Q2), 50/50 dev/val split."""
import json
from research.power import plan_check as PC

def spec(ppy, ac, years, stress=0.15, skew=0.0, exk=0.0):
    return {"name": "sweep", "design": "timeseries",
            "params": {"periods_per_year": ppy, "autocorr": ac, "skew": skew, "exkurt": exk},
            "windows": {"dev_years": years / 2, "val_years": years / 2},
            "gates": {"batch_k": 2, "stress_drag_sr": stress, "dev": {"kind": "amendment2"},
                      "val": {"kind": "tstat", "alpha": "auto", "floor": 0.30}, "pav": {"k_val": 2, "floor": 0.30}}}

rows = []
for lab, ppy, ac in (("daily_iid", 252, 0.0), ("weekly_ar0.1", 52, 0.1), ("monthly_D1.5", 12, {"model": "lrv", "D": 1.5})):
    for Y in (6, 8, 10, 12, 16, 20, 24, 28, 32, 40):
        r = PC.run_spec(spec(ppy, ac, Y))
        p = {row["world"] if "world" in row else row.get("label"): row for row in r["power"]} if isinstance(r["power"], list) else r["power"]
        rows.append((lab, Y, r["joint_power_at_0.7"], r["verdict"], r["verdict_with_proposed_val_gate"]))
for x in rows: print(x)
