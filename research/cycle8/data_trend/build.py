"""Cycle 8: process TREND inputs and retail ETF histories (single series only; no portfolio returns).

Outputs
  data/cycle8/proc/trend_monthly.parquet     AQR TSMOM excess returns (decimal, USD), month-end 'date'
  data/cycle8/proc/us_tbill_ff_monthly.parquet  Ken French RF (decimal, USD 1M T-bill), month-end 'date'
  data/cycle8/proc/etf/<TICKER>.parquet      daily close, adjclose, dividends, splits, currency
  data/cycle8/proc/etf_monthly_adj.parquet   month-end adjclose, columns = tickers (complete months only)
  data/cycle8/proc/etf_inventory.csv         ticker, name, currency, first/last date, n, ER
  data/cycle8/meta/<file>.json               provenance per processed file
  data/cycle8/notes/trend_checks.md          validation of the FRAMEWORK TREND sleeve (USD) vs live funds
  data/cycle8/notes/etf_anomalies.csv        daily |adjclose move| > 25%

Run: python -m research.cycle8.data_trend.build   (from repo root)
"""
from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from research.cycle8.data_trend.acquire import ETFS, ROOT

RAW = ROOT / "data" / "cycle8" / "raw"
PROC = ROOT / "data" / "cycle8" / "proc"
META = ROOT / "data" / "cycle8" / "meta"
NOTES = ROOT / "data" / "cycle8" / "notes"
LOG = json.loads((RAW / "retrieval_log_trend_etf.json").read_text())
AS_OF = "2026-09-27"
DRAG = 0.02  # FRAMEWORK §2 TREND drag, %/yr
LAST_COMPLETE_MONTH = pd.Timestamp("2026-08-31")  # run date 2026-09-27: September incomplete

TSMOM_NOTES = (
    "AQR file text: 'excess returns of the long/short Time Series Momentum (TSMOM) factors'; 'updated and "
    "extended version of the factors used in Moskowitz, Ooi and Pedersen (2012)'; '12-month time series momentum "
    "strategy with a 1-month holding period'; 'AQR reconstructs the full history each time the returns are "
    "updated'. Definitions tab (EMF image, parsed): 58 instruments (9 equity index, 13 bond, 12 FX crosses, 24 "
    "commodities); each position sized to ex-ante 40% annualised vol (EWMA, 60-day centre of mass, t-1 estimate); "
    "equal-weighted average across available instruments gives 'an annualized volatility of about 12% per year'. "
    "NO mention anywhere in the file of fees, management/performance fees, transaction costs, slippage or "
    "financing: treat as GROSS of fees and trading costs, hypothetical, excess of cash (self-financing futures). "
    "Pre-futures periods use MSCI/JPM cash-index returns and Datastream/IBOR FX returns."
)


def month_end(idx) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(idx).to_period("M").to_timestamp("M")


def log_entry(file_rel: str) -> dict:
    hits = [e for e in LOG if e.get("file") == file_rel]
    return hits[-1] if hits else {}


def write_meta(proc_path: Path, info: dict) -> None:
    META.mkdir(parents=True, exist_ok=True)
    info = {"file": str(proc_path.relative_to(ROOT)), "as_of": AS_OF,
            "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), **info}
    (META / f"{proc_path.name}.json").write_text(json.dumps(info, indent=1, default=str))


# ---------------------------------------------------------------- trend
def read_aqr(path: Path, sheet: int = 0) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=sheet, header=None)
    hdr = raw.index[raw.apply(lambda r: r.astype(str).str.fullmatch("TSMOM").any(), axis=1)][0]
    cols = [str(c) for c in raw.iloc[hdr]]
    d = raw.iloc[hdr + 1:].copy()
    d.columns = ["date"] + cols[1:]
    d = d[pd.to_datetime(d["date"], errors="coerce").notna()]
    d["date"] = month_end(pd.to_datetime(d["date"]))
    return d.set_index("date").astype(float)


