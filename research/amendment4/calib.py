"""research.amendment4.calib -- null-calibrated inference for short, autocorrelated or crash-skewed return series.

Procedure ("NCT", null-calibrated t; a Monte Carlo test in the sense of Dufour 2006, with an AR-sieve null
(Buhlmann 1997) and a residual bootstrap for the innovations):

  1. Statistic: the Bartlett-kernel HAC t of the mean, T = mean / sqrt(LRV(L) / n), with a fixed-b bandwidth
         L = max(floor(4 (n/100)^(2/9)), 2H, ceil(0.10 n))   (H = declared overlapping horizon, else 1);
     LRV is Newey-West for L <= 16 and overlapping batch means (the O(n) Bartlett equivalent) above.
  2. Null model, fitted to the DEMEANED series: AR(p), p in {0..max(3, 2H)} chosen by BIC on Yule-Walker
     (Levinson-Durbin) innovation variances, bias-corrected (Kilian 1998, R = 50 inner fits, shrunk to stay
     stationary). Innovations: iid resample of the centred AR residuals (keeps skew / kurtosis).
     Optional declared crash layer: when the PLAN declares a crash process (probability per period, jump in sd
     units) the null is ALSO simulated with a standardised Gaussian+Bernoulli-jump innovation and the larger of
     the two p-values is used (a sample without a crash cannot reveal the crash; the declaration can).
  3. Simulate B series of the observed length n from the null model (burn-in 200), compute T* with the same L,
         p = (1 + #{T* >= T}) / (B + 1).
     With B + 1 a multiple of 1/alpha the Monte Carlo test is exact when the fitted null equals the truth; the
     finite B costs a little power, not size. Default B = 159 (B + 1 = 160 = 2/0.0125 = 8/0.05); a decision at
     alpha is "p <= alpha".
  4. Sequential stopping (Besag & Clifford 1991): once #{T* >= T} exceeds alpha_max (B+1) - 1 the p-value
     cannot fall below alpha_max, so the loop stops. Decisions at any alpha <= alpha_max are unchanged.

Also here (comparators and old tests): the literal Newey-West t with a normal critical value, the mean-centred
circular block bootstrap p (research.power.simulate semantics), and the batch-means t (Ibragimov-Mueller 2010).

Everything is numba-compiled and parallel over paths; each path's random stream is seeded by (seed + path index),
so results do not depend on the thread count.
"""
from __future__ import annotations

import math

import numpy as np
from numba import njit, prange
from scipy import stats

BURN = 200
PMAX = 3
B_DEFAULT = 159


def nw_default_lags(n: int) -> int:
    return int(math.floor(4 * (max(n, 1) / 100.0) ** (2.0 / 9.0)))


BANDWIDTH_FRACTION = 0.10


