"""BTC off-US-hours vs US-hours returns, 2017-08..2026-08, from 1-minute BTC.
For each NYSE session d: day = 09:30 -> close(d) (16:00, 13:00 early close); off = close(prev session) -> 09:30(d)."""
import numpy as np, pandas as pd
from pathlib import Path
from research.forward import nyse
H = Path(__file__).parent
b = pd.read_parquet(H.parents[2] / "BTC-Acum/data/btc_usd_1m_candles_polymarket_arb.parquet")
b = b.set_index(pd.to_datetime(b.timestamp)).close.sort_index(); b = b[~b.index.duplicated()]
def px(t):
    i = b.index.searchsorted(pd.Timestamp(t), side="right") - 1
    return b.iloc[i] if i >= 0 and (pd.Timestamp(t) - b.index[i]) < pd.Timedelta("10min") else np.nan
rows = []
d = nyse.next_session(pd.Timestamp("2017-08-21").date())
end = pd.Timestamp("2026-08-10").date()
while d <= end:
    pv = nyse.previous_session(d)
    o, c, pc = px(nyse.open_utc(d)), px(nyse.close_utc(d)), px(nyse.close_utc(pv))
    rows.append(dict(date=pd.Timestamp(d), dow=d.weekday(), gap_days=(d - pv).days, off=np.log(o / pc), day=np.log(c / o)))
    d = nyse.next_session(d)
s = pd.DataFrame(rows).set_index("date").dropna()
s.to_parquet(H / "sessions.parquet"); print(s.shape, s.index.min().date(), s.index.max().date())
