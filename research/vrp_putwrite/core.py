"""Monthly SPY put writing: the volatility-insurance premium (research/vrp_putwrite/PLAN.md). Frozen by the plan.

* **Cycle k.** Enter on the first NYSE session after monthly expiry X_{k-1}, and sell one put on the
  next monthly expiry X_k. Monthly expiry is the third Friday; pre-2015 Saturday-dated expiries map to
  the preceding Friday.
* **Strike.** The highest put strike ≤ the raw SPY close on the entry day, within 2% of spot, that
  printed on the entry day (volume ≥ 1) for expiry X_k. If there is none, the cycle is skipped (cash).
* **Premium.** The entry-day close print. It is rejected if below intrinsic value or outside 0.2–10%
  of the strike; a rejected cycle is skipped.
* **Settlement.** Payoff = max(K − S_X, 0), with S_X the raw SPY close on X_k (last session ≤ X_k).
* **Excess return** on fully collateralised notional K = (premium − payoff − cost) / K. Collateral
  earns T-bills, so this is the return in excess of cash.
* **Costs.** Base 1%, stress 5% of the premium (entry spread; expiry is cash-settled at intrinsic).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MONEY_TOL = 0.02
COSTS = {"gross": 0.0, "base": 0.01, "stress": 0.05}


def load_spy_raw() -> pd.DataFrame:
    d = pd.read_parquet(ROOT / "data" / "etf_hybrids" / "SPY.parquet")
    d = d.set_index(pd.to_datetime(d["date"])).sort_index()
    return d[["close", "adj_close"]]


def monthly_expiries(exp: pd.Series) -> pd.DatetimeIndex:
    e = pd.to_datetime(pd.Series(exp.unique()))
    fri = e[(e.dt.dayofweek == 4) & e.dt.day.between(15, 21)]
    sat = e[(e.dt.dayofweek == 5) & e.dt.day.between(16, 22)]
    thu = e[(e.dt.dayofweek == 3) & e.dt.day.between(14, 20)]          # Good-Friday weeks
    thu = [t for t in thu if (t + pd.Timedelta(days=1)) not in set(fri)]
    return pd.DatetimeIndex(sorted(set(fri) | set(sat - pd.Timedelta(days=1)) | set(thu)))


def load_puts() -> pd.DataFrame:
    o = pd.read_parquet(ROOT / "data" / "lse" / "options_etf_1d" / "SPY.parquet",
                        columns=["ts", "expiry", "opt_type", "strike", "close", "volume"])
    o = o[o["opt_type"] == "P"].copy()
    o["d"] = o["ts"].dt.tz_localize(None).dt.normalize()
    ex = pd.to_datetime(o["expiry"])
    o["exp_fri"] = ex.where(ex.dt.dayofweek != 5, ex - pd.Timedelta(days=1))
    return o[["d", "exp_fri", "strike", "close", "volume"]]


def cycles(puts: pd.DataFrame, spy: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    xs = monthly_expiries(puts["exp_fri"])
    sess = spy.index
    rows = []
    for x_prev, x in zip(xs[:-1], xs[1:]):
        e_pos = sess.searchsorted(x_prev, side="right")
        if e_pos >= len(sess):
            break
        e = sess[e_pos]
        if e < pd.Timestamp(start) or e > pd.Timestamp(end):
            continue
        x_sess = sess[sess <= x]
        if len(x_sess) == 0 or x_sess[-1] <= e:
            continue
        xs_day = x_sess[-1]
        S = float(spy.loc[e, "close"])
        cand = puts[(puts["d"] == e) & (puts["exp_fri"] == x) & (puts["volume"] >= 1)
                    & (puts["strike"] <= S) & (puts["strike"] >= S * (1 - MONEY_TOL))]
        row = {"entry": e, "expiry": xs_day, "spot": S, "spot_x": float(spy.loc[xs_day, "close"]),
               "adj_ret_spy": float(spy.loc[xs_day, "adj_close"] / spy.loc[e, "adj_close"] - 1),
               "strike": np.nan, "premium": np.nan, "status": "no_print"}
        if len(cand):
            best = cand.sort_values(["strike", "volume"]).iloc[-1]
            K, P = float(best["strike"]), float(best["close"])
            if P < max(K - S, 0.0) or not (0.002 * K <= P <= 0.10 * K):
                row.update(strike=K, premium=P, status="bad_print")
            else:
                row.update(strike=K, premium=P, status="ok")
        rows.append(row)
    return pd.DataFrame(rows)


def excess_returns(cy: pd.DataFrame, cost_frac: float) -> pd.Series:
    ok = cy["status"] == "ok"
    payoff = np.maximum(cy["strike"] - cy["spot_x"], 0.0)
    r = ((cy["premium"] - payoff - cost_frac * cy["premium"]) / cy["strike"]).where(ok, 0.0)
    return pd.Series(r.to_numpy(), index=cy["entry"])
