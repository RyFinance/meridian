import pandas as pd, numpy as np
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
O = "/Users/rytty/CCP/quant_v7/research/btc_ah/index_gaps"
for name in ["fade_grid_index", "fade_grid_leveraged"]:
    d = pd.read_csv(f"{O}/{name}.csv")
    d["variant"] = d.sym + "|" + d.gap_dir + "|" + d.gap_bin + "|" + d.target + "|stop" + d.stop.astype(str)
    cols = ["variant", "dev_n", "dev_win", "dev_mean_bp", "dev_t", "dev_flip_mean_bp", "chk_n", "chk_win", "chk_mean_bp", "chk_t", "chk_flip_mean_bp"]
    d2 = d[d.dev_n >= 60].copy()
    print(f"== {name}: total {len(d)} variants, {len(d2)} with dev_n>=60")
    print("dev-positive (mean>0):", (d2.dev_mean_bp > 0).sum(), " check-positive:", (d2.chk_mean_bp > 0).sum())
    print("--- top 3 by dev mean net (bp)")
    top = d2.sort_values("dev_mean_bp", ascending=False).head(3)
    print(top[cols].round(3).to_string(index=False))
    print("--- top 3 by dev win rate (small target, mean shown)")
    tw = d2[d2.dev_mean_bp > -1e9].sort_values("dev_win", ascending=False).head(3)
    print(tw[cols].round(3).to_string(index=False))
    print("--- best dev win-rate with mean>0 in dev and check (any):")
    ok = d2[(d2.dev_mean_bp > 0) & (d2.chk_mean_bp > 0)]
    print(len(ok), "variants positive in both dev and check")
    print(ok[cols].sort_values("dev_mean_bp", ascending=False).head(5).round(3).to_string(index=False))
    print("--- win rate >= 60% and mean<0 in dev (fail examples count):", ((d2.dev_win >= 0.6) & (d2.dev_mean_bp < 0)).sum(), "of", (d2.dev_win >= 0.6).sum())
    d.to_csv(f"{O}/{name}_with_variant.csv", index=False)
