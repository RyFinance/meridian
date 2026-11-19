"""Straddle (long) and iron-fly (short) trades at 09:31-09:35 entry, time exits 10:30 / 12:00 / 15:55.
Costs: half_spread = max($0.03, 2.5% px) per leg per side, COMM $0.65/contract/side (= 0.0065 per share-unit).
Both legs must print in the SAME minute for entry; exits use the last print at or before the exit minute (ffill)."""
from __future__ import annotations
import numpy as np
import pandas as pd

COMM = 0.0065
WING = 0.05          # iron-fly wings targeted at spot*(1 +/- 5%), nearest listed strike with a print at entry
ENTRY_WINDOW = range(1, 6)


def hs(px):
    return np.maximum(0.03, 0.025 * px)


def _px(day, typ, k, m):
    b = day.bars.get((typ, k))
    if b is None:
        return None
    s = b.close.reindex(range(0, 391)).ffill()
    v = s.get(m, np.nan)
    return float(v) if np.isfinite(v) else None


def trade(day, kind: str, exit_m: int):
    """kind: 'long_straddle' or 'short_fly'. Returns dict or None."""
    for m in ENTRY_WINDOW:
        sp = day.spot.get(m, np.nan)
        if not np.isfinite(sp):
            continue
        cs = {k for (t, k), b in day.bars.items() if t == "C" and m in b.index}
        ps = {k for (t, k), b in day.bars.items() if t == "P" and m in b.index}
        both = sorted(cs & ps)
        if not both:
            continue
        k0 = min(both, key=lambda k: abs(k - sp))
        if abs(k0 / sp - 1) > 0.03:
            continue
        c, p = _px(day, "C", k0, m), _px(day, "P", k0, m)
        if c is None or p is None:
            continue
        if kind == "long_straddle":
            cost = (c + hs(c)) + (p + hs(p)) + 2 * COMM
            cx, px_ = _px(day, "C", k0, exit_m), _px(day, "P", k0, exit_m)
            if cx is None or px_ is None:
                return None
            val = max(cx - hs(cx), 0) + max(px_ - hs(px_), 0) - 2 * COMM
            return {"date": day.d, "m": m, "exit_m": exit_m, "k0": k0, "spot": sp, "cost": cost,
                    "ret": float(val / cost - 1)}
        # short iron fly: short ATM straddle, long wings at spot*(1+/-WING)
        cw = sorted(k for (t, k), b in day.bars.items() if t == "C" and k > k0 and m in b.index)
        pw = sorted(k for (t, k), b in day.bars.items() if t == "P" and k < k0 and m in b.index)
        if not cw or not pw:
            continue
        kc = min(cw, key=lambda k: abs(k - sp * (1 + WING)))
        kp = min(pw, key=lambda k: abs(k - sp * (1 - WING)))
        wc, wp = _px(day, "C", kc, m), _px(day, "P", kp, m)
        if wc is None or wp is None:
            continue
        credit = (c - hs(c)) + (p - hs(p)) - (wc + hs(wc)) - (wp + hs(wp)) - 4 * COMM
        if credit <= 0:
            continue
        width = max(kc - k0, k0 - kp)
        maxrisk = width - credit
        if maxrisk <= 0:
            continue
        cc, cp = _px(day, "C", k0, exit_m), _px(day, "P", k0, exit_m)
        cwx, cpx = _px(day, "C", kc, exit_m), _px(day, "P", kp, exit_m)
        if None in (cc, cp, cwx, cpx):
            return None
        close_cost = (cc + hs(cc)) + (cp + hs(cp)) - (cwx - hs(cwx)) - (cpx - hs(cpx)) + 4 * COMM
        pnl = credit - close_cost
        return {"date": day.d, "m": m, "exit_m": exit_m, "k0": k0, "kc": kc, "kp": kp, "spot": sp,
                "credit": credit, "maxrisk": maxrisk, "ret": float(pnl / maxrisk)}
    return None


def run(days, kind, exit_m):
    rows = [t for t in (trade(d, kind, exit_m) for d in days) if t]
    return pd.DataFrame(rows).set_index("date") if rows else pd.DataFrame(columns=["ret"])


def st(x: pd.Series) -> dict:
    x = x.dropna()
    n = len(x)
    if n < 2:
        return {"n": n}
    sd = x.std()
    return {"n": n, "win": float((x > 0).mean()), "mean": float(x.mean()),
            "t": float(x.mean() / sd * np.sqrt(n)) if sd > 0 else 0.0,
            "avg_win": float(x[x > 0].mean()) if (x > 0).any() else 0.0,
            "avg_loss": float(x[x <= 0].mean()) if (x <= 0).any() else 0.0}
