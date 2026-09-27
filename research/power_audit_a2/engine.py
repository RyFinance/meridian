"""Independent MC engine for auditing the quant_v7 dev/validation gates (cycle 5, Program A2).

Written from scratch; does not import research/power.

Core pieces
-----------
* circular block bootstrap (CBB), mean-centred, one-sided p for H0: mean <= 0.
  Vectorised with a block-start count matrix so the bootstrap means are a BLAS matmul:
      m*_{w,b} = (1/nb) * sum_j bm_{w,j} * C_{b,j}
  where bm are the n circular block means of world w and C counts how often block start j is drawn
  in replicate b. A fresh C is drawn for every chunk of worlds.
* gate evaluation for the development gate, the Amendment-3 validation gate and the old 0.75 gate.
"""
from __future__ import annotations

import numpy as np

B_DEFAULT = 999


def block_len(n: int) -> int:
    return max(2, int(round(n ** (1.0 / 3.0))))


def _count_matrix(n: int, b: int, B: int, rng: np.random.Generator) -> np.ndarray:
    nb = int(np.ceil(n / b))
    starts = rng.integers(0, n, size=(B, nb))
    flat = (np.arange(B)[:, None] * n + starts).ravel()
    C = np.bincount(flat, minlength=B * n).reshape(B, n).astype(np.float64)
    return C, nb


def circ_block_means(x: np.ndarray, b: int) -> np.ndarray:
    """x: (W, n). Returns (W, n) circular block means starting at each index."""
    W, n = x.shape
    xc = np.concatenate([x, x[:, : b - 1]], axis=1)
    cs = np.concatenate([np.zeros((W, 1)), np.cumsum(xc, axis=1)], axis=1)
    return (cs[:, b : b + n] - cs[:, :n]) / b


def cbb_pvalue(x: np.ndarray, rng: np.random.Generator, b: int | None = None, B: int = B_DEFAULT,
               chunk: int = 512) -> np.ndarray:
    """One-sided mean-centred circular-block-bootstrap p-value of H0: E[x] <= 0 for each row.

    p = (1 + #{m* - xbar >= xbar}) / (B + 1)
    """
    x = np.asarray(x, dtype=np.float64)
    W, n = x.shape
    if b is None:
        b = block_len(n)
    out = np.empty(W)
    for s in range(0, W, chunk):
        xs = x[s : s + chunk]
        xbar = xs.mean(axis=1)
        if b == 1:
            bm = xs
        else:
            bm = circ_block_means(xs, b)
        C, nb = _count_matrix(n, b, B, rng)
        mstar = bm @ C.T / nb  # (w, B)
        # circular => bootstrap expectation of the mean of block means equals xbar exactly only when
        # nb*b == n; centre on the bootstrap-population mean of block means (which is xbar) anyway.
        centre = bm.mean(axis=1)
        cnt = ((mstar - centre[:, None]) >= xbar[:, None]).sum(axis=1)
        out[s : s + chunk] = (1.0 + cnt) / (B + 1.0)
    return out


def ann_sharpe(x: np.ndarray, ppy: float) -> np.ndarray:
    sd = x.std(axis=1, ddof=1)
    return x.mean(axis=1) / sd * np.sqrt(ppy)


def stage_stats(net: np.ndarray, stress: np.ndarray, ppy: float, rng, b=None, B=B_DEFAULT) -> dict:
    return {
        "S": ann_sharpe(net, ppy),
        "p": cbb_pvalue(net, rng, b=b, B=B),
        "stress_pos": stress.mean(axis=1) > 0,
        "T": net.shape[1] / ppy,
    }


def dev_pass(st: dict, k: int, alpha: float = 0.05) -> np.ndarray:
    c = 2.4 if k >= 4 else 1.8
    return (st["S"] >= c / np.sqrt(st["T"])) & (st["p"] < alpha / k) & st["stress_pos"]


def val_new_pass(st: dict, k_val, alpha: float = 0.05, floor: float = 0.30) -> np.ndarray:
    k_val = np.maximum(np.asarray(k_val), 1)
    return (st["p"] < alpha / k_val) & st["stress_pos"] & (st["S"] >= floor)


def val_old_pass(st: dict, k: int, alpha: float = 0.05) -> np.ndarray:
    return (st["S"] >= 0.75) & st["stress_pos"] & (st["p"] < alpha / k)


def binom_se(p: float, n: int) -> float:
    return float(np.sqrt(max(p * (1 - p), 1e-12) / n))
