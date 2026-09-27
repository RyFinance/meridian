"""Section 4: forward-test design. Extends reports/forward_power/REPORT.md (same convention: one-sided
5% test, 80% power) with (i) candidate-specific Sharpe estimates, (ii) a resampling-based standard-
error inflation factor k in place of the iid SE = 1/sqrt(years), (iii) a paired test against each
candidate's control using the strategy-control correlation, and (iv) a pre-specifiable sequential
monitoring rule with simulated operating characteristics, emitted as a frozen JSON spec together
with a mechanical evaluator (`evaluate_forward`).
"""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd
from scipy.stats import norm

Z_ALPHA = float(norm.ppf(0.95))
Z_BETA = float(norm.ppf(0.80))
MONTH_DAYS = 21
MAX_MONTHS = 60


# ---------------------------------------------------------------- fixed-sample power
def years_needed(effect: float, k: float = 1.0, alpha: float = 0.05, power: float = 0.80) -> float:
    """Years of daily data for a one-sided z-test of an annualised Sharpe (or information ratio)
    `effect` to reach `power`, when SE(annualised estimate) = k / sqrt(years). k = 1 is the iid case
    of reports/forward_power (Sharpe 1 -> 6.2 years; 0.5 -> 24.7)."""
    if not np.isfinite(effect) or effect <= 0:
        return float("inf")
    z = norm.ppf(1 - alpha) + norm.ppf(power)
    return float((k * z / effect) ** 2)


def power_at(years: float, effect: float, k: float = 1.0, alpha: float = 0.05) -> float:
    return float(norm.cdf(effect * np.sqrt(years) / k - norm.ppf(1 - alpha)))


def assurance(years: float, mean: float, sd: float, k: float = 1.0, alpha: float = 0.05) -> float:
    """Expected power when the true effect is uncertain, effect ~ N(mean, sd^2): the probability the
    forward test ends significant. Closed form for a normal effect."""
    se = k / np.sqrt(years)
    return float(norm.cdf((mean - norm.ppf(1 - alpha) * se) / np.sqrt(se ** 2 + sd ** 2)))


def paired_ir(mu_s: float, mu_c: float, sd_s: float, sd_c: float, rho: float) -> float:
    """Annualised information ratio of strategy minus control from annualised means/vols and the
    daily correlation: (mu_s - mu_c) / sqrt(sd_s^2 + sd_c^2 - 2 rho sd_s sd_c)."""
    te = np.sqrt(max(sd_s ** 2 + sd_c ** 2 - 2 * rho * sd_s * sd_c, 1e-18))
    return float((mu_s - mu_c) / te)


# ---------------------------------------------------------------- posterior
def posterior(est: np.ndarray, years: np.ndarray, prior_mean: float, prior_sd: float, k: float):
    """Normal-normal update for an annualised Sharpe/IR: est ~ N(theta, k^2 / years)."""
    prec = 1.0 / prior_sd ** 2 + years / k ** 2
    mean = (prior_mean / prior_sd ** 2 + est * years / k ** 2) / prec
    return mean, 1.0 / np.sqrt(prec)


def prob_above(mean, sd, c: float):
    return 1.0 - norm.cdf((c - mean) / sd)


# ---------------------------------------------------------------- rule
def sceptical_sd(estimate: float) -> float:
    """Sceptical prior N(0, sd^2) with 5% prior probability above the backtest estimate."""
    return max(abs(estimate), 0.05) / Z_ALPHA


DEFAULT_RULE = {
    "look_every_trading_days": MONTH_DAYS,
    "max_months": MAX_MONTHS,
    "kill_sharpe": {"threshold": 0.30, "prob_below": 0.10, "min_months": 6},
    "kill_drawdown": {"percentile": 0.99},
    "revert_to_control": {"threshold": 0.0, "prob_below": 0.10, "min_months": 24},
    "promote": {"min_months": 24, "p_sharpe_gt_0": 0.95, "p_ir_gt_0": 0.90},
}


