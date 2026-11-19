"""Defined-risk credit spreads directed by BTC's off-hours move.

If BTC rose overnight, sell a put spread below the market (bet MSTR does not fall far); if BTC fell, sell a
call spread above it. Short leg = `short_steps` strikes OTM from the money, long (protective) leg = `width` more
strikes further out. Entry at minute `entry_min` after 09:30; both legs must print within 5 minutes of it.
Exit: take-profit when the spread can be bought back for <= (1 - tp) x credit, stop when buyback >= (1 + sl) x
credit, else expiry (0DTE: intrinsic from the closing spot) or the last print at/before the close (Monday trades).
Return is on capital at risk = (strike width - credit) x 100 per spread (what a broker holds as margin).
Fills: base = close -/+ half-spread on each leg; worst = the costlier of that and the bar extreme.
Commission $0.65 per contract per side, both legs; nothing on expiry settlement."""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

from research.mstr_btc_0dte.engine import Day, half_spread, COMM


@dataclass(frozen=True)
class Spread:
    short_steps: int = 2
    width: int = 1
    entry_min: int = 5
    tp: float | None = None     # fraction of credit captured to exit early (0.5 = buy back at half)
    sl: float | None = None     # loss as multiple of credit to stop (1.0 = buyback costs 2x credit)
    min_btc: float = 0.0
    fills: str = "base"
    flip: bool = False
    both: bool = False          # control: sell BOTH sides (iron condor), ignoring BTC


def _px(b, m0, m1):
    return b[(b.index >= m0) & (b.index <= m1)]


def one_side(day: Day, s: Spread, typ: str) -> dict | None:
    sp0 = day.spot.get(s.entry_min, np.nan)
    if not np.isfinite(sp0):
        return None
    otm = 1 if typ == "C" else -1
    strikes = sorted({k for (t, k) in day.bars if t == typ})
    out = [k for k in strikes if otm * (k - sp0) > 0]
    out.sort(key=lambda k: otm * k)
    if len(out) < s.short_steps + s.width:
        return None
    ks, kl = out[s.short_steps - 1], out[s.short_steps - 1 + s.width]
    bs, bl = day.bars[(typ, ks)], day.bars[(typ, kl)]
    es, el = _px(bs, s.entry_min, s.entry_min + 4), _px(bl, s.entry_min, s.entry_min + 4)
    if es.empty or el.empty:
        return None
    w = s.fills == "worst"
    e_s, e_l = es.iloc[0], el.iloc[0]
    sell = min(e_s.low, e_s.close - half_spread(e_s.close)) if w else e_s.close - half_spread(e_s.close)
    buy = max(e_l.high, e_l.close + half_spread(e_l.close)) if w else e_l.close + half_spread(e_l.close)
    credit = sell - buy - 2 * COMM
    width = abs(kl - ks)
    if credit <= 0.02 or credit > 0.6 * width:  # an OTM spread worth >60% of its width means stale prints
        return None
    risk = width - credit
    m0 = max(int(es.index[0]), int(el.index[0]))
    # minute-by-minute buyback cost of the spread (forward-fill each leg's last print)
    idx = range(m0 + 1, 391)
    cs = bs.close.reindex(idx).ffill(); cl = bl.close.reindex(idx).ffill()
    if w:
        hs = bs.high.reindex(idx); ll = bl.low.reindex(idx)
        buy_s = np.maximum(hs.fillna(cs), cs + half_spread(cs)); sell_l = np.minimum(ll.fillna(cl), cl - half_spread(cl))
    else:
        buy_s = cs + half_spread(cs); sell_l = cl - half_spread(cl)
    cost = (buy_s - sell_l.clip(lower=0)).clip(lower=0, upper=width) + 2 * COMM
    fresh = bs.close.reindex(idx).notna() | bl.close.reindex(idx).notna()
    exit_m, why, paid = None, None, None
    for m in idx:
        c = cost.get(m)
        if c is None or not np.isfinite(c) or not fresh.get(m, False):
            continue
        if s.tp is not None and c <= (1 - s.tp) * (credit + 2 * COMM):
            exit_m, why, paid = m, "tp", c; break
        if s.sl is not None and c >= (1 + s.sl) * (credit + 2 * COMM):
            exit_m, why, paid = m, "sl", c; break
    if exit_m is None:
        if day.exp == day.d:
            spc = day.spot.iloc[-1]
            intr_s = max(spc - ks, 0) if typ == "C" else max(ks - spc, 0)
            intr_l = max(spc - kl, 0) if typ == "C" else max(kl - spc, 0)
            paid, why, exit_m = min(intr_s - intr_l, width), "expiry", 390
        else:
            valid = cost[fresh].dropna()
            if valid.empty:
                return None
            exit_m, paid, why = int(valid.index[-1]), float(valid.iloc[-1]), "close"
    pnl = credit - paid
    return {"date": day.d, "dow": day.d.dayofweek, "typ": typ, "ks": ks, "kl": kl, "spot": sp0, "credit": credit,
            "width": width, "ret": pnl / risk, "ret_credit": pnl / credit, "why": why, "xm": exit_m}


def trade(day: Day, s: Spread) -> list[dict]:
    if day.btc == 0 or abs(day.btc) < s.min_btc:
        return []
    if s.both:
        return [t for t in (one_side(day, s, "C"), one_side(day, s, "P")) if t]
    up = (day.btc > 0) != s.flip
    t = one_side(day, s, "P" if up else "C")
    return [t] if t else []


def backtest(days, s: Spread) -> pd.DataFrame:
    rows = [t for d in days for t in trade(d, s)]
    return pd.DataFrame(rows).set_index("date") if rows else pd.DataFrame()


def stats(t: pd.DataFrame) -> dict:
    if t.empty or len(t) < 2:
        return {"n": len(t)}
    x = t.ret
    return {"n": len(t), "win": float((x > 0).mean()), "mean": float(x.mean()), "med": float(x.median()),
            "t": float(x.mean() / x.std() * np.sqrt(len(x))) if x.std() > 0 else 0.0, "worst": float(x.min()),
            "avg_credit_pct_width": float((t.credit / t.width).mean())}


def grid(days, specs) -> pd.DataFrame:
    out = []
    for s in specs:
        row = asdict(s)
        for f in ("base", "worst"):
            st = stats(backtest(days, Spread(**{**asdict(s), "fills": f})))
            row.update({f"{f}_{k}": v for k, v in st.items()})
        out.append(row)
    return pd.DataFrame(out).drop(columns=["fills"])
