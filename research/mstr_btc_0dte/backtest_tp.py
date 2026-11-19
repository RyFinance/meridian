"""Take-profit-ASAP backtest on 1-minute MSTR option prints.

Each Monday/Friday:
  direction = sign(BTC 16:00 ET prev session -> 09:30 ET)   (calls if up, puts if down)
  contract  = nearest expiry (0DTE Fri; that Friday on Mon), first OTM strike vs MSTR's first-minute price,
              among contracts that traded in the first ENTRY_MIN minutes
  entry     = the first minute bar at/after 09:31 for that contract
  exit      = the FIRST later minute whose sellable price clears entry + all fees by >= TARGET; otherwise at the
              time stop (STOP_MIN after the open), or at 15:59 for the "hold" variant
Fills (no bid/ask exists in the prints):
  base    buy at bar close + half-spread, sell at bar close - half-spread; half-spread = max($0.03, 2.5% of price)
  stress  buy at the bar HIGH, sell at the bar LOW (+ base half-spread on top of nothing; the range is the spread)
  commission $0.65/contract per side in both.
Only bar CLOSES (base) or the adverse extreme (stress) are used to decide an exit, so there is no look-ahead into
a bar's best print."""
from __future__ import annotations

import glob
from pathlib import Path

import numpy as np
import pandas as pd

H = Path(__file__).parent
ROOT = H.parents[1]
COMM = 0.65 / 100  # per share-equivalent of one contract
ET = "America/New_York"


def half_spread(px):
    return np.maximum(0.03, 0.025 * px)


DEV_END = pd.Timestamp("2024-01-01")


def load_1m(window: str = "dev") -> pd.DataFrame:
    """window='dev' (< 2024-01-01) or 'validation' (>= 2024-01-01, only for registered candidates)."""
    if window == "validation" and not (H / "CANDIDATES.md").exists():
        raise RuntimeError("validation window is locked until CANDIDATES.md is written and registered")
    files = sorted(glob.glob(str(ROOT / "data/lse/options_mstr/1m/chunk_*.parquet")))
    o = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    ts = pd.to_datetime(o.ts)
    ts = ts.dt.tz_localize("UTC") if ts.dt.tz is None else ts
    o["t"] = ts.dt.tz_convert(ET).dt.tz_localize(None)
    o["d"] = o.t.dt.normalize()
    o["expiry"] = pd.to_datetime(o.expiry)
    o = o.drop_duplicates(["osi", "t"]).sort_values("t")
    return o[o.d < DEV_END] if window == "dev" else o[o.d >= DEV_END]


def panel() -> pd.DataFrame:
    p = pd.read_parquet(H / "daily_panel.parquet")
    return p[p.dow.isin([0, 4])]


def run(o, p, target=0.0, stop_min=60, fills="base", entry_min=5, min_abs_btc=0.0):
    out = []
    for d, g in o.groupby("d"):
        if d not in p.index:
            continue
        r = p.loc[d]
        if abs(r.btc_off) < min_abs_btc or r.btc_off == 0:
            continue
        s = 1 if r.btc_off > 0 else -1
        typ = "C" if s > 0 else "P"
        exp = g.expiry[g.expiry >= d].min()
        if pd.isna(exp) or (exp - d).days > 4:
            continue
        t_open = d + pd.Timedelta(hours=9, minutes=31)
        early = g[(g.expiry == exp) & (g.opt_type == typ) & (g.t >= t_open) & (g.t < t_open + pd.Timedelta(minutes=entry_min))]
        if early.empty:
            continue
        # MSTR's price at entry, implied from put-call parity is overkill; use the strike where call and put
        # first-minute prices cross (the ATM strike) from the same expiry's early prints.
        both = g[(g.expiry == exp) & (g.t >= t_open) & (g.t < t_open + pd.Timedelta(minutes=entry_min))]
        first = both.sort_values("t").groupby(["strike", "opt_type"]).close.first().unstack()
        if not {"C", "P"} <= set(first.columns):
            continue
        first = first.dropna()
        if first.empty:
            continue
        spot = float((first.index.values + first.C - first.P).median())  # parity, rates ~0 over hours
        if typ == "C":
            ks = sorted(k for k in early.strike.unique() if k >= spot)
        else:
            ks = sorted((k for k in early.strike.unique() if k <= spot), reverse=True)
        if not ks or abs(ks[0] / spot - 1) > 0.05:
            continue
        k = ks[0]
        c = g[(g.expiry == exp) & (g.opt_type == typ) & (g.strike == k) & (g.t >= t_open)].sort_values("t")
        e = c.iloc[0]
        buy = e.high if fills == "stress" else e.close + half_spread(e.close)
        cost = buy + COMM
        t_stop = d + pd.Timedelta(hours=9, minutes=30) + pd.Timedelta(minutes=stop_min) if stop_min else d + pd.Timedelta(hours=15, minutes=59)
        later = c[(c.t > e.t) & (c.t <= t_stop)]
        sell = (later.low if fills == "stress" else later.close - half_spread(later.close)).clip(lower=0) - COMM
        hit = later[(sell / cost - 1) >= target]
        if len(hit):
            x = hit.iloc[0]; px = float(sell.loc[x.name]); why = "target"
        elif len(later):
            x = later.iloc[-1]; px = float(sell.iloc[-1]); why = "time_stop"
            if exp == d and stop_min == 0:  # held 0DTE to the end: settle at intrinsic if better than last print
                why = "close"
        else:
            x = e; px = -COMM; why = "no_later_print"
        out.append(dict(date=d, dow=d.dayofweek, typ=typ, strike=k, spot=spot, dte=(exp - d).days, entry_t=e.t,
                        exit_t=x.t, minutes=(x.t - e.t).total_seconds() / 60, cost=cost, proceeds=px,
                        ret=max(px, -COMM) / cost - 1, why=why, btc_off=r.btc_off))
    return pd.DataFrame(out).set_index("date") if out else pd.DataFrame()


def summary(t: pd.DataFrame) -> dict:
    if t.empty:
        return {"n": 0}
    return {"n": len(t), "win": float((t.ret > 0).mean()), "mean": float(t.ret.mean()), "median": float(t.ret.median()),
            "avg_win": float(t.ret[t.ret > 0].mean()) if (t.ret > 0).any() else 0.0,
            "avg_loss": float(t.ret[t.ret <= 0].mean()) if (t.ret <= 0).any() else 0.0,
            "t": float(t.ret.mean() / t.ret.std() * np.sqrt(len(t))) if len(t) > 1 else None,
            "median_minutes": float(t.minutes.median()), "target_hit": float((t.why == "target").mean())}


if __name__ == "__main__":
    o, p = load_1m(), panel()
    print("1m data", o.d.min().date(), "..", o.d.max().date(), "days", o.d.nunique())
    rows = []
    for fills in ["base", "stress"]:
        for target in [0.0, 0.10, 0.25, 0.50]:
            for stop in [15, 60, 0]:
                t = run(o, p, target, stop, fills)
                s = summary(t)
                rows.append({"fills": fills, "target": target, "stop_min": stop or "hold", **s})
                if fills == "base" and target == 0.0 and stop == 60:
                    t.to_csv(H / "tp_trades_base_t0_s60.csv")
    res = pd.DataFrame(rows)
    res.to_csv(H / "tp_grid.csv", index=False)
    pd.set_option("display.width", 220)
    print(res.round(3).to_string(index=False))
