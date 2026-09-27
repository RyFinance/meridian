"""Official regular-session opens and closes, with the source of every price.

Two sources:

* LSE Terminal (read-only MCP `get_history`, via research.lse_mcp_client).
  LSE `1d` bars for US listings are UTC-calendar-day bars that include pre- and
  after-hours trades, so they are NOT the official session (e.g. AZO 2026-09-22:
  LSE 1d open 2821.00, official open 2894.25). Sessions are therefore rebuilt
  from 30-minute bars filtered to 09:30 -> close (America/New_York):
  open = first regular bar's open, close = last regular bar's close. That close
  is the last continuous trade before the bell; the official close is the
  closing-auction print, which LSE stamps in the first after-hours bar. The two
  usually agree to a few basis points (reports/forward/lse_reconstruction_check.json).
* yfinance daily bars (auto_adjust=False): the exchange's official open/close,
  plus dividends and splits. Used as the cross-check, as the fallback for
  symbols LSE does not carry (SPMO), and for corporate actions.

Every returned row names the source of its open and close and, where both
sources exist, the difference in basis points.
"""
from __future__ import annotations

import datetime as dt
import io
from typing import Callable

import numpy as np
import pandas as pd

from research.forward import nyse

LSE_TIMEFRAME = "30m"
BAR_MINUTES = 30
LSE_CHUNK_DAYS = 120  # 32 extended-hours bars/day -> ~2,700 bars per request (cap 5,000)
SOURCE_LSE = "lse_30m_regular_session"
SOURCE_YF = "yfinance_daily_official"

Fetcher = Callable[[str, str, str, str, int], str]  # (symbol, timeframe, start, end, limit) -> CSV text


# -- LSE --------------------------------------------------------------------------

def parse_lse_csv(text: str) -> pd.DataFrame:
    """The CSV block of an LSE get_history answer (first line is a summary)."""
    lines = text.strip().splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("time,")), None)
    if start is None:
        return pd.DataFrame(columns=["time", "open", "high", "low", "close", "volume"])
    df = pd.read_csv(io.StringIO("\n".join(lines[start:])))
    df["time"] = pd.to_datetime(df["time"], utc=True)
    return df


def reconstruct_sessions(bars: pd.DataFrame, bar_minutes: int = BAR_MINUTES) -> pd.DataFrame:
    """Regular-session open/close per NYSE session from intraday bars (UTC)."""
    cols = ["open", "close", "n_bars", "complete", "first_bar_et", "last_bar_et"]
    if bars.empty:
        return pd.DataFrame(columns=cols)
    et = bars.assign(et=bars["time"].dt.tz_convert(nyse.ET))
    et["day"] = et["et"].dt.date
    rows = {}
    for day, group in et.groupby("day"):
        if not nyse.is_session(day):
            continue
        open_t = dt.datetime.combine(day, nyse.OPEN, tzinfo=nyse.ET)
        close_t = dt.datetime.combine(day, nyse.session_close_time(day), tzinfo=nyse.ET)
        regular = group[(group["et"] >= open_t) & (group["et"] < close_t)].sort_values("et")
        if regular.empty:
            continue
        first, last = regular.iloc[0], regular.iloc[-1]
        complete = bool(first["et"] == open_t and last["et"] == close_t - dt.timedelta(minutes=bar_minutes))
        rows[day] = {"open": float(first["open"]), "close": float(last["close"]), "n_bars": int(len(regular)),
                     "complete": complete, "first_bar_et": first["et"].strftime("%H:%M"),
                     "last_bar_et": last["et"].strftime("%H:%M")}
    return pd.DataFrame.from_dict(rows, orient="index", columns=cols)


