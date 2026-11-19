"""Cycle-7 FI data build: FI-NEW and FI-DEEP daily 10y excess returns (DATA ONLY; FRAMEWORK §1-§3, ADDENDUM-1).

Nothing here computes a signal, a strategy, control or portfolio return. Outputs are per-instrument daily excess
returns and instrument-level QA (gaps, flat runs, traded-proxy tracking error, point-in-time notes).

Construction = cycle-6 code path: research.core_premia_data.rates_fx_eq.synthetic.bond_excess(series, 10, "par",
country-coupon-flag, rf) -> r = y_{t-1}dt - D dy + 0.5 C dy^2 - rf_{t-1}dt, par-bond D, C (annual coupon for the
cycle-6 ANNUAL set + other euro-area/European annual payers GR, HU; semiannual otherwise), no return across a gap
> 10 business days. QA = cycle-6 FRAMEWORK §3 via research.cycle6.data_rates.build.{gap_scan, flat_runs, te_ratio}:
FAIL if (a) monthly TE/sigma_proxy > 0.60 on >= 36 months vs a pre-declared proxy, (b) unexplained gap > 10 bd in
the used window, (c) flat run >= 10 bd in the used window, (d) not point-in-time. ADDENDUM-1 item 1 truncation:
history starts after the last unexplained gap > 10 bd and after the last flat run >= 10 bd.

Cycle-7 additions (declared before any return was computed; FRAMEWORK §1 requires DAILY returns):
  * Daily-frequency rule: a series segment observed weekly or less often is not a daily series. History starts after
    the last calendar month (the final, partial month excepted) with fewer than 10 observations. Reported per row.
  * Short rates, cycle-6 priority: official daily (lag 1 obs) > LSE daily (lag 1 obs, ffill <= 10 bd) > OECD monthly
    (IRSTCI, IR3TIB overriding, value of month M usable from M+1). Cycle-6 currencies reuse the cycle-6
    short_rates_daily bytes. Euro members use the EUR rate from their euro entry date, the national OECD rate before
    (cycle 6 had no pre-euro need; GR joined 2001-01-01, DE pre-1999 for FI-DEEP). MYR: Bank Negara OPR step series
    (LSE maoprate change points, lag 1 day, carried forward to last obs + 10 days).
  * FI-DEEP par yields derived from official zero-coupon curves (BoE GLC spot, continuously compounded, semiannual
    par; SNB rendoblid Confederation spot, annual compounding, annual par): par = f(1 - D(T)) / sum_k D(k/f).
    Checked against the official par series on overlap (UK IUDMNPY) / cycle-6 series (CH) and QA'd with the cycle-6
    series of the same market as the tracking proxy (TE/sigma <= 0.60 on >= 36 overlapping months).
  * FI-DEEP proxy rule: extension series are compared with the cycle-6 PASS series of the same market on their
    overlap (the cycle-6 series is the reference, no traded proxy existed before 1993).
Proxies (pre-declared, fixed before any TE was computed): AU IGB.AX (cycle-6), KR 148070.KS (KOSEF 10y KTB),
IN LTGILTBEES.NS (Nifty 8-13y G-Sec), ZA STXGOV.JO (Satrix SA bond, ALBI). No single-market local-currency 10y
proxy for the other markets (BR IRFM11/IMAB11 are 1-5y nominal / inflation-linked: not declared).
Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.cycle7.data_fi.build
"""
from __future__ import annotations

import glob
import io
import json
import zipfile

import numpy as np
import pandas as pd

from research.core_premia_data.rates_fx_eq import synthetic as old
from research.cycle6.data_rates.build import flat_runs, gap_scan, te_ratio
from research.cycle7.data_fi.common import D6, META, OLD, OUT, RAW, ROOT, sha_file, utc_now, write_json
from research.cycle7.data_fi.lse_ingest import parse_reply

IDX = pd.bdate_range("1960-01-01", "2026-09-30")
# FI-DEEP: rules (gap/flat/daily-frequency truncation) apply to the extension segment actually used (dates before
# the cycle-6 first date); TE vs the cycle-6 series uses the full extension series on the overlap.
C6_FI = ["CA", "CH", "DE", "ES", "FR", "IT", "JP", "NO", "NZ", "SE", "UK", "US"]
ANNUAL = {"DE", "FR", "IT", "ES", "CH", "SE", "NO", "NL", "BE", "AT", "GR", "HU"}
DEEP_CUT = pd.Timestamp("1993-05-31")  # last holding day needed by the 1993-03 signal month (one-session lag)
DEEP_FIRST_MONTH_EXCL = "1993-04"  # FI-DEEP months are those before cycle-6 TSMOM-FI first month

