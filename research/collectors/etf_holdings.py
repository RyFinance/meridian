"""Issuer-published daily ETF holdings/shares-outstanding files (iShares, SPDR).

Keyless, public static files on the issuers' own sites. No account, no key. Both issuers
publish these files specifically for public daily download (iShares' "download holdings"
CSV, State Street's "daily holdings" spreadsheet) -- this is the documented, intended use
of the file, not a scrape of a page meant for something else. robots.txt for both hosts
(checked 2026-09-25) does not disallow these paths.

Daily holdings + shares-outstanding is the standard free proxy for ETF creation/redemption
activity: a day-over-day change in shares outstanding, multiplied by NAV/price, approximates
net creation (inflow) or redemption (outflow) `--` this collector only stores the raw files;
computing that proxy is left to later analysis code, which is out of scope here.

Two funds are covered as a starting set (both S&P 500 trackers, different issuers, so any
later comparison has an issuer-independent check): IVV (iShares Core S&P 500) and SPY
(SPDR S&P 500). Extending SYMBOLS to more funds is a one-line change per issuer.

    PYTHONPATH=. .venv/bin/python -m research.collectors.etf_holdings
"""
from __future__ import annotations

from research.collectors.common import FetchError, http_get, summarize, utc_now, write_snapshot

SOURCE = "etf_holdings"

ISHARES_FUNDS = {
    # fund_id used in ishares.com's own ajax holdings-download URL
    "IVV": "239726",
}
ISHARES_URL = ("https://www.ishares.com/us/products/{fund_id}/x/1467271812596.ajax"
               "?fileType=csv&fileName={ticker}_holdings&dataType=fund")

SPDR_FUNDS = {
    "SPY": "https://www.ssga.com/us/en/individual/etfs/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spy.xlsx",
}


def run_once(when=None) -> dict:
    when = when or utc_now()
    records: list[dict] = []
    errors: list[str] = []

    for ticker, fund_id in ISHARES_FUNDS.items():
        url = ISHARES_URL.format(fund_id=fund_id, ticker=ticker)
        try:
            resp = http_get(url)
            if resp.status_code == 200:
                records.append(write_snapshot(SOURCE, f"ishares.{ticker}.holdings", resp.content, when=when,
                                               ext="csv", extra_meta={"url": url}))
            else:
                errors.append(f"ishares.{ticker}: HTTP {resp.status_code}")
        except FetchError as e:
            errors.append(f"ishares.{ticker}: {e}")

    for ticker, url in SPDR_FUNDS.items():
        try:
            resp = http_get(url)
            if resp.status_code == 200:
                records.append(write_snapshot(SOURCE, f"spdr.{ticker}.holdings", resp.content, when=when,
                                               ext="xlsx", extra_meta={"url": url}))
            else:
                errors.append(f"spdr.{ticker}: HTTP {resp.status_code}")
        except FetchError as e:
            errors.append(f"spdr.{ticker}: {e}")

    return summarize(SOURCE, records, errors=errors)


if __name__ == "__main__":
    import json
    print(json.dumps(run_once(), indent=2))
