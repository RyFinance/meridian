"""research.amendment4.ci -- Section 6: calibrated confidence intervals for post-publication net mean and Sharpe.

Method (same null model as the calibrated test, re-centred at the estimate; a studentised AR-sieve bootstrap-t):
  fit AR(p) (BIC, p <= 3, Kilian bias-corrected) to the demeaned series, keep centred residuals;
  simulate B = 499 series y* = mean_hat + AR(residual bootstrap) of the same length;
  mean:   T* = (m* - m) / se*,   se = sqrt(LRV(L) / n), L = max(NW plug-in, ceil(0.1 n))
  Sharpe: T* = (s* - s) / se_s*, se_s from the LRV of the Sharpe influence function
          psi_t = z_t - s/2 (z_t^2 - 1), z_t = (x_t - m)/sd   (captures skew, kurtosis and autocorrelation)
  CI = [est - q_{1-a/2}(T*) se, est - q_{a/2}(T*) se]  (equal-tailed).
Comparators: HAC-normal (NW plug-in lags) and the 12-month circular-block percentile interval (Amendment 5's
default block). These are ESTIMATES with intervals, never pass/fail gates.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from numba import njit, prange
from scipy import stats

from research.amendment4 import calib, dgp
from research.amendment4.calib import (_mean, _sim_ar, ar_residuals, bias_correct, fit_ar_bic, nw_lrv, obm_lrv)

B_CI = 499
LEVELS = (0.90, 0.95)


@njit(cache=True)
def _lrv(x, L):
    return obm_lrv(x, L + 1) if L > 16 else nw_lrv(x, L)


@njit(cache=True)
def _est(x, L):
    n = x.shape[0]
    m = _mean(x)
    v = 0.0
    for i in range(n):
        v += (x[i] - m) ** 2
    sd = math.sqrt(v / (n - 1))
    s = m / sd
    se_m = math.sqrt(_lrv(x, L) / n)
    psi = np.empty(n)
    for i in range(n):
        z = (x[i] - m) / sd
        psi[i] = z - 0.5 * s * (z * z - 1.0)
    se_s = math.sqrt(_lrv(psi, L) / n)
    return m, se_m, s, se_s


@njit(parallel=True, cache=True)
def boot_t_batch(X, L, B, seed, bc):
    """Returns per path: m, se_m, s, se_s and the B studentised draws for the mean and the Sharpe (P x B each)."""
    P, n = X.shape
    est = np.empty((P, 4))
    tm = np.empty((P, B))
    ts = np.empty((P, B))
    for i in prange(P):
        np.random.seed(seed + i)
        x = X[i]
        m, se_m, s, se_s = _est(x, L)
        est[i, 0] = m
        est[i, 1] = se_m
        est[i, 2] = s
        est[i, 3] = se_s
        e = x - m
        p, phi = fit_ar_bic(e, 3, -1.0)
        u = ar_residuals(e, p, phi)
        if bc > 0 and p > 0:
            phi = bias_correct(phi, p, u, n, bc, 3)
            u = ar_residuals(e, p, phi)
        y = np.empty(n + 200)
        for b in range(B):
            ys = _sim_ar(y, phi, p, u, 0, 0.0, 0.0, 1.0, m)
            mb, sem, sb, ses = _est(ys, L)
            tm[i, b] = (mb - m) / sem
            ts[i, b] = (sb - s) / ses
    return est, tm, ts


@njit(parallel=True, cache=True)
def cbb_percentile_batch(X, block, B, seed):
    """Circular block bootstrap draws of the mean and the Sharpe (P x B each)."""
    P, n = X.shape
    bm = np.empty((P, B))
    bs = np.empty((P, B))
    nb = (n + block - 1) // block
    for i in prange(P):
        np.random.seed(seed + i)
        x = X[i]
        for b in range(B):
            s1 = 0.0
            s2 = 0.0
            cnt = 0
            for k in range(nb):
                st = np.random.randint(0, n)
                for j in range(block):
                    if cnt < n:
                        v = x[(st + j) % n]
                        s1 += v
                        s2 += v * v
                        cnt += 1
            m = s1 / n
            var = (s2 - n * m * m) / (n - 1)
            bm[i, b] = m
            bs[i, b] = m / math.sqrt(var) if var > 0 else 0.0
    return bm, bs


def calibrated_ci(x, level=0.90, q=12, B=B_CI, seed=1, bias_correct_R=50):
    """Calibrated CIs for one series: returns dict(mean=(lo, hi, est), sharpe_ann=(lo, hi, est)) (annualised)."""
    X = np.ascontiguousarray(np.asarray(x, float)[None, :])
    n = X.shape[1]
    L = calib.stat_lags(n)
    est, tm, ts = boot_t_batch(X, L, B, seed, bias_correct_R)
    a = 1 - level
    m, se_m, s, se_s = est[0]
    qm = np.quantile(tm[0], [1 - a / 2, a / 2])
    qs = np.quantile(ts[0], [1 - a / 2, a / 2])
    return {"mean_ann": ((m - qm[0] * se_m) * q, (m - qm[1] * se_m) * q, m * q),
            "sharpe_ann": ((s - qs[0] * se_s) * math.sqrt(q), (s - qs[1] * se_s) * math.sqrt(q), s * math.sqrt(q)),
            "L": L}


SCEN = {
    "iid": lambda P, n, rng: dgp.iid(P, n, rng),
    "ar1_0.2": lambda P, n, rng: dgp.ar1(P, n, rng, 0.2),
    "crash_l0.2_J-6": lambda P, n, rng: dgp.crash(P, n, rng, 0.2 / 12, -6.0),
    "crash+ar1_0.2": lambda P, n, rng: dgp.crash(P, n, rng, 0.2 / 12, -6.0, phi=0.2),
}


def run(paths=20000, S=0.4, q=12, months=(60, 120, 180), seed=20261001, chunk=5000):
    rows = []
    for si, (name, gen) in enumerate(SCEN.items()):
        for n in months:
            L = calib.stat_lags(n)
            Lnw = calib.nw_default_lags(n)
            acc = {}
            for i0 in range(0, paths, chunk):
                P = min(chunk, paths - i0)
                rng = np.random.default_rng([seed, si, n, i0])
                X = np.ascontiguousarray(gen(P, n, rng) + S / math.sqrt(q))   # unit variance -> true Sharpe S
                est, tm, ts = boot_t_batch(X, L, B_CI, seed + i0, 50)
                bm, bs = cbb_percentile_batch(X, 12, B_CI, seed + 7 + i0)
                mu, sd = S / math.sqrt(q), 1.0
                s_true = mu / sd
                # HAC-normal comparator (NW plug-in lags)
                se_nw = np.sqrt(calib.nw_t_batch(X, Lnw) ** -2 * est[:, 0] ** 2)  # = sqrt(LRV_NW/n)
                for lev in LEVELS:
                    a = 1 - lev
                    z = stats.norm.isf(a / 2)
                    qm_hi, qm_lo = np.quantile(tm, 1 - a / 2, axis=1), np.quantile(tm, a / 2, axis=1)
                    qs_hi, qs_lo = np.quantile(ts, 1 - a / 2, axis=1), np.quantile(ts, a / 2, axis=1)
                    ci = {
                        ("calibrated_boot_t", "mean"): (est[:, 0] - qm_hi * est[:, 1], est[:, 0] - qm_lo * est[:, 1], mu),
                        ("calibrated_boot_t", "sharpe"): (est[:, 2] - qs_hi * est[:, 3], est[:, 2] - qs_lo * est[:, 3], s_true),
                        ("hac_normal", "mean"): (est[:, 0] - z * se_nw, est[:, 0] + z * se_nw, mu),
                        ("cbb12_percentile", "mean"): (np.quantile(bm, a / 2, axis=1), np.quantile(bm, 1 - a / 2, axis=1), mu),
                        ("cbb12_percentile", "sharpe"): (np.quantile(bs, a / 2, axis=1), np.quantile(bs, 1 - a / 2, axis=1), s_true),
                    }
                    for k, (lo, hi, tru) in ci.items():
                        d = acc.setdefault((k[0], k[1], lev), {"cover": [], "miss_lo": [], "miss_hi": [], "width": []})
                        d["cover"].append((lo <= tru) & (tru <= hi))
                        d["miss_lo"].append(tru < lo)     # interval entirely above the truth
                        d["miss_hi"].append(tru > hi)     # interval entirely below the truth
                        d["width"].append(hi - lo)
            for (meth, par, lev), d in acc.items():
                cov = np.concatenate(d["cover"])
                scale = q if par == "mean" else math.sqrt(q)
                rows.append({"scenario": name, "months": n, "true_sharpe_ann": S, "method": meth, "parameter": par,
                             "nominal": lev, "coverage": float(cov.mean()),
                             "mc_se": math.sqrt(lev * (1 - lev) / len(cov)),
                             "share_ci_above_truth": float(np.concatenate(d["miss_lo"]).mean()),
                             "share_ci_below_truth": float(np.concatenate(d["miss_hi"]).mean()),
                             "median_width_ann": float(np.median(np.concatenate(d["width"])) * scale),
                             "paths": len(cov), "inner_B": B_CI, "bandwidth_L": L})
            print(f"[ci] {name} n={n} " + " ".join(
                f"{r['method'][:6]}/{r['parameter'][:2]}/{r['nominal']}={r['coverage']:.3f}" for r in rows[-10:]),
                flush=True)
    return pd.DataFrame(rows)
