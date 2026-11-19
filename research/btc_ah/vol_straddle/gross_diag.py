"""Diagnostic only: same dev/check trades with zero spread and zero commission (is there any gross edge?)."""
import pickle, sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, "/Users/rytty/CCP/quant_v7/research/btc_ah/vol_straddle")
import trades as T
H = Path(__file__).parent
T.COMM = 0.0
T.hs = lambda px: 0 * px
days = [d for d in pickle.load(open(H / "dev_days_vol.pkl", "rb"))]
for kind in ("long_straddle", "short_fly"):
    for ex, m in (("1030", 60), ("1200", 150), ("1555", 385)):
        r = T.run(days, kind, m)
        r.index = pd.to_datetime(r.index)
        d = T.st(r.ret[r.index <= "2022-06-30"]); c = T.st(r.ret[(r.index > "2022-06-30")])
        print(kind, ex, "GROSS dev mean %.3f t %.2f | check mean %.3f t %.2f" % (d["mean"], d["t"], c["mean"], c["t"]))
