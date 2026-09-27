"""Daily marked NAV for an engine ledger, with exactly research/pead_audit/mtm_audit.mtm_book's accounting.

`mark_book` is a numpy transcription of mtm_book (same path, same half-cost at entry and exit, same idle
cash at T-bills on NAV minus long market value, same exposure timing). It exists only for speed; it is
checked against mtm_book itself on the real ledger at every run (run.py) and in the tests.

One deliberate, pre-registered difference that never binds for the recorded book: a position still open
on the last replay date is marked at that date's close with no exit cost (mtm_book would receive a NaN
exit price there). The recorded sweep_wide_5p0 ledger has no position open at the end.

`exit_day_cash_fix=True` is the D3 sensitivity: mtm_book counts a position's capital as idle cash
(earning T-bills) on its exit day although it was invested overnight; the fix removes that.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research.pead_audit.mtm_audit import START_CAPITAL, mtm_book

ONE_WAY = 0.0005  # mtm_audit.ONE_WAY


def mark_book(trades: pd.DataFrame, px_mark: np.ndarray, col: dict[str, int], rf: np.ndarray,
              one_way: float = ONE_WAY, borrow: float = 0.0, cash_earns_rf: bool = True,
              exit_day_cash_fix: bool = False) -> dict[str, np.ndarray]:
    n = len(rf)
    pnl = np.zeros(n)
    long_mv = np.zeros(n)
    short_mv = np.zeros(n)
    if len(trades):
        for r in trades.itertuples(index=False):
            a = int(r.entry_i)
            closed = int(r.exit_i) >= 0
            b = int(r.exit_i) if closed else n - 1
            path = px_mark[a:b + 1, col[r.ticker]].copy()
            path[0] = r.fill_price
            if closed:
                path[-1] = r.exit_price
            mv = (r.notional / r.fill_price) * path
            dp = np.zeros(len(mv))
            dp[1:] = r.sign * np.diff(mv)
            dp = np.nan_to_num(dp)
            dp[0] -= r.notional * one_way
            if closed:
                dp[-1] -= mv[-1] * one_way
            pnl[a:b + 1] += dp
            if len(mv) > 1:
                held = np.nan_to_num(mv[:-2]) if not exit_day_cash_fix else np.nan_to_num(mv[:-1])
                tgt = long_mv if r.sign > 0 else short_mv
                tgt[a + 1:a + 1 + len(held)] += held
    nav = START_CAPITAL + np.cumsum(pnl)
    nav_prev = np.concatenate([[START_CAPITAL], nav[:-1]])
    interest = np.clip(nav_prev - long_mv, 0, None) * rf if cash_earns_rf else np.zeros(n)
    total = pnl + interest - short_mv * borrow / 252
    nav2 = START_CAPITAL + np.cumsum(total)
    ret = total / np.concatenate([[START_CAPITAL], nav2[:-1]])
    return {"ret": ret, "nav": nav2, "long_mv": long_mv, "short_mv": short_mv,
            "gross": (long_mv + short_mv) / np.concatenate([[START_CAPITAL], nav2[:-1]])}


def to_mtm_positions(trades: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Engine ledger -> the frame research.pead_audit.mtm_audit.positions() returns (closed trades only)."""
    t = trades[trades["exit_i"] >= 0]
    return pd.DataFrame({
        "ticker": t["ticker"].to_numpy(), "entry_date": dates[t["entry_i"].to_numpy()],
        "exit_date": dates[t["exit_i"].to_numpy()], "fill_price": t["fill_price"].to_numpy(),
        "exit_price": t["exit_price"].to_numpy(), "notional": t["notional"].to_numpy(),
        "sign": t["sign"].to_numpy(dtype=float), "shares": (t["notional"] / t["fill_price"]).to_numpy()})


def mark_with_mtm_audit(trades: pd.DataFrame, px_mark: pd.DataFrame, dates: pd.DatetimeIndex, rf: pd.Series) -> pd.DataFrame:
    """The reference implementation, called unchanged."""
    p = to_mtm_positions(trades, dates)
    return mtm_book(p, px_mark.reindex(columns=p["ticker"].unique()), dates, rf, ONE_WAY, 0.0, cash_earns_rf=True)
