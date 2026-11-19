import pandas as pd, numpy as np
from pathlib import Path
import sys; sys.path.insert(0, str(Path(__file__).parent))
from analyze import ld, ASIA, EURO, ETF, D_SPLIT, I_SPLIT
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40); pd.set_option("display.max_colwidth", 60)
R = pd.read_pickle(Path(__file__).parent / "rules.pkl")
R["sig"] = R["sig"].fillna("-")
key = ["idea","pair","thr","sig","dir"]
dev = R[R.split=="dev"].set_index(key); chk = R[R.split=="check"].set_index(key)
cols = ["n","win","mean","t","flip_mean","mean_worst"]
dv = dev[cols].rename(columns=lambda c: c + "_dev"); cv = chk[cols].rename(columns=lambda c: c + "_chk")
J = dv.join(cv).rename(columns={"flip_mean_dev":"flip_dev","flip_mean_chk":"flip_chk","mean_worst_dev":"worst_dev","mean_worst_chk":"worst_chk"})
J.to_csv(Path(__file__).parent / "rules_dev_check.csv")
print("TOTAL VARIANTS:", len(J))
print("\n== Family summary (dev/check, all rules) ==")
for idea, g in J.reset_index().groupby("idea"):
    print(idea, "rules", len(g), "dev mean>0:", (g.mean_dev>0).sum(), "check mean>0:", (g.mean_chk>0).sum(),
          "dev t>2:", (g.t_dev>2).sum(), "check t>2:", (g.t_chk>2).sum(),
          "| median dev mean %.4f check mean %.4f" % (g.mean_dev.median(), g.mean_chk.median()))
Jn = J.reset_index()
Jn = Jn[Jn.n_dev>=30]
top = Jn.sort_values("mean_dev", ascending=False).head(12)
print("\n== Top 12 by DEV mean net (n_dev>=30) ==")
print(top[["idea","pair","thr","sig","dir","n_dev","win_dev","mean_dev","t_dev","flip_dev","n_chk","win_chk","mean_chk","t_chk","flip_chk"]].round(4).to_string(index=False))
print("\n== Top 10 by CHECK mean net (for reference, not selected on) ==")
print(Jn.sort_values("mean_chk", ascending=False).head(10)[["idea","pair","thr","sig","dir","n_dev","mean_dev","t_dev","n_chk","mean_chk","t_chk"]].round(4).to_string(index=False))
