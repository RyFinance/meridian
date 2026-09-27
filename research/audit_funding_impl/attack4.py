import json, numpy as np, pandas as pd
from research.audit_funding_impl.replicate import *
d = pd.read_csv(OUT / "my_daily.csv", header=[0, 1], index_col=0, parse_dates=True)
b = d[("base", "net")]
def boot(x, B=5000, blk=21, seed=20260925):
    x = np.asarray(x); n = len(x); xc = x - x.mean(); rng = np.random.default_rng(seed); obs = x.mean(); nb = int(np.ceil(n / blk)); c = 0
    for _ in range(B):
        st = rng.integers(0, n - blk + 1, nb); c += np.concatenate([xc[i:i + blk] for i in st])[:n].mean() >= obs
    return (c + 1) / (B + 1)
R = {}
for name, x in {"from_2020-10-31(as-run live span)": b[b.index >= "2020-10-31"], "2021-2022": b[b.index >= "2021-01-01"],
                "ex_2021-01-28": b.drop(pd.Timestamp("2021-01-28"))}.items():
    R[name] = {"sharpe": sharpe(x), "p": boot(x.to_numpy()), "gate_1.8/sqrtT": 1.8 / np.sqrt(len(x) / 365)}
print(json.dumps(R, indent=1)); (OUT / "attack4.json").write_text(json.dumps(R, indent=1))
