"""Forward 1-year Monte Carlo: bootstrap historical per-trade returns (4-trade blocks), fixed fraction of equity
in premium per trade. Also a 'shrunk' case: every trade return shifted so the mean is halved (overfit haircut)."""
import numpy as np, pandas as pd
from pathlib import Path
H = Path(__file__).parent
res = pd.read_pickle(H / "trades.pkl")
rng = np.random.default_rng(7)
N, PATHS = 104, 20000
def sim(r, f):
    r = np.asarray(r); nb = N // 4
    starts = rng.integers(0, len(r) - 4, (PATHS, nb))
    x = r[(starts[:, :, None] + np.arange(4)).reshape(PATHS, -1)]
    eq = np.cumprod(1 + f * x, axis=1)
    dd = (eq / np.maximum.accumulate(eq, axis=1) - 1).min(1)
    return eq[:, -1], dd
rows = []
for key, lab in [(("RAW", "OTM1", 1.0), "RAW OTM1 Mon+Fri"), (("RAW", "OTM1", 2.0), "RAW OTM1 Mon+Fri stress-cost")]:
    t = res[key]
    for sub, nm in [(t, ""), (t[t.dow == 4], " Fri-only")]:
        for haircut in [False, True]:
            r = sub.ret.values - (sub.ret.mean() / 2 if haircut and sub.ret.mean() > 0 else 0)
            for f in [0.02, 0.05, 0.10]:
                fe, dd = sim(r, f)
                rows.append(dict(strategy=lab + nm + (" (edge halved)" if haircut else ""), risk_per_trade=f,
                                 median_1y=np.median(fe) - 1, p5=np.percentile(fe, 5) - 1, p95=np.percentile(fe, 95) - 1,
                                 prob_loss=np.mean(fe < 1), prob_down30=np.mean(fe < .7), med_maxDD=np.median(dd)))
df = pd.DataFrame(rows); df.to_csv(H / "montecarlo.csv", index=False)
pd.set_option("display.width", 200)
print(df.round(3).to_string(index=False))
