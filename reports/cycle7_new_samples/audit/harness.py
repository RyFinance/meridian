"""Audit harness for CARRY-FX__FX-EM. SENSITIVITIES ONLY: every variant here is a labelled robustness report,
not a trial; none can create a pass. The base case must reproduce the ledgered active series exactly."""
from __future__ import annotations

import copy
import math
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from research.cycle7.runner import sample as smp, evaluate  # noqa: E402
from research.cycle6.engine import component, guards  # noqa: E402
from research.amendment4 import calib, ci as a4ci  # noqa: E402

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)
SAMPLE = REPO / "research/cycle7/samples/CARRY-FX__FX-EM.md"
KMVP_CUT = "2013-09"
CRASH = (0.2 / 12, -6.0)


@lru_cache(maxsize=1)
def base_inputs():
    s = smp.parse_sample(SAMPLE.read_text())
    spec = guards.parse_params((REPO / s["spec_path"]).read_text())
    params, _ = smp.map_params(spec, s)
    root = REPO / s["snapshot_root_rel"]
    ids = evaluate.filtered_universe(root, root / s["membership"], params, s["instrument_filter"])
    data = evaluate.apply_filter(component.load_inputs(params, root, root / s["membership"]), ids)
    cl = pd.read_csv(root / "eval/candidate_list.csv").set_index("market_id")
    return params, data, cl


def ndf_ids():
    _, _, cl = base_inputs()
    return sorted(cl.index[cl.ndf_only.astype(str) == "True"])


def run(drop=(), haircut_pp=0.0, haircut_ids=(), fx_bp=None, return_res=False):
    params, data, _ = base_inputs()
    p = copy.deepcopy(params)
    d = {k: (v.copy() if hasattr(v, "copy") else v) for k, v in data.items()}
    d["signal_inputs"] = {k: v.copy() for k, v in data["signal_inputs"].items()}
    keep = [c for c in d["daily"].columns if c not in set(drop)]
    d = evaluate.apply_filter(d, keep)
    if haircut_pp:
        fr = d["signal_inputs"]["fx_foreign_rate"]
        scale = 100.0 if fr.abs().stack().median() > 0.5 else 1.0   # percent vs decimal units
        for c in haircut_ids:
            if c in d["daily"].columns:
                d["daily"][c] = d["daily"][c] - haircut_pp / 100.0 / 260.0   # lower earned foreign rate
                fr[c] = fr[c] - haircut_pp * (scale / 100.0)                 # and lower signal carry
    if fx_bp is not None:
        p["costs"]["bp_per_side"]["FX"] = fx_bp
    res = component.compute_component(p, d)
    act = res["net"]["ret"] - res["control"]["net"]
    act.index = pd.PeriodIndex(act.index.astype(str), freq="M")
    return (act, res) if return_res else act


def sharpe(x):
    x = pd.Series(x).dropna()
    return float(x.mean() / x.std(ddof=1) * math.sqrt(12))


def pval(x, seed=20260939, bw=0.10, crash=True, B=9999):
    kw = dict(B=B, seed=seed, full=True, bandwidth_fraction=bw)
    if crash:
        kw["crash"] = CRASH
    return float(calib.calibrated_pvalues(np.asarray(pd.Series(x).dropna(), float)[None, :], **kw)["p"][0])


def cint(x, level=0.95, seed=20260939):
    r = a4ci.calibrated_ci(np.asarray(pd.Series(x).dropna(), float), level=level, seed=seed)["sharpe_ann"]
    return float(r[0]), float(r[1])


def summarize(label, x, start=None, end=None):
    x = pd.Series(x).dropna()
    if start:
        x = x.loc[start:]
    if end:
        x = x.loc[:end]
    lo90, hi90 = cint(x, 0.90); lo95, hi95 = cint(x, 0.95)
    return dict(variant=label, n=len(x), first=str(x.index.min()), sharpe=sharpe(x), mean_pct_yr=100 * x.mean() * 12,
                p_crash=pval(x), ci90=f"[{lo90:.2f}, {hi90:.2f}]", ci95=f"[{lo95:.2f}, {hi95:.2f}]",
                ci95_excl_zero=lo95 > 0)
