"""LOCK-SAFE panel for the statistical/economic audit of crypto_funding_xs.

Reads ONLY monthly archive files whose month is <= 2022-12 (research/crypto_funding_xs/LOCK_2023_2026.md).
Consequence: the single funding settlement at 2023-01-01 00:00 UTC (paid for holding day 2022-12-31) is not read,
so the last dev day differs trivially from the frozen run. Everything else mirrors research/crypto_funding_xs/core.py
(pure functions weights()/returns() are imported unchanged). Caches the panel to reports/audit_funding_stat/.
"""
from __future__ import annotations

import pickle
import re

import numpy as np
import pandas as pd

from research.crypto_funding_xs import core as c
from research.struct_common import ROOT

OUT = ROOT / "reports" / "audit_funding_stat"
DEV = ("2020-01-01", "2022-12-31")
LAST_MONTH = "2022-12"
_M = re.compile(r"(\d{4}-\d{2})\.zip$")


def _files(d):
    out = []
    for f in sorted(d.glob("*.zip")):
        m = _M.search(f.name)
        if m and m.group(1) <= LAST_MONTH:
            out.append(f)
    return out


def klines(sym):
    fs = _files(c.BIN / "klines_1d" / sym)
    if not fs:
        return pd.DataFrame()
    d = pd.concat([c._read_zip_csv(f, c.KCOLS) for f in fs], ignore_index=True)
    d["day"] = pd.to_datetime(pd.to_numeric(d["open_time"]), unit="ms").dt.normalize()
    d = d.drop_duplicates("day").set_index("day").sort_index()
    d = d[d.index <= pd.Timestamp(DEV[1])]
    return d[["open", "close", "quote_volume"]].astype(float)


def funding(sym):
    fs = _files(c.BIN / "fundingRate" / sym)
    if not fs:
        return pd.Series(dtype=float)
    d = pd.concat([c._read_zip_csv(f, ["calc_time", "funding_interval_hours", "last_funding_rate"]) for f in fs],
                  ignore_index=True)
    t = pd.to_datetime(pd.to_numeric(d["calc_time"]), unit="ms")
    s = pd.Series(pd.to_numeric(d["last_funding_rate"]).to_numpy(), index=t).sort_index().groupby(level=0).last()
    return s[s.index < pd.Timestamp("2023-01-01")]


def panel():
    """Same construction as core.panel for the DEV window, from lock-safe readers."""
    start, end = DEV
    days = pd.date_range(pd.Timestamp(start) - pd.Timedelta(days=90), end, freq="D")
    O, C, V, SIG, FUND, FIRST = {}, {}, {}, {}, {}, {}
    for s in c.symbols():
        k = klines(s)
        if k.empty:
            continue
        FIRST[s] = k.index[0]
        k = k.reindex(days)
        O[s], C[s], V[s] = k["open"], k["close"], k["quote_volume"]
        f = funding(s)
        if f.empty:
            SIG[s] = pd.Series(np.nan, index=days)
            FUND[s] = pd.Series(0.0, index=days)
            continue
        cs = f.cumsum()
        cnt = pd.Series(1.0, index=f.index).cumsum()

        def at(x, when):
            return x.reindex(x.index.union(when)).ffill().reindex(when).fillna(0.0)
        hi = days - pd.Timedelta(milliseconds=1)
        lo = days - pd.Timedelta(days=c.SIG_DAYS) - pd.Timedelta(milliseconds=1)
        ssum = at(cs, hi).to_numpy() - at(cs, lo).to_numpy()
        n = at(cnt, hi).to_numpy() - at(cnt, lo).to_numpy()
        SIG[s] = pd.Series(np.where(n >= c.MIN_SETTLE, ssum / c.SIG_DAYS, np.nan), index=days)
        a = at(cs, days + pd.Timedelta(days=1)).to_numpy() - at(cs, days).to_numpy()
        FUND[s] = pd.Series(a, index=days)
    return {k: pd.DataFrame(v) for k, v in dict(O=O, C=C, V=V, SIG=SIG, FUND=FUND).items()}, FIRST


def cached():
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "_lockpanel_cache.pkl"
    if p.exists():
        return pickle.loads(p.read_bytes())
    P, FIRST = panel()
    W = c.weights(P, FIRST, *DEV)
    p.write_bytes(pickle.dumps((P, FIRST, W)))
    return P, FIRST, W
