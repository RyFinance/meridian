"""Cycle 8 equity / FX / CPI processing (research only; single series only, no portfolio returns).

Reads raw bytes from data/cycle8/raw/eq/ (written by acquire.py) and writes
  data/cycle8/proc/eq_monthly.parquet, eq_monthly_aux.parquet, eq_daily.parquet,
  fx_monthly.parquet, fx_daily.parquet, cpi_ca_monthly.parquet
plus data/cycle8/meta/<file>.json and data/cycle8/notes/eq_checks.md.

Usage:  python research/cycle8/data_eq/build.py
"""
from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import nnls

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "cycle8" / "raw" / "eq"
PROC = ROOT / "data" / "cycle8" / "proc"
META = ROOT / "data" / "cycle8" / "meta"
NOTES = ROOT / "data" / "cycle8" / "notes"
LOG = json.loads((RAW / "_acquire_log.json").read_text())

ME = pd.offsets.MonthEnd(0)


def src(name: str) -> dict:
    r = LOG.get(name, {})
    return {"name": name, "url": r.get("url"), "retrieved_utc": r.get("retrieved_utc"),
            "raw_file": r.get("file"), "sha256": r.get("sha256"), "status": r.get("status")}


# ----------------------------------------------------------------------------- readers
def kf_csv(zname: str, daily: bool = False) -> pd.DataFrame:
    z = zipfile.ZipFile(RAW / zname)
    txt = z.read(z.namelist()[0]).decode("latin1")
    rows, cols, started = [], None, False
    n = 8 if daily else 6
    for line in txt.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if parts[0] == "" and len(parts) > 1 and "Mkt-RF" in parts:
            if started:
                break
            cols = parts[1:]
            continue
        if cols and re.fullmatch(r"\d{%d}" % n, parts[0]):
            started = True
            rows.append([parts[0]] + [float(p) for p in parts[1:len(cols) + 1]])
        elif started:
            break
    df = pd.DataFrame(rows, columns=["d"] + cols)
    fmt = "%Y%m%d" if daily else "%Y%m"
    idx = pd.to_datetime(df.pop("d"), format=fmt)
    df.index = idx if daily else idx + ME
    df.index.name = "date"
    return df.replace(-99.99, np.nan)


def kf_dat_first_block(zname: str, member: str) -> pd.Series:
    """First block of a KF international .Dat = Value-Weight Dollar Returns, 'All 4 Data Items Not Reqd'; Mkt col."""
    z = zipfile.ZipFile(RAW / zname)
    lines = z.read(member).decode("latin1").splitlines()
    hdr = next(i for i, l in enumerate(lines) if "Dollar Returns" in l)
    assert "Not Reqd" in lines[hdr], lines[hdr]
    out, started = {}, False
    for l in lines[hdr + 1:]:
        s = l.split()
        if s and re.fullmatch(r"\d{6}", s[0]):
            started = True
            out[s[0]] = float(s[1])
        elif started:
            break
    ser = pd.Series(out)
    ser.index = pd.to_datetime(ser.index, format="%Y%m") + ME
    ser.index.name = "date"
    return ser.replace(-99.99, np.nan) / 100


def msci(code: str, var: str = "GRTR", freq: str = "m") -> pd.Series:
    x = json.loads((RAW / f"msci_{code}_{var}_{freq}.json").read_text())["indexes"]["INDEX_LEVELS"]
    s = pd.Series({pd.Timestamp(str(r["calc_date"])): r["level_eod"] for r in x}).sort_index()
    if freq == "m":
        s.index = s.index + ME
    s.index.name = "date"
    return s


def yahoo(name: str) -> pd.DataFrame:
    r = json.loads((RAW / f"yahoo_{name}.json").read_text())["chart"]["result"][0]
    off = r["meta"].get("gmtoffset", 0)
    ts = pd.to_datetime(np.array(r["timestamp"]), unit="s")
    # use exchange-local calendar date (timestamps are market-open UTC)
    tz = r["meta"].get("exchangeTimezoneName", "UTC")
    dates = ts.tz_localize("UTC").tz_convert(tz).tz_localize(None).normalize()
    q = r["indicators"]["quote"][0]
    df = pd.DataFrame({"close": q["close"]}, index=dates)
    if "adjclose" in r["indicators"]:
        df["adjclose"] = r["indicators"]["adjclose"][0]["adjclose"]
    df.index.name = "date"
    df = df[~df.index.duplicated(keep="last")].dropna(how="all")
    return df


