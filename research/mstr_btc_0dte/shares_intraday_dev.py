"""DEV-window intraday shares test for the BTC off-hours move (MSTR stock 1m, LSE Terminal).

Direction = sign(btc_off) from the daily panel (same definition as signal_study.py).
Baseline registered rule: enter at official open, exit at official close. Variants here:
  * entry: official open vs the first 1m print close within (09:30, 09:30+entry_min]
  * exit: official close vs take-profit/stop in bp vs fixed clock time
  * filters: |btc_off| >= 1% (SHARES plan gate) and unfiltered
  * stress costs: 10 bp/side, commission x2
Dev window only (< 2024-01-01). Costs mirror costs.py: IBKR $0.005/share/side (min $1,
max 1%), SEC $27.80/$1M + FINRA TAF on the sale side, slippage against 1m print prices.
"""
from __future__ import annotations

import itertools
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parents[2]))
from research.mstr_btc_0dte.costs import (COMMISSION_PER_SHARE, COMMISSION_MIN, SEC_RATE,
                                          TAF_PER_SHARE, TAF_MAX)

H = Path(__file__).parent
DEV_END = pd.Timestamp("2024-01-01")


@dataclass(frozen=True)
class ShareRule:
    entry_min: int = 0            # 0 = official open; N>0 = enter at the close of the first 1m print in (09:30, 09:30+N]  (users: identical to open)
    entry_delay: int = 0          # literal clock delay: enter at open x cumret through minute N
    exit_tp_bp: float | None = None
    exit_sl_bp: float | None = None
    exit_min: int = 390           # minutes after 09:30; 390 = official close
    min_off: float = 0.0
    slip_bp: float = 3.0          # per side
    comm_mult: float = 1.0


def load_context() -> tuple[pd.DataFrame, dict]:
    panel = pd.read_parquet(H / "daily_panel.parquet")
    panel = panel[(panel.dow.isin(range(5))) & (panel.index < DEV_END)].dropna()
    yf = pd.read_parquet(H / "mstr_daily_yf.parquet")
    ctx = {"panel": panel, "open": yf["Open"], "close": yf["Close"]}
    return yf, ctx


