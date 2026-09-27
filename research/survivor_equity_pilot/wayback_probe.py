"""Internet Archive (Wayback) as a free source for (a) point-in-time listing directories and
(b) archived *price pages* of now-delisted tickers (Yahoo q/hp, ichart CSV, Google Finance historical).

Only public archived captures are read (CDX index + a handful of raw captures). No returns computed.

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.survivor_equity_pilot.wayback_probe
"""
from __future__ import annotations

import json
import re
from collections import Counter

import pandas as pd

from research.survivor_equity_pilot.common import DATA_DIR, REPORT_DIR, fetch
from research.survivor_equity_pilot.pilot_universe import rows

CDX = "http://web.archive.org/cdx/search/cdx?output=json&fl=timestamp,original,statuscode,mimetype,length"


def cdx(url: str, extra: str = "", fname: str | None = None) -> list[dict]:
    cache = DATA_DIR / "wayback_cdx" / (fname or "")
    if fname and cache.exists():
        try:  # resume: reuse a previously stored, parseable CDX answer
            d = json.loads(cache.read_bytes())
            return [dict(zip(d[0], r)) for r in d[1:]] if d else []
        except (json.JSONDecodeError, IndexError):
            pass
    st, body, _ = fetch(f"{CDX}&url={url}{extra}", "wayback_cdx", fname, timeout=45, retries=0)
    if st != 200 or not body:
        return [{"_error": st}]
    try:
        d = json.loads(body)
    except json.JSONDecodeError:
        return []
    if not d:
        return []
    hdr = d[0]
    return [dict(zip(hdr, r)) for r in d[1:]]


def directory_density() -> dict:
    out = {}
    for name, url in {"nasdaqlisted": "nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
                      "otherlisted": "nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
                      "sec_company_tickers": "www.sec.gov/files/company_tickers.json",
                      "sec_ticker_txt": "www.sec.gov/include/ticker.txt"}.items():
        caps = cdx(url, "&filter=statuscode:200", f"dir_{name}.json")
        if caps and "_error" in caps[0]:
            out[name] = {"error": caps[0]["_error"]}
            continue
        yrs = Counter(c["timestamp"][:4] for c in caps)
        out[name] = {"n_captures_200": len(caps), "by_year": dict(sorted(yrs.items())),
                     "first": caps[0]["timestamp"] if caps else None,
                     "last": caps[-1]["timestamp"] if caps else None}
    return out


def parse_yahoo_hp(html: str) -> int:
    """Count daily price rows on an archived Yahoo 'Historical Prices' page (dates like 'Sep 12, 2008')."""
    new_fmt = re.findall(r">(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) \d{1,2}, (?:19|20)\d\d<", html)
    old_fmt = re.findall(r">\d{1,2}-[A-Z][a-z]{2}-\d{2}<", html)  # pre-2010 layout, e.g. >5-Mar-08<
    return len(new_fmt) + len(old_fmt)


def main() -> None:
    res = {"directories": directory_density(), "price_pages": []}
    fetched = 0
    for r in rows(include_controls=False):
        t, ev = r["ticker"], pd.Timestamp(r["event_date"])
        rec = {"key": r["key"], "ticker": t, "event_date": r["event_date"]}
        for label, url in {"yahoo_hp": f"finance.yahoo.com/q/hp?s={t}*",
                           "yahoo_ichart_csv": f"ichart.finance.yahoo.com/table.csv?s={t}*",
                           "google_hist": f"www.google.com/finance/historical?q=*{t}*"}.items():
            if label == "google_hist":  # CDX does not support infix wildcards; use exchange-qualified form
                url = f"www.google.com/finance/historical?q={r['exchange'] if r['exchange'] != 'NASDAQ' else 'NASDAQ'}:{t}*"
            caps = cdx(url, "&filter=statuscode:200&limit=500", f"px_{label}_{t}.json")
            ok = [c for c in caps if "_error" not in c
                  and re.search(rf"[?&](s|q)=([A-Z]+:)?{re.escape(t)}($|&)", c["original"], re.I)]
            pre = [c for c in ok if pd.Timestamp(c["timestamp"][:8]) <= ev]
            rec[label] = {"n_captures": len(ok), "n_pre_event": len(pre),
                          "pre_event_months": len({c["timestamp"][:6] for c in pre}),
                          "error": caps[0].get("_error") if caps and "_error" in caps[0] else None}
            # fetch ONE pre-event capture per ticker for yahoo_hp to measure rows per page
            if label == "yahoo_hp" and pre and fetched < 12:
                c = pre[-1]
                st, body, _ = fetch(f"http://web.archive.org/web/{c['timestamp']}id_/{c['original']}",
                                    "wayback_pricepages", f"{t}_{c['timestamp']}.html", timeout=90)
                fetched += 1
                rec[label]["sample_capture"] = c["timestamp"]
                rec[label]["sample_rows"] = parse_yahoo_hp(body.decode("latin-1")) if st == 200 and body else None
        res["price_pages"].append(rec)
        print(rec, flush=True)
    (REPORT_DIR / "wayback_probe.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res["directories"], indent=1))


if __name__ == "__main__":
    main()