def h10_usdcad() -> pd.Series:
    z = zipfile.ZipFile(RAW / "frb_H10.zip")
    t = z.read("H10_data.xml").decode("utf-8")
    i = t.find('SERIES_NAME="RXI_N.B.CA"')
    blk = t[i:t.find("</kf:Series>", i)]
    obs = re.findall(r'<frb:Obs([^>]*)/>', blk)
    out = {}
    for o in obs:
        v = re.search(r'OBS_VALUE="([^"]+)"', o).group(1)
        d = re.search(r'TIME_PERIOD="([^"]+)"', o).group(1)
        st = re.search(r'OBS_STATUS="([^"]+)"', o)
        if st and st.group(1) != "A":
            continue
        fv = float(v)
        if fv > 0:
            out[pd.Timestamp(d)] = fv
    s = pd.Series(out).sort_index()
    s.index.name = "date"
    return s


def boc(series: str) -> pd.Series:
    txt = (RAW / f"boc_{series}.csv").read_text(encoding="utf-8-sig")
    body = txt[txt.find('"OBSERVATIONS"'):].splitlines()[1:]
    df = pd.read_csv(io.StringIO("\n".join(body)))
    s = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    s.index = pd.to_datetime(df.iloc[:, 0])
    return s.dropna()


def fred(series: str) -> pd.Series | None:
    p = RAW / f"fred_{series}.csv"
    if not p.exists():
        return None
    df = pd.read_csv(p)
    s = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    s.index = pd.to_datetime(df.iloc[:, 0])
    return s.dropna()


def bls_cpi() -> pd.Series | None:
    out = {}
    for f in sorted(RAW.glob("bls_CUUR0000SA0_*.json")):
        d = json.loads(f.read_text())
        for r in d["Results"]["series"][0]["data"]:
            if r["period"].startswith("M") and r["period"] != "M13" and r["value"] not in ("-", ""):
                out[pd.Timestamp(int(r["year"]), int(r["period"][1:]), 1) + ME] = float(r["value"])
    if not out:
        return None
    s = pd.Series(out).sort_index()
    s.index.name = "date"
    return s


def statcan_cpi() -> pd.Series:
    z = zipfile.ZipFile(RAW / "statcan_18100004-eng.zip")
    with z.open("18100004.csv") as f:
        df = pd.read_csv(f, usecols=["REF_DATE", "GEO", "Products and product groups", "UOM", "VECTOR", "VALUE"],
                         dtype=str)
    df = df[(df.VECTOR == "v41690973")]
    assert (df.GEO == "Canada").all() and (df["Products and product groups"] == "All-items").all()
    s = pd.to_numeric(df.VALUE, errors="coerce")
    s.index = pd.to_datetime(df.REF_DATE, format="%Y-%m") + ME
    s.index.name = "date"
    return s.dropna().sort_index()


def shiller() -> pd.DataFrame:
    d = pd.read_excel(RAW / "ie_data.xls", sheet_name="Data", header=None, skiprows=8)
    d = d.iloc[:, :5]
    d.columns = ["date", "P", "D", "E", "CPI"]
    d = d[pd.to_numeric(d.date, errors="coerce").notna()].copy()
    # Shiller dates are YYYY.MM floats; .1 means October
    yr = d.date.astype(float).apply(lambda x: int(x))
    mo = d.date.astype(float).apply(lambda x: int(round((x - int(x)) * 100)))
    d.index = pd.to_datetime(dict(year=yr, month=mo, day=1)) + ME
    d.index.name = "date"
    return d[["P", "D", "E", "CPI"]].apply(pd.to_numeric, errors="coerce")


# ----------------------------------------------------------------------------- helpers
def monthly_last(s: pd.Series) -> pd.Series:
    m = s.groupby(s.index + ME).last()
    m.index.name = "date"
    return m


def span(s: pd.Series) -> dict:
    s = s.dropna()
    return {"first": str(s.index[0].date()), "last": str(s.index[-1].date()), "n": int(len(s))}


def write_meta(fname: str, df: pd.DataFrame, columns: dict, sources: list, notes: list, asof: str) -> None:
    now = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    meta = {"file": f"data/cycle8/proc/{fname}", "built_utc": now, "builder": "research/cycle8/data_eq/build.py",
            "logical_asof": asof, "first_date": str(df.index.min().date()), "last_date": str(df.index.max().date()),
            "row_count": int(len(df)), "index": "date", "columns": {}, "sources": sources, "notes": notes}
    for c, info in columns.items():
        meta["columns"][c] = {**info, **span(df[c])}
    (META / f"{fname}.json").write_text(json.dumps(meta, indent=1))