def mcp_fetcher() -> Fetcher:
    """Read-only LSE fetcher over the user's configured MCP server (lazy start)."""
    from research.lse_mcp_client import Terminal, content_text

    holder: dict = {}

    def fetch(symbol: str, timeframe: str, start: str, end: str, limit: int) -> str:
        if "t" not in holder:
            holder["t"] = Terminal()
        result = holder["t"].call("get_history", {"symbol": symbol, "timeframe": timeframe, "start": start,
                                                  "end": end, "limit": limit, "provider": "lse"}, timeout=90)
        text = content_text(result)
        if result.get("isError"):
            raise LookupError(text)
        return text

    fetch.close = lambda: holder.pop("t").close() if "t" in holder else None  # type: ignore[attr-defined]
    return fetch


class LSESource:
    name = SOURCE_LSE

    def __init__(self, fetcher: Fetcher | None = None):
        self._fetcher = fetcher
        self.errors: dict[str, str] = {}

    @property
    def fetcher(self) -> Fetcher:
        if self._fetcher is None:
            self._fetcher = mcp_fetcher()
        return self._fetcher

    def bars(self, symbol: str, start: dt.date, end: dt.date, timeframe: str = LSE_TIMEFRAME) -> pd.DataFrame:
        """Bars with start <= ET day <= end (LSE's `end` is exclusive)."""
        frames, lo = [], start
        while lo <= end:
            hi = min(end, lo + dt.timedelta(days=LSE_CHUNK_DAYS - 1))
            try:
                text = self.fetcher(symbol, timeframe, lo.isoformat(), (hi + dt.timedelta(days=1)).isoformat(), 5000)
            except Exception as e:  # symbol not carried, MCP down, timeout: fall back, keep the reason
                self.errors[symbol] = str(e)[:200]
                return pd.DataFrame()
            frames.append(parse_lse_csv(text))
            lo = hi + dt.timedelta(days=1)
        frames = [f for f in frames if not f.empty]
        return pd.concat(frames, ignore_index=True).drop_duplicates("time") if frames else pd.DataFrame()

    def sessions(self, symbol: str, start: dt.date, end: dt.date) -> pd.DataFrame:
        bars = self.bars(symbol, start, end)
        return reconstruct_sessions(bars) if not bars.empty else reconstruct_sessions(pd.DataFrame())

    def close(self):
        closer = getattr(self._fetcher, "close", None)
        if closer:
            closer()


# -- yfinance -------------------------------------------------------------------------

class YFSource:
    name = SOURCE_YF

    def __init__(self, history: Callable[[str, dt.date, dt.date], pd.DataFrame] | None = None):
        self._history = history
        self.errors: dict[str, str] = {}

    def _download(self, symbol: str, start: dt.date, end: dt.date) -> pd.DataFrame:
        import yfinance as yf

        return yf.Ticker(symbol).history(start=start.isoformat(), end=(end + dt.timedelta(days=1)).isoformat(),
                                         auto_adjust=False, actions=True)

    def sessions(self, symbol: str, start: dt.date, end: dt.date) -> pd.DataFrame:
        """open, close (nominal, official), dividend (per share, ex-date), split (ratio, 0 = none)."""
        try:
            raw = (self._history or self._download)(symbol, start, end)
        except Exception as e:  # network / symbol errors are data, not crashes
            self.errors[symbol] = repr(e)[:200]
            raw = pd.DataFrame()
        cols = ["open", "close", "dividend", "split"]
        if raw is None or raw.empty:
            return pd.DataFrame(columns=cols)
        idx = [pd.Timestamp(t).date() for t in raw.index]
        out = pd.DataFrame({
            "open": raw["Open"].to_numpy(dtype=float), "close": raw["Close"].to_numpy(dtype=float),
            "dividend": raw["Dividends"].to_numpy(dtype=float) if "Dividends" in raw else 0.0,
            "split": raw["Stock Splits"].to_numpy(dtype=float) if "Stock Splits" in raw else 0.0,
        }, index=idx)
        return out[[start <= d <= end for d in out.index]]


# -- merged -----------------------------------------------------------------------------

