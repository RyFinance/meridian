import numpy as np, pandas as pd, yfinance as yf, warnings
warnings.filterwarnings("ignore")
from research.zb_itb.verify.f3_canonical import build, ld, C
OUT = "research/zb_itb/round6/events/"
# ---- release dates FROM MEMORY (official schedules) ----
CPI = "2024-05-15 2024-06-12 2024-07-11 2024-08-14 2024-09-11 2024-10-10 2024-11-13 2024-12-11 2025-01-15 2025-02-12 2025-03-12 2025-04-10 2025-05-13 2025-06-11 2025-07-15 2025-08-12 2025-09-11 2025-10-24 2025-12-18 2026-01-13 2026-02-13 2026-03-11 2026-04-10 2026-05-12 2026-06-10 2026-07-14 2026-08-12 2026-09-11 2026-10-14".split()
NFP = "2024-06-07 2024-07-05 2024-08-02 2024-09-06 2024-10-04 2024-11-01 2024-12-06 2025-01-10 2025-02-07 2025-03-07 2025-04-04 2025-05-02 2025-06-06 2025-07-03 2025-08-01 2025-09-05 2025-11-20 2025-12-16 2026-01-09 2026-02-11 2026-03-06 2026-04-03 2026-05-08 2026-06-05 2026-07-02 2026-08-07 2026-09-04 2026-10-02".split()
PCE = "2024-05-31 2024-06-28 2024-07-26 2024-08-30 2024-09-27 2024-10-31 2024-11-27 2024-12-20 2025-01-31 2025-02-28 2025-03-28 2025-04-30 2025-05-30 2025-06-27 2025-07-31 2025-08-29 2025-09-26 2025-12-05 2026-01-22 2026-02-20 2026-03-13 2026-04-09 2026-04-30 2026-05-28 2026-06-25 2026-07-30 2026-08-26 2026-09-30 2026-10-29".split()
FOMC = "2024-06-12 2024-07-31 2024-09-18 2024-11-07 2024-12-18 2025-01-29 2025-03-19 2025-05-07 2025-06-18 2025-07-30 2025-09-17 2025-10-29 2025-12-10 2026-01-28 2026-03-18 2026-04-29 2026-06-17 2026-07-29 2026-09-16 2026-10-28".split()
# spot check vs calendar
cal = pd.read_csv("/Users/rytty/CCP/polymarket_arb/state/cache/economic_calendar.csv", low_memory=False)
cal = cal[(cal.region_code == "US") & (cal.date >= "2024-05-01") & (cal.date <= "2026-10-31")]
chk = {"CPI": (CPI, "^Inflation Rate MoM"), "NFP": (NFP, "^Non Farm Payrolls"), "PCE": (PCE, "^PCE Price Index MoM"), "FOMC": (FOMC, "Fed Interest Rate Decision")}
chk_lines = []
for k, (lst, pat) in chk.items():
    cs = set(cal[cal.event.str.contains(pat)].date); ms = set(lst)
    chk_lines.append(f"- {k}: memory {len(ms)}, calendar {len(cs)}, in both {len(ms&cs)}; memory-only {sorted(ms-cs)}; calendar-only {sorted(cs-ms)}")
print("\n".join(chk_lines))

# ---- base trades ----
r = build("ITB"); r = r[r.d.notna() & (r.d != 0)].copy()
r["net"] = r.g_off - 0.0004
r = r[r.net.notna()]
days = r.index
# trading-day calendar from ITB 60m
e = ld("ITB_60m.parquet"); tdays = pd.DatetimeIndex(sorted(set(e.index.normalize().tz_localize(None))))
prev_td = pd.Series(tdays[:-1], index=tdays[1:])
r["prev_td"] = prev_td.reindex(r.index)
r["dow"] = r.index.dayofweek
# after holiday: a weekday strictly between prev trading day and D (excl. weekends)
def after_hol(D, P):
    return any(x.dayofweek < 5 for x in pd.date_range(P + pd.Timedelta(days=1), D - pd.Timedelta(days=1)))
r["after_hol"] = [after_hol(D, P) for D, P in zip(r.index, r.prev_td)]
def tab(groups, base=r, col="net"):
    rows = []
    for name, msk in groups:
        x = base.loc[msk, col].dropna()
        n = len(x)
        if n < 2: rows.append((name, n, np.nan, np.nan, np.nan)); continue
        rows.append((name, n, x.mean()*1e4, x.mean()/x.std()*np.sqrt(n), (x > 0).mean()*100))
    t = pd.DataFrame(rows, columns=["group", "n", "mean_net_bp", "t", "win_%"])
    return t.round(1).to_markdown(index=False)
