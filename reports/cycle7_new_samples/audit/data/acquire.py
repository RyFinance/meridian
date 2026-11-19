"""cycle7 hostile-audit DATA acquisition. Raw bytes -> raw/, parsed -> *.parquet/csv, manifest.json.
No strategy returns computed. Run: python3 acquire.py"""
import hashlib, json, subprocess, datetime as dt, pathlib, io
import pandas as pd
D = pathlib.Path(__file__).resolve().parent; R = D / "raw"; R.mkdir(exist_ok=True)
MAN = D / "manifest.json"
man = json.loads(MAN.read_text()) if MAN.exists() else {}
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"

def get(url, fn):
    p = R / fn
    r = subprocess.run(["curl", "-sSL", "-m", "90", "-A", UA, "-o", str(p), "-w", "%{http_code}", url], capture_output=True, text=True)
    code = r.stdout.strip()
    rec = {"url": url, "raw_file": f"raw/{fn}", "retrieved_utc": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), "http": code, "err": r.stderr.strip()[:300]}
    if p.exists():
        b = p.read_bytes(); rec["sha256"] = hashlib.sha256(b).hexdigest(); rec["bytes"] = len(b)
    return p, rec

def note(key, rec, df=None, datecol=None, out=None, **extra):
    if df is not None and len(df):
        idx = df.index if datecol is None else df[datecol]
        rec.update(rows=int(len(df)), first=str(pd.Timestamp(idx.min()).date()), last=str(pd.Timestamp(idx.max()).date()))
        if out:
            df.to_parquet(D / f"{out}.parquet"); df.to_csv(D / f"{out}.csv"); rec["parsed"] = [f"{out}.parquet", f"{out}.csv"]
    rec.update(extra); man[key] = rec; print(key, {k: rec.get(k) for k in ("http", "rows", "first", "last")})

# 1 LRV currency portfolios (Verdelhan)
p, rec = get("https://web.mit.edu/adrienv/www/CurrencyPortfolios.xls", "verdelhan_CurrencyPortfolios.xls")
hdr = subprocess.run(["curl", "-sSI", "-m", "30", "https://web.mit.edu/adrienv/www/CurrencyPortfolios.xls"], capture_output=True, text=True).stdout
lm = [l.split(":", 1)[1].strip() for l in hdr.splitlines() if l.lower().startswith("last-modified")]
out = {}
for sheet, tag in [("All currencies", "all"), ("Developed currencies", "dev"), ("All currencies (net)", "all_net"), ("Developed currencies (net)", "dev_net")]:
    d = pd.read_excel(p, sheet, header=0)
    d = d.rename(columns={d.columns[0]: "date"}).dropna(subset=["date"])
    d["date"] = pd.to_datetime(d["date"]) + pd.offsets.MonthEnd(0)
    rx = [c for c in d.columns if str(c).startswith("RX")][0]; hml = [c for c in d.columns if str(c).startswith("HML")][0]
    ports = [c for c in d.columns if str(c).startswith("Portfolio")]
    for c in ports: out[f"{tag}_{c}"] = d.set_index("date")[c].astype(float)
    out[f"{tag}_RX_DOL"] = d.set_index("date")[rx].astype(float); out[f"{tag}_HML_FX"] = d.set_index("date")[hml].astype(float)
lrv = pd.DataFrame(out); lrv.index.name = "date"
note("lrv_currency_factors", rec, lrv, out="lrv_currency_factors", file_last_modified=lm,
     notes="LRV (RFS 2011) portfolios, simple (level) excess returns; gross and net-of-bid-ask; all = 6 portfolios (HML=P6-P1), developed = 5 (HML=P5-P1). Page says 'Updated monthly' but file stops 2021-05.")
p2, rec2 = get("https://web.mit.edu/adrienv/www/Data_for_AugmentedUIP_allcountries.xls", "verdelhan_Data_for_AugmentedUIP_allcountries.xls")
fac = {}
for s in ["Carry Factors", "Dollar Factors"]:
    d = pd.read_excel(p2, s, header=0); d = d.rename(columns={d.columns[0]: "date"}).dropna(subset=["date"]).set_index("date")
    d.index = pd.to_datetime(d.index) + pd.offsets.MonthEnd(0)
    fac[s] = d
pd.concat(fac, axis=1).to_parquet(D / "verdelhan_2018_country_factors.parquet")
note("verdelhan_share_systematic_country_factors", rec2, fac["Dollar Factors"], out=None,
     parsed=["verdelhan_2018_country_factors.parquet"], notes="Verdelhan (JF 2018) country-specific carry & dollar factors (excl. own currency); file last-modified 2020-05-26, ends 2020-04")

