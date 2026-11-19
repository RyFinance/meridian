"""Per-year flip numbers for the family C candidate and the family-C pass-through for ITB/XHB."""
import numpy as np, pandas as pd, pickle
import analyze as A, clean_grid as CG
from pathlib import Path
H = Path(__file__).parent
store = pd.read_pickle(H / "clean_store.pkl")
for name in ["C:ZB->ITB|follow|H1|k0.0", "C:ZB->ITB|follow|H1|k0.5", "C:ZB->ITB|follow|H1|k1.0"]:
    tr, fl = store[name]
    for lab, d in [("trade", tr), ("flip", fl)]:
        x = d.assign(yr=pd.to_datetime(d.D).dt.year).groupby("yr").net.agg(["count", "mean"]).round(4)
        print(name, lab, x.to_dict())
maps = CG.load_all(); days = CG.sessions(maps)
df = CG.build_clean("ZB", "ITB", maps, days)
df["D"] = pd.to_datetime(df.D).dt.date
for lab, m in [("dev", df.D < A.SPLIT), ("check", df.D >= A.SPLIT)]:
    d = df[m]
    b, t = A.ols(d.rS.values, d.G.values)
    b2, t2 = A.ols(d.rS.values, np.log(d.a_o/ d.c_o).values) if False else (np.nan, np.nan)
    b3, t3 = A.ols(d.rS.values, np.log(d.c_c / d.c_o).values)
    print(lab, "ITB overnight-gap beta", round(b, 3), "t", round(t, 1), "| 09:30->10:30 move beta", round(b3, 3), "t", round(t3, 1), "n", len(d))
