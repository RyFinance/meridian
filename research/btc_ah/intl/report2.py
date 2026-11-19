import pandas as pd, numpy as np, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from analyze import ld, ev_daily, ev_intra_asia, ev_europe, trades, ASIA, EURO, D_SPLIT, I_SPLIT
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
J = pd.read_csv(Path(__file__).parent / "rules_dev_check.csv")
J["sig"] = J["sig"].fillna("-")
def pick(idea, k=4):
    g = J[(J.idea==idea) & (J.n_dev>=30)].sort_values("mean_dev", ascending=False).head(k)
    return g
print("== 1b 60m top dev ==");   print(pick("1b_60m_1030")[["pair","sig","dir","n_dev","mean_dev","t_dev","flip_dev","n_chk","mean_chk","t_chk","flip_chk"]].round(4).to_string(index=False))
print("== 3 Europe top dev ==");  print(pick("3_europe_1030")[["pair","thr","sig","dir","n_dev","mean_dev","t_dev","flip_dev","n_chk","mean_chk","t_chk","flip_chk"]].round(4).to_string(index=False))
# worst-fill and per-year for top 3 overall dev daily/intraday
print("\n== Top 3 overall dev: worst-fill and per-year (net, decimal) ==")
top3 = J[J.n_dev>=30].sort_values("mean_dev", ascending=False).head(3)
print(top3[["idea","pair","thr","sig","dir","mean_dev","worst_dev","mean_chk","worst_chk"]].round(5).to_string(index=False))
# per-year for top3: recompute trades
def build(idea, pair, sig):
    A, H = pair.split("/")
    if idea=="1a_daily": return ev_daily(A,H), "sig"
    if idea=="1b_60m_1030": return ev_intra_asia(A,H), sig
    return ev_europe(A,H), sig
for _, r in top3.iterrows():
    e, s = build(r.idea, r.pair, r.sig)
    d = 1 if r.dir=="cont" else -1
    tr = trades(e, float(r.thr), d, s)
    tr["yr"] = tr.date.dt.year
    print(r.pair, r.dir, r.thr, "per-year n / mean net (bp)")
    print(tr.groupby("yr").net.agg(["size","mean"]).assign(mean=lambda x: (x["mean"]*1e4).round(1)).T.to_string())
# Idea 2: US session (ADR open->close) predicting next home-session return. NOT tradable as-is.
print("\n== Idea 2 (note only): corr(ADR open->close on D, home return on next home session) ==")
rows=[]
for A,H in ASIA:
    e = ev_daily(A,H).dropna(subset=["nxt"])
    oc = e.ex_c/e.en_o-1
    r = np.corrcoef(oc, e.nxt)[0,1]; n=len(e)
    rows.append((f"{A}/{H}", n, round(r,4), round(r*np.sqrt(n-2)/np.sqrt(1-r*r),2)))
print(pd.DataFrame(rows, columns=["pair","n","corr","t"]).to_string(index=False))
# Diagnostic: is the US open pricing the home move? slope of gap on home return and corr of open->close with home return
print("\n== Diagnostic: gap vs home return (daily), and open->close vs home return ==")
rows=[]
for A,H in ASIA:
    e = ev_daily(A,H).dropna(subset=["gap"])
    b = np.polyfit(e.sig, e.gap, 1)[0]
    oc = e.ex_c/e.en_o-1
    rows.append((f"{A}/{H}", len(e), round(np.corrcoef(e.sig,e.gap)[0,1],3), round(b,3), round(np.corrcoef(e.sig, oc)[0,1],3)))
print(pd.DataFrame(rows, columns=["pair","n","corr(hret,gap)","slope gap~hret","corr(hret,oc)"]).to_string(index=False))
