"""Full-chain pilot: CIK -> ticker history -> listing/delisting dates -> free price series -> validation.

For each pilot security (research/survivor_equity_pilot/pilot_universe.py) every link is attempted
against every free source, and the first failing link is recorded per source. NO returns and no
signal->return relation are computed: price series are used only for presence, date coverage,
identity (last close vs. announced cash deal price) and volume cross-checks against FINRA.

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.survivor_equity_pilot.chain
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from research.survivor_equity_pilot.common import DATA_DIR, REPORT_DIR, ROOT, cached_json, fetch
from research.survivor_equity_pilot.pilot_universe import rows

FINRA_DIR = ROOT / "data" / "c4" / "finra_regsho"
DELIST_FORMS = ("25", "25-NSE", "25/A", "25-NSE/A")
DEREG_FORMS = ("15-12B", "15-12G", "15-15D", "15-12B/A", "15-12G/A", "15-15D/A", "15F-12B", "15F-12G")

# Announced per-share all-cash consideration (general knowledge) -> identity check for acquired names.
CASH_DEAL_PRICE = {"TWITTER": 54.20, "LINKEDIN": 196.00, "WHOLEFOODS": 42.00, "MONSANTO": 128.00,
                   "REDHAT": 190.00, "TIFFANY": 131.50, "ACTIVISION": 95.00, "HEINZ": 72.50,
                   "DELL_OLD": 13.75, "GENENTECH": 95.00, "MOTOMOBILITY": 40.00, "SUNMICRO": 9.50,
                   "ANHEUSER": 70.00, "WYETH": None, "BNSF": 100.00}
# A few well-documented closing prices (general knowledge, flagged as memory-based) for identity checks
# of non-cash-deal names. Tolerance 3%.
KNOWN_CLOSE = {"FIRSTREPUBLIC": ("2023-04-28", 3.51), "AMR": ("2011-11-28", 1.62),
               "SVB": ("2023-03-09", 106.04), "BBBY": ("2023-04-21", 0.2935)}


_STOP = {"INC", "CORP", "CO", "THE", "CORPORATION", "COMPANY", "LTD", "HOLDINGS", "HOLDING", "DE", "NEW"}


def norm(s: str) -> str:
    words = re.sub(r"[^A-Z0-9 ]", " ", (s or "").upper()).split()
    return " ".join(w for w in words if w not in _STOP)


def name_match(q: str, names: list[str]) -> bool:
    qn = set(norm(q).split())
    for n in names:
        nn = set(norm(n).split())
        if qn and len(qn & nn) >= max(1, int(0.75 * len(qn) + 0.5)):
            return True
    return False


# ------------------------------------------------------------------------------------------ SEC
def submissions(cik: int) -> tuple[int, dict | None]:
    return cached_json(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", "sec_submissions")


def all_filings(sub: dict) -> pd.DataFrame:
    frames = [pd.DataFrame(sub["filings"]["recent"])]
    for f in sub["filings"].get("files", []):
        st, older = cached_json(f"https://data.sec.gov/submissions/{f['name']}", "sec_submissions")
        if st == 200 and older:
            frames.append(pd.DataFrame(older))
    df = pd.concat(frames, ignore_index=True)
    if "items" not in df:
        df["items"] = ""
    df["items"] = df["items"].fillna("")
    return df


def efts_autocomplete(q: str) -> list[tuple[int, str]]:
    st, d = cached_json("https://efts.sec.gov/LATEST/search-index?keysTyped=" + q.replace(" ", "%20"),
                        "sec_efts")
    if st != 200 or not d:
        return []
    return [(int(h["_id"]), h["_source"]["entity"]) for h in d["hits"]["hits"]]


def efts_tickers(cik: int) -> dict:
    """EDGAR full-text-search index: display_names carry the ticker(s) EDGAR currently associates
    with the CIK, even for dead issuers (e.g. SIVBQ). Also gives Form 25 / 15 hits with dates."""
    url = (f"https://efts.sec.gov/LATEST/search-index?forms=25-NSE,25,15-12B,15-12G,15-15D"
           f"&ciks={cik:010d}&dateRange=custom&startdt=2001-01-01&enddt=2026-09-25")
    st, d = cached_json(url, "sec_efts", f"forms25_15_{cik}.json")
    out = {"status": st, "tickers": set(), "hits": []}
    if st == 200 and d:
        for h in d["hits"]["hits"]:
            s = h["_source"]
            for dn in s.get("display_names", []):
                if f"CIK {cik:010d}" in dn:
                    m = re.search(r"\(([A-Z0-9.,\- ]+)\)\s+\(CIK", dn)
                    if m:
                        out["tickers"].update(t.strip() for t in m.group(1).split(","))
            out["hits"].append({"form": s.get("form"), "file_date": s.get("file_date"),
                                "filer_names": s.get("display_names")})
    out["tickers"] = sorted(out["tickers"])
    return out


def efts_fulltext_ciks(q: str) -> list[int]:
    """Fallback for renamed dead issuers (autocomplete indexes current names only, e.g. A123 -> B456)."""
    url = ("https://efts.sec.gov/LATEST/search-index?q=%22" + q.replace(" ", "%20") +
           "%22&forms=10-K,10-Q&dateRange=custom&startdt=2001-01-01&enddt=2026-09-25")
    st, d = cached_json(url, "sec_efts", "fts_" + re.sub(r"[^A-Za-z0-9]", "_", q) + ".json")
    if st != 200 or not d:
        return []
    ciks: list[int] = []
    for h in d["hits"]["hits"]:
        for c in h["_source"].get("ciks", []):
            if int(c) not in ciks:
                ciks.append(int(c))
    return ciks


def _window_ok(sub: dict, ev: pd.Timestamp) -> tuple[bool, dict]:
    """The CIK must have been an active filer (periodic reports) in the year before the event."""
    f = all_filings(sub)
    per = f[f["form"].isin(["10-K", "10-Q", "10-K405", "10-KSB", "10-QSB", "N-CSR", "N-CSRS", "N-Q",
                            "NPORT-P", "20-F", "40-F"])]
    if per.empty:
        return False, {"n_periodic": 0}
    d = pd.to_datetime(per["filingDate"])
    ok = (d.min() <= ev - pd.Timedelta(days=365)) and (d.max() >= ev - pd.Timedelta(days=400))
    return bool(ok), {"n_periodic": len(per), "first_periodic": str(d.min().date()),
                      "last_periodic": str(d.max().date())}


def resolve_cik(r: dict) -> dict:
    tried = []
    ev = pd.Timestamp(r["event_date"])
    cands: list[tuple[int, str]] = []
    if r["cik_guess"]:
        cands.append((r["cik_guess"], "guess"))
    cands += [(c, "efts_autocomplete") for c, ent in efts_autocomplete(r["name_q"])[:8]
              if name_match(r["name_q"], [ent])]
    fts_done = False
    i = 0
    while True:
        if i >= len(cands):
            if fts_done:
                break
            fts_done = True
            cands += [(c, "efts_fulltext") for c in efts_fulltext_ciks(r["name_q"])[:10]
                      if c not in [x[0] for x in cands]]
            if i >= len(cands):
                break
        cik, how = cands[i]
        i += 1
        st, sub = submissions(cik)
        if not sub:
            tried.append({"cik": cik, "via": how, "status": st})
            continue
        names = [sub["name"]] + [f["name"] for f in sub.get("formerNames", [])]
        nm = name_match(r["name_q"], names)
        wok, winfo = _window_ok(sub, ev) if nm else (False, {})
        tried.append({"cik": cik, "via": how, "status": st, "names": names[:4], "name_ok": nm,
                      "window_ok": wok, **winfo})
        if nm and wok:
            return {"cik": cik, "method": how + "_verified", "sub": sub, "tried": tried}
    return {"cik": None, "method": "unresolved", "sub": None, "tried": tried}


# ------------------------------------------------------------------------------------- tickers
def ticker_sources(cik: int, r: dict, ct: pd.DataFrame, sd: pd.DataFrame, ti: pd.DataFrame,
                   sub: dict | None) -> dict:
    out = {}
    out["sec_submissions_current"] = sorted(sub.get("tickers", [])) if sub else []
    e = efts_tickers(cik)
    out["efts_display_names"] = e["tickers"]
    snap = ct[ct["cik"] == cik].groupby("ticker")["snapshot"].agg(["min", "max"]).reset_index()
    out["wayback_company_tickers"] = snap.to_dict("records")
    # symbol directories carry no CIK: match by name, restricted to common stock-like lines
    names = [r["name_q"]] + ([sub["name"]] + [f["name"] for f in sub.get("formerNames", [])] if sub else [])
    # search ALL symbols by name (no prior ticker knowledge); keep common-stock-looking lines only
    first = norm(names[0]).split()[:1]
    cand = sd[sd["name"].str.upper().str.contains(first[0], regex=False)] if first else sd.iloc[:0]
    cand = cand[~cand["name"].str.contains(r"Warrant|Preferred|Notes|Depositary|Unit|Right|Debenture|%",
                                           case=False, regex=True)]
    hits = cand[[any(name_match(x, [n]) for x in names) for n in cand["name"]]] if len(cand) else cand
    out["wayback_symdir"] = ([] if hits.empty else hits.groupby("symbol").agg(
        first_snap=("snapshot", "min"), last_snap=("snapshot", "max"), name=("name", "first"))
        .reset_index().to_dict("records"))
    tt = ti[ti["ticker"].str.upper().isin([r["ticker"].lower().upper(), (r.get("successor") or "__")])]
    out["tiingo_supported"] = tt.to_dict("records")
    derived = set(out["sec_submissions_current"]) | set(out["efts_display_names"]) | \
        {x["ticker"] for x in out["wayback_company_tickers"]} | {x["symbol"] for x in out["wayback_symdir"]}
    out["derived_without_prior"] = sorted(derived)
    out["expected_ticker_recovered"] = r["ticker"] in derived
    out["efts_forms25_15"] = e["hits"]
    return out


# ------------------------------------------------------------------------------------- dates
def delisting_dates(f: pd.DataFrame) -> dict:
    f = f.copy()
    f["filingDate"] = pd.to_datetime(f["filingDate"])
    d25 = f[f["form"].isin(DELIST_FORMS)].sort_values("filingDate")
    d15 = f[f["form"].isin(DEREG_FORMS)].sort_values("filingDate")
    k301 = f[(f["form"].str.startswith("8-K")) & f["items"].str.contains(r"3\.01")].sort_values("filingDate")
    k103 = f[(f["form"].str.startswith("8-K")) & f["items"].str.contains(r"1\.03")].sort_values("filingDate")
    k201 = f[(f["form"].str.startswith("8-K")) & f["items"].str.contains(r"2\.01")].sort_values("filingDate")
    k503 = f[(f["form"].str.startswith("8-K")) & f["items"].str.contains(r"5\.03")].sort_values("filingDate")
    s = lambda x: [d.strftime("%Y-%m-%d") for d in x["filingDate"]]  # noqa: E731
    per = f[f["form"].isin(["10-K", "10-Q", "10-K405", "10-KSB", "10-QSB"])]
    return {"form25": s(d25), "form15": s(d15), "8k_3.01": s(k301), "8k_1.03": s(k103),
            "8k_2.01": s(k201)[-3:], "8k_5.03": s(k503)[-3:],
            "first_filing": f["filingDate"].min().strftime("%Y-%m-%d"),
            "last_filing": f["filingDate"].max().strftime("%Y-%m-%d"),
            "last_periodic": per["filingDate"].max().strftime("%Y-%m-%d") if len(per) else None,
            "n_filings": len(f), "items_populated": bool((f["items"] != "").any())}


_finra_cache: dict[str, pd.DataFrame] = {}


def finra_presence(tickers: list[str]) -> dict:
    """First/last day each symbol appears in the local FINRA CNMS Reg SHO daily files."""
    if "all" not in _finra_cache:
        files = sorted(FINRA_DIR.glob("CNMSshvol*.txt"))
        parts = []
        want = set(tickers)
        for p in files:
            try:
                df = pd.read_csv(p, sep="|", dtype={"Symbol": str}, usecols=["Date", "Symbol", "TotalVolume"])
            except Exception:  # noqa: BLE001
                continue
            parts.append(df)
        allf = pd.concat(parts, ignore_index=True)
        allf = allf[allf["Date"].astype(str).str.fullmatch(r"\d{8}")]
        allf["Date"] = pd.to_datetime(allf["Date"].astype(str))
        _finra_cache["all"] = allf
        _finra_cache["days"] = allf["Date"].drop_duplicates().sort_values()
        _ = want
    a = _finra_cache["all"]
    out = {}
    for t in tickers:
        x = a[a["Symbol"] == t]
        out[t] = None if x.empty else {"first": x["Date"].min().strftime("%Y-%m-%d"),
                                       "last": x["Date"].max().strftime("%Y-%m-%d"), "n_days": len(x)}
    return out


def finra_series(t: str) -> pd.Series:
    a = _finra_cache["all"]
    x = a[a["Symbol"] == t]
    return x.groupby("Date")["TotalVolume"].sum()


# ------------------------------------------------------------------------------------- prices
def yahoo_chart(sym: str, p1: int = 0, p2: int | None = None, host: str = "query1") -> dict:
    p2 = p2 or int(datetime(2026, 9, 25, tzinfo=timezone.utc).timestamp())
    url = (f"https://{host}.finance.yahoo.com/v8/finance/chart/{sym}?period1={p1}&period2={p2}"
           f"&interval=1d&events=div%2Csplit&includeAdjustedClose=true")
    st, d = cached_json(url, "yahoo_chart", f"{sym}_{p1}_{p2}_{host}.json")
    res = {"symbol": sym, "http": st, "url": url}
    try:
        r = d["chart"]["result"][0]
    except (TypeError, KeyError, IndexError):
        res["error"] = (d or {}).get("chart", {}).get("error") if isinstance(d, dict) else None
        res["n"] = 0
        return res
    ts = r.get("timestamp") or []
    q = r["indicators"]["quote"][0]
    df = pd.DataFrame({"date": pd.to_datetime(ts, unit="s").normalize(), "close": q.get("close"),
                       "volume": q.get("volume")}).dropna(subset=["close"])
    meta = r.get("meta", {})
    res.update({"n": len(df), "first": df["date"].min().strftime("%Y-%m-%d") if len(df) else None,
                "last": df["date"].max().strftime("%Y-%m-%d") if len(df) else None,
                "exchange": meta.get("fullExchangeName"), "firstTradeDate":
                datetime.fromtimestamp(meta["firstTradeDate"], timezone.utc).strftime("%Y-%m-%d")
                if meta.get("firstTradeDate") else None, "instrumentType": meta.get("instrumentType"),
                "longName": meta.get("longName"), "_df": df})
    return res


def classify_series(y: dict, ev: pd.Timestamp) -> str:
    if not y.get("n"):
        return "NOT_FOUND"
    df = y["_df"]
    pre = df[(df["date"] <= ev) & (df["date"] >= ev - pd.Timedelta(days=365))]
    if pd.Timestamp(y["first"]) > ev + pd.Timedelta(days=5):
        return "RECYCLED_OR_POST_EVENT_ONLY"
    if len(pre) >= 200:
        return "GENUINE_PRE_EVENT_1Y"
    if len(pre) > 0:
        return "PARTIAL_PRE_EVENT"
    return "NO_PRE_EVENT_OVERLAP"


def validate(r: dict, y: dict, ev: pd.Timestamp, finra: dict, sec_names: list[str],
             tiingo_win: tuple | None) -> dict:
    df = y["_df"]
    v = {}
    last = pd.Timestamp(y["last"])
    if r["event_type"] in ("acquired", "liquidation"):
        v["last_date_minus_event_days"] = int((last - ev).days)
        v["last_date_ok"] = -4 <= (last - ev).days <= 1
        px = CASH_DEAL_PRICE.get(r["key"])
        if px:
            lc = float(df.iloc[-1]["close"])
            v["last_close"], v["deal_price"] = round(lc, 4), px
            v["last_close_within_2pct_of_cash_deal"] = abs(lc / px - 1) <= 0.02
    else:
        v["series_continues_after_event_days"] = int((last - ev).days)
    v["yahoo_longname"] = y.get("longName")
    v["longname_matches_sec"] = name_match(r["name_q"], [y.get("longName") or ""]) or \
        any(name_match(n, [y.get("longName") or ""]) for n in sec_names)
    kf = KNOWN_CLOSE.get(r["key"])
    if kf:
        row = df[df["date"] == pd.Timestamp(kf[0])]
        v["known_close"] = {"date": kf[0], "expected": kf[1],
                            "yahoo": round(float(row["close"].iloc[0]), 4) if len(row) else None}
        v["known_close_ok"] = bool(len(row)) and abs(float(row["close"].iloc[0]) / kf[1] - 1) <= 0.03
    if tiingo_win is not None:
        v["tiingo_window"] = tiingo_win
        v["yahoo_first_vs_tiingo_start_days"] = int((pd.Timestamp(y["first"]) - pd.Timestamp(tiingo_win[0])).days)
    t = r["ticker"]
    if finra.get(t):
        fr = finra_series(t)
        yy = df.set_index("date")["volume"]
        j = pd.concat([yy, fr], axis=1, join="inner").dropna()
        j = j[j.index <= ev + pd.Timedelta(days=3)]
        if len(j) >= 20:
            v["finra_overlap_days"] = len(j)
            v["finra_volume_spearman"] = round(float(j.rank().corr().iloc[0, 1]), 3)
        v["finra_last_cnms_day"] = finra[t]["last"]
    return v


# ------------------------------------------------------------------------------------- driver
def main() -> None:
    ct = pd.read_parquet(DATA_DIR / "company_tickers_history.parquet")
    sd = pd.read_parquet(DATA_DIR / "symdir_history.parquet")
    from research.survivor_equity_pilot.sources import load_tiingo
    ti = load_tiingo()
    ti["ticker"] = ti["ticker"].str.upper()
    universe = rows()
    finra = finra_presence(sorted({r["ticker"] for r in universe} | {r["successor"] for r in universe if r["successor"]}))
    results, series_summ = [], []
    for r in universe:
        ev = pd.Timestamp(r["event_date"])
        rec = {k: r[k] for k in ("key", "name_q", "exchange", "ticker", "event_type", "event_date", "successor")}
        c = resolve_cik(r)
        rec["cik"], rec["cik_method"], rec["cik_tried"] = c["cik"], c["method"], c["tried"]
        sub = c["sub"]
        if c["cik"]:
            rec["sec_name"] = sub["name"]
            rec["former_names"] = sub.get("formerNames", [])
            f = all_filings(sub)
            rec["dates"] = delisting_dates(f)
            rec["tickers"] = ticker_sources(c["cik"], r, ct, sd, ti, sub)
        else:
            rec["dates"], rec["tickers"] = None, None
        rec["finra_cnms"] = {t: finra.get(t) for t in [r["ticker"], r["successor"]] if t}
        # prices: original ticker, known successor, and any EDGAR-derived ticker
        syms = [r["ticker"]] + ([r["successor"]] if r["successor"] else [])
        if rec["tickers"]:
            syms += [s for s in rec["tickers"]["efts_display_names"] if s not in syms]
        yres = []
        for s in syms:
            y = yahoo_chart(s)
            y["class"] = classify_series(y, ev)
            if y.get("n") and y["class"] in ("GENUINE_PRE_EVENT_1Y", "PARTIAL_PRE_EVENT"):
                sec_names = [rec.get("sec_name") or ""] + [f["name"] for f in rec.get("former_names") or []]
                tw = None
                if rec["tickers"]:
                    stk = [x for x in rec["tickers"]["tiingo_supported"]
                           if x["assetType"] == "Stock" and pd.Timestamp(x["endDate"]) <= ev + pd.Timedelta(days=900)
                           and pd.Timestamp(x["startDate"]) <= ev]
                    if stk:
                        tw = (min(x["startDate"] for x in stk), max(x["endDate"] for x in stk))
                y["validation"] = validate(r, y, ev, finra, sec_names, tw)
                val = y["validation"]
                y["identity"] = ("CONFIRMED" if (val.get("known_close_ok") or val.get("last_close_within_2pct_of_cash_deal")
                                                 or (val.get("finra_volume_spearman") or 0) >= 0.6)
                                 else "REJECTED" if (not val["longname_matches_sec"] or val.get("known_close_ok") is False
                                                     or val.get("last_close_within_2pct_of_cash_deal") is False
                                                     or (val.get("finra_volume_spearman") is not None and val["finra_volume_spearman"] < 0.3)
                                                     or abs(val.get("yahoo_first_vs_tiingo_start_days") or 0) > 400)
                                 else "UNVERIFIED")
                # store the validated series (date, close, volume only) for coverage audit
                y["_df"].to_csv(DATA_DIR / "yahoo_chart" / f"series_{r['key']}_{s}.csv", index=False)
            y.pop("_df", None)
            yres.append(y)
            series_summ.append({"key": r["key"], "symbol": s, "class": y["class"], "identity": y.get("identity"),
                                "n": y.get("n"),
                                "first": y.get("first"), "last": y.get("last"), "exchange": y.get("exchange")})
        rec["yahoo"] = yres
        results.append(rec)
        print(r["key"], rec["cik"], rec["cik_method"], [(y["symbol"], y["class"], y.get("identity")) for y in yres])
    (REPORT_DIR / "pilot_chain_detail.json").write_text(json.dumps(results, indent=1, default=str))
    pd.DataFrame(series_summ).to_csv(REPORT_DIR / "pilot_yahoo_series.csv", index=False)


if __name__ == "__main__":
    main()
