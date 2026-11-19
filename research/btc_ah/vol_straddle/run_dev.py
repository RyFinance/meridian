"""Dev/check screen of overnight-BTC vol signals -> ATM straddle (signal true) or short iron fly (signal false).

PRE-REGISTERED (written before any result was printed):
  signals (5): S1 range/|net| >= dev median; S2 overnight RV z(20 prior nights) >= 1; S3 RV / median(20 prior) >= 1.5;
               S4 late share (|08:00->09:29| / total |move|) > 0.5; S5 Monday (weekend-spanning night).
  exits (3): 10:30, 12:00, 15:55 (time exits only; no targets/stops).
  variants = 5 signals x 3 exits = 15 primary rules, each with its exact flip = 30 total.
  DEV = trade dates <= 2022-06-30 (dev median and all selection). CHECK = 2022-07-01..2023-12-31.
  Dev pass: pooled mean > 0, t >= 2.0, flip mean < 0. Check pass: pooled mean > 0 and t >= 1.0.
  Passing rules go to a single 2024+ validation (frozen first). Costs as in trades.py.
"""
from __future__ import annotations
import pickle
from pathlib import Path
import numpy as np
import pandas as pd
import sys
sys.path.insert(0, "/Users/rytty/CCP/quant_v7/research/btc_ah/vol_straddle")
from trades import run, st

H = Path(__file__).parent
DEV_END = pd.Timestamp("2022-06-30")
CHECK_END = pd.Timestamp("2023-12-31")
EXITS = {"1030": 60, "1200": 150, "1555": 385}

days = pickle.load(open(H / "dev_days_vol.pkl", "rb"))
days = [d for d in days if d.d <= CHECK_END]
nf = pd.read_parquet(H / "night_features_dev.parquet")
f = nf.reindex([d.d for d in days])
f = f[f.index.isin([d.d for d in days])]

dev_mask = f.index <= DEV_END
med_ratio = f.loc[dev_mask, "ratio"].median()
SIG = {
    "S1_range_over_net": f.ratio >= med_ratio,
    "S2_rvz20>=1": f.rv_z20 >= 1.0,
    "S3_rvmr20>=1.5": f.rv_mr20 >= 1.5,
    "S4_late_share>0.5": f.late_share > 0.5,
    "S5_monday": f.dow == 0,
}
print(f"days {len(days)}  dev {int(dev_mask.sum())} (<= {DEV_END.date()})  check {int((~dev_mask).sum())}  "
      f"S1 dev median ratio = {med_ratio:.3f}")
print("signal true-rate (all days):", {k: round(float(v.mean()), 3) for k, v in SIG.items()})

cache = {}
for ex_name, ex_m in EXITS.items():
    cache[("long_straddle", ex_name)] = run(days, "long_straddle", ex_m)
    cache[("short_fly", ex_name)] = run(days, "short_fly", ex_m)


def legs(sig_series, ex_name, true_kind):
    """true_kind: instrument traded when signal is True; the other instrument on signal False."""
    false_kind = "short_fly" if true_kind == "long_straddle" else "long_straddle"
    a = cache[(true_kind, ex_name)]
    b = cache[(false_kind, ex_name)]
    ta = a[a.index.isin(sig_series.index[sig_series])]
    tb = b[b.index.isin(sig_series.index[~sig_series])]
    return ta, tb


rows = []
for sname, s in SIG.items():
    for ex_name in EXITS:
        for mapping, true_kind in (("primary", "long_straddle"), ("flip", "short_fly")):
            ta, tb = legs(s, ex_name, true_kind)
            pooled = pd.concat([ta.ret, tb.ret]) if len(ta) + len(tb) else pd.Series(dtype=float)
            pooled.index = pd.to_datetime(pooled.index)
            for period, lo, hi in (("dev", None, DEV_END), ("check", DEV_END, CHECK_END)):
                def win(x):
                    x = x.copy()
                    x.index = pd.to_datetime(x.index)
                    if lo is None:
                        return x[x.index <= hi]
                    return x[(x.index > lo) & (x.index <= hi)]
                p_ = win(pooled)
                la, lb = win(ta.ret), win(tb.ret)
                rows.append({"signal": sname, "exit": ex_name, "mapping": mapping, "period": period,
                             "true_leg": true_kind if mapping == "primary" else ("short_fly" if mapping == "flip" else ""),
                             **{f"pool_{k}": v for k, v in st(p_).items()},
                             **{f"legT_{k}": v for k, v in st(la).items()},
                             **{f"legF_{k}": v for k, v in st(lb).items()}})

out = pd.DataFrame(rows)
out.to_csv(H / "dev_check_results.csv", index=False)
pd.set_option("display.width", 250)
cols = ["signal", "exit", "mapping", "period", "pool_n", "pool_mean", "pool_t", "pool_win", "pool_avg_win",
        "pool_avg_loss", "legT_n", "legT_mean", "legF_n", "legF_mean"]
print(out[cols].round(3).to_string(index=False))

# controls: unconditional straddle and fly on all days
print("\nUNCONDITIONAL controls (all days):")
for ex_name in EXITS:
    for kind in ("long_straddle", "short_fly"):
        r = cache[(kind, ex_name)]
        r.index = pd.to_datetime(r.index)
        print(kind, ex_name, "dev", {k: round(v, 3) for k, v in st(r.ret[r.index <= DEV_END]).items()},
              "check", {k: round(v, 3) for k, v in st(r.ret[(r.index > DEV_END) & (r.index <= CHECK_END)]).items()})
