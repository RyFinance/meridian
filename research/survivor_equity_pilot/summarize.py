"""Build the chain-break table and coverage statistics from the pilot outputs.

Inputs: reports/survivor_equity_pilot/{pilot_chain_detail,wayback_probe,random_coverage_summary}.json
LSE Terminal observations (read-only MCP, 15 calls, 2026-09-25) are recorded below verbatim-summarised
because the MCP is not callable from Python.

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.survivor_equity_pilot.summarize
"""
from __future__ import annotations

import json

import pandas as pd

from research.survivor_equity_pilot.common import REPORT_DIR

LSE_OBS = {  # symbol -> result of get_history(provider=lse, 1d) around the delisting event
    "TWTR": "404 no candle data", "SIVB": "404 no candle data", "ATVI": "404 no candle data",
    "FRC": "404 no candle data", "XLNX": "404 no candle data", "CELG": "404 no candle data",
    "SHLD": "404 no candle data", "FB": "404 no candle data", "DELL": "no bars 2013-09..11",
    "BBBY": "RECYCLED: bars 2015-2023 at ~$18-24 = current BBBY occupant (Beyond/Overstock), not Bed Bath & Beyond",
    "WM": "RECYCLED: 2008-09 bars at ~$34 = Waste Management, not Washington Mutual",
}
LSE_SEARCH_EMPTY = ["Twitter", "SVB Financial", "Activision", "Bed Bath"]


