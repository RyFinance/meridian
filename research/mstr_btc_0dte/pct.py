"""Short options by % out of the money, optionally with a far protective wing (defined risk).

side: 'safe' = sell the option on the side BTC's overnight move points AWAY from (BTC up -> sell a put),
      'opposite' = the other side (control), 'both' = a strangle (both sides, ignores BTC).
Short strike = nearest listed strike at or beyond otm% from spot at entry; wing strike = nearest at or beyond
(otm + wing)% (None = naked). Hold to expiry (0DTE: settle on the closing spot) or the last print on the day for
non-0DTE (Monday) trades. Return on capital = pnl / margin, where margin = width - credit for a spread, and the
Reg-T naked requirement max(20% x S - OTM amount, 10% x S) + premium for a naked short.
Fills as in engine.py ('base' / 'worst'); commission $0.65 per contract per side, none at expiry."""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

from research.mstr_btc_0dte.engine import half_spread, COMM


@dataclass(frozen=True)
class Short:
    side: str = "safe"
    otm: float = 0.04
    wing: float | None = None
    entry_min: int = 5
    min_btc: float = 0.0
    fridays_only: bool = True
    fills: str = "base"


def _first(b, m0):
    x = b[(b.index >= m0) & (b.index <= m0 + 4)]
    return (int(x.index[0]), x.iloc[0]) if len(x) else (None, None)


def leg(day, typ, s: Short):
    sp0 = day.spot.get(s.entry_min, np.nan)
    if not np.isfinite(sp0):
        return None
    sign = 1 if typ == "C" else -1
    strikes = sorted({k for (t, k) in day.bars if t == typ})

    def pick(pct):
        c = [k for k in strikes if sign * (k / sp0 - 1) >= pct]
        if not c:
            return None
        return min(c, key=lambda k: sign * k)

    ks = pick(s.otm)
    if ks is None:
        return None
    ms, es = _first(day.bars[(typ, ks)], s.entry_min)
    if es is None:
        return None
    w = s.fills == "worst"
    credit = (min(es.low, es.close - half_spread(es.close)) if w else es.close - half_spread(es.close)) - COMM
    kl, debit = None, 0.0
    if s.wing is not None:
        kl = pick(s.otm + s.wing)
        if kl is None or kl == ks:
            return None
        ml, el = _first(day.bars[(typ, kl)], s.entry_min)
        if el is None:
            return None
        debit = (max(el.high, el.close + half_spread(el.close)) if w else el.close + half_spread(el.close)) + COMM
    net = credit - debit
    if net <= 0.01:
        return None
    if day.exp == day.d:
        spc = day.spot.iloc[-1]
        intr = lambda k: max(spc - k, 0) if typ == "C" else max(k - spc, 0)
        paid = intr(ks) - (intr(kl) if kl is not None else 0.0)
        paid += COMM if intr(ks) > 0 else 0.0
    else:  # buy back at the last print of the day (+ half-spread), sell the wing back
        bs = day.bars[(typ, ks)]; last = bs[bs.index > ms]
        if last.empty:
            return None
        c = last.close.iloc[-1]
        paid = (max(last.high.iloc[-1], c + half_spread(c)) if w else c + half_spread(c)) + COMM
        if kl is not None:
            bl = day.bars[(typ, kl)]; ll = bl[bl.index > s.entry_min]
            v = ll.close.iloc[-1] if len(ll) else 0.0
            paid -= max(v - half_spread(v), 0) - COMM
    pnl = net - paid
    if kl is not None:
        margin = abs(kl - ks) - net
    else:
        margin = max(0.20 * sp0 - abs(ks - sp0), 0.10 * sp0) + es.close
    if margin <= 0:
        return None
    return {"date": day.d, "dow": day.d.dayofweek, "typ": typ, "ks": ks, "kl": kl, "spot": sp0, "credit": net,
            "pnl": pnl, "margin": margin, "ret": pnl / margin, "ret_credit": pnl / net,
            "lost": paid > net, "otm_real": abs(ks / sp0 - 1)}


def trade(day, s: Short):
    if day.btc == 0 or abs(day.btc) < s.min_btc:
        return []
    if s.fridays_only and not (day.d.dayofweek == 4 and day.exp == day.d):
        return []
    up = day.btc > 0
    if s.side == "both":
        legs = [leg(day, "C", s), leg(day, "P", s)]
        legs = [x for x in legs if x]
        if len(legs) < 2:
            return []
        # one combined position: capital = the larger side's margin (only one side can finish in the money)
        m = max(x["margin"] for x in legs); pnl = sum(x["pnl"] for x in legs)
        return [{**legs[0], "typ": "CP", "pnl": pnl, "margin": m, "ret": pnl / m,
                 "credit": sum(x["credit"] for x in legs), "lost": pnl < 0}]
    typ = ("P" if up else "C") if s.side == "safe" else ("C" if up else "P")
    x = leg(day, typ, s)
    return [x] if x else []


def backtest(days, s: Short) -> pd.DataFrame:
    rows = [t for d in days for t in trade(d, s)]
    return pd.DataFrame(rows).set_index("date") if rows else pd.DataFrame()


def stats(t) -> dict:
    if t.empty or len(t) < 3:
        return {"n": len(t)}
    x = t.ret
    return {"n": len(t), "win": float((x > 0).mean()), "mean": float(x.mean()), "t": float(x.mean() / x.std() * np.sqrt(len(x))),
            "worst": float(x.min()), "sum": float(x.sum()), "avg_credit_on_margin": float((t.credit / t.margin).mean())}


def grid(days, specs):
    out = []
    for s in specs:
        row = asdict(s)
        for f in ("base", "worst"):
            row.update({f"{f}_{k}": v for k, v in stats(backtest(days, Short(**{**asdict(s), "fills": f}))).items()})
        out.append(row)
    return pd.DataFrame(out).drop(columns=["fills"])