def stat_lags(n: int, overlap: int = 1, b: float = BANDWIDTH_FRACTION) -> int:
    """Bandwidth of the calibrated statistic: L = max(NW plug-in, 2H, ceil(b n)), b = 0.10 by default (a fixed-b
    bandwidth, Kiefer & Vogelsang 2005: it keeps slow regime / overlap dependence inside the variance estimate, and
    the null calibration supplies the matching critical value)."""
    L = nw_default_lags(n)
    if overlap and overlap > 1:
        L = max(L, 2 * int(overlap))
    L = max(L, int(math.ceil(b * n)))
    return max(1, min(L, n // 3))


# ============================================================================================ numba kernels
@njit(cache=True)
def _mean(x):
    s = 0.0
    for i in range(x.shape[0]):
        s += x[i]
    return s / x.shape[0]


@njit(cache=True)
def nw_lrv(x, L):
    n = x.shape[0]
    m = _mean(x)
    v = 0.0
    for i in range(n):
        d = x[i] - m
        v += d * d
    v /= n
    for k in range(1, L + 1):
        g = 0.0
        for i in range(k, n):
            g += (x[i] - m) * (x[i - k] - m)
        v += 2.0 * (1.0 - k / (L + 1.0)) * g / n
    if v < 1e-300:
        v = 1e-300
    return v


@njit(cache=True)
def obm_lrv(x, M):
    """Overlapping-batch-means long-run variance with batch length M (asymptotically the Bartlett kernel with
    bandwidth M; O(n) via running sums). Used by the calibrated statistic when L > 16."""
    n = x.shape[0]
    m = _mean(x)
    s = 0.0
    for i in range(M):
        s += x[i] - m
    acc = s * s
    for j in range(1, n - M + 1):
        s += (x[j + M - 1] - m) - (x[j - 1] - m)
        acc += s * s
    v = acc / ((n - M + 1) * M)
    if v < 1e-300:
        v = 1e-300
    return v


@njit(cache=True)
def nw_t(x, L):
    n = x.shape[0]
    if L > 16:
        return _mean(x) / math.sqrt(obm_lrv(x, L + 1) / n)
    return _mean(x) / math.sqrt(nw_lrv(x, L) / n)


@njit(cache=True)
def fit_ar_bic(e, pmax, pen=-1.0):
    """Yule-Walker AR(p), p <= pmax by BIC (e must be demeaned). Returns (p, phi[pmax])."""
    n = e.shape[0]
    r = np.zeros(pmax + 1)
    for k in range(pmax + 1):
        s = 0.0
        for i in range(k, n):
            s += e[i] * e[i - k]
        r[k] = s / n
    best_phi = np.zeros(pmax)
    best_p = 0
    if r[0] <= 0.0:
        return 0, best_phi
    v = r[0]
    best_bic = n * math.log(v)
    phi = np.zeros(pmax)
    tmp = np.zeros(pmax)
    for p in range(1, pmax + 1):
        acc = r[p]
        for j in range(1, p):
            acc -= phi[j - 1] * r[p - j]
        kr = acc / v
        for j in range(1, p):
            tmp[j - 1] = phi[j - 1] - kr * phi[p - j - 1]
        for j in range(1, p):
            phi[j - 1] = tmp[j - 1]
        phi[p - 1] = kr
        v = v * (1.0 - kr * kr)
        if v <= 0.0:
            break
        bic = n * math.log(v) + p * (math.log(n) if pen < 0 else pen)
        if pen == 0.0 or bic < best_bic:
            best_bic = bic
            best_p = p
            for j in range(pmax):
                best_phi[j] = phi[j] if j < p else 0.0
    return best_p, best_phi


@njit(cache=True)
def ar_residuals(e, p, phi):
    n = e.shape[0]
    u = np.empty(n - p)
    for t in range(p, n):
        v = e[t]
        for j in range(p):
            v -= phi[j] * e[t - 1 - j]
        u[t - p] = v
    m = _mean(u)
    for i in range(u.shape[0]):
        u[i] -= m
    return u


@njit(cache=True)
def fit_ar_fixed(e, p, pmax):
    """Yule-Walker AR of fixed order p (returns phi[pmax])."""
    n = e.shape[0]
    r = np.zeros(p + 1)
    for k in range(p + 1):
        s = 0.0
        for i in range(k, n):
            s += e[i] * e[i - k]
        r[k] = s / n
    phi = np.zeros(pmax)
    if p == 0 or r[0] <= 0.0:
        return phi
    tmp = np.zeros(pmax)
    v = r[0]
    for q in range(1, p + 1):
        acc = r[q]
        for j in range(1, q):
            acc -= phi[j - 1] * r[q - j]
        kr = acc / v
        for j in range(1, q):
            tmp[j - 1] = phi[j - 1] - kr * phi[q - j - 1]
        for j in range(1, q):
            phi[j - 1] = tmp[j - 1]
        phi[q - 1] = kr
        v = v * (1.0 - kr * kr)
        if v <= 0.0:
            break
    return phi


@njit(cache=True)
def is_stationary(phi, p):
    """Step-down Levinson: AR(p) is stationary iff every reflection coefficient has |k| < 1."""
    a = phi[:p].copy()
    for q in range(p, 0, -1):
        k = a[q - 1]
        if abs(k) >= 0.999:
            return False
        if q == 1:
            break
        b = np.empty(q - 1)
        for j in range(q - 1):
            b[j] = (a[j] + k * a[q - 2 - j]) / (1.0 - k * k)
        a = b
    return True


@njit(cache=True)
def bias_correct(phi, p, u, n, R, pmax):
    """Kilian (1998) bootstrap bias correction of the AR coefficients (R replications at the sample length),
    shrunk towards the raw estimate until the corrected model is stationary."""
    if p == 0:
        return phi
    acc = np.zeros(pmax)
    y = np.empty(n + BURN)
    for r in range(R):
        ys = _sim_ar(y, phi, p, u, 0, 0.0, 0.0, 1.0, 0.0)
        m = _mean(ys)
        f = fit_ar_fixed(ys - m, p, pmax)
        for j in range(p):
            acc[j] += f[j]
    bias = np.zeros(pmax)
    for j in range(p):
        bias[j] = acc[j] / R - phi[j]
    out = phi.copy()
    delta = 1.0
    for it in range(12):
        for j in range(p):
            out[j] = phi[j] - delta * bias[j]
        if is_stationary(out, p):
            return out
        delta *= 0.7
    return phi.copy()


@njit(cache=True)
def _sim_ar(y, phi, p, u, mode, cp, cJ, csd, mu):
    """Fill y (length n + BURN) with an AR(p) path; returns the last n values + mu.
    mode 0: innovations resampled from u; mode 1: standardised Gaussian + Bernoulli(cp) jump cJ, scaled by csd."""
    N = y.shape[0]
    nu = u.shape[0]
    sc = 1.0 / math.sqrt(1.0 + cp * (1.0 - cp) * cJ * cJ)
    for t in range(N):
        if mode == 0:
            eps = u[np.random.randint(0, nu)]
        else:
            z = np.random.standard_normal()
            if np.random.random() < cp:
                z += cJ
            eps = csd * (z - cp * cJ) * sc
        val = eps
        for j in range(p):
            if t - 1 - j >= 0:
                val += phi[j] * y[t - 1 - j]
        y[t] = val
    out = y[N - (N - BURN):].copy() if N > BURN else y.copy()
    for i in range(out.shape[0]):
        out[i] += mu
    return out


@njit(cache=True)
def _calib_one(x, L, B, pmax, mode, cp, cJ, stop_cnt, bc, pen):
    n = x.shape[0]
    m = _mean(x)
    e = x - m
    p, phi = fit_ar_bic(e, pmax, pen)
    u = ar_residuals(e, p, phi)
    if bc > 0 and p > 0:
        phi = bias_correct(phi, p, u, n, bc, pmax)
        u = ar_residuals(e, p, phi)
    csd = 0.0
    for i in range(u.shape[0]):
        csd += u[i] * u[i]
    csd = math.sqrt(csd / u.shape[0])
    T = nw_t(x, L)
    y = np.empty(n + BURN)
    cnt = 0
    done = 0
    for b in range(B):
        ys = _sim_ar(y, phi, p, u, mode, cp, cJ, csd, 0.0)
        if nw_t(ys, L) >= T:
            cnt += 1
        done += 1
        if cnt > stop_cnt:
            break
    if done < B:   # stopped early: p > alpha_max; report the (conservative) running value
        return (1.0 + cnt) / (done + 1.0), T, p
    return (1.0 + cnt) / (B + 1.0), T, p


@njit(parallel=True, cache=True)
def calibrated_p_batch(X, L, B, pmax, seeds, mode, cp, cJ, stop_cnt, bc, pen):
    P = X.shape[0]
    pv = np.empty(P)
    tv = np.empty(P)
    order = np.empty(P, np.int64)
    for i in prange(P):
        np.random.seed(seeds[i])
        a, b, c = _calib_one(X[i], L, B, pmax, mode, cp, cJ, stop_cnt, bc, pen)
        pv[i] = a
        tv[i] = b
        order[i] = c
    return pv, tv, order


@njit(parallel=True, cache=True)
def nw_t_batch(X, L):
    P = X.shape[0]
    out = np.empty(P)
    for i in prange(P):
        out[i] = nw_t(X[i], L)
    return out


@njit(parallel=True, cache=True)
def cbb_p_batch(X, blocks, B, seed, stop_cnt):
    """Mean-centred circular block bootstrap p (one-sided, upper): p = (1 + #{mean* >= mean}) / (B + 1)."""
    P, n = X.shape
    out = np.empty(P)
    for i in prange(P):
        np.random.seed(seed + i)
        x = X[i]
        b = blocks[i]
        m = _mean(x)
        nb = (n + b - 1) // b
        bs = np.empty(n)
        for s in range(n):
            acc = 0.0
            for j in range(b):
                acc += x[(s + j) % n] - m
            bs[s] = acc
        cnt = 0
        done = 0
        for r in range(B):
            tot = 0.0
            for k in range(nb):
                tot += bs[np.random.randint(0, n)]
            if tot / (nb * b) >= m:
                cnt += 1
            done += 1
            if cnt > stop_cnt:
                break
        out[i] = (1.0 + cnt) / (done + 1.0) if done < B else (1.0 + cnt) / (B + 1.0)
    return out


@njit(parallel=True, cache=True)
def rho1_batch(X):
    P, n = X.shape
    out = np.empty(P)
    for i in prange(P):
        x = X[i]
        m = _mean(x)
        g0 = 0.0
        g1 = 0.0
        for t in range(n):
            g0 += (x[t] - m) ** 2
        for t in range(1, n):
            g1 += (x[t] - m) * (x[t - 1] - m)
        out[i] = g1 / g0 if g0 > 0 else 0.0
    return out


# ============================================================================================ python API
def _stop(alpha_max: float, B: int) -> int:
    return int(math.floor(alpha_max * (B + 1) + 1e-9)) - 1


def calibrated_pvalues(X, *, overlap: int = 1, B: int = B_DEFAULT, seed: int = 1, alpha_max: float = 0.05,
                       crash: tuple | None = None, pmax: int | None = None, full: bool = False,
                       bias_correct_R: int = 50, L: int | None = None, order_penalty: float = -1.0,
                       bandwidth_fraction: float = BANDWIDTH_FRACTION, seeds=None):
    """Null-calibrated one-sided p-values (H1: mean > 0) for each row of X (paths x n).

    crash = (prob_per_period, jump_in_sd) declares a crash layer; the p-value is then max(p_resid, p_crash).
    full=True disables sequential stopping (exact p for every path; slower).
    Returns dict(p, t, ar_order)."""
    X = np.ascontiguousarray(np.atleast_2d(np.asarray(X, float)))
    n = X.shape[1]
    L = stat_lags(n, overlap, bandwidth_fraction) if L is None else int(L)
    if pmax is None:
        pmax = max(PMAX, 2 * int(overlap)) if overlap and overlap > 1 else PMAX
    stop = B + 1 if full else _stop(alpha_max, B)
    bc = int(bias_correct_R)
    if seeds is None:
        seeds = int(seed) + np.arange(X.shape[0], dtype=np.int64)
    seeds = np.asarray(seeds, np.int64) % (2 ** 31 - 1)
    p0, t, order = calibrated_p_batch(X, L, B, pmax, seeds, 0, 0.0, 0.0, stop, bc, float(order_penalty))
    if crash is not None:
        cp, cJ = float(crash[0]), float(crash[1])
        p1, _, _ = calibrated_p_batch(X, L, B, pmax, (seeds + 7_000_003) % (2 ** 31 - 1), 1, cp, cJ, stop, bc, float(order_penalty))
        p0 = np.maximum(p0, p1)
    return {"p": p0, "t": t, "ar_order": order, "L": L}


def calibrated_pvalue(x, **kw) -> float:
    """Single-series convenience wrapper (exact p, no sequential stopping)."""
    kw.setdefault("full", True)
    return float(calibrated_pvalues(np.asarray(x, float)[None, :], **kw)["p"][0])


def old_nw_t_reject(X, alpha: float, lags: int) -> np.ndarray:
    X = np.ascontiguousarray(np.atleast_2d(np.asarray(X, float)))
    return nw_t_batch(X, int(lags)) >= stats.norm.isf(alpha)


def cbb_pvalues(X, block, *, B: int = B_DEFAULT, seed: int = 2, alpha_max: float = 0.05) -> np.ndarray:
    X = np.ascontiguousarray(np.atleast_2d(np.asarray(X, float)))
    blocks = np.broadcast_to(np.asarray(block, np.int64), (X.shape[0],)).copy()
    return cbb_p_batch(X, blocks, B, int(seed), _stop(alpha_max, B))


def a4q3_blocks(X) -> np.ndarray:
    """Amendment-4 proposal Q3 block rule: max(n^(1/3), 2 (1 + rho1) / (1 - rho1)) (rho1 estimated per path)."""
    X = np.ascontiguousarray(np.atleast_2d(np.asarray(X, float)))
    n = X.shape[1]
    r1 = np.clip(rho1_batch(X), -0.95, 0.95)
    b = np.maximum(round(n ** (1 / 3)), np.ceil(2 * (1 + r1) / (1 - r1)))
    return np.minimum(b, n // 2).astype(np.int64)


def batch_means_t_reject(X, alpha: float, K: int = 10) -> np.ndarray:
    """Ibragimov-Mueller (2010) batch-means t with K equal batches and a t_{K-1} critical value."""
    X = np.atleast_2d(np.asarray(X, float))
    n = X.shape[1]
    m = n // K
    bm = X[:, : m * K].reshape(X.shape[0], K, m).mean(axis=2)
    t = bm.mean(axis=1) / (bm.std(axis=1, ddof=1) / math.sqrt(K))
    return t >= stats.t.isf(alpha, K - 1)