# 2 Fed H.10 dollar indexes (daily + monthly packages)
for h, tag in [("122e3bcb627e8e53f1bf72a1a09cfb81", "daily"), ("847be2166a425bda9b4d92465f797544", "monthly")]:
    url = f"https://www.federalreserve.gov/datadownload/Output.aspx?rel=H10&series={h}&lastobs=&from=&to=&filetype=csv&label=include&layout=seriescolumn&type=package"
    p, rec = get(url, f"fed_h10_dollar_index_{tag}.csv")
    raw = pd.read_csv(p, skiprows=5, na_values=["ND", "NA"])
    raw = raw.rename(columns={raw.columns[0]: "date"}); raw["date"] = pd.to_datetime(raw["date"]); raw = raw.set_index("date").astype(float)
    raw.columns = [{"JRXWTFB_N.B": "broad", "JRXWTFN_N.B": "afe", "JRXWTFO_N.B": "eme", "JRXWTFB_N.M": "broad", "JRXWTFN_N.M": "afe", "JRXWTFO_N.M": "eme"}.get(c, c) for c in raw.columns]
    if tag == "daily":
        m = raw.dropna(how="all").resample("ME").last(); m.index.name = "date"
        note("fed_h10_dollar_index_daily", rec, raw.dropna(how="all"), out="fed_h10_dollar_index_daily")
        man["fed_h10_dollar_index_monthly_from_daily"] = {"derived_from": "fed_h10_dollar_index_daily", "method": "last available daily obs in calendar month", "rows": len(m), "first": str(m.index.min().date()), "last": str(m.index.max().date()), "parsed": ["fed_h10_dollar_index_monthly_eom.parquet", "fed_h10_dollar_index_monthly_eom.csv"]}
        m.to_parquet(D / "fed_h10_dollar_index_monthly_eom.parquet"); m.to_csv(D / "fed_h10_dollar_index_monthly_eom.csv")
    else:
        raw.index = raw.index + pd.offsets.MonthEnd(0)
        note("fed_h10_dollar_index_monthly_avg", rec, raw.dropna(how="all"), out="fed_h10_dollar_index_monthly_avg", notes="Fed official monthly averages")

# Yahoo daily -> month-end
def yahoo(sym, key):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1=0&period2=9999999999&interval=1d&events=div%2Csplit&includeAdjustedClose=true"
    safe = sym.replace("^", "").replace("=", "_")
    p, rec = get(url, f"yahoo_{safe}_daily.json")
    try:
        j = json.loads(p.read_bytes())["chart"]["result"][0]
    except Exception as e:
        note(key, rec, None, status="FAILED", error=str(e)[:200]); return
    ts = pd.to_datetime(j["timestamp"], unit="s").normalize()
    q = j["indicators"]["quote"][0]
    d = pd.DataFrame({"close": q["close"], "volume": q.get("volume")}, index=ts)
    if "adjclose" in j["indicators"]: d["adjclose"] = j["indicators"]["adjclose"][0]["adjclose"]
    d.index.name = "date"; d = d[~d.index.duplicated(keep="last")].dropna(subset=["close"])
    divs = pd.DataFrame([(pd.to_datetime(int(k), unit="s").date(), v["amount"]) for k, v in j.get("events", {}).get("dividends", {}).items()], columns=["exdate", "amount"]).sort_values("exdate") if j.get("events", {}).get("dividends") else pd.DataFrame(columns=["exdate", "amount"])
    d.to_parquet(D / f"yahoo_{safe}_daily.parquet")
    m = d.resample("ME").last(); m.index.name = "date"
    divs.to_csv(D / f"yahoo_{safe}_distributions.csv", index=False)
    meta = j["meta"]
    note(key, rec, m, out=f"yahoo_{safe}_monthly", daily_rows=len(d), daily_first=str(d.index.min().date()), daily_last=str(d.index.max().date()),
         first_trade_date=str(pd.to_datetime(meta.get("firstTradeDate", 0), unit="s").date()) if meta.get("firstTradeDate") else None,
         n_distributions=len(divs), distributions_ttm=float(divs[pd.to_datetime(divs.exdate) > d.index.max() - pd.Timedelta(days=365)].amount.sum()) if len(divs) else None,
         notes="Yahoo v8 chart; monthly = last daily obs in month; adjclose = Yahoo split+dividend adjusted (total-return proxy)")

for sym, key in [("DX-Y.NYB", "yahoo_dxy"), ("EEM", "yahoo_eem"), ("^VIX", "yahoo_vix"), ("HYG", "yahoo_hyg"), ("CEW", "yahoo_cew"),
                 ("EMLC", "yahoo_emlc"), ("LEMB", "yahoo_lemb"), ("EBND", "yahoo_ebnd"), ("JNK", "yahoo_jnk")]:
    yahoo(sym, key)

# 4 Cboe VIX
p, rec = get("https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv", "cboe_VIX_History.csv")
try:
    v = pd.read_csv(p); v["DATE"] = pd.to_datetime(v["DATE"]); v = v.set_index("DATE"); v.index.name = "date"
    vm = v.resample("ME").last()
    note("cboe_vix", rec, vm, out="cboe_vix_monthly_eom", daily_rows=len(v), daily_first=str(v.index.min().date()), daily_last=str(v.index.max().date()))
except Exception as e:
    note("cboe_vix", rec, None, status="FAILED", error=str(e)[:200])

MAN.write_text(json.dumps(man, indent=1, default=str))
