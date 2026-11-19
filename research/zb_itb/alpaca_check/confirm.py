"""Final confirmation with an independent price source (Alpaca SIP 1-minute bars, all US exchanges).
(1) 2024-05..2026-10: the live ZB signal (frozen yfinance futures bars), ITB/NAIL prices from Alpaca SIP:
    entry = open of the 09:30 minute, exit = close of the 10:29 minute. Compared trade-by-trade with yfinance.
(2) 2016..2026: tradable bond proxy that needs no futures data: d = sign(TLT last pre-market trade at or before 09:25 ET /
    TLT close of the 15:59 minute on the previous session). Requires a TLT print 08:00-09:25. Same ITB/NAIL trade.
(3) The live regime switch (past-only 60d corr of daily ITB vs TLT > 0) applied to (2)."""
import glob, numpy as np, pandas as pd
from research.zb_itb.verify.f3_canonical import build
B = "research/zb_itb/alpaca_check/bars/"
C = "research/zb_itb/verify/yf_cache/"


def load(sym):
    d = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(f"{B}{sym}_*.parquet"))])
    d["day"] = d.t.dt.tz_localize(None).dt.normalize(); d["mins"] = d.t.dt.hour * 60 + d.t.dt.minute
    return d


def daily(sym):
    d = load(sym)
    o930 = d[d.mins == 570].groupby("day").o.first(); c1029 = d[d.mins == 629].groupby("day").c.last()
    c1559 = d[d.mins == 959].groupby("day").c.last()
    pre = d[(d.mins >= 480) & (d.mins <= 565)].sort_values("t").groupby("day").c.last()      # last trade 08:00-09:25
    return pd.DataFrame({"o930": o930, "c1029": c1029, "c1559": c1559, "pre925": pre}).sort_index()


def stats(p, lab):
    p = p.dropna(); eq = np.exp(p.cumsum()); yrs = max((p.index[-1] - p.index[0]).days / 365.25, 1e-9)
    return (f"{lab:44s} n {len(p):4d} | avg {p.mean()*1e4:+6.1f}bp t {p.mean()/p.std()*np.sqrt(len(p)):+5.2f} | win {(p>0).mean():.1%} | "
            f"CAGR {(eq.iloc[-1]**(1/yrs)-1)*100:+5.0f}% | Sharpe {p.mean()/p.std()*np.sqrt(252):.2f} | maxDD {((eq/eq.cummax())-1).min()*100:.0f}%")


itb, nail, tlt = daily("ITB"), daily("NAIL"), daily("TLT")
cost = {"ITB": 0.0004, "NAIL": 0.0010}
print("== (1) 2024-26: live ZB signal, Alpaca SIP prices vs yfinance")
for sym, px in [("ITB", itb), ("NAIL", nail)]:
    y = build(sym); y = y[y.d.notna() & (y.d != 0)]
    a = (y.d * np.log(px.c1029 / px.o930).reindex(y.index)) - cost[sym]
    yy = y.g_h1 - cost[sym]
    j = pd.concat({"alp": a, "yf": yy}, axis=1).dropna()
    print(stats(j.alp, f"{sym} Alpaca SIP prices"))
    print(stats(j.yf, f"{sym} yfinance prices (same days)"))
    print(f"    per-trade correlation {j.alp.corr(j.yf):.3f}, mean |diff| {(j.alp - j.yf).abs().mean()*1e4:.1f}bp, days {len(j)}")
print("\n== (2) 2016-26: TLT pre-market (09:25) signal, fully tradable, Alpaca SIP prices")
sig = np.sign(np.log(tlt.pre925 / tlt.c1559.shift()))
ri = pd.read_parquet(C + "ITB_1d.parquet")["Adj Close"]; rt = pd.read_parquet(C + "TLT_1d.parquet")["Adj Close"]
corr = np.log(ri).diff().rolling(60).corr(np.log(rt).diff()).shift()
for sym, px in [("ITB", itb), ("NAIL", nail)]:
    p = (sig * np.log(px.c1029 / px.o930)).where(sig != 0) - cost[sym]
    p = p.dropna()
    print(stats(p, f"{sym} all days"))
    for a, b in [("2016", "2019"), ("2020", "2023"), ("2024", "2026")]:
        q = p[(p.index >= a) & (p.index <= b + "-12-31")]; print("   " + stats(q, f"{sym} {a}-{b}"))
    f = p[corr.reindex(p.index) > 0]
    print(stats(f, f"{sym} WITH regime switch (corr>0)"))
    for a, b in [("2016", "2019"), ("2020", "2023"), ("2024", "2026")]:
        q = f[(f.index >= a) & (f.index <= b + "-12-31")]; print("   " + stats(q, f"{sym} {a}-{b} switch on"))
zb = build("ITB"); zb = zb[zb.d.notna() & (zb.d != 0)]
s2 = sig.reindex(zb.index)
print(f"\nTLT-premarket vs ZB signal agreement 2024-26: {(s2 == zb.d).mean():.0%} of {s2.notna().sum()} days")
