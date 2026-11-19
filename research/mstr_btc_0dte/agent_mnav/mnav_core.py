"""Shared, deliberately small mechanics for the gross-BTC mNAV research run.

This is a research-only daily equity simulator.  It never submits orders.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
MSTR_DAILY = PROJECT / "mstr_daily_yf.parquet"
BTC_1M = ROOT.parents[3] / "BTC-Acum" / "data" / "btc_usd_1m_candles_polymarket_arb.parquet"
SPLIT_DATE = pd.Timestamp("2024-08-08")
SEC_DIR = ROOT / "sec_source"


@dataclass(frozen=True)
class HoldingObservation:
    filing_date: str
    report_date: str
    form: str
    accession: str
    source_url: str
    share_asof: str
    class_a_shares: int
    class_b_shares: int
    btc_asof: str
    btc_held: int

    @property
    def total_common_shares(self) -> int:
        return self.class_a_shares + self.class_b_shares


def _parse_date(value: str) -> pd.Timestamp:
    normalized = value.replace("\xa0", " ").replace(" ,", ",")
    return pd.Timestamp(datetime.strptime(normalized, "%B %d, %Y").date())


def observations_from_filings(manifest_path: Path, *, through: str | None = None) -> list[HoldingObservation]:
    """Extract dated holdings/shares from cached 10-Q/10-K source documents.

    The cover's Class A/B count and the latest explicitly stated BTC count on
    or before each filing date are used.  Both become usable only *after* the
    filing date in the daily panel; the actual simulation adds a further close
    to next-open delay.
    """

    records = json.loads(manifest_path.read_text())
    root = manifest_path.parent
    out: list[HoldingObservation] = []
    cover_pattern = re.compile(
        r"As of ([A-Z][a-z]+\s+\d{1,2}\s*,\s*\d{4})\s*,\s*the\s+r\s*egistrant had "
        r"([\d,]+)\s+a\s*nd\s+([\d,]+) shares of class A common stock and class B common stock "
        r"outstanding, respectively",
        re.IGNORECASE,
    )
    btc_pattern = re.compile(
        r"As of ([A-Z][a-z]+\s+\d{1,2}\s*,\s*\d{4})\s*,\s*(?:we|the Company) held approximately "
        r"([\d,]+) bitcoins",
        re.IGNORECASE,
    )
    for record in records:
        if through is not None and record["filing_date"] > through:
            continue
        html = (root / record["file"]).read_bytes()
        text = " ".join(BeautifulSoup(html, "html.parser").stripped_strings).replace("\xa0", " ")
        cover = cover_pattern.search(text)
        if cover is None:
            raise ValueError(f"No Class A/B cover share count in {record['file']}")
        possible_btc = []
        filing_date = pd.Timestamp(record["filing_date"])
        for match in btc_pattern.finditer(text):
            asof = _parse_date(match.group(1))
            if asof <= filing_date:
                possible_btc.append((asof, int(match.group(2).replace(",", ""))))
        if not possible_btc:
            raise ValueError(f"No explicit BTC count in {record['file']}")
        btc_asof, btc_held = max(possible_btc, key=lambda x: x[0])
        out.append(
            HoldingObservation(
                filing_date=record["filing_date"],
                report_date=record["report_date"],
                form=record["form"],
                accession=record["accession"],
                source_url=record["url"],
                share_asof=_parse_date(cover.group(1)).strftime("%Y-%m-%d"),
                class_a_shares=int(cover.group(2).replace(",", "")),
                class_b_shares=int(cover.group(3).replace(",", "")),
                btc_asof=btc_asof.strftime("%Y-%m-%d"),
                btc_held=btc_held,
            )
        )
    return sorted(out, key=lambda r: r.filing_date)


def save_observations(records: Iterable[HoldingObservation], path: Path) -> pd.DataFrame:
    frame = pd.DataFrame([asdict(x) | {"total_common_shares": x.total_common_shares} for x in records])
    frame.to_csv(path, index=False)
    return frame


def _btc_at_equity_close(session_dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Return last source tick no later than 16:00 America/New_York per session."""

    raw = pd.read_parquet(BTC_1M, columns=["timestamp", "close"])
    raw = raw.dropna(subset=["timestamp", "close"]).sort_values("timestamp")
    stamps = pd.DatetimeIndex(raw["timestamp"])
    targets = (
        pd.DatetimeIndex(session_dates)
        .tz_localize("America/New_York")
        .normalize()
        + pd.Timedelta(hours=16)
    ).tz_convert("UTC")
    positions = stamps.searchsorted(targets, side="right") - 1
    valid_position = positions >= 0
    observed = pd.DatetimeIndex(
        [stamps[pos] if ok else pd.NaT for pos, ok in zip(positions, valid_position)]
    )
    lag_seconds = np.full(len(targets), np.nan)
    lag_seconds[valid_position] = (targets[valid_position] - observed[valid_position]).total_seconds()
    # The source has documented month-sized holes.  Treat anything more than
    # 15 minutes stale as unavailable; never carry a stale BTC value forward.
    usable = valid_position & (lag_seconds <= 15 * 60)
    closes = np.full(len(targets), np.nan)
    closes[usable] = raw["close"].to_numpy()[positions[usable]]
    return pd.DataFrame(
        {"btc_close_4pm_et": closes, "btc_lag_seconds": lag_seconds},
        index=session_dates,
    )