# ---------------------------------------------------------------------------------------------- FI-NEW universe
# market -> (currency, OECD area, euro entry date or None, yield source key)
NEW = {
    "AU": ("AUD", "AUS", None, "lse:AU10Y"), "GR": ("EUR", "GRC", "2001-01-01", "lse:GR10Y"),
    "ID": ("IDR", "IDN", None, "lse:ID10Y"), "RU": ("RUB", "RUS", None, "lse:RU10Y"),
    "CN": ("CNY", "CHN", None, "lse:CN10Y"), "MX": ("MXN", "MEX", None, "lse:MX10Y"),
    "CL": ("CLP", "CHL", None, "lse:CL10Y"), "BR": ("BRL", "BRA", None, "lse:BR10Y"),
    "ZA": ("ZAR", "ZAF", None, "lse:ZA10Y"), "NG": ("NGN", None, None, "lse:NG10Y"),
    "IN": ("INR", "IND", None, "lse:IN10Y"), "SG": ("SGD", None, None, "lse:SG10Y"),
    "MY": ("MYR", None, None, "lse:MY10Y"), "KR": ("KRW", "KOR", None, "lse:KR10Y"),
    "TH": ("THB", None, None, "lse:TH10Y"), "TR": ("TRY", "TUR", None, "lse:TR10Y"),
    "HU": ("HUF", "HUN", None, "akk:10Y"),
}
LSE_SHORT = {"KRW": "southkoreintrat", "CLP": "chileintrat", "INR": "indiaintrat", "IDR": "indonesiaintrat",
             "CNY": "chinaintrat", "ZAR": "southafriintrat", "HUF": "hungaryintrat", "SGD": "sibcon",
             "THB": "thailandintrat", "NGN": "nigeriaintrat"}
PROXY_NEW = {"AU": "IGB.AX", "KR": "148070.KS", "IN": "LTGILTBEES.NS", "ZA": "STXGOV.JO"}
NO_DAILY = {  # market -> (what was checked, exact missing field)
    "NL": "LSE bonds: NL3M/NL6M/NL2Y(2025-07+) only; DNB (www.dnb.nl) 403; ECB data-api blocked (TLS)",
    "BE": "LSE bonds: BE2Y from 2025-07 only; NBB.Stat (stat.nbb.be) empty reply",
    "AT": "LSE bonds: AT1Y only; OeNB site reachable but no daily 10y series found",
    "DK": "Danmarks Nationalbank StatBank DNRENTD (daily) holds only policy/DESTR rates; bond yields only in DNRENTM (monthly)",
    "FI": "LSE bonds: FI2Y from 2025-07 only; Suomen Pankki blocked (TLS)",
    "IE": "LSE: no IE yields; Central Bank of Ireland reachable, monthly only",
    "PT": "LSE bonds: PT1Y/3Y/5Y (5Y from 1994) but PT10Y absent; PT20Y/30Y from 2025-07 only",
    "PL": "LSE: no PL yields (polandintrat short rate only); NBP 403",
    "CZ": "LSE: no CZ yields; CNB publishes 10y for convergence criteria monthly",
    "IL": "LSE: no IL yields; Bank of Israel SDMX (edge.boi.gov.il) blocked (TLS)",
    "PH": "LSE: no PH yields; BSP 403",
    "CO": "LSE: no CO yields (colombiaintrat short rate only)",
    "HK": "LSE: no HK yields; HKMA API timed out / 502",
    "TW": "LSE: no TW yields (taiwanintrat short rate only)",
}

# ---------------------------------------------------------------------------------------------- FI-DEEP extensions
DEEP_EXT = {  # market -> (currency, national pre-euro OECD area, euro entry, source key)
    "UK": ("GBP", None, None, "boe_glc_par"), "CH": ("CHF", None, None, "snb_par"),
    "DE": ("EUR", "DEU", "1999-01-01", "bbk_r0815"), "CA": ("CAD", None, None, "statcan_v39055"),
}


MONTHLY_INFEASIBLE = {  # FRAMEWORK §1: missing field = DAILY frequency (TSMOM vol needs daily excess returns)
    "OECD MEI long-term rates IRLT (all countries)": "monthly averages; data/core_premia/rates_fx_eq/processed/oecd_monthly.parquet (sdmx.oecd.org DF_FINMARK)",
    "BoE Millennium of Macroeconomic Data": "annual/monthly; https://www.bankofengland.co.uk/statistics/research-datasets",
    "Shiller long rate (US)": "monthly; http://www.econ.yale.edu/~shiller/data.htm",
    "Jorda-Schularick-Taylor Macrohistory": "annual; https://www.macrohistory.net/database/",
    "SNB rendoblid CH spot curve 1988-1997": "~62 obs/yr (weekly) before 1998; https://data.snb.ch/api/cube/rendoblid/data/csv/en",
    "SNB rendoblim": "monthly; https://data.snb.ch/api/cube/rendoblim/data/csv/en",
    "Bundesbank listed Federal securities 8-15y (BBSIS ...R0815) before 1987-11": "weekly (48 obs/yr)",
    "Bundesbank listed Federal 9-10y unweighted (BBSIS UMU R0910) before 1994": "weekly",
    "Riksbank SEGVB10YC 1987-01..1990-02": "daily but truncated by the ADDENDUM-1 gap rule (gap 1990-01-22..02-19)",
    "US H.15 RIFLGFCY10 1962-01..1965-06": "daily but truncated by the flat-run rule (last flat run 1965-05-28..06-11), as cycle 6",
    "MoF JGB 10y before 1986-07": "10y column starts 1986-07-05 in jgbcme_all.csv (other tenors from 1974-09)",
    "France TEC10 (Banque de France webstat)": "API key registration required (not used); LSE FR10Y 1990-06..1994-02 gap",
    "RBA F2 daily (AU)": "blocked: https://www.rba.gov.au/statistics/tables/xls/f02d.xlsx (TLS self-signed chain)",
    "RBNZ B2 daily (NZ)": "403: https://www.rbnz.govt.nz/-/media/project/sites/rbnz/files/statistics/series/b/b2/hb2-daily.xlsx",
    "Norges Bank GOVT_GENERIC_RATES 10y": "daily from 2019 only",
}


