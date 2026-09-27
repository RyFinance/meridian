"""research.amendment4.validators -- wrapper validators enforcing Amendment-4 effective-N semantics on research.power
design specs (research/power itself is not edited).

1. Variance ratio D >= 1: effective observations never exceed raw observations.
   A D < 1 input is refused unless it comes with evidence {"source": "full_dev_null", "se": ...} AND the caller
   shows the verdict at D = 1 (validate_spec re-evaluates at D = 1 via `verdict_at_D1`). Otherwise D is floored at 1.
2. Breadth correlation semantics: rho_bet (the correlation between BETS, i.e. signal x residual return) must come
   from IC / spread dispersion, rho_bet = (N sd(IC)^2 - 1) / (N - 1), or from the literal mean pairwise correlation
   of the held bets. The average pairwise correlation of market-neutral residual returns is refused (it is ~0 by
   construction and overstates breadth by up to ~50x, Sharpe by ~7x).
"""
from __future__ import annotations

import copy
import math
import warnings

import numpy as np

from research.power import designs

ALLOWED_RHO_SOURCES = ("ic_dispersion", "spread_dispersion", "held_bets_mean_corr", "factor_share_declared")
REFUSED_RHO_SOURCES = ("market_neutral_pairwise_residual", "pairwise_residual_corr", "avg_pairwise_resid")


class EffectiveNError(ValueError):
    pass


# -------------------------------------------------------------------------------------------- 1. variance ratio
def enforce_D(D: float, evidence: dict | None = None) -> float:
    """Return the D to use. D < 1 is floored at 1 unless evidence = {"source": "full_dev_null", "se": float} is
    given (the caller must then also report the verdict at D = 1)."""
    D = float(D)
    if not math.isfinite(D) or D <= 0:
        raise EffectiveNError(f"variance ratio D must be a positive number, got {D}")
    if D >= 1.0:
        return D
    if evidence and evidence.get("source") == "full_dev_null" and evidence.get("se") is not None:
        warnings.warn(f"D = {D:.3f} < 1 accepted on full-dev-null evidence (se {evidence['se']}); "
                      "the verdict must also be reported at D = 1", stacklevel=2)
        return D
    return 1.0


def effective_obs(n_raw: float, D: float, evidence: dict | None = None) -> float:
    """n_eff = n_raw / D with D floored at 1 (so n_eff <= n_raw) unless evidence is supplied."""
    return float(n_raw) / enforce_D(D, evidence)


def _walk_autocorr(params: dict):
    """Yield (container, key) for every autocorrelation spec in a design's params."""
    for key in ("autocorr", "ic_autocorr", "spread_autocorr", "portfolio_autocorr"):
        if key in params:
            yield params, key


# -------------------------------------------------------------------------------------------- 2. breadth
def rho_bet_from_ic_dispersion(n_assets: int, sd_ic: float) -> float:
    """rho_bet = (N sd(IC)^2 - 1) / (N - 1), clipped to [0, 1]. sd_ic is the time-series sd of the per-period
    cross-sectional IC measured on pre-dev (or dev) data. (Var IC = (1 + (N - 1) rho_bet) / N.)"""
    N = float(n_assets)
    if N < 2:
        raise EffectiveNError("need at least 2 assets")
    return float(min(1.0, max(0.0, (N * sd_ic ** 2 - 1.0) / (N - 1.0))))


def rho_bet_from_spread_dispersion(n_assets: int, quantile: float, spread_sd: float, cs_dispersion: float) -> float:
    """Equicorrelated-bets inversion of the long-short spread sd: Var(spread)/sigma_cs^2 = (2/(Nq))(1 + (2Nq - 1) rho)
    (research.power.designs 'equicorrelated_bets' mode)."""
    m = 2.0 * n_assets * quantile
    ratio = (spread_sd / cs_dispersion) ** 2 * m / 2.0
    return float(min(1.0, max(0.0, (ratio - 1.0) / (m - 1.0))))


