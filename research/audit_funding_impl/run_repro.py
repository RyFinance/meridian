import json, numpy as np, pandas as pd
from research.audit_funding_impl.replicate import *

K, F = load()
P = panels(K, F)
W, nU = build_weights(P)
res = {}
books = {k: daily(P, W, c, dl) for k, (c, dl) in {"gross": (0, 0), "base": (7e-4, 0), "stress": (20e-4, .2)}.items()}
ref = pd.read_csv(ROOT / "reports/crypto_funding_xs/corrected/dev_daily.csv", index_col=0, parse_dates=True)
refW = pd.read_parquet(ROOT / "reports/crypto_funding_xs/corrected/dev_weights.parquet")
for k, b in books.items():
    d = b.net.reindex(ref.index) - ref[k]
    res[k] = {"sharpe_mine": sharpe(b.net), "sharpe_ref": sharpe(ref[k]), "n_mine": len(b), "n_ref": len(ref),
              "max_abs_diff": float(d.abs().max()), "n_diff_gt_1e-9": int((d.abs() > 1e-9).sum()),
              "by_year_mine": {int(y): float(g.sum()) for y, g in b.net.groupby(b.index.year)}}
d = books["base"].net.reindex(ref.index) - ref["base"]
res["diff_days"] = {str(i.date()): float(v) for i, v in d[d.abs() > 1e-9].items()}
cols = [c for c in W.columns if c in refW.columns]
wd = (W[cols].fillna(0) - refW.reindex(W.index)[cols].fillna(0)).abs().sum(axis=1)
res["weight_mismatch_days"] = int((wd > 1e-12).sum())
res["ref_weight_nonzero_cols_missing_from_mine"] = sorted(set(refW.columns[(refW.fillna(0) != 0).any()]) - set(W.columns))
res["days_dropped"] = int(W.isna().all(axis=1).sum()); res["first_live"] = str(W.dropna().index[0].date())
res["universe_size"] = {int(y): [int(g[g >= 25].min()), float(g[g >= 25].mean()), int(g.max())] for y, g in nU.groupby(nU.index.year) if (g >= 25).any()}
print(json.dumps(res, indent=1))
(OUT / "repro.json").write_text(json.dumps(res, indent=1))
W.to_parquet(OUT / "my_weights.parquet"); nU.to_frame("n").to_parquet(OUT / "my_universe_n.parquet")
pd.concat({k: b for k, b in books.items()}, axis=1).to_csv(OUT / "my_daily.csv")
