"""DEV ONLY (2019-2022): grid over stock set x rule. Days = all NYSE sessions with >=1 name in panel."""
import numpy as np, pandas as pd
from pathlib import Path
from bt import trades, stats, per_year
H = Path(__file__).parent
P = pd.read_parquet(H / "panel.parquet"); P = P[P.date <= "2022-12-31"]
days = pd.DatetimeIndex(sorted(P[P.date >= "2019-06-01"].date.unique()))
SETS = {"all_ex_mstr": ["MARA","RIOT","CLSK","HUT","CIFR","WULF","IREN","BTBT","COIN","HOOD","XYZ","HIVE","BTDR","CAN","GBTC","BITO","IBIT","FBTC","CORZ"],
        "large_ex_mstr": ["COIN","MARA","RIOT","HOOD","XYZ","GBTC","BITO","IBIT","FBTC"],
        "small": ["CLSK","HUT","CIFR","WULF","IREN","BTBT","HIVE","BTDR","CAN","CORZ"],
        "miners": ["MARA","RIOT","CLSK","HUT","CIFR","WULF","IREN","BTBT","HIVE","BTDR","CORZ"],
        "coin_hood": ["COIN","HOOD"]}
out = []
for sn, names in SETS.items():
    for mode in ["ls", "long", "cond"]:
        for k in [0.5, 1.0, 1.5, 2.0]:
            for bm in [0.0, 0.01, 0.02]:
                T = trades(P, names, k, mode, bm); 
                if len(T) < 30: continue
                out.append(dict(set=sn, mode=mode, k=k, btc_min=bm, **stats(T, days)))
R = pd.DataFrame(out); R.to_csv(H / "dev_grid.csv", index=False)
pd.set_option("display.width", 250)
print(R.sort_values("t", ascending=False).head(30).round(2).to_string())
print("\nfraction of grid cells with net t>2: %.2f of %d" % ((R.t > 2).mean(), len(R)))
print(R.groupby(["set", "mode"]).t.median().unstack().round(2))