# ---------------------------------------------------------------------------------------------- loaders
def lse_series():
    """Union of all direct MCP macro_series replies per symbol (complete JSON rows only), with conflict count."""
    recs = [json.loads(x) for x in (RAW / "lse_mcp" / "manifest.jsonl").read_text().splitlines()]
    rows = {}
    files = {}
    for r in recs:
        s = r["arguments"]["symbol"]
        got, _ = parse_reply((RAW / r["path"]).read_text())
        rows.setdefault(s, []).extend((d, v) for _, d, v in got)
        files.setdefault(s, []).append({"path": r["path"], "sha256": r["sha256"], "n_rows": r["n_rows"],
                                        "arguments": r["arguments"]})
    out, conflicts = {}, {}
    for s, lst in rows.items():
        df = pd.DataFrame(lst, columns=["date", "value"]).dropna()
        df["date"] = pd.to_datetime(df["date"])
        g = df.groupby("date")["value"].nunique()
        conflicts[s] = int((g > 1).sum())
        out[s] = df.drop_duplicates("date", keep="first").set_index("date")["value"].astype(float).sort_index()
    return out, conflicts, files


def akk_10y():
    parts = []
    for f in sorted(glob.glob(str(RAW / "akk_hu" / "benchmark_*.json"))):
        d = json.loads(open(f).read())
        for r in d.get("data", []):
            if r.get("tenor") == "10Y" and r.get("yield") is not None:
                parts.append((r["date"], float(r["yield"]), r.get("isin")))
    df = pd.DataFrame(parts, columns=["date", "value", "isin"]).drop_duplicates("date")
    df["date"] = pd.to_datetime(df["date"])
    s = df.set_index("date").sort_index()
    return s["value"], s["isin"]


def bbk(name):
    f = sorted(glob.glob(str(RAW / "bundesbank" / f"{name}.*.csv")))[-1]
    d = pd.read_csv(f, skiprows=8, header=None, names=["date", "v", "flag"])
    d = d[d.v != "."]
    d["date"] = pd.to_datetime(d["date"])
    return d.set_index("date")["v"].astype(float).sort_index(), f


def statcan():
    f = sorted(glob.glob(str(RAW / "statcan" / "v39055.*.json")))[-1]
    pts = json.loads(open(f).read())[0]["object"]["vectorDataPoint"]
    s = pd.Series({pd.Timestamp(p["refPer"]): p["value"] for p in pts if p["value"] is not None}, dtype=float)
    return s.sort_index(), f


def snb_par():
    f = sorted(glob.glob(str(RAW / "snb" / "rendoblid.*.csv")))[-1]
    d = pd.read_csv(f, sep=";", skiprows=3)
    d = d.dropna(subset=["Value"])
    w = d.pivot(index="Date", columns="D0", values="Value").astype(float)
    w.index = pd.to_datetime(w.index)
    cols = [f"{k}J" for k in range(1, 10)] + ["10J0"]
    z = w[cols].dropna() / 100.0
    D = np.column_stack([(1 + z[c]) ** -(i + 1) for i, c in enumerate(cols)])
    par = (1 - D[:, -1]) / D.sum(axis=1) * 100.0
    return pd.Series(par, index=z.index).sort_index(), f


def boe_par():
    f = sorted(glob.glob(str(RAW / "boe" / "glcnominalddata.*.zip")))[-1]
    zf = zipfile.ZipFile(f)
    out = []
    for n in sorted(zf.namelist()):
        xl = pd.ExcelFile(io.BytesIO(zf.read(n)))
        sh = [q for q in xl.sheet_names if "spot curve" in q.lower() and "short" not in q.lower()]
        x = xl.parse(sh[0], header=None)
        hdr = x.iloc[3]
        body = x.iloc[5:]
        body = body[pd.to_datetime(body[0], errors="coerce").notna()]
        mats = {float(h): j for j, h in enumerate(hdr) if j > 0 and isinstance(h, (int, float)) and not pd.isna(h)}
        need = [k / 2 for k in range(1, 21)]
        if not all(m in mats for m in need):
            continue
        Z = body[[mats[m] for m in need]].apply(pd.to_numeric, errors="coerce") / 100.0
        Z.columns = need
        # short end missing on days when the shortest gilt is longer than 6m: flat-extrapolate from the shortest
        # available maturity if it is <= 2y (declared); interior/long-end holes are not filled
        first = Z.notna().idxmax(axis=1).where(Z.notna().any(axis=1))
        lead = Z.notna().cumsum(axis=1) == 0
        Z = Z.where(~lead, Z.bfill(axis=1))
        Z = Z.where(np.repeat((first <= 2.0).to_numpy()[:, None], Z.shape[1], axis=1))
        dates = pd.to_datetime(body[0])
        ok = Z.notna().all(axis=1).to_numpy()
        Zv = Z.to_numpy()[ok]
        D = np.exp(-Zv * np.array(need))
        par = 2 * (1 - D[:, -1]) / D.sum(axis=1) * 100.0
        out.append(pd.Series(par, index=dates[ok].to_numpy()))
    s = pd.concat(out).sort_index()
    return s[~s.index.duplicated()], f


