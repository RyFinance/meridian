"""Writes reports/data_scout/vendor_matrix.csv (data-scout survey, accessed 2026-09-23).

Every row was checked against the cited URL on 2026-09-23 unless `verified` says otherwise.
"unverified" = taken from a third-party page, a search snippet, or memory; confirm before paying.
Run: PYTHONPATH=. .venv/bin/python -m research.data_scout.build_vendor_matrix
"""
from __future__ import annotations

import csv
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "reports" / "data_scout" / "vendor_matrix.csv"
ACCESSED = "2026-09-23"

COLS = ["rank_for_project", "need", "vendor", "product", "coverage", "history_start", "delisted_handling",
        "point_in_time", "timestamp_quality", "index_membership", "license_personal", "price_usd",
        "api_format", "pitfalls", "verified", "sources"]

ROWS = [
    # ---------------- 1. survivorship-free equities (+ 2. PIT fundamentals, + 4. 13F) ----------------
    ["1", "equities+fundamentals+13F", "Sharadar (direct, sharadar.com)", "Bundle, Full History (SEP, SFP, SF1, SF2, SF3, DAILY, EVENTS, ACTIONS, TICKERS, SP500)",
     "~21k stocks + 10k funds on NYSE/Nasdaq/NYSEMKT/Arca/BATS; fundamentals ~18k companies incl. ~12k delisted",
     "prices Dec-1997/1998; fundamentals 1998 (QuantRocket says SF1 1990); 13F 2013; insiders 2005; 8-K events 1993",
     "delisted kept; permaticker + isdelisted; ACTIONS has delisting reasons, acquirer contraticker; NO CRSP-style delisting return",
     "SF1 AR dimensions (ARQ/ARY/ART) as-reported, datekey = SEC filing date; MR dims are restated (lookahead)",
     "daily; fundamentals within 24h of 10-K/10-Q filing; datekey is a DATE (no acceptance time); 10-Q date lags the 8-K earnings release",
     "S&P 500 add/remove table (Sharadar docs: 1998+; QuantRocket: 1957+). No Russell.",
     "Personal Use License; guest checkout", "$69/mo or $499/yr (full history); 10y $49/$399; 5y $29/$299",
     "REST (Nasdaq Data Link style tables) + bulk CSV download; macOS-native",
     "'99% survivorship-free' is vendor claim; closeadj is split+div+spinoff adjusted, check vs closeunadj; SP500 table start date conflicts between sources; licence terms on lapse not checked",
     "verified prices/plans on sharadar.com/subscribe; history dates partly conflicting",
     "https://sharadar.com/subscribe ; https://sharadar.com/fundamentals ; https://sharadar.com/prices ; https://sharadar.com/docs/sp500 ; https://www.quantrocket.com/sharadar/"],
    ["2", "equities (+Russell membership)", "Norgate Data", "US Stocks Platinum (Diamond adds 1950+)",
     "all US listed + 25,222 delisted (1950-Sep 2022 count); coverage 'essentially complete back to late 1992'",
     "Platinum delisted back to 1990; Diamond 1950",
     "delisted kept, symbol suffixed with delist year-month; NO delisting returns (vendor says close on last bar)",
     "prices PIT; fundamentals and broker consensus CURRENT ONLY (no history)",
     "EOD bars; official session",
     "S&P 500 (from Mar-1957), Russell 1000/2000/3000 (from Jul-1990), Nasdaq-100, S&P 100/400/600, DJIA - as PIT timeseries",
     "personal use only; data (incl. exports/backups) must be deleted when subscription lapses",
     "12 months: Gold $360, Platinum $630, Diamond $787.50 (6-month terms exist, price unverified)",
     "Norgate Data Updater (Windows-only) + norgatedata Python package; Mac needs a Windows VM/VPS",
     "Windows dependency; delete-on-expiry licence makes results unreproducible after lapse; one review reported dividend gaps (unverified)",
     "verified prices/coverage on norgatedata.com",
     "https://norgatedata.com/stockmarketpackages.php ; https://norgatedata.com/data-content-tables.php ; https://norgatedata.com/data-package-faq.php ; https://norgatedata.com/faq.php"],
    ["4", "equities+fundamentals", "EODHD", "All-In-One (EOD, fundamentals, intraday) + marketplace S&P/DJ historical constituents",
     "26,000+ delisted US tickers (mostly from Jan-2000); 70+ exchanges",
     "EOD 30+ yrs; fundamentals 30+ yrs for ~11k majors, 10 yrs for minor",
     "delisted listed via exchange symbol list then normal endpoints",
     "fundamentals not documented as as-reported/PIT (treat as restated)",
     "EOD date only", "standard API: S&P 500 log, thin before ~2012-2015 (snapshot 2008 = 436 names); marketplace S&P Global feed $29.99/mo, up to 12 yrs",
     "personal plans; commercial from $399/mo", "EOD $19.99/mo; Fundamentals $59.99/mo; All-in-one $99.99/mo ($999.90/yr); constituents add-on $29.99/mo",
     "REST JSON/CSV", "constituent history too short for 2000-2012; fundamentals restated", "verified pricing page; constituent caveat from EODHD blog/search",
     "https://eodhd.com/pricing ; https://eodhd.com/financial-apis-blog/reworked-sp-500-historical-constituents ; https://eodhd.com/lp/spglobal ; https://eodhd.com/financial-apis/delisted-stock-companies-data-2"],
    ["5", "equities", "Tiingo", "Power plan (+ fundamentals add-on)",
     "65k+ equities/funds; delisted/recycled via permaTicker", "30+ yrs EOD; fundamentals 15+ yrs (Power)",
     "permaTicker for delisted/recycled symbols (completeness unverified)", "fundamentals asReported=true gives as-filed values; 'date' = release date",
     "EOD date", "none", "individual $30/mo or $300/yr; commercial internal $50/mo; fundamentals add-on price not public",
     "$30/mo + add-on (ask sales)", "REST", "no index membership; fundamentals price opaque", "verified pricing page",
     "https://www.tiingo.com/about/pricing ; https://www.tiingo.com/documentation/fundamentals"],
    ["6", "equities", "Massive (formerly Polygon.io)", "Stocks Starter/Developer/Advanced + flat files",
     "all US listed stocks; trades/quotes/aggs start 2003-09-10", "2003-09-10 (Advanced 20+ yrs; Developer 10; Starter 5)",
     "day files contain every ticker that traded (delisted names present on their dates); ticker renames must be stitched by user",
     "prices only; 'Financials & Ratios' $29/mo (PIT not documented)", "tick-level SIP timestamps; daily aggs may include eligible extended-hours trades",
     "none", "Individual use only / non-pro", "$29 / $79 / $199 per month",
     "REST, WebSocket, S3 flat files", "daily close may differ from official close; renames; LSE vault appears to resell this feed (inference: same 2003-09-10 start and O: option tickers)",
     "verified plans on massive.com/pricing; aggs caveat from Massive knowledge base",
     "https://massive.com/pricing ; https://massive.com/knowledge-base/categories/data-coverage ; https://polygon.io/knowledge-base/article/does-polygon-offer-pre-market-and-after-hours-data"],
    ["9", "equities", "QuantConnect (AlgoSeek US Equities)", "bulk daily download + US Equity Security Master",
     "~27,500 securities incl. delisted, since Jan-1998", "1998", "survivorship-free, map files for renames, factor files for splits/dividends",
     "prices only", "SIP", "none (no PIT index membership)", "requires paid organisation tier", "daily bulk $2,136 + $600/yr updates; Security Master $600 + $600/yr; plus tier fee",
     "LEAN CLI download", "most expensive route to the same coverage; LEAN file format", "verified docs page",
     "https://www.quantconnect.com/docs/v2/lean-cli/datasets/quantconnect/us-equity ; https://www.quantconnect.com/data/algoseek-us-equities"],
    ["10", "equities", "FirstRate Data", "Stocks complete bundle (1-min to daily)",
     "16k stocks incl. 7,000+ delisted", "Jan-2000", "delisted included", "prices only", "bars include pre/post-market trades (same official-close problem as LSE vault)",
     "none", "not stated", "one-off price not visible (JS); updates $79.95/mo after first month (unverified)", "CSV download",
     "extended-hours in daily bars; no index membership", "partially verified",
     "https://firstratedata.com/stock-data ; https://firstratedata.com/cb/1/complete"],
    ["11", "equities", "Stooq", "free bulk db (stooq.com/db/h)", "current listings, broad", "varies", "NOT survivorship-free (delisted not systematically kept)",
     "prices only", "EOD", "none", "free; API key required since Mar-2026", "$0", "CSV/txt bulk",
     "survivor-biased; only useful as a second source for survivors", "partially verified (pandas-datareader issue)",
     "https://github.com/pydata/pandas-datareader/issues/1012"],
    ["n/a", "equities+fundamentals", "CRSP (now Morningstar) via WRDS", "CRSP US Stock",
     "gold standard incl. delisting returns (DLRET)", "1925", "full delisting returns", "yes", "daily", "S&P 500 membership files",
     "WRDS accounts only for faculty/students/staff of subscribing institutions; no individual route found", "institutional only (price not public)",
     "WRDS", "NOT accessible to an unaffiliated individual; Morningstar completed acquisition 2026-02-02 (retail offering not announced)",
     "verified eligibility page; acquisition news", "https://wrds-www.wharton.upenn.edu/pages/about/wrds-account-types/ ; https://newsroom.morningstar.com/news/news-details/2026/Morningstar-Completes-Acquisition-of-CRSP-and-Extends-Relationship-with-Vanguard/default.aspx"],
    ["n/a", "fundamentals/estimates", "Compustat, I/B/E/S, Zacks history", "PIT fundamentals / consensus history",
     "institutional", "Compustat 1950s; I/B/E/S 1976; Zacks annual EPS 1979", "yes", "Compustat snapshot/PIT products; I/B/E/S unadjusted detail",
     "", "", "institutional contracts; Zacks history 'contact sales'", "Capital IQ ~$30k+/yr industry estimate (unverified); Zacks unknown",
     "WRDS / vendor feeds", "no credible retail route to point-in-time consensus estimates", "unverified pricing",
     "https://costbench.com/software/financial-data-terminals/sp-capital-iq/ ; https://zacksdata.com/consensus/faq/"],
    # ---------------- 3. options with quotes / OI ----------------
    ["1", "options", "ORATS", "Near end-of-day historical backfill (individual) + optional daily delivery",
     "5,000+ underlyings, full chains", "2007-01-01", "delisted underlyings retained ('contracts as the markets presented them')",
     "snapshot data, no restatement", "NBBO taken 14 min before close (~15:46 ET) with stock price at snapshot; OI and volume included (OI timing to audit)",
     "n/a", "Individual licence; 14-day S3 download window", "$599 one-off (~500 GB); $99/mo ongoing; API plans $199-$899/mo",
     "S3 CSV archive; REST API", "smoothed IV is a model output - use raw bid/ask for tests; OI likely prior-day; 15:46 snapshot != close",
     "verified orats.com/near-eod-data", "https://orats.com/near-eod-data ; https://orats.com/data-api ; https://orats.com/university/historical-data"],
    ["2", "options", "HistoricalOptionData.com (DeltaNeutral)", "EOD all US options, Level 1/2/3",
     "5,900+ underlyings, ~1.7M contracts/day", "2002 (SPX 1990)", "survivorship-free; delisted/merged underlyings retained",
     "snapshot", "EOD bid/ask; snapshot time not stated (audit)", "n/a", "all sales final once accessed; licence text not found",
     "L1 (bid/ask/vol/OI) full $1,150, 1-yr $230; L2 (+greeks/IV) $1,495; L3 $2,035; subscriptions $585-$865/yr",
     "CSV/Parquet via dnfilevault", "closing-quote timing vs underlying close unknown; no refunds", "verified homepage + FAQ",
     "https://historicaloptiondata.com/ ; https://historicaloptiondata.com/faq/"],
    ["3", "options (reference/reconciliation)", "Cboe DataShop", "Option EOD Summary",
     "all OPRA series", "2012-01", "all listed series on the day", "snapshot", "NBBO at 15:45 and at EOD; OHLC, VWAP, volume, OI; IV/greeks at 15:45 are a paid add-on",
     "n/a", "internal use; no redistribution", "$50/trading day full market (capped $300/month), $1,500/yr, archive 2012+ $7,200, single underlying-day $6 (third-party quote)",
     "CSV files", "authoritative exchange source; ideal for spot reconciliation; expensive for bulk", "fields verified on Cboe page; prices unverified (third-party review 2026-09-13)",
     "https://datashop.cboe.com/option-eod-summary ; https://stockmarketstack.com/tools/cboe-datashop"],
    ["4", "options (spot checks)", "IVolatility", "EOD data download, pay-per-use (retail)",
     "US + global options", "2005", "not stated", "snapshot", "NBBO option prices; IV surface products", "n/a", "retail users only",
     "$0.40 per ticker-day option prices; $0.60 IV products; $0.20 underlying", "CSV", "per-ticker-day pricing makes cross-sections expensive (100 names x 19 yrs ~ $190k); fine for spot checks",
     "verified", "https://www.ivolatility.com/data-download-intro/"],
    ["5", "options (raw OPRA)", "Databento", "OPRA.PILLAR, Standard plan",
     "full OPRA", "2013-04-01 for trades, OHLCV, statistics (OI), definitions, CBBO-1m", "definitions per day",
     "raw exchange messages", "exchange timestamps (ns); CBBO-1m = NBBO each minute", "n/a", "Standard allows personal use",
     "Standard $199/mo: L0 (OHLCV, definitions, statistics) 16+ yrs, L1 1 yr; older CBBO pay-as-you-go $/GB (use metadata.get_cost); $125 free credit",
     "API + DBN/CSV", "heavy engineering; cost of CBBO history unknown until quoted", "verified pricing page; OPRA history from search snippet of Databento blog",
     "https://databento.com/pricing ; https://databento.com/blog/introducing-new-opra-pricing-plans ; https://databento.com/docs/schemas-and-data-formats/statistics"],
    ["7", "options", "Massive (Polygon) Options", "Options Advanced",
     "full OPRA", "trades since 2014; quotes depth '5+ years' (start unverified)", "expired contracts via reference", "raw", "tick", "n/a", "individual", "$199/mo (Starter $29, Developer $79)",
     "REST, S3 flat files", "greeks/IV/OI documented only for snapshots (current), not history; quote files are huge", "partially verified",
     "https://massive.com/options"],
    ["8", "options", "EODHD US options", "Options data package", "6,600+ US underlyings", "Q4-2023", "not stated", "snapshot", "bid/ask, OI, greeks, IV (42 fields)",
     "n/a", "personal", "$29.99/mo", "REST", "history too short for backtests; usable as forward feed", "verified landing page", "https://eodhd.com/lp/us-stock-options-api"],
    ["n/a", "options", "OptionMetrics IvyDB US", "IvyDB", "academic standard", "1996", "yes", "snapshot", "EOD best bid/offer, OI, IV, greeks", "n/a",
     "institutional/WRDS only", "institutional only", "WRDS", "not accessible to an individual", "verified (WRDS/vendor pages)", "https://optionmetrics.com/united-states/ ; https://wrds-www.wharton.upenn.edu/pages/about/data-vendors/optionmetrics/"],
    ["n/a", "options", "QuantConnect (AlgoSeek US Equity Options)", "minute options incl. OI", "4,000 symbols", "2012-01", "", "", "minute trades/quotes + OI", "n/a", "paid tier",
     "download price not found (docs page 404)", "LEAN", "unverified", "unverified", "https://www.quantconnect.com/data/algoseek-us-equity-options"],
    # ---------------- 4. other genuinely new information ----------------
    ["1", "13F holdings", "SEC Form 13F data sets", "structured 13F-HR holdings", "all 13F filers", "2013-07 (structured)", "filers and issuers by CUSIP; delisted issuers included",
     "filing date + period of report", "filing date; 45-day reporting lag", "n/a", "public domain", "$0", "quarterly zip of TSV",
     "values in $000s through 2022, dollars from 2023; CUSIP-to-ticker mapping needed; pre-2013 requires parsing raw filings", "verified",
     "https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets"],
    ["1", "PIT fundamentals", "SEC Financial Statement Data Sets", "XBRL numbers from 10-K/10-Q etc.", "every XBRL filer incl. later-delisted", "2009-Q1 (small filers from ~2011)",
     "all filers by CIK", "as-filed values per filing (restatements appear as new filings)", "filing date + acceptance datetime in SUB table (field names from memory - check readme)",
     "n/a", "public domain", "$0", "quarterly zip of TSV (sub/num/tag/pre)", "tag inconsistency; CIK-to-ticker mapping for dead firms; SEC disclaims accuracy", "verified page; field list unverified",
     "https://www.sec.gov/data-research/sec-markets-data/financial-statement-data-sets"],
    ["2", "short interest", "FINRA Equity Short Interest", "twice-monthly short positions", "all exchange-listed and OTC equities", "online grid 5 rolling years; archive files (start for listed names unverified)",
     "by symbol on report date", "as published", "settlement date 15th and month-end; published ~7 business days later", "n/a", "free", "$0", "API (JSON/CSV) + pipe-delimited archives",
     "use publication date, not settlement date, for PIT; pre-FINRA listed-stock history came from exchanges", "verified",
     "https://www.finra.org/finra-data/browse-catalog/equity-short-interest ; https://www.finra.org/sites/default/files/Equity_Short_Interest_Data_File_Download_API.pdf"],
    ["3", "short volume", "FINRA Reg SHO daily short sale volume", "off-exchange (TRF/ADF/ORF) short-sale volume", "listed + OTC", "2009-08 (CNMS files)", "by symbol/day", "as published", "daily",
     "n/a", "free", "$0", "daily txt files (cdn.finra.org)", "NOT short interest; dominated by market-maker shorting; only off-exchange volume", "verified",
     "https://www.finra.org/finra-data/browse-catalog/short-sale-volume-data/daily-short-sale-volume-files ; https://developer.finra.org/docs/reg-sho-daily-short-sale-volume"],
    ["4", "settlement fails", "SEC fails-to-deliver", "CNS fails by CUSIP", "all NSCC CNS securities", "2004-02 (complete from 2008-09-16; before only >=10k-share balances)",
     "by CUSIP", "as published", "twice monthly, ~2-week lag", "n/a", "public", "$0", "pipe-delimited txt", "threshold change 2008-09-16", "verified via search",
     "https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data"],
    ["5", "fund holdings/flows", "SEC Form N-PORT data sets", "quarterly public NPORT-P", "registered funds incl. ETFs", "2019-10", "all filers", "filing date", "public only for 3rd month of fiscal quarter, 60-day lag",
     "n/a", "public", "$0", "structured data sets", "monthly flows only, short history; not daily creations/redemptions", "partially verified (third-party + data.gov listing)",
     "https://catalog.data.gov/dataset/form-n-port-data-sets"],
    ["6", "borrow fees", "Interactive Brokers shortstock FTP / iBorrowDesk", "indicative borrow rate and availability", "US + intl", "FTP: current only; iBorrowDesk charts", "n/a",
     "forward only", "intraday snapshots", "n/a", "IBKR customer / free site (check ToS before scraping)", "$0", "FTP text file", "no downloadable history; institutional history (S&P/Markit Securities Finance) not retail",
     "partially verified", "https://www.iborrowdesk.com/ ; https://community.portfolio123.com/t/historical-data-on-ib-short-lending-fee-and-share-availability/58254"],
    ["7", "membership cross-check", "fja05680/sp500 (GitHub) + Wikipedia + S&P DJI announcements", "free S&P 500 membership history", "S&P 500", "1996", "tickers as symbols",
     "change dates", "announcement vs effective date must be separated", "S&P 500 only", "free (check repo licence)", "$0", "CSV",
     "author notes first ~5 years may miss symbols; Wikipedia lists 'selected changes'; last explicit update noted May-2021", "verified repo README",
     "https://github.com/fja05680/sp500 ; https://www.spglobal.com/spdji/en/media-center/news-announcements/"],
    ["8", "listing events", "Nasdaq Trader symbol directory / Daily List", "current symbol files; Daily List of adds/deletes/changes", "Nasdaq + other exchanges", "directory: current only; Daily List archive 1999 (paid via Nasdaq Data Link NDL)",
     "current directory drops delisted names", "n/a", "intraday file timestamps", "n/a", "free directory; Daily List fee-liable", "$0 directory", "pipe-delimited txt via FTP",
     "no archive of the free files - must be collected forward", "verified", "https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs ; https://www.nasdaqtrader.com/Trader.aspx?id=dailylistpd"],
    # ---------------- existing project sources ----------------
    ["have", "all", "LSE vault (current key)", "stocks, options prints, reference tables", "3,982 stock symbols (127 non-live, all went dark after 2026-04-13); 3,186 option underlyings",
     "stocks 2003-09-10; options prints 2014-06-02; options_chain snapshots 2026-06-11; options_flow_1m 2026-01-02", "NO: SIVB/TWTR/FRC/CELG candles 404; financial_reports for SIVB/TWTR empty; dividends DO include FRC/ATVI",
     "financial_reports carry accepted_date (current names only)", "1d candles are UTC calendar-day incl. extended hours", "none (no constituents dataset)", "existing key", "already paid",
     "REST + /export (5/hour, 2.5M-row cap)", "no option bid/ask or OI anywhere; no short interest/13F/borrow", "probed 2026-09-23 (reports/data_scout/lse_probe_*.json)",
     "data/lse_catalog_20260917.json ; https://api.londonstrategicedge.com/vault (probe)"],
    ["have", "options (forward)", "LSE Terminal MCP options_chain", "live chain snapshot", "~900+ underlyings", "live; vault keeps chain snapshots since 2026-06-11",
     "n/a", "forward only", "last-trade price, IV and greeks per contract; rows can be days stale (last_trade_at)", "n/a", "existing", "already paid", "MCP / engine REST",
     "no bid/ask, no OI; IV derived from last trades carries bid-ask bounce and staleness", "probed by coordinator 2026-09-23", "LSE Terminal engine /api/options/chain"],
]


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLS + ["accessed"])
        for r in ROWS:
            assert len(r) == len(COLS), (r[2], len(r))
            w.writerow(r + [ACCESSED])
    print(f"wrote {len(ROWS)} rows to {OUT}")


if __name__ == "__main__":
    main()
