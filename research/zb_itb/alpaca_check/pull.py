"""Pull 1-minute SIP bars (all US exchanges, incl. extended hours) from Alpaca's data API for ITB, NAIL, TLT.
Keeps 04:00-10:31 ET and 15:55-16:00 ET minutes (signal + entry/exit + previous close). One parquet per symbol-year."""
import sys, time, datetime as dt
from pathlib import Path
import pandas as pd
from live.zb_itb.broker import Alpaca, DATA_URL
OUT = Path(__file__).parent / "bars"
b = Alpaca()
def pull(sym, start, end):
    rows, tok = [], None
    while True:
        p = {"timeframe": "1Min", "start": start, "end": end, "feed": "sip", "limit": 10000, "adjustment": "all"}
        if tok: p["page_token"] = tok
        j = b._req("GET", f"{DATA_URL}/v2/stocks/{sym}/bars", params=p)
        rows += j.get("bars") or []; tok = j.get("next_page_token")
        if not tok: break
        time.sleep(0.3)
    d = pd.DataFrame(rows)
    if d.empty: return d
    d["t"] = pd.to_datetime(d.t, utc=True).dt.tz_convert("America/New_York")
    m = d.t.dt.hour * 60 + d.t.dt.minute
    return d[((m >= 240) & (m <= 631)) | ((m >= 955) & (m <= 960))]
for sym in sys.argv[1:] or ["ITB", "NAIL", "TLT"]:
    for y in range(2016, 2027):
        f = OUT / f"{sym}_{y}.parquet"
        if f.exists(): continue
        s, e = f"{y}-01-01T00:00:00Z", (f"{y+1}-01-01T00:00:00Z" if y < 2026 else (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ"))
        try:
            d = pull(sym, s, e); d.to_parquet(f); print(sym, y, len(d), flush=True)
        except Exception as ex:
            print(sym, y, "ERR", str(ex)[:150], flush=True)
print("DONE")