def _bps(a, b) -> float | None:
    if a is None or b is None or not np.isfinite(a) or not np.isfinite(b) or b == 0:
        return None
    return float((a / b - 1.0) * 1e4)


def official_sessions(symbol: str, start: dt.date, end: dt.date, prefer: str = "lse",
                      lse: LSESource | None = None, yfs: YFSource | None = None) -> pd.DataFrame:
    """One row per session in [start, end] with a usable open or close.

    Columns: open, close, open_source, close_source, lse_open, lse_close,
    lse_complete, yf_open, yf_close, open_diff_bps, close_diff_bps (LSE vs
    yfinance), dividend, split."""
    if prefer not in {"lse", "yfinance"}:
        raise ValueError("prefer must be 'lse' or 'yfinance'")
    lse_df = lse.sessions(symbol, start, end) if lse is not None else pd.DataFrame()
    yf_df = yfs.sessions(symbol, start, end) if yfs is not None else pd.DataFrame()
    rows = {}
    for day in nyse.sessions_between(start, end):
        l = lse_df.loc[day] if day in lse_df.index else None
        y = yf_df.loc[day] if day in yf_df.index else None
        l_ok = l is not None and bool(l["complete"])
        l_open = float(l["open"]) if l is not None else None
        l_close = float(l["close"]) if l is not None else None
        y_open = float(y["open"]) if y is not None and np.isfinite(y["open"]) else None
        y_close = float(y["close"]) if y is not None and np.isfinite(y["close"]) else None
        picks = []
        for field, lv, yv in (("open", l_open, y_open), ("close", l_close, y_close)):
            order = [(lv if l_ok else None, SOURCE_LSE), (yv, SOURCE_YF)]
            if prefer == "yfinance":
                order.reverse()
            value, source = next(((v, s) for v, s in order if v is not None), (None, None))
            picks.append((value, source))
        if picks[0][0] is None and picks[1][0] is None:
            continue
        rows[day] = {
            "open": picks[0][0], "close": picks[1][0], "open_source": picks[0][1], "close_source": picks[1][1],
            "lse_open": l_open, "lse_close": l_close, "lse_complete": l_ok if l is not None else None,
            "yf_open": y_open, "yf_close": y_close,
            "open_diff_bps": _bps(l_open, y_open), "close_diff_bps": _bps(l_close, y_close),
            "dividend": float(y["dividend"]) if y is not None and np.isfinite(y["dividend"]) else 0.0,
            "split": float(y["split"]) if y is not None and np.isfinite(y["split"]) else 0.0,
        }
    return pd.DataFrame.from_dict(rows, orient="index")


class PriceBook:
    """Caches official_sessions per symbol for one evaluation / recording run."""

    def __init__(self, prefer: str = "lse", lse: LSESource | None = None, yfs: YFSource | None = None):
        self.prefer = prefer
        self.lse = lse
        self.yfs = yfs
        self._cache: dict[tuple[str, dt.date, dt.date], pd.DataFrame] = {}

    def get(self, symbol: str, start: dt.date, end: dt.date) -> pd.DataFrame:
        key = (symbol, start, end)
        if key not in self._cache:
            self._cache[key] = official_sessions(symbol, start, end, self.prefer, self.lse, self.yfs)
        return self._cache[key]

    def sources_used(self) -> dict:
        out = {}
        for (symbol, _, _), df in self._cache.items():
            if df.empty:
                out[symbol] = {"open": [], "close": []}
                continue
            out[symbol] = {"open": sorted(df["open_source"].dropna().unique().tolist()),
                           "close": sorted(df["close_source"].dropna().unique().tolist())}
        return out

    def errors(self) -> dict:
        return {"lse": dict(self.lse.errors) if self.lse else {}, "yfinance": dict(self.yfs.errors) if self.yfs else {}}

    def close(self):
        if self.lse is not None:
            self.lse.close()


def default_pricebook(prefer: str = "lse") -> PriceBook:
    return PriceBook(prefer=prefer, lse=LSESource(), yfs=YFSource())
