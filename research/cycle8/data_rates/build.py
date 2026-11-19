"""Cycle 8 rates / bond / gold processing (research only; single series only — no sleeve mixes).

Reads raw bytes from data/cycle8/raw/rates/ (see acquire.py) and writes
  data/cycle8/proc/rates_monthly.parquet   month-end rate LEVELS (annual decimals) + US T-bill monthly return
  data/cycle8/proc/bond_monthly.parquet    CA10_ret, US10_ret par-bond total returns (local currency)
  data/cycle8/proc/bond_daily.parquet      US10_ret, US20_ret, CA10_ret daily par-bond returns (+ yields used)
  data/cycle8/proc/gold_monthly.parquet    gold USD levels (World Bank monthly average; month-end GC=F; GLD)
  data/cycle8/proc/gold_daily.parquet      GC=F close, GLD adjclose
and data/cycle8/meta/<file>.json for each. Validation lives in validate.py.

Usage: python research/cycle8/data_rates/build.py
"""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bondmath as bm  # noqa: E402

ROOT = HERE.parents[2]
RAW = ROOT / "data" / "cycle8" / "raw" / "rates"
PROC = ROOT / "data" / "cycle8" / "proc"
META = ROOT / "data" / "cycle8" / "meta"
ACQ = json.loads((RAW / "_acquire_log.json").read_text())

ME = pd.offsets.MonthEnd(0)
LAST_FULL_MONTH = pd.Timestamp.today().normalize() + pd.offsets.MonthEnd(-1)


# ----------------------------------------------------------------------------- readers
def src(name: str) -> dict:
    r = ACQ[name]
    return {"name": name, "url": r.get("url"), "retrieved_utc": r.get("retrieved_utc"),
            "raw_file": r.get("file"), "sha256": r.get("sha256")}


def fred(sid: str) -> pd.Series:
    d = pd.read_csv(RAW / f"fred_{sid}.csv", index_col=0, parse_dates=True)
    s = pd.to_numeric(d.iloc[:, 0], errors="coerce").dropna()
    s.index.name = "date"
    return s.rename(sid)


def valet(sid: str) -> pd.Series:
    j = json.loads((RAW / f"boc_{sid}.json").read_text())
    s = pd.Series({pd.Timestamp(o["d"]): float(o[sid]["v"]) for o in j["observations"]
                   if sid in o and o[sid].get("v") not in (None, "")}).sort_index()
    s.index.name = "date"
    return s.rename(sid)


_STATCAN = None


def statcan(vec: str) -> pd.Series:
    """StatCan 10-10-0122-01 monthly vector (last Wednesday unless stated), month-end index."""
    global _STATCAN
    if _STATCAN is None:
        z = zipfile.ZipFile(RAW / "statcan_10100122-eng.zip")
        d = pd.read_csv(z.open("10100122.csv"), encoding="utf-8-sig", low_memory=False)
        d["VALUE"] = pd.to_numeric(d["VALUE"], errors="coerce")
        d.loc[d["VALUE"] <= -99, "VALUE"] = np.nan  # -99.999 sentinel = not available
        w = d.pivot_table(index="REF_DATE", columns="VECTOR", values="VALUE", dropna=False)
        w.index = pd.to_datetime(w.index) + ME
        w.index.name = "date"
        _STATCAN = w
    return _STATCAN[vec].dropna().rename(vec)


def month_end_last(s: pd.Series) -> pd.Series:
    """Last available daily observation in each calendar month, indexed at the month-end date."""
    out = s.dropna().resample("ME").last().dropna()
    out = out.loc[:LAST_FULL_MONTH]  # the running month is not a month-end yet
    out.index.name = "date"
    return out


def month_start_to_end(s: pd.Series) -> pd.Series:
    s = s.copy()
    s.index = s.index + ME
    s.index.name = "date"
    return s


