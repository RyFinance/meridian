"""Binance USD-M perpetual funding-rate cross-section (research/crypto_funding_xs/PLAN.md). Frozen by the plan."""
from __future__ import annotations

import io
import json
import zipfile
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "data" / "c4" / "binance_um"
EXCL_BASE = {"BTCDOM", "DEFI", "FOOTBALL", "BLUEBIRD"}
TOP_N, MIN_HIST, VOL_LOOKBACK, SIG_DAYS, MIN_SETTLE, MIN_UNIVERSE, Q = 100, 60, 30, 7, 10, 25, 0.2
COSTS = {"gross": (0.0, 0.0), "base": (7e-4, 0.0), "stress": (20e-4, 0.20)}   # (cost per side, adverse delist move)
KCOLS = ["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume", "count",
         "taker_buy_volume", "taker_buy_quote_volume", "ignore"]


def _read_zip_csv(p: Path, cols: list[str] | None) -> pd.DataFrame:
    with zipfile.ZipFile(p) as z:
        raw = z.read(z.namelist()[0]).decode()
    first = raw.split("\n", 1)[0]
    has_header = not first.split(",")[0].strip().lstrip("-").isdigit()
    return pd.read_csv(io.StringIO(raw), header=0 if has_header else None, names=None if has_header else cols)


def symbols() -> list[str]:
    s = json.loads((BIN / "symbols_fundingRate.json").read_text())
    out = []
    for x in s:
        if not x.endswith("USDT"):
            continue
        base = x[:-4]
        if base in EXCL_BASE:
            continue
        out.append(x)
    return sorted(out)


def tokenized_stock_bases() -> set[str]:
    """Bases equal to a US-listed equity ticker in the LSE stock catalog (applied only to symbols first listed >= 2025-01-01)."""
    cat = json.loads((ROOT / "data" / "lse_catalog_20260917.json").read_text())
    return {str(r["symbol"]).upper() for r in cat if r.get("dataset") == "stocks"}


@lru_cache(maxsize=None)
def klines(sym: str) -> pd.DataFrame:
    fs = sorted((BIN / "klines_1d" / sym).glob("*.zip"))
    if not fs:
        return pd.DataFrame()
    d = pd.concat([_read_zip_csv(f, KCOLS) for f in fs], ignore_index=True)
    d = d.rename(columns={c: c for c in d.columns})
    d["day"] = pd.to_datetime(pd.to_numeric(d["open_time"]), unit="ms").dt.normalize()
    d = d.drop_duplicates("day").set_index("day").sort_index()
    return d[["open", "close", "quote_volume"]].astype(float)


@lru_cache(maxsize=None)
def funding(sym: str) -> pd.Series:
    fs = sorted((BIN / "fundingRate" / sym).glob("*.zip"))
    if not fs:
        return pd.Series(dtype=float)
    d = pd.concat([_read_zip_csv(f, ["calc_time", "funding_interval_hours", "last_funding_rate"]) for f in fs], ignore_index=True)
    t = pd.to_datetime(pd.to_numeric(d["calc_time"]), unit="ms")
    return pd.Series(pd.to_numeric(d["last_funding_rate"]).to_numpy(), index=t).sort_index().groupby(level=0).last()


