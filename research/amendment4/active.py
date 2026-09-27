"""research.amendment4.active -- Section 1: gate directional books on returns net of an exposure-matched control.

active_series(book, exposure, bench_excess) = book - mean(exposure) * bench_excess
(per window; with several benchmarks, sum over columns). Under zero timing skill E[active] = cov(e_t, r_t) = 0, so
the gate's size is nominal whatever the benchmark premium.

Simulation (A2's long-only timing DGP, rebuilt): daily, exposure e_t in {0, 1} Markov (stay 0.95, 60% on), market
Sharpe 0.4, costs 0.05 Sharpe units per stage (stress = double cost), zero timing skill; dev = Amendment-2 gate,
validation = Amendment-3 gate, 12 + 12 years, p-leg = the calibrated test (NCT) and, for reference, the old CBB.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from research.amendment4 import gating


def active_series(book, exposure, bench_excess):
    """Book return net of an exposure-matched control: book_t - sum_j mean_t(exposure_j) * bench_excess_{t,j}.

    book: (T,) or (P, T); exposure and bench_excess: same shape as book, or with a trailing asset axis (.., T, J).
    The control holds the window's AVERAGE exposure to each benchmark (static beta), so timing skill is what is left.
    """
    book = np.asarray(book, float)
    e = np.asarray(exposure, float)
    r = np.asarray(bench_excess, float)
    if e.shape != r.shape:
        raise ValueError("exposure and bench_excess must have the same shape")
    if e.shape == book.shape:
        return book - e.mean(axis=-1, keepdims=True) * r
    if e.shape[:-1] == book.shape:
        ebar = e.mean(axis=-2, keepdims=True)
        return book - (ebar * r).sum(axis=-1)
    raise ValueError("exposure must match book's shape, optionally with a trailing benchmark axis")


def long_only_timing(P, n, rng, S_active=0.0, ppy=252, mkt_sr=0.4, p_stay=0.95, pi_on=0.6, cost_sr=0.05):
    p10 = 1 - p_stay
    p01 = p10 * pi_on / (1 - pi_on)
    e = np.empty((P, n))
    cur = rng.random(P) < pi_on
    u = rng.random((P, n))
    for t in range(n):
        cur = np.where(cur, u[:, t] >= p10, u[:, t] < p01)
        e[:, t] = cur
    mu_m = mkt_sr / math.sqrt(ppy)
    turn = np.abs(np.diff(e, axis=1, prepend=e[:, :1]))
    Eturn = 2 * pi_on * p10
    cpt = cost_sr / math.sqrt(ppy) / Eturn
    var_e = pi_on * (1 - pi_on)
    delta = (S_active / math.sqrt(ppy) * math.sqrt(var_e) + cpt * Eturn) / var_e
    r = mu_m + delta * (e - pi_on) + rng.standard_normal((P, n))
    book = e * r - cpt * turn
    return book, e, r, cpt * turn


def run(paths=20000, years=(12, 12), seed=20260927, chunk=4000, tests=("nct", "cbb_old")):
    q = 252
    nd, nv = years[0] * q, years[1] * q
    rows = []
    for S in (0.0, 0.3, 0.7):
        res = {}
        for i0 in range(0, paths, chunk):
            P = min(chunk, paths - i0)
            rng = np.random.default_rng([seed, int(S * 100), i0])
            book, e, r, cost = long_only_timing(P, nd + nv, rng, S_active=S)
            for lab, (a, b) in {"dev": (0, nd), "val": (nd, nd + nv)}.items():
                bk, ee, rr, cc = book[:, a:b], e[:, a:b], r[:, a:b], cost[:, a:b]
                act = active_series(bk, ee, rr)
                for series, x in (("raw", bk), ("active", act)):
                    x = np.ascontiguousarray(x)
                    st = x - cc
                    for test in tests:
                        if lab == "dev":
                            ok = gating.dev_gate(x, st, q, test=test, seed=seed + i0)
                        else:
                            ok = gating.val_gate(x, st, q, test=test, seed=seed + 50 + i0)
                        res.setdefault((series, test, lab), []).append(ok)
                    if lab == "val":
                        res.setdefault((series, "Sh"), []).append(gating.sharpe(x, q))
        for series in ("raw", "active"):
            Sh = np.concatenate(res[(series, "Sh")])
            for test in tests:
                okd = np.concatenate(res[(series, test, "dev")])
                okv = np.concatenate(res[(series, test, "val")])
                pj = float((okd & okv).mean())
                rows.append({"true_active_sharpe": S, "gated_series": series, "p_test": test, "paths": paths,
                             "dev_years": years[0], "val_years": years[1], "mkt_sharpe": 0.4,
                             "P_dev": okd.mean(), "P_val": okv.mean(), "P_joint": pj,
                             "mc_se_joint": math.sqrt(max(pj * (1 - pj), 1e-12) / paths),
                             "mean_val_sharpe_hat": float(np.nanmean(Sh))})
                print(f"[active] S={S} {series} {test} joint={pj:.4f}", flush=True)
    return pd.DataFrame(rows)


def single_stage_size(paths=20000, years=12, seed=20260931, chunk=5000):
    """One-stage size of the calibrated p-test (p <= alpha) on raw vs active series at zero timing skill."""
    q = 252
    n = years * q
    acc = {}
    for i0 in range(0, paths, chunk):
        P = min(chunk, paths - i0)
        rng = np.random.default_rng([seed, i0])
        book, e, r, cost = long_only_timing(P, n, rng, S_active=0.0)
        for series, x in (("raw", book), ("active", active_series(book, e, r))):
            p = gating.p_values(np.ascontiguousarray(x), "nct", seed=seed + i0, alpha_max=0.05)
            acc.setdefault(series, []).append(p)
    rows = []
    for series, ps in acc.items():
        p = np.concatenate(ps)
        rows.append({"true_active_sharpe": 0.0, "gated_series": series, "p_test": "nct", "paths": paths,
                     "dev_years": years, "stage": "single-stage p-test only",
                     "size_0.05": float(np.mean(p <= 0.05)), "size_0.0125": float(np.mean(p <= 0.0125))})
        print(f"[active-size] {series} {rows[-1]['size_0.05']:.4f} {rows[-1]['size_0.0125']:.4f}", flush=True)
    return pd.DataFrame(rows)