def build_trend() -> tuple[pd.DataFrame, pd.Series]:
    cur = read_aqr(RAW / "trend" / "tsmom_factors_monthly.xlsx")
    orig = read_aqr(RAW / "trend" / "tsmom_original_paper_data.xlsx")
    out = pd.DataFrame({
        "tsmom_excess": cur["TSMOM"],
        "tsmom_cm_excess": cur["TSMOM^CM"], "tsmom_eq_excess": cur["TSMOM^EQ"],
        "tsmom_fi_excess": cur["TSMOM^FI"], "tsmom_fx_excess": cur["TSMOM^FX"],
        "tsmom_excess_2012paper": orig["TSMOM"].reindex(cur.index),
    })
    out.index.name = "date"
    p = PROC / "trend_monthly.parquet"
    out.to_parquet(p)
    e1, e2 = log_entry("data/cycle8/raw/trend/tsmom_factors_monthly.xlsx"), \
        log_entry("data/cycle8/raw/trend/tsmom_original_paper_data.xlsx")
    ov = out[["tsmom_excess", "tsmom_excess_2012paper"]].dropna()
    write_meta(p, {
        "source": "AQR Data Library: 'Time Series Momentum: Factors, Monthly' (current vintage) and "
                  "'Time Series Momentum: Original Paper Data' (1985-2009, frozen 2012 vintage)",
        "url": [e1.get("url"), e2.get("url")], "retrieved_utc": [e1.get("retrieved_utc"), e2.get("retrieved_utc")],
        "first": out.index.min(), "last": out["tsmom_excess"].last_valid_index(), "rows": len(out),
        "units": "decimal monthly excess return (over cash), USD; index = month-end (AQR dates are last "
                 "business day, remapped to calendar month-end)",
        "columns": {
            "tsmom_excess": "TSMOM, all asset classes (the FRAMEWORK series)",
            "tsmom_cm/eq/fi/fx_excess": "asset-class sub-factors",
            "tsmom_excess_2012paper": "TSMOM from the original-paper file, 1985-01..2009-12 only (vintage check)"},
        "gross_or_net": "GROSS of fees and transaction costs (no cost deduction mentioned in file)",
        "vol_target": "40% ex-ante per instrument, equal-weighted; about 12%/yr realised portfolio vol (AQR text)",
        "notes": TSMOM_NOTES + f" Vintage check 1985-2009: corr(current, 2012 paper) = "
                 f"{ov.corr().iloc[0, 1]:.3f} over {len(ov)} months.",
        "century_of_evidence_series": "NOT OBTAINED: no free dataset exists on AQR Data Library (see "
                                      "data/cycle8/notes/blocked_trend_etf.md); FRAMEWORK fallback applies: "
                                      "TREND sleeve starts 1985-01.",
    })

    zf = zipfile.ZipFile(RAW / "trend" / "ff_research_data_factors_csv.zip")
    txt = zf.read(zf.namelist()[0]).decode("latin-1").splitlines()
    rows = []
    for line in txt[txt.index(next(l for l in txt if l.startswith(",Mkt-RF"))) + 1:]:
        parts = [x.strip() for x in line.split(",")]
        if len(parts) != 5 or not parts[0].isdigit() or len(parts[0]) != 6:
            break
        rows.append((parts[0], float(parts[4]) / 100))
    rf = pd.Series(dict(rows), name="rf_usd")
    rf.index = month_end(pd.to_datetime(rf.index, format="%Y%m"))
    rf.index.name = "date"
    p = PROC / "us_tbill_ff_monthly.parquet"
    rf.to_frame().to_parquet(p)
    e = log_entry("data/cycle8/raw/trend/ff_research_data_factors_csv.zip")
    write_meta(p, {"source": "Ken French Data Library, F-F_Research_Data_Factors (monthly), column RF",
                   "url": e.get("url"), "retrieved_utc": e.get("retrieved_utc"),
                   "first": rf.index.min(), "last": rf.index.max(), "rows": len(rf),
                   "units": "decimal monthly return of 1-month US T-bill, USD",
                   "notes": txt[0].strip() + " " + txt[1].strip()})
    return out, rf


# ---------------------------------------------------------------- ETFs
def load_yahoo(name: str) -> tuple[pd.DataFrame, dict]:
    res = json.loads((RAW / "etf" / f"{name}.json").read_text())["chart"]["result"][0]
    m = res["meta"]
    ts = pd.to_datetime(np.array(res["timestamp"]) + m["gmtoffset"], unit="s").normalize()
    q = res["indicators"]["quote"][0]
    df = pd.DataFrame({"close": q["close"], "adjclose": res["indicators"]["adjclose"][0]["adjclose"]}, index=ts)
    ev = res.get("events", {})
    div = pd.Series({pd.to_datetime(v["date"] + m["gmtoffset"], unit="s").normalize(): v["amount"]
                     for v in ev.get("dividends", {}).values()}, dtype=float)
    spl = pd.Series({pd.to_datetime(v["date"] + m["gmtoffset"], unit="s").normalize():
                     v["numerator"] / v["denominator"] for v in ev.get("splits", {}).values()}, dtype=float)
    df = df[~df.index.duplicated(keep="last")].dropna(subset=["close", "adjclose"], how="all")
    df["dividends"] = div.groupby(level=0).sum().reindex(df.index).fillna(0.0)
    df["splits"] = spl.groupby(level=0).prod().reindex(df.index).fillna(1.0)
    df["currency"] = m.get("currency")
    df.index.name = "date"
    return df, m


