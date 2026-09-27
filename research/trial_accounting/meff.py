"""Effective-number-of-independent-tests (M_eff) estimators.

Three eigenvalue-based methods from the multiple-testing-correction literature
(originally developed for correlated genetic markers, applied here to
correlated strategy-return series):

- Cheverud (2001), *Evolution* 55(4): M_eff = 1 + (M-1)(1 - Var(lambda)/M),
  using the sample variance of the eigenvalues of the correlation matrix.
- Nyholt (2004), *Am J Hum Genet* 74(4): M_eff = M - sum_i [ (lambda_i - 1) for
  lambda_i > 1 ], i.e. subtract the "excess" eigenvalue mass sitting above 1.
- Li & Ji (2005), *Heredity* 95(3): M_eff = sum_i f(lambda_i), where
  f(lambda) = 1{lambda >= 1} + (lambda - floor(lambda)).

All three are computed from the same correlation-matrix eigenvalues and are
reported side by side because they do not agree exactly; the spread between
them is itself informative about estimation uncertainty. All are clipped to
[1, M].

This module does NOT compute strategy performance. It only consumes a
pre-built pandas DataFrame of (already existing) return series and reports
correlation structure.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def eigenvalues_of_correlation(returns: pd.DataFrame, min_overlap: int = 6) -> tuple[np.ndarray, pd.DataFrame, dict]:
    """Compute the eigenvalues of the pairwise-complete correlation matrix.

    Parameters
    ----------
    returns : DataFrame, columns = series, index = period (e.g. month), values = return
        May contain NaNs (series do not all cover the same window).
    min_overlap : minimum number of overlapping non-NaN observations required
        for a pair to get a real correlation; pairs below this are set to 0
        (treated as uncorrelated / no evidence either way) and flagged.

    Returns
    -------
    eigs : eigenvalues (descending), floored at 0 (a pairwise-complete
        correlation matrix is not guaranteed positive semi-definite; small
        negative eigenvalues from sampling noise are clipped to 0 and this is
        reported, not hidden).
    corr : the correlation matrix used.
    diagnostics : dict with n_series, n_low_overlap_pairs, n_negative_eigs_clipped,
        sum_clipped_magnitude.
    """
    cols = list(returns.columns)
    n = len(cols)
    corr = pd.DataFrame(np.eye(n), index=cols, columns=cols)
    low_overlap_pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            a = returns.iloc[:, i]
            b = returns.iloc[:, j]
            mask = a.notna() & b.notna()
            overlap = int(mask.sum())
            if overlap < min_overlap:
                c = 0.0
                low_overlap_pairs.append((cols[i], cols[j], overlap))
            else:
                av, bv = a[mask], b[mask]
                if av.std(ddof=0) == 0 or bv.std(ddof=0) == 0:
                    c = 0.0
                else:
                    c = float(np.corrcoef(av, bv)[0, 1])
                    if not np.isfinite(c):
                        c = 0.0
            corr.iloc[i, j] = c
            corr.iloc[j, i] = c

    eigs_raw = np.linalg.eigvalsh(corr.values)
    eigs_raw = np.sort(eigs_raw)[::-1]
    n_neg = int((eigs_raw < -1e-8).sum())
    clipped_mag = float(-eigs_raw[eigs_raw < 0].sum()) if n_neg else 0.0
    eigs = np.clip(eigs_raw, 0.0, None)
    # Renormalize so sum(eigs) == M exactly (trace-preserving), since clipping
    # negative eigenvalues to 0 without renormalizing would understate M_eff.
    if eigs.sum() > 0:
        eigs = eigs * (n / eigs.sum())

    diagnostics = {
        "n_series": n,
        "n_pairs": n * (n - 1) // 2,
        "n_low_overlap_pairs": len(low_overlap_pairs),
        "low_overlap_pairs_sample": low_overlap_pairs[:10],
        "n_negative_eigenvalues_clipped": n_neg,
        "clipped_eigenvalue_magnitude": clipped_mag,
    }
    return eigs, corr, diagnostics


def cheverud_meff(eigs: np.ndarray) -> float:
    m = len(eigs)
    if m <= 1:
        return float(m)
    var_lambda = float(np.sum((eigs - 1.0) ** 2) / (m - 1))
    meff = 1.0 + (m - 1) * (1.0 - var_lambda / m)
    return float(np.clip(meff, 1.0, m))


def nyholt_meff(eigs: np.ndarray) -> float:
    m = len(eigs)
    if m == 0:
        return 0.0
    excess = np.sum(np.where(eigs > 1.0, eigs - 1.0, 0.0))
    meff = m - excess
    return float(np.clip(meff, 1.0, m))


def li_ji_meff(eigs: np.ndarray) -> float:
    m = len(eigs)
    if m == 0:
        return 0.0
    contrib = np.where(eigs >= 1.0, 1.0, 0.0) + (eigs - np.floor(eigs))
    meff = float(np.sum(contrib))
    return float(np.clip(meff, 1.0, m))


def all_meff(returns: pd.DataFrame, min_overlap: int = 6) -> dict:
    """Convenience wrapper: returns M (raw count) and all three M_eff estimates."""
    m = returns.shape[1]
    if m == 0:
        return {"m": 0, "cheverud": 0.0, "nyholt": 0.0, "li_ji": 0.0, "diagnostics": {}}
    if m == 1:
        return {"m": 1, "cheverud": 1.0, "nyholt": 1.0, "li_ji": 1.0, "diagnostics": {"n_series": 1}}
    eigs, corr, diag = eigenvalues_of_correlation(returns, min_overlap=min_overlap)
    return {
        "m": m,
        "cheverud": round(cheverud_meff(eigs), 2),
        "nyholt": round(nyholt_meff(eigs), 2),
        "li_ji": round(li_ji_meff(eigs), 2),
        "diagnostics": diag,
    }