def yahoo(name: str) -> pd.DataFrame:
    j = json.loads((RAW / f"yahoo_{name}.json").read_text())["chart"]["result"][0]
    tz = j["meta"].get("exchangeTimezoneName", "America/New_York")
    idx = pd.to_datetime(j["timestamp"], unit="s", utc=True).tz_convert(tz).tz_localize(None).normalize()
    q = j["indicators"]["quote"][0]
    adj = j["indicators"].get("adjclose", [{}])[0].get("adjclose", q["close"])
    df = pd.DataFrame({"close": q["close"], "adjclose": adj}, index=idx).astype(float)
    df = df[~df.index.duplicated(keep="last")].dropna(subset=["close"])
    df.index.name = "date"
    return df


def shiller_long_rate() -> pd.Series:
    d = pd.read_excel(RAW / "ie_data.xls", sheet_name="Data", header=None, skiprows=8)
    d = d[[0, 6]].dropna()
    d = d[pd.to_numeric(d[0], errors="coerce").notna()]
    yrs = d[0].astype(float)
    year = np.floor(yrs + 1e-9).astype(int)
    month = np.rint((yrs - year) * 100).astype(int)
    idx = pd.to_datetime(dict(year=year, month=month, day=1)) + ME
    s = pd.Series(pd.to_numeric(d[6], errors="coerce").to_numpy(), index=idx).dropna()
    s.index.name = "date"
    return s.rename("shiller_GS10")


def splice(pieces: list[tuple[pd.Series, str, str | None, str | None]]):
    """pieces = [(series, label, start, end)] in priority order -> (series, list of segments)."""
    out = None
    segs = []
    for s, lab, a, b in pieces:
        s = s.loc[a:b] if (a or b) else s
        new = s[~s.index.isin(out.index)].dropna() if out is not None else s.dropna()
        if len(new):
            out = new.astype(float) if out is None else pd.concat([out, new.astype(float)])
            segs.append({"source": lab, "first": str(new.index.min().date()),
                         "last": str(new.index.max().date()), "n": int(len(new))})
    out = out.sort_index()
    out.index.name = "date"
    return out, segs


# ----------------------------------------------------------------------------- meta
def sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(df: pd.DataFrame, fname: str, meta: dict) -> None:
    PROC.mkdir(parents=True, exist_ok=True)
    META.mkdir(parents=True, exist_ok=True)
    p = PROC / fname
    df.to_parquet(p)
    cols = {}
    for c in df.columns:
        s = df[c].dropna()
        cols[c] = {"first": str(s.index.min().date()) if len(s) else None,
                   "last": str(s.index.max().date()) if len(s) else None, "n": int(len(s)),
                   **meta.get("columns", {}).get(c, {})}
    m = {k: v for k, v in meta.items() if k != "columns"}
    m.update(file=str(p.relative_to(ROOT)), sha256=sha_file(p), rows=int(len(df)),
             first_date=str(df.index.min().date()), last_date=str(df.index.max().date()),
             built_utc=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             builder="research/cycle8/data_rates/build.py", columns=cols)
    (META / f"{fname}.json").write_text(json.dumps(m, indent=1, default=str))
    print(f"wrote {p.relative_to(ROOT)} {df.shape}")


