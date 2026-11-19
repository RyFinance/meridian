"""Round 6 'uk': US Treasury-futures overnight move -> UK housebuilders at the London open (08:00 London entry).

Signal (per London session D, previous London session D'):
  ZB_LON: ln(ZB close of bar ending <= 08:00 London on D / ZB close of bar ending <= 16:30 London on D')
  ZN_LON: same with ZN=F
  ZB_US:  ln(ZB close ending <= 08:00 London on D / ZB close ending <= 16:00 ET on the last US date before that)
Bars are START-labeled 60m; 'bar ending <= T' = bar starting floor(T, 1h) - 1h, exact label, no fallback.
Entry = Open of the 08:00 London bar. Exits = Close of 08:00 bar (09:00), 09:00 bar (10:00), 16:00 bar (16:30 close),
and '1d' = daily close (daily Open->Close).
Costs: 10 bp per side (20 bp round trip). Stamp duty 50 bp on purchases of UK shares (d>0 longs) only.
"""
from pathlib import Path
import numpy as np, pandas as pd

D = Path(__file__).parent / "data"
ET, LON = "America/New_York", "Europe/London"
DEV = (pd.Timestamp("2024-05-28"), pd.Timestamp("2025-06-30"))
CHK = (pd.Timestamp("2025-07-01"), pd.Timestamp("2026-10-16"))
RT, STAMP = 0.0020, 0.0050
HB = ["PSN.L", "TW.L", "BKG.L", "BTRW.L", "VTY.L", "CRST.L"]
PLACEBO = ["VMID.L", "IDX_FTMC"]          # FTSE 250 ETF and index: no stamp duty (placebo)
CONTROL = ["LLOY.L"]                      # UK bank, rate-sensitive control, stamp applies
UK_SHARES = set(HB + CONTROL)


def fname(sym):
    return sym.replace("=", "_").replace("^", "IDX_").replace(".", "_")


def load60(sym, tz):
    d = pd.read_parquet(D / f"{fname(sym)}_60m.parquet")
    d.index = d.index.tz_convert(tz)
    return d


def key(ts):
    return ts.tz_convert("UTC").value


def make_map(df):
    return {key(t): c for t, c in zip(df.index, df["Close"])}


def close_ending_by(m, T):
    """Close of the bar ending at or before T (start-labeled bars): start = floor(T to hour) - 1h, exact label."""
    start = T.tz_convert(ET).floor("h") - pd.Timedelta(hours=1)
    return m.get(key(start), np.nan)


def bar(df, T):
    return df.loc[T] if T in df.index else None


zb = load60("ZB=F", ET); zn = load60("ZN=F", ET)
zbm, znm = make_map(zb), make_map(zn)
zb_days = set(zb.index.tz_convert(ET).normalize().date) if False else None
lon_cal_src = load60("LLOY.L", LON)
cal = sorted({t.date() for t in lon_cal_src.index if t.hour == 8 and t.minute == 0})
cal = [pd.Timestamp(x) for x in cal]

rows = []
names = HB + PLACEBO + CONTROL
stock60 = {s: load60(s, LON) for s in names}
d1 = {s: pd.read_parquet(D / f"{fname(s)}_1d.parquet") for s in names}
for s in names:
    d1[s].index = pd.to_datetime(d1[s].index).tz_localize(None) if d1[s].index.tz is None else pd.to_datetime(d1[s].index.tz_localize(None))

for i in range(1, len(cal)):
    Dd, Dp = cal[i], cal[i - 1]
    T_open = pd.Timestamp(Dd.date()).tz_localize(LON) + pd.Timedelta(hours=8)
    T_ref_lon = pd.Timestamp(Dp.date()).tz_localize(LON) + pd.Timedelta(hours=16, minutes=30)
    # most recent 16:00 ET close strictly before the London open (ET date k days back)
    T_ref_us = np.nan
    base = T_open.tz_convert(ET).normalize()
    for k in range(1, 8):
        cand = (base - pd.Timedelta(days=k)) + pd.Timedelta(hours=16)
        v = close_ending_by(zbm, cand)
        if not np.isnan(v):
            T_ref_us = v; break
    p_open_zb = close_ending_by(zbm, T_open)
    p_open_zn = close_ending_by(znm, T_open)
    p_ref_lon_zb = close_ending_by(zbm, T_ref_lon)
    p_ref_lon_zn = close_ending_by(znm, T_ref_lon)
    sig = {
        "ZB_LON": np.log(p_open_zb / p_ref_lon_zb),
        "ZN_LON": np.log(p_open_zn / p_ref_lon_zn),
        "ZB_US": np.log(p_open_zb / T_ref_us),
    }
    for s in names:
        df = stock60[s]
        e = df.index.get_indexer([T_open])[0]
        T_end16 = pd.Timestamp(Dd.date()).tz_localize(LON) + pd.Timedelta(hours=16)
        T_09 = T_open + pd.Timedelta(hours=1); T_10 = T_open + pd.Timedelta(hours=2)
        def cl(t):
            return df.loc[t, "Close"] if t in df.index else np.nan
        entry = df.loc[T_open, "Open"] if T_open in df.index else np.nan
        x08, x09, x1630 = cl(T_open), cl(T_09), cl(T_end16)
        if Dd in d1[s].index:
            d_open, d_close = d1[s].loc[Dd, "Open"], d1[s].loc[Dd, "Close"]
        else:
            d_open = d_close = np.nan
        rows.append(dict(date=Dd, sym=s, entry=entry, x08=x08, x09=x09, x1630=x1630, x1d=d_close, d_open=d_open,
                         **{f"sig_{k}": v for k, v in sig.items()}))

R = pd.DataFrame(rows)
R.to_pickle(Path(__file__).parent / "panel.pkl")
print("panel rows", len(R), "dates", R.date.nunique(), "span", R.date.min().date(), R.date.max().date())
print("signal nan share:", {k: round(float(R[f"sig_{k}"].isna().mean()), 3) for k in ["ZB_LON", "ZN_LON", "ZB_US"]})
print("zero signals:", {k: int((R[f"sig_{k}"] == 0).sum()) for k in ["ZB_LON", "ZN_LON", "ZB_US"]})