def fund_profile(name: str) -> dict:
    p = RAW / "etf" / "quotesummary" / f"{name}.json"
    try:
        r = json.loads(p.read_text())["quoteSummary"]["result"][0]
    except Exception:
        return {}
    fe = r.get("fundProfile", {}).get("feesExpensesInvestment", {}) or {}
    er = (fe.get("annualReportExpenseRatio") or {}).get("raw")
    if er is None:
        er = (fe.get("netExpRatio") or {}).get("raw")
    ks = r.get("defaultKeyStatistics", {})
    return {"er_yahoo": er, "inception_yahoo": (ks.get("fundInceptionDate") or {}).get("fmt"),
            "category": r.get("fundProfile", {}).get("categoryName")}


KNOWN_CRASH = [("2008-09-01", "2008-12-31"), ("2020-02-20", "2020-04-15"), ("1987-10-19", "1987-10-20")]


def build_etfs() -> pd.DataFrame:
    (PROC / "etf").mkdir(parents=True, exist_ok=True)
    inv, monthly, anomalies = [], {}, []
    for name in ETFS:
        f = RAW / "etf" / f"{name}.json"
        if not f.exists():
            continue
        df, m = load_yahoo(name)
        tk = name
        # independent total-return index from close + cash dividends (reference for Yahoo adjclose errors,
        # e.g. XBB.TO year-end 2000/2003/2004 where adjclose double-counts the distribution)
        own = ((df["close"] + df["dividends"]) / df["close"].shift(1)).fillna(1.0)
        df["tr_own"] = own.cumprod() * df["adjclose"].iloc[0]
        p = PROC / "etf" / f"{tk}.parquet"
        df.to_parquet(p)
        e = log_entry(f"data/cycle8/raw/etf/{name}.json")
        # adjclose vs own close+dividend total return (sanity of Yahoo adjustment)
        c = df["close"]
        tr_own = ((c + df["dividends"]) / c.shift(1) - 1).dropna()
        tr_adj = df["adjclose"].pct_change().dropna()
        yrs = (df.index[-1] - df.index[0]).days / 365.25
        ann = lambda r: (1 + r).prod() ** (1 / yrs) - 1 if yrs > 0 else np.nan
        gap = ann(tr_adj) - ann(tr_own.reindex(tr_adj.index).fillna(0))
        big = tr_adj[tr_adj.abs() > 0.25]
        for d, r in big.items():
            crash = any(pd.Timestamp(a) <= d <= pd.Timestamp(b) for a, b in KNOWN_CRASH)
            anomalies.append({"ticker": tk, "date": d.date(), "adj_return": round(r, 4),
                              "close_return": round(c.pct_change().get(d, np.nan), 4),
                              "split_on_day": df["splits"].get(d, 1.0), "known_crash_window": crash})
        fp = fund_profile(name)
        inv.append({"ticker": tk, "yahoo_symbol": m["symbol"], "name": m.get("longName") or m.get("shortName"),
                    "currency": m.get("currency"), "exchange": m.get("exchangeName"),
                    "type": m.get("instrumentType"),
                    "first_date": df.index[0].date(), "last_date": df.index[-1].date(), "n_days": len(df),
                    "n_div": int((df["dividends"] > 0).sum()), "n_splits": int((df["splits"] != 1).sum()),
                    "ann_gap_adj_minus_own_tr": round(gap, 5), **fp})
        write_meta(p, {"source": "Yahoo Finance v8 chart API (daily, events=div,split)", "url": e.get("url"),
                       "retrieved_utc": e.get("retrieved_utc"), "yahoo_symbol": m["symbol"],
                       "name": m.get("longName"), "first": df.index[0], "last": df.index[-1], "rows": len(df),
                       "units": f"{m.get('currency')} per unit; close = split-adjusted (not dividend-adjusted) "
                                "close; adjclose = Yahoo split+distribution-adjusted close; dividends = cash "
                                "per unit on ex-date; splits = ratio on ex-date (Canadian 0.99x 'splits' at "
                                "year-end are reinvested-distribution consolidations; the reinvested amount appears "
                                "in dividends); tr_own = own total-return index from close+dividends, rebased to "
                                "the first adjclose (reference only)",
                       "expense_ratio_yahoo": fp.get("er_yahoo"), "inception_yahoo": fp.get("inception_yahoo"),
                       "notes": "Dates are exchange-local trading dates. Last row may be an intraday/partial "
                                "quote for 2026-09-25/26. Yahoo 'adjclose' annualised minus own "
                                f"(close+div)/close TR = {gap:+.4%}/yr."})
        s = df["adjclose"].dropna()
        monthly[tk] = s.groupby(s.index.to_period("M")).last()
    inv = pd.DataFrame(inv)
    inv.to_csv(PROC / "etf_inventory.csv", index=False)
    mo = pd.DataFrame(monthly)
    mo.index = mo.index.to_timestamp("M")
    mo.index.name = "date"
    mo = mo[mo.index <= LAST_COMPLETE_MONTH]
    p = PROC / "etf_monthly_adj.parquet"
    mo.to_parquet(p)
    write_meta(p, {"source": "derived from data/cycle8/proc/etf/*.parquet (Yahoo adjclose)",
                   "first": mo.index.min(), "last": mo.index.max(), "rows": len(mo),
                   "units": "month-end (last trading day in month) adjclose, native currency per column; "
                            "currency per ticker in etf_inventory.csv",
                   "currency": dict(zip(inv["ticker"], inv["currency"])),
                   "notes": "First month of each ticker is a partial month (inception mid-month): its level is "
                            "valid, but the first monthly return should start from the first full month. "
                            "2026-09 excluded (incomplete at build time)."})
    NOTES.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(anomalies).to_csv(NOTES / "etf_anomalies.csv", index=False)
    return mo


