import numpy as np, pandas as pd
from research.btc_ah.lead_verify.resfade import run, st
names = ["MARA", "RIOT", "CLSK", "HUT", "CIFR", "WULF", "IREN", "BTBT", "MSTR"]
for thr in [0.0, 0.01, 0.02, 0.03, 0.05]:
    ps = []
    for t in names:
        x, p, r = run(t, thr=thr); ps.append(p)
    P = pd.concat(ps).sort_index()  # every trade (pooled)
    dev, chk = P[P.index < "2024-07-01"], P[P.index >= "2024-07-01"]
    print(f"thr {thr:.2f} DEV {st(dev)} | CHK {st(chk)} | 2026 {st(P[P.index>='2026'])}")
