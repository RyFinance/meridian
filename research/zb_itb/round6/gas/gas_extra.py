"""Pooled family tests and SPY-hedged (target minus SPY, same signal and window) checks for top picks.
Imports the frozen logic from gas_test.py (run as module, prints suppressed)."""
import io, contextlib, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
with contextlib.redirect_stdout(io.StringIO()):
    import gas_test as G
def trades(sig, sym, exit_key, sign=1):
    t = G.TG[sym]; d = G.FUT[sig].reindex(t.index).dropna() * sign; d = d[d != 0]
    cost = G.side_cost(t.adv.median()) if sym != "SPY" else 2.0
    return ((d * t.loc[d.index, exit_key]) - 2 * cost / 1e4).dropna()
def hedged(sig, sym, exit_key):
    t = G.TG[sym]; s = G.TG["SPY"]
    idx = t.index.intersection(s.index)
    d = G.FUT[sig].reindex(idx).dropna(); d = d[d != 0]
    cost = G.side_cost(t.adv.median())
    ex = (t.loc[d.index, exit_key] - s.loc[d.index, exit_key])
    return ((d * ex) - 2 * cost / 1e4 - 2 * 2 / 1e4).dropna()  # long target, short SPY (both legs, costs both)
def pooled(sig, syms, exit_key):
    parts = {}
    for s in syms:
        if s not in G.TG: continue
        parts[s] = trades(sig, s, exit_key)
    out = {}
    for w, (a, b) in {"dev": G.DEV, "chk": G.CHK}.items():
        ser = pd.concat([p.loc[a:b] for p in parts.values()]).sort_index()
        # equal weight per name: average the per-name daily means
        per = pd.concat([p.loc[a:b] for p in parts.values()], axis=1).mean(axis=1).dropna()
        out[w] = G.stats(per)
    return out
rows = []
for name, sig, syms in [("gas-pool NG", "NG", G.GAS), ("oil-pool CL", "CL", G.OIL)]:
    for ek in ["x1030", "x1130", "xc"]:
        p = pooled(sig, syms, ek)
        rows.append(dict(test=name, exit=ek, dev_bp=p["dev"]["mean"], dev_t=p["dev"]["t"], chk_bp=p["chk"]["mean"], chk_t=p["chk"]["t"], n_chk=p["chk"]["n"]))
for sig, sym, ek in [("NG","EQT","x1130"),("NG","EQT","x1030"),("NG","EXE","x1030"),("NG","EXE","x1130"),("NG","LNG","x1030"),("CL","XLE","xc"),("CL","XOP","x1030")]:
    h_dev = hedged(sig, sym, ek).loc[G.DEV[0]:G.DEV[1]]; h_chk = hedged(sig, sym, ek).loc[G.CHK[0]:G.CHK[1]]
    sd, sc = G.stats(h_dev), G.stats(h_chk)
    rows.append(dict(test=f"hedged {sym} vs SPY ({sig})", exit=ek, dev_bp=sd["mean"], dev_t=sd["t"], chk_bp=sc["mean"], chk_t=sc["t"], n_chk=sc["n"]))
R = pd.DataFrame(rows)
pd.set_option("display.width", 200)
print(R.round(2).to_string(index=False))
