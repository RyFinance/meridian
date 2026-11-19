"""General intraday engine for MSTR option trades directed by BTC's off-hours move (dev window only by default).

Per trading day (Mon/Fri) it prepares:
  * the nearest expiry (0DTE Fri; that week's Friday on Mon),
  * a per-minute MSTR spot estimate from put-call parity (median over the 6 strikes nearest the money that printed
    in that minute, forward-filled; rates ~0 over hours),
  * per-contract minute bars.
A rule = (direction source, strike choice, entry time, optional confirmation, take-profit, stop-loss, time stop).
Fills: 'base' = bar close -/+ half-spread max($0.03, 2.5%); 'worst' = the costlier of that and the bar high (buy) / low (sell).
Exits are decided on the sellable price of each minute AFTER the entry minute (no look-ahead within a bar).
Commission $0.65/contract per side."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import pandas as pd

from research.mstr_btc_0dte.backtest_tp import load_1m, panel

H = Path(__file__).parent
COMM = 0.0065


@dataclass(frozen=True)
class Rule:
    side: str = "buy"           # "buy" options, or "sell" (credit: sell the option, buy back)
    strike_steps: int = 1       # +1 = first OTM, 0 = nearest ATM, -1 = first ITM, -2 = second ITM ...
    entry_min: int = 1          # minutes after 09:30 to enter
    confirm: float = 0.0        # require spot to have moved >= confirm (frac) in BTC's direction by entry
    tp: float | None = 0.0      # exit when net return >= tp (None = no target)
    sl: float | None = None     # exit when net return <= -sl
    stop_min: int = 60          # time stop, minutes after 09:30 (390 = close)
    min_btc: float = 0.0        # |btc_off| filter
    fills: str = "base"
    flip: bool = False          # opposite direction (control)


def half_spread(px):
    return np.maximum(0.03, 0.025 * px)


class Day:
    __slots__ = ("d", "btc", "exp", "spot", "bars")

    def __init__(self, d, btc, exp, spot, bars):
        self.d, self.btc, self.exp, self.spot, self.bars = d, btc, exp, spot, bars


def prepare(window: str = "dev") -> list[Day]:
    o, p = load_1m(window), panel()
    days = []
    for d, g in o.groupby("d"):
        if d not in p.index:
            continue
        exp = g.expiry[g.expiry >= d].min()
        if pd.isna(exp) or (exp - d).days > 4:
            continue
        g = g[(g.expiry == exp) & (g.t >= d + pd.Timedelta(hours=9, minutes=30)) & (g.t <= d + pd.Timedelta(hours=16))]
        if g.empty:
            continue
        g = g.assign(m=((g.t - d).dt.total_seconds() // 60 - 570).astype(int))  # minute index from 09:30
        piv = g.pivot_table(index=["m", "strike"], columns="opt_type", values="close", aggfunc="last").dropna()
        if piv.empty or not {"C", "P"} <= set(piv.columns):
            continue
        piv = piv.reset_index()
        piv["s"] = piv.strike + piv.C - piv.P
        piv["dist"] = (piv.C - piv.P).abs()
        spot = piv.sort_values("dist").groupby("m").head(6).groupby("m").s.median()
        spot = spot.reindex(range(0, 391)).ffill()
        bars = {k: v.set_index("m")[["open", "high", "low", "close", "volume"]].groupby(level=0).last()
                for k, v in g.groupby(["opt_type", "strike"])}
        days.append(Day(d, float(p.loc[d, "btc_off"]), exp, spot, bars))
    return days


def trade(day: Day, r: Rule) -> dict | None:
    if abs(day.btc) < r.min_btc or day.btc == 0:
        return None
    s = (1 if day.btc > 0 else -1) * (-1 if r.flip else 1)
    # the option that profits from the BTC direction when bought; a seller sells the OTHER side
    want_up = (s > 0) if r.side == "buy" else (s < 0)
    typ = "C" if want_up else "P"
    sp0 = day.spot.get(r.entry_min, np.nan)
    if not np.isfinite(sp0):
        return None
    if r.confirm > 0:
        sp_open = day.spot.dropna().iloc[0] if day.spot.notna().any() else np.nan
        if not np.isfinite(sp_open) or s * (sp0 / sp_open - 1) < r.confirm:
            return None
    strikes = sorted(k for (t, k), b in day.bars.items() if t == typ and (b.index >= r.entry_min).any()
                     and (b.index <= r.entry_min + 4).any())
    if not strikes:
        return None
    # order strikes from deep ITM to far OTM for this option type
    otm_dir = 1 if typ == "C" else -1
    atm = min(strikes, key=lambda k: abs(k - sp0))
    ladder = sorted(strikes, key=lambda k: otm_dir * k)
    i = ladder.index(atm)
    if r.strike_steps > 0 and otm_dir * (atm - sp0) < 0:   # ATM is ITM; first OTM is the next one out
        i += 1
    i += max(r.strike_steps - 1, 0) if r.strike_steps > 0 else r.strike_steps
    if not 0 <= i < len(ladder):
        return None
    k = ladder[i]
    if abs(k / sp0 - 1) > 0.08:
        return None
    b = day.bars[(typ, k)]
    eb = b[(b.index >= r.entry_min) & (b.index <= r.entry_min + 4)]
    if eb.empty:
        return None
    em = int(eb.index[0]); e = eb.iloc[0]
    later = b[(b.index > em) & (b.index <= r.stop_min)]
    if r.side == "buy":
        cost = (max(e.high, e.close + half_spread(e.close)) if r.fills == "worst" else e.close + half_spread(e.close)) + COMM
        sell = np.minimum(later.low, later.close - half_spread(later.close)) if r.fills == "worst" else later.close - half_spread(later.close)
        val = sell.clip(lower=0) - COMM
        ret = val / cost - 1
    else:  # sell to open, buy to close; return on a margin of 1x strike-distance proxy = premium received
        credit = (min(e.low, e.close - half_spread(e.close)) if r.fills == "worst" else e.close - half_spread(e.close)) - COMM
        if credit <= 0:
            return None
        buyback = (np.maximum(later.high, later.close + half_spread(later.close)) if r.fills == "worst" else later.close + half_spread(later.close)) + COMM
        ret = (credit - buyback) / credit   # fraction of premium kept (can be << -1)
    exit_m, why = None, "time"
    for m, x in ret.items():
        if r.tp is not None and x >= r.tp:
            exit_m, why = m, "tp"; break
        if r.sl is not None and x <= -r.sl:
            exit_m, why = m, "sl"; break
    if exit_m is None:
        if r.stop_min >= 389 and day.exp == day.d:   # held a 0DTE to the end: settle on the closing spot
            spc = day.spot.iloc[-1]
            intr = max(spc - k, 0) if typ == "C" else max(k - spc, 0)
            if r.side == "buy":
                x = (max(intr - (half_spread(intr) if intr > 0 else 0), 0) - (COMM if intr > 0 else 0)) / cost - 1
            else:
                x = (credit - intr - (COMM if intr > 0 else 0)) / credit
            exit_m, why = 390, "expiry"
        elif len(ret):
            exit_m, x = int(ret.index[-1]), float(ret.iloc[-1])
        else:
            return None
    else:
        x = float(ret.loc[exit_m])
    return {"date": day.d, "dow": day.d.dayofweek, "typ": typ, "k": k, "spot": sp0, "em": em, "xm": exit_m,
            "why": why, "ret": float(x), "premium": float(e.close)}


def backtest(days: list[Day], r: Rule) -> pd.DataFrame:
    rows = [t for t in (trade(d, r) for d in days) if t]
    return pd.DataFrame(rows).set_index("date") if rows else pd.DataFrame()


def stats(t: pd.DataFrame) -> dict:
    if t.empty or len(t) < 2:
        return {"n": len(t)}
    x = t.ret
    return {"n": len(t), "win": float((x > 0).mean()), "mean": float(x.mean()), "med": float(x.median()),
            "avg_win": float(x[x > 0].mean()) if (x > 0).any() else 0.0,
            "avg_loss": float(x[x <= 0].mean()) if (x <= 0).any() else 0.0,
            "t": float(x.mean() / x.std() * np.sqrt(len(x))) if x.std() > 0 else 0.0,
            "worst": float(x.min())}


def grid(days, rules: list[Rule]) -> pd.DataFrame:
    out = []
    for r in rules:
        row = {**asdict(r)}
        for f in ("base", "worst"):
            s = stats(backtest(days, Rule(**{**asdict(r), "fills": f})))
            row.update({f"{f}_{k}": v for k, v in s.items()})
        out.append(row)
    return pd.DataFrame(out).drop(columns=["fills"])
