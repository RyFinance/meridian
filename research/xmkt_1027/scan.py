"""Cross-market intraday scan, 2016-2026, 15-min SIP bars.
Splits: DISCOVERY 2016-2020 · VALIDATION 2021-2023 · HOLDOUT 2024-2026 (scored only with --holdout, once).
Families
  A  intraday momentum  : x = signal-ETF move prev close→T1 (T1 = 10:00 / 15:30); trade target 15:30→16:00, sign(x)
  B  overnight          : hold target close→next 09:30 open, unconditional and conditional on the day's/last-30m sign
  C  pre-market lead    : x = signal-ETF pre-market move (prev close→last print before 09:15); trade target 09:30→{10:30,13:00,16:00}
  D  gap, late entry    : x = target's own gap (prev close→09:30 open); trade target 10:00→16:00 (no open-print fill)
Every rule trades target T in direction k·sign(x); k (follow/fade) is chosen on DISCOVERY only."""
import sys, glob, itertools, numpy as np, pandas as pd
sys.path.insert(0, ".")
from research.xmkt_1027.prep import daily
LIQ = set("SPY QQQ IWM DIA TQQQ SQQQ SPXL UPRO SOXL SMH TLT IEF GLD SLV XLE XLF EEM HYG LQD FXI EWZ KRE GDX USO XLU VNQ XHB ITB TNA".split())
def cost(t): return (2 if t in LIQ else 6) / 1e4          # per side
syms = sorted(p.split("/")[-1][:-8] for p in glob.glob("research/xmkt_1027/bars/*.parquet"))
D = {s: daily(s) for s in syms}
def split(p):
    p = p.dropna()
    return p[p.index < "2021"], p[(p.index >= "2021") & (p.index < "2024")], p[p.index >= "2024"]
def st(p):
    p = p.dropna()
    if len(p) < 80 or p.std() == 0: return None
    yrs = max((p.index[-1] - p.index[0]).days / 365.25, .5); eq = np.exp(p.cumsum())
    return dict(n=len(p), bp=p.mean() * 1e4, t=p.mean() / p.std() * np.sqrt(len(p)), cagr=eq.iloc[-1] ** (1 / yrs) - 1,
                dd=(eq / eq.cummax() - 1).min(), sh=p.mean() / p.std() * np.sqrt(252 * len(p) / max(1, (p.index[-1]-p.index[0]).days*252/365.25)))
rows = []
def test(fam, desc, x, y, tgt, holdout=False):
    x = x.reindex(y.index); d = np.sign(x)
    g = (d * y).where(d != 0).dropna()
    a, b, h = split(g)
    if len(a) < 150 or len(b) < 100: return
    k = 1 if a.mean() > 0 else -1
    c = 2 * cost(tgt)
    sa, sb = st(k * a - c), st(k * b - c)
    if not sa or not sb: return
    r = dict(fam=fam, rule=desc, tgt=tgt, dir="follow" if k > 0 else "fade", d_t=sa["t"], d_bp=sa["bp"], v_t=sb["t"], v_bp=sb["bp"],
             v_cagr=sb["cagr"], v_dd=sb["dd"], v_n=sb["n"])
    if holdout:
        sh = st(k * h - c); r.update(h_t=sh["t"], h_bp=sh["bp"], h_cagr=sh["cagr"], h_dd=sh["dd"], h_n=sh["n"]) if sh else None
    rows.append(r)
def run(holdout=False):
    for t, T in D.items():
        lr = lambda a, b: np.log(T[b] / T[a])
        ylate = lr("c1530", "c1600")
        # A: intraday momentum (signals: own + SPY/QQQ/IWM/TLT)
        for s in set([t, "SPY", "QQQ", "IWM", "TLT"]) & set(D):
            S = D[s]
            for t1 in ("c1000", "c1530"):
                test("A", f"{s} prev→{t1[1:]} ⇒ {t} 15:30→16:00", np.log(S[t1] / S.prev), ylate, t, holdout)
        # B: overnight hold, conditioned on own day / last 30m
        on = np.log(T.o930.shift(-1) / T.c1600)
        test("B", f"{t} overnight | sign(day)", np.log(T.c1600 / T.prev), on, t, holdout)
        test("B", f"{t} overnight | sign(last30m)", ylate, on, t, holdout)
        test("B", f"{t} overnight | always", pd.Series(1.0, index=T.index), on, t, holdout)
        # D: own gap, late entry
        gap = np.log(T.o930 / T.prev)
        test("D", f"{t} own gap ⇒ 10:00→16:00", gap, lr("c1000", "c1600"), t, holdout)
        test("D", f"{t} own gap ⇒ 10:00→13:00", gap, lr("c1000", "c1300"), t, holdout)
        # C: pre-market lead from every other symbol
        for s, S in D.items():
            if s == t: continue
            x = np.log(S.pre915 / S.prev)
            for ex in ("c1030", "c1300", "c1600"):
                test("C", f"{s} pre-mkt ⇒ {t} 09:30→{ex[1:]}", x, lr("o930", ex), t, holdout)
if __name__ == "__main__":
    ho = "--holdout" in sys.argv
    run(ho)
    R = pd.DataFrame(rows); R.to_csv("research/xmkt_1027/scan" + ("_holdout" if ho else "") + ".csv", index=False)
    print(len(syms), "symbols ·", len(R), "rules")
    ok = R[(R.d_t > 2.5) & (R.v_t > 2.0)].sort_values("v_cagr", ascending=False)
    pd.set_option("display.width", 260); pd.set_option("display.max_colwidth", 48)
    print(len(ok), "pass discovery t>2.5 AND validation t>2"); print(ok.head(40).round(2).to_string(index=False))
