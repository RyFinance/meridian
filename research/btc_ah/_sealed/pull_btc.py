"""Sealed holdout: Coinbase BTC-USD 1m 2026-08-10 .. 2026-10-17 via curl (not inspected until candidates are frozen)."""
import datetime as dt, json, subprocess, time, pandas as pd
from pathlib import Path
API = "https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=60&start={}&end={}"
cur, end, rows = dt.datetime(2026,8,10,tzinfo=dt.timezone.utc), dt.datetime(2026,10,17,21,0,tzinfo=dt.timezone.utc), []
while cur < end:
    nxt = min(cur + dt.timedelta(minutes=300), end)
    for a in range(8):
        out = subprocess.run(["curl","-s","-A","research/1.0",API.format(cur.strftime("%Y-%m-%dT%H:%M:%SZ"), nxt.strftime("%Y-%m-%dT%H:%M:%SZ"))],capture_output=True,text=True).stdout
        try: data = json.loads(out); assert isinstance(data, list); break
        except Exception: time.sleep(2*(a+1))
    else: raise RuntimeError(cur)
    rows += [dict(ts=r[0], open=r[3], high=r[2], low=r[1], close=r[4], volume=r[5]) for r in data]
    cur = nxt; time.sleep(0.2)
d = pd.DataFrame(rows).drop_duplicates('ts').sort_values('ts'); d['ts'] = pd.to_datetime(d.ts, unit='s', utc=True)
d.to_parquet(Path(__file__).parent/'btc_1m_holdout.parquet'); print('rows', len(d))
