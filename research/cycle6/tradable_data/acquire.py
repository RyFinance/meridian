"""Cycle-6 TRADABLE-VARIANTS data pass (phase 1): acquire free daily prices for the mapped vehicles, USD/CAD and
sizing-only futures price levels; copy the frozen BOOK/component/eval inputs the variants consume; write
data/cycle6/trade/ (long-format parquet: date, market_id, value), completeness.json and the snapshot spec.

Sources (free, no key, no login): Yahoo Finance via yfinance (history(period="max", auto_adjust=False,
actions=True)); FRED fredgraph.csv DEXCAUS (Fed H.10 noon NY buying rate, CAD per USD). No strategy returns are
computed here. Delisted FXS (SEK, liquidated 2020-05-22) has no free history (Yahoo 404; Stooq behind a JS bot
check, not bypassed; LSE terminal: no candles) and is recorded as unavailable.

    python -m research.cycle6.tradable_data.acquire [--no-download]   # download + build + completeness + spec
"""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import shutil
import time
import urllib.request
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "data" / "cycle6" / "trade"
RAW = OUT / "raw"
INP = OUT / "inputs"
SPEC = REPO / "research" / "cycle6" / "snapshot_spec_cycle6_trade_v1.json"

ETFS = {  # ticker: (listing currency, economic exposure)
    "SPY": ("USD", "US equity (core)"), "IEF": ("USD", "US Treasury 7-10y"),
    "ZFM.TO": ("CAD", "Canada federal bonds 5-10y"),
    "FXE": ("USD", "EUR"), "FXY": ("USD", "JPY"), "FXB": ("USD", "GBP"), "FXA": ("USD", "AUD"),
    "FXC": ("USD", "CAD"), "FXF": ("USD", "CHF"), "FXS": ("USD", "SEK (liquidated 2020-05-22)"),
    "GLD": ("USD", "gold"), "SLV": ("USD", "silver"), "PALL": ("USD", "palladium"), "PPLT": ("USD", "platinum"),
    "USO": ("USD", "WTI"), "UNG": ("USD", "natgas"), "BNO": ("USD", "Brent"), "UGA": ("USD", "gasoline"),
    "CPER": ("USD", "copper"), "CORN": ("USD", "corn"), "SOYB": ("USD", "soybeans"), "WEAT": ("USD", "wheat"),
}
SIZING = {"GC=F": "COMEX gold front (sizing MGC only)", "CL=F": "NYMEX WTI front (sizing MCL only)",
          "NG=F": "NYMEX natgas front (sizing MNG only)", "^GSPC": "S&P 500 index (sizing MES only)"}
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXCAUS"

BOOK_DIR = REPO / "reports" / "cycle6_core_premia" / "book"
COMP_DIR = REPO / "reports" / "cycle6_core_premia" / "components"
EVAL = REPO / "data" / "cycle6" / "eval"
SLEEVES = ["CARRY-FX", "SEAS-FX", "TSMOM-CM", "TSMOM-FI", "VAL-FX", "XSMOM-FX"]
EVAL_COPIES = ["panels/daily_excess_FX.parquet", "panels/daily_excess_CM.parquet", "panels/daily_excess_FI10.parquet",
               "series/core_etf_excess_daily.parquet", "series/core_etf_total_return_daily.parquet",
               "series/tbill_3m_daily.parquet", "signals/fx_spot_monthly.parquet",
               "signals/fx_foreign_rate_monthly.parquet"]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _yahoo(tk: str, tries: int = 3):
    import yfinance as yf
    err = None
    for i in range(tries):
        try:
            h = yf.Ticker(tk).history(period="max", auto_adjust=False, actions=True)
            if h is not None and len(h):
                h.index = pd.DatetimeIndex(h.index).tz_localize(None).normalize()
                return h, None, i + 1
            err = "empty"
        except Exception as exc:  # recorded, retried
            err = f"{type(exc).__name__}: {exc}"
        time.sleep(2)
    return None, err, tries


def _long(frame: pd.DataFrame, col: str, mid: str, nonzero: bool = False) -> pd.DataFrame:
    s = frame[col].dropna()
    if nonzero:
        s = s[s != 0]
    return pd.DataFrame({"date": s.index, "market_id": mid, "value": s.to_numpy(float)})


