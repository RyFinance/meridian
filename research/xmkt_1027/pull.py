"""Alpaca SIP 15-minute bars (incl. pre/post market), 2016-01 → now−30 min, for a cross-market ETF universe."""
import sys, os, time, datetime as dt, pandas as pd
sys.path.insert(0, ".")
from pathlib import Path
from live.zb_itb.broker import Alpaca, load_env
a = Alpaca(load_env(Path(".env.alpaca.itb")))
D = "https://data.alpaca.markets/v2/stocks/{}/bars"
OUT = "research/xmkt_1027/bars/"
U = sys.argv[1].split(",")
end = (dt.datetime.utcnow() - dt.timedelta(minutes=40)).strftime("%Y-%m-%dT%H:%M:%SZ")
for s in U:
    f = OUT + s + ".parquet"
    if os.path.exists(f): continue
    rows, tok = [], None
    while True:
        p = {"timeframe": "15Min", "start": "2016-01-01T00:00:00Z", "end": end, "feed": "sip", "limit": 10000, "adjustment": "all"}
        if tok: p["page_token"] = tok
        try: j = a._req("GET", D.format(s), params=p)
        except Exception as e: print(s, "ERR", str(e)[:80]); break
        rows += j.get("bars") or []; tok = j.get("next_page_token")
        if not tok: break
    if rows:
        d = pd.DataFrame(rows); d["t"] = pd.to_datetime(d.t, utc=True).dt.tz_convert("America/New_York"); d.to_parquet(f)
        print(s, len(d), d.t.iloc[0].date(), flush=True)
