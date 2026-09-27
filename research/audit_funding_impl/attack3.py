import json, numpy as np, pandas as pd
from research.audit_funding_impl.replicate import *

K, F = load(); P = panels(K, F)
W = pd.read_parquet(OUT / "my_weights.parquet"); nU = pd.read_parquet(OUT / "my_universe_n.parquet").n
live = W.notna().all(axis=1); Wf = W.fillna(0.0); idx = W.index
O, H, L, C, V, FU = (P[k].reindex(idx) for k in ("O", "H", "L", "C", "V", "FUND"))
ret = C / O - 1; base = daily(P, W); R = {}
stale = (V == 0)
held = (Wf != 0) & live.to_numpy()[:, None]
sp = (Wf * ret.fillna(0))[stale & held]; sf = (-(Wf * FU))[stale & held]
R["stale_heldday_pnl"] = {"price": float(sp.sum().sum()), "funding": float(sf.sum().sum()),
                         "by_sym": {s: [round(float(sp[s].sum()), 4), round(float(sf[s].sum()), 4), int((stale & held)[s].sum())] for s in sp.columns[(stale & held).any()]}}
# Variant: eligibility additionally requires positive quote volume on t-1 (a zero-volume kline is not a tradable kline)
P2 = dict(P); V2 = P["V"].copy()
C2 = P["C"].where(P["V"] > 0)      # zero-volume day treated as "no kline"
P2["C"] = C2
W2, n2 = build_weights(P2)
b2 = daily(P, W2)     # returns still computed from the real (stale) prices
R["require_nonzero_volume_t-1"] = {"sharpe": sharpe(b2.net), "by_year": {int(y): round(float(g.sum()), 4) for y, g in b2.net.groupby(b2.index.year)},
                                    "stress_sharpe": sharpe(daily(P, W2, 20e-4, .2).net), "days": len(b2)}
# BTCST detail
kb = K[K.sym == "BTCSTUSDT"].set_index("day")
R["btcst_2021_05"] = kb.loc["2021-05-01":"2021-05-06", ["open", "high", "low", "close", "qv"]].astype(str).values.tolist()
R["btcst_first_last"] = [str(kb.index.min().date()), str(kb.index.max().date()), int((kb.qv > 0).sum())]
R["ftt_2022_11"] = K[(K.sym == "FTTUSDT") & K.day.between("2022-11-12", "2022-11-17")][["day", "open", "close", "qv"]].astype(str).values.tolist()
R["ftt_funding_2022_11_15_22"] = F[(F.sym == "FTTUSDT") & F.ts.between("2022-11-15", "2022-11-23")].rate.agg(["count", "sum", "min"]).round(4).to_dict()
# combined 'clean' variant: nonzero-volume eligibility + hole days excluded + hour-rounded funding + drift turnover
Ph = panels(K, F, "hour"); Ph["C"] = Ph["C"].where(Ph["V"] > 0)
W3, _ = build_weights(Ph)
Ph_real = panels(K, F, "hour")
b3 = daily(Ph_real, W3, drift_turnover=True)
holes = pd.to_datetime(["2022-02-26", "2022-02-27", "2022-02-28", "2022-03-01", "2022-04-01", "2022-04-02", "2022-04-03"])
b3n = b3.net.drop(holes, errors="ignore")
R["combined_clean"] = {"sharpe_base": sharpe(b3n), "ann_mean": float(b3n.mean() * 365), "by_year": {int(y): round(float(g.sum()), 4) for y, g in b3n.groupby(b3n.index.year)},
                       "stress_20bp_no_delist_penalty": sharpe(daily(Ph_real, W3, 20e-4, 0, drift_turnover=True).net.drop(holes, errors="ignore")),
                       "stress_20bp_delist_penalty": sharpe(daily(Ph_real, W3, 20e-4, .2, drift_turnover=True).net.drop(holes, errors="ignore"))}
# centred 21d block bootstrap p (own implementation) for base and combined
def boot(x, B=5000, blk=21, seed=20260925):
    x = np.asarray(x); n = len(x); xc = x - x.mean(); rng = np.random.default_rng(seed); obs = x.mean()
    nb = int(np.ceil(n / blk)); c = 0
    for _ in range(B):
        st = rng.integers(0, n - blk + 1, nb); s = np.concatenate([xc[i:i + blk] for i in st])[:n]
        c += s.mean() >= obs
    return (c + 1) / (B + 1)
R["own_bootstrap_p_base"] = boot(base.net.to_numpy()); R["own_bootstrap_p_combined_clean"] = boot(b3n.to_numpy())
(OUT / "attack3.json").write_text(json.dumps(R, indent=1, default=str)); print(json.dumps(R, indent=1, default=str))