def download() -> dict:
    RAW.mkdir(parents=True, exist_ok=True)
    rec = {"yahoo": {}, "fred": {}}
    parts = {"adj": [], "close": [], "div": [], "split": [], "size": []}
    for tk in list(ETFS) + list(SIZING):
        t0 = utc_now()
        h, err, n = _yahoo(tk)
        r = {"endpoint": f"yfinance {tk} history(period=max, auto_adjust=False, actions=True)",
             "retrieval_utc": t0, "attempts": n, "ok": h is not None, "error": err}
        if h is not None:
            h = h[~h.index.duplicated(keep="last")].sort_index()
            raw = RAW / f"yahoo_{tk.replace('^', '').replace('=', '_')}.csv"
            h.to_csv(raw)
            r.update({"raw": str(raw.relative_to(REPO)), "raw_sha256": sha(raw), "rows": int(len(h)),
                      "first": str(h.index.min().date()), "last": str(h.index.max().date()),
                      "duplicates_dropped": 0, "n_dividends": int((h.get("Dividends", 0) != 0).sum()),
                      "n_splits": int((h.get("Stock Splits", 0) != 0).sum())})
            if tk in ETFS:
                parts["adj"].append(_long(h, "Adj Close", tk))
                parts["close"].append(_long(h, "Close", tk))
                if "Dividends" in h:
                    parts["div"].append(_long(h, "Dividends", tk, nonzero=True))
                if "Stock Splits" in h:
                    parts["split"].append(_long(h, "Stock Splits", tk, nonzero=True))
            else:
                parts["size"].append(_long(h, "Close", tk))
        rec["yahoo"][tk] = r
    t0 = utc_now()
    req = urllib.request.Request(FRED_URL, headers={"User-Agent": "Mozilla/5.0"})
    body = urllib.request.urlopen(req, timeout=60).read()
    raw = RAW / "fred_DEXCAUS.csv"
    raw.write_bytes(body)
    fx = pd.read_csv(io.BytesIO(body))
    fx.columns = ["date", "value"]
    fx["value"] = pd.to_numeric(fx["value"], errors="coerce")
    n_missing = int(fx["value"].isna().sum())
    fx = fx.dropna()
    fx["date"] = pd.to_datetime(fx["date"])
    fx["market_id"] = "USDCAD"
    rec["fred"]["DEXCAUS"] = {"endpoint": FRED_URL, "retrieval_utc": t0, "ok": True, "raw": str(raw.relative_to(REPO)),
                             "raw_sha256": sha(raw), "rows": int(len(fx)), "holiday_blank_rows_dropped": n_missing,
                             "first": str(fx.date.min().date()), "last": str(fx.date.max().date()),
                             "units": "CAD per 1 USD, noon New York buying rate (H.10)"}
    empty = pd.DataFrame({"date": pd.to_datetime([]), "market_id": [], "value": []})
    out = {k: (pd.concat(v, ignore_index=True) if v else empty) for k, v in parts.items()}
    out["usdcad"] = fx[["date", "market_id", "value"]]
    names = {"adj": "etf_adjclose_daily", "close": "etf_close_daily", "div": "etf_dividends",
             "split": "etf_splits", "size": "futures_sizing_levels_daily", "usdcad": "usdcad_daily"}
    for k, d in out.items():
        d = d.sort_values(["market_id", "date"]).reset_index(drop=True)
        assert not d.duplicated(["date", "market_id"]).any(), k
        d.to_parquet(OUT / f"{names[k]}.parquet", index=False)
    (OUT / "meta").mkdir(exist_ok=True)
    (OUT / "meta" / "acquire_record.json").write_text(json.dumps(rec, indent=1, sort_keys=True))
    return rec


def copy_inputs() -> dict:
    """Byte copies of the frozen BOOK / component / eval files the variants consume (hash-checked)."""
    if INP.exists():
        shutil.rmtree(INP)
    rec = {}
    pairs = [(BOOK_DIR / f, INP / "book" / f) for f in ("weights.csv", "book.csv", "sleeves.csv", "metrics.json")]
    for c in SLEEVES:
        pairs += [(COMP_DIR / c / f, INP / "components" / c / f) for f in ("weights.parquet", "net.csv", "metrics.json")]
    pairs += [(EVAL / f, INP / "eval" / f) for f in EVAL_COPIES]
    for src, dst in pairs:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        assert sha(src) == sha(dst)
        rec[str(dst.relative_to(OUT))] = {"source": str(src.relative_to(REPO)), "sha256": sha(dst)}
    (OUT / "meta" / "inputs_copied.json").write_text(json.dumps(rec, indent=1, sort_keys=True))
    return rec