def main() -> None:
    d = json.load(open(REPORT_DIR / "pilot_chain_detail.json"))
    wb = {r["key"]: r for r in json.load(open(REPORT_DIR / "wayback_probe.json"))["price_pages"]} \
        if (REPORT_DIR / "wayback_probe.json").exists() else {}
    rows = []
    for r in d:
        if r["key"].endswith("_CTRL"):
            continue
        ev = pd.Timestamp(r["event_date"])
        dt = r["dates"] or {}
        t = r["tickers"] or {}
        f25 = [pd.Timestamp(x) for x in dt.get("form25", [])]
        f25_near = [x for x in f25 if -45 <= (x - ev).days <= 150]
        f15_near = [x for x in map(pd.Timestamp, dt.get("form15", [])) if -45 <= (x - ev).days <= 400]
        k301_near = [x for x in map(pd.Timestamp, dt.get("8k_3.01", [])) if -120 <= (x - ev).days <= 60]
        fin = (r.get("finra_cnms") or {}).get(r["ticker"])
        fin_last = pd.Timestamp(fin["last"]) if fin else None
        finra_ok = fin_last is not None and -10 <= (fin_last - ev).days <= 200
        yok = [y for y in r["yahoo"] if y.get("identity") == "CONFIRMED"]
        yrej = [y for y in r["yahoo"] if y.get("identity") == "REJECTED"]
        yrec = [y for y in r["yahoo"] if y.get("class") == "RECYCLED_OR_POST_EVENT_ONLY"]
        w = wb.get(r["key"], {})
        wy = w.get("yahoo_hp", {})
        wg = w.get("google_hist", {})
        wi = w.get("yahoo_ichart_csv", {})
        ti = [x for x in t.get("tiingo_supported", []) if x.get("assetType") == "Stock"
              and pd.Timestamp(x["startDate"]) <= ev <= pd.Timestamp(x["endDate"]) + pd.Timedelta(days=5)]
        row = {
            "key": r["key"], "ticker": r["ticker"], "event_type": r["event_type"], "event_date": r["event_date"],
            "L1_cik": r["cik"] if r["cik"] else "BREAK:" + ("FDIC/bank-regulator filer, not SEC"
                                                            if r["key"] in ("FIRSTREPUBLIC", "SIGNATURE") else "unresolved"),
            "L1_method": r["cik_method"],
            "L2_ticker_recovered_free": t.get("expected_ticker_recovered"),
            "L2_ticker_sources": ";".join(k for k in ("efts_display_names", "wayback_company_tickers", "wayback_symdir")
                                          if (r["ticker"] in (t.get(k) and [x if isinstance(x, str) else x.get("ticker", x.get("symbol"))
                                                                              for x in t.get(k)] or []))),
            "L2_n_candidate_symbols": len(t.get("derived_without_prior", [])),
            "L3_form25_near_event": f25_near[0].strftime("%Y-%m-%d") if f25_near else None,
            "L3_form15_near_event": f15_near[0].strftime("%Y-%m-%d") if f15_near else None,
            "L3_8k301_near_event": k301_near[0].strftime("%Y-%m-%d") if k301_near else None,
            "L3_finra_last_cnms_day": fin["last"] if fin else None,
            "L3_finra_consistent": finra_ok if fin else None,
            "L3_tiingo_window": f"{ti[0]['ticker']}:{ti[0]['startDate']}..{ti[0]['endDate']}" if ti else None,
            "L4_yahoo": ("CONFIRMED:" + ",".join(y["symbol"] for y in yok)) if yok else
                        ("FALSE_HISTORY_REJECTED:" + ",".join(y["symbol"] for y in yrej)) if yrej else
                        ("RECYCLED:" + ",".join(y["symbol"] for y in yrec)) if yrec else "NOT_FOUND",
            "L4_lse_terminal": LSE_OBS.get(r["ticker"], "not queried (call budget)"),
            "L4_wayback_yahoo_hp_captures_pre_event": wy.get("n_pre_event"),
            "L4_wayback_yahoo_hp_months_pre_event": wy.get("pre_event_months"),
            "L4_wayback_google_hist_captures_pre_event": wg.get("n_pre_event"),
            "L4_wayback_ichart_csv_captures": wi.get("n_captures"),
            "L4_wayback_sample_rows_per_page": wy.get("sample_rows"),
            "L4_tiingo_has_history_needs_key": bool(ti),
        }
        link3 = bool(row["L3_form25_near_event"] or row["L3_form15_near_event"] or row["L3_8k301_near_event"])
        row["chain_breaks_at"] = ("L1_CIK" if not r["cik"] else
                                  "L2_TICKER" if not row["L2_ticker_recovered_free"] else
                                  "L3_DELIST_DATE" if not link3 else
                                  "L4_PRICE" if not yok else "COMPLETE")
        rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(REPORT_DIR / "chain_break_table.csv", index=False)
    n = len(df)
    era = pd.cut(pd.to_datetime(df["event_date"]).dt.year, [2000, 2009, 2014, 2018, 2023],
                 labels=["2001-2009", "2010-2014", "2015-2018", "2019-2023"])
    stats = {
        "n_pilot_delisted": n,
        "L1_cik_resolved": int(df["L1_cik"].apply(lambda x: not str(x).startswith("BREAK")).sum()),
        "L2_ticker_recovered_free": int(df["L2_ticker_recovered_free"].fillna(False).sum()),
        "L3_any_sec_delisting_marker": int((df["L3_form25_near_event"].notna() | df["L3_form15_near_event"].notna()
                                            | df["L3_8k301_near_event"].notna()).sum()),
        "L3_form25_near_event": int(df["L3_form25_near_event"].notna().sum()),
        "L3_finra_available": int(df["L3_finra_last_cnms_day"].notna().sum()),
        "L3_finra_consistent": int(df["L3_finra_consistent"].fillna(False).sum()),
        "L4_yahoo_confirmed": int(df["L4_yahoo"].str.startswith("CONFIRMED").sum()),
        "L4_yahoo_false_history_or_recycled": int(df["L4_yahoo"].str.match("FALSE|RECYCLED").sum()),
        "L4_yahoo_not_found": int((df["L4_yahoo"] == "NOT_FOUND").sum()),
        "L4_lse_genuine": 0, "L4_lse_queried": int(df["L4_lse_terminal"].ne("not queried (call budget)").sum()),
        "L4_tiingo_listed_needs_key": int(df["L4_tiingo_has_history_needs_key"].sum()),
        "L4_wayback_any_yahoo_hp_pre_event": int((df["L4_wayback_yahoo_hp_captures_pre_event"].fillna(0) > 0).sum()),
        "chain_breaks_at": df["chain_breaks_at"].value_counts().to_dict(),
        "complete_by_era": df.assign(era=era).groupby("era", observed=False)["chain_breaks_at"]
            .apply(lambda s: f"{(s == 'COMPLETE').sum()}/{len(s)}").to_dict(),
        "lse_search_instruments_empty_for": LSE_SEARCH_EMPTY,
    }
    (REPORT_DIR / "pilot_coverage_stats.json").write_text(json.dumps(stats, indent=1, default=str))
    print(json.dumps(stats, indent=1, default=str))
    print(df[["key", "L1_cik", "L2_ticker_recovered_free", "L3_form25_near_event", "L3_finra_last_cnms_day",
              "L4_yahoo", "L4_wayback_yahoo_hp_captures_pre_event", "L4_wayback_google_hist_captures_pre_event",
              "chain_breaks_at"]].to_string())


if __name__ == "__main__":
    main()
