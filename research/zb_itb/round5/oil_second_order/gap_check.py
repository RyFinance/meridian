"""Where does the oil move show up? Overnight gap (prior 16:00 close -> 09:30 open) vs first hour (09:30 open -> 10:30 close),
aligned with d = sign(CL 08:00 close / prior 15:00 close). Also dev/check split of the first-hour part."""
import pandas as pd, numpy as np
import importlib.util, sys
C = "research/zb_itb/round5/oil_second_order/cache/"
def ld(f):
    d = pd.read_parquet(C + f); d.index = d.index.tz_convert("America/New_York"); return d
def T(s): return pd.Timestamp(s).time()
def dayx(x): return x.index.normalize().tz_localize(None)
def dsig(fut):
    f = ld(f"{fut}_60m.parquet")
    c8 = f[f.index.time == T("08:00")]; c15 = f[f.index.time == T("15:00")]
    a = pd.Series(c8.Close.values, index=dayx(c8)); b = pd.Series(c15.Close.values, index=dayx(c15))
    days = sorted(set(dayx(ld("SPY_60m.parquet"))))
    d = {}
    for i in range(1, len(days)):
        D, P = days[i], days[i - 1]
        if D in a.index and P in b.index: d[D] = np.sign(np.log(a[D] / b[P]))
    return pd.Series(d)
def parts(stock):
    e = ld(f"{stock}_60m.parquet"); rows = {}
    for day, g in e.groupby(dayx(e)):
        o = g[g.index.time == T("09:30")]; x = g[g.index.time == T("09:30")]  # close of the 09:30-labeled bar = 10:30 ET
        prev = e[(e.index < g.index[0])]
        if len(o) == 0 or len(x) == 0 or len(prev) == 0: continue
        pc = prev[prev.index.time == T("15:30")]
        if len(pc) == 0: continue
        rows[day] = dict(gap=np.log(o.Open.iloc[0] / pc.Close.iloc[-1]), hour1=np.log(x.Close.iloc[0] / o.Open.iloc[0]))
    return pd.DataFrame(rows).T
DEV = (pd.Timestamp("2024-05-28"), pd.Timestamp("2025-06-30")); CHK = (pd.Timestamp("2025-07-01"), pd.Timestamp("2026-10-16"))
def st(x):
    x = x.dropna(); return len(x), x.mean() * 1e4, x.mean() / x.std() * np.sqrt(len(x)) if len(x) > 2 else np.nan
out = []
for fut, names in [("CL_F", ["USO", "XLE", "XLE", "JETS", "DAL", "UAL", "AAL", "LUV", "ALK", "CCL", "RCL", "NCLH", "ODFL", "JBHT", "FDX", "UPS", "DOW", "LYB", "VLO", "MPC", "PSX", "SPY"]),
                   ("NG_F", ["XLU", "NEE", "DUK", "CF", "NTR", "SPY"])]:
    d = dsig(fut)
    for n in dict.fromkeys(names):
        p = parts(n)
        j = p.join(d.rename("d"), how="inner"); j = j[j.d != 0]
        for lab, col in [("gap", "gap"), ("hour1", "hour1")]:
            for per, (a, b) in [("dev", DEV), ("chk", CHK)]:
                s = j.loc[(j.index >= a) & (j.index <= b)]
                n_, m, t = st(s[col] * s.d)
                out.append(dict(fut=fut, name=n, part=lab, period=per, n=n_, d_aligned_bp=round(m, 2), t=round(t, 2)))
O = pd.DataFrame(out)
pd.set_option("display.width", 200); pd.set_option("display.max_rows", 500)
print(O.pivot_table(index=["fut", "name", "part"], columns="period", values=["d_aligned_bp", "t"]).round(2).to_string())
O.to_csv("research/zb_itb/round5/oil_second_order/gap_check.csv", index=False)
