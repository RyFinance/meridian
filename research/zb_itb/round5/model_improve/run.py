import numpy as np, pandas as pd, os, sys
from research.zb_itb.verify.f3_canonical import ld, C
O = "research/zb_itb/round5/model_improve/"
DEV = ("2024-05-28", "2025-06-30"); CHK = ("2025-07-01", "2026-10-16")
itb = ld("ITB_60m.parquet")
days = list(itb[itb.index.time == pd.Timestamp("09:30").time()].index.normalize())
def zseg(f):
    z = ld(f); rows = []
    for i in range(1, len(days)):
        D, p = days[i], days[i-1]
        g = lambda t: z.Close.get(t, np.nan)
        rows.append(dict(date=D.tz_localize(None), a=g(p+pd.Timedelta(hours=15)), b=g(D+pd.Timedelta(hours=7)), c=g(D+pd.Timedelta(hours=8))))
    r = pd.DataFrame(rows).set_index("date")
    return pd.DataFrame(dict(m=np.log(r.c/r.a), over=np.log(r.b/r.a), last=np.log(r.c/r.b)))
ZB, ZN = zseg("ZB_F_60m.parquet"), zseg("ZN_F_60m.parquet")
def legs(sym, path=None):
    if path: e = pd.read_parquet(path+f"{sym}_60m.parquet"); e.index = e.index.tz_convert("America/New_York"); d1 = pd.read_parquet(path+f"{sym}_1d.parquet")
    else: e = ld(f"{sym}_60m.parquet"); d1 = pd.read_parquet(C+f"{sym}_1d.parquet")
    rows = []
    for i in range(1, len(days)):
        D = days[i]; dd = pd.Timestamp(D.date()); day = e[(e.index >= D) & (e.index < D+pd.Timedelta(days=1))]
        pc = e.loc[e.index < D].Close.iloc[-1]
        gt = lambda h: day.Close.get(D+pd.Timedelta(hours=h), np.nan)
        rows.append(dict(date=dd, off=d1.Open.get(dd, np.nan), pc=pc, c1=gt(9.5), c2=gt(10.5), c3=gt(12.5), cC=gt(15.5)))
    r = pd.DataFrame(rows).set_index("date")
    return r
def tmask(ix, rng): return (ix >= rng[0]) & (ix <= rng[1])
def stats(p, n):
    p = p.dropna(); yrs = max((p.index[-1]-p.index[0]).days/365.25, 1e-9); eq = np.exp(p.cumsum())
    sd = p.std()
    return dict(n=int(n), mean=p.mean()*1e4, t=p.mean()/sd*np.sqrt(len(p)), sh=p.mean()/sd*np.sqrt(252), cagr=(eq.iloc[-1]**(1/yrs)-1)*100, dd=(eq/eq.cummax()-1).min()*100)
def run(name, L, d, w, cost_rt, exit_col="c1", exitprice=None):
    """d direction, w weight (pre-normalisation), L legs. gross uses exit price series."""
    xp = L[exit_col] if exitprice is None else exitprice
    gross = np.log(xp / L.off)
    ok = d.notna() & gross.notna() & w.notna()
    w = w.where(ok, 0.0).fillna(0.0)*(d.where(ok, 0.0).abs() > 0)
    dd = d.fillna(0)
    ix = L.index; dm = tmask(ix, DEV)
    k = 1.0/w[dm].abs().mean()
    wn = w*k
    # cost can be series or scalar
    pnl = wn*(dd*gross - cost_rt)*(w != 0)
    pnl = pnl.where(ok, 0.0)
    out = {}
    for lab, rng in [("dev", DEV), ("chk", CHK)]:
        mk = tmask(ix, rng)
        out[lab] = stats(pnl[mk], ((w != 0)[mk]).sum())
    res.append((name, out)); return pnl