# ----------------------------------------------------------------------------- rates_monthly
def build_rates():
    info = {}
    # Canada 3m T-bill
    tb_daily = month_end_last(valet("TB.CDN.90D.MID"))
    tbill_cad, seg = splice([
        (tb_daily, "BoC Valet TB.CDN.90D.MID daily, last obs of month (month-end)", "2001-01-01", None),
        (statcan("v122531"), "StatCan 10-10-0122 v122531 T-bills 3m, last Wednesday", None, "2000-12-31"),
        (statcan("v122541"), "StatCan v122541 T-bill auction avg yield 3m (fills 1934-1961 and "
                             "v122531 gaps 1970-02, 1970-11, 1971-02, 1973-04)", None, "2000-12-31"),
    ])
    info["tbill_cad"] = {"segments": seg, "timing": "point-in-time: month-end (2001+) / last Wednesday (before)",
                         "units": "annual decimal, as published (BoC mid yield)",
                         "note": "1934-05..1935-05 has 6 missing months (StatCan -99.999); left NaN"}

    # policy rate
    tgt = month_start_to_end(valet("STATIC_ATABLE_V39079"))
    br = month_start_to_end(valet("V122530"))
    policy_cad, seg = splice([
        (tgt, "BoC Valet STATIC_ATABLE_V39079 target for the overnight rate, end of month", None, None),
        (br, "BoC Valet V122530 (= StatCan v122530) Bank Rate, last Wednesday", None, "1995-12-31"),
    ])
    d39079 = month_end_last(valet("V39079"))
    chk = (tgt - d39079).dropna().abs().max()
    gap = (br - tgt)["1996":"2000"].mean()
    info["policy_cad"] = {"segments": seg, "timing": "point-in-time (end of month / last Wednesday)",
                          "units": "annual decimal",
                          "splice": "Overnight target from 1996-01 (first month BoC publishes its end-of-month "
                                    "series); Bank Rate before. FRAMEWORK §4.1: Bank Rate before the target existed. "
                                    f"Bank Rate sits above the target (mean gap 1996-2000 = {gap:.3f} pp; 0.25 pp by "
                                    "construction since 1996-02: Bank Rate = top of the 50bp operating band; 1980-1996 "
                                    "Bank Rate = 3m T-bill auction + 0.25). Not adjusted.",
                          "check": f"STATIC_ATABLE_V39079 vs daily V39079 month-end (2009+): max |diff| = {chk:.4f} pp"}

    # Canada 10Y
    y10ca_daily = month_end_last(valet("BD.CDN.10YR.DQ.YLD"))
    y10_ca, seg = splice([
        (y10ca_daily, "BoC Valet BD.CDN.10YR.DQ.YLD 10Y benchmark daily, last obs of month", "2001-01-01", None),
        (statcan("v122543"), "StatCan v122543 GoC benchmark 10Y, last Wednesday", None, "2000-12-31"),
        (statcan("v122486"), "StatCan v122486 GoC marketable bonds avg yield 5-10y, last Wednesday", None, "1982-05-31"),
        (statcan("v122487"), "StatCan v122487 GoC marketable bonds avg yield over 10y, last Wednesday", None, "1950-12-31"),
    ])
    b = statcan("v122543")
    diag = {}
    for lab, s in (("v122486_5to10y", statcan("v122486")), ("v122487_over10y", statcan("v122487")),
                   ("FRED_IRLTLT01CAM156N", month_start_to_end(fred("IRLTLT01CAM156N")))):
        dd = (s - b)["1982-06":"2000-12"].dropna()
        ch = s.diff()["1982-07":"2000-12"].corr(b.diff()["1982-07":"2000-12"])
        diag[lab] = {"mean_level_diff_pp_vs_10Y_benchmark_1982_2000": round(float(dd.mean()), 3),
                     "mean_abs_diff_pp": round(float(dd.abs().mean()), 3),
                     "corr_of_monthly_changes": round(float(ch), 3)}
    info["y10_ca"] = {"segments": seg, "units": "annual decimal",
                      "timing": "point-in-time (month-end 2001+, last Wednesday before)",
                      "pre_1982_choice": "v122486 (5-10y average, last Wednesday) chosen over FRED IRLTLT01CAM156N: "
                                         "OECD series matches the 10Y level but is a monthly-average-like series "
                                         "(corr of monthly changes vs benchmark 0.76 vs 0.98), which would smooth "
                                         "returns. Level bias ~-7bp vs the 10Y benchmark (shorter bucket), not adjusted. 1936-1950 uses the over-10y bucket.",
                      "overlap_diagnostics_1982_2000": diag}

    # US 10Y
    y10_us, seg = splice([
        (month_end_last(fred("DGS10")), "FRED DGS10 daily, last obs of month (month-end)", "1962-01-01", None),
        (month_start_to_end(fred("GS10")), "FRED GS10 monthly AVERAGE of daily", "1953-04-01", "1961-12-31"),
        (shiller_long_rate(), "Shiller ie_data.xls 'Rate GS10' (pre-1953: annual Homer/Sylla-type long "
                              "government rate linearly interpolated to months)", None, "1953-03-31"),
    ])
    info["y10_us"] = {"segments": seg, "units": "annual decimal",
                      "timing": "month-end 1962-01+; monthly average 1953-04..1961-12; before 1953-04 annual values "
                                "linearly interpolated (returns strongly smoothed; vol understated)"}

    # US T-bill level
    tbill_usd, seg = splice([
        (month_end_last(fred("DTB3")), "FRED DTB3 daily secondary market 3m, last obs of month", "1954-01-01", None),
        (month_start_to_end(fred("TB3MS")), "FRED TB3MS monthly average", None, "1953-12-31"),
    ])
    info["tbill_usd"] = {"segments": seg, "units": "annual decimal, DISCOUNT basis as published by the Fed",
                         "timing": "month-end 1954+; monthly average 1934-1953"}

    # Ken French RF
    z = zipfile.ZipFile(RAW / "F-F_Research_Data_Factors_CSV.zip")
    txt = z.read(z.namelist()[0]).decode("latin-1").splitlines()
    rows = []
    for ln in txt:
        parts = [p.strip() for p in ln.split(",")]
        if len(parts) == 5 and parts[0].isdigit() and len(parts[0]) == 6:
            rows.append((parts[0], float(parts[4])))
        elif rows and ln.strip().lower().startswith("annual"):
            break
    rf = pd.Series({pd.Timestamp(f"{k[:4]}-{k[4:]}-01") + ME: v / 100 for k, v in rows})
    rf.index.name = "date"
    info["rf_usd_ret"] = {"segments": [{"source": "Ken French F-F_Research_Data_Factors RF/100 (1-month T-bill "
                                                  "return; Ibbotson to 2024-05, ICE BofA 1M after)",
                                        "first": str(rf.index.min().date()), "last": str(rf.index.max().date()),
                                        "n": int(len(rf))}],
                          "units": "decimal simple MONTHLY return (not annualised)", "timing": "return over month t"}

    df = pd.DataFrame({"tbill_cad": tbill_cad / 100, "policy_cad": policy_cad / 100, "y10_ca": y10_ca / 100,
                       "y10_us": y10_us / 100, "rf_usd_ret": rf, "tbill_usd": tbill_usd / 100}).sort_index()
    df.index.name = "date"
    sources = [src(n) for n in ("boc_TB.CDN.90D.MID", "statcan_10100122", "boc_STATIC_ATABLE_V39079", "boc_V39079",
                                "boc_V122530", "boc_BD.CDN.10YR.DQ.YLD", "fred_DGS10", "fred_GS10",
                                "shiller_ie_data", "fred_DTB3", "fred_TB3MS", "kf_ff3_monthly",
                                "fred_IRLTLT01CAM156N")]
    write(df, "rates_monthly.parquet", {
        "description": "Month-end rate levels (annual decimals) + Ken French RF monthly return. Index = calendar "
                       "month-end. Splice segments per column below.",
        "logical_as_of": str(df.dropna(how="all").index.max().date()),
        "sources": sources, "columns": info})
    return df, info