def yahoo_proxy(tk):
    """Adjusted close from a Yahoo chart JSON saved in raw/yahoo (repo market_daily for cycle-6 IGB.AX)."""
    if tk == "IGB.AX":
        m = pd.read_parquet(OLD / "processed" / "market_daily.parquet")
        m["date"] = pd.to_datetime(m["date"])
        g = m[m.ticker == tk].set_index("date").sort_index()
        return g[~g.index.duplicated()]["adjclose"], "data/core_premia/rates_fx_eq/processed/market_daily.parquet"
    fs = sorted(glob.glob(str(RAW / "yahoo" / f"{tk}.*.json")))
    if not fs:
        return None, None
    d = json.loads(open(fs[-1]).read())["chart"]["result"][0]
    ts = pd.to_datetime(d["timestamp"], unit="s").normalize()
    ind = d["indicators"]
    adj = ind.get("adjclose", [{}])[0].get("adjclose") or ind["quote"][0]["close"]
    s = pd.Series(adj, index=ts, dtype=float).dropna()
    return s[~s.index.duplicated(keep="last")].sort_index(), fs[-1]


# ---------------------------------------------------------------------------------------------- short rates
def oecd_rate(o, area, index):
    out = pd.DataFrame(index=index)
    out["rf_pct"], out["rf_source"] = np.nan, None
    if area is None:
        return out
    for meas in ("IRSTCI", "IR3TIB"):
        s = o[(o.ref_area == area) & (o.measure == meas)].set_index("month")["value_pct"].sort_index()
        if s.empty:
            continue
        s.index = s.index + pd.Timedelta(days=1)
        s = s.reindex(index.union(s.index)).ffill().reindex(index)
        s[index > o[(o.ref_area == area) & (o.measure == meas)]["month"].max() + pd.Timedelta(days=62)] = np.nan
        m = s.notna()
        out.loc[m, "rf_pct"] = s[m]
        out.loc[m, "rf_source"] = f"oecd_{meas}_{area}_prev_month_avg"
    return out


def overlay_lse(base, s, label, limit=10):
    s = s.shift(1)
    last = s.index.max()
    s = s.reindex(IDX.union(s.index)).ffill(limit=limit).reindex(IDX)
    s[IDX > last + pd.Timedelta(days=10)] = np.nan
    m = s.notna()
    base.loc[m, "rf_pct"] = s[m]
    base.loc[m, "rf_source"] = f"lse:economics/{label}_lag1"
    return base


def c6_rates():
    s = pd.read_parquet(D6 / "rates" / "short_rates_daily.parquet")
    s["date"] = pd.to_datetime(s["date"])
    return {c: g.set_index("date")[["rf_pct", "rf_source"]].reindex(IDX) for c, g in s.groupby("ccy")}


def rate_for(ccy, area, euro_entry, o, c6, lse):
    if ccy in c6 and euro_entry is None:
        return c6[ccy], "cycle-6 short_rates_daily bytes"
    if ccy == "EUR":  # national before euro entry, cycle-6 EUR after
        nat = oecd_rate(o, area, IDX)
        eur = c6["EUR"]
        m = IDX >= pd.Timestamp(euro_entry)
        r = nat.copy()
        r.loc[m, ["rf_pct", "rf_source"]] = eur.loc[m, ["rf_pct", "rf_source"]].to_numpy()
        return r, f"OECD {area} before {euro_entry}, cycle-6 EUR after"
    base = oecd_rate(o, area, IDX)
    note = f"OECD {area}" if area else "no OECD area"
    if ccy in LSE_SHORT and LSE_SHORT[ccy] in lse:
        base = overlay_lse(base, lse[LSE_SHORT[ccy]], LSE_SHORT[ccy])
        note += f" < LSE daily {LSE_SHORT[ccy]}"
    if ccy == "MYR":
        cp = pd.read_csv(RAW / "lse_mcp_inline" / "maoprate_changepoints.csv", comment="#")
        cp["date"] = pd.to_datetime(cp["date"])
        s = cp.set_index("date")["value"].shift(1, freq="D")
        last = cp["date"].max()
        s = s.reindex(IDX.union(s.index)).ffill().reindex(IDX)
        s[IDX > last + pd.Timedelta(days=10)] = np.nan
        m = s.notna()
        base.loc[m, "rf_pct"], base.loc[m, "rf_source"] = s[m], "lse:economics/maoprate_OPR_step_lag1d"
        note += " < LSE maoprate OPR step"
    return base, note


# ---------------------------------------------------------------------------------------------- one instrument
def daily_freq_start(s: pd.Series):
    cnt = s.groupby(s.index.to_period("M")).size()
    full = pd.period_range(cnt.index.min(), cnt.index.max(), freq="M")
    cnt = cnt.reindex(full, fill_value=0).iloc[:-1]
    low = cnt[cnt < 10]
    if low.empty:
        return None, 0
    return (low.index.max() + 1).to_timestamp(), int(len(low))


