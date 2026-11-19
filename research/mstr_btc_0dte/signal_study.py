"""Does BTC's off-hours move (prior 16:00 ET -> 09:30 ET) predict MSTR's open->close move?"""
import pandas as pd, numpy as np
from pathlib import Path
H = Path(__file__).parent
btc = pd.read_parquet(H.parents[2] / "BTC-Acum/data/btc_usd_1m_candles_polymarket_arb.parquet")
btc["ts"] = pd.to_datetime(btc.timestamp).dt.tz_convert("America/New_York")
btc = btc.set_index("ts").close.sort_index()
m = pd.read_parquet(H / "mstr_daily_yf.parquet")[["Open", "Close"]]
m = m[m.index >= "2020-08-11"]  # MSTR bitcoin treasury start
def px(t):  # last BTC price at or before t
    i = btc.index.searchsorted(t, side="right") - 1
    return btc.iloc[i] if i >= 0 and (t - btc.index[i]) < pd.Timedelta("30min") else np.nan
rows = []
dates = list(m.index)
for prev, d in zip(dates[:-1], dates[1:]):
    t_prev_close = pd.Timestamp(prev.date()).tz_localize("America/New_York") + pd.Timedelta(hours=16)
    t_open = pd.Timestamp(d.date()).tz_localize("America/New_York") + pd.Timedelta(hours=9, minutes=30)
    t_close = t_open + pd.Timedelta(hours=6, minutes=30)
    b0, b1, b2 = px(t_prev_close), px(t_open), px(t_close)
    rows.append(dict(date=d, dow=d.dayofweek, gap_days=(d - prev).days,
                     btc_off=np.log(b1 / b0), btc_day=np.log(b2 / b1),
                     mstr_gap=np.log(m.Open[d] / m.Close[prev]), mstr_day=np.log(m.Close[d] / m.Open[d])))
df = pd.DataFrame(rows).dropna().set_index("date")
df.to_parquet(H / "daily_panel.parquet")
print(df.index.min(), df.index.max(), len(df))
print("\nbeta of MSTR gap on BTC off-hours move, and does BTC off-hours predict MSTR open->close?")
for name, sub in [("all", df), ("Mon", df[df.dow == 0]), ("Fri", df[df.dow == 4]), ("Tue-Thu", df[df.dow.isin([1, 2, 3])])]:
    bg = np.polyfit(sub.btc_off, sub.mstr_gap, 1)[0]
    resid = sub.mstr_gap - bg * sub.btc_off   # MSTR gap not explained by BTC
    under = sub.btc_off * bg - sub.mstr_gap   # positive = MSTR opened below what BTC implies
    c1 = sub.btc_off.corr(sub.mstr_day); c2 = under.corr(sub.mstr_day); c3 = sub.btc_day.corr(sub.mstr_day)
    hit = (np.sign(sub.btc_off) == np.sign(sub.mstr_day)).mean()
    print(f"{name:8s} n={len(sub):4d} gapBeta={bg:.2f} corr(btcOff,mstrDay)={c1:+.3f} corr(underreact,mstrDay)={c2:+.3f} "
          f"hit={hit:.3f} | contemporaneous corr(btcDay,mstrDay)={c3:+.2f}")
print("\nby year, Mon+Fri: corr(btc_off, mstr_day)")
mf = df[df.dow.isin([0, 4])]
print(mf.groupby(mf.index.year).apply(lambda s: pd.Series(dict(n=len(s), corr=s.btc_off.corr(s.mstr_day),
      hit=(np.sign(s.btc_off) == np.sign(s.mstr_day)).mean()))).round(3))
print("\nMon+Fri, quintiles of btc_off -> mean MSTR open->close (bps)")
mf = mf.assign(q=pd.qcut(mf.btc_off, 5, labels=False))
print(mf.groupby("q").agg(btc_off=("btc_off", "mean"), mstr_day=("mstr_day", "mean"), n=("mstr_day", "size"),
      sd=("mstr_day", "std")).assign(btc_off=lambda x: x.btc_off * 1e4, mstr_day=lambda x: x.mstr_day * 1e4).round(1))
