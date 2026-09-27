"""research.amendment4.size_study -- Section 2: size of the calibrated test (NCT) vs the old tests.

Outer paths: >= 20,000 per scenario (synthetic, zero true mean). Inner: NCT B = 159 null draws per path (B + 1 = 160
makes alpha = 0.05 and 0.0125 exact MC-test levels) with sequential stopping, AR bias correction R = 50 inner fits;
CBB B = 159. Tests:
  old_NW_t        literal Newey-West t, framework plug-in lags (research.power.simulate._auto_lags), normal cv
  old_CBB         mean-centred circular block bootstrap, block 21 (daily) or round(n^(1/3)) (monthly / weekly)
  A4prop_CBB      the proposal's Q3 block rule max(n^(1/3), 2(1+rho1)/(1-rho1)), rho1 estimated per path
  IM_batch10      Ibragimov-Mueller batch-means t, 10 batches, t_9 critical value
  NCT_short       null-calibrated t with the short NW plug-in bandwidth (no fixed-b floor)       [ablation]
  NCT             null-calibrated t, fixed-b bandwidth b = 0.10 (THE PROPOSED DEFAULT)
  NCT_b0.2        the same with b = 0.20                                                        [fallback]
  NCT_declared    NCT + declared crash layer (carry scenario only)
"""
from __future__ import annotations

import math
import time

import numpy as np
import pandas as pd

from research.amendment4 import calib, dgp
from research.power.core import Autocorr
from research.power.simulate import _auto_lags

ALPHAS = (0.05, 0.0125)


def _old_lags(name, n):
    g, kw, q, _, H, _ = dgp.SCENARIOS[name]
    if H > 1:
        ac = Autocorr("overlap", horizon=H)
    elif "phi" in kw:
        ac = Autocorr("ar1", phi=kw["phi"])
    else:
        ac = Autocorr("ar1", phi=0.0)
    return _auto_lags(ac, n)


def run(paths: int = 20000, seed: int = 20260926, scenarios=None) -> pd.DataFrame:
    rows = []
    names = scenarios or [s for s in dgp.SCENARIOS if s != "monthly_carry_crash_10y_declared"]
    for si, name in enumerate(names):
        g, kw, q, n, H, cr = dgp.SCENARIOS[name]
        rng = np.random.default_rng([seed, si])
        X = np.ascontiguousarray(dgp.generate(name, paths, rng))
        t0 = time.time()
        res = {}
        L_old = _old_lags(name, n)
        for a in ALPHAS:
            res[("old_NW_t", a)] = calib.old_nw_t_reject(X, a, L_old).mean()
        b_old = 21 if q >= 252 else int(round(n ** (1 / 3)))
        p = calib.cbb_pvalues(X, b_old, seed=seed + 11)
        for a in ALPHAS:
            res[("old_CBB", a)] = np.mean(p <= a)
        p = calib.cbb_pvalues(X, calib.a4q3_blocks(X), seed=seed + 12)
        for a in ALPHAS:
            res[("A4prop_CBB", a)] = np.mean(p <= a)
        for a in ALPHAS:
            res[("IM_batch10", a)] = calib.batch_means_t_reject(X, a).mean()
        variants = [("NCT_short", dict(L=calib.stat_lags(n, H, 0.0))), ("NCT", {}),
                    ("NCT_b0.2", dict(bandwidth_fraction=0.2))]
        if "crash" in name:
            variants.append(("NCT_declared", dict(crash=(kw["p"], kw["J"]))))
        for lab, extra in variants:
            r = calib.calibrated_pvalues(X, overlap=H, seed=seed + 100 + si, **extra)
            for a in ALPHAS:
                res[(lab, a)] = np.mean(r["p"] <= a)
            res[(lab, "L")] = r["L"]
        el = time.time() - t0
        tests = sorted({k[0] for k in res}, key=lambda s: list(dict.fromkeys(k[0] for k in res)).index(s))
        for tst in tests:
            row = {"scenario": name, "periods_per_year": q, "n": n, "paths": paths, "test": tst,
                   "bandwidth_L": res.get((tst, "L"), L_old if tst == "old_NW_t" else None)}
            for a in ALPHAS:
                s = float(res[(tst, a)])
                row[f"size_{a}"] = s
                row[f"ratio_{a}"] = s / a
                row[f"mc_se_{a}"] = math.sqrt(a * (1 - a) / paths)
            row["within_1.5x_both"] = bool(row["ratio_0.05"] <= 1.5 and row["ratio_0.0125"] <= 1.5)
            row["seconds_scenario"] = el
            rows.append(row)
        print(f"[size] {name} {el:.1f}s", flush=True)
    return pd.DataFrame(rows)