# ----------------------------------------------------------------------------- bonds
def build_bond_monthly(rates: pd.DataFrame, rinfo: dict):
    ca = bm.returns_from_yields(rates["y10_ca"].dropna(), 10.0, 1 / 12)
    us = bm.returns_from_yields(rates["y10_us"].dropna(), 10.0, 1 / 12)
    df = pd.DataFrame({"CA10_ret": ca, "US10_ret": us}).sort_index()
    df.index.name = "date"
    method = ("Par-bond repricing (FRAMEWORK §2): r_t = P(c=y_{t-1}, 10-1/12, y_t) + y_{t-1}/12 - 1, "
              "P(c,n,y) = c/y (1-(1+y/2)^(-2n)) + (1+y/2)^(-2n); semiannual compounding; "
              "research/cycle8/data_rates/bondmath.py; tests/test_cycle8_bond.py")
    write(df, "bond_monthly.parquet", {
        "description": "Constant-maturity 10Y par-bond monthly total returns, local currency (CA10 in CAD, US10 in "
                       "USD). No fees, no hedging (sleeve construction is downstream).",
        "method": method, "logical_as_of": str(df.index.max().date()),
        "columns": {"CA10_ret": {"units": "decimal simple monthly return, CAD", "yield_input": "rates_monthly.y10_ca",
                                 "segments": rinfo["y10_ca"]["segments"],
                                 "note": "months straddling a splice boundary mix sources (1951-01, 1982-06, 2001-01)"},
                    "US10_ret": {"units": "decimal simple monthly return, USD", "yield_input": "rates_monthly.y10_us",
                                 "segments": rinfo["y10_us"]["segments"],
                                 "note": "pre-1953-04 yields are interpolated annual values -> smooth returns; "
                                         "1953-04..1961-12 monthly averages -> mildly smoothed; boundary months "
                                         "1953-04 and 1962-01 mix sources"}},
        "sources": [src("fred_DGS10"), src("fred_GS10"), src("shiller_ie_data"),
                    src("boc_BD.CDN.10YR.DQ.YLD"), src("statcan_10100122")]})
    return df


