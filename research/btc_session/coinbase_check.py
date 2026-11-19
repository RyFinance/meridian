"""Independent check of the 17:00-18:00 ET weekday effect on Coinbase BTC-USD 1m candles (the forward scoring venue)."""
import datetime as dt, json, time, urllib.request, urllib.parse
import numpy as np, pandas as pd
from pathlib import Path
from zoneinfo import ZoneInfo
from research.forward import nyse
ET = ZoneInfo("America/New_York"); H = Path(__file__).parent
OUT = H / "coinbase_17_18.parquet"
def candles(t0, t1):
    q = urllib.parse.urlencode({"granularity": 60, "start": t0.strftime("%Y-%m-%dT%H:%M:%SZ"), "end": t1.strftime("%Y-%m-%dT%H:%M:%SZ")})
    for a in range(5):
        try:
            req = urllib.request.Request(f"https://api.exchange.coinbase.com/products/BTC-USD/candles?{q}", headers={"User-Agent": "quant_v7/1.0"})
            return json.loads(urllib.request.urlopen(req, timeout=20).read())
        except Exception:
            time.sleep(2 * (a + 1))
    return []
rows = []
d = dt.date(2019, 1, 2)
while d <= dt.date(2026, 10, 16):
    if d.weekday() < 5 and nyse.is_session(d):
        a = dt.datetime.combine(d, dt.time(16, 58), ET).astimezone(dt.timezone.utc)
        b = dt.datetime.combine(d, dt.time(18, 1), ET).astimezone(dt.timezone.utc)
        c = {int(x[0]): x[4] for x in candles(a, b)}
        s17 = int((dt.datetime.combine(d, dt.time(16, 59), ET)).timestamp()); s18 = int((dt.datetime.combine(d, dt.time(17, 59), ET)).timestamp())
        if s17 in c and s18 in c:
            rows.append((pd.Timestamp(d), np.log(c[s18] / c[s17])))
        time.sleep(0.12)
    d += dt.timedelta(days=1)
r = pd.Series(dict(rows)); r.to_frame("r").to_parquet(OUT)
for per, x in [("2019-22", r[:"2022-12-31"]), ("2023-26", r["2023":]), ("2024-26", r["2024":]), ("2026", r["2026":])]:
    print(f"{per}: n={len(x)} mean {x.mean()*1e4:+.2f}bp t={x.mean()/x.std()*np.sqrt(len(x)):+.2f} hit={(x>0).mean():.3f}")
print("by year:", r.groupby(r.index.year).mean().mul(1e4).round(1).to_dict())
