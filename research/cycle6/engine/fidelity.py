"""Fidelity tiers (FRAMEWORK §5, A5 §C). Unassessable = FAIL with a reason, never repaired.

AQR-class tier: gross shadow vs benchmark on identical months: n, Pearson rho, OLS-with-intercept
beta = Cov(rep, ref)/Var(ref), TE = sqrt(12) sd(rep - ref), TE / sigma_ref (sigma_ref = sqrt(12) sd(ref)).
Scale convention: "none" (raw), or "ex_post_vol" (benchmark documented as scaled ex post to a constant vol:
the replica is scaled by target_vol_ann / its OWN full-sample vol -- a unit convention, never fitted to the ref).

Paper-stat tier: over the paper sample [start, end]: coverage = months present / paper months >= coverage_min;
|dmean| <= max(mean_abs, mean_rel |mean_paper|), |dvol| <= max(vol_abs, vol_rel vol_paper), |dSharpe| <= sharpe_abs.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

AQR_CLASS_THRESHOLDS = {"n_min": 60, "rho_min": 0.65, "beta_lo": 0.70, "beta_hi": 1.30, "te_ratio_max": 0.90}
PAPER_STAT_THRESHOLDS = {"coverage_min": 0.95, "mean_abs": 0.02, "mean_rel": 0.25, "vol_abs": 0.02,
                         "vol_rel": 0.20, "sharpe_abs": 0.30}


def aqr_tier(rep: pd.Series, ref: pd.Series, *, thresholds: dict | None = None, scale_convention: str = "none",
             target_vol_ann: float | None = None) -> dict:
    th = {**AQR_CLASS_THRESHOLDS, **(thresholds or {})}
    df = pd.concat([rep.rename("rep"), ref.rename("ref")], axis=1).dropna()
    out = {"tier": "aqr_class", "thresholds": th, "scale_convention": scale_convention, "n": int(len(df))}
    reasons = []
    if len(df) < 3:
        out.update({"pass": False, "reasons": ["unassessable: no common months"]})
        return out
    r = df["rep"].to_numpy()
    if scale_convention == "ex_post_vol":
        own = rep.dropna().std(ddof=1) * math.sqrt(12)
        r = r * (float(target_vol_ann) / own)
        out["scale_factor"] = float(target_vol_ann) / own
    elif scale_convention != "none":
        raise ValueError(f"unknown scale convention {scale_convention}")
    f = df["ref"].to_numpy()
    rho = float(np.corrcoef(r, f)[0, 1])
    beta = float(np.cov(r, f, ddof=1)[0, 1] / np.var(f, ddof=1))
    te = float(np.std(r - f, ddof=1) * math.sqrt(12))
    sref = float(np.std(f, ddof=1) * math.sqrt(12))
    out.update({"rho": rho, "beta": beta, "te_ann": te, "sigma_ref_ann": sref, "te_ratio": te / sref,
                "first": str(df.index[0]), "last": str(df.index[-1])})
    if len(df) < th["n_min"]:
        reasons.append(f"n {len(df)} < {th['n_min']} (unassessable)")
    if not rho >= th["rho_min"]:
        reasons.append(f"rho {rho:.3f} < {th['rho_min']}")
    if not th["beta_lo"] <= beta <= th["beta_hi"]:
        reasons.append(f"beta {beta:.3f} outside [{th['beta_lo']}, {th['beta_hi']}]")
    if not te / sref <= th["te_ratio_max"]:
        reasons.append(f"TE/sigma_ref {te / sref:.3f} > {th['te_ratio_max']}")
    out["pass"] = not reasons
    out["reasons"] = reasons
    return out


def paper_stat_tier(rep: pd.Series, paper: dict, *, thresholds: dict | None = None) -> dict:
    """paper = {start: 'YYYY-MM', end: 'YYYY-MM', n_months (optional; default calendar count),
    mean_ann, vol_ann, sharpe_ann} (decimals, paper annualisation x12 / sqrt(12)). A metric the paper does not
    publish (null), or whose band threshold is null, is skipped and reported; at least one metric must be
    compared; coverage always binds."""
    th = {**PAPER_STAT_THRESHOLDS, **(thresholds or {})}
    start, end = pd.Period(paper["start"], "M"), pd.Period(paper["end"], "M")
    x = rep.dropna()
    x = x[(x.index >= start) & (x.index <= end)]
    n_paper = int(paper.get("n_months") or len(pd.period_range(start, end, freq="M")))
    cov = len(x) / n_paper
    out = {"tier": "paper_stat", "thresholds": th, "n": int(len(x)), "n_paper": n_paper, "coverage": cov}
    reasons, compared, skipped = [], [], []
    if th.get("coverage_min") is None or cov < th["coverage_min"]:
        reasons.append(f"coverage {cov:.3f} < {th.get('coverage_min')} (unassessable)")
    if len(x) >= 3:
        m = float(x.mean() * 12)
        v = float(x.std(ddof=1) * math.sqrt(12))
        s = m / v if v > 0 else float("nan")
        out.update({"mean_ann": m, "vol_ann": v, "sharpe_ann": s})
        checks = {
            "mean_ann": (m, ("mean_abs", "mean_rel"),
                         lambda pv: max(th["mean_abs"], th["mean_rel"] * abs(pv))),
            "vol_ann": (v, ("vol_abs", "vol_rel"), lambda pv: max(th["vol_abs"], th["vol_rel"] * pv)),
            "sharpe_ann": (s, ("sharpe_abs",), lambda pv: th["sharpe_abs"]),
        }
        for key, (own, tkeys, band_fn) in checks.items():
            pv = paper.get(key)
            if pv is None:
                skipped.append({"metric": key, "reason": "not published (null in paper block)"})
                continue
            if any(th.get(k) is None for k in tkeys):
                skipped.append({"metric": key, "reason": "threshold null"})
                continue
            band = band_fn(pv)
            d = own - pv
            out[f"d_{key}"] = d
            out[f"band_{key}"] = band
            compared.append(key)
            if not abs(d) <= band:
                reasons.append(f"|d {key}| {abs(d):.4f} > {band:.4f}")
        if not compared:
            reasons.append("unassessable: no published metric to compare")
    else:
        reasons.append("unassessable: fewer than 3 months in paper sample")
    out["compared_metrics"] = compared
    out["skipped_metrics"] = skipped
    out["pass"] = not reasons
    out["reasons"] = reasons
    return out
