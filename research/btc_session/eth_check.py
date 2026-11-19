"""Independent check of the 17:00-18:00 ET weekday effect on Coinbase ETH-USD 1m candles (the forward scoring venue)."""
import datetime as dt, json, time, urllib.request, urllib.parse
import numpy as np, pandas as pd
from pathlib import Path
from zoneinfo import ZoneInfo
from research.forward import nyse
ET = ZoneInfo("America/New_York"); H = Path(__file__).parent
OUT = H / "coinbase_eth_hours.parquet"
def candles(t0, t1):
    q = urllib.parse.urlencode({"granularity": 60, "start": t0.strftime("%Y-%m-%dT%H:%M:%SZ"), "end": t1.strftime("%Y-%m-%dT%H:%M:%SZ")})
    for a in range(5):
        try:
            req = urllib.request.Request(f"https://api.exchange.coinbase.com/products/ETH-USD/candles?{q}", headers={"User-Agent": "quant_v7/1.0"})
            return json.loads(urllib.request.urlopen(req, timeout=20).read())
        except Exception:
            time.sleep(2 * (a + 1))
    return []
rows = []
d = dt.date(2019, 1, 2)
while d <= dt.date(2026, 10, 16):
    if d.weekday() < 5 and nyse.is_session(d):
        a = dt.datetime.combine(d, dt.time(15, 58), ET).astimezone(dt.timezone.utc)
        b = dt.datetime.combine(d, dt.time(19, 1), ET).astimezone(dt.timezone.utc)
        c = {int(x[0]): x[4] for x in candles(a, b)}
        k = {h: int((dt.datetime.combine(d, dt.time(h - 1, 59), ET)).timestamp()) for h in (16, 17, 18, 19)}
        if all(v in c for v in k.values()):
            rows.append(dict(d=pd.Timestamp(d), h16=np.log(c[k[17]] / c[k[16]]), h17=np.log(c[k[18]] / c[k[17]]), h18=np.log(c[k[19]] / c[k[18]])))
        time.sleep(0.12)
    d += dt.timedelta(days=1)
R = pd.DataFrame(rows).set_index("d"); R.to_parquet(OUT)
for col, lab in [("h17", "17-18 (CME break, TEST)"), ("h16", "16-17 placebo"), ("h18", "18-19 placebo")]:
    r = R[col]
    for per, x in [("2019-26", r), ("2019-22", r[:"2022-12-31"]), ("2023-26", r["2023":]), ("2026", r["2026":])]:
        print(f"{lab:24s} {per}: n={len(x)} mean {x.mean()*1e4:+.2f}bp t={x.mean()/x.std()*np.sqrt(len(x)):+.2f} hit={(x>0).mean():.3f}")
print("17-18 by year:", R.h17.groupby(R.index.year).mean().mul(1e4).round(1).to_dict())
