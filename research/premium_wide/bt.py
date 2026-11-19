"""Defined-risk premium selling on daily option prints (PROTOCOL.md)."""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import pandas as pd

H = Path(__file__).parent
ROOT = H.parents[1]
COMM = 0.0065
SPLIT = pd.Timestamp("2024-08-08")


@dataclass(frozen=True)
class Rule:
    kind: str = "pcs"        # pcs (put credit spread), ccs, condor, csp
    dte: int = 30
    otm: float = 0.10
    wing: float = 0.05
    tp: float | None = None  # 0.5 = take profit at 50% of credit
    ivf: bool = False        # only when short-option IV > 20d realized vol
    stress: bool = False


def hs(px, stress):
    return np.maximum(0.10, 0.10 * px) if stress else np.maximum(0.05, 0.05 * px)


def load(sym: str):
    if sym == "MSTR":
        o = pd.read_parquet(ROOT / "data/lse/options_mstr/MSTR.parquet")
        m = pd.read_parquet(ROOT / "research/mstr_btc_0dte/mstr_daily_yf.parquet")[["Close"]]
        m["S"] = m.Close * np.where(m.index < SPLIT, 10.0, 1.0)
    else:
        o = pd.read_parquet(ROOT / "data/lse/options_ibit/IBIT.parquet")
        import yfinance as yf
        m = yf.download(sym, start="2024-01-01", end="2026-10-17", auto_adjust=False, progress=False, multi_level_index=False)[["Close"]]
        m["S"] = m.Close
    m.index = pd.to_datetime(m.index).normalize()
    o["d"] = pd.to_datetime(o.ts).dt.tz_localize(None).dt.normalize()
    o["expiry"] = pd.to_datetime(o.expiry)
    o = o[(o.volume > 0) & (o.close > 0)]
    chains = {d: g.set_index(["expiry", "opt_type", "strike"]).close for d, g in o.groupby("d")}
    spot = m.S
    rv = np.log(spot).diff().rolling(20).std() * math.sqrt(252)
    return chains, spot, rv


def bs_iv(price, S, K, T, typ, r=0.04):
    if T <= 0 or price <= 0:
        return np.nan
    def bs(sig):
        d1 = (math.log(S / K) + (r + sig * sig / 2) * T) / (sig * math.sqrt(T)); d2 = d1 - sig * math.sqrt(T)
        N = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
        return S * N(d1) - K * math.exp(-r * T) * N(d2) if typ == "C" else K * math.exp(-r * T) * N(-d2) - S * N(-d1)
    lo, hi = 1e-3, 6.0
    if not (bs(lo) <= price <= bs(hi)):
        return np.nan
    for _ in range(50):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if bs(mid) < price else (lo, mid)
    return (lo + hi) / 2


def settle_px(spot, e):
    s = spot[spot.index <= e]
    return float(s.iloc[-1]) if len(s) else np.nan


def side_legs(ch, S, e, typ, otm, wing, need_wing):
    try:
        c = ch.loc[(e, typ)]
    except KeyError:
        return None
    if typ == "P":
        shorts = c[c.index <= S * (1 - otm)]; ks = shorts.index.max() if len(shorts) else None
        if ks is None: return None
        if not need_wing: return ks, None
        longs = c[c.index <= ks * (1 - wing) + 1e-9]; kl = longs.index.max() if len(longs) else None
    else:
        shorts = c[c.index >= S * (1 + otm)]; ks = shorts.index.min() if len(shorts) else None
        if ks is None: return None
        if not need_wing: return ks, None
        longs = c[c.index >= ks * (1 + wing) - 1e-9]; kl = longs.index.min() if len(longs) else None
    return (ks, kl) if kl is not None else None


