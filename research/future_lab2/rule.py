"""Simple, pre-declared sequential rules for forward evaluation, and fixed-sample power.

1. A classic Wald SPRT (Sequential Probability Ratio Test) on a monthly mean, with FIXED,
   pre-declared variance (estimated once from history, never re-estimated on forward data): tests
   H0: mu = mu0 ("kill", no edge) against H1: mu = mu1 ("confirm"), one look per month.
   `A = ln((1-beta)/alpha)`, `B = ln(beta/(1-alpha))` (Wald 1945); the cumulative log-likelihood
   ratio for iid Normal(mu, sigma^2) observations is linear in the cumulative sum, so this reduces
   to a running-sum test against two straight boundaries -- transparent enough to be a genuinely
   pre-registerable rule, unlike the Bayesian machinery in research/future_lab/forward.py (which
   this module also reuses directly, for momentum_gold_v1's frozen "spmo_gld" spec).
2. Fixed-sample (non-sequential) power / months-needed, `(z_alpha + z_beta)^2 * (sigma/effect)^2`,
   the same convention as research.future_lab.forward.years_needed but in months-of-monthly-data
   units directly (both candidates' natural look cadence is monthly).
"""
from __future__ import annotations

import numpy as np
from scipy.stats import norm

from research.future_lab import forward as F
from research.future_lab import paths as PA
from research.future_lab import risk as RK

Z_ALPHA = float(norm.ppf(0.95))
Z_BETA = float(norm.ppf(0.80))


# ---------------------------------------------------------------- SPRT
def sprt_bounds(alpha: float, beta: float) -> tuple[float, float]:
    return float(np.log((1 - beta) / alpha)), float(np.log(beta / (1 - alpha)))


def sprt_run(X: np.ndarray, mu0: float, mu1: float, sigma: float, alpha: float = 0.05,
            beta: float = 0.2) -> dict:
    """X: (n_paths, horizon) sequential monthly observations. Vectorised across paths; the only
    Python-level loop is inside research.future_lab.engines.stationary_indices, which built X.

    Returns boolean confirm/kill/undecided (n_paths,), 1-based month of decision (-1 if undecided
    by the end of X), and the full log-likelihood-ratio path for diagnostics/plotting.
    """
    A, B = sprt_bounds(alpha, beta)
    incr = (mu1 - mu0) / sigma ** 2 * (X - (mu0 + mu1) / 2.0)
    llr = np.cumsum(incr, axis=1)
    exit_mask = (llr >= A) | (llr <= B)
    has_exit = exit_mask.any(axis=1)
    H = X.shape[1]
    first = np.where(has_exit, exit_mask.argmax(axis=1), H - 1)
    at_first = llr[np.arange(X.shape[0]), first]
    confirm = has_exit & (at_first >= A)
    kill = has_exit & (at_first <= B)
    undecided = ~has_exit
    month = np.where(has_exit, first + 1, -1)
    return {"confirm": confirm, "kill": kill, "undecided": undecided, "month": month, "A": A, "B": B, "llr": llr}


def sprt_summary(res: dict, checkpoints=(12, 24, 36, 60, 120)) -> dict:
    dec_months = res["month"][res["month"] > 0]
    out = {
        "p_confirm": float(res["confirm"].mean()),
        "p_kill": float(res["kill"].mean()),
        "p_undecided_at_cap": float(res["undecided"].mean()),
        "median_months_to_decision": float(np.median(dec_months)) if len(dec_months) else None,
        "mean_months_to_decision": float(np.mean(dec_months)) if len(dec_months) else None,
        "p05_months_to_decision": float(np.quantile(dec_months, 0.05)) if len(dec_months) else None,
        "p95_months_to_decision": float(np.quantile(dec_months, 0.95)) if len(dec_months) else None,
    }
    by_cp = {}
    for cp in checkpoints:
        decided_by = (res["month"] > 0) & (res["month"] <= cp)
        by_cp[f"{cp}m"] = {
            "p_confirm_by": float((decided_by & res["confirm"]).mean()),
            "p_kill_by": float((decided_by & res["kill"]).mean()),
            "p_undecided_by": float(1.0 - decided_by.mean()),
        }
    out["by_checkpoint"] = by_cp
    return out


# ---------------------------------------------------------------- fixed-sample power
def fixed_sample_months_needed(effect: float, sigma: float, alpha: float = 0.05, power: float = 0.8) -> float:
    """Months of monthly data for a one-sided z-test of a mean `effect` (vs 0) at `alpha` to reach
    `power`, with known/pre-declared sigma. Same formula as research.future_lab.forward.years_needed,
    in raw observation-count units rather than annualised-Sharpe/years units."""
    if not np.isfinite(effect) or effect == 0:
        return float("inf")
    z = norm.ppf(1 - alpha) + norm.ppf(power)
    return float((z * sigma / abs(effect)) ** 2)


def fixed_sample_power(n: float, effect: float, sigma: float, alpha: float = 0.05) -> float:
    if n <= 0:
        return float(alpha)
    z = effect * np.sqrt(n) / sigma - norm.ppf(1 - alpha)
    return float(norm.cdf(z))


# ---------------------------------------------------------------- t-stat / Sharpe distributions
def dist_tstat_sharpe(X: np.ndarray, ann_factor: float, checkpoints=(12, 24, 36, 60, 120),
                      key_fn=None) -> dict:
    """X: (n_paths, horizon) observations of one series, in whatever unit `checkpoints` counts
    (months for TLT's window series; trading days for momentum_gold's daily series -- pass
    `key_fn` to label the output by month regardless of the underlying unit). At each checkpoint n
    (using the first n observations), the cross-path distribution of the one-sample t-stat of the
    mean and of the Sharpe-style ratio annualised at ann_factor observations/year."""
    key_fn = key_fn or (lambda cp: f"{cp}m")
    out = {}
    n_paths, H = X.shape
    for cp in checkpoints:
        if cp > H:
            continue
        x = X[:, :cp]
        mean = x.mean(axis=1)
        sd = x.std(axis=1, ddof=1)
        sd_safe = np.where(sd > 0, sd, np.nan)
        tstat = mean / sd_safe * np.sqrt(cp)
        sharpe = mean / sd_safe * np.sqrt(ann_factor)
        out[key_fn(cp)] = {"tstat": PA.q(tstat), "sharpe": PA.q(sharpe),
                           "p_tstat_gt_1645": float(np.nanmean(tstat > 1.645)),
                           "p_sharpe_gt_0": float(np.nanmean(sharpe > 0))}
    return out


# ---------------------------------------------------------------- frozen Bayesian rule (reuse)
def apply_frozen_rule(R: np.ndarray, C: np.ndarray, RF: np.ndarray, rule: dict, params: dict,
                      checkpoints=(12, 24, 36, 60)) -> dict:
    """Apply research.future_lab.forward's frozen Bayesian monitoring rule (as registered for
    "spmo_gld" in reports/future_lab/monitoring_rule_spec.json) to simulated daily paths."""
    ex, act = R - RF, R - C
    rdd_month = RK.running_dd_by_month(R, months=rule["max_months"], month_days=F.MONTH_DAYS)
    dec = F.rule_decisions(ex, act, rdd_month, rule, params)
    oc = F.summarize_oc(dec, checkpoints)
    fm = dec["first_month"]
    dec_months = fm[fm > 0]
    return {"operating_characteristics": oc,
            "median_months_to_decision": float(np.median(dec_months)) if len(dec_months) else None,
            "p_undecided_at_cap": float((fm == 0).mean())}
