import json, numpy as np, pandas as pd
from research.audit_funding_impl.replicate import *

K, F = load(); P = panels(K, F)
W = pd.read_parquet(OUT / "my_weights.parquet"); nU = pd.read_parquet(OUT / "my_universe_n.parquet").n
live = W.notna().all(axis=1); Wf = W.fillna(0.0); idx = W.index
O, H, L, C, V, FU, SIG = (P[k].reindex(idx) for k in ("O", "H", "L", "C", "V", "FUND", "SIG"))
ret = C / O - 1; base = daily(P, W); R = {}
# stale / zero-volume klines while held
stale = ((V == 0) | ((H == L) & (O == C))) & (Wf != 0) & live.to_numpy()[:, None]
R["stale_held"] = {f"{d.date()} {s}": float(Wf.loc[d, s]) for (d, s), v in stale.stack().items() if v}
allstale = K[(K.qv == 0)]
R["zero_volume_rows_dev"] = allstale.groupby("sym").day.agg(["min", "max", "count"]).astype(str).reset_index().values.tolist()
# funding settlements counted per held position-day
t = F.copy(); t["d"] = (t.ts - pd.Timedelta(milliseconds=1)).dt.normalize()   # (d, d+1] bucket
cnt = t.groupby(["d", "sym"]).size().unstack().reindex(index=idx, columns=W.columns).fillna(0)
h = cnt[(Wf != 0) & live.to_numpy()[:, None]].stack()
R["settlements_per_held_day"] = {int(k): int(v) for k, v in h.value_counts().sort_index().items()}
low = h[h < 3]
R["held_days_lt3_settlements"] = [f"{d.date()} {s} n={int(v)}" for (d, s), v in low.items()][:40]
# funding-rate outliers held
fr = F[(F.rate.abs() > 0.01)]
R["abs_rate_gt_1pct_per_settlement"] = fr.groupby("sym").rate.agg(["count", "min", "max"]).round(4).reset_index().values.tolist()
# ties at the quintile boundary
nties = 0; tied_days = 0; rows = []
for d in idx[live]:
    w = Wf.loc[d]; s = SIG.loc[d]
    inU = None
    k = int((w > 0).sum())
    lo_b = s[w > 0].max(); hi_b = s[w < 0].min()
    # univ members = those ranked; approximate: members with same signal as boundary but not selected
    # recompute universe membership quickly
    tl = int(((s == lo_b)).sum()); th = int(((s == hi_b)).sum())
    if tl > 1 or th > 1:
        tied_days += 1
R["days_with_tied_signal_at_boundary_any"] = tied_days
# random tie-breaking: perturb the signal by tiny noise (1e-15 relative) -> ties broken randomly
sh = []
for seed in range(20):
    rng = np.random.default_rng(seed)
    P2 = dict(P); P2["SIG"] = P["SIG"] + rng.uniform(-1e-12, 1e-12, P["SIG"].shape)
    W2, _ = build_weights(P2); sh.append(sharpe(daily(P2, W2).net))
R["random_tiebreak_sharpe"] = {"min": min(sh), "max": max(sh), "mean": float(np.mean(sh))}
P3 = dict(P); P3["SIG"] = P["SIG"].round(10)
# reverse alphabetical tie-break
P4 = {k: (v.iloc[:, ::-1] if isinstance(v, pd.DataFrame) else v) for k, v in P.items()}; P4["first"] = P["first"].iloc[::-1]
W4, _ = build_weights(P4); R["reverse_alpha_tiebreak_sharpe"] = sharpe(daily(P4, W4).net)
# share of signals exactly at the 0.01%/8h default (0.0003/day)
sv = SIG.where(Wf.notna() & live.to_numpy()[:, None]).stack()
R["share_signal_eq_default_0.0003"] = float((sv.round(9) == 0.0003).mean())
# DOGE 2021-01-28 check and THETA 2020
R["doge_2021_01_26_30"] = K[(K.sym == "DOGEUSDT") & K.day.between("2021-01-26", "2021-01-30")][["day", "open", "high", "low", "close", "qv"]].astype(str).values.tolist()
R["doge_weight_2021_01_25_30"] = Wf.loc["2021-01-25":"2021-01-30", "DOGEUSDT"].round(4).tolist()
R["doge_signal_2021_01_28"] = float(SIG.loc["2021-01-28", "DOGEUSDT"])
R["sharpe_ex_2021_01_28"] = sharpe(base.net.drop(pd.Timestamp("2021-01-28")))
th = (Wf["THETAUSDT"] * ret["THETAUSDT"].fillna(0) - Wf["THETAUSDT"] * FU["THETAUSDT"])[live]
th20 = th[th.index.year == 2020]
R["theta_2020"] = {"long_days": int((Wf.loc[th20.index, "THETAUSDT"] > 0).sum()), "short_days": int((Wf.loc[th20.index, "THETAUSDT"] < 0).sum()),
                   "pnl": float(th20.sum()), "top5_days": {str(d.date()): round(v, 4) for d, v in th20.sort_values()[::-1].head(5).items()}}
b20 = base.net[base.index.year == 2020]
R["2020_monthly"] = {str(m): round(float(g.sum()), 4) for m, g in b20.groupby(b20.index.to_period("M"))}
R["2020_universe_by_month"] = {str(m): [int(g.min()), int(g.max())] for m, g in nU[b20.index].groupby(b20.index.to_period("M"))}
# small-universe effect: simulate as if 2020 had k fixed... report per-day P&L sd vs k
kk = (Wf[live] > 0).sum(axis=1)
R["daily_sd_by_k_bucket"] = {str(b): [round(float(base.net[kk[kk.between(*b)].index].std()), 4), round(float(base.net[kk[kk.between(*b)].index].mean() * 365), 3), int(kk.between(*b).sum())] for b in [(5, 8), (9, 14), (15, 20)]}
(OUT / "attack2.json").write_text(json.dumps(R, indent=1, default=str)); print(json.dumps(R, indent=1, default=str))
