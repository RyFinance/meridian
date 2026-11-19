"""Shared loaders and trade math for crypto_deep. Sealed holdout: nothing dated after 2026-08-10 ET is kept.
All timestamps are naive US/Eastern wall-clock (bar start). Price helpers:
  Po(T)  = open of the 15m bar starting at T   (= the executable price at T)
  Pc(T)  = close of the 15m bar that completes at T (bar starting T-15m), i.e. info strictly before T
Decisions at T use Pc(T) only; entries/exits use Po(.) of the next bar. Costs: 10 bp round trip (5 bp/side).
"""
import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = "/Users/rytty/CCP/quant_v7/research/btc_ah/crypto_deep"
CUT = pd.Timestamp("2026-08-10 23:59:59")          # sealed: ET date <= 2026-08-10
DEV_END = pd.Timestamp("2022-12-31 23:59:59")      # dev = 2017-2022, check = 2023..2026-08-10
COST = 0.0010                                      # 10 bp round trip
M15 = pd.Timedelta("15min")


def _resample15(df):
    r = df.resample("15min", label="left", closed="left").agg({"o": "first", "h": "max", "l": "min", "c": "last"})
    return r.dropna(subset=["o"])


def load(asset):
    if asset == "BTC":
        b = pd.read_parquet("/Users/rytty/CCP/BTC-Acum/data/btc_usd_1m_candles_polymarket_arb.parquet")
        idx = pd.DatetimeIndex(b["timestamp"]).tz_convert(ET).tz_localize(None)
        df = pd.DataFrame({"o": b.open.values, "h": b.high.values, "l": b.low.values, "c": b.close.values}, index=idx)
    elif asset == "ETH":
        # Coinbase ETH-USD 5m pull already on disk (verified against a fresh curl pull, identical bars)
        e = pd.read_parquet("/Users/rytty/CCP/quant_v7/research/btc_ah/eth_names/data/eth_5m.parquet")
        idx = pd.DatetimeIndex(e["ts_utc"]).tz_localize("UTC").tz_convert(ET).tz_localize(None)
        df = pd.DataFrame({"o": e.open.values, "h": e.high.values, "l": e.low.values, "c": e.close.values}, index=idx)
    elif asset == "SOL":
        s = pd.read_parquet(f"{ROOT}/data/sol_15m.parquet")
        idx = pd.DatetimeIndex(s["ts_utc"]).tz_localize("UTC").tz_convert(ET).tz_localize(None)
        df = pd.DataFrame({"o": s.open.values, "h": s.high.values, "l": s.low.values, "c": s.close.values}, index=idx)
    else:
        raise ValueError(asset)
    df = df[df.index <= CUT].sort_index()
    df = df[~df.index.duplicated(keep="first")]
    return _resample15(df)


class Px:
    def __init__(self, B):
        self.B = B

    def o(self, ts):
        return self.B["o"].reindex(ts).to_numpy(dtype=float)

    def h(self, ts):
        return self.B["h"].reindex(ts).to_numpy(dtype=float)

    def l(self, ts):
        return self.B["l"].reindex(ts).to_numpy(dtype=float)

    def pc(self, ts):  # close of bar completing at ts
        return self.B["c"].reindex(ts - M15).to_numpy(dtype=float)

    def pc_at(self, ts):
        return self.pc(ts)


def trades(P, sig, entry_ts, exit_ts):
    """sig: signed signal return (sign gives direction). Returns arrays of net returns."""
    sig = np.asarray(sig, float)
    eo, xo = P.o(entry_ts), P.o(exit_ts)
    eh, el = P.h(entry_ts), P.l(entry_ts)
    xh, xl = P.h(exit_ts), P.l(exit_ts)
    s = np.sign(sig)
    gross = xo / eo - 1.0
    valid = np.isfinite(eo) & np.isfinite(xo) & np.isfinite(sig) & (s != 0)
    nw = s * gross - COST                  # continuation (with the signal)
    na = -s * gross - COST                 # against (flipped-direction control)
    # worst fills: long buys at high, sells at low; short sells at low, buys back at high
    ww = np.where(s > 0, xl / eh - 1.0, 1.0 - xh / el) - COST
    return valid, nw, na, ww


def summ(x):
    x = np.asarray(x, float)
    n = len(x)
    if n < 2:
        return dict(n=n, mean_bp=np.nan, t=np.nan)
    m = x.mean()
    sd = x.std(ddof=1)
    return dict(n=n, mean_bp=m * 1e4, t=m / (sd / np.sqrt(n)) if sd > 0 else np.nan)


def cell_stats(df, col):
    """df has columns nw, na, ww, entry (ts). Returns dict with stats for with-direction plus flip."""
    out = {}
    s = summ(df["nw"]) if col is None else None
    if len(df) < 2:
        return dict(n=len(df))
    x = df["nw"].to_numpy()
    y = df["na"].to_numpy()
    out["n"] = len(x)
    out["win_pct"] = 100 * (x > 0).mean()
    out["with_mean_bp"] = x.mean() * 1e4
    out["with_t"] = x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if x.std(ddof=1) > 0 else np.nan
    w = x[x > 0]
    l = x[x <= 0]
    out["avg_win_bp"] = w.mean() * 1e4 if len(w) else np.nan
    out["avg_loss_bp"] = l.mean() * 1e4 if len(l) else np.nan
    out["against_mean_bp"] = y.mean() * 1e4
    out["against_t"] = y.mean() / (y.std(ddof=1) / np.sqrt(len(y))) if y.std(ddof=1) > 0 else np.nan
    out["worst_with_bp"] = df["ww"].mean() * 1e4
    return out


def yearly(df):
    if len(df) == 0:
        return ""
    g = df.groupby(df["entry"].dt.year)["nw"].agg(["mean", "size"])
    return " ".join(f"{int(y)}:{m*1e4:+.0f}({int(k)})" for y, (m, k) in g.iterrows())
