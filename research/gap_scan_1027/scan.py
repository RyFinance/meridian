"""Overnight futures move (15:00 prev ET bar close -> 08:00 ET bar close, start-labeled 60m) -> trade a target
from the 09:30 open to the close of the 09:30/10:30/12:30/15:30 bar. Direction (follow/fade) picked on the first half;
stats reported on the second half (pseudo-holdout). 5 bp/side cost. Daily, compounding, no leverage beyond the ETF's."""
import glob, numpy as np, pandas as pd
B = "research/gap_scan_1027/bars/"
def ld(s):
    d = pd.read_parquet(B + s.replace("=", "_") + ".parquet"); d.index = pd.DatetimeIndex(d.index).tz_convert("America/New_York"); return d
SIG = ["ZB=F", "ZN=F", "CL=F", "GC=F", "ES=F", "NQ=F", "RTY=F", "HG=F", "NG=F", "6J=F", "BTC-USD"]
TGT = [p.split("/")[-1][:-8] for p in glob.glob(B + "*.parquet")]
TGT = [t for t in TGT if t.replace("_", "=") not in SIG and t != "BTC-USD"]
HOLDS = {"10:30": 9.5, "11:30": 10.5, "13:30": 12.5, "16:00": 15.5}
def overnight(z):
    out = {}
    idx = z.index; days = sorted(set(idx.normalize()))
    c = z.Close
    for i in range(1, len(days)):
        D = days[i]; t1 = D + pd.Timedelta(hours=8)
        prev = c[(idx < D) & (idx.hour == 15)]
        if t1 in c.index and len(prev): out[D] = np.log(c[t1] / prev.iloc[-1])
    return pd.Series(out)
def stats(p):
    p = p.dropna(); 
    if len(p) < 60 or p.std() == 0: return None
    eq = np.exp(p.cumsum()); yrs = (p.index[-1] - p.index[0]).days / 365.25
    return dict(n=len(p), bp=p.mean()*1e4, t=p.mean()/p.std()*np.sqrt(len(p)), sharpe=p.mean()/p.std()*np.sqrt(252),
                cagr=eq.iloc[-1]**(1/yrs)-1, dd=(eq/eq.cummax()-1).min(), win=(p>0).mean())
sigs = {s: overnight(ld(s)) for s in SIG}
rows = []
for t in TGT:
    e = ld(t); first = e[e.index.time == pd.Timestamp("09:30").time()]
    o930 = pd.Series(first.Open.values, index=first.index.normalize())
    for hn, hh in HOLDS.items():
        h = int(hh); m = 30
        ex = e[(e.index.hour == h) & (e.index.minute == m)].Close
        ex.index = ex.index.normalize()
        r = np.log(ex / o930).dropna()
        for s, m_ in sigs.items():
            d = np.sign(m_.reindex(r.index)); p = (d * r).where(d != 0).dropna()
            if len(p) < 200: continue
            mid = p.index[len(p)//2]
            tr, te = p[p.index < mid], p[p.index >= mid]
            k = 1 if tr.mean() > 0 else -1
            net_te = k * te - 10e-4; net_all = k * p - 10e-4
            a, b = stats(net_te), stats(net_all); tt = stats(k*tr - 10e-4)
            if a and b and tt: rows.append(dict(sig=s, tgt=t, hold=hn, dir="follow" if k>0 else "fade", train_t=tt["t"],
                    te_cagr=a["cagr"], te_sharpe=a["sharpe"], te_t=a["t"], te_dd=a["dd"], te_bp=a["bp"], te_n=a["n"],
                    all_cagr=b["cagr"], all_sharpe=b["sharpe"], all_dd=b["dd"], all_win=b["win"]))
R = pd.DataFrame(rows); R.to_csv("research/gap_scan_1027/scan.csv", index=False)
print("combos", len(R))
ok = R[(R.train_t > 2) & (R.te_t > 2) & (R.te_sharpe > 1.2)].sort_values("te_cagr", ascending=False)
pd.set_option("display.width", 250)
print(ok.head(25).round(2).to_string(index=False))
