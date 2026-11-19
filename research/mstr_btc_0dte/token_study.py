"""MSTRUSDT perp (24/7 tokenized MSTR exposure) vs BTC and vs the real MSTR stock, Feb-Sep 2026."""
import glob, zipfile, io
import numpy as np, pandas as pd
from pathlib import Path
H = Path(__file__).parent; D = H.parents[1] / "data/binance_mstr_token"
def load(sym):
    out = []
    for f in sorted(glob.glob(str(D / f"{sym}-1m-*.zip"))):
        z = zipfile.ZipFile(f); raw = z.read(z.namelist()[0]).decode()
        df = pd.read_csv(io.StringIO(raw), header=0 if raw.startswith("open_time") else None)
        df = df.iloc[:, :6]; df.columns = ["t", "o", "h", "l", "c", "v"]; out.append(df)
    df = pd.concat(out); df["t"] = pd.to_datetime(df.t.astype("int64"), unit="ms", utc=True).dt.tz_convert("America/New_York").dt.tz_localize(None)
    return df.drop_duplicates("t").set_index("t").c.astype(float)
tok, btc = load("MSTRUSDT"), load("BTCUSDT")
print("token", tok.index.min(), tok.index.max(), len(tok))
m = pd.read_parquet(H / "mstr_daily_yf.parquet")[["Open", "Close"]]
m = m[(m.index >= tok.index.min().normalize()) & (m.index <= tok.index.max().normalize())]
def at(s, t):
    i = s.index.searchsorted(t, side="right") - 1
    return s.iloc[i] if i >= 0 and t - s.index[i] < pd.Timedelta("5min") else np.nan
rows = []
dates = list(m.index)
for prev, d in zip(dates[:-1], dates[1:]):
    c0 = prev + pd.Timedelta(hours=16); o1 = d + pd.Timedelta(hours=9, minutes=29)
    r = dict(date=d, dow=d.dayofweek, gap_days=(d - prev).days,
             tok_c=at(tok, c0), tok_o=at(tok, o1), btc_c=at(btc, c0), btc_o=at(btc, o1),
             mstr_c=m.Close[prev], mstr_o=m.Open[d], mstr_close=m.Close[d], tok_931=at(tok, d + pd.Timedelta(hours=9, minutes=31)))
    rows.append(r)
p = pd.DataFrame(rows).set_index("date").dropna()
p["btc_off"] = np.log(p.btc_o / p.btc_c); p["tok_off"] = np.log(p.tok_o / p.tok_c); p["mstr_gap"] = np.log(p.mstr_o / p.mstr_c)
p["basis_close"] = p.tok_c / p.mstr_c - 1          # token vs stock at the prior close
p["basis_open"] = p.mstr_o / p.tok_o - 1           # how far the real open lands from the token at 09:29
print(f"\noff-hours days n={len(p)} (Mon/after-holiday n={(p.gap_days>1).sum()})")
print("corr(BTC off-hours, token off-hours) = %.3f   corr(token off-hours, MSTR gap) = %.3f   corr(BTC, MSTR gap) = %.3f"
      % (p.btc_off.corr(p.tok_off), p.tok_off.corr(p.mstr_gap), p.btc_off.corr(p.mstr_gap)))
print("same direction token vs MSTR gap: %.0f%%" % (100 * (np.sign(p.tok_off) == np.sign(p.mstr_gap)).mean()))
print("token vs stock at prior 16:00: mean %+.1f bp, sd %.1f bp" % (p.basis_close.mean() * 1e4, p.basis_close.std() * 1e4))
print("MSTR open vs token at 09:29: mean %+.1f bp, sd %.1f bp, |.|>50bp on %.0f%% of days"
      % (p.basis_open.mean() * 1e4, p.basis_open.std() * 1e4, 100 * (p.basis_open.abs() > .005).mean()))
# does the token under/over-react to BTC off-hours? (residual vs the real gap)
b = np.polyfit(p.btc_off, p.tok_off, 1)[0]; bg = np.polyfit(p.btc_off, p.mstr_gap, 1)[0]
print(f"beta token~BTC {b:.2f}   beta MSTRgap~BTC {bg:.2f}")
# tradable test 1: buy token at Fri 16:00 (or prior close) in BTC... can't know BTC. Instead: residual at 09:29 predicts the open?
res = bg * p.btc_off - p.tok_off
print("corr(BTC-implied minus token move by 09:29, MSTR open vs token 09:29) = %.3f" % res.corr(p.basis_open))
p.to_parquet(H / "token_panel.parquet")
# lead-lag in off-hours minutes: BTC past 5m vs token next 5m, weekends & nights only
j = pd.DataFrame({"b": np.log(btc).diff(), "k": np.log(tok).diff()}).dropna()
off = ~((j.index.dayofweek < 5) & (j.index.time >= pd.Timestamp("09:30").time()) & (j.index.time < pd.Timestamp("16:00").time()))
for nm, z in [("off-hours", j[off]), ("market hours", j[~off])]:
    b5 = z.b.rolling(5).sum(); k5 = z.k.rolling(5).sum(); kf = z.k[::-1].rolling(5).sum()[::-1].shift(-1)
    print(f"{nm:12s} minutes={len(z)} corr same-minute={z.b.corr(z.k):.3f}  corr(BTC past5, token next5)={b5.corr(kf):.3f}  corr((BTC-token) past5, token next5)={(b5-k5).corr(kf):.3f}")