def _ret_own_calendar(y: pd.Series, T: float) -> pd.Series:
    y = y.dropna() / 100
    return bm.returns_from_yields(y, T, 1 / 252)


def build_bond_daily():
    dgs10, dgs20, dgs30 = fred("DGS10"), fred("DGS20"), fred("DGS30")
    ca = valet("BD.CDN.10YR.DQ.YLD")
    us10 = _ret_own_calendar(dgs10, 10.0)
    # US20: joint US calendar = dates with DGS20 or DGS30; per-day return from one series on both days
    cal = dgs20.index.union(dgs30.index)
    y20 = dgs20.reindex(cal) / 100
    y30 = dgs30.reindex(cal) / 100
    r20 = pd.Series(bm.par_bond_return(y20.shift(1).to_numpy(), y20.to_numpy(), 20.0, 1 / 252), index=cal)
    r30 = pd.Series(bm.par_bond_return(y30.shift(1).to_numpy(), y30.to_numpy(), 20.0, 1 / 252), index=cal)
    # Level break in DGS20 on 1973-01-04 (20y-10y spread jumps -0.12 -> +0.39 pp overnight; a series
    # construction change, not a market move). On break days the return uses the DGS10 daily change.
    y10c = (dgs10 / 100).reindex(cal)
    breaks = [pd.Timestamp("1973-01-04")]
    for bd in breaks:
        i = cal.get_loc(bd)
        yp = y20.iloc[i - 1]
        r20.iloc[i] = bm.par_bond_return(yp, yp + (y10c.iloc[i] - y10c.iloc[i - 1]), 20.0, 1 / 252)
    us20 = r20.where(r20.notna(), r30)
    us20_src = pd.Series(np.where(r20.notna(), 20, np.where(r30.notna(), 30, 0)), index=cal)
    us20 = us20.loc[us20.first_valid_index():]
    ca10 = _ret_own_calendar(ca, 10.0)
    y20used = y20.where(y20.notna() & (us20_src == 20), y30)
    df = pd.DataFrame({"US10_ret": us10, "US20_ret": us20, "CA10_ret": ca10,
                       "US10_y": dgs10 / 100, "US20_y": y20used.where(us20_src > 0),
                       "US20_ysrc": us20_src.where(us20_src > 0), "CA10_y": ca / 100}).sort_index()
    df.index.name = "date"
    gap = us20_src[(us20_src == 30)]
    note20 = (f"DGS20 missing {gap.index.min().date()}..{gap.index.max().date()} ({len(gap)} days): return that day "
              "from DGS30 (both endpoints DGS30, priced as a 20Y par bond) so no level jump enters a return; "
              "US20_ysrc = 20 or 30 marks the yield series used. "
              "DGS20 level break on 1973-01-04 (+74bp vs DGS10 -2bp; 20y-10y spread -0.12 -> +0.39 pp): that day's "
              "US20 return uses the DGS10 yield change instead (otherwise a spurious -8.0% day).")
    write(df, "bond_daily.parquet", {
        "description": "Daily constant-maturity par-bond total returns (local ccy), step 1/252 per observation on "
                       "each series' OWN business-day calendar (NaN = no observation that day for that market; "
                       "holiday gaps are absorbed in the next observation with a single 1/252 accrual).",
        "method": "r_d = P(c=y_{d-1}, T-1/252, y_d) + y_{d-1}/252 - 1; T=10 (US10, CA10), 20 (US20).",
        "logical_as_of": str(df.index.max().date()),
        "columns": {"US10_ret": {"units": "decimal daily return USD", "source": "FRED DGS10"},
                    "US20_ret": {"units": "decimal daily return USD", "source": "FRED DGS20; DGS30 in DGS20 gap",
                                 "splice": note20},
                    "CA10_ret": {"units": "decimal daily return CAD", "source": "BoC Valet BD.CDN.10YR.DQ.YLD "
                                 "(longest free daily CA 10Y found: 2001-01-02+)"},
                    "US10_y": {"units": "annual decimal"}, "US20_y": {"units": "annual decimal"},
                    "US20_ysrc": {"units": "20 = DGS20, 30 = DGS30"}, "CA10_y": {"units": "annual decimal"}},
        "sources": [src("fred_DGS10"), src("fred_DGS20"), src("fred_DGS30"), src("boc_BD.CDN.10YR.DQ.YLD")]})
    return df


