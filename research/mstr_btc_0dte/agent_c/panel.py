"""Build per-name daily panel: BTC off-hours move (prior NYSE close -> 09:30 ET open, from 1m BTC),
stock gap, open->close, open->10:30 (60m bars), rolling prior-250d gap beta and under-reaction residual."""
import sys, numpy as np, pandas as pd
from pathlib import Path
H = Path(__file__).parent
sys.path.insert(0, str(H.parents[1] / "forward"))
import nyse
START = {"MSTR":"2020-08-11","MARA":"2019-01-01","RIOT":"2019-01-01","CLSK":"2020-12-10","HUT":"2021-06-15",
         "CIFR":"2021-08-30","WULF":"2021-12-14","IREN":"2021-11-17","BTBT":"2020-06-01","COIN":"2021-04-14",
         "HOOD":"2021-07-29","XYZ":"2019-01-01","HIVE":"2021-06-24","BTDR":"2023-04-14","CAN":"2019-11-21",
         "GBTC":"2019-01-01","BITO":"2021-10-19","IBIT":"2024-01-11","FBTC":"2024-01-11","CORZ":"2024-01-24"}
LARGE = {"MSTR","COIN","MARA","RIOT","HOOD","IBIT","FBTC","XYZ","GBTC","BITO"}
btc = pd.read_parquet(H.parents[3] / "BTC-Acum/data/btc_usd_1m_candles_polymarket_arb.parquet")
btc = btc.set_index(pd.to_datetime(btc.timestamp, utc=True)).close.sort_index()
bi, bv = btc.index.values, btc.values
def px(ts):  # last BTC 1m close at or before ts (within 30 min)
    t = np.array(pd.DatetimeIndex(ts).tz_convert("UTC").tz_localize(None).values, dtype="datetime64[ns]")
    bix = np.array(bi.astype("datetime64[ns]")) if bi.dtype.kind == "M" else bi
    i = np.searchsorted(btc.index.tz_localize(None).values, t, side="right") - 1
    ok = (i >= 0) & ((t - btc.index.tz_localize(None).values[np.clip(i, 0, None)]) < np.timedelta64(30, "m"))
    out = np.where(ok, bv[np.clip(i, 0, None)], np.nan); return out
D = pd.read_parquet(H / "daily.parquet")
Hr = pd.read_parquet(H / "hourly.parquet")
rows = []
for tk, st in START.items():
    s = D.loc[tk][["Open", "High", "Low", "Close", "Volume"]].copy(); s.index = pd.to_datetime(s.index)
    s = s[(s.Volume > 0) & (s.Open > 0)]
    s["dvol20"] = (s.Close * s.Volume).rolling(20).mean().shift(1)  # prior-20d avg $ volume (no look-ahead)
    s["prev_close"] = s.Close.shift(1); s["prev_date"] = pd.Series(s.index, index=s.index).shift(1)
    s = s[s.index >= st].dropna(subset=["prev_close"])
    days = [x.date() for x in s.index]
    s = s[[nyse.is_session(x) for x in days]]
    days = [x.date() for x in s.index]
    # require prev_date to be the previous NYSE session (no missing-data gaps)
    s = s[[pd.Timestamp(nyse.previous_session(x)) == p for x, p in zip(days, s.prev_date)]]
    days = [x.date() for x in s.index]
    t_pc = pd.DatetimeIndex([nyse.close_utc(nyse.previous_session(x)) for x in days])
    t_o = pd.DatetimeIndex([nyse.open_utc(x) for x in days]); t_c = pd.DatetimeIndex([nyse.close_utc(x) for x in days])
    b0, b1, b2 = px(t_pc), px(t_o), px(t_c)
    s["btc_off"] = np.log(b1 / b0); s["btc_day"] = np.log(b2 / b1)
    s["gap"] = np.log(s.Open / s.prev_close); s["oc"] = np.log(s.Close / s.Open)
    s["early"] = [nyse.session_close_time(x).hour != 16 for x in days]
    # first 60m bar (09:30-10:30 ET) close
    if tk in Hr.index.get_level_values(0):
        h = Hr.loc[tk].copy(); h.index = pd.to_datetime(h.index, utc=True).tz_convert("America/New_York")
        h = h[(h.index.hour == 9) & (h.index.minute == 30)]
        h1 = pd.Series(h.Close.values, index=pd.DatetimeIndex(h.index.date)); h1 = h1[~h1.index.duplicated()]
        s["c1030"] = h1.reindex(s.index)
    else: s["c1030"] = np.nan
    s["o1030"] = np.log(s.c1030 / s.Open)
    s = s.dropna(subset=["btc_off", "gap", "oc"])
    # rolling prior-250-day OLS beta of gap on btc_off (min 120 obs), shifted so day t uses t-250..t-1
    x, y = s.btc_off, s.gap
    mx, my = x.rolling(250, min_periods=120).mean(), y.rolling(250, min_periods=120).mean()
    cov = (x * y).rolling(250, min_periods=120).mean() - mx * my; var = (x * x).rolling(250, min_periods=120).mean() - mx * mx
    s["beta"] = (cov / var).shift(1)
    s["u"] = s.beta * s.btc_off - s.gap                       # >0: opened BELOW what BTC implies (under-reaction to up move)
    s["u_sd"] = s.u.rolling(250, min_periods=60).std().shift(1)
    s["z"] = s.u / s.u_sd
    s["tk"] = tk; s["large"] = tk in LARGE
    rows.append(s.reset_index().rename(columns={"index": "date", "Date": "date"}))
P = pd.concat(rows, ignore_index=True)
P.to_parquet(H / "panel.parquet")
print(P.groupby("tk").agg(n=("oc", "size"), first=("date", "min"), last=("date", "max"), nbeta=("beta", "count"), n1030=("o1030", "count")))