def build_panel(
    observations: list[HoldingObservation], *, start: str, end: str
) -> pd.DataFrame:
    """Build a causal daily gross-BTC mNAV-proxy panel.

    The ratio is MSTR class-A close times total A+B common shares divided by
    Bitcoin held times the 16:00 ET BTC spot price.  It deliberately excludes
    debt, preferred claims, cash, and the software business, so it is neither
    an enterprise mNAV nor the company-reported mNAV.
    """

    price = pd.read_parquet(MSTR_DAILY).sort_index().loc[start:end].copy()
    price.index = pd.DatetimeIndex(price.index).normalize()
    price.index.name = "date"
    btc = _btc_at_equity_close(price.index)
    panel = price[["Open", "Close"]].rename(columns={"Open": "mstr_open", "Close": "mstr_close"}).join(btc)
    panel["btc_held"] = np.nan
    panel["class_a_shares"] = np.nan
    panel["class_b_shares"] = np.nan
    panel["observation_filing_date"] = pd.NaT
    panel["observation_share_asof"] = pd.NaT
    for obs in observations:
        filing = pd.Timestamp(obs.filing_date)
        # Strictly later session prevents using an after-close filing on its
        # filing date.  The rule is then evaluated after that later close.
        use_dates = panel.index[panel.index > filing]
        if len(use_dates) == 0:
            continue
        available = use_dates[0]
        mask = panel.index >= available
        panel.loc[mask, "btc_held"] = obs.btc_held
        panel.loc[mask, "class_a_shares"] = obs.class_a_shares
        panel.loc[mask, "class_b_shares"] = obs.class_b_shares
        panel.loc[mask, "observation_filing_date"] = filing
        panel.loc[mask, "observation_share_asof"] = pd.Timestamp(obs.share_asof)
    panel["total_common_shares_reported"] = panel["class_a_shares"] + panel["class_b_shares"]
    # Price history is post-split adjusted.  The multiplier belongs to the
    # *reported share observation* rather than the current trading date: the
    # last pre-split report remains on a pre-split share basis for the few
    # sessions after the split until the first post-split filing is available.
    panel["split_factor_to_price_basis"] = np.where(
        panel["observation_share_asof"] < SPLIT_DATE, 10.0, 1.0
    )
    panel["total_common_shares_price_basis"] = (
        panel["total_common_shares_reported"] * panel["split_factor_to_price_basis"]
    )
    panel["gross_btc_mnav_proxy"] = (
        panel["mstr_close"] * panel["total_common_shares_price_basis"]
        / (panel["btc_held"] * panel["btc_close_4pm_et"])
    )
    panel["log_gross_btc_mnav_proxy"] = np.log(panel["gross_btc_mnav_proxy"])
    # We retain MSTR sessions after the first observable proxy value, including
    # later BTC-source gaps.  The signal code freezes the last stance in a gap,
    # while the simulator continues to book actual MSTR open-to-open P&L.
    first_usable = panel["gross_btc_mnav_proxy"].first_valid_index()
    if first_usable is None:
        raise ValueError("No usable gross-BTC mNAV observations in requested interval")
    return panel.loc[first_usable:].copy()


