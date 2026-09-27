"""Gross paper-fidelity shadow and net implementable series (FRAMEWORK §2).

W (month-end t x market) is formed at the close of t.
- Gross shadow, month t+1: sum_i W_{t,i} R^cal_{t+1,i}, R^cal = calendar-month compounded daily excess return
  (month-end close to month-end close). No costs.
- Net, holding period t+1: sum_i W_{t,i} R^net_{t+1,i} - cost_{t+1}, R^net from the close of each instrument's
  first session of month t+1 to the close of its first session of month t+2 (panel.net_period_returns).
  Traded notional at the execution close: |W_{t,i} - W~_{t-1,i}|, W~ = previous weights drifted by their holding
  period return (drift=True) or undrifted (drift=False). cost = sum_i traded_i * c_class(i) (per side).
  Stress: cost multiplied by the stress multiplier.
A held position whose period return is missing contributes zero and is COUNTED (``unpriced``) -- never silent.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _align(W: pd.DataFrame, R: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    idx = W.index.union(R.index)
    idx = pd.period_range(idx.min(), idx.max(), freq="M")
    return W.reindex(index=idx, columns=R.columns).fillna(0.0), R.reindex(index=idx)


def held_weights(W: pd.DataFrame, R: pd.DataFrame) -> pd.DataFrame:
    """Weights held during period m = W formed at m-1."""
    Wa, Ra = _align(W, R)
    return Wa.shift(1).fillna(0.0)


def gross_shadow(W: pd.DataFrame, R_cal: pd.DataFrame, defined: pd.Series) -> pd.DataFrame:
    Wa, Ra = _align(W, R_cal)
    Wl = Wa.shift(1).fillna(0.0)
    held = Wl != 0
    ret = (Wl * Ra.fillna(0.0)).sum(axis=1)
    unpriced = (held & Ra.isna()).sum(axis=1)
    d = defined.reindex(Wa.index, fill_value=False).shift(1, fill_value=False).astype(bool)
    out = pd.DataFrame({"ret": ret, "n_held": held.sum(axis=1), "unpriced": unpriced})
    return out[d & Ra.notna().any(axis=1)]


def net_implementable(W: pd.DataFrame, R_net: pd.DataFrame, cost_rate: pd.Series, defined: pd.Series, *,
                      cost_multiplier: float = 1.0, drift: bool = True) -> pd.DataFrame:
    """cost_rate: per-side decimal cost per unit traded notional, indexed by market_id."""
    Wa, Ra = _align(W, R_net)
    Wl = Wa.shift(1).fillna(0.0)
    R0 = Ra.fillna(0.0)
    gross_ret = (Wl * R0).sum(axis=1)
    prev = Wl.shift(1).fillna(0.0)
    if drift:
        denom = (1.0 + gross_ret.shift(1).fillna(0.0))
        prev = (prev * (1.0 + R0.shift(1).fillna(0.0))).div(denom.where(denom > 0), axis=0).fillna(0.0)
    traded = (Wl - prev).abs()
    c = cost_rate.reindex(Wa.columns).fillna(np.nan)
    if c.isna().any():
        raise ValueError(f"no cost rate for markets {list(c[c.isna()].index)}")
    cost = (traded * c).sum(axis=1) * float(cost_multiplier)
    turnover = traded.sum(axis=1)
    held = Wl != 0
    out = pd.DataFrame({"ret": gross_ret - cost, "ret_before_cost": gross_ret, "cost": cost,
                        "turnover": turnover, "net_exposure": Wl.sum(axis=1), "gross_exposure": Wl.abs().sum(axis=1),
                        "n_held": held.sum(axis=1), "unpriced": (held & Ra.isna()).sum(axis=1)})
    d = defined.reindex(Wa.index, fill_value=False).shift(1, fill_value=False).astype(bool)
    keep = (d & Ra.notna().any(axis=1)) | (turnover > 0)
    return out[keep]


def asset_pnl(W: pd.DataFrame, R: pd.DataFrame) -> pd.DataFrame:
    """Per-asset monthly contribution W_{t-1,i} R_{t,i} (before costs)."""
    Wa, Ra = _align(W, R)
    return Wa.shift(1).fillna(0.0) * Ra.fillna(0.0)


def weights_long(W: pd.DataFrame) -> pd.DataFrame:
    s = W.stack()
    s = s[s != 0]
    df = s.rename("weight").reset_index()
    df.columns = ["signal_month", "market_id", "weight"]
    df["signal_month"] = df["signal_month"].astype(str)
    return df
