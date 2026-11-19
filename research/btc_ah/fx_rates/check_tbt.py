"""Sanity check of the pre-market fade on ZB->TBT: volume and gap sizes on the trades it selects."""
import numpy as np, pandas as pd
import analyze as A
from pathlib import Path

maps = {k: A.load(k) for k in ["6E_F", "6J_F", "6B_F", "ZN_F", "ZB_F", "TBT", "FXE"]}
raw = pd.read_parquet(Path(__file__).parent / "cache" / "TBT_1h.parquet")
raw = raw[raw.index.date <= A.CUT]
raw.index = raw.index.strftime("%Y-%m-%d %H:%M")
keys = [k for k in maps["FXE"] if k.endswith("09:30")]
days = sorted({pd.Timestamp(k[:10]).strftime("%Y-%m-%d") for k in keys})
df = A.add_resid(A.build("ZB", "TBT", maps, days))
sel = df[(df.z.abs() >= 1.0)].copy()
rows = []
for _, r in sel.iterrows():
    d = pd.Timestamp(r.D).strftime("%Y-%m-%d")
    v08 = raw.loc[f"{d} 08:00"] if f"{d} 08:00" in raw.index else None
    v09 = raw.loc[f"{d} 09:30"] if f"{d} 09:30" in raw.index else None
    rows.append(dict(D=d, rS_bp=round(1e4 * r.rS, 1), G_bp=round(1e4 * r.G, 1), R_bp=round(1e4 * r.R, 1),
                     gap_0900_0930_bp=round(1e4 * r.gap, 1),
                     vol08=None if v08 is None else int(v08.volume),
                     vol0930=None if v09 is None else int(v09.volume)))
out = pd.DataFrame(rows)
pd.set_option("display.width", 200)
print(out.to_string(index=False))
print("\nmedian vol08:", out.vol08.median(), " share with vol08==0:", round((out.vol08 == 0).mean(), 2))
