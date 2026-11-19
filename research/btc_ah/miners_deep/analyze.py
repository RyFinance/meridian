import pandas as pd, numpy as np
pd.set_option("display.width", 300); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 500)
R = pd.read_csv("/Users/rytty/CCP/quant_v7/research/btc_ah/miners_deep/variants_stats.csv")
def piv(ex, cols=("dev","check","y2026")):
    q = R[(R.exit==ex) & R["sample"].isin(cols)]
    out = q.pivot_table(index="variant", columns="sample", values=["n","mean_bp","t_day","flip_mean_bp"], aggfunc="first")
    return out
D = piv("D_close", ("dev","check","y2026"))
D.columns = [f"{a}_{b}" for a,b in D.columns]
cols = ["n_dev","mean_bp_dev","t_day_dev","n_check","mean_bp_check","t_day_check","n_y2026","mean_bp_y2026","t_day_y2026","flip_mean_bp_check"]
print("DAILY-CLOSE (ideal entry at 09:30 open). dev 2020-08..23 | check 2024-01..2026-08-10 | 2026 YTD")
print(D[cols].sort_values("t_day_dev", ascending=False).round(2).to_string())
