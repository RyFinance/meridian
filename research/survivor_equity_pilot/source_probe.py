"""Access probe for every candidate free source (status codes only; no keys, no accounts, no
JS-challenge / CAPTCHA solving). A source that answers with a bot check or a key requirement is
recorded as such and not pursued.

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.survivor_equity_pilot.source_probe
"""
from __future__ import annotations

import json

from research.survivor_equity_pilot.common import REPORT_DIR, fetch

PROBES = {
    # SEC
    "sec_submissions_dead_cik": "https://data.sec.gov/submissions/CIK0000806085.json",  # Lehman
    "sec_company_tickers_json": "https://www.sec.gov/files/company_tickers.json",
    "sec_company_tickers_exchange": "https://www.sec.gov/files/company_tickers_exchange.json",
    "sec_full_index_form_idx_2010Q1": "https://www.sec.gov/Archives/edgar/full-index/2010/QTR1/form.idx",
    "sec_archives_form25_doc_SVB": "https://www.sec.gov/Archives/edgar/data/719739/000135445723000327/primary_doc.xml",
    "sec_efts_form25_2023": "https://efts.sec.gov/LATEST/search-index?forms=25-NSE&dateRange=custom&startdt=2023-01-01&enddt=2023-12-31",
    # Exchange / FINRA directories
    "nasdaqtrader_nasdaqlisted": "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
    "nasdaqtrader_otherlisted": "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
    "nasdaqtrader_dailylist_archive": "https://www.nasdaqtrader.com/dynamic/dailylist/dailylist20230313.txt",
    "finra_cnms_regsho_2023": "https://cdn.finra.org/equity/regsho/daily/CNMSshvol20230313.txt",
    "finra_orf_otc_regsho_2023": "https://cdn.finra.org/equity/regsho/daily/FORFshvol20230313.txt",
    "finra_orf_otc_regsho_2018": "https://cdn.finra.org/equity/regsho/daily/FORFshvol20181015.txt",
    # Prices
    "yahoo_v8_query1_delisted_TWTR": "https://query1.finance.yahoo.com/v8/finance/chart/TWTR?period1=1577836800&period2=1680000000&interval=1d",
    "yahoo_v8_query2_delisted_TWTR": "https://query2.finance.yahoo.com/v8/finance/chart/TWTR?period1=1577836800&period2=1680000000&interval=1d",
    "yahoo_v8_range_max_TWTR": "https://query1.finance.yahoo.com/v8/finance/chart/TWTR?range=max&interval=1d",
    "yahoo_v8_live_control_AAPL": "https://query1.finance.yahoo.com/v8/finance/chart/AAPL?range=5d&interval=1d",
    "yahoo_v7_download_csv": "https://query1.finance.yahoo.com/v7/finance/download/AAPL?period1=1690000000&period2=1700000000&interval=1d",
    "stooq_csv": "https://stooq.com/q/d/l/?s=aapl.us&i=d",
    "nasdaq_api_historical_delisted_TWTR": "https://api.nasdaq.com/api/quote/TWTR/historical?assetclass=stocks&fromdate=2020-01-01&todate=2022-12-31&limit=10",
    "nasdaq_api_historical_live_AAPL": "https://api.nasdaq.com/api/quote/AAPL/historical?assetclass=stocks&fromdate=2024-01-01&todate=2024-01-31&limit=10",
    "tiingo_supported_tickers_public": "https://apimedia.tiingo.com/docs/tiingo/daily/supported_tickers.zip",
    "tiingo_prices_no_key": "https://api.tiingo.com/tiingo/daily/sivbq/prices?startDate=2023-01-01",
    "alphavantage_no_key": "https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol=TWTR",
    "eodhd_no_key": "https://eodhd.com/api/eod/TWTR.US?fmt=json",
}
# NOTE: the Kaggle dataset endpoint below served the FULL 515 MB zip without login on 2026-09-25
# (it was expected to be a login wall). It is now probed with a streamed request that reads only the
# first bytes, so re-running this script cannot re-download it.
KAGGLE = "https://www.kaggle.com/api/v1/datasets/download/borismarjanovic/price-volume-data-for-all-us-stocks-etfs"


def main() -> None:
    out = {}
    for name, url in PROBES.items():
        big = name in ("tiingo_supported_tickers_public",)
        st, body, rel = fetch(url, "source_probe", name + ".bin", store=not big, timeout=40)
        snippet = (body or b"")[:300].decode("latin-1", "replace")
        tag = None
        low = snippet.lower()
        if "requires javascript" in low or "verify your browser" in low:
            tag = "JS_BOT_CHALLENGE (not bypassed)"
        elif "apikey" in low or "api key" in low or "token" in low or st == 401:
            tag = "KEY_OR_ACCOUNT_REQUIRED"
        elif "undeclared automated tool" in low or "rate threshold" in low:
            tag = "SEC_403_UA_POLICY"
        elif "no data found" in low or "symbol not exists" in low or "not found" in low:
            tag = "NO_DATA_FOR_SYMBOL"
        out[name] = {"url": url, "status": st, "bytes": len(body or b""), "tag": tag, "snippet": snippet[:200]}
        print(name, st, tag)
    import requests
    from research.survivor_equity_pilot.common import USER_AGENT
    with requests.get(KAGGLE, headers={"User-Agent": USER_AGENT}, stream=True, timeout=40) as r:
        head = next(r.iter_content(64), b"")
        out["kaggle_dataset_download_no_login"] = {
            "url": KAGGLE, "status": r.status_code, "content_length": r.headers.get("Content-Length"),
            "is_zip": head[:2] == b"PK", "tag": "SERVED_WITHOUT_LOGIN; licence unverified; frozen 2017-11 snapshot"}
    (REPORT_DIR / "source_access_probe.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