def vehicle_universe(rec: dict) -> pd.DataFrame:
    rows = []
    for tk, (ccy, expo) in ETFS.items():
        r = rec["yahoo"][tk]
        rows.append({"vehicle": tk, "kind": "ETF", "listing_ccy": ccy, "exposure": expo,
                     "data_status": "OK" if r["ok"] else "UNAVAILABLE",
                     "first_date": r.get("first"), "last_date": r.get("last"),
                     "note": "" if r["ok"] else ("liquidated 2020-05-22; no free daily history (Yahoo 404, Stooq JS "
                                                 "bot-check not bypassed, LSE terminal no candles)" if tk == "FXS"
                                                 else r["error"])})
    d = pd.DataFrame(rows)
    d.to_csv(OUT / "vehicle_universe.csv", index=False)
    return d


def completeness(rec: dict, inputs: dict) -> dict:
    exp = sorted(ETFS)
    got = sorted(k for k in exp if rec["yahoo"][k]["ok"])
    gaps = {}
    adj = pd.read_parquet(OUT / "etf_adjclose_daily.parquet")
    for tk, g in adj.groupby("market_id"):
        d = pd.DatetimeIndex(g.date).sort_values()
        bd = pd.Series(d[1:] - d[:-1]).dt.days
        gaps[tk] = {"max_calendar_gap_days": int(bd.max()) if len(bd) else None,
                    "n_gaps_gt_10_calendar_days": int((bd > 10).sum()),
                    "stale_runs_ge_10": int(((g.value.diff() == 0).astype(int).groupby(
                        (g.value.diff() != 0).cumsum()).sum() >= 10).sum())}
    fx = pd.read_parquet(OUT / "usdcad_daily.parquet")
    fxd = pd.Series(fx.date.sort_values().diff().dt.days.dropna())
    out = {"written_utc": utc_now(), "dataset_version": "cycle6_trade_v1",
           "scope": "cycle-6 TRADABLE-VARIANTS phase-1 data (no variant returns computed)",
           "endpoints": {**{f"yahoo:{k}": v for k, v in rec["yahoo"].items()},
                         **{f"fred:{k}": v for k, v in rec["fred"].items()}},
           "expected_vs_received": {"etf_expected": exp, "etf_received": got,
                                    "etf_missing": sorted(set(exp) - set(got)),
                                    "sizing_levels_expected": sorted(SIZING),
                                    "sizing_levels_received": sorted(k for k in SIZING if rec["yahoo"][k]["ok"])},
           "gap_checks": gaps,
           "usdcad_max_calendar_gap_days": int(fxd.max()),
           "conventions": {
               "prices": "Yahoo 'Adj Close' (split- and distribution-adjusted, used for total returns); 'Close' "
                         "(split-adjusted only) plus the split list reconstructs the as-traded share price for "
                         "integer-share rounding; 'Dividends' = per-share cash distribution on the ex-date "
                         "(split-adjusted) for the withholding drag",
               "timezone": "exchange-local session dates (tz dropped); NYSE Arca / Nasdaq / TSX closes",
               "holidays": "no fill; a vehicle's holding period uses its own sessions (engine panel convention)",
               "fx": "DEXCAUS CAD per USD, H.10 noon NY; used for CAD/USD translation; blank holiday rows dropped",
               "futures": "no futures prices are acquired for returns: micro-future excess returns are proxied by "
                          "the frozen paper instrument series (inputs/eval panels) -- declared in TRADE-MARGIN; "
                          "front-month continuous closes (GC=F, CL=F, NG=F) and ^GSPC are used ONLY to size "
                          "contracts (notional per contract)",
               "collateral": "cash/financing per A5 §E, T-bill from inputs/eval/series/tbill_3m_daily; CAD cash "
                             "from inputs/eval/signals/fx_foreign_rate_monthly FX_CAD"},
           "inputs_copied": inputs,
           "unavailable": {"FXS": "liquidated 2020-05-22; no free daily history reachable without bypassing a bot "
                                  "check -> SEK has no ETF vehicle in either variant (dropped, listed in specs)"}}
    (OUT / "completeness.json").write_text(json.dumps(out, indent=1, sort_keys=True))
    return out


