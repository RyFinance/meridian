"""Frozen rule btc_cme_break (long BTC 17:00->18:00 ET, NYSE weekdays) on the sealed Coinbase window 2026-08-11..2026-10-16."""
import numpy as np, pandas as pd
b = pd.read_parquet("research/btc_ah/_sealed/btc_1m_holdout.parquet")
b["et"] = b.ts.dt.tz_convert("America/New_York"); s = b.set_index("et").close.sort_index()
days = pd.bdate_range("2026-08-11", "2026-10-16").difference(pd.to_datetime(["2026-09-07"]))  # Labor Day
r, plc = [], {h: [] for h in range(24)}
def px(t):
    i = s.index.searchsorted(t) - 1
    return s.iloc[i] if i >= 0 and t - s.index[i] < pd.Timedelta(minutes=5) else np.nan
for d in days:
    d = d.tz_localize("America/New_York")
    for h in range(24):
        a, z = px(d + pd.Timedelta(hours=h)), px(d + pd.Timedelta(hours=h + 1))
        if np.isfinite(a) and np.isfinite(z): plc[h].append(np.log(z / a))
x = pd.Series(plc[17]) * 1e4
print(f"17-18 ET n {len(x)} gross mean {x.mean():+.1f}bp t {x.mean()/x.std()*np.sqrt(len(x)):+.2f} win {(x>0).mean():.2f} | net@4bp {x.mean()-4:+.1f}bp")
print("other hours (placebo) mean bp:", {h: round(np.mean(v) * 1e4, 1) for h, v in plc.items()})
