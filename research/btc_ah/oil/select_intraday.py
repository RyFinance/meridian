import pandas as pd, numpy as np
from pathlib import Path
O = Path(__file__).parent
pd.set_option("display.width", 220); pd.set_option("display.max_rows", 500); pd.set_option("display.max_columns", 30)
R = pd.read_csv(O / "results_intraday.csv")
D = R[R.part == "dev"].set_index(["rule","inst"])
C = R[R.part == "check"].set_index(["rule","inst"])
M = D[["n","mean_bp","t","win"]].join(C[["n","mean_bp","t","win"]], lsuffix="_dev", rsuffix="_chk")
M = M[M.n_dev >= 60].sort_values("t_dev", ascending=False)
print(M.head(15).round(2).to_string())
print("dev variants with t>2:", (M.t_dev > 2).sum(), "of", len(M), "; dev mean>0:", (M.mean_bp_dev>0).sum())
print("dev->check sign agreement among dev t>2:", ((M.t_dev>2)&(M.mean_bp_chk>0)).sum())