def rule_decisions(ex: np.ndarray, act: np.ndarray, rdd_month: np.ndarray, rule: dict, params: dict) -> dict:
    """Apply the monitoring rule to many forward paths at once.

    ex: (N, H) daily excess returns of the candidate; act: (N, H) daily candidate - control returns
    (None when there is no control); rdd_month: (N, M) running max drawdown at each month-end.
    Returns first-decision month and code per path: 0 continue, 1 kill (Sharpe), 2 kill (drawdown),
    3 revert to control, 4 promote. Decisions are terminal; checked at each look in the order
    drawdown -> Sharpe kill -> revert -> promote.

    Two priors, as in Bayesian trial monitoring (Spiegelhalter, Freedman & Parmar 1994): futility
    (kill / revert) uses the haircut-backtest prior, so a candidate is not killed on noise while the
    backtest still supports it; promotion uses a sceptical prior centred at zero (5% prior mass
    above the backtest estimate), so only forward data can carry a promotion.
    """
    N, H = ex.shape
    M = min(rule["max_months"], H // MONTH_DAYS, rdd_month.shape[1])
    looks = np.arange(1, M + 1) * MONTH_DAYS - 1
    cs, cs2 = np.cumsum(ex, axis=1)[:, looks], np.cumsum(ex ** 2, axis=1)[:, looks]
    n = looks + 1.0
    mean = cs / n
    var = np.maximum(cs2 / n - mean ** 2, 1e-18) * n / (n - 1)
    yrs = n / 252.0
    sr = mean / np.sqrt(var) * np.sqrt(252)
    pm, ps = posterior(sr, yrs[None], params["prior_sharpe_mean"], params["prior_sharpe_sd"], params["k_sharpe"])
    p_sr_gt_kill = prob_above(pm, ps, rule["kill_sharpe"]["threshold"])
    sm, ss = posterior(sr, yrs[None], 0.0, params["skeptical_sharpe_sd"], params["k_sharpe"])
    p_sr_gt_0 = prob_above(sm, ss, 0.0)
    if act is not None:
        ca, ca2 = np.cumsum(act, axis=1)[:, looks], np.cumsum(act ** 2, axis=1)[:, looks]
        am = ca / n
        av = np.maximum(ca2 / n - am ** 2, 1e-18) * n / (n - 1)
        ir = am / np.sqrt(av) * np.sqrt(252)
        qm, qs = posterior(ir, yrs[None], params["prior_ir_mean"], params["prior_ir_sd"], params["k_ir"])
        p_ir_gt = prob_above(qm, qs, rule["revert_to_control"]["threshold"])
        tm, ts = posterior(ir, yrs[None], 0.0, params["skeptical_ir_sd"], params["k_ir"])
        p_ir_gt_0 = prob_above(tm, ts, 0.0)
    else:
        p_ir_gt = np.ones_like(pm)
        p_ir_gt_0 = np.ones_like(pm)
    months = np.arange(1, M + 1)[None]
    bound = np.asarray(params["dd_boundary"])[:M][None]
    code = np.zeros((N, M), dtype=np.int8)
    promote = ((months >= rule["promote"]["min_months"]) & (p_sr_gt_0 >= rule["promote"]["p_sharpe_gt_0"])
               & (p_ir_gt_0 >= rule["promote"]["p_ir_gt_0"]))
    revert = (months >= rule["revert_to_control"]["min_months"]) & (p_ir_gt < rule["revert_to_control"]["prob_below"])
    kill_sr = (months >= rule["kill_sharpe"]["min_months"]) & (p_sr_gt_kill < rule["kill_sharpe"]["prob_below"])
    kill_dd = rdd_month[:, :M] < bound
    code = np.where(promote, 4, code)
    code = np.where(revert, 3, code)
    code = np.where(kill_sr, 1, code)
    code = np.where(kill_dd, 2, code)
    any_dec = code > 0
    first = np.where(any_dec.any(axis=1), any_dec.argmax(axis=1), -1)
    final_code = np.where(first >= 0, code[np.arange(N), np.maximum(first, 0)], 0)
    return {"first_month": np.where(first >= 0, first + 1, 0), "code": final_code, "months": M}


def summarize_oc(dec: dict, checkpoints=(12, 24, 36, 60)) -> dict:
    fm, code = dec["first_month"], dec["code"]
    out = {}
    names = {1: "kill_sharpe", 2: "kill_drawdown", 3: "revert_to_control", 4: "promote"}
    for c in checkpoints:
        if c > dec["months"]:
            continue
        done = (fm > 0) & (fm <= c)
        row = {v: float((done & (code == k)).mean()) for k, v in names.items()}
        row["kill_any"] = row["kill_sharpe"] + row["kill_drawdown"]
        row["undecided"] = float(1 - done.mean())
        out[f"{c}m"] = row
    return out


# ---------------------------------------------------------------- DD boundary
def dd_boundary(rdd_month: np.ndarray, percentile: float = 0.99) -> np.ndarray:
    """Pointwise boundary: the (1 - percentile) quantile of the running max drawdown at each elapsed
    month, i.e. a drawdown deeper than 99% of resampled paths had reached by that month."""
    return np.quantile(rdd_month, 1 - percentile, axis=0)


def boundary_false_alarm(rdd_month: np.ndarray, bound: np.ndarray, months: int | None = None) -> float:
    M = months or len(bound)
    return float((rdd_month[:, :M] < bound[None, :M]).any(axis=1).mean())


# ---------------------------------------------------------------- mechanical evaluator
def evaluate_forward(spec_cand: dict, daily: pd.DataFrame, rule: dict | None = None) -> dict:
    """Apply a frozen candidate spec to genuine forward data.

    daily: DataFrame indexed by trading date from the spec's forward_start, with columns
      'ret' (candidate daily net total return), 'rf' (daily T-bill return) and, when the spec has a
      control, 'control_ret'. Looks are taken at each calendar month-end in the data (the last
      trading day of each month) once at least 21 forward trading days exist. Returns every look's
      statistics and the first terminal decision (or CONTINUE)."""
    rule = rule or spec_cand["rule"]
    prm = spec_cand["parameters"]
    d = daily.sort_index()
    d = d.loc[pd.Timestamp(spec_cand["forward_start"]):]
    ex = (d["ret"] - d["rf"]).to_numpy()
    act = (d["ret"] - d["control_ret"]).to_numpy() if "control_ret" in d and spec_cand.get("control") else None
    W = np.cumprod(1 + d["ret"].to_numpy())
    peak = np.maximum.accumulate(np.maximum(W, 1.0))
    rdd = np.minimum.accumulate(W / peak - 1)
    month = pd.Series(d.index.to_period("M"), index=d.index)
    month_end = month.ne(month.shift(-1)).to_numpy()
    looks = []
    names = {1: "KILL_SHARPE", 2: "KILL_DRAWDOWN", 3: "REVERT_TO_CONTROL", 4: "PROMOTE"}
    bound = prm["dd_boundary"]
    for i in np.flatnonzero(month_end):
        n = i + 1
        if n < rule["look_every_trading_days"]:
            continue
        m_el = int(round(n / MONTH_DAYS))
        m_idx = min(max(m_el, 1), len(bound)) - 1
        x = ex[:n]
        yrs = n / 252.0
        sr = float(x.mean() / x.std(ddof=1) * np.sqrt(252)) if x.std(ddof=1) > 0 else 0.0
        pm, ps = posterior(np.array(sr), np.array(yrs), prm["prior_sharpe_mean"], prm["prior_sharpe_sd"], prm["k_sharpe"])
        sm, ss = posterior(np.array(sr), np.array(yrs), 0.0, prm["skeptical_sharpe_sd"], prm["k_sharpe"])
        look = {"date": str(d.index[i].date()), "trading_days": n, "months_elapsed": m_el, "sharpe": sr,
                "post_sharpe_mean": float(pm), "post_sharpe_sd": float(ps),
                "p_sharpe_gt_kill": float(prob_above(pm, ps, rule["kill_sharpe"]["threshold"])),
                "p_sharpe_gt_0": float(prob_above(sm, ss, 0.0)), "running_max_dd": float(rdd[i]),
                "dd_boundary": float(bound[m_idx])}
        if act is not None:
            a = act[:n]
            ir = float(a.mean() / a.std(ddof=1) * np.sqrt(252)) if a.std(ddof=1) > 0 else 0.0
            qm, qs = posterior(np.array(ir), np.array(yrs), prm["prior_ir_mean"], prm["prior_ir_sd"], prm["k_ir"])
            tm, ts = posterior(np.array(ir), np.array(yrs), 0.0, prm["skeptical_ir_sd"], prm["k_ir"])
            look.update({"ir_vs_control": ir, "p_ir_gt_revert": float(prob_above(qm, qs, rule["revert_to_control"]["threshold"])),
                         "p_ir_gt_0": float(prob_above(tm, ts, 0.0))})
        else:
            look.update({"p_ir_gt_revert": 1.0, "p_ir_gt_0": 1.0})
        code = 0
        if look["running_max_dd"] < look["dd_boundary"]:
            code = 2
        elif m_el >= rule["kill_sharpe"]["min_months"] and look["p_sharpe_gt_kill"] < rule["kill_sharpe"]["prob_below"]:
            code = 1
        elif m_el >= rule["revert_to_control"]["min_months"] and look["p_ir_gt_revert"] < rule["revert_to_control"]["prob_below"]:
            code = 3
        elif (m_el >= rule["promote"]["min_months"] and look["p_sharpe_gt_0"] >= rule["promote"]["p_sharpe_gt_0"]
              and look["p_ir_gt_0"] >= rule["promote"]["p_ir_gt_0"]):
            code = 4
        look["decision"] = names.get(code, "CONTINUE")
        looks.append(look)
        if code:
            break
        if m_el >= rule["max_months"]:
            look["decision"] = "END_NO_DECISION"
            break
    final = looks[-1]["decision"] if looks else "NO_LOOK_YET"
    return {"candidate": spec_cand["candidate"], "decision": final, "looks": looks}


def canonical_hash(obj: dict) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def verify_spec(spec: dict) -> bool:
    body = {k: v for k, v in spec.items() if k != "sha256"}
    return canonical_hash(body) == spec.get("sha256")


def evaluate_from_spec(spec_path, name: str, daily: pd.DataFrame) -> dict:
    """Load the frozen spec, refuse it if its content hash does not match, and evaluate one candidate."""
    from pathlib import Path

    spec = json.loads(Path(spec_path).read_text())
    if not verify_spec(spec):
        raise ValueError("monitoring spec hash mismatch: the spec was edited after freezing")
    out = evaluate_forward(spec["candidates"][name], daily, rule=spec["rule"])
    out["spec_sha256"] = spec["sha256"]
    return out
