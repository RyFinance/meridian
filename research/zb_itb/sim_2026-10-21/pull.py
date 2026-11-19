import sys, json; sys.path.insert(0, ".")
from pathlib import Path
from live.zb_itb.broker import Alpaca, load_env
a = Alpaca(load_env(Path(".env.alpaca.itb")))
D = "https://data.alpaca.markets/v2/stocks"
out = {}
for sym in ["ITB", "NAIL"]:
    m = a._req("GET", f"{D}/{sym}/bars", params={"timeframe": "1Min", "start": "2026-10-21T13:29:00Z", "end": "2026-10-21T14:35:00Z", "feed": "sip", "limit": 10000, "adjustment": "raw"})
    d = {"bars": []}
    out[sym] = {"min": m.get("bars") or [], "day": d.get("bars") or []}
    bars = out[sym]["min"]
    print(sym, "day bars", [(b["t"][:10], b["o"], b["c"]) for b in out[sym]["day"]], "| 1m bars", len(bars), bars[0]["t"] if bars else None, bars[-1]["t"] if bars else None)
json.dump(out, open(sys.argv[1], "w"))
