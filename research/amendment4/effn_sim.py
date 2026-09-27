"""research.amendment4.effn_sim -- Section 4 simulations: (a) D < 1 inputs; (b) breadth-correlation misread.

(a) D < 1. Daily AR(1) phi = 0.09 (true D = 1.198), 12 years, true net Sharpe 0.7. Per path the analyst backs D out of
    ONE realised sample, as commodity_roll did: D_hat = (t_iid / z_{1-p})^2 with p the sample's mean-centred CBB p
    (block 21, B = 999), and alternatively the sample NW ratio LRV_NW / gamma_0. Compared: claimed effective obs
    n / D_hat vs raw n, and the single-stage power (p < 0.05 and S_hat >= 0.30, 12 years) implied by D_hat, by
    max(D_hat, 1) (the fix) and by the true D.

(b) Breadth. N = 500 assets, monthly, 10 sectors plus a style factor with Rademacher loadings (style share of residual
    variance 0.20, sector share 0.20); the signal loads on the style direction with share rho_signal = 0.30; true IC
    0.02. Residuals are sector-demeaned (market / sector neutral). Per path, 60 pre-dev months give
      misread: rho = average pairwise TIME-SERIES correlation of the neutral residual returns (~0 by construction)
      fix:     rho_bet = (N sd(IC)^2 - 1) / (N - 1) from the per-period IC dispersion
    and the implied Sharpe of the IC-weighted book IC * sqrt(12 N / (1 + (N - 1) rho)). Truth = the long-run Sharpe of
    the same book (mean IC / sd IC * sqrt(12)) from 8 x 5,000-month simulation of the same model.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from numba import njit, prange
from scipy import stats

from research.amendment4 import calib, dgp


# ---------------------------------------------------------------------------------------------- (a) D < 1
def run_D(paths=20000, seed=20260929, phi=0.09, years=12, S=0.7, q=252):
    n = years * q
    rng = np.random.default_rng(seed)
    D_true = (1 + phi) / (1 - phi)
    rows = []
    X = np.ascontiguousarray(dgp.ar1(paths, n, rng, phi) + S / math.sqrt(q))   # unit-variance AR(1): Sharpe S
    p = calib.cbb_p_batch(X, np.full(paths, 21, np.int64), 999, seed, 10 ** 9)
    Sh = X.mean(1) / X.std(1, ddof=1) * math.sqrt(q)
    t_iid = Sh * math.sqrt(years)
    z = stats.norm.isf(np.clip(p, 1 / 1000, 0.5))
    D_backed = np.where(p < 0.5, (t_iid / z) ** 2, np.nan)
    L = calib.nw_default_lags(n)
    lrv = np.array([calib.nw_lrv(x, L) for x in X])
    D_nw = lrv / X.var(1)

    def pw(D):
        se = np.sqrt(D / years)
        h = np.maximum(stats.norm.isf(0.05) * se, 0.30)
        return stats.norm.sf((h - S) / se)

    p_true = float(pw(D_true))
    for lab, Dh in (("backed_out_from_one_CBB_p", D_backed), ("sample_NW_ratio", D_nw)):
        ok = np.isfinite(Dh)
        Dh = Dh[ok]
        for rule, Du in (("as_estimated", Dh), ("floored_at_1 (A4)", np.maximum(Dh, 1.0))):
            pwr = pw(Du)
            rows.append({"part": "D_lt_1", "true_phi": phi, "estimator": lab, "rule": rule, "paths": int(ok.sum()), "true_D": D_true,
                         "median_D_hat": float(np.median(Du)), "share_D_lt_1": float(np.mean(Du < 1)),
                         "share_neff_gt_nraw": float(np.mean(n / Du > n)),
                         "mean_neff_over_nraw": float(np.mean(1 / Du)), "true_neff_over_nraw": 1 / D_true,
                         "true_power": p_true, "mean_claimed_power": float(np.mean(pwr)),
                         "share_power_overstated": float(np.mean(pwr > p_true + 1e-9)),
                         "mean_power_overstatement": float(np.mean(np.maximum(pwr - p_true, 0)))})
    return rows


# ---------------------------------------------------------------------------------------------- (b) breadth
@njit(cache=True)
def _ic_period(s, r, N):
    ms = 0.0
    mr = 0.0
    for i in range(N):
        ms += s[i]
        mr += r[i]
    ms /= N
    mr /= N
    a = 0.0
    b = 0.0
    c = 0.0
    for i in range(N):
        a += (s[i] - ms) * (r[i] - mr)
        b += (s[i] - ms) ** 2
        c += (r[i] - mr) ** 2
    return a / math.sqrt(b * c)


@njit(cache=True)
def _one_study(N, T, n_sec, style_sh, sec_sh, rho_sig, ic, R):
    beta = np.empty(N)
    sec = np.empty(N, np.int64)
    for i in range(N):
        beta[i] = 1.0 if np.random.random() < 0.5 else -1.0
        sec[i] = i % n_sec
    idio_sh = 1.0 - style_sh - sec_sh
    ics = np.empty(T)
    Rm = np.empty((T, N))
    s = np.empty(N)
    r = np.empty(N)
    g = np.empty(n_sec)
    cnt = np.zeros(n_sec)
    for i in range(N):
        cnt[sec[i]] += 1
    for t in range(T):
        F = np.random.standard_normal()
        for k in range(n_sec):
            g[k] = np.random.standard_normal()
        for i in range(N):
            s[i] = math.sqrt(rho_sig) * beta[i] + math.sqrt(1 - rho_sig) * np.random.standard_normal()
            noise = (math.sqrt(style_sh) * beta[i] * F + math.sqrt(sec_sh) * g[sec[i]]
                     + math.sqrt(idio_sh) * np.random.standard_normal())
            r[i] = ic * s[i] + math.sqrt(1 - ic * ic) * noise
        # sector-neutral residuals
        sm = np.zeros(n_sec)
        for i in range(N):
            sm[sec[i]] += r[i]
        for i in range(N):
            r[i] -= sm[sec[i]] / cnt[sec[i]]
            Rm[t, i] = r[i]
        ics[t] = _ic_period(s, r, N)
    # average pairwise time-series correlation of the neutral residuals
    Z = np.empty((T, N))
    for i in range(N):
        m = 0.0
        for t in range(T):
            m += Rm[t, i]
        m /= T
        v = 0.0
        for t in range(T):
            v += (Rm[t, i] - m) ** 2
        sd = math.sqrt(v / T)
        for t in range(T):
            Z[t, i] = (Rm[t, i] - m) / sd
    tot = 0.0
    for t in range(T):
        st = 0.0
        for i in range(N):
            st += Z[t, i]
        tot += st * st
    rho_pair = (tot / T - N) / (N * (N - 1.0))
    mic = 0.0
    for t in range(T):
        mic += ics[t]
    mic /= T
    vic = 0.0
    for t in range(T):
        vic += (ics[t] - mic) ** 2
    vic /= (T - 1)
    return rho_pair, vic, mic


@njit(parallel=True, cache=True)
def _studies(P, N, T, n_sec, style_sh, sec_sh, rho_sig, ic, seed):
    out = np.empty((P, 3))
    for p in prange(P):
        np.random.seed(seed + p)
        a, b, c = _one_study(N, T, n_sec, style_sh, sec_sh, rho_sig, ic, 0)
        out[p, 0] = a
        out[p, 1] = b
        out[p, 2] = c
    return out


def run_breadth(paths=20000, seed=20260930, N=500, T=60, n_sec=10, style_sh=0.2, sec_sh=0.2, rho_sig=0.3, ic=0.02,
                truth_T=40000):
    q = 12
    res = _studies(paths, N, T, n_sec, style_sh, sec_sh, rho_sig, ic, seed)
    # truth: one long study (same model, fixed loadings drawn once -> average several)
    tr = _studies(8, N, truth_T // 8, n_sec, style_sh, sec_sh, rho_sig, ic, seed + 10 ** 7)
    S_true = float(np.mean(tr[:, 2] / np.sqrt(tr[:, 1]) * math.sqrt(q)))
    rho_true = float(np.mean((N * tr[:, 1] - 1) / (N - 1)))
    rows = []
    for lab, rho in (("misread: avg pairwise corr of neutral residuals", res[:, 0]),
                     ("fix: rho_bet from IC dispersion", np.clip((N * res[:, 1] - 1) / (N - 1), 0, 1))):
        raw_median = float(np.median(rho))
        rho = np.clip(rho, 0, 1)          # even clipped at 0 (N_eff <= N) the misread gives N_eff = N
        neff = N / (1 + (N - 1) * rho)
        S_impl = ic * np.sqrt(q * np.clip(neff, 1, None))
        ratio = S_impl / S_true
        rows.append({"part": "breadth", "estimator": lab, "paths": paths, "N": N, "pre_dev_months": T,
                     "true_rho_bet": rho_true, "median_rho_raw": raw_median, "median_rho_used": float(np.median(rho)),
                     "median_N_eff": float(np.median(neff)), "true_N_eff": N / (1 + (N - 1) * rho_true),
                     "true_sharpe": S_true, "median_implied_sharpe": float(np.median(S_impl)),
                     "median_ratio_implied_over_true": float(np.median(ratio)),
                     "p05_ratio": float(np.quantile(ratio, 0.05)), "p95_ratio": float(np.quantile(ratio, 0.95)),
                     "share_overstated_by_50pct": float(np.mean(ratio > 1.5)),
                     "naive_fundamental_law_sharpe": ic * math.sqrt(q * N)})
    return rows


def run(paths=20000):
    return pd.DataFrame(run_D(paths, phi=0.0) + run_D(paths, phi=0.09) + run_breadth(paths))
