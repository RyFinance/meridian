"""Family summaries, top-3 dev picks with check results, per-year, flips, worst-fill sensitivity."""
from pathlib import Path
import numpy as np
import pandas as pd
from research.btc_ah.metals.study import PAIRS, day_table, signals, trades, stats, H

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)
R = pd.read_csv(H / "variants_summary.csv")
Rg = R[R["eq"] != "GOLD"]  # GOLD has no dev-period history (starts 2025-12), so it cannot be dev-picked
print("variants:", len(R), " dev-eligible (excl GOLD):", len(Rg), " dev t>2:", int((Rg.dev_t > 2).sum()),
      " dev t>1.96:", int((Rg.dev_t > 1.96).sum()), " dev t<-1.96:", int((Rg.dev_t < -1.96).sum()))
fam = Rg.groupby(["sig", "hold", "k"]).agg(
    dev_mean=("dev_mean", "mean"), dev_t_med=("dev_t", "median"),
    check_mean=("check_mean", "mean"), check_t_med=("check_t", "median"),
    flip_dev=("dev_flip_mean", "mean"), flip_check=("check_flip_mean", "mean"),
    n_dev_pos=("dev_mean", lambda x: int((x > 0).sum())),
    n_check_pos=("check_mean", lambda x: int((x > 0).sum())))
print("\nFamily means across 15 pairs (net bp per trade):")
print(fam.round(2).to_string())
top = Rg.sort_values("dev_t", ascending=False).head(3)
print("\nTop 3 by dev t (dev n>=100 not required; all shown):")
print(top[["eq", "sig", "k", "hold", "dev_n", "dev_mean", "dev_t", "dev_win", "dev_flip_mean",
           "check_n", "check_mean", "check_t", "check_win", "check_flip_mean"]].round(2).to_string(index=False))
# decay: correlation of dev vs check mean across all eligible variants
print("\ncorr(dev mean, check mean) across variants: %.3f" % Rg[["dev_mean", "check_mean"]].corr().iloc[0, 1])

T = pd.read_parquet(H / "all_trades.parquet")
print("\nPer-year net mean (bp) and n for top 3, and flips:")
for _, r in top.iterrows():
    g = T[(T["eq"] == r["eq"]) & (T.sig == r.sig) & (T.k == r.k) & (T.hold == r.hold)]
    py = g.groupby("year").agg(n=("net", "size"), net=("net", "mean"), flip=("flip_net", "mean"),
                              win=("net", lambda x: (x > 0).mean()))
    w, l = g.loc[g.net > 0, "net"], g.loc[g.net <= 0, "net"]
    print(f"\n{r["eq"]} {r.sig} k={r.k} {r.hold}: all n={len(g)} net={g.net.mean():.1f} t={stats(g.net)['t']:.2f} "
          f"win={(g.net>0).mean():.2f} avgWin={w.mean():.1f} avgLoss={l.mean():.1f} flip_net={g.flip_net.mean():.1f} flip_t={stats(g.flip_net)['t']:.2f}")
    print(py.round(2).to_string())

print("\nWorst-fill sensitivity (long entry at high, exit at low; mirrored for shorts), top 3:")
cost_of = {e: c for _, e, c in [(m, e, c) for m, e, c in PAIRS]}
metal_of = {e: m for m, e, _ in PAIRS}
for _, r in top.iterrows():
    t = day_table(metal_of[r["eq"]], r["eq"])
    sg = signals(t)
    wt = trades(t, sg, cost_of[r["eq"]], worst=True)
    g = wt[(wt.sig == r.sig) & (wt.k == r.k) & (wt.hold == r.hold)]
    print(f"{r["eq"]} {r.sig} k={r.k} {r.hold}: worst-fill n={len(g)} net={g.net.mean():.1f} t={stats(g.net)['t']:.2f}")