def run(data, r: Rule, start, end):
    chains, spot, rv = data
    days = [d for d in sorted(chains) if pd.Timestamp(start) <= d <= pd.Timestamp(end) and d in spot.index]
    out, i = [], 0
    sides = {"pcs": ["P"], "ccs": ["C"], "condor": ["P", "C"], "csp": ["P"]}[r.kind]
    while i < len(days):
        d = days[i]; ch = chains[d]; S = float(spot[d])
        exps = sorted({e for e in ch.index.get_level_values(0) if (e - d).days >= 4})
        if not exps:
            i += 1; continue
        e = min(exps, key=lambda x: abs((x - d).days - r.dte))
        legs = {t: side_legs(ch, S, e, t, r.otm, r.wing, r.kind != "csp") for t in sides}
        if any(v is None for v in legs.values()):
            i += 1; continue
        if r.ivf:
            t0 = sides[0]; ks0 = legs[t0][0]
            iv = bs_iv(float(ch.loc[(e, t0, ks0)]), S, ks0, (e - d).days / 365, t0)
            if not (np.isfinite(iv) and np.isfinite(rv.get(d, np.nan)) and iv > rv[d]):
                i += 1; continue
        credit, width, legsp = 0.0, 0.0, []
        for t, (ks, kl) in legs.items():
            ps = float(ch.loc[(e, t, ks)]); credit += ps - hs(ps, r.stress) - COMM
            if kl is not None:
                pl = float(ch.loc[(e, t, kl)]); credit -= pl + hs(pl, r.stress) + COMM
                width = max(width, abs(ks - kl))
            legsp.append((t, ks, kl))
        if credit <= 0.02:
            i += 1; continue
        cap = (width - credit) if r.kind != "csp" else (legs["P"][0] - credit)
        if cap <= 0:
            i += 1; continue
        # walk forward for take-profit, else settle at expiry
        exit_d, paid, j = None, None, i + 1
        if r.tp is not None:
            while j < len(days) and days[j] < e:
                cj = chains[days[j]]; cost, ok = 0.0, True
                for t, ks, kl in legsp:
                    try:
                        ps = float(cj.loc[(e, t, ks)]); cost += ps + hs(ps, r.stress) + COMM
                        if kl is not None:
                            pl = float(cj.loc[(e, t, kl)]); cost -= max(pl - hs(pl, r.stress), 0) - COMM
                    except KeyError:
                        ok = False; break
                if ok and cost <= (1 - r.tp) * credit:
                    exit_d, paid = days[j], cost; break
                j += 1
        if exit_d is None:
            Se = settle_px(spot, e)
            if not np.isfinite(Se):
                break
            paid = 0.0
            for t, ks, kl in legsp:
                intr = (lambda k: max(k - Se, 0)) if t == "P" else (lambda k: max(Se - k, 0))
                paid += intr(ks) - (intr(kl) if kl is not None else 0.0)
            exit_d = e
        pnl = credit - paid
        out.append(dict(entry=d, exit=exit_d, dte=(e - d).days, S=S, credit=credit, cap=cap, pnl=pnl, ret=pnl / cap))
        nxt = [k for k, x in enumerate(days) if x > exit_d]
        if not nxt:
            break
        i = nxt[0]
    return pd.DataFrame(out)


def stats(t):
    if len(t) < 8:
        return {"n": len(t)}
    x = t.ret; eq = (1 + x).cumprod()
    yrs = max((t.exit.max() - t.entry.min()).days / 365.25, 0.1)
    return {"n": len(t), "win": round((x > 0).mean(), 3), "mean": round(x.mean(), 4), "t": round(x.mean() / x.std() * math.sqrt(len(x)), 2),
            "worst": round(x.min(), 3), "cagr": round(eq.iloc[-1] ** (1 / yrs) - 1, 4), "maxdd": round((eq / eq.cummax() - 1).min(), 3)}


def grid():
    for kind, dte, otm, wing, tp, ivf in itertools.product(["pcs", "ccs", "condor"], [2, 4, 7, 14], [0.03, 0.05, 0.10],
                                                          [0.05, 0.10], [None, 0.5], [False, True]):
        yield Rule(kind, dte, otm, wing, tp, ivf)
