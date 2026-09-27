"""research.amendment4.stress -- Section 3: operating characteristics of candidate validation stress-cost rules.

Setting: monthly Gaussian net series (unit vol), 12 + 12 years, k = 1; stress series = net - d / sqrt(12) (an extra
cost of d Sharpe units = plausible cost misestimation). Dev gate: Amendment 2 (1.8/sqrt(T), calibrated p <= 0.05,
stress mean > 0 -- unchanged). Validation: calibrated p <= 0.05, S_hat >= 0.30 and one stress rule
(research.amendment4.gating.stress_leg). Common random numbers across drags and rules.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from research.amendment4 import gating

RULES = ("R0_mean_pos", "R1_floor", "R2_half", "R3_signif", "R4_gate")
DRAGS = (0.0, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.7, 1.0, 1.5)
SHARPES = (0.0, 0.3, 0.5, 0.7)


def run(paths=20000, years=(12, 12), q=12, seed=20260928):
    nd, nv = years[0] * q, years[1] * q
    rows = []
    for S in SHARPES:
        rng = np.random.default_rng([seed, int(S * 100)])
        x = rng.standard_normal((paths, nd + nv)) + S / math.sqrt(q)
        dev, val = np.ascontiguousarray(x[:, :nd]), np.ascontiguousarray(x[:, nd:])
        # base validation legs (without stress): p <= 0.05 and S_hat >= 0.30
        base_val = gating.val_gate(val, val + 1.0, q, stress_rule="R0_mean_pos", seed=seed + 1)
        Sh_val = gating.sharpe(val, q)
        for d in DRAGS:
            c = d / math.sqrt(q)
            okd = gating.dev_gate(dev, dev - c, q, seed=seed + 2)
            idx = np.where(base_val)[0]
            for rule in RULES:
                okv = np.zeros(paths, bool)
                if len(idx):
                    okv[idx] = gating.stress_leg(val[idx], val[idx] - c, q, rule, seed=seed + 1,
                                                 base_sharpe=Sh_val[idx], path_idx=idx)
                pj = float((okd & okv).mean())
                rows.append({"true_net_sharpe": S, "stress_drag_sr": d, "true_stress_sharpe": S - d, "rule": rule,
                             "paths": paths, "dev_years": years[0], "val_years": years[1],
                             "P_dev": float(okd.mean()), "P_val_base": float(base_val.mean()),
                             "P_val": float(okv.mean()),
                             "P_stress_leg_given_base": float(okv[idx].mean()) if len(idx) else np.nan,
                             "P_joint": pj, "mc_se_joint": math.sqrt(max(pj * (1 - pj), 1e-12) / paths)})
            print(f"[stress] S={S} d={d} " + " ".join(f"{r['rule']}={r['P_joint']:.3f}" for r in rows[-len(RULES):]),
                  flush=True)
    return pd.DataFrame(rows)
