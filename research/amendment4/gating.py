"""research.amendment4.gating -- literal dev / validation gates on simulated paths, with the calibrated p-leg.

A path's p-value is computed only when its cheaper legs pass (exactly equivalent decisions, much faster).
"""
from __future__ import annotations

import math

import numpy as np

from research.amendment4 import calib


def sharpe(x, q):
    sd = x.std(axis=-1, ddof=1)
    return x.mean(axis=-1) / np.where(sd > 0, sd, np.nan) * math.sqrt(q)


def p_values(x, test: str, *, overlap=1, seed=1, alpha_max=0.05, crash=None, idx=None):
    """idx = the rows' original path indices: each path's null draws are then seeded by (seed + path index), so the
    same path gets the same null draws in every call (net and stress p-tests share them)."""
    x = np.ascontiguousarray(x)
    if len(x) == 0:
        return np.empty(0)
    if test == "nct":
        seeds = None if idx is None else seed + np.asarray(idx, np.int64)
        return calib.calibrated_pvalues(x, overlap=overlap, seed=seed, alpha_max=alpha_max, crash=crash,
                                        seeds=seeds)["p"]
    if test == "cbb_old":
        n = x.shape[1]
        return calib.cbb_pvalues(x, int(round(n ** (1 / 3))), seed=seed, alpha_max=alpha_max)
    raise ValueError(test)


def stress_leg(net, stress, q, rule, *, alpha=0.05, test="nct", overlap=1, seed=7, base_sharpe=None, path_idx=None):
    """Stress-cost leg (boolean per path).
    R0_mean_pos      stress mean > 0 (current)
    R1_floor         stress Sharpe >= 0.30 (proposal Q4)
    R2_half          stress Sharpe >= max(0.30, 0.5 * base Sharpe) (owner's first option)
    R3_signif        stress series passes the calibrated p-test at alpha
    R4_gate          R1 and R3: the stress series passes the full validation gate (p <= alpha AND Sharpe >= 0.30)
    """
    Ss = sharpe(stress, q)
    if rule == "R0_mean_pos":
        return stress.mean(axis=1) > 0
    if rule == "R1_floor":
        return Ss >= 0.30
    if rule == "R2_half":
        Sb = sharpe(net, q) if base_sharpe is None else base_sharpe
        return Ss >= np.maximum(0.30, 0.5 * Sb)
    if rule in ("R3_signif", "R4_gate"):
        ok = np.ones(len(stress), bool) if rule == "R3_signif" else (Ss >= 0.30)
        # the p-test on the stress series is only needed where the rest could pass
        idx = np.where(ok & (stress.mean(axis=1) > 0))[0]
        out = np.zeros(len(stress), bool)
        if len(idx):
            pi = None if path_idx is None else np.asarray(path_idx)[idx]
            p = p_values(stress[idx], test, overlap=overlap, seed=seed, alpha_max=max(alpha, 0.0125), idx=pi)
            out[idx] = p <= alpha
        return out & ok
    raise ValueError(rule)


def dev_gate(net, stress, q, *, k=1, test="nct", overlap=1, seed=11, crash=None):
    """Amendment-2 dev gate: S_hat >= 1.8/sqrt(Y) (2.4 if k >= 4), p <= 0.05/k, stress mean > 0."""
    Y = net.shape[1] / q
    Sh = sharpe(net, q)
    ok = (Sh >= (2.4 if k >= 4 else 1.8) / math.sqrt(Y)) & (stress.mean(axis=1) > 0)
    idx = np.where(ok)[0]
    out = np.zeros(len(net), bool)
    if len(idx):
        a = 0.05 / k
        p = p_values(net[idx], test, overlap=overlap, seed=seed, alpha_max=a, crash=crash, idx=idx)
        out[idx] = p <= a
    return out


def val_gate(net, stress, q, *, k_val=1, floor=0.30, stress_rule="R0_mean_pos", test="nct", overlap=1, seed=13,
             crash=None):
    """Amendment-3 validation gate: p <= 0.05/k_val, S_hat >= floor, plus a stress leg (see stress_leg)."""
    a = 0.05 / k_val
    Sh = sharpe(net, q)
    ok = (Sh >= floor) & (net.mean(axis=1) > 0)
    idx = np.where(ok)[0]
    out = np.zeros(len(net), bool)
    if len(idx):
        p = p_values(net[idx], test, overlap=overlap, seed=seed, alpha_max=a, crash=crash, idx=idx)
        out[idx] = p <= a
    idx2 = np.where(out)[0]
    if len(idx2):
        st = stress_leg(net[idx2], stress[idx2], q, stress_rule, alpha=a, test=test, overlap=overlap, seed=seed,
                        base_sharpe=Sh[idx2], path_idx=idx2)
        out[idx2] = st
    return out
