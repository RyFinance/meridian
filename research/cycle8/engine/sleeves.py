"""Build CAD sleeve returns (FRAMEWORK §2, ADDENDUM_1 §5) from data/cycle8/proc.

Monthly frame columns (all CAD simple returns unless noted):
  EQ_G_tfsa, EQ_G_margin, EQ_GH_tfsa, EQ_GH_margin, BOND, GOLD, TREND, CASH,
  X_TREND (overlay excess, USD P&L), X_BOND (overlay excess), MRATE (margin cost for the month), RF_USD,
  plus the four equity components in CAD for daily-path reconstruction.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
PROC = ROOT / "data" / "cycle8" / "proc"

EQ_W = {"US": 0.45, "CA": 0.25, "DXNA": 0.25, "EM": 0.05}
FEE = {"EQ": 0.0020, "BOND": 0.0010, "GOLD": 0.0025, "TREND_DRAG": 0.020, "HEDGE": 0.0010}
WHT = {"US": 0.15, "DXNA": 0.10, "EM": 0.10}
DY_CONST = {"DXNA": 0.030, "EM": 0.025}
MARGIN_SPREAD = 0.015


def _me(df):
    df = df.copy()
    df.index = pd.DatetimeIndex(df.index).to_period("M").to_timestamp("M")
    df.index.name = "date"
    return df


def load(proc: Path = PROC, root: Path | None = None) -> dict:
    p = Path(proc)
    d = {}
    for name in ["eq_monthly", "fx_monthly", "cpi_ca_monthly", "rates_monthly", "bond_monthly", "gold_monthly",
                 "trend_monthly"]:
        d[name] = _me(pd.read_parquet(p / f"{name}.parquet"))
    for name in ["eq_daily", "fx_daily", "bond_daily", "gold_daily"]:
        f = p / f"{name}.parquet"
        if f.exists():
            x = pd.read_parquet(f)
            x.index = pd.DatetimeIndex(x.index)
            d[name] = x
    return d


def gold_level(gd: pd.DataFrame) -> pd.Series:
    """World Bank monthly-average gold to 2000-07, COMEX front-month month-end from 2000-08 (ADDENDUM_1 §10)."""
    wb = gd["gold_usd_wb_avg"].loc[:"2000-07-31"]
    fut = gd["gold_usd_gcf_me"].loc["2000-08-31":]
    return pd.concat([wb, fut]).dropna()


def monthly_sleeves(d: dict) -> pd.DataFrame:
    eq, fx, rt, bd = d["eq_monthly"], d["fx_monthly"], d["rates_monthly"], d["bond_monthly"]
    gd, tr = d["gold_monthly"], d["trend_monthly"]
    idx = eq.index
    usdcad = fx["USDCAD"].reindex(idx)
    fxr = usdcad / usdcad.shift(1) - 1                      # CAD return of holding 1 USD
    rf_cad = (rt["tbill_cad"].shift(1) / 12).reindex(idx)
    rf_usd = rt["rf_usd_ret"].reindex(idx)
    mrate = ((rt["policy_cad"].shift(1) + MARGIN_SPREAD) / 12).reindex(idx)
    # --- equity components in USD with backfill rules (FRAMEWORK §2)
    us = eq["US_usd"]
    ca = eq["CA_usd"].where(eq["CA_usd"].notna(), us)
    dx = eq["DXNA_usd"].where(eq["DXNA_usd"].notna(), us)
    em = eq["EM_usd"].where(eq["EM_usd"].notna(), dx)
    comp_usd = pd.DataFrame({"US": us, "CA": ca, "DXNA": dx, "EM": em})
    comp_cad = (1 + comp_usd).mul(1 + fxr, axis=0) - 1
    dp_us = eq["US_dp"].reindex(idx).ffill()
    wht = pd.DataFrame({"US": WHT["US"] * dp_us / 12, "CA": 0.0, "DXNA": WHT["DXNA"] * DY_CONST["DXNA"] / 12,
                        "EM": WHT["EM"] * DY_CONST["EM"] / 12}, index=idx)
    w = pd.Series(EQ_W)
    fee_eq = FEE["EQ"] / 12
    eqg = (comp_cad * w).sum(1, min_count=4)
    eqg_wht = (wht * w).sum(1)
    # hedged: foreign (non-CA) components earn USD return + (rf_cad - rf_usd) - hedge cost
    hed = comp_cad.copy()
    for c in ["US", "DXNA", "EM"]:
        hed[c] = comp_usd[c] + (rf_cad - rf_usd) - FEE["HEDGE"] / 12
    eqgh = (hed * w).sum(1, min_count=4)
    out = pd.DataFrame(index=idx)
    out["EQ_G_margin"] = eqg - fee_eq
    out["EQ_G_tfsa"] = eqg - fee_eq - eqg_wht
    out["EQ_GH_margin"] = eqgh - fee_eq
    out["EQ_GH_tfsa"] = eqgh - fee_eq - eqg_wht
    # --- bonds: 60% Canada 10Y (CAD) + 40% US 10Y hedged
    b = 0.6 * bd["CA10_ret"].reindex(idx) + 0.4 * (bd["US10_ret"].reindex(idx) + rf_cad - rf_usd)
    out["BOND"] = b - FEE["BOND"] / 12
    # --- gold (USD level -> CAD return)
    g = gold_level(gd).reindex(idx)
    out["GOLD"] = (1 + g / g.shift(1) - 1) * (1 + fxr) - 1 - FEE["GOLD"] / 12
    # --- trend: funded USD sleeve -> CAD
    tx = tr["tsmom_excess"].reindex(idx)
    out["TREND"] = (1 + rf_usd + tx - FEE["TREND_DRAG"] / 12) * (1 + fxr) - 1
    out["X_TREND"] = tx - FEE["TREND_DRAG"] / 12
    out["X_BOND"] = out["BOND"] - rf_cad
    out["CASH"] = rf_cad
    out["MRATE"] = mrate
    out["RF_USD"] = rf_usd
    out["FXR"] = fxr
    for c in comp_cad:
        out[f"C_{c}"] = comp_cad[c]
    return out
