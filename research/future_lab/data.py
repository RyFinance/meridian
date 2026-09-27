"""Joint daily panels for the future lab, built only from files already on disk (read-only).

Three panels. Every row is one historical trading date, so any resampler that draws rows keeps the
strategy, its controls, the market and the T-bill rate on the same dates (joint resampling).

- `pead`  2021-08-12 .. 2025-06-27. From reports/pead_audit/*_curves.csv (research/pead_audit/mtm_audit.py):
  `mtm_rf` = marked NAV with idle cash at T-bills; `rf_index` = cumulative Fama-French daily T-bill;
  `universe_control` / `spy_control` = the same trades placed in the equal-weight universe average /
  in SPY. Turnover = traded notional (entries + exits) / previous-day marked NAV, from the sweep ledger.
- `gold`  2017-01-04 .. 2026-09-16. From reports/momentum_gold_audit_20260921/{momentum,market}_gold_full.csv:
  `return` is the daily net total return of the 50/50 SPMO/GLD (and 50/50 SPY/GLD) ledger; `turnover` is
  traded notional / NAV. The first (initial purchase) and last (final liquidation) rows are dropped,
  so only the recurring monthly-rebalance turnover remains. T-bills: research.return_search.run.cash_rates.
- `long`  2005-01-04 .. 2026-09-17, a window-sensitivity panel: SPY, and a SIMPLIFIED 50/50 SPY/GLD
  (rebalanced at the first session close of each month, 5 bps a side). It is not the audited ledger;
  `tests/test_future_lab.py` checks it tracks market_gold_full closely on the overlap.

Regime variables are causal: the label on date t uses SPY closes up to t-1 only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PEAD_DIR = ROOT / "reports" / "pead_audit"
GOLD_DIR = ROOT / "reports" / "momentum_gold_audit_20260921"
ETF_DIR = ROOT / "data" / "multiasset" / "etf"
GOLD_END = "2026-09-17"
PEAD_START_CAPITAL = 100_000.0
VOL_WINDOW = 63
DD_WINDOW = 252
DD_THRESHOLD = -0.10


@dataclass
class Panel:
    """A joint daily panel. `returns` holds total daily returns (decimal) of every series, `rf` the
    daily T-bill return on the same dates, `turnover` traded notional / NAV for series that trade."""
    name: str
    returns: pd.DataFrame
    rf: pd.Series
    turnover: pd.DataFrame
    regimes: pd.DataFrame
    notes: dict = field(default_factory=dict)

    @property
    def dates(self) -> pd.DatetimeIndex:
        return self.returns.index

    def excess(self, col: str) -> pd.Series:
        return self.returns[col] - self.rf


def etf_close(ticker: str, end: str | None = None) -> pd.Series:
    d = pd.read_parquet(ETF_DIR / f"{ticker}.parquet", columns=["date", "close"])
    s = d.assign(date=pd.to_datetime(d["date"]).dt.tz_localize(None).dt.normalize()).set_index("date")["close"]
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s.loc[:end] if end else s


def spy_state(end: str | None = None) -> pd.DataFrame:
    """Causal SPY market-state variables on every SPY date (2003 onward).

    vol63: annualised std of the 63 daily returns ending at t-1.
    dd252: SPY close at t-1 relative to its max over the 252 closes ending at t-1.
    vol_tercile: 0/1/2 by fixed thresholds = terciles of vol63 over the whole SPY history 2003-2026
      (a broad reference distribution, not fitted to either candidate's window).
    dd_state: 1 if dd252 < -10%, else 0.
    """
    c = etf_close("SPY", end)
    r = c.pct_change(fill_method=None)
    vol = r.rolling(VOL_WINDOW).std().shift(1) * np.sqrt(252)
    lag = c.shift(1)
    dd = lag / lag.rolling(DD_WINDOW, min_periods=21).max() - 1
    q = vol.dropna().quantile([1 / 3, 2 / 3]).to_numpy()
    out = pd.DataFrame({"vol63": vol, "dd252": dd})
    out["vol_tercile"] = np.where(vol.isna(), -1, np.digitize(vol.fillna(0), q)).astype(int)
    out["dd_state"] = np.where(dd.isna(), -1, (dd < DD_THRESHOLD).astype(int)).astype(int)
    out.attrs["vol_thresholds"] = [float(x) for x in q]
    return out


def _regimes_for(dates: pd.DatetimeIndex) -> pd.DataFrame:
    st = spy_state()
    reg = st.reindex(dates, method="ffill")[["vol63", "dd252", "vol_tercile", "dd_state"]]
    if (reg[["vol_tercile", "dd_state"]] < 0).any().any():
        raise ValueError("regime variable undefined on some dates")
    reg.attrs["vol_thresholds"] = st.attrs["vol_thresholds"]
    return reg


def pead_turnover(name: str, nav: pd.Series) -> pd.Series:
    """Daily traded notional (entry notional + exit value) / previous-day marked NAV (dollars)."""
    from research.pead_audit.mtm_audit import positions

    p = positions(name)
    entry = p.groupby("entry_date")["notional"].sum()
    exit_value = (p["shares"] * p["exit_price"]).groupby(p["exit_date"]).sum()
    traded = entry.reindex(nav.index, fill_value=0.0) + exit_value.reindex(nav.index, fill_value=0.0)
    prev = nav.shift(1).fillna(PEAD_START_CAPITAL)
    return traded / prev


def load_pead() -> Panel:
    frames, turnover = {}, {}
    rf = None
    for name, key in [("wide_5p0", "pead_2x"), ("wide_2p5", "pead_2p5")]:
        c = pd.read_csv(PEAD_DIR / f"{name}_curves.csv", index_col=0, parse_dates=True)
        r = c.pct_change()
        frames[key] = r["mtm_rf"]
        frames[f"{key}_univ_ctl"] = r["universe_control"]
        frames[f"{key}_spy_ctl"] = r["spy_control"]
        turnover[key] = pead_turnover(name, c["mtm_rf"] * PEAD_START_CAPITAL)
        this_rf = r["rf_index"]
        rf = this_rf if rf is None else rf
        assert np.allclose(rf.dropna(), this_rf.dropna())
    ret = pd.DataFrame(frames)
    spy = etf_close("SPY").pct_change(fill_method=None)
    ret["spy"] = spy.reindex(ret.index)
    ret = ret.iloc[1:]  # first row has no return
    if ret.isna().any().any():
        raise ValueError(f"missing values in PEAD panel: {ret.isna().sum().to_dict()}")
    tov = pd.DataFrame(turnover).reindex(ret.index).fillna(0.0)
    return Panel("pead", ret, rf.reindex(ret.index), tov, _regimes_for(ret.index),
                 notes={"source": "reports/pead_audit/{wide_5p0,wide_2p5}_curves.csv; ledger turnover via "
                                   "research.pead_audit.mtm_audit.positions", "rf": "Fama-French daily rf"})


def load_gold() -> Panel:
    from research.return_search.run import cash_rates

    mg = pd.read_csv(GOLD_DIR / "momentum_gold_full.csv", index_col=0, parse_dates=True)
    sg = pd.read_csv(GOLD_DIR / "market_gold_full.csv", index_col=0, parse_dates=True)
    assert mg.index.equals(sg.index)
    rf_all = cash_rates(mg.index, GOLD_END)
    ret = pd.DataFrame({"spmo_gld": mg["return"], "spy_gld": sg["return"]})
    spy = etf_close("SPY").pct_change(fill_method=None)
    ret["spy"] = spy.reindex(ret.index)
    tov = pd.DataFrame({"spmo_gld": mg["turnover"], "spy_gld": sg["turnover"], "spy": 0.0})
    keep = ret.index[1:-1]  # drop initial purchase and final liquidation days
    ret, tov = ret.loc[keep], tov.loc[keep]
    if ret.isna().any().any():
        raise ValueError("missing values in gold panel")
    return Panel("gold", ret, rf_all.reindex(keep), tov, _regimes_for(keep),
                 notes={"source": "reports/momentum_gold_audit_20260921/{momentum,market}_gold_full.csv",
                        "rf": "research.return_search.run.cash_rates (IRX, lagged one day)",
                        "dropped": "first and last rows (initial purchase / final liquidation)"})


def simple_fixed_mix(closes: pd.DataFrame, weights: dict[str, float], one_way: float = 0.0005) -> pd.DataFrame:
    """Fixed-weight mix, rebalanced to target at the close of the first session of each month.
    Returns daily net return and turnover (traded notional / NAV). A simplified, close-to-close
    construction for the long-window sensitivity only."""
    r = closes.pct_change(fill_method=None).iloc[1:]
    cols = list(weights)
    w_target = np.array([weights[c] for c in cols])
    month = pd.Series(r.index.to_period("M"), index=r.index)
    rebal = month.ne(month.shift()).to_numpy()
    w = w_target.copy()
    out_r = np.empty(len(r))
    out_t = np.zeros(len(r))
    rv = r[cols].to_numpy()
    for i in range(len(r)):
        gross = w * (1 + rv[i])
        port = gross.sum()
        out_r[i] = port - 1
        w = gross / port
        if rebal[i]:
            t = np.abs(w_target - w).sum()
            out_t[i] = t
            out_r[i] -= t * one_way * (1 + out_r[i])
            w = w_target.copy()
    return pd.DataFrame({"return": out_r, "turnover": out_t}, index=r.index)


def load_long() -> Panel:
    from research.return_search.run import cash_rates

    closes = pd.DataFrame({"SPY": etf_close("SPY", GOLD_END), "GLD": etf_close("GLD", GOLD_END)}).dropna()
    closes = closes.loc["2004-12-31":]
    mix = simple_fixed_mix(closes, {"SPY": 0.5, "GLD": 0.5})
    ret = pd.DataFrame({"spy_gld": mix["return"], "spy": closes["SPY"].pct_change(fill_method=None).reindex(mix.index)})
    tov = pd.DataFrame({"spy_gld": mix["turnover"], "spy": 0.0})
    rf = cash_rates(ret.index, GOLD_END)
    return Panel("long", ret, rf, tov, _regimes_for(ret.index),
                 notes={"source": "data/multiasset/etf/{SPY,GLD}.parquet; simplified monthly 50/50 rebalance",
                        "rf": "research.return_search.run.cash_rates"})


# Candidate registry: which series is evaluated, against which control, in which panel.
CANDIDATES = {
    "pead_2x": {"panel": "pead", "series": "pead_2x", "control": "pead_2x_univ_ctl",
                "alt_control": "pead_2x_spy_ctl", "label": "PEAD 2x (5% positions)",
                "control_label": "same trades in universe average"},
    "pead_2p5": {"panel": "pead", "series": "pead_2p5", "control": "pead_2p5_univ_ctl",
                 "alt_control": "pead_2p5_spy_ctl", "label": "PEAD 2.5% (live)",
                 "control_label": "same trades in universe average"},
    "spmo_gld": {"panel": "gold", "series": "spmo_gld", "control": "spy_gld", "alt_control": None,
                 "label": "SPMO/GLD 50/50", "control_label": "SPY/GLD 50/50"},
    "spy_gld": {"panel": "gold", "series": "spy_gld", "control": "spy", "alt_control": None,
                "label": "SPY/GLD 50/50 (control)", "control_label": "SPY"},
    "spy": {"panel": "gold", "series": "spy", "control": None, "alt_control": None,
            "label": "SPY", "control_label": "T-bills"},
}
LONG_CANDIDATES = {
    "spy_gld_long": {"panel": "long", "series": "spy_gld", "control": "spy", "label": "SPY/GLD 50/50, 2005-2026 (simplified)",
                     "control_label": "SPY"},
    "spy_long": {"panel": "long", "series": "spy", "control": None, "label": "SPY, 2005-2026", "control_label": "T-bills"},
}


def load_all() -> dict[str, Panel]:
    return {"pead": load_pead(), "gold": load_gold(), "long": load_long()}