def _bounds(p: Path):
    d = pd.read_parquet(p) if p.suffix == ".parquet" else None
    if d is None or "date" not in d.columns or d.empty:
        return None, None, (len(d) if d is not None else None)
    t = pd.to_datetime(d["date"])
    iso = lambda x: pd.Timestamp(x).tz_localize("UTC").isoformat() if pd.Timestamp(x).tzinfo is None else pd.Timestamp(x).isoformat()
    return iso(t.min()), iso(t.max()), len(d)


def write_spec(rec: dict, inputs: dict) -> dict:
    retrieved = min(v["retrieval_utc"] for v in list(rec["yahoo"].values()) + list(rec["fred"].values()))
    meta = {}
    for p in sorted(OUT.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(OUT))
        key = f"trade/{rel}"
        n = None
        first = last = None
        temporal = False
        if p.suffix == ".parquet":
            d = pd.read_parquet(p)
            n = len(d)
            tcol = "date" if "date" in d.columns else ("signal_month" if "signal_month" in d.columns else None)
            if tcol and n:
                t = pd.to_datetime(d[tcol].astype(str))
                first, last, temporal = t.min(), t.max(), True
        elif p.suffix == ".csv":
            d = pd.read_csv(p)
            n = len(d)
            tcol = "month" if "month" in d.columns else ("Date" if "Date" in d.columns else
                                                          ("observation_date" if "observation_date" in d.columns else None))
            if tcol and n:
                t = pd.to_datetime(d[tcol].astype(str).str[:10])
                first, last, temporal = t.min(), t.max(), True
        else:
            n = len(p.read_bytes().splitlines())
        src = inputs.get(rel, {}).get("source")
        if src:
            source, ident = f"byte copy of frozen cycle-6 output/eval file {src}", f"{src} sha256 {inputs[rel]['sha256']}"
        elif rel.startswith("raw/yahoo_") or rel.startswith("etf_") or rel.startswith("futures_sizing"):
            source, ident = "Yahoo Finance via yfinance 0.2.58", "yfinance Ticker.history(period='max', auto_adjust=False, actions=True)"
        elif "DEXCAUS" in rel or rel.startswith("usdcad"):
            source, ident = "FRED (Fed H.10) DEXCAUS", FRED_URL
        else:
            source, ident = "cycle6 TRADABLE-VARIANTS data pass (research/cycle6/tradable_data/acquire.py)", None
        iso = lambda x: pd.Timestamp(x).tz_localize("UTC").isoformat()
        meta[key] = {"source": source, "source_identifier": ident, "retrieved_at": retrieved,
                     "logical_as_of": "2026-09-26", "symbol": rel, "row_count": int(n),
                     "first_timestamp": iso(first) if temporal else None,
                     "last_timestamp": iso(last) if temporal else None, "temporal": bool(temporal)}
    spec = {"dataset_version": "cycle6_trade_v1",
            "scopes": [{"name": "trade", "root": str(OUT), "include": ["**/*"]}],
            "metadata": meta,
            "intermediate_artifacts": sorted(k for k in meta if not k.startswith("trade/raw/")
                                             and k != "trade/vehicle_universe.csv"),
            "universe": {"membership_artifact": "trade/vehicle_universe.csv",
                         "exclusions": [{"vehicle": "FXS", "reason": "liquidated 2020-05-22; no free history"}],
                         "delistings": [{"vehicle": "FXS", "delisted": "2020-05-22", "data": "unavailable"}],
                         "delisting_note": "only FXS among candidate vehicles is delisted; it is unavailable",
                         "symbol_mappings": {"mapping": "instrument->vehicle tables live in the TRADE-ETF-LF and "
                                                        "TRADE-MARGIN spec params (fixed from availability only)"}}}
    SPEC.write_text(json.dumps(spec, indent=1, sort_keys=True))
    return spec


def main():
    import sys
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "meta").mkdir(exist_ok=True)
    if "--no-download" in sys.argv:   # rebuild copies/completeness/spec from the saved ingest record
        rec = json.loads((OUT / "meta" / "acquire_record.json").read_text())
    else:
        rec = download()
    inputs = copy_inputs()
    vehicle_universe(rec)
    completeness(rec, inputs)
    write_spec(rec, inputs)
    print(json.dumps({k: (v["ok"], v.get("first"), v.get("last")) for k, v in rec["yahoo"].items()}, indent=0))


if __name__ == "__main__":
    main()
