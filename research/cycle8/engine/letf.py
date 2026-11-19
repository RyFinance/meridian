"""Daily-reset leveraged ETF simulation (FRAMEWORK §4.2)."""
from __future__ import annotations

import numpy as np
import pandas as pd

SPEC = {  # k, financing spread over T-bill (annual), expense ratio (annual)
    "SSO": (2, 0.0050, 0.0089, "eq"),
    "UPRO": (3, 0.0050, 0.0091, "eq"),
    "UBT": (2, 0.0025, 0.0095, "tsy"),
    "TMF": (3, 0.0025, 0.0106, "tsy"),
}


def letf_daily(index_ret: pd.Series, rf_daily: pd.Series, k: int, spread: float, er: float) -> pd.Series:
    """Daily ETF return = k r - (k - 1)(rf + spread/252) - er/252. rf_daily is the daily T-bill return."""
    rf = rf_daily.reindex(index_ret.index).ffill().fillna(0.0)
    return k * index_ret - (k - 1) * (rf + spread / 252) - er / 252


def to_monthly(daily: pd.Series) -> pd.Series:
    return (1 + daily).groupby(daily.index.to_period("M")).prod().sub(1).to_timestamp("M")
