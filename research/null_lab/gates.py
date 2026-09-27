"""The project's decision gates, applied to batches of null-world return series.

  dev gate  : net base excess Sharpe >= dev_sharpe AND stress mean excess > 0
  val gate  : net base excess Sharpe >= val_sharpe AND stress mean excess > 0
              AND one-sided circular-block bootstrap p < alpha / k
  pipeline  : dev gate, then val gate on the later, non-overlapping window

The bootstrap p is the project's own procedure (research/macro_surprise/evaluate.block_bootstrap_p
and research/options_signals/evaluate.block_bootstrap_p are the same algorithm with different
defaults): centre the series, draw `draws` sets of circular blocks with a FIXED seed, and report
(#{resampled mean >= observed mean} + 1) / (draws + 1). `BootstrapP` computes the identical number
for many series at once from block sums (verified equal to the project function in the tests).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from research.null_lab.engines import sharpe


class BootstrapP:
    """Exact batched replica of the project's block_bootstrap_p for a fixed (n, block, draws, seed)."""

    def __init__(self, n: int, block: int, draws: int, seed: int):
        self.n, self.block, self.draws = n, block, draws
        rng = np.random.default_rng(seed)
        nb = int(np.ceil(n / block))
        self.starts = rng.integers(0, n, size=(draws, nb))
        self.nb = nb
        self.tail = n - (nb - 1) * block          # length of the truncated last block

    def _circ_sums(self, c: np.ndarray, length: int) -> np.ndarray:
        """(W, n) circular rolling sums of `length` starting at each index."""
        ext = np.concatenate([c, c[:, :length]], axis=1)
        cs = np.concatenate([np.zeros((c.shape[0], 1)), np.cumsum(ext, axis=1)], axis=1)
        return cs[:, length:length + self.n] - cs[:, :self.n]

    def pvalues(self, x: np.ndarray) -> np.ndarray:
        x = np.atleast_2d(np.asarray(x, float))
        if x.shape[1] != self.n:
            raise ValueError("length mismatch")
        mu = x.mean(axis=1, keepdims=True)
        c = x - mu
        full = self._circ_sums(c, self.block)
        part = self._circ_sums(c, self.tail)
        out = np.empty(x.shape[0])
        for i in range(x.shape[0]):
            s = full[i][self.starts[:, :-1]].sum(axis=1) + part[i][self.starts[:, -1]]
            means = s / self.n
            out[i] = (np.sum(means >= mu[i, 0]) + 1) / (self.draws + 1)
        return out


@dataclass
class Gate:
    dev_sharpe: float = 0.50
    val_sharpe: float = 0.75
    alpha: float = 0.05
    k: int = 4                      # Bonferroni divisor (candidates in the family)
    block: int = 21                 # bootstrap block, in return periods
    draws: int = 5000
    seed: int = 20260923

    def __post_init__(self):
        self._boot: dict[int, BootstrapP] = {}

    def boot(self, n: int) -> BootstrapP:
        if n not in self._boot:
            self._boot[n] = BootstrapP(n, self.block, self.draws, self.seed)
        return self._boot[n]

    def evaluate(self, out: dict, periods: int, windows=("dev", "val"), horizons=()) -> dict:
        """out: {(window, cost): (W, T)} -> per-world Sharpes, stress means, p-values and pass flags.
        `horizons` (years): also Sharpe / stress mean over the first h years of each window."""
        res = {}
        for wn in windows:
            b, s = out[(wn, "base")], out[(wn, "stress")]
            res[f"sr_{wn}"] = sharpe(b, periods)
            res[f"stress_mean_{wn}"] = s.mean(axis=1) * periods
            res[f"years_{wn}"] = b.shape[1] / periods
            for h in horizons:
                n = int(round(h * periods))
                if n <= b.shape[1]:
                    res[f"sr_{wn}_h{h}"] = sharpe(b[:, :n], periods)
                    res[f"stress_mean_{wn}_h{h}"] = s[:, :n].mean(axis=1) * periods
        res["pass_dev"] = (res["sr_dev"] >= self.dev_sharpe) & (res["stress_mean_dev"] > 0)
        if "val" in windows:
            cand = (res["sr_val"] >= self.val_sharpe) & (res["stress_mean_val"] > 0)
            p = np.full(len(cand), np.nan)
            if cand.any():
                p[cand] = self.boot(out[("val", "base")].shape[1]).pvalues(out[("val", "base")][cand])
            res["p_val"] = p
            res["pass_val"] = cand & (np.nan_to_num(p, nan=1.0) < self.alpha / self.k)
            res["pass_both"] = res["pass_dev"] & res["pass_val"]
        return res