def premium_trend_signal(
    panel: pd.DataFrame,
    *,
    premium_momentum_days: int,
    premium_sma_days: int,
    btc_momentum_days: int | None = None,
    minimum_log_premium_momentum: float = 0.0,
) -> pd.Series:
    """Long-only premium-expansion trend signal, known after the close."""

    log_premium = panel["log_gross_btc_mnav_proxy"]
    premium_momentum = log_premium - log_premium.shift(premium_momentum_days)
    premium_trend = log_premium > log_premium.rolling(premium_sma_days).mean()
    signal = (premium_momentum > minimum_log_premium_momentum) & premium_trend
    valid = premium_momentum.notna() & premium_trend.notna()
    if btc_momentum_days is not None:
        log_btc = np.log(panel["btc_close_4pm_et"])
        btc_momentum = log_btc - log_btc.shift(btc_momentum_days)
        signal &= btc_momentum > 0.0
        valid &= btc_momentum.notna()
    # Incomplete lookbacks (including a genuine source hole) do not generate a
    # new order: carry the last causal stance rather than invent a BTC price or
    # artificially omit the associated MSTR P&L.
    held = signal.astype("boolean").where(valid).ffill().fillna(False)
    return held.astype(bool)


def simulate_long_only(
    panel: pd.DataFrame,
    close_signal: pd.Series,
    *,
    slippage_bps_each_side: float,
    commission_per_actual_share: float,
    start_long: bool = False,
) -> tuple[pd.Series, pd.DataFrame]:
    """Causal next-open execution with a cash/MSTR long-only portfolio.

    All OHLC fields are split-adjusted.  Before the 2024-08-08 10-for-1 split,
    one split-adjusted pseudo-share represents 0.1 actual historical share;
    fixed commission is therefore divided by ten for those observations.
    """

    signal = close_signal.reindex(panel.index).fillna(False).astype(bool)
    cash = 1.0
    shares = 0.0
    rows: list[dict[str, object]] = []
    trades: list[dict[str, object]] = []
    slip = slippage_bps_each_side / 10_000.0
    for i, (date, row) in enumerate(panel.iterrows()):
        desired_long = start_long if i == 0 else bool(signal.iloc[i - 1])
        price = float(row.mstr_open)
        commission = commission_per_actual_share / (10.0 if date < SPLIT_DATE else 1.0)
        was_long = shares > 0
        if desired_long and not was_long:
            execution_price = price * (1.0 + slip) + commission
            before = cash
            shares = cash / execution_price
            cash = 0.0
            trades.append(
                {
                    "date": date,
                    "side": "buy",
                    "mid_open": price,
                    "execution_price": execution_price,
                    "portfolio_before": before,
                    "portfolio_after": shares * price,
                }
            )
        elif not desired_long and was_long:
            execution_price = price * (1.0 - slip) - commission
            before = shares * price
            cash = shares * execution_price
            shares = 0.0
            trades.append(
                {
                    "date": date,
                    "side": "sell",
                    "mid_open": price,
                    "execution_price": execution_price,
                    "portfolio_before": before,
                    "portfolio_after": cash,
                }
            )
        nav = cash + shares * price
        rows.append({"date": date, "nav": nav, "long_after_open": int(shares > 0), "signal_prior_close": desired_long})
    # Report a fully realized, comparable result.  There is no next-session
    # data in the panel on which to defer this exit.
    if shares > 0:
        date = panel.index[-1]
        price = float(panel.iloc[-1].mstr_open)
        commission = commission_per_actual_share / (10.0 if date < SPLIT_DATE else 1.0)
        execution_price = price * (1.0 - slip) - commission
        before = shares * price
        cash = shares * execution_price
        shares = 0.0
        trades.append(
            {
                "date": date,
                "side": "sell_forced_final_open",
                "mid_open": price,
                "execution_price": execution_price,
                "portfolio_before": before,
                "portfolio_after": cash,
            }
        )
        rows[-1]["nav"] = cash
        rows[-1]["long_after_open"] = 0
    equity = pd.DataFrame(rows).set_index("date")["nav"]
    return equity, pd.DataFrame(trades)


