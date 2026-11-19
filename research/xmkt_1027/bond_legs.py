"""TLT pre-market move (prev close → last print before 09:15) ⇒ every target, MOO entry (09:30 open) or 09:45 entry,
exits 09:45/10:30/13:00/16:00. All three periods shown; follow only (the economic direction: bonds up → rate-sensitives up)."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, ".")
from research.xmkt_1027.prep import daily
from research.xmkt_1027.scan import st, D, cost
S = D["TLT"]; x = np.sign(np.log(S.pre915 / S.prev))
rows = []
for t, T in D.items():
    if t in ("TLT", "TMF", "IEF"): continue
    for ent, exs in (("o930", ("c945", "c1030", "c1300", "c1600")), ("c945", ("c1030", "c1300"))):
        for ex in exs:
            g = (x.reindex(T.index) * np.log(T[ex] / T[ent])).where(x.reindex(T.index) != 0).dropna() - 2 * cost(t)
            r = {}
            for lab, a, b in (("16-20", "2016", "2021"), ("21-23", "2021", "2024"), ("24-26", "2024", "2027")):
                s = st(g[(g.index >= a) & (g.index < b)]); r[lab] = s
            if all(r.values()):
                rows.append(dict(tgt=t, win=f"{ent[1:]}→{ex[1:]}", **{f"t{k}": v["t"] for k, v in r.items()},
                                 **{f"cagr{k}": v["cagr"] for k, v in r.items()}, dd=min(v["dd"] for v in r.values())))
R = pd.DataFrame(rows); R["minT"] = R[["t16-20", "t21-23", "t24-26"]].min(axis=1)
pd.set_option("display.width", 250)
print(R[R.minT > 1.5].sort_values("cagr24-26", ascending=False).round(2).to_string(index=False))
