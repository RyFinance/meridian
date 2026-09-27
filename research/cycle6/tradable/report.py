"""Variant metrics: stats and A4 calibrated CIs (engine inference -> research.amendment4.ci.calibrated_ci), tracking
vs the paper BOOK, rounding error vs the unrounded path, cost-drag breakdown."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from research.cycle6.engine import inference

COST_COLS = ["cost_spread", "cost_commission", "cost_fx", "cost_roll", "withholding", "borrow"]


def window(s, start=None):
    return s if start is None else s[s.index >= pd.Period(start, "M")]


def series_block(frame: pd.DataFrame, post_cut: str, inf: dict) -> dict:
    out = {}
    for name, f in (("full", frame), ("post", window(frame, post_cut))):
        x = f["excess"].dropna()
        out[name] = {"excess": inference.basic_stats(x),
                     "total": inference.basic_stats(f["total"].dropna()),
                     "ci": inference.calibrated_ci(x, level=inf["ci_level"], B=inf["ci_B"], seed=inf["seed"]),
                     "cost_drag_ann": {c: float(f[c].mean() * 12) for c in COST_COLS + ["withholding_creditable"]},
                     "cash_interest_ann": float(f["cash_interest"].mean() * 12),
                     "mean_gross": float(f["gross"].mean()), "max_gross": float(f["gross"].max()),
                     "mean_cash_frac": float(f["cash_frac"].mean()), "min_cash_frac": float(f["cash_frac"].min()),
                     "turnover_ann": float(f["turnover"].mean() * 12),
                     "n_nan_months": int(f["excess"].isna().sum())}
    return out


def tracking(a: pd.Series, b: pd.Series, post_cut: str) -> dict:
    out = {}
    for name, cut in (("full", None), ("post", post_cut)):
        x = pd.concat([window(a, cut), window(b, cut)], axis=1, join="inner").dropna()
        if len(x) < 12:
            out[name] = {"n": len(x)}
            continue
        d = x.iloc[:, 0] - x.iloc[:, 1]
        out[name] = {"n": len(x), "first": str(x.index[0]), "last": str(x.index[-1]),
                     "corr": float(x.corr().iloc[0, 1]), "te_ann": float(d.std(ddof=1) * math.sqrt(12)),
                     "mean_diff_ann": float(d.mean() * 12)}
    return out


def rounding_block(rounded: pd.DataFrame, ideal: pd.DataFrame, post_cut: str) -> dict:
    out = {}
    for name, cut in (("full", None), ("post", post_cut)):
        r, i = window(rounded, cut), window(ideal, cut)
        tgt = r["n_target"].replace(0, np.nan)
        out[name] = {"mean_abs_weight_error": float(r["round_abs_err"].mean()),
                     "mean_frac_targets_unheld": float((r["n_zero_held"] / tgt).mean()),
                     "tracking_vs_unrounded": tracking(r["excess"], i["excess"], None)["full"]}
    return out


def drop_summary(drops: pd.DataFrame, X: pd.DataFrame, post_cut: str) -> dict:
    out = {}
    if drops.empty:
        return out
    d = drops.copy()
    d["month"] = pd.PeriodIndex(d["month"], freq="M")
    for name, cut in (("full", None), ("post", post_cut)):
        dd = d if cut is None else d[d["month"] >= pd.Period(cut, "M")]
        n = len(X.index) if cut is None else int((X.index >= pd.Period(cut, "M")).sum())
        out[name] = {i: float(g["weight"].abs().sum() / max(n, 1)) for i, g in dd.groupby("instrument")}
    return out
