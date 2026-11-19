import pandas as pd, numpy as np
pd.set_option("display.width", 300); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 500)
R = pd.read_csv("/Users/rytty/CCP/quant_v7/research/btc_ah/miners_deep/variants_stats.csv")
T = pd.read_parquet("/Users/rytty/CCP/quant_v7/research/btc_ah/miners_deep/trades.parquet")
q = R[R.exit!="D_close"]
for ex in ["V_close","V_1230"]:
    p = q[(q.exit==ex) & (q["sample"].isin(["w_chk","y2026"]))].pivot_table(index="variant", columns="sample", values=["n","mean_bp","t_day"], aggfunc="first")
    p.columns = [f"{a}_{b}" for a,b in p.columns]
    print(f"\nVALID intraday {ex} (decision 09:30 bar, enter 10:30 open). Check window 2025-07..2026-08-10 and 2026 YTD. Down-gap buys (long) only:")
    m = p[p.index.str.startswith("down_buy")]
    print(m.round(2).sort_values("t_day_w_chk", ascending=False).head(20).to_string())
    print(f"all {len(p)} {ex} variants: n_pos_wchk={int((p.mean_bp_w_chk>0).sum())}, median wchk bp={p.mean_bp_w_chk.median():.1f}")
# ideal check & 2026 for the intraday ideal families (dev window too)
print("\nIDEAL I_close/I_1030 down_buy, w_dev vs w_chk:")
p = q[(q.exit.isin(["I_1030","I_close"])) & (q.variant.str.startswith("down_buy")) & (q["sample"].isin(["w_dev","w_chk"]))].pivot_table(index=["variant","exit"], columns="sample", values=["n","mean_bp","t_day"], aggfunc="first")
print(p.round(2).head(40).to_string())
# worst-fill stress for the valid long-only rules with best check
def worst(variant, ex):
    g = T[(T.variant==variant)&(T.exit==ex)].dropna(subset=["net_worst"])
    return dict(variant=variant, exit=ex, n=len(g), mean_bp=g.net.mean()*1e4, worst_mean_bp=g.net_worst.mean()*1e4, worst_win=(g.net_worst>0).mean())
rows=[]
for v in ["down_buy|z>=1|btc_below|vol_all","down_buy|z>=1|btc_all|vol_all","down_buy|z>=0|btc_all|vol_all"]:
    for ex in ["V_close","V_1230","I_close"]:
        rows.append(worst(v,ex))
print("\nWORST-FILL stress (buy at entry-bar high, sell at exit-bar low):")
print(pd.DataFrame(rows).round(3).to_string(index=False))