md = []
def sec(h, body): md.append(f"\n## {h}\n\n{body}\n")

ix = r.index.strftime("%Y-%m-%d")
isin = lambda L: pd.Series(ix.isin(L), index=r.index)
fomc_next = set()
for f in FOMC:
    i = tdays.searchsorted(pd.Timestamp(f), side="right")
    if i < len(tdays): fomc_next.add(tdays[i].strftime("%Y-%m-%d"))
cpi, nfp, pce, fn, fd = isin(CPI), isin(NFP), isin(PCE), isin(fomc_next), isin(FOMC)
anyev = cpi | nfp | pce | fn | fd
mon = r.dow == 0
macro = [("ALL", pd.Series(True, index=r.index)), ("CPI day", cpi), ("NFP day", nfp), ("PCE day", pce), ("FOMC decision day", fd), ("Day after FOMC", fn),
         ("Any of the above", anyev), ("Other days (none of the above)", ~anyev), ("Monday (weekend gap)", mon), ("Non-Monday", ~mon),
         ("First day after weekday holiday", r.after_hol), ("Mon excl. holiday", mon & ~r.after_hol)]
sec("1. Macro days", "Release dates are hard-coded FROM MEMORY of the official schedules (BLS, BEA, FOMC). Spot-check against polymarket_arb economic_calendar.csv (US rows):\n\n" + "\n".join(chk_lines) +
    "\n\nCategories overlap (e.g. PCE and FOMC can coincide); 'Other' excludes all five. Net = g_off - 4 bp (2 bp/side), official open entry, 10:30 exit.\n\n" + tab(macro))
