"""Instrument-level synthetic excess-return constructions, FOR DATA QA ONLY.

Hard rule honoured: nothing here conditions on a signal, sorts on carry, forms a strategy, control
or portfolio, or relates any signal to future returns. Each output row is one instrument's own
daily excess return (or its carry INPUT level), used to measure synthetic-construction error
against real investable proxies in ``audit.py``.

Declared constructions (all parameters fixed before any comparison was run):
  * Short rate r_f(d) for currency/country c: official DAILY rate where one exists (table
    SHORT_DAILY), else OECD monthly IR3TIB, else IRSTCI, *of the previous calendar month*
    (OECD values are monthly AVERAGES, only known after month-end), forward-filled daily.
    Daily official rates are also lagged one observation (known at t-1). Percent p.a.
  * Bonds, constant maturity T, yield y (decimal) from a published curve point:
        r_t = y_{t-1}*dt - D_{t-1}*dy + 0.5*C_{t-1}*dy^2 ,  dt = calendar days/365
        excess_t = r_t - r_f,{t-1}*dt
    D, C = modified duration and convexity of a PAR bond (coupon = y_{t-1}, frequency f) for par
    or benchmark/CMT yields; for zero-coupon points D=T/(1+y), C=T(T+1)/(1+y)^2. No roll-down.
  * FX (long foreign currency vs USD), S = USD per unit of currency (H.10 noon NY unless noted):
        excess_t = S_t/S_{t-1} - 1 + (r_f,ccy - r_f,USD)_{t-1}*dt
  * Equity: price index (local, price-only) + dividend-yield estimate - local cash:
        excess_t = P_t/P_{t-1} - 1 + dy_{t-1}*dt - r_f,{t-1}*dt
    dy = trailing-12-month distributions of the mapped ETF / ETF close (known at t-1).
    Total-return indices (^SP500TR, ^GDAXI) and ETF adjusted closes give 'reference' excess returns.

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.core_premia_data.rates_fx_eq.synthetic
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from research.core_premia_data.rates_fx_eq.common import META, PROC, SYN, utc_now, write_json

# currency -> (OECD ref_area, [daily official short-rate (source, series_id, tenor)])
CCY = {
    "USD": ("USA", [("fed_h15", "RIFLGFCM03_N.B")]),
    "EUR": ("EA20", [("ecb", "YC_AAA_SR_3M")]),
    "DEM": ("DEU", []), "JPY": ("JPN", []),
    "GBP": ("GBR", [("boe_iadb", "IUDVCDA"), ("boe_iadb", "IUDSOIA")]),
    "CAD": ("CAN", [("boc_valet", "V80691303")]),
    "SEK": ("SWE", [("riksbank", "SETB3MBENCH")]),
    "NOK": ("NOR", [("norges_bank", "GOVT_GENERIC_RATES.B.3M.TBIL")]),
    "CHF": ("CHE", []), "AUD": ("AUS", []), "NZD": ("NZL", []), "DKK": ("DNK", []),
    "MXN": ("MEX", []), "KRW": ("KOR", []), "INR": ("IND", []), "ZAR": ("ZAF", []),
    "CNY": ("CHN", []), "BRL": ("BRA", []), "HKD": (None, []), "SGD": (None, []),
    "MYR": (None, []), "TWD": (None, []), "THB": (None, []), "LKR": (None, []), "VEB": (None, []),
    "IDR": ("IDN", []), "TRY": ("TUR", []), "PLN": ("POL", []), "ILS": ("ISR", []),
}
COUNTRY_CCY = {"US": "USD", "DE": "EUR", "FR": "EUR", "IT": "EUR", "ES": "EUR", "JP": "JPY", "UK": "GBP",
               "CA": "CAD", "SE": "SEK", "NO": "NOK", "CH": "CHF", "AU": "AUD", "NZ": "NZD", "MX": "MXN",
               "KR": "KRW", "IN": "INR", "ZA": "ZAR", "CN": "CNY", "BR": "BRL", "ID": "IDR", "TR": "TRY",
               "EA_AAA": "EUR"}
# country OECD area used for the country's own *bond financing* rate (EUR members use EA20 after 1999,
# national before) -- here simply the currency's rate, i.e. EUR members financed at EUR rate.
ANNUAL_COUPON = {"DE", "FR", "IT", "ES", "CH", "SE", "NO", "EA_AAA"}


def load():
    y = pd.read_parquet(PROC / "yields_daily.parquet")
    fx = pd.read_parquet(PROC / "fx_spot_daily.parquet")
    o = pd.read_parquet(PROC / "oecd_monthly.parquet")
    m = pd.read_parquet(PROC / "market_daily.parquet")
    dv = pd.read_parquet(PROC / "dividends.parquet")
    return y, fx, o, m, dv


def short_rate(ccy: str, y: pd.DataFrame, o: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    """Daily r_f (% p.a.) known at each date, plus which source supplied it."""
    area, dailies = CCY.get(ccy, (None, []))
    out = pd.DataFrame(index=index)
    out["rf_pct"], out["rf_source"] = np.nan, None
    if area is not None:
        for meas in ("IRSTCI", "IR3TIB"):  # IR3TIB overrides IRSTCI where both exist
            s = o[(o.ref_area == area) & (o.measure == meas)].set_index("month")["value_pct"].sort_index()
            if s.empty:
                continue
            # value for month M is the M average -> usable from the first day of M+1
            s.index = s.index + pd.Timedelta(days=1)
            s = s.reindex(index.union(s.index)).ffill().reindex(index)
            # only fill forward at most ~2 months past the last available monthly value
            last_ok = o[(o.ref_area == area) & (o.measure == meas)]["month"].max() + pd.Timedelta(days=62)
            s[index > last_ok] = np.nan
            mask = s.notna()
            out.loc[mask, "rf_pct"] = s[mask]
            out.loc[mask, "rf_source"] = f"oecd_{meas}_{area}_prev_month_avg"
    for src, sid in dailies:  # later entries override earlier where present
        s = y[(y.source == src) & (y.series_id == sid)].set_index("date")["value_pct"].sort_index()
        if s.empty:
            continue
        s = s.shift(1)  # known at t-1 close
        s = s.reindex(index.union(s.index)).ffill(limit=10).reindex(index)
        s[index > y[(y.source == src) & (y.series_id == sid)]["date"].max() + pd.Timedelta(days=10)] = np.nan
        mask = s.notna()
        out.loc[mask, "rf_pct"] = s[mask]
        out.loc[mask, "rf_source"] = f"{src}:{sid}_lag1"
    return out


def _par_price(c, y, T, f):
    n = np.maximum(np.round(T * f), 1)
    v = 1.0 / (1.0 + y / f)
    ann = np.where(np.abs(y) < 1e-10, n, (1 - v ** n) / np.where(np.abs(y) < 1e-10, 1, y / f))
    return (c / f) * ann + v ** n


def par_dur_conv(y: np.ndarray, T: float, f: int):
    h = 1e-5
    p0 = _par_price(y, y, T, f)
    pu, pd_ = _par_price(y, y + h, T, f), _par_price(y, y - h, T, f)
    D = -(pu - pd_) / (2 * h) / p0
    C = (pu - 2 * p0 + pd_) / (h * h) / p0
    return D, C


def bond_excess(series: pd.Series, T: float, kind: str, country: str, rf: pd.DataFrame) -> pd.DataFrame:
    s = series.dropna().sort_index() / 100.0
    df = pd.DataFrame({"y": s})
    df["y_lag"] = df["y"].shift(1)
    df["dy"] = df["y"] - df["y_lag"]
    df["dt"] = df.index.to_series().diff().dt.days / 365.0
    if kind.startswith("zero"):
        D = T / (1 + df["y_lag"])
        C = T * (T + 1) / (1 + df["y_lag"]) ** 2
    else:
        D, C = par_dur_conv(df["y_lag"].values, T, 1 if country in ANNUAL_COUPON else 2)
    df["dur"], df["conv"] = D, C
    df["carry_income"] = df["y_lag"] * df["dt"]
    df["price_ret"] = -df["dur"] * df["dy"] + 0.5 * df["conv"] * df["dy"] ** 2
    df["total_ret"] = df["carry_income"] + df["price_ret"]
    r = rf.reindex(df.index)
    df["rf_pct"], df["rf_source"] = r["rf_pct"], r["rf_source"]
    df["excess_ret"] = df["total_ret"] - df["rf_pct"] / 100.0 * df["dt"]
    df["gap_days"] = df.index.to_series().diff().dt.days
    return df.iloc[1:]


# Primary daily curve point per bond market (country, tenor): (source, series_id, kind)
BOND_SPECS = {
    ("US", 2): ("fed_h15", "RIFLGFCY02_N.B", "par"), ("US", 5): ("fed_h15", "RIFLGFCY05_N.B", "par"),
    ("US", 7): ("fed_h15", "RIFLGFCY07_N.B", "par"), ("US", 10): ("fed_h15", "RIFLGFCY10_N.B", "par"),
    ("US", 20): ("fed_h15", "RIFLGFCY20_N.B", "par"), ("US", 30): ("fed_h15", "RIFLGFCY30_N.B", "par"),
    ("DE", 2): ("bundesbank", "BBSIS.D.I.ZAR.ZI.EUR.S1311.B.A604.R02XX.R.A.A._Z._Z.A", "par"),
    ("DE", 5): ("bundesbank", "BBSIS.D.I.ZAR.ZI.EUR.S1311.B.A604.R05XX.R.A.A._Z._Z.A", "par"),
    ("DE", 10): ("bundesbank", "BBSIS.D.I.ZAR.ZI.EUR.S1311.B.A604.R10XX.R.A.A._Z._Z.A", "par"),
    ("JP", 2): ("mof_japan", "JGB_2Y", "par"), ("JP", 10): ("mof_japan", "JGB_10Y", "par"),
    ("JP", 7): ("mof_japan", "JGB_7Y", "par"),
    ("UK", 5): ("boe_iadb", "IUDSNPY", "par"), ("UK", 10): ("boe_iadb", "IUDMNPY", "par"),
    ("UK", 20): ("boe_iadb", "IUDLNPY", "par"),
    ("UK_ZC", 10): ("boe_iadb", "IUDMNZC", "zero"),
    ("CA", 2): ("boc_valet", "BD.CDN.2YR.DQ.YLD", "par"), ("CA", 10): ("boc_valet", "BD.CDN.10YR.DQ.YLD", "par"),
    ("CA", 30): ("boc_valet", "BD.CDN.LONG.DQ.YLD", "par"),
    ("FR", 10): ("lse_vault_legacy_bonds_1995window", "bonds/FR10Y", "par"),
    ("IT", 10): ("lse_vault_legacy_bonds_1995window", "bonds/IT10Y", "par"),
    ("ES", 10): ("lse_vault_legacy_bonds_1995window", "bonds/ES10Y", "par"),
    ("AU", 10): ("lse_vault_legacy_bonds_full", "bonds/AU10Y", "par"),
    ("CH", 10): ("lse_vault_legacy_bonds_1995window", "bonds/CH10Y", "par"),
    ("SE", 10): ("riksbank", "SEGVB10YC", "par"),
    ("NO", 10): ("lse_vault_legacy_bonds_1995window", "bonds/NO10Y", "par"),
    ("NZ", 10): ("lse_vault_legacy_bonds_1995window", "bonds/NZ10Y", "par"),
    ("EA_AAA", 10): ("ecb", "YC_AAA_SR_10Y", "zero"),
    ("MX", 10): ("lse_vault_legacy_bonds_full", "bonds/MX10Y", "par"),
    ("KR", 10): ("lse_vault_legacy_bonds_full", "bonds/KR10Y", "par"),
    ("IN", 10): ("lse_vault_legacy_bonds_full", "bonds/IN10Y", "par"),
    ("CN", 10): ("lse_vault_legacy_bonds_full", "bonds/CN10Y", "par"),
    ("ZA", 10): ("lse_vault_legacy_bonds_full", "bonds/ZA10Y", "par"),
    ("BR", 10): ("lse_vault_legacy_bonds_full", "bonds/BR10Y", "par"),
    ("ID", 10): ("lse_vault_legacy_bonds_full", "bonds/ID10Y", "par"),
    ("TR", 10): ("lse_vault_legacy_bonds_full", "bonds/TR10Y", "par"),
}

# Equity market -> (price index, TR index or None, ETF proxy, currency, continuous future or None)
EQUITY = {
    "US_SPX": ("^GSPC", "^SP500TR", "SPY", "USD", "ES=F"), "US_NDX": ("^NDX", None, "QQQ", "USD", "NQ=F"),
    "US_DJI": ("^DJI", None, "DIA", "USD", "YM=F"), "US_RUT": ("^RUT", None, "IWM", "USD", "RTY=F"),
    "CA": ("^GSPTSE", None, "EWC", "CAD", None), "UK": ("^FTSE", None, "EWU", "GBP", None),
    "UK_MID": ("^FTMC", None, None, "GBP", None),
    "DE": (None, "^GDAXI", "EWG", "EUR", None), "FR": ("^FCHI", None, "EWQ", "EUR", None),
    "IT": ("FTSEMIB.MI", None, "EWI", "EUR", None), "ES": ("^IBEX", None, "EWP", "EUR", None),
    "NL": ("^AEX", None, "EWN", "EUR", None), "CH": ("^SSMI", None, "EWL", "CHF", None),
    "EZ50": ("^STOXX50E", None, None, "EUR", None), "SE": ("^OMX", None, "EWD", "SEK", None),
    "BE": ("^BFX", None, "EWK", "EUR", None), "AT": ("^ATX", None, "EWO", "EUR", None),
    "JP": ("^N225", None, "EWJ", "JPY", "NKD=F"), "HK": ("^HSI", None, "EWH", "HKD", None),
    "AU": ("^AXJO", None, "EWA", "AUD", None), "AU_ALLORD": ("^AORD", None, None, "AUD", None),
    "SG": ("^STI", None, "EWS", "SGD", None), "KR": ("^KS11", None, "EWY", "KRW", None),
    "TW": ("^TWII", None, "EWT", "TWD", None), "BR": ("^BVSP", None, "EWZ", "BRL", None),
    "MX": ("^MXX", None, "EWW", "MXN", None), "IN": ("^BSESN", None, "INDA", "INR", None),
    "IN_NIFTY": ("^NSEI", None, None, "INR", None), "CN": ("000001.SS", None, "FXI", "CNY", None),
    "MY": ("^KLSE", None, "EWM", "MYR", None), "ID": ("^JKSE", None, None, "IDR", None),
    "TR": ("XU100.IS", None, "TUR", "TRY", None), "IL": ("^TA125.TA", None, "EIS", "ILS", None),
    "NZ": ("^NZ50", None, "ENZL", "NZD", None), "AR": ("^MERV", None, None, "USD?", None),
    "ZA": (None, None, "EZA", "ZAR", None), "DK": (None, None, "EDEN", "DKK", None),
    "NO": (None, None, "ENOR", "NOK", None), "PL": (None, None, "EPOL", "PLN", None),
}


def run():
    y, fx, o, m, dv = load()
    idx = pd.bdate_range("1960-01-01", "2026-09-30")
    rf = {c: short_rate(c, y, o, idx) for c in CCY}
    rows = []
    for c, d in rf.items():
        dd = d.dropna(subset=["rf_pct"]).reset_index(names="date")
        dd["ccy"] = c
        rows.append(dd)
    rfp = pd.concat(rows, ignore_index=True)
    rfp.to_parquet(SYN / "short_rates_daily.parquet", index=False)

    # bonds
    brows, bmeta = [], {}
    for (ctry, T), (src, sid, kind) in BOND_SPECS.items():
        s = y[(y.source == src) & (y.series_id == sid)].set_index("date")["value_pct"]
        if s.empty:
            bmeta[f"{ctry}_{T}y"] = {"error": "no series"}
            continue
        ccy = COUNTRY_CCY[ctry.split("_ZC")[0]]
        df = bond_excess(s, T, kind, ctry.split("_ZC")[0], rf[ccy])
        df = df.reset_index(names="date")
        df["market_id"], df["country"], df["tenor_y"], df["source"], df["series_id"], df["kind"] = \
            f"BOND_{ctry}_{T}Y", ctry, T, src, sid, kind
        brows.append(df)
        bmeta[f"BOND_{ctry}_{T}Y"] = {"rows": len(df), "first": str(df.date.min().date()), "last": str(df.date.max().date()),
                                     "rf_missing_rows": int(df.rf_pct.isna().sum()), "max_gap_days": int(df.gap_days.max())}
    b = pd.concat(brows, ignore_index=True)
    b.to_parquet(SYN / "bond_excess_daily.parquet", index=False)

    # FX (H.10 primary; ECB and LSE-legacy EUR etc. kept as alt sources)
    frows, fmeta = [], {}
    usd = rf["USD"]
    for (src, ccy), g in fx.groupby(["source", "ccy"]):
        s = g.set_index("date")["usd_per_ccy"].sort_index()
        s = s[~s.index.duplicated()]
        df = pd.DataFrame({"S": s})
        df["spot_ret"] = df["S"] / df["S"].shift(1) - 1
        df["dt"] = df.index.to_series().diff().dt.days / 365.0
        rfc = rf.get(ccy, pd.DataFrame(index=idx, columns=["rf_pct", "rf_source"])).reindex(df.index)
        df["rf_ccy_pct"], df["rf_ccy_source"] = rfc["rf_pct"], rfc["rf_source"]
        df["rf_usd_pct"] = usd.reindex(df.index)["rf_pct"]
        df["carry_diff_pct"] = df["rf_ccy_pct"] - df["rf_usd_pct"]
        df["excess_ret"] = df["spot_ret"] + df["carry_diff_pct"] / 100.0 * df["dt"]
        df = df.iloc[1:].reset_index(names="date")
        df["market_id"], df["ccy"], df["source"] = f"FX_{ccy}", ccy, src
        frows.append(df)
        fmeta[f"{src}/{ccy}"] = {"rows": len(df), "first": str(df.date.min().date()), "last": str(df.date.max().date()),
                                 "carry_missing_rows": int(df.carry_diff_pct.isna().sum())}
    f = pd.concat(frows, ignore_index=True)
    f.to_parquet(SYN / "fx_excess_daily.parquet", index=False)

    # equity: price+dy-cash synthetic, TR-index excess, ETF excess (USD), futures price returns
    mk = {t: g.set_index("date").sort_index() for t, g in m.groupby("ticker")}
    divs = {t: g.set_index("date")["amount"].sort_index() for t, g in dv.groupby("ticker")} if len(dv) else {}
    erows, emeta = [], {}
    for mid, (px, tr, etf, ccy, fut) in EQUITY.items():
        dy = None
        if etf and etf in mk:
            e = mk[etf]
            dser = divs.get(etf, pd.Series(dtype=float)).reindex(e.index).fillna(0.0)
            ttm = dser.rolling("365D").sum()
            # only after 12 months of ETF history; known at t-1 (shift)
            valid = e.index >= e.index[0] + pd.Timedelta(days=365)
            dy = (ttm / e["close"]).where(valid).shift(1)
        rfc = rf.get(ccy, pd.DataFrame(index=idx, columns=["rf_pct", "rf_source"]))
        for role, tick in (("price_index", px), ("tr_index", tr), ("etf_usd", etf), ("future_cont_usd", fut)):
            if not tick or tick not in mk:
                continue
            d = mk[tick]
            col = "adjclose" if role == "etf_usd" else "close"
            df = pd.DataFrame({"level": d[col]})
            df["ret"] = df["level"] / df["level"].shift(1) - 1
            df["dt"] = df.index.to_series().diff().dt.days / 365.0
            cash = (usd if role in ("etf_usd", "future_cont_usd") else rfc).reindex(df.index)
            df["rf_pct"], df["rf_source"] = cash["rf_pct"], cash["rf_source"]
            if role == "price_index":
                df["dy_est"] = dy.reindex(df.index).ffill(limit=5) if dy is not None else np.nan
                df["excess_ret"] = df["ret"] + df["dy_est"] * df["dt"] - df["rf_pct"] / 100 * df["dt"]
            elif role == "future_cont_usd":
                df["dy_est"] = np.nan
                df["excess_ret"] = df["ret"]  # futures price return is already an excess return (roll gaps!)
            else:
                df["dy_est"] = np.nan
                df["excess_ret"] = df["ret"] - df["rf_pct"] / 100 * df["dt"]
            df = df.iloc[1:].reset_index(names="date")
            df["market_id"], df["role"], df["ticker"], df["ccy"] = f"EQ_{mid}", role, tick, ("USD" if role in ("etf_usd", "future_cont_usd") else ccy)
            erows.append(df)
            emeta[f"EQ_{mid}/{role}/{tick}"] = {"rows": len(df), "first": str(df.date.min().date()),
                                                "last": str(df.date.max().date()),
                                                "excess_missing": int(df.excess_ret.isna().sum())}
    eq = pd.concat(erows, ignore_index=True)
    eq.to_parquet(SYN / "equity_excess_daily.parquet", index=False)
    write_json(META / "synthetic_record.json", {"built_at_utc": utc_now().isoformat(), "bonds": bmeta, "fx": fmeta,
                                                "equity": emeta})
    print(len(b), len(f), len(eq))


if __name__ == "__main__":
    run()