def build_one(mid, ctry, s, src, sid, rf, proxy=None, proxy_label=None, proxy_rf=None, explained=()):
    s = s.dropna()
    s = s[~s.index.duplicated()].sort_index()
    dts = s.index.to_series().reset_index(drop=True)
    gaps = gap_scan(dts, list(explained))
    unexpl = [g for g in gaps if not g["explained"]]
    flat_all = flat_runs(dts, s.reset_index(drop=True))
    fstart, n_low = daily_freq_start(s)
    start = s.index.min()
    if unexpl:
        start = max(start, pd.Timestamp(unexpl[-1]["to"]))
    if flat_all:
        nxt = s.index[s.index > pd.Timestamp(flat_all[-1]["to"])]
        start = max(start, nxt[0] if len(nxt) else s.index.max())
    if fstart is not None:
        nxt = s.index[s.index >= fstart]
        start = max(start, nxt[0] if len(nxt) else s.index.max())
    su = s[s.index >= start]
    if len(su) < 3:
        return None, {"market_id": mid, "qa_status": "FAIL", "qa_reasons": "no usable daily history after truncation",
                      "source": f"{src}:{sid}", "notes": f"gaps {len(unexpl)}, flats {len(flat_all)}, low-freq months {n_low}"}
    df = old.bond_excess(su, 10.0, "par", "DE" if ctry in ANNUAL else "US", rf)
    gb = np.r_[np.nan, np.busday_count(su.index[:-1].values.astype("datetime64[D]"),
                                       su.index[1:].values.astype("datetime64[D]")) - 1][1:]
    df.loc[gb > 10, ["excess_ret", "total_ret"]] = np.nan
    df = df.reset_index(names="date")
    df["market_id"], df["country"], df["tenor"], df["source"], df["series_id"] = mid, ctry, 10, src, sid
    dts_u = su.index.to_series().reset_index(drop=True)
    g_used = [g for g in gap_scan(dts_u, list(explained)) if not g["explained"]]
    fr = flat_runs(dts_u, su.reset_index(drop=True))
    reasons, notes = [], []
    te = n_te = rho = None
    if proxy is not None:
        te, n_te, rho = te_ratio(df.set_index("date")["excess_ret"], proxy)
        notes.append(f"proxy {proxy_label}: TE/sigma={te if te is None else round(te, 3)} on {n_te} months, "
                     f"rho={rho if rho is None else round(rho, 3)}")
        if te is not None and n_te >= 36 and te > 0.60:
            reasons.append(f"(a) TE/sigma_proxy {te:.2f} > 0.60 vs {proxy_label} ({n_te} months)")
        if n_te is not None and n_te < 36:
            notes.append(f"(a) proxy overlap {n_te} < 36 months: TE not binding")
    else:
        notes.append("no single-market traded proxy declared: (a) not applicable")
    if g_used:
        reasons.append(f"(b) {len(g_used)} unexplained gaps >10bd")
    if fr:
        reasons.append(f"(c) {len(fr)} flat runs >=10bd, first {fr[0]}")
    if unexpl or flat_all or fstart is not None:
        notes.append(f"history truncated to {start.date()} (last unexplained gap>10bd {unexpl[-1] if unexpl else None}; "
                     f"last flat run>=10bd {flat_all[-1] if flat_all else None}; daily-frequency rule: {n_low} months "
                     f"<10 obs, start {fstart.date() if fstart is not None else None}); STRICT full-history status: "
                     f"{len(unexpl)} gaps, {len(flat_all)} flat runs")
    d_ = su.diff()
    spikes = int(((d_.abs() > 0.25) & (d_.shift(-1).abs() > 0.25) & (d_ * d_.shift(-1) < 0)).sum())
    notes.append(f"reversing spikes >25bp in used window: {spikes}")
    rfsrc = df["rf_source"].fillna("NONE").astype(str).str.split(":").str[0].str.split("_").str[:2].str.join("_")
    notes.append(f"rf sources {rfsrc.value_counts().to_dict()}; rf missing rows {int(df.rf_pct.isna().sum())}")
    ex = df.dropna(subset=["excess_ret"])
    if ex.empty:
        reasons.append("no excess return (short rate missing on every row)")
    cand = {"class": "FI", "market_id": mid, "economic_market": f"{ctry} government bond 10y",
            "construction": "yield->y*dt - D*dy + 0.5*C*dy^2 - local cash (par bond D,C; "
                            f"{'annual' if ctry in ANNUAL else 'semiannual'} coupon)",
            "source": f"{src}:{sid}", "first_date": str(ex.date.min().date()) if len(ex) else "",
            "last_date": str(ex.date.max().date()) if len(ex) else "",
            "n_months": int(ex.date.dt.to_period("M").nunique()), "qa_status": "FAIL" if reasons else "PASS",
            "qa_reasons": "; ".join(reasons), "tenor": 10.0, "notes": "; ".join(notes),
            "_te": te, "_n_te": n_te, "_rho": rho, "_gaps": gaps, "_flat": fr, "_start": str(start.date())}
    return df, cand


def proxy_excess(px, rf):
    pr = px.pct_change()
    dt_ = px.index.to_series().diff().dt.days / 365.0
    return pr - rf["rf_pct"].reindex(px.index) / 100 * dt_


# ---------------------------------------------------------------------------------------------- panels / counts
CAND_COLS = ["class", "market_id", "qa_status", "source_class", "tenor", "economic_market", "construction", "source",
             "first_date", "last_date", "n_months", "alias_of", "use_note", "source_file"]


def panel(bonds: pd.DataFrame, cands: pd.DataFrame) -> pd.DataFrame:
    p = cands[cands.qa_status == "PASS"].set_index("market_id")
    x = bonds[bonds.market_id.isin(p.index)][["date", "market_id", "excess_ret"]].dropna()
    x = x.merge(p[["first_date", "last_date"]], left_on="market_id", right_index=True)
    x = x[(x.date >= pd.to_datetime(x.first_date)) & (x.date <= pd.to_datetime(x.last_date))]
    x = x.rename(columns={"excess_ret": "value"})[["date", "market_id", "value"]]
    x = x.sort_values(["market_id", "date"]).reset_index(drop=True)
    if x.duplicated(["date", "market_id"]).any():
        raise ValueError("duplicate (date, market_id)")
    return x