res = []
Li = legs("ITB"); ix = Li.index
zb, zn = ZB.reindex(ix), ZN.reindex(ix)
m = zb.m; d0 = np.sign(m); one = pd.Series(1.0, index=ix)
CR = 0.0004
dm = tmask(ix, DEV)
sd_zb, sd_zn = m[dm].std(), zn.m[dm].std()
def up(wv): return wv
base = run("00 baseline ITB fixed (10:30)", Li, d0, one, CR)
# ---- sizing
avg = m.abs()/m[dm].abs().mean()
run("01 size |m| cap2", Li, d0, avg.clip(upper=2), CR)
vol = m.rolling(60, min_periods=10).std().shift(1)
run("02 size |m|/roll vol60 cap2", Li, d0, (m.abs()/vol).clip(upper=2/ (1)).fillna(1.0) if False else (m.abs()/vol/ (m.abs()/vol)[dm].mean()).clip(upper=2).fillna(1.0), CR)
run("03 size sqrt|m| cap2", Li, d0, (np.sqrt(m.abs())/np.sqrt(m.abs())[dm].mean()).clip(upper=2), CR)
run("04 filter |m|>dev median", Li, d0, (m.abs() > m[dm].abs().median()).astype(float), CR)
# ---- composite
mz = m/sd_zb + zn.m/sd_zn
run("05 ZN only", Li, np.sign(zn.m), one, CR)
run("06 avg ZB+ZN (std)", Li, np.sign(mz), one, CR)
agree = (np.sign(m) == np.sign(zn.m)).astype(float)
run("07 agree-only ZB&ZN", Li, d0, agree, CR)
run("08 overnight 16->08 only", Li, np.sign(zb.over), one, CR)
run("09 last hour 08->09 only", Li, np.sign(zb['last']), one, CR)
sv = zb.over/zb.over[dm].std() + 2*zb['last']/zb['last'][dm].std()
run("10 wtd over+2*last", Li, np.sign(sv), one, CR)
# ---- instrument
Lx = legs("XHB"); run("11 XHB", Lx, d0, one, CR)
bk = {s: legs(s) for s in ["DHI","LEN","PHM","TOL","KBH","NVR"]}
cside = {"DHI":2,"LEN":2,"PHM":2,"TOL":5,"KBH":5,"NVR":5}
Lb = pd.DataFrame({c: np.mean([np.log(bk[s][c]/bk[s].pc) for s in bk], axis=0) for c in ["off","c1","c2","c3","cC"]}, index=ix)
Lb = np.exp(Lb); Lb["pc"] = 1.0  # synthetic EW basket in price-relative terms
run("12 EW basket 6 names (3.5bp/side)", Lb, d0, one, 2*np.mean(list(cside.values()))/1e4)
Lm = pd.DataFrame({c: np.sqrt(Li[c]/Li.pc*Lx[c]/Lx.pc) for c in ["off","c1","c2","c3","cC"]}); Lm["pc"]=1.0
run("13 ITB+XHB avg (2bp/side)", Lm, d0, one, CR)
Ln = legs("NAIL", O)
run("14 NAIL (10bp/side)", Ln, d0, one, 0.0020)
run("14b NAIL (5bp/side)", Ln, d0, one, 0.0010)
# ---- exit
run("15 exit 11:30", Li, d0, one, CR, "c2")
run("16 exit 13:30 (c3)", Li, d0, one, CR, "c3")
run("17 exit close", Li, d0, one, CR, "cC")
prof = (d0*np.log(Li.c1/Li.off)) > 0
run("18 hold to close if profit@10:30", Li, d0, one, CR, exitprice=np.where(prof, Li.cC, Li.c1))
run("19 hold to 11:30 if profit@10:30", Li, d0, one, CR, exitprice=np.where(prof, Li.c2, Li.c1))
# ---- unpriced gap
gap = np.log(Li.off/Li.pc)
beta = (gap[dm]*m[dm]).sum()/(m[dm]**2).sum()
unp = beta*m - gap                       # expected catch-up at 09:30
run("20 d=sign(beta*m-gap)", Li, np.sign(unp), one, CR)
agree_u = (np.sign(unp) == d0).astype(float)
run("21 filter: open under-priced (d*unp>0)", Li, d0, agree_u, CR)
uw = (d0*unp/ (d0*unp)[dm].abs().mean()).clip(0, 2)
run("22 size by clipped d*unp (0..2)", Li, d0, uw, CR)
rem = beta*m - np.log(Li.c1/Li.pc)       # unpriced remaining at 10:30
ext = (d0*rem) > 0
run("23 extend to 11:30 if remaining unpriced>0", Li, d0, one, CR, exitprice=np.where(ext, Li.c2, Li.c1))
run("24 extend to 11:30 if rem>0 and profit", Li, d0, one, CR, exitprice=np.where(ext & prof, Li.c2, Li.c1))
run("25 filter: open under-priced + exit 11:30", Li, d0, agree_u, CR, "c2")
# ---- controls
run("C1 flip ITB", Li, -d0, one, CR)
Ls = legs("SPY"); run("C2 placebo SPY", Ls, d0, one, CR)
Lk = legs("KRE", None) if False else None
rows = []
for nm, o in res: rows.append(dict(variant=nm, **{f"{l}_{k}": v for l in o for k, v in o[l].items()}))
T = pd.DataFrame(rows); pd.set_option("display.width", 250)
cols = ["variant","dev_n","dev_mean","dev_t","dev_sh","dev_dd","chk_n","chk_mean","chk_t","chk_sh","chk_cagr","chk_dd"]
print(T[cols].round(2).to_string(index=False)); T.to_csv(O+"table.csv", index=False)
print("beta", beta, "variants", len(res))
# NAIL tracking
x = pd.DataFrame({"itb": np.log(Li.c1/Li.off), "nail": np.log(Ln.c1/Ln.off)}).dropna()
print("NAIL vs ITB first-hour: corr", x.corr().iloc[0,1].round(3), "slope", (x.cov().iloc[0,1]/x.itb.var()).round(2), "n", len(x))
print("NAIL median price", pd.read_parquet(O+"NAIL_1d.parquet").Close.tail(60).median(), "avg $vol 60d", (pd.read_parquet(O+"NAIL_1d.parquet")[["Close","Volume"]].tail(60).prod(axis=1)).mean())
print("ITB legs NaN counts", Li.isna().sum().to_dict())