def panel(syms: list[str], start: str, end: str):
    """Daily panels (index = UTC day) of open, close, quote volume, signal, next-day funding paid."""
    days = pd.date_range(pd.Timestamp(start) - pd.Timedelta(days=90), end, freq="D")
    O, C, V, SIG, FUND, FIRST = {}, {}, {}, {}, {}, {}
    for s in syms:
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
        # signal at day t: settlements with calc_time in [t-7d, t)
        cs = f.cumsum()
        cnt = pd.Series(1.0, index=f.index).cumsum()
        def at(x, when):
            return x.reindex(x.index.union(when)).ffill().reindex(when).fillna(0.0)
        hi = days - pd.Timedelta(milliseconds=1)
        lo = days - pd.Timedelta(days=SIG_DAYS) - pd.Timedelta(milliseconds=1)
        ssum = at(cs, hi).to_numpy() - at(cs, lo).to_numpy()
        n = at(cnt, hi).to_numpy() - at(cnt, lo).to_numpy()
        SIG[s] = pd.Series(np.where(n >= MIN_SETTLE, ssum / SIG_DAYS, np.nan), index=days)
        # funding paid during day t: calc_time in (t, t+1d]
        a = at(cs, days + pd.Timedelta(days=1)).to_numpy() - at(cs, days).to_numpy()
        FUND[s] = pd.Series(a, index=days)
    return {k: pd.DataFrame(v) for k, v in dict(O=O, C=C, V=V, SIG=SIG, FUND=FUND).items()}, FIRST


def weights(P: dict, FIRST: dict, start: str, end: str, rng=None, stock_bases: set | None = None) -> pd.DataFrame:
    """Vectorised: eligibility -> top-N by trailing median quote volume -> bottom/top quintile of the funding signal."""
    O, C, V, SIG = P["O"], P["C"], P["V"], P["SIG"]
    days = pd.date_range(start, end, freq="D")
    cols = [s for s in O.columns if s in FIRST]
    stock_bases = stock_bases or set()
    medvol = V[cols].shift(1).rolling(VOL_LOOKBACK, min_periods=VOL_LOOKBACK // 2).median().reindex(days)
    first = pd.Series({s: FIRST[s] for s in cols})
    hist_ok = pd.DataFrame(((days.values[:, None] - first.values[None, :]) >= np.timedelta64(MIN_HIST, "D")), index=days, columns=cols)
    excl = pd.Series({s: bool(FIRST[s] >= pd.Timestamp("2025-01-01") and s[:-4] in stock_bases) for s in cols})
    elig = (hist_ok & C[cols].shift(1).reindex(days).notna() & SIG[cols].reindex(days).notna() & medvol.notna()
            & ~excl.reindex(cols).to_numpy()[None, :])
    univ = medvol.where(elig).rank(axis=1, ascending=False, method="first") <= TOP_N
    n = univ.sum(axis=1)
    sig = SIG[cols].reindex(days).where(univ)
    if rng is not None:
        a = sig.to_numpy().copy()
        for i in range(len(a)):
            m = ~np.isnan(a[i])
            a[i, m] = rng.permutation(a[i, m])
        sig = pd.DataFrame(a, index=days, columns=cols)
    r = sig.rank(axis=1, method="first")
    k = np.floor(Q * n).clip(lower=1)
    lo = r.le(k, axis=0)
    hi = r.gt(n - k, axis=0) & univ
    W = lo.mul(0.5 / k, axis=0) - hi.mul(0.5 / k, axis=0)
    W = W.reindex(columns=O.columns, fill_value=0.0).astype(float)
    W[n < MIN_UNIVERSE] = np.nan
    return W


def returns(P: dict, W: pd.DataFrame, cost_key: str) -> pd.Series:
    cost, delist = COSTS[cost_key]
    O, C, FUND = (P[k].reindex(W.index) for k in ("O", "C", "FUND"))
    live = W.notna().all(axis=1)
    Wf = W.fillna(0.0)
    r = (C / O - 1)
    missing = r.isna() & (Wf != 0)
    r = r.fillna(0.0)
    pnl = (Wf * r).sum(axis=1) - (missing * Wf.abs()).sum(axis=1) * delist   # missing day: 0 in base, adverse 20% in stress
    fund = -(Wf * FUND.fillna(0.0)).sum(axis=1)                  # long pays positive funding, short receives
    turn = Wf.diff().abs().sum(axis=1)
    turn.iloc[0] = Wf.iloc[0].abs().sum()
    out = pnl + fund - turn * cost
    return out[live]