def tsmom_counts(p: pd.DataFrame, month_filter=None):
    """Data-availability eligibility (research/cycle6/feasibility_counts.py TSMOM rule): >= 756 valid daily obs
    through month-end t and a return in each of months t-11..t; defined iff >= 3 eligible."""
    d = p.pivot(index="date", columns="market_id", values="value").sort_index()
    per = d.index.to_period("M")
    months = pd.period_range(per.min(), per.max(), freq="M")
    mh = d.notna().groupby(per).any().reindex(months, fill_value=False)
    cnt = d.notna().cumsum().where(d.notna())
    vol_ok = (cnt >= 756).where(d.notna()).fillna(False).astype(bool).groupby(per).any().reindex(months,
                                                                                                    fill_value=False)
    al = None
    for L in range(12):
        sh = mh.shift(L, fill_value=False)
        al = sh if al is None else (al & sh)
    n = (al & vol_ok).sum(axis=1)
    if month_filter is not None:
        n = n[month_filter(n.index)]
    ok = n >= 3
    return {"defined_months": int(ok.sum()), "first_defined": str(n.index[ok.argmax()]) if ok.any() else None,
            "last_defined": str(n.index[::-1][ok[::-1].argmax()]) if ok.any() else None,
            "max_eligible": int(n.max()) if len(n) else 0, "feasible_ge_24": bool(ok.sum() >= 24),
            "eligible_by_month": {str(k): int(v) for k, v in n[n > 0].items()}}


def to_candidate_list(cands, source_file, use_note):
    rows = []
    for c in cands:
        if c.get("qa_status") != "PASS":
            continue
        rows.append({"class": "FI", "market_id": c["market_id"], "qa_status": "PASS", "source_class": "FI",
                     "tenor": 10.0, "economic_market": c["economic_market"], "construction": c["construction"],
                     "source": c["source"], "first_date": c["first_date"], "last_date": c["last_date"],
                     "n_months": c["n_months"], "alias_of": "", "use_note": use_note, "source_file": source_file})
    return pd.DataFrame(rows, columns=CAND_COLS).sort_values("market_id").reset_index(drop=True)


def all_cands_frame(cands):
    cols = ["class", "market_id", "economic_market", "construction", "source", "first_date", "last_date", "n_months",
            "qa_status", "qa_reasons", "tenor", "notes"]
    return pd.DataFrame([{k: c.get(k, "") for k in cols} for c in cands], columns=cols)


