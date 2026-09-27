"""Monthly account simulation of a vehicle target-weight path (constant capital, next-session execution).

Conventions (all declared in the variant specs):
- Constant capital A in the funding currency F (CAD or USD): each month every position is re-sized against A, so
  integer rounding granularity is stationary; the month's P&L / A is the return (profits withdrawn, losses topped
  up). ``A=None`` is not allowed; the unrounded ("ideal") path uses the same A without rounding or minimum tickets.
- Month h (holding period from the close of the vehicle's first session of h to that of h+1, engine panel
  convention): target y_{h,v} (fraction of NAV) -> quantity n = y A_c / U (A_c = A in the vehicle currency at the
  USD/CAD rate of month-end h-1; U = unit notional: ETF as-traded close at the execution session, future
  multiplier x price level at month-end h-1); rounded paths use round-half-away-from-zero; achieved weight
  y~ = n U / A_c.
- Return in F: ETF  y~ (1+R_c)(1+g_F) - y~ ; future y~ r_excess (1+g_F) (futures use no cash);
  g_F = USD/CAD holding-period translation for a vehicle whose currency differs from F.
- Cash C = 1 - sum_ETF y~ (short proceeds included): C >= 0 earns C max(0, r_F - cash_spread)/12, C < 0 pays
  C (r_F + financing_spread)/12, r_F = funding-currency 3m rate at month-end h-1 (A5 §E rule).
- Costs (fractions of A): half-spread x spread_mult x traded notional; commissions per order (per share / per
  contract, min ticket and cap on rounded paths only); CAD/USD conversion rate x traded notional of every ETF not
  in F, and x |futures P&L| when F != USD; futures rolls = two legs (commission + half-spread each) on |n| in roll
  months; ETF borrow fee_ann/12 on short notional; withholding rate(account, tax class) x long y~ x distribution
  yield over the holding period (creditable amounts in a taxable account are reported, not charged).
- excess = total - r_F/12.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

COLS = ["total", "excess", "rf", "asset_ret", "cash_interest", "cost_spread", "cost_commission", "cost_fx",
        "cost_roll", "withholding", "withholding_creditable", "borrow", "turnover", "gross", "net", "cash_frac",
        "etf_gross", "fut_gross", "round_abs_err", "n_target", "n_zero_held", "n_held"]


def round_half_away(x: np.ndarray) -> np.ndarray:
    return np.sign(x) * np.floor(np.abs(x) + 0.5)


def _fx_to(c: str, F: str, L: float) -> float:
    """Units of F per unit of c at USD/CAD level L (CAD per USD)."""
    if c == F:
        return 1.0
    if c == "USD" and F == "CAD":
        return L
    if c == "CAD" and F == "USD":
        return 1.0 / L
    raise ValueError(f"unsupported currency pair {c}->{F}")


def _g(c: str, F: str, g: float) -> float:
    """Holding-period translation return of currency c into F (g = USD/CAD change, CAD per USD)."""
    if c == F:
        return 0.0
    if c == "USD" and F == "CAD":
        return g
    return 1.0 / (1.0 + g) - 1.0


def _commission(model: dict, qty: float, notional: float, rounded: bool) -> float:
    if qty == 0:
        return 0.0
    if model["type"] == "per_contract":
        return abs(qty) * model["per_contract"]
    c = abs(qty) * model["per_share"]
    if rounded:
        c = max(c, model["min"])
        c = min(c, model["max_pct"] * abs(notional))
    return c


def simulate(Y: pd.DataFrame, mkt: dict, meta: dict, acct: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Y: month x vehicle targets. mkt: {"R": month x vehicle local return (futures: excess), "U": unit notional,
    "dy": distribution yield, "g": Series USD/CAD holding-period change, "L": Series USD/CAD at month-end h-1,
    "r": {"USD": Series, "CAD": Series} annual rates at month-end h-1}. meta: vehicle -> dict(kind, ccy,
    half_spread_bp, commission, tax_class, borrow_fee_ann, tick_value, roll_months). acct: F, capital, rounded,
    account, withholding{class: rate}, creditable{class: rate}, conv_rate, cash_spread, financing_spread,
    spread_mult, borrow_mult. Returns (monthly frame, held quantities frame)."""
    F, A, rounded = acct["F"], float(acct["capital"]), bool(acct["rounded"])
    wht, cred = acct.get("withholding", {}), acct.get("creditable", {})
    vehicles = list(Y.columns)
    R, U, DY = (mkt[k].reindex(index=Y.index, columns=vehicles) for k in ("R", "U", "dy"))
    Uff = U.ffill()
    g = mkt["g"].reindex(Y.index)
    L = mkt["L"].reindex(Y.index)
    rF = mkt["r"][F].reindex(Y.index)
    n_prev = {v: 0.0 for v in vehicles}
    rows, qrows = [], []
    for h in Y.index:
        Lh = float(L.get(h, np.nan))
        gh = float(g.get(h, np.nan))
        if not math.isfinite(Lh):
            raise ValueError(f"no USD/CAD level for {h}")
        if not math.isfinite(gh):
            gh = 0.0 if F == "USD" and all(meta[v]["ccy"] == "USD" for v in vehicles) else np.nan
        rec = {k: 0.0 for k in COLS}
        qty = {}
        for v in vehicles:
            m = meta[v]
            y = float(Y.at[h, v])
            c = m["ccy"]
            Ac = A / _fx_to(c, F, Lh)                      # capital in vehicle currency
            u = float(U.at[h, v]) if pd.notna(U.at[h, v]) else float(Uff.at[h, v]) if pd.notna(Uff.at[h, v]) else np.nan
            if y != 0 and not (math.isfinite(u) and u > 0):
                raise ValueError(f"target on {v} in {h} without a unit notional")
            n = 0.0 if y == 0 else y * Ac / u
            if rounded:
                n = float(round_half_away(np.array([n]))[0])
            ya = n * u / Ac if n != 0 else 0.0
            dq = n - n_prev[v]
            trade_notional = abs(dq) * u if dq != 0 else 0.0
            tfrac = trade_notional / Ac if dq != 0 else 0.0
            rec["turnover"] += tfrac
            rec["round_abs_err"] += abs(ya - y)
            if y != 0:
                rec["n_target"] += 1
                if n == 0:
                    rec["n_zero_held"] += 1
            if n != 0:
                rec["n_held"] += 1
            spread = m.get("half_spread_bp", 0.0) / 1e4 * acct["spread_mult"]
            gF = _g(c, F, gh) if c != F else 0.0
            if m["kind"] == "future":
                rec["cost_spread"] += acct["spread_mult"] * 0.5 * m["tick_value"] * abs(dq) / Ac
                rec["cost_commission"] += _commission(m["commission"], dq, trade_notional, rounded) / Ac
                if n != 0 and h.month in m.get("roll_months", []):
                    legs = 2 * abs(n)
                    rec["cost_roll"] += (legs * m["commission"]["per_contract"]
                                         + acct["spread_mult"] * 0.5 * m["tick_value"] * legs) / Ac
                if ya != 0 and pd.isna(R.at[h, v]):
                    raise ValueError(f"held {v} in {h} without a return")
                r = float(R.at[h, v]) if pd.notna(R.at[h, v]) else 0.0
                pnl = ya * r * (1.0 + gF)
                rec["asset_ret"] += pnl
                if c != F:
                    rec["cost_fx"] += acct["conv_rate"] * abs(pnl)
                rec["fut_gross"] += abs(ya)
            else:
                rec["cost_spread"] += spread * tfrac
                rec["cost_commission"] += _commission(m["commission"], dq, trade_notional, rounded) / Ac
                if c != F:
                    rec["cost_fx"] += acct["conv_rate"] * tfrac
                r = float(R.at[h, v]) if pd.notna(R.at[h, v]) else 0.0
                if ya != 0 and pd.isna(R.at[h, v]):
                    raise ValueError(f"held {v} in {h} without a return")
                rec["asset_ret"] += ya * ((1.0 + r) * (1.0 + gF) - 1.0)
                rec["etf_gross"] += abs(ya)
                rec["net"] += ya
                if ya > 0:
                    dy = float(DY.at[h, v]) if pd.notna(DY.at[h, v]) else 0.0
                    rec["withholding"] += wht.get(m["tax_class"], 0.0) * ya * dy
                    rec["withholding_creditable"] += cred.get(m["tax_class"], 0.0) * ya * dy
                if ya < 0:
                    rec["borrow"] += m["borrow_fee_ann"] * acct.get("borrow_mult", 1.0) / 12.0 * (-ya)
            qty[v] = n
            n_prev[v] = n
        rec["gross"] = rec["etf_gross"] + rec["fut_gross"]
        rh = float(rF.get(h, np.nan))
        C = 1.0 - rec["net"]
        rec["cash_frac"] = C
        if C >= 0:
            rec["cash_interest"] = C * max(0.0, rh - acct["cash_spread"]) / 12.0
        else:
            rec["cash_interest"] = C * (rh + acct["financing_spread"]) / 12.0
        rec["rf"] = rh / 12.0
        costs = rec["cost_spread"] + rec["cost_commission"] + rec["cost_fx"] + rec["cost_roll"]
        rec["total"] = rec["asset_ret"] + rec["cash_interest"] - costs - rec["withholding"] - rec["borrow"]
        rec["excess"] = rec["total"] - rec["rf"]
        rec["month"] = h
        rows.append(rec)
        qrows.append({"month": h, **qty})
    out = pd.DataFrame(rows).set_index("month")[COLS]
    return out, pd.DataFrame(qrows).set_index("month")