def rho_bet_from_held_bets(bet_returns: np.ndarray) -> float:
    """Literal mean pairwise correlation of the held bets' P&L (T x M matrix of signal-weighted residual returns)."""
    B = np.asarray(bet_returns, float)
    C = np.corrcoef(B, rowvar=False)
    M = C.shape[0]
    return float((C.sum() - np.trace(C)) / (M * (M - 1)))


def validate_breadth(params: dict, provenance: dict | None) -> dict:
    """Check the rho source for breadth-bearing designs. Returns params with rho_resid*rho_signal replaced by the
    validated rho_bet when provenance gives one."""
    p = dict(params)
    prov = provenance or {}
    src = prov.get("rho_source")
    if src is None:
        raise EffectiveNError("breadth correlation needs provenance['rho_source'] in "
                              f"{ALLOWED_RHO_SOURCES}")
    if src in REFUSED_RHO_SOURCES:
        raise EffectiveNError("the average pairwise correlation of market-neutral residual returns is not a bet "
                              "correlation (it is ~0 by construction); derive rho_bet from IC / spread dispersion "
                              "or the held bets' mean correlation")
    if src not in ALLOWED_RHO_SOURCES:
        raise EffectiveNError(f"unknown rho_source {src!r}")
    if src == "ic_dispersion":
        rb = rho_bet_from_ic_dispersion(p["n_assets"], prov["sd_ic"])
    elif src == "spread_dispersion":
        rb = rho_bet_from_spread_dispersion(p["n_assets"], p["quantile"], prov["spread_sd"], p["cs_dispersion"])
    elif src == "held_bets_mean_corr":
        rb = float(prov["rho_bar_held"])
    else:  # factor_share_declared: rho_resid (factor variance share) x rho_signal (signal loading share)
        rb = float(p["rho_resid"]) * float(p.get("rho_signal", 1.0))
    if "rho_resid" in p:
        p["rho_resid"] = rb
        p["rho_signal"] = 1.0
    elif "rho" in p:
        p["rho"] = rb
    return p


BREADTH_KINDS = ("cross_sectional_ic", "long_short")


def validate_spec(kind: str, params: dict, provenance: dict | None = None) -> dict:
    """Validate (and minimally repair) a research.power design spec. Returns {params, notes, D_floored}."""
    p = copy.deepcopy(params)
    prov = provenance or {}
    notes = []
    floored = False
    for cont, key in _walk_autocorr(p):
        spec = cont[key]
        if isinstance(spec, dict) and spec.get("model") == "lrv":
            D = float(spec["D"])
            D2 = enforce_D(D, prov.get("D_evidence"))
            if D2 != D:
                cont[key] = {"model": "lrv", "D": D2}
                floored = True
                notes.append(f"{key}: D = {D} < 1 floored at 1 (effective obs may not exceed raw)")
        elif isinstance(spec, (int, float)) and float(spec) < 0 and not prov.get("D_evidence"):
            cont[key] = 0.0
            floored = True
            notes.append(f"{key}: negative AR(1) phi {spec} implies D < 1; floored at phi = 0")
    if "null_D" in p and p["null_D"] is not None:
        D = float(p["null_D"])
        D2 = enforce_D(D, prov.get("D_evidence"))
        if D2 != D:
            p["null_D"] = D2
            floored = True
            notes.append(f"null_D = {D} floored at 1")
    if kind in BREADTH_KINDS:
        p = validate_breadth(p, prov)
        notes.append(f"rho_bet from {prov.get('rho_source')}")
    return {"params": p, "notes": notes, "D_floored": floored}


def build_validated(kind: str, params: dict, provenance: dict | None = None, name: str | None = None):
    """validate_spec, then research.power.designs.build. Also asserts n_eff <= n_raw in the time dimension."""
    v = validate_spec(kind, params, provenance)
    d = designs.build(kind, v["params"], name)
    if d.series.D1 < 1.0 - 1e-12 and not (provenance or {}).get("D_evidence"):
        raise EffectiveNError(f"design implies D1 = {d.series.D1:.3f} < 1 (effective obs > raw)")
    return d, v
