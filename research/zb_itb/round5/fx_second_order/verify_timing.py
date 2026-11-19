"""Check FX 60m bar labels (start vs end) against 5m bars over the last 60 days."""
from pathlib import Path
import pandas as pd, yfinance as yf
C = Path(__file__).parent / "yf_cache"; NY = "America/New_York"
for sym in ["6E=F", "DX-Y.NYB", "6J=F"]:
    f5 = yf.download(sym, period="60d", interval="5m", auto_adjust=False, progress=False)
    f5.columns = f5.columns.get_level_values(0); f5.index = f5.index.tz_convert(NY)
    f60 = pd.read_parquet(C / f"{sym.replace('=','_').replace('^','').replace('.','_')}_60m.parquet"); f60.index = f60.index.tz_convert(NY)
    ok_s = ok_e = n = 0
    for ts in f60.index[-400:]:
        h = f5[(f5.index >= ts) & (f5.index < ts + pd.Timedelta(hours=1))]
        if len(h) < 10: continue
        n += 1
        o5, hi5, lo5, c5 = h.Open.iloc[0], h.High.max(), h.Low.min(), h.Close.iloc[-1]
        r = f60.loc[ts]
        if abs(r.Open - o5) < 1e-9 * max(1, abs(o5)) and abs(r.High - hi5) < 1e-9 * max(1, abs(hi5)) and abs(r.Close - c5) < 1e-9 * max(1, abs(c5)): ok_s += 1
    print(sym, "matched bars (start-label, OHLC):", ok_s, "of", n)
