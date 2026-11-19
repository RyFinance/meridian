"""Weekday post-US-close BTC window: long BTC from the NYSE close (16:00 ET; 13:00 on early-close days) for W minutes.
Only NYSE session days. Exact 1-minute prices; costs per round trip in bp."""
import numpy as np, pandas as pd
from pathlib import Path
from research.forward import nyse
H = Path(__file__).parent
def load_btc():
    b = pd.read_parquet(H.parents[2] / "BTC-Acum/data/btc_usd_1m_candles_polymarket_arb.parquet")
    b = b.set_index(pd.to_datetime(b.timestamp)).close.sort_index(); return b[~b.index.duplicated()]
def trades(b, W=60, start="2017-08-21", end="2026-08-10", lead=0):
    out = []; d = nyse.next_session(pd.Timestamp(start).date())
    while d <= pd.Timestamp(end).date():
        t0 = pd.Timestamp(nyse.close_utc(d)) + pd.Timedelta(minutes=lead); t1 = t0 + pd.Timedelta(minutes=W)
        i0 = b.index.searchsorted(t0, side="right") - 1; i1 = b.index.searchsorted(t1, side="right") - 1
        if i0 >= 0 and i1 > i0 and t0 - b.index[i0] < pd.Timedelta("5min") and t1 - b.index[i1] < pd.Timedelta("5min"):
            out.append((pd.Timestamp(d), np.log(b.iloc[i1] / b.iloc[i0])))
        d = nyse.next_session(d)
    return pd.Series(dict(out))
if __name__ == "__main__":
    b = load_btc()
    for W, lead in [(60, 0), (120, 0), (60, -60), (180, -60)]:
        r = trades(b, W, lead=lead)
        lab = f"close{lead:+d}min, {W}min"
        for per, x in [("2017-22", r[:"2022-12-31"]), ("2023-26", r["2023-01-01":]), ("ETF 2024-26", r["2024-01-01":])]:
            yrs = (x.index[-1] - x.index[0]).days / 365.25
            line = f"{lab:20s} {per:11s} n={len(x)} gross {x.mean()*1e4:+5.1f}bp t={x.mean()/x.std()*np.sqrt(len(x)):+.2f} hit={(x>0).mean():.3f}"
            for c in (2, 5, 8):
                n = x - c / 1e4; line += f" | net@{c}bp {n.mean()*1e4:+5.1f} ann {n.sum()/yrs*100:+5.1f}% SR {n.mean()/n.std()*np.sqrt(len(n)/yrs):+.2f}"
            print(line)
        r.to_frame("r").to_parquet(H / f"postclose_W{W}_lead{lead}.parquet")
    r = trades(b, 60); print("16-17 by year (bp):", r.groupby(r.index.year).mean().mul(1e4).round(1).to_dict())
