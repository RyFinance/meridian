"""Where does the edge accrue? ZB signal (yfinance) x builder basket 1m bars (vault), 2024-05..2026-09-16: mean signed return from 09:30 open to each minute, and from entry at minute k to 10:30."""
import numpy as np, pandas as pd
from research.zb_itb.verify.f3_canonical import build
from research.zb_itb.verify.long_history import load
sig = build(); sig = sig[sig.d.notna() & (sig.d != 0)].d
paths = []
for s in ["DHI", "LEN", "PHM", "TOL", "KBH", "NVR"]:
    d = load(s, "1m"); d = d[d.hm <= "10:30"]
    piv = d.pivot_table(index="day", columns="hm", values="close", aggfunc="last").ffill(axis=1)
    o = d.sort_values("et").groupby("day").open.first()  # first regular-session print at/after 09:30
    paths.append(np.log(piv.div(o, axis=0)))
P = pd.concat(paths, keys=range(len(paths))).groupby(level=1).mean()
P = P.reindex(sig.index).dropna(how="all"); s = sig.reindex(P.index)
cum = P.mul(s, axis=0).mean() * 1e4
print("n days", len(P)); print("cum signed basket return from 09:30 open (bp):", {k: round(cum[k], 1) for k in ["09:30", "09:31", "09:32", "09:35", "09:40", "09:45", "10:00", "10:15", "10:29"] if k in cum})
for k in ["09:31", "09:32", "09:35", "09:40", "09:45", "10:00"]:
    r = (P["10:29"] - P[k]).mul(s); r = r.dropna() - 0.0006
    print(f"enter at close of {k} bar -> 10:30: net {r.mean()*1e4:+.1f}bp t {r.mean()/r.std()*np.sqrt(len(r)):+.2f}")
