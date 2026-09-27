"""Reusable, polite fetchers used to scout the public datasets in this cycle.

These functions reproduce the curl probes run by hand during the session (documented in
data/public_scout/MANIFEST.json and the final report). They are here so the checks are re-runnable,
not because every probe in the report was executed through this file. Rate limit: <=3 req/s,
one request at a time, sleep(0.4) between calls, descriptive User-Agent, no email address.

Run individual checks, e.g.:
    cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -c \
        "from research.public_scout.probes import finra_regsho_history_bounds as f; print(f())"
"""
from __future__ import annotations

import time
from datetime import date, timedelta

import requests

UA = "quant_v7-research/1.0"
HEADERS = {"User-Agent": UA}
SLEEP = 0.4


def _get(url: str, **kw) -> requests.Response:
    time.sleep(SLEEP)
    return requests.get(url, headers=HEADERS, timeout=20, **kw)


def finra_regsho_exists(d: date) -> bool:
    """True if the FINRA consolidated-NMS Reg SHO daily short-volume file exists for date d."""
    url = f"https://cdn.finra.org/equity/regsho/daily/CNMSshvol{d:%Y%m%d}.txt"
    return _get(url).status_code == 200


def finra_regsho_history_bounds(probe_years=(2009, 2014, 2018, 2019, 2020)) -> dict:
    """Coarse bisection of how far back the CDN flat-file archive goes. Empirically the archive
    starts 2018-08-01 (verified in this session), NOT the 2009-11-09 date FINRA cites for when it
    first began publishing short-volume data -- the CDN only serves a retained window."""
    out = {}
    for y in probe_years:
        out[y] = finra_regsho_exists(date(y, 1, 2))
    return out


def finra_short_interest_biweekly_exists(d: date) -> bool:
    url = f"https://cdn.finra.org/equity/otcmarket/biweekly/shrt{d:%Y%m%d}.csv"
    return _get(url).status_code == 200


def binance_um_monthly_file_exists(kind: str, symbol: str, year_month: str, interval: str | None = None) -> bool:
    """kind in {fundingRate, klines, premiumIndexKlines}. year_month like '2022-05'."""
    base = f"https://data.binance.vision/data/futures/um/monthly/{kind}/{symbol}"
    if interval:
        url = f"{base}/{interval}/{symbol}-{interval}-{year_month}.zip"
    else:
        url = f"{base}/{symbol}-{kind}-{year_month}.zip"
    return _get(url).status_code == 200


def binance_delisted_symbol_retention(symbol: str, months: list[str]) -> dict[str, bool]:
    """Check whether monthly funding-rate archives survive past a token's delisting.
    Known delisted USD-M perps checked in this cycle: LUNAUSDT (crashed/delisted 2022-05),
    FTTUSDT and SRMUSDT (FTX-ecosystem, delisted ~2022-11/12)."""
    return {m: binance_um_monthly_file_exists("fundingRate", symbol, m) for m in months}


def cftc_cot_annual_zip_exists(report: str, year: int) -> bool:
    """report in {deacot (legacy), fut_disagg_txt, fut_fin_txt (TFF), dea_cit_txt (supplemental/CIT)}."""
    if report == "deacot":
        url = f"https://www.cftc.gov/files/dea/history/deacot{year}.zip"
    else:
        url = f"https://www.cftc.gov/files/dea/history/{report}_{year}.zip"
    return _get(url).status_code == 200


def treasury_auction_results_sample(start: str, end: str, security_type: str = "Note") -> list[dict]:
    """TreasuryDirect TA_WS search endpoint: keyless, returns full auction results (bid-to-cover,
    high/low/median yield, indirect/direct/primary-dealer allocations, tail), not just dates."""
    url = "https://www.treasurydirect.gov/TA_WS/securities/search"
    params = {"format": "json", "startDate": start, "endDate": end, "type": security_type}
    r = _get(url, params=params)
    r.raise_for_status()
    return r.json()


def wikipedia_pageviews(article: str, start: str, end: str, project: str = "en.wikipedia") -> dict:
    """Keyless. start/end as YYYYMMDD00. Daily granularity; API data begins 2015-07-01."""
    url = (
        f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{project}/"
        f"all-access/all-agents/{article}/daily/{start}/{end}"
    )
    r = _get(url)
    r.raise_for_status()
    return r.json()


if __name__ == "__main__":
    print("finra_regsho_history_bounds:", finra_regsho_history_bounds())
    print(
        "LUNAUSDT retention around delisting:",
        binance_delisted_symbol_retention("LUNAUSDT", ["2022-04", "2022-05", "2022-06"]),
    )
