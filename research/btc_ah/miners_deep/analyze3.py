import pandas as pd, numpy as np
pd.set_option("display.width", 300); pd.set_option("display.max_columns", 40)
R = pd.read_csv("/Users/rytty/CCP/quant_v7/research/btc_ah/miners_deep/variants_stats.csv")
V = ["down_buy|z>=0|btc_above|vol_lo","down_buy|z>=0|btc_all|vol_lo","down_buy|z>=0|btc_all|vol_all","down_buy|z>=1|btc_below|vol_all","down_buy|z>=1|btc_all|vol_all","up_short|z>=1|btc_all|vol_lo","up_short|z>=1|btc_all|vol_all"]
for ex in ["V_close","V_1230"]:
    q = R[(R.exit==ex)&(R.variant.isin(V))&(R["sample"].isin(["w_dev","w_chk","y2026"]))]
    print(f"\n{ex} within-window dev/check and 2026:")
    print(q.pivot_table(index="variant", columns="sample", values=["n","mean_bp","t_day","flip_mean_bp"], aggfunc="first").round(1).to_string())
print("\nPER-YEAR (ideal daily close, mean bp / n / t_day) for dev-selected top rules and the all-regime down-gap buy base:")
for v in ["up_short|z>=1|btc_all|vol_lo","down_buy|z>=1|btc_below|vol_all","up_short|z>=1|btc_all|vol_all","down_buy|z>=0|btc_all|vol_all"]:
    q = R[(R.exit=="D_close")&(R.variant==v)&(R["sample"].str.match(r"^y20\d\d$"))]
    print(v, " | ".join(f"{r['sample']} {r.mean_bp:+.0f}bp n{int(r.n)} t{r.t_day:+.1f}" for _,r in q.iterrows()))