def metrics(equity: pd.Series, trades: pd.DataFrame) -> dict[str, float | int | str]:
    if len(equity) < 2:
        raise ValueError("At least two sessions are required")
    # Capital is 1.0 immediately before the first included open.  Including it
    # makes an opening buy's costs count in return, Sharpe, and drawdown rather
    # than quietly normalizing them away when the run begins long.
    starting_nav = 1.0
    equity_with_start = pd.concat(
        [pd.Series([starting_nav], index=[equity.index[0] - pd.Timedelta(nanoseconds=1)]), equity]
    )
    daily = equity_with_start.pct_change().dropna()
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1.0 / 365.25)
    total_return = equity.iloc[-1] / starting_nav - 1.0
    cagr = (equity.iloc[-1] / starting_nav) ** (1.0 / years) - 1.0
    vol = daily.std(ddof=1)
    sharpe = np.sqrt(252.0) * daily.mean() / vol if vol > 0 else np.nan
    max_drawdown = (equity_with_start / equity_with_start.cummax() - 1.0).min()
    enters = int((trades["side"] == "buy").sum()) if not trades.empty else 0
    exits = int(trades["side"].astype(str).str.startswith("sell").sum()) if not trades.empty else 0
    return {
        "start": str(equity.index[0].date()),
        "end": str(equity.index[-1].date()),
        "sessions": int(len(equity)),
        "total_return": float(total_return),
        "cagr": float(cagr),
        "annualized_sharpe": float(sharpe),
        "max_drawdown": float(max_drawdown),
        "entry_trades": enters,
        "exit_trades": exits,
        "round_trips": float(min(enters, exits)),
        "time_long": float((equity.index.to_series().map(lambda x: 0)).mean()) if False else np.nan,
    }


def add_time_long(stat: dict[str, float | int | str], equity: pd.Series, trades: pd.DataFrame, panel: pd.DataFrame, signal: pd.Series, *, start_long: bool = False) -> dict[str, float | int | str]:
    """Add exposure using causal next-open signal timing without changing results."""
    desired = signal.reindex(panel.index).fillna(False).astype(bool).shift(1, fill_value=start_long)
    stat = dict(stat)
    stat["time_long"] = float(desired.mean())
    return stat


def per_calendar_year(
    panel: pd.DataFrame,
    signal: pd.Series,
    *,
    slippage_bps_each_side: float,
    commission_per_actual_share: float,
    start_long: bool = False,
) -> pd.DataFrame:
    """Independent calendar-year runs, with entry/exit costs each year."""
    rows = []
    for year, year_panel in panel.groupby(panel.index.year):
        year_signal = signal.reindex(year_panel.index)
        equity, trades = simulate_long_only(
            year_panel,
            year_signal,
            slippage_bps_each_side=slippage_bps_each_side,
            commission_per_actual_share=commission_per_actual_share,
            start_long=start_long,
        )
        row = metrics(equity, trades)
        row["year"] = int(year)
        rows.append(row)
    return pd.DataFrame(rows).set_index("year")