# weekday for completeness
sec("1b. By weekday", tab([(n, r.dow == i) for i, n in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri"])]))

# ---- regime ----
z1 = pd.read_parquet(C + "ZB_F_1d.parquet"); z1.index = pd.to_datetime(z1.index).tz_localize(None).normalize()
zr = np.log(z1.Close).diff()
zvol = zr.rolling(20).std().shift(1) * np.sqrt(252) * 100  # uses returns through D-1
tnx = yf.download("^TNX", start="2024-01-01", end="2026-10-20", progress=False, auto_adjust=False)
tnx = tnx["Close"].squeeze(); tnx.index = pd.to_datetime(tnx.index).tz_localize(None).normalize()
tl = tnx.shift(1); tchg = (tnx.shift(1) - tnx.shift(21))
i1 = pd.read_parquet(C + "ITB_1d.parquet"); i1.index = pd.to_datetime(i1.index).tz_localize(None).normalize()
iret = (np.log(i1.Close).shift(1) - np.log(i1.Close).shift(21))
r["zvol"] = zvol.reindex(r.index); r["tnx"] = tl.reindex(r.index); r["tchg"] = tchg.reindex(r.index); r["iret"] = iret.reindex(r.index)
def terc(col, lab):
    q = r[col].quantile([1/3, 2/3]).values
    return [(f"{lab} low (<={q[0]:.2f})", r[col] <= q[0]), (f"{lab} mid", (r[col] > q[0]) & (r[col] <= q[1])), (f"{lab} high (>{q[1]:.2f})", r[col] > q[1])]
reg = terc("zvol", "ZB 20d vol ann%") 
sec("2a. ZB trailing 20d realized vol (terciles, features use data through D-1; cutoffs full-sample)", tab(reg))
sec("2b. 10Y yield level (^TNX close D-1, terciles) and 20d trend", tab(terc("tnx", "10Y level %") + [("10Y rising over 20d", r.tchg > 0), ("10Y falling over 20d", r.tchg <= 0)] + terc("tchg", "10Y 20d chg (pts)")))
sec("2c. ITB trailing 20d return (close D-1 vs close D-21, terciles)", tab(terc("iret", "ITB 20d ret")))
# interaction: direction vs trend
sec("2d. Signal direction vs 10Y trend (long ITB = ZB up = yields down)", tab([("long, 10Y falling", (r.d > 0) & (r.tchg <= 0)), ("long, 10Y rising", (r.d > 0) & (r.tchg > 0)), ("short, 10Y falling", (r.d < 0) & (r.tchg <= 0)), ("short, 10Y rising", (r.d < 0) & (r.tchg > 0))]))

# ---- signal size ----
mm = pd.read_csv("research/zb_itb/verify/f3_trades_canonical.csv", index_col=0, parse_dates=True)["m"]
sd60 = mm.rolling(60, min_periods=30).std().shift(1)
r["z"] = (r.m.abs() / sd60.reindex(r.index))
zq = r.z.dropna()
bins = [0, .25, .5, .75, 1, 1.5, 2, 99]
zg = [(f"|z| {bins[i]}-{bins[i+1] if bins[i+1]<99 else 'inf'}", (r.z > bins[i]) & (r.z <= bins[i+1])) for i in range(len(bins)-1)]
zg += [("|z| < 0.5", r.z < .5), ("|z| >= 0.5", r.z >= .5), ("|z| < 1", r.z < 1), ("|z| >= 1", r.z >= 1)]
sec("3. Signal size z = |m| / trailing 60d stdev of m (past-only)", tab(zg) + "\n\nGross (before cost), same bins, to see whether small trades are noise or just cost-killed:\n\n" + tab(zg[:7], col="g_off") +
    f"\n\nCorrelation of |z| with signed gross return: {np.corrcoef(r.z.dropna(), r.loc[r.z.dropna().index,'g_off'])[0,1]:.3f}; with raw ITB first-hour |return|: {np.corrcoef(r.z.dropna(), (np.log(r.exit/r.entry_off)).abs().loc[r.z.dropna().index])[0,1]:.3f}")
q5 = pd.qcut(r.z, 5, labels=False); sec("3b. |z| quintiles", tab([(f"Q{i+1}", q5 == i) for i in range(5)]))

# ---- overnight path ----
zb = ld("ZB_F_60m.parquet").Close
def c_at(ts, tol="3h"):
    s = zb[zb.index <= ts]
    if len(s) == 0 or ts - s.index[-1] > pd.Timedelta(tol): return np.nan
    return s.iloc[-1]
rows = []
for D in r.index:
    D0 = pd.Timestamp(D).tz_localize("America/New_York")
    P = pd.Timestamp(r.loc[D, "prev_td"]).tz_localize("America/New_York")
    c15 = zb.get(P + pd.Timedelta(hours=15), np.nan)
    c19 = c_at((D0 - pd.Timedelta(days=1)) + pd.Timedelta(hours=19))
    c01 = c_at(D0 + pd.Timedelta(hours=1)); c07 = c_at(D0 + pd.Timedelta(hours=7)); c08 = zb.get(D0 + pd.Timedelta(hours=8), np.nan)
    rows.append(dict(date=D, s1=np.log(c19/c15), s2=np.log(c01/c19), s3=np.log(c07/c01), s4=np.log(c08/c07)))
seg = pd.DataFrame(rows).set_index("date")
r = r.join(seg)
r["sumseg"] = r[["s1","s2","s3","s4"]].sum(axis=1, skipna=False)
r["ret"] = np.log(r.exit / r.entry_off)  # raw (unsigned) ITB first-hour return, official open entry
import statsmodels.api as sm
names = {"s1": "16-20", "s2": "20-02", "s3": "02-08", "s4": "08-09"}
dd = r.dropna(subset=["s1","s2","s3","s4","ret"])
X = dd[["s1","s2","s3","s4"]] * 1e4  # bp
res = sm.OLS(dd.ret*1e4, sm.add_constant(X)).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
Xs = (X / X.std())
res2 = sm.OLS(dd.ret*1e4, sm.add_constant(Xs)).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
rg = pd.DataFrame({"segment": [names[k] for k in X.columns], "seg stdev bp": X.std().values, "beta (ITB bp per ZB bp)": res.params[1:].values, "t (HAC)": res.tvalues[1:].values, "std beta (ITB bp per 1sd)": res2.params[1:].values, "std t": res2.tvalues[1:].values}).round(2)
res_all = sm.OLS(dd.ret*1e4, sm.add_constant(dd.sumseg*1e4)).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
uni = []
for k in X.columns:
    ru = sm.OLS(dd.ret*1e4, sm.add_constant(X[k])).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
    # sign-rule result using this segment alone
    sg = np.sign(dd[k]) * dd.ret - 0.0004
    uni.append((names[k], ru.params[k], ru.tvalues[k], ru.rsquared*100, sg.mean()*1e4, sg.mean()/sg.std()*np.sqrt(len(sg)), (np.sign(dd[k]) == np.sign(dd.m)).mean()*100))
ut = pd.DataFrame(uni, columns=["segment", "beta", "t", "R2 %", "sign-rule net bp", "sign-rule t", "sign agrees w/ full m %"]).round(2)
sec("4. Overnight path (ZB 60m, segments 16:00-20:00, 20:00-02:00, 02:00-08:00, 08:00-09:00 ET; n=%d)" % len(dd),
    "Multivariate OLS of ITB raw first-hour return (09:30 official open -> 10:30 close, bp) on the four ZB segment returns (bp). HAC(5) t.\n\n" + rg.to_markdown(index=False) +
    f"\n\nAll four segments summed (= m): beta {res_all.params.iloc[1]:.3f}, t {res_all.tvalues.iloc[1]:.2f}, R2 {res_all.rsquared*100:.1f}%. Multivariate R2 {res.rsquared*100:.1f}%.\n\nUnivariate (each segment alone) and what the sign rule earns if only that segment is used:\n\n" + ut.to_markdown(index=False))
# segment-sum check
sec("4b. Sum-of-segments sanity", f"max |s1+s2+s3+s4 - m| (bp) = {((dd.sumseg-dd.m).abs().max()*1e4):.2f}; segments computed with 'last bar at or before' on calendar evening before D (handles Sunday-open / holidays), missing >3h => dropped.")
# when segments disagree
r["agree_early"] = np.sign(r.s1 + r.s2 + r.s3) == np.sign(r.s4)
dd = r.dropna(subset=["s1","s2","s3","s4"])
sec("4c. Overnight (16:00-08:00) vs last hour (08:00-09:00) direction", tab([("last hour same sign as earlier overnight", dd.agree_early), ("last hour opposes earlier overnight", ~dd.agree_early)], base=dd))

# ---- capacity ----
cap = e[e.index.time == pd.Timestamp("09:30").time()].copy(); cap.index = cap.index.normalize().tz_localize(None)
cap["px"] = (cap.Open + cap.Close) / 2; cap["dv"] = cap.Volume * cap.px
dv = cap.dv.reindex(r.index)
last6 = cap.dv[cap.index >= cap.index[-1] - pd.Timedelta(days=180)]
capmd = f"""ITB 09:30-10:30 60m bar: Volume x (open+close)/2, trade days n={dv.notna().sum()}.

| stat | $ first-hour volume | 1% of it |
|---|---|---|
| mean | {dv.mean()/1e6:.1f}M | ${dv.mean()*.01/1e3:.0f}k |
| median | {dv.median()/1e6:.1f}M | ${dv.median()*.01/1e3:.0f}k |
| 10th pct | {dv.quantile(.1)/1e6:.1f}M | ${dv.quantile(.1)*.01/1e3:.0f}k |
| min | {dv.min()/1e6:.1f}M | ${dv.min()*.01/1e3:.0f}k |
| last 180d mean | {last6.mean()/1e6:.1f}M | ${last6.mean()*.01/1e3:.0f}k |

Mean by year: {', '.join(f'{y}: {v/1e6:.1f}M' for y, v in dv.groupby(dv.index.year).mean().items())}.
Caveat: 09:30 bar volume includes the opening auction. The volume the strategy adds is MOO (auction) + continuous trading in the same hour; a 1% participation rule on the whole hour is a rough guide. Edge diffuses in 45 min, so own impact scales with size; the 5 bp/side breakeven check (+16 bp) in VERIFICATION gives some room. The signed day-by-day edge vs first-hour dollar volume tercile:

""" + tab([(f"$vol {l}", m) for l, m in [("low", dv <= dv.quantile(1/3)), ("mid", (dv > dv.quantile(1/3)) & (dv <= dv.quantile(2/3))), ("high", dv > dv.quantile(2/3))]])
sec("5. Capacity", capmd)
r.drop(columns=["prev_td"]).to_csv(OUT + "event_table.csv")
head = f"# Round 6 events: when does ZB -> ITB pay?\n\nFrozen helper build('ITB'), net = g_off - 4 bp (official-open entry, 10:30 exit, 2 bp/side), n={len(r)} trades, mean {r.net.mean()*1e4:.1f} bp, t {r.net.mean()/r.net.std()*np.sqrt(len(r)):.1f}. Diagnostic only; all splits are post-hoc and many cells are small. t ~ 2 in a thin cell is not evidence."
open(OUT + "RESULTS_body.md", "w").write(head + "\n" + "\n".join(md))
print(head); print("\n".join(md))
