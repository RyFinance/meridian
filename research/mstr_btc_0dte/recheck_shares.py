"""Historical reference only (whole window already viewed): RAW-Monday shares with the realistic cost model,
BTC sampled at 09:25 ET (the forward rule) instead of 09:30. $100k notional, no compounding."""
import numpy as np, pandas as pd
from pathlib import Path
from research.mstr_btc_0dte.costs import round_trip_return
from research.forward import nyse
H = Path(__file__).parent
btc = pd.read_parquet(H.parents[2] / "BTC-Acum/data/btc_usd_1m_candles_polymarket_arb.parquet")
btc = btc.set_index(pd.to_datetime(btc.timestamp)).close.sort_index()
m = pd.read_parquet(H / "mstr_daily_yf.parquet")
m = m[(m.index >= "2020-08-11") & (m.index <= "2026-08-10")]
def px(t):
    i = btc.index.searchsorted(t, side="right") - 1
    return btc.iloc[i] if i >= 0 and (t - btc.index[i]) < pd.Timedelta("10min") else np.nan
rows = []
for d in m.index[m.index.dayofweek == 0]:
    prev = nyse.previous_session(d.date())
    b0 = px(pd.Timestamp(nyse.close_utc(prev))); b1 = px(pd.Timestamp(nyse.open_utc(d.date())) - pd.Timedelta(minutes=5))
    if not (np.isfinite(b0) and np.isfinite(b1)) or b1 == b0:
        continue
    s = int(np.sign(np.log(b1 / b0)))
    o, c = m.Open[d], m.Close[d]
    base, stress = round_trip_return(s, o, c, 100_000), round_trip_return(s, o, c, 100_000, stress=True)
    rows.append(dict(date=d, sig=s, gross=base["gross"], net=base["net"], stress=stress["net"], cost=base["cost_usd"]))
t = pd.DataFrame(rows).set_index("date")
yrs = (t.index[-1] - t.index[0]).days / 365.25
for col in ["gross", "net", "stress"]:
    x = t[col]
    print(f"{col:6s} n={len(x)} mean={x.mean()*1e4:+.1f}bp win={np.mean(x>0):.2f} t={x.mean()/x.std()*np.sqrt(len(x)):+.2f} "
          f"Sharpe(yr, Mondays only)={x.mean()/x.std()*np.sqrt(len(x)/yrs):+.2f} total={x.sum():+.1%}")
print(f"avg cost per round trip ${t.cost.mean():.2f} ({t.cost.mean()/1e3:.2f} bp of $100k... i.e. {(t.gross-t.net).mean()*1e4:.1f} bp)")
print(t.groupby(t.index.year).net.agg(["size", "mean", "sum"]).round(4))
