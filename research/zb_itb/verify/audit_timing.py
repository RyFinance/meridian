"""Audit bar labeling and prices: yfinance 60m vs 5m vs daily for ITB and ZB=F (recent 60 days)."""
import numpy as np, pandas as pd
C = "research/zb_itb/verify/yf_cache/"
def ld(f):
    d = pd.read_parquet(C + f); d.index = d.index.tz_convert("America/New_York"); return d
i60, i5, i1d = ld("ITB_60m.parquet"), ld("ITB_5m.parquet"), pd.read_parquet(C + "ITB_1d.parquet")
z60, z5 = ld("ZB_F_60m.parquet"), ld("ZB_F_5m.parquet")
print("ITB 60m labels per day (time counts):", pd.Series(i60.index.time).value_counts().sort_index().to_dict())
print("ZB 60m label minutes:", sorted(set(i.minute for i in z60.index))[:5], " 5m label minutes sample:", sorted(set(i.minute for i in z5.index))[:12])
days = sorted(set(i5.index.normalize()) & set(i60.index.normalize()))
rows = []
for d in days:
    t930 = d + pd.Timedelta(hours=9, minutes=30)
    a, b = i60.loc[t930] if t930 in i60.index else None, i5.loc[t930] if t930 in i5.index else None
    t1025 = d + pd.Timedelta(hours=10, minutes=25)
    if a is None or b is None or t1025 not in i5.index: continue
    dd = pd.Timestamp(d.date())
    rows.append(dict(day=d.date(), o60=a.Open, o5=b.Open, o1d=i1d.loc[dd, "Open"] if dd in i1d.index else np.nan,
                     c60=a.Close, c5_1025=i5.loc[t1025, "Close"]))
r = pd.DataFrame(rows)
bp = lambda x, y: np.abs(np.log(x / y) * 1e4)
print(f"ITB days {len(r)} | 60m open vs 5m open: median |diff| {bp(r.o60, r.o5).median():.2f}bp max {bp(r.o60, r.o5).max():.2f} | 60m open vs daily open: median {bp(r.o60, r.o1d).median():.2f}bp max {bp(r.o60, r.o1d).max():.2f} | 60m close vs 5m 10:25 close: median {bp(r.c60, r.c5_1025).median():.2f}bp max {bp(r.c60, r.c5_1025).max():.2f}")
# ZB: is the 60m bar labeled 08:00 the 08:00-09:00 bar? compare to 5m bar labeled 08:55 (ends 09:00) and 09:55
zr = []
for d in sorted(set(z5.index.normalize())):
    for lab60, lab5_end, lab5_alt in [(8, (8, 55), (9, 55)), (15, (15, 55), (16, 55))]:
        t60 = d + pd.Timedelta(hours=lab60); t5 = d + pd.Timedelta(hours=lab5_end[0], minutes=lab5_end[1]); t5b = d + pd.Timedelta(hours=lab5_alt[0], minutes=lab5_alt[1])
        if t60 in z60.index and t5 in z5.index and t5b in z5.index:
            zr.append(dict(lab=lab60, start_label=bp(z60.loc[t60, "Close"], z5.loc[t5, "Close"]), end_label=bp(z60.loc[t60, "Close"], z5.loc[t5b, "Close"])))
z = pd.DataFrame(zr)
print("ZB 60m Close vs 5m closes (median |diff| bp): if START-labeled, 'start_label' ~0:\n", z.groupby("lab")[["start_label", "end_label"]].median().round(2), "\n n:", z.groupby("lab").size().to_dict())
