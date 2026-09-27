"""Controls (FRAMEWORK §4, A4 §1, A5 §D).

- always-long (TSMOM): same instruments and scaling with sign forced +1 (styles.tsmom_weights(force_long=True));
  active = book - mbar * control, mbar = mean over the window of (book net exposure / control net exposure).
- random-rank placebo (rank styles): mean of n seeded books whose signal is iid uniform on the SAME eligible
  set, pushed through the SAME weight builder, portfolio, lag and costs.
- calendar-shuffled placebo (SEAS): mean of n seeded books built from month-label-permuted histories.
Seeds: book b uses numpy default_rng([seed, b]).
"""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

from research.amendment4.active import active_series

from . import styles


def exposure_ratio(book_net_exposure: pd.Series, control_net_exposure: pd.Series) -> pd.Series:
    c = control_net_exposure.reindex(book_net_exposure.index)
    return (book_net_exposure / c.where(c > 0))


def matched_active(book: pd.Series, control: pd.Series, ratio: pd.Series, window: pd.Index | None = None):
    """A4 active_series on the window: book - mean(ratio) * control. Returns (active, mbar)."""
    idx = book.index.intersection(control.index)
    if window is not None:
        idx = idx.intersection(window)
    b, c, e = book.reindex(idx), control.reindex(idx), ratio.reindex(idx)
    mbar = float(np.nanmean(e.to_numpy())) if len(idx) else float("nan")
    e_full = np.full(len(idx), mbar)
    act = active_series(b.to_numpy(), e_full, c.to_numpy())
    return pd.Series(act, index=idx), mbar


def random_rank_books(eligible: pd.DataFrame, builder: Callable[[pd.DataFrame], pd.DataFrame],
                      evaluate: Callable[[pd.DataFrame], dict], *, n_books: int, seed: int) -> dict:
    """builder(signal) -> W ; evaluate(W) -> {name: Series}. Returns {name: mean Series over books}."""
    acc: dict[str, list] = {}
    for b in range(int(n_books)):
        rng = np.random.default_rng([int(seed), b])
        sig = pd.DataFrame(rng.random(eligible.shape), index=eligible.index, columns=eligible.columns)
        sig = sig.where(eligible)
        for k, s in evaluate(builder(sig)).items():
            acc.setdefault(k, []).append(s)
    return {k: pd.concat(v, axis=1).mean(axis=1) for k, v in acc.items()}


def calendar_shuffle_books(mret: pd.DataFrame, signal_fn: Callable[[pd.DataFrame], pd.DataFrame],
                           builder: Callable[[pd.DataFrame], pd.DataFrame],
                           evaluate: Callable[[pd.DataFrame], dict], *, n_books: int, seed: int) -> dict:
    acc: dict[str, list] = {}
    for b in range(int(n_books)):
        rng = np.random.default_rng([int(seed), b])
        sig = signal_fn(styles.permute_month_labels(mret, rng))
        for k, s in evaluate(builder(sig)).items():
            acc.setdefault(k, []).append(s)
    return {k: pd.concat(v, axis=1).mean(axis=1) for k, v in acc.items()}