def load_days() -> dict:
    """{date: rets} where rets = 1m return series indexed by minute-from-09:30 (regular session)."""
    out = {}
    yf, _ = load_context()
    for f in sorted((H / "stock_1m_dev").glob("*.parquet")):
        d = f.stem
        if pd.Timestamp(d) not in yf.index:
            continue
        bars = pd.read_parquet(f)
        ts = pd.to_datetime(bars.time, utc=True).dt.tz_convert("America/New_York").dt.tz_localize(None)
        mm = ((ts - pd.Timestamp(f"{d} 09:30")).dt.total_seconds() // 60).astype(int)
        reg = bars[((mm >= 1) & (mm <= 390)).values].assign(minute=mm[(mm >= 1) & (mm <= 390)].values)
        if reg.empty:
            continue
        px = reg.groupby("minute").close.last().sort_index()
        rets = px.pct_change().dropna()
        if len(rets) == 0:
            continue
        first_ret = None
        if rets.index.min() == 1:
            p0 = px.iloc[0] / (1 + rets.iloc[0])          # implied open from the first bar
            first_ret = px.iloc[0] / p0 - 1.0
        else:
            first_ret = 0.0
        rets = pd.concat([pd.Series({0: first_ret}), rets]) if first_ret is not None else rets
        out[d] = rets.reindex(sorted(set(rets.index) | set(range(0, 391)))).ffill()
    return out


def trade(r: ShareRule, day: str, rets: pd.Series, open_px: float, official_close: float) -> float | None:
    shares = int(100_000 // open_px)
    if shares <= 0:
        return None
    if r.entry_delay > 0:
        drift = (1 + rets.loc[1:r.entry_delay].dropna()).prod() - 1
        entry = open_px * (1 + drift)
        start = r.entry_delay + 1
    elif r.entry_min > 0:
        w = rets.loc[1:r.entry_min].dropna()
        if len(w) == 0:
            return None
        em = int(w.index[0])          # first tradeable print within the entry window
        entry = open_px * (1 + rets.loc[em])
        start = em + 1                # path composes returns AFTER the entry minute
    else:
        entry, start = open_px, 1
    w = rets[(rets.index >= start) & (rets.index <= r.exit_min)].dropna()
    value, exit_px_frac, why = 1.0, None, ""
    sell_px, why = None, ""
    for m, x in w.items():
        value *= (1 + x)
        if r.exit_tp_bp is not None and value >= 1 + r.exit_tp_bp / 1e4:
            sell_px, why = entry * value, "tp"
            break
        if r.exit_sl_bp is not None and value <= 1 - r.exit_sl_bp / 1e4:
            sell_px, why = entry * value, "sl"
            break
    if sell_px is None:
        if r.exit_min >= 389:
            sell_px, why = official_close, "close"      # anchor at the official close (absolute)
        elif len(w):
            sell_px, why = entry * value, "time"
        else:
            return None
    xv = sell_px
    slip = r.slip_bp / 1e4
    cm = max(max(COMMISSION_PER_SHARE * r.comm_mult * shares, COMMISSION_MIN), 0.01 * entry * shares) \
        + max(max(COMMISSION_PER_SHARE * r.comm_mult * shares, COMMISSION_MIN), 0.01 * xv * shares)
    sec_taf = SEC_RATE * xv * shares + min(TAF_PER_SHARE * shares, TAF_MAX)
    pnl = shares * (xv * (1 - slip) - entry * (1 + slip)) - cm - sec_taf
    return pnl / (shares * entry * (1 + slip))


def run_grid(days: dict) -> pd.DataFrame:
    yf, ctx = load_context()
    panel = ctx["panel"]
    rules: list[ShareRule] = [
        ShareRule(entry_min=0, exit_min=390, min_off=0.01, slip_bp=3.0),
        ShareRule(entry_min=0, exit_min=390, min_off=0.0, slip_bp=3.0),
        *[ShareRule(entry_min=0, entry_delay=d_, exit_min=390, min_off=0.01) for d_ in (5, 15, 30, 60)],
        *[ShareRule(entry_min=0, exit_tp_bp=t, min_off=0.01) for t in (25, 50, 100)],
        *[ShareRule(entry_min=0, exit_sl_bp=s, min_off=0.01) for s in (50, 100)],
        *[ShareRule(entry_min=0, exit_min=x, min_off=0.01) for x in (60, 120, 240)],
        ShareRule(entry_min=5, exit_tp_bp=50, exit_sl_bp=100, min_off=0.01),
        ShareRule(entry_min=0, exit_min=390, min_off=0.01, slip_bp=10.0, comm_mult=2.0),
    ]
    rows = []
    for r in rules:
        rets = []
        for d, sr in days.items():
            if pd.Timestamp(d) not in panel.index:
                continue
            row = panel.loc[pd.Timestamp(d)]
            if row.btc_off == 0 or abs(row.btc_off) < r.min_off:
                continue
            open_px = float(ctx["open"].loc[pd.Timestamp(d)])
            x = trade(r, d, sr, open_px, float(ctx["close"].loc[pd.Timestamp(d)]))
            if x is None:
                continue
            rets.append((d, x * np.sign(row.btc_off)))
        t = pd.DataFrame(rets, columns=["d", "ret"]).set_index("d")
        x = t.ret if len(t) else pd.Series(dtype=float)
        entry = {"entry_min": r.entry_min, "entry_delay": r.entry_delay, "tp": r.exit_tp_bp, "sl": r.exit_sl_bp,
                 "exit_min": r.exit_min, "min_off": r.min_off, "slip_bp": r.slip_bp,
                 "comm_x": r.comm_mult}
        if len(x) < 3:
            rows.append({**entry, "n": len(x)})
            continue
        rows.append({**entry, "n": len(x), "mean_bp": x.mean() * 1e4,
                     "t": float(x.mean() / x.std() * np.sqrt(len(x))),
                     "win": float((x > 0).mean())})
    out = pd.DataFrame(rows)
    out.to_csv(H / "shares_intraday_dev.csv", index=False)
    return out


if __name__ == "__main__":
    print("dev days with 1m bars:", end=" ")
    dl = load_days()
    print(len(dl))
    pd.set_option("display.width", 220)
    print(run_grid(dl).round(3).to_string(index=False))