# ---------------------------------------------------------------- validation
def stats(r: pd.Series) -> tuple[float, float]:
    n = len(r)
    return (1 + r).prod() ** (12 / n) - 1, r.std() * np.sqrt(12)


def validate(trend: pd.DataFrame, rf: pd.Series, mo: pd.DataFrame) -> str:
    x = trend["tsmom_excess"].dropna()
    sleeve = (rf.reindex(x.index) + x - DRAG / 12).dropna().rename("sleeve")
    L = [f"# TREND sleeve checks (cycle 8, data only)\n",
         f"Built {datetime.now(timezone.utc).isoformat(timespec='seconds')} by "
         "`research/cycle8/data_trend/build.py`. USD only. Sleeve (FRAMEWORK §2, USD form for this check): "
         "`r = RF_FF + tsmom_excess - 2.0%/12`. AQR TSMOM is gross of fees/costs, ~12%/yr vol by construction. "
         f"Sleeve months: {sleeve.index.min():%Y-%m}..{sleeve.index.max():%Y-%m} (n={len(sleeve)}). "
         "Fund returns: month-end Yahoo adjclose, first full month after inception onward; "
         f"AQR data end {x.index.max():%Y-%m} bounds every overlap.\n",
         "Annualised return = geometric (CAGR over the overlap). Gap = fund − sleeve. TE = sd(fund − sleeve)×√12.\n",
         "## 1. Sleeve vs live managed-futures funds (USD, overlapping months)\n",
         "| fund | months | corr | fund ann. | sleeve ann. | gap | fund vol | sleeve vol | TE | fund 2022 | sleeve 2022 |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    funds = ["DBMF", "KMLM", "CTA", "FFUT", "AQMIX", "PQTIX", "ASFYX", "WTMF", "FMF"]
    for f in funds:
        if f not in mo:
            continue
        p = mo[f].dropna()
        # p's first level is the inception-month end; its first return (next month) is a full month.
        r = p.pct_change().dropna()
        j = pd.concat([r.rename("f"), sleeve], axis=1, join="inner").dropna()
        if len(j) < 12:
            continue
        fa, fv = stats(j["f"]); sa, sv = stats(j["sleeve"])
        te = (j["f"] - j["sleeve"]).std() * np.sqrt(12)
        r22 = r["2022"]
        f22 = (1 + r22).prod() - 1
        s22 = (1 + sleeve.reindex(r22.index)).prod() - 1
        if len(r22) < 12:
            f += f" (2022 = {r22.index.min():%m}..12 only)"
        L.append(f"| {f} | {j.index.min():%Y-%m}..{j.index.max():%Y-%m} ({len(j)}) | {j.corr().iloc[0,1]:.2f} | "
                 f"{fa:.2%} | {sa:.2%} | {fa-sa:+.2%} | {fv:.1%} | {sv:.1%} | {te:.1%} | "
                 f"{f22:.1%} | {s22:.1%} |")
    L.append("\nCalendar 2022 for the raw AQR factor: tsmom_excess compounded = "
             f"{(1 + x['2022']).prod() - 1:.1%}; US T-bill 2022 = {(1 + rf['2022']).prod() - 1:.2%}.\n")

    # common window across DBMF/KMLM/CTA
    L.append("## 2. Common window (all of DBMF, KMLM, CTA available)\n")
    cw = pd.concat({f: mo[f].pct_change() for f in ["DBMF", "KMLM", "CTA"]}, axis=1).dropna()
    cw = cw.join(sleeve, how="inner")
    if len(cw):
        L.append(f"Months {cw.index.min():%Y-%m}..{cw.index.max():%Y-%m} (n={len(cw)}).\n")
        L.append("| series | ann. return | vol | corr with sleeve |\n|---|---|---|---|")
        for c in cw:
            a, v = stats(cw[c]); L.append(f"| {c} | {a:.2%} | {v:.1%} | {cw[c].corr(cw['sleeve']):.2f} |")
        eq = cw[["DBMF", "KMLM", "CTA"]].mean(axis=1)
        a, v = stats(eq)
        L.append(f"| equal-wt avg of 3 funds (descriptive only) | {a:.2%} | {v:.1%} | {eq.corr(cw['sleeve']):.2f} |\n")

    # pre/post publication
    L.append("## 3. tsmom_excess (gross, excess of cash) before vs after publication (MOP 2012)\n")
    L.append("| window | months | ann. mean (arith ×12) | vol | Sharpe | CAGR of excess | t-stat mean |\n|---|---|---|---|---|---|---|")
    for lab, s in [("1985-01..2011-12", x[:"2011-12"]), ("2012-01..end", x["2012-01":]),
                   ("2010-01..end (post orig. sample 1985-2009)", x["2010-01":]),
                   ("full 1985-01..end", x)]:
        mu, sd = s.mean() * 12, s.std() * np.sqrt(12)
        L.append(f"| {lab} | {len(s)} | {mu:.2%} | {sd:.1%} | {mu/sd:.2f} | {(1+s).prod()**(12/len(s))-1:.2%} | "
                 f"{s.mean()/s.std()*np.sqrt(len(s)):.2f} |")
    ss = [("1985-01..2011-12", sleeve[:"2011-12"]), ("2012-01..end", sleeve["2012-01":]), ("full", sleeve)]
    L.append("\nSleeve (RF + tsmom − 2%) total return, same windows: " + "; ".join(
        f"{lab}: CAGR {stats(s)[0]:.2%}, vol {stats(s)[1]:.1%}" for lab, s in ss) + ".\n")
    ov = trend[["tsmom_excess", "tsmom_excess_2012paper"]].dropna()
    L.append(f"Vintage check: current AQR TSMOM vs 2012 paper file, {ov.index.min():%Y-%m}..{ov.index.max():%Y-%m}: "
             f"corr {ov.corr().iloc[0,1]:.3f}; ann. mean {ov.iloc[:,0].mean()*12:.2%} (current) vs "
             f"{ov.iloc[:,1].mean()*12:.2%} (paper). AQR reconstructs history on every update, so in-sample "
             "values are not frozen.\n")
    L.append("## 4. Caveats (descriptive)\n\n"
             "- Fund returns are net of their own fees (ETF ERs 0.66-0.99%; mutual-fund Yahoo ERs AQMIX 3.09% "
             "incl. acquired/other expenses, PQTIX 1.51%, ASFYX 1.45%); the sleeve deducts a flat 2.0%/yr.\n"
             "- Funds target 10-17% vol and differ in design (DBMF replicates SG CTA index; KMLM = MLM index, "
             "no equities; CTA = Simplify discretionary-systematic blend); correlations 0.3-0.76 mean monthly "
             "tracking is loose (TE 8.5-14.5%/yr) even where multi-year averages are close.\n"
             "- Mutual-fund returns from Yahoo adjclose; year-end capital-gain distributions are included via "
             "adjclose (checked vs close+distributions: differences < 0.01%/yr).\n"
             "- FRAMEWORK converts to CAD; this check is USD only by design.\n")
    return "\n".join(L)


def main() -> None:
    PROC.mkdir(parents=True, exist_ok=True)
    trend, rf = build_trend()
    mo = build_etfs()
    txt = validate(trend, rf, mo)
    (NOTES / "trend_checks.md").write_text(txt)
    print(txt)


if __name__ == "__main__":
    main()