def rolling_nnls(y: pd.Series, X: pd.DataFrame, half: int = 12) -> pd.DataFrame:
    """Centred (2*half+1)-month NNLS weights of y on X (no intercept), rows with any NaN in X or y dropped."""
    ok = pd.concat([y, X], axis=1).dropna()
    yy, XX = ok.iloc[:, 0].values, ok.iloc[:, 1:].values
    out = {}
    for i, d in enumerate(ok.index):
        lo, hi = max(0, i - half), min(len(ok), i + half + 1)
        b, _ = nnls(XX[lo:hi], yy[lo:hi])
        out[d] = b
    return pd.DataFrame.from_dict(out, orient="index", columns=X.columns)


# ----------------------------------------------------------------------------- build
def main() -> None:
    for p in (PROC, META, NOTES):
        p.mkdir(parents=True, exist_ok=True)
    notes_md: list[str] = []

    # ---------- FX (needed for CA splice) ----------
    fxd = h10_usdcad().rename("USDCAD")
    fxm = monthly_last(fxd).rename("USDCAD")
    last_bd = (fxm.index[-1] - pd.offsets.BDay(0)) if fxm.index[-1].weekday() < 5 else fxm.index[-1] - pd.offsets.BDay(1)
    fx_partial = fxd.index[-1] < last_bd - pd.Timedelta(days=3)
    if fx_partial:  # drop incomplete final month (H.10 is released weekly with a lag)
        fxm = fxm.iloc[:-1]

    # ---------- US ----------
    ff = kf_csv("F-F_Research_Data_Factors_CSV.zip")
    us = ((ff["Mkt-RF"] + ff["RF"]) / 100).rename("US_usd")
    ffd = kf_csv("F-F_Research_Data_Factors_daily_CSV.zip", daily=True)
    us_d = ((ffd["Mkt-RF"] + ffd["RF"]) / 100).rename("US_usd")

    # ---------- KF international (country + index) ----------
    ca_kf = kf_dat_first_block("F-F_International_Countries.zip", "Canada.Dat").rename("CA_kf")
    zc = zipfile.ZipFile(RAW / "F-F_International_Countries.zip")
    ctry = {m[:-4]: kf_dat_first_block("F-F_International_Countries.zip", m) for m in zc.namelist() if m.endswith(".Dat")}
    ind = {k: kf_dat_first_block("F-F_International_Indices.zip", f"Ind_{k}.Dat")
           for k in ("all", "Eur_With_UK", "Scandanavia", "Asia_Pacific", "UK", "Eur_WOut_UK")}
    mm = ind["all"].rename("KF_MajorMkts_incl_CA")

    # DXNA: back Canada out of KF 'Major Markets' (EAFE+Canada cap weights).
    X = pd.DataFrame({"EU": ind["Eur_With_UK"], "SC": ind["Scandanavia"], "AP": ind["Asia_Pacific"], "CA": ca_kf})
    Xc = X.loc["1977-01-31":]  # Canada enters KF index 1977-01
    W = rolling_nnls(mm.loc[Xc.index], Xc, half=12)
    wsum = W.sum(axis=1)
    wC = (W["CA"] / wsum).rename("w_CA")
    dx = mm.copy()
    dx.loc[wC.index] = (mm.loc[wC.index] - wC * ca_kf.loc[wC.index]) / (1 - wC)
    dxna_kf = dx.rename("DXNA_kf")
    fit_resid = (mm.loc[W.index] - (Xc.loc[W.index] * W).sum(axis=1))

    # Equal-weighted developed ex-NA fallback (framework's 'else' rule) -- diagnostic only
    exna = [k for k in ctry if k not in ("Canada", "Malaysia")]
    dxna_ew = pd.DataFrame({k: ctry[k] for k in exna}).mean(axis=1, skipna=True).rename("DXNA_ew_kf")

    # MSCI validation / extension
    eafe_m = msci("990300").pct_change().dropna().rename("MSCI_EAFE_GR")
    eafe_n = msci("990300", "NETR").pct_change().dropna().rename("MSCI_EAFE_NR")
    em_m = msci("891800").pct_change().dropna().rename("MSCI_EM_GR")
    wld_m = msci("990100").pct_change().dropna().rename("MSCI_World_GR")
    usa_m = msci("984000").pct_change().dropna().rename("MSCI_USA_GR")

    # EM
    em5 = kf_csv("Emerging_5_Factors_CSV.zip")
    em = ((em5["Mkt-RF"] + em5["RF"]) / 100).rename("EM_usd")

    # Yahoo daily
    tsx = yahoo("GSPTSE")
    efa, eem, spy, xic = yahoo("EFA"), yahoo("EEM"), yahoo("SPY"), yahoo("XIC.TO")

    # CA extension beyond KF end: XIC.TO adjusted (CAD) -> USD at month-end H.10 USDCAD
    xic_m = monthly_last(xic["adjclose"].dropna())
    xic_usd = (xic_m / fxm.reindex(xic_m.index)).pct_change().rename("XIC_usd")
    ca = ca_kf.copy()
    ca_ext_idx = xic_usd.index[(xic_usd.index > ca_kf.dropna().index[-1]) & (xic_usd.index <= us.index[-1])]
    ca = pd.concat([ca, xic_usd.loc[ca_ext_idx]]).rename("CA_usd")
    # DXNA extension beyond KF end: MSCI EAFE GR (USD)
    dx_ext_idx = eafe_m.index[(eafe_m.index > dxna_kf.dropna().index[-1]) & (eafe_m.index <= us.index[-1])]
    dxna = pd.concat([dxna_kf, eafe_m.loc[dx_ext_idx]]).rename("DXNA_usd")

    # Shiller D/P
    sh = shiller()
    dp = (sh["D"] / sh["P"]).rename("US_dp")

    idx = pd.date_range("1926-07-31", us.index[-1], freq="ME", name="date")
    eqm = pd.DataFrame({"US_usd": us, "CA_usd": ca, "DXNA_usd": dxna, "EM_usd": em, "US_dp": dp}).reindex(idx)
    eqm.to_parquet(PROC / "eq_monthly.parquet")
    asof = str(idx[-1].date())
    write_meta("eq_monthly.parquet", eqm, {
        "US_usd": {"units": "decimal simple monthly total return, USD", "source": "Ken French F-F_Research_Data_Factors (Mkt-RF + RF)/100 (CRSP VW all NYSE/AMEX/NASDAQ)"},
        "CA_usd": {"units": "decimal simple monthly total return, USD",
                   "source": "Ken French International Countries Canada.Dat, block 1 'Value-Weight Dollar Returns, All 4 Data Items Not Reqd', Mkt column",
                   "splice": f"KF ends {ca_kf.dropna().index[-1].date()}; {len(ca_ext_idx)} later months ({', '.join(str(d.date()) for d in ca_ext_idx[:1])}..{str(ca_ext_idx[-1].date()) if len(ca_ext_idx) else ''}) = XIC.TO Yahoo adjclose (CAD, net of 0.06% MER) converted at month-end H.10 USD/CAD"},
        "DXNA_usd": {"units": "decimal simple monthly total return, USD",
                     "source": "Ken French International Indices Ind_all.Dat ('Major Markets', EAFE+Canada cap weights) with Canada backed out: (MM - wCA*CA)/(1-wCA); wCA from centred 25-month NNLS of MM on [Eur w/UK, Scandinavia, Asia Pacific, Canada] KF index/country returns, normalised to sum 1. 1975-01..1976-12 = MM unchanged (Canada enters 1977-01)",
                     "splice": f"KF ends {dxna_kf.dropna().index[-1].date()}; {len(dx_ext_idx)} later months = MSCI EAFE gross (990300 GRTR, USD) from app2.msci.com"},
        "EM_usd": {"units": "decimal simple monthly total return, USD", "source": "Ken French Emerging_5_Factors (Mkt-RF + RF)/100"},
        "US_dp": {"units": "annual dividend yield, decimal (D/P)", "source": "Shiller ie_data.xls: D (12m trailing dividends, annual rate) / P (monthly average S&P Composite price); YYYY.MM mapped to calendar month-end"},
    }, [src(n) for n in ("kf_ff3_monthly", "kf_intl_countries", "kf_intl_indices", "kf_emerging_5f", "shiller_ie_data",
                         "msci_990300_GRTR_m", "yahoo_XIC.TO", "frb_h10_zip", "kf_intl_index_detail")],
        ["Index = calendar month-end. NaN before availability (no backfill): CA 1977-01+, DXNA 1975-01+, EM 1989-07+.",
         "KF international files (Countries/Indices) are updated annually; this edition ends 2025-12 (raw data MSCI 1975-2006, Bloomberg 2007+).",
         "KF 'Major Markets' excludes Malaysia; the Asia Pacific regional index includes Malaysia 1994-2001 (small effect on the NNLS weight fit only). Israel (2011+) is in MM but not in any region (absorbed by NNLS residual).",
         "Shiller file ends 2024-09 with D through 2024-06 -> US_dp NaN after 2024-06 (engine may forward-fill; not done here).",
         "DXNA_usd includes the KF-derived series through 2025-12 and MSCI EAFE GR afterwards; see eq_monthly_aux.parquet for unspliced components."],
        asof)

    aux = pd.DataFrame({"CA_kf": ca_kf, "DXNA_kf": dxna_kf, "KF_MajorMkts_incl_CA": mm, "w_CA_est": wC,
                        "NNLS_fit_resid": fit_resid, "DXNA_ew_kf": dxna_ew, "MSCI_EAFE_GR": eafe_m, "MSCI_EAFE_NR": eafe_n,
                        "MSCI_EM_GR": em_m, "MSCI_World_GR": wld_m, "MSCI_USA_GR": usa_m, "XIC_usd": xic_usd,
                        "w_EU": W["EU"] / wsum, "w_SC": W["SC"] / wsum, "w_AP": W["AP"] / wsum})
    aux = aux.loc["1975-01-31":]
    aux.index.name = "date"
    aux.to_parquet(PROC / "eq_monthly_aux.parquet")
    write_meta("eq_monthly_aux.parquet", aux, {c: {"units": "decimal (returns monthly simple USD; w_* weights)"} for c in aux.columns},
               [src(n) for n in ("kf_intl_countries", "kf_intl_indices", "msci_990300_GRTR_m", "msci_990300_NETR_m",
                                 "msci_891800_GRTR_m", "msci_990100_GRTR_m", "msci_984000_GRTR_m", "yahoo_XIC.TO")],
               ["Diagnostics / unspliced components for eq_monthly.parquet. DXNA_ew_kf = equal-weighted mean of available KF developed ex-NA country Mkt returns (framework fallback rule; not used).",
                "MSCI series from app2.msci.com getLevelDataForGraph start 2000-12 (first return 2001-01) regardless of requested start."],
               str(aux.index[-1].date()))

    # ---------- daily ----------
    tsx_r = tsx["close"].dropna().pct_change().rename("CA_cad")
    efa_r = efa["adjclose"].dropna().pct_change().rename("EFA")
    eem_r = eem["adjclose"].dropna().pct_change().rename("EEM")
    eafe_d = msci("990300", freq="d").pct_change().dropna()
    emd = msci("891800", freq="d").pct_change().dropna()

    # pre-EFA DXNA daily: KF Europe / Japan / APxJ daily market returns, weights from monthly NNLS vs DXNA_kf
    reg_m, reg_d = {}, {}
    for k, zm, zd in (("EU", "Europe_3_Factors_CSV.zip", "Europe_3_Factors_Daily_CSV.zip"),
                      ("JP", "Japan_3_Factors_CSV.zip", "Japan_3_Factors_Daily_CSV.zip"),
                      ("AX", "Asia_Pacific_ex_Japan_3_Factors_CSV.zip", "Asia_Pacific_ex_Japan_3_Factors_Daily_CSV.zip")):
        a, b = kf_csv(zm), kf_csv(zd, daily=True)
        reg_m[k] = (a["Mkt-RF"] + a["RF"]) / 100
        reg_d[k] = (b["Mkt-RF"] + b["RF"]) / 100
    RM, RD = pd.DataFrame(reg_m), pd.DataFrame(reg_d)
    Wr = rolling_nnls(dxna_kf, RM, half=12)
    Wr = Wr.div(Wr.sum(axis=1), axis=0)
    wd = Wr.reindex(RD.index + ME).set_axis(RD.index)
    kfblend = (RD * wd).sum(axis=1, min_count=3).dropna()
    efa_start = efa_r.dropna().index[0]
    dx_d = pd.concat([kfblend.loc[:efa_start - pd.Timedelta(days=1)], efa_r.dropna()]).rename("DXNA_usd")
    eem_start = eem_r.dropna().index[0]
    em_d = pd.concat([emd.loc[:eem_start - pd.Timedelta(days=1)], eem_r.dropna()]).rename("EM_usd")

    eqd = pd.concat([us_d, tsx_r, dx_d, em_d], axis=1).sort_index()
    eqd.index.name = "date"
    eqd = eqd.loc[eqd.notna().any(axis=1)]
    # sanity flags on daily Yahoo series
    big = {c: {str(k.date()): v for k, v in eqd[c][eqd[c].abs() > 0.15].round(4).items()} for c in eqd.columns}
    eqd.to_parquet(PROC / "eq_daily.parquet")
    write_meta("eq_daily.parquet", eqd, {
        "US_usd": {"units": "decimal simple daily total return USD", "source": "Ken French F-F_Research_Data_Factors_daily (Mkt-RF + RF)/100"},
        "CA_cad": {"units": "decimal simple daily PRICE return CAD (no dividends)", "source": "Yahoo ^GSPTSE close"},
        "DXNA_usd": {"units": "decimal simple daily total return USD",
                     "source": f"{kfblend.index[0].date()}..{(efa_start - pd.Timedelta(days=1)).date()}: blend of KF Europe/Japan/Asia-Pacific-ex-Japan daily Mkt (Mkt-RF+RF) with monthly weights = centred 25m NNLS of DXNA_kf on the three KF regional monthly Mkt returns (normalised); {efa_start.date()}+: Yahoo EFA adjclose (net of ETF fee, US-hours pricing)"},
        "EM_usd": {"units": "decimal simple daily total return USD",
                   "source": f"{emd.index[0].date()}..{(eem_start - pd.Timedelta(days=1)).date()}: MSCI EM gross daily (891800 GRTR, app2.msci.com); {eem_start.date()}+: Yahoo EEM adjclose"},
    }, [src(n) for n in ("kf_ff3_daily", "yahoo_GSPTSE", "yahoo_EFA", "yahoo_EEM", "msci_891800_GRTR_d",
                         "kf_europe_3f_daily", "kf_japan_3f_daily", "kf_apxj_3f_daily", "kf_europe_3f", "kf_japan_3f", "kf_apxj_3f")],
        [f"Rows = union of trading dates across series (NaN where a series has no observation). Daily moves >15%: {json.dumps(big, default=str)}",
         "Used only as intramonth path shapes (engine rescales to monthly returns).",
         "MSCI daily levels include some market holidays (e.g. Jan 1) with small/zero moves; EFA/EEM are US-listed and priced at US close (asynchronous to local markets), so daily correlation with local-close KF regional data is ~0.7 while monthly correlation is ~0.99."],
        str(eqd.index[-1].date()))

    # ---------- FX ----------
    fx_daily = pd.DataFrame({"USDCAD": fxd})
    boc_d = boc("FXUSDCAD")
    fx_daily.to_parquet(PROC / "fx_daily.parquet")
    fx_srcs = [src("frb_h10_zip"), src("boc_FXUSDCAD"), src("boc_IEXE0101"), src("fred_DEXCAUS")]
    diff = (fxd - boc_d).dropna()
    fx_note = [f"H.10 RXI_N.B.CA = noon buying rate in New York, CAD per USD = the series FRED republishes as DEXCAUS. Non-'A' status / non-positive obs dropped.",
               f"Validation vs Bank of Canada FXUSDCAD (daily average rate, 2017+): n={len(diff)}, mean diff={diff.mean():.5f}, max abs diff={diff.abs().max():.4f}.",
               "No free source found for pre-1971 daily/month-end USD/CAD (BoC Valet legacy noon rates start 2007-05; FRED EXCAUS/DEXCAUS start 1971-01)."]
    fdex = fred("DEXCAUS")
    if fdex is not None:
        dd = (fxd - fdex).dropna()
        fx_note.append(f"Check vs FRED DEXCAUS: n={len(dd)}, max abs diff={dd.abs().max():.6f}")
    write_meta("fx_daily.parquet", fx_daily, {"USDCAD": {"units": "CAD per 1 USD", "source": "Federal Reserve H.10 RXI_N.B.CA daily"}},
               fx_srcs, fx_note, str(fx_daily.index[-1].date()))
    fx_month = pd.DataFrame({"USDCAD": fxm})
    fx_month.to_parquet(PROC / "fx_monthly.parquet")
    write_meta("fx_monthly.parquet", fx_month, {"USDCAD": {"units": "CAD per 1 USD, last daily obs of each calendar month (month-end), NOT monthly average", "source": "Federal Reserve H.10 RXI_N.B.CA daily (=FRED DEXCAUS)"}},
               fx_srcs, fx_note + [f"Final month dropped if incomplete (H.10 last obs {fxd.index[-1].date()}; dropped={bool(fx_partial)})."], str(fx_month.index[-1].date()))

    # ---------- CPI ----------
    cpi_ca = statcan_cpi().rename("CPI_CA")
    us_cpi = fred("CPIAUCNS")
    if us_cpi is not None:
        us_cpi.index = us_cpi.index + ME
        us_srcs, us_note = [src("fred_CPIAUCNS")], "US CPI = FRED CPIAUCNS (CPI-U all items NSA, 1982-84=100)."
    else:
        us_cpi = bls_cpi()
        us_srcs = [src(k) for k in sorted(LOG) if k.startswith("bls_CUUR0000SA0")]
        us_note = ("US CPI = BLS CUUR0000SA0 (CPI-U, U.S. city average, all items, NSA, 1982-84=100) via BLS public API v1 "
                   "(same series FRED republishes as CPIAUCNS; FRED fredgraph.csv timed out / HTTP2 errors at retrieval time).")
    miss = [str(d.date()) for d in pd.date_range(us_cpi.index[0], us_cpi.index[-1], freq="ME") if d not in us_cpi.index]
    us_note += f" Months missing in source (left NaN, not interpolated): {miss or 'none'} (BLS did not publish Oct-2025 CPI during the federal shutdown)."
    chk = pd.concat([us_cpi, sh["CPI"]], axis=1).dropna()
    chk = chk.loc[:"2024-06-30"]
    us_note += f" Check vs Shiller CPI column 1914..2024-06: max abs rel diff {((chk.iloc[:, 0] / chk.iloc[:, 1]) - 1).abs().max():.4%}."
    cpi = pd.DataFrame({"CPI_CA": cpi_ca, "CPI_US": us_cpi.rename("CPI_US")}).loc["1914-01-31":]
    cpi.index.name = "date"
    cpi.to_parquet(PROC / "cpi_ca_monthly.parquet")
    cpi_notes = [us_note, "CPI_CA = StatCan table 18-10-0004-01, vector v41690973, Canada, All-items, 2002=100, NSA, monthly (1914+). Reference month mapped to calendar month-end (index is NOT a release date)."]
    fca = fred("CPALCY01CAM661N")
    if fca is not None:
        fca.index = fca.index + ME
        r = pd.concat([cpi_ca.pct_change(12), fca.pct_change(12)], axis=1).dropna()
        cpi_notes.append(f"Check vs FRED CPALCY01CAM661N yoy: corr={r.corr().iloc[0, 1]:.4f}, n={len(r)}")
    write_meta("cpi_ca_monthly.parquet", cpi, {"CPI_CA": {"units": "index 2002=100"}, "CPI_US": {"units": "index 1982-84=100"}},
               [src("statcan_18100004")] + us_srcs, cpi_notes, str(cpi.index[-1].date()))

    # ---------- checks ----------
    L = ["# Cycle 8 equity/FX/CPI sanity checks", "",
         f"Generated by `research/cycle8/data_eq/build.py` at {pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M UTC}. Single-series checks only; no portfolio returns.", ""]

    def cmp(a: pd.Series, b: pd.Series, la: str, lb: str) -> str:
        j = pd.concat([a, b], axis=1).dropna()
        if len(j) < 12:
            return f"| {la} vs {lb} | n<12 | | | | |"
        ca_, cb_ = (1 + j.iloc[:, 0]).prod() ** (12 / len(j)) - 1, (1 + j.iloc[:, 1]).prod() ** (12 / len(j)) - 1
        te = (j.iloc[:, 0] - j.iloc[:, 1]).std() * np.sqrt(12)
        return (f"| {la} vs {lb} | {j.index[0]:%Y-%m}..{j.index[-1]:%Y-%m} | {len(j)} | {j.corr().iloc[0, 1]:.4f} | "
                f"{(ca_ - cb_) * 100:+.2f} | {te * 100:.2f} |")

    spy_m = monthly_last(spy["adjclose"].dropna()).pct_change()
    efa_m = monthly_last(efa["adjclose"].dropna()).pct_change()
    eem_m = monthly_last(eem["adjclose"].dropna()).pct_change()
    L += ["## Monthly validation (USD)", "",
          "| pair | overlap | n | corr | ann. return diff (a-b, %/yr, geometric) | tracking error (%/yr) |", "|---|---|---|---|---|---|"]
    kf_dxus = kf_csv("Developed_ex_US_3_Factors_CSV.zip")
    kf_dxus_r = (kf_dxus["Mkt-RF"] + kf_dxus["RF"]) / 100
    for a, b, la, lb in [
        (us, usa_m, "US_usd (KF)", "MSCI USA GR"), (us, spy_m, "US_usd (KF)", "SPY adj"),
        (dxna_kf, eafe_m, "DXNA_kf", "MSCI EAFE GR"), (dxna_kf, eafe_n, "DXNA_kf", "MSCI EAFE NR"),
        (dxna_kf, efa_m, "DXNA_kf", "EFA adj"), (mm, eafe_m, "KF Major Mkts incl CA (raw)", "MSCI EAFE GR"),
        (dxna_ew, eafe_m, "DXNA_ew_kf (EW fallback)", "MSCI EAFE GR"), (dxna_kf, kf_dxus_r, "DXNA_kf", "KF Developed ex US (incl CA)"),
        (em, em_m, "EM_usd (KF)", "MSCI EM GR"), (em, eem_m, "EM_usd (KF)", "EEM adj"),
        (ca_kf, xic_usd, "CA_kf", "XIC.TO adj in USD"),
        (ca_kf, (monthly_last(tsx["close"].dropna()) / fxm).pct_change(), "CA_kf", "^GSPTSE price in USD"),
    ]:
        L.append(cmp(a, b, la, lb))
    L += ["", f"Estimated Canada weight inside KF Major Markets (w_CA): mean {wC.mean():.3f}, min {wC.min():.3f}, max {wC.max():.3f}; "
              f"NNLS fit residual sd {fit_resid.std() * 100:.3f}%/month (sum of raw weights mean {wsum.mean():.3f}).",
          "",
          "Daily DXNA pre-EFA blend vs EFA on overlap (daily corr, from KF blend weights applied through the end of KF daily data): "
          + (f"{pd.concat([kfblend, efa_r], axis=1).dropna().corr().iloc[0, 1]:.3f}" if len(pd.concat([kfblend, efa_r], axis=1).dropna()) else "n/a"),
          "",
          "## Crisis months (monthly simple returns, %)", "", "| month | US_usd | CA_usd | DXNA_usd | EM_usd | MSCI EAFE GR | MSCI EM GR |", "|---|---|---|---|---|---|---|"]
    for m in ("1987-10-31", "1998-08-31", "2008-09-30", "2008-10-31", "2020-02-29", "2020-03-31", "2022-09-30"):
        d = pd.Timestamp(m)
        f = lambda s: "" if d not in s.index or pd.isna(s.get(d)) else f"{s[d] * 100:.2f}"
        L.append(f"| {m[:7]} | {f(eqm.US_usd)} | {f(eqm.CA_usd)} | {f(eqm.DXNA_usd)} | {f(eqm.EM_usd)} | {f(eafe_m)} | {f(em_m)} |")
    L += ["", "Worst 5 months per series:", ""]
    for c in ("US_usd", "CA_usd", "DXNA_usd", "EM_usd"):
        w = eqm[c].dropna().nsmallest(5)
        L.append(f"- {c}: " + ", ".join(f"{i:%Y-%m} {v * 100:.1f}%" for i, v in w.items()))
    L += ["", "## Gaps / coverage", ""]
    for c in eqm.columns:
        s = eqm[c]
        fv, lv = s.first_valid_index(), s.last_valid_index()
        inner = s.loc[fv:lv].isna().sum()
        L.append(f"- eq_monthly.{c}: {fv:%Y-%m}..{lv:%Y-%m}, internal NaN months = {inner}")
    for c in eqd.columns:
        s = eqd[c].dropna()
        gaps = s.index.to_series().diff().dt.days
        L.append(f"- eq_daily.{c}: {s.index[0].date()}..{s.index[-1].date()}, n={len(s)}, max calendar gap {int(gaps.max())} days (at {gaps.idxmax().date()}); |r|>15% days: {len(big[c])}")
    g = fxd.index.to_series().diff().dt.days
    L.append(f"- fx_daily.USDCAD: {fxd.index[0].date()}..{fxd.index[-1].date()}, n={len(fxd)}, max gap {int(g.max())} days (at {g.idxmax().date()})")
    L.append(f"- fx_monthly.USDCAD: {fxm.index[0]:%Y-%m}..{fxm.index[-1]:%Y-%m}, n={len(fxm)}; {fx_note[1]}")
    for c in cpi.columns:
        s = cpi[c].dropna()
        L.append(f"- cpi.{c}: {s.index[0]:%Y-%m}..{s.index[-1]:%Y-%m}, n={len(s)}, internal NaN = {cpi[c].loc[s.index[0]:s.index[-1]].isna().sum()}")
    L += ["", "## Notes", "",
          "- KF international (Countries/Indices) edition ends 2025-12; CA_usd and DXNA_usd are spliced for 2026-01..last month (XIC.TO in USD; MSCI EAFE GR). Unspliced columns in eq_monthly_aux.parquet.",
          "- Canada in KF begins 1977-01 (not 1975): CA_usd is NaN 1926-07..1976-12.",
          "- US_dp ends where Shiller's dividend column ends (2024-06).",
          ]
    (NOTES / "eq_checks.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