# ----------------------------------------------------------------------------- gold
def build_gold():
    g = pd.read_csv(RAW / "gold_prices_monthly.csv")
    g.index = pd.to_datetime(g["Date"] + "-01") + ME
    g = g["Price"].astype(float)
    g.index.name = "date"
    g = g.loc["1960-01-31":]  # 1833-1959 rows are annual averages repeated (datapackage.json)
    gc = yahoo("GC=F")
    gld = yahoo("GLD")
    gc_me = month_end_last(gc["close"])
    gld_me = month_end_last(gld["adjclose"])
    dfm = pd.DataFrame({"gold_usd_wb_avg": g, "gold_usd_gcf_me": gc_me, "gld_adjclose_me": gld_me}).sort_index()
    dfm.index.name = "date"
    write(dfm, "gold_monthly.parquet", {
        "description": "Gold USD/troy oz monthly. Primary long series = datahub/GitHub datasets/gold-prices "
                       "(World Bank Pink Sheet from 1960) = MONTHLY AVERAGE price, not month-end; returns from it "
                       "are smoothed (averaging cuts vol ~ by sqrt(2/3) and adds ~+0.25 autocorrelation). "
                       "Month-end series: COMEX front-month futures GC=F close (Yahoo; 2000-08+; futures, not LBMA "
                       "spot) and GLD adjclose (2004-11+; net of 0.40% fee). Running month excluded.",
        "logical_as_of": str(dfm.dropna(how="all").index.max().date()),
        "columns": {"gold_usd_wb_avg": {"units": "USD/oz level, monthly average", "source": "datasets/gold-prices "
                                        "monthly.csv (World Bank 1960+); 1833-1959 annual repeated rows excluded"},
                    "gold_usd_gcf_me": {"units": "USD/oz level, month-end (last trading day close)",
                                        "source": "Yahoo GC=F continuous front-month COMEX future (roll effects)"},
                    "gld_adjclose_me": {"units": "USD adjclose, month-end", "source": "Yahoo GLD"}},
        "sources": [src("gold_monthly"), src("gold_datapackage"), src("yahoo_GC=F"), src("yahoo_GLD")]})
    dfd = pd.DataFrame({"gold_usd_gcf": gc["close"], "gld_adjclose": gld["adjclose"]}).sort_index()
    dfd.index.name = "date"
    write(dfd, "gold_daily.parquet", {
        "description": "Daily gold: Yahoo GC=F close (COMEX continuous front-month, 2000-08-30+) and GLD adjclose "
                       "(2004-11-18+). No free daily LBMA series was reachable (see notes/blocked_rates.md).",
        "logical_as_of": str(dfd.index.max().date()),
        "columns": {"gold_usd_gcf": {"units": "USD/oz"}, "gld_adjclose": {"units": "USD"}},
        "sources": [src("yahoo_GC=F"), src("yahoo_GLD")]})
    return dfm, dfd


def main():
    rates, info = build_rates()
    build_bond_monthly(rates, info)
    build_bond_daily()
    build_gold()


if __name__ == "__main__":
    main()