# ---------------------------------------------------------------------------------------------- main
def main():
    o = pd.read_parquet(OLD / "processed" / "oecd_monthly.parquet")
    c6 = c6_rates()
    lse, conflicts, lse_files = lse_series()
    rec = {"built_at_utc": utc_now().isoformat(), "lse_conflicting_dates": conflicts, "short_rates": {}, "inputs": {}}

    # ------------------------------ FI-NEW
    bonds, cands = [], []
    for ctry, (ccy, area, euro, key) in NEW.items():
        rf, rnote = rate_for(ccy, area, euro, o, c6, lse)
        rec["short_rates"][ctry] = rnote
        if key.startswith("lse:"):
            sym = key[4:]
            s, src, sid = lse[sym], "lse_vendor_mcp", f"bonds/{sym}"
            rec["inputs"][f"FI_{ctry}_10Y"] = {"files": lse_files[sym]}
        else:
            s, isin = akk_10y()
            src, sid = "akk_hu", "getBenchmark tenor=10Y"
            rec["inputs"]["FI_HU_10Y"] = {"files": sorted(glob.glob(str(RAW / "akk_hu" / "*.json"))),
                                          "benchmark_isin_changes": int((isin != isin.shift()).sum() - 1)}
        px = lbl = None
        if ctry in PROXY_NEW:
            raw, pf = yahoo_proxy(PROXY_NEW[ctry])
            if raw is not None:
                px, lbl = proxy_excess(raw, rf), PROXY_NEW[ctry]
                rec["inputs"][f"proxy_{ctry}"] = pf
        df, cand = build_one(f"FI_{ctry}_10Y", ctry, s, src, sid, rf, px, lbl)
        if ctry == "AU":
            cand["notes"] += "; cycle-6 FAIL (LSE vendor, TE 0.64 vs IGB.AX); re-tested on a fresh direct MCP pull"
        if df is not None:
            bonds.append(df)
        cands.append(cand)
    for c, why in NO_DAILY.items():
        cands.append({"class": "FI", "market_id": f"FI_{c}_10Y", "economic_market": f"{c} government bond 10y",
                      "construction": "none", "source": "none", "first_date": "", "last_date": "", "n_months": 0,
                      "qa_status": "FAIL", "qa_reasons": "INFEASIBLE: no free DAILY 10y yield", "tenor": 10.0,
                      "notes": why})
    b = pd.concat(bonds, ignore_index=True)
    ev = OUT / "eval_new"
    (ev / "panels").mkdir(parents=True, exist_ok=True)
    b.to_parquet(ev / "bond_excess_daily_full.parquet", index=False)
    cl = to_candidate_list(cands, "data/cycle7/fi/eval_new/candidates_all.csv", "FI-NEW 10y per country (FRAMEWORK §2)")
    all_cands_frame(cands).to_csv(ev / "candidates_all.csv", index=False)
    cl.to_csv(ev / "candidate_list.csv", index=False)
    pn = panel(b, pd.DataFrame(cands))
    pn.to_parquet(ev / "panels" / "daily_excess_FI10.parquet", index=False)
    feas_new = tsmom_counts(pn)
    qa_new = {c["market_id"]: {k: c.get(k) for k in ("_te", "_n_te", "_rho", "_gaps", "_flat", "_start")}
              for c in cands if "_gaps" in c}
    write_json(ev / "completeness.json", {
        "written_utc": utc_now().isoformat(), "sample": "FI-NEW",
        "scope": "10y government bonds not in the cycle-6 FI 10y universe (CA CH DE ES FR IT JP NO NZ SE UK US)",
        "conventions": {"bond_excess": "cycle-6 code path synthetic.bond_excess(series, 10, 'par', coupon flag, rf); "
                                       "no return across a gap > 10 bd", "qa": "cycle-6 FRAMEWORK §3 (a)-(d) + "
                        "ADDENDUM-1 truncation + cycle-7 daily-frequency rule (build.py docstring)",
                        "short_rates": rec["short_rates"], "proxies": PROXY_NEW},
        "candidates": {c["market_id"]: {"qa_status": c["qa_status"], "qa_reasons": c.get("qa_reasons", ""),
                                        "first_date": c.get("first_date", ""), "last_date": c.get("last_date", "")}
                       for c in cands},
        "qa_detail": qa_new, "inputs": rec["inputs"], "lse_conflicting_dates": conflicts,
        "panel_rows": len(pn), "panel_sha256": sha_file(ev / "panels" / "daily_excess_FI10.parquet"),
        "feasibility_tsmom": {k: v for k, v in feas_new.items() if k != "eligible_by_month"},
        "not_frozen": "no snapshot frozen (instruction)"})

    # ------------------------------ FI-DEEP
    c6c = pd.read_csv(D6 / "rates" / "candidates.csv")
    c6b = pd.read_parquet(D6 / "rates" / "bond_excess_daily.parquet")
    c6b["date"] = pd.to_datetime(c6b["date"])
    c6_first = {r.market_id: pd.Timestamp(r.first_date) for r in c6c.itertuples()
                if r.qa_status == "PASS" and float(r.tenor) == 10}
    ylong = pd.read_parquet(OLD / "processed" / "yields_daily.parquet")
    ylong["date"] = pd.to_datetime(ylong["date"])
    ext_series = {"UK": boe_par(), "CH": snb_par(), "DE": bbk("bbk_r0815"), "CA": statcan()}
    deep_rows, deep_cands, level_checks = [], [], {}
    for ctry, (ccy, area, euro, key) in DEEP_EXT.items():
        s, f = ext_series[ctry]
        mid = f"FI_{ctry}_10Y"
        if euro:
            rf, rnote = rate_for(ccy, area, euro, o, c6, lse)
        else:
            rf, rnote = c6[ccy], "cycle-6 short_rates_daily bytes"
        rec["short_rates"][f"DEEP_{ctry}"] = rnote
        ref = c6b[c6b.market_id == mid].set_index("date")
        c6y = ref["y"] * 100
        j = pd.concat([s.rename("ext"), c6y.rename("c6")], axis=1, join="inner").dropna()
        lv = {"n": len(j)}
        if len(j):
            dd = j.ext - j.c6
            lv.update({"mean_diff_bp": round(dd.mean() * 100, 2), "p95_abs_diff_bp": round(dd.abs().quantile(.95) * 100, 2),
                       "corr_daily_change": round(float(j.diff().corr().iloc[0, 1]), 3)})
        if ctry == "UK":  # official par (IUDMNPY) check
            off = ylong[(ylong.source == "boe_iadb") & (ylong.series_id == "IUDMNPY")].set_index("date")["value_pct"]
            jj = pd.concat([s.rename("ext"), off.rename("off")], axis=1, join="inner").dropna()
            lv["vs_IUDMNPY"] = {"n": len(jj), "mean_diff_bp": round((jj.ext - jj.off).mean() * 100, 2),
                                "p95_abs_diff_bp": round((jj.ext - jj.off).abs().quantile(.95) * 100, 2)}
        level_checks[mid] = lv
        sc = s.dropna()
        sc = sc[~sc.index.duplicated()].sort_index()
        full = old.bond_excess(sc, 10.0, "par", "DE" if ctry in ANNUAL else "US", rf)
        sd = sc.index
        gbf = np.busday_count(sd[:-1].values.astype("datetime64[D]"), sd[1:].values.astype("datetime64[D]")) - 1
        full.loc[gbf > 10, "excess_ret"] = np.nan
        te_full = te_ratio(full["excess_ret"], ref["excess_ret"])
        s_used = s[s.index < c6_first[mid]]
        df, cand = build_one(mid, ctry, s_used, key, f.split("/")[-1], rf, None, None)
        te, n_te, rho = te_full
        cand["_te"], cand["_n_te"], cand["_rho"] = te, n_te, rho
        cand["notes"] = cand["notes"].replace("no single-market traded proxy declared: (a) not applicable",
                                              f"proxy cycle-6 {mid} on overlap (full extension series): TE/sigma="
                                              f"{te if te is None else round(te, 3)} on {n_te} months, rho="
                                              f"{rho if rho is None else round(rho, 3)}; QA rules applied to the "
                                              f"segment before the cycle-6 first date {c6_first[mid].date()}")
        if te is not None and n_te >= 36 and te > 0.60:
            cand["qa_status"] = "FAIL"
            cand["qa_reasons"] = "; ".join(x for x in [cand["qa_reasons"], f"(a) TE/sigma {te:.2f} > 0.60 vs cycle-6 {mid}"] if x)
        if n_te is None or n_te < 36:
            cand["qa_status"] = "FAIL"
            cand["qa_reasons"] = "; ".join(x for x in [cand["qa_reasons"], f"(a) overlap with cycle-6 {mid} {n_te} < 36 months: unassessable"] if x)
        cand["notes"] += f"; level check vs cycle-6 series {lv}"
        cand["_ext"] = True
        if df is not None:
            deep_rows.append(df)
        deep_cands.append(cand)
    for mid in ["FI_US_10Y", "FI_JP_10Y", "FI_SE_10Y", "FI_FR_10Y", "FI_IT_10Y", "FI_ES_10Y", "FI_NO_10Y", "FI_NZ_10Y"]:
        if c6_first[mid] > DEEP_CUT:
            continue
        g = c6b[c6b.market_id == mid].copy()
        deep_rows.append(g)
        r = c6c[c6c.market_id == mid].iloc[0]
        deep_cands.append({"class": "FI", "market_id": mid, "economic_market": r.economic_market,
                           "construction": r.construction, "source": f"cycle-6 bytes {r.source}",
                           "first_date": r.first_date, "last_date": r.last_date, "n_months": r.n_months,
                           "qa_status": "PASS", "qa_reasons": "", "tenor": 10.0,
                           "notes": "cycle-6 PASS row, bytes of data/cycle6/rates/bond_excess_daily.parquet; " + r.notes})
    db = pd.concat(deep_rows, ignore_index=True)
    db = db[db.date <= DEEP_CUT]
    for c in deep_cands:  # FI-DEEP window: extension rows usable only before the cycle-6 first date and <= DEEP_CUT
        if c.get("_ext") and c["qa_status"] == "PASS":
            lim = min(DEEP_CUT, c6_first[c["market_id"]] - pd.Timedelta(days=1))
            sub = db[(db.market_id == c["market_id"]) & (db.date <= lim)].dropna(subset=["excess_ret"])
            c["last_date"] = str(sub.date.max().date()) if len(sub) else ""
            c["n_months"] = int(sub.date.dt.to_period("M").nunique())
            if sub.empty:
                c["qa_status"], c["qa_reasons"] = "FAIL", "no rows before 1993-06"
        elif c["qa_status"] == "PASS":
            sub = db[(db.market_id == c["market_id"])].dropna(subset=["excess_ret"])
            c["last_date"] = str(min(pd.Timestamp(c["last_date"]), sub.date.max()).date())
    evd = OUT / "eval_deep"
    (evd / "panels").mkdir(parents=True, exist_ok=True)
    db.to_parquet(evd / "bond_excess_daily_full.parquet", index=False)
    cld = to_candidate_list(deep_cands, "data/cycle7/fi/eval_deep/candidates_all.csv",
                            "FI-DEEP: cycle-6 FI 10y market history before 1993-04 (+ warm-up, holding to 1993-05)")
    all_cands_frame(deep_cands).to_csv(evd / "candidates_all.csv", index=False)
    cld.to_csv(evd / "candidate_list.csv", index=False)
    pdp = panel(db, pd.DataFrame(deep_cands))
    pdp.to_parquet(evd / "panels" / "daily_excess_FI10.parquet", index=False)
    feas_deep = tsmom_counts(pdp, lambda idx: idx < pd.Period(DEEP_FIRST_MONTH_EXCL, "M"))
    write_json(evd / "completeness.json", {
        "written_utc": utc_now().isoformat(), "sample": "FI-DEEP",
        "scope": "cycle-6 FI 10y markets, months before 1993-04; panel holds history through 1993-05-31 (holding "
                 "period of the 1993-03 signal) including the 756-obs warm-up",
        "extensions": {k: v[3] for k, v in DEEP_EXT.items()}, "level_checks": level_checks,
        "infeasible_monthly_or_nondaily": MONTHLY_INFEASIBLE,
        "candidates": {c["market_id"]: {"qa_status": c["qa_status"], "qa_reasons": c.get("qa_reasons", ""),
                                        "first_date": c.get("first_date", ""), "last_date": c.get("last_date", ""),
                                        "source": c.get("source")} for c in deep_cands},
        "qa_detail": {c["market_id"]: {k: c.get(k) for k in ("_te", "_n_te", "_rho", "_gaps", "_flat", "_start")}
                      for c in deep_cands if "_gaps" in c},
        "short_rates": {k: v for k, v in rec["short_rates"].items() if k.startswith("DEEP")},
        "panel_rows": len(pdp), "panel_sha256": sha_file(evd / "panels" / "daily_excess_FI10.parquet"),
        "feasibility_tsmom_months_before_1993-04": {k: v for k, v in feas_deep.items() if k != "eligible_by_month"},
        "not_frozen": "no snapshot frozen (instruction)"})
    write_json(META / "build_record.json", {**rec, "feasibility": {"FI-NEW": feas_new, "FI-DEEP": feas_deep}})
    pd.set_option("display.width", 250)
    for nm, cc in (("FI-NEW", cands), ("FI-DEEP", deep_cands)):
        print(f"== {nm}")
        print(all_cands_frame(cc)[["market_id", "source", "first_date", "last_date", "n_months", "qa_status",
                                    "qa_reasons"]].to_string())
    print("FI-NEW", {k: v for k, v in feas_new.items() if k != "eligible_by_month"})
    print("FI-DEEP", {k: v for k, v in feas_deep.items() if k != "eligible_by_month"})


if __name__ == "__main__":
    main()
