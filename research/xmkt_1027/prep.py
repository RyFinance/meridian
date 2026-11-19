"""Daily price table per symbol from 15-min SIP bars (bars are START-labeled, ET)."""
import pandas as pd, numpy as np
B = "research/xmkt_1027/bars/"
def daily(sym):
    d = pd.read_parquet(B + sym + ".parquet")
    d["day"] = d.t.dt.tz_localize(None).dt.normalize(); d["hm"] = d.t.dt.hour * 100 + d.t.dt.minute
    g = lambda hm, col: d[d.hm == hm].groupby("day")[col].last()
    pre = d[(d.hm >= 800) & (d.hm <= 900)].groupby("day").c.last()          # last pre-market print before 09:15
    out = pd.DataFrame({"pre915": pre, "o930": g(930, "o"), "c945": g(930, "c"), "c1000": g(945, "c"), "c1030": g(1015, "c"),
                        "c1130": g(1115, "c"), "c1300": g(1245, "c"), "c1530": g(1515, "c"), "c1600": g(1545, "c"),
                        "v": d[(d.hm >= 930) & (d.hm < 1600)].groupby("day").v.sum()}).sort_index()
    out = out[out.o930.notna() & out.c1600.notna()]
    out["prev"] = out.c1600.shift()
    return out
