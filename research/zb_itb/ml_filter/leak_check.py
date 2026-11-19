import numpy as np, pandas as pd, sys
sys.path.insert(0, "research/zb_itb/ml_filter"); from features import *
dat = Data(); X, me = build_all(dat); X = X.astype(float)
tr = dat.tr
# 1. m reproduces frozen m
mm = pd.concat([X.m, tr.m], axis=1, keys=["mine", "frozen"]).dropna(); print("m vs frozen max abs diff:", float((mm.mine - mm.frozen).abs().max()), "n", len(mm))
# 2. every source bar ended by 09:00 ET on D
cut = pd.Series({D: D.tz_localize("America/New_York") + pd.Timedelta(hours=9) for D in me.index}); slack = (cut - me).dt.total_seconds() / 60
print("min slack (min) between last source bar end and 09:00 ET:", slack.min(), "| days violating:", int((slack < 0).sum()))
# 3. truncation test: rebuild features for sampled days from data truncated to 09:00 D; must be identical
rng = np.random.default_rng(1); days = [D for D in X.index if X.loc[D].notna().sum() > 15]; samp = rng.choice(len(days), 60, replace=False); bad = 0
mh_full = X.m
for k in samp:
    D = days[k]; i = dat.days.index(D); t = dat.truncate(D)
    f, _ = day_features(t, D, dat.days[i-1], mh_full[mh_full.index < D])
    a = pd.Series(f).astype(float); b = X.loc[D]; diff = (a - b).abs().fillna(0)
    if (diff > 1e-9).any(): bad += 1; print("MISMATCH", D.date(), list(diff[diff > 1e-9].index))
print("truncation test: 60 sampled days, mismatches:", bad)
X.to_pickle("research/zb_itb/ml_filter/X.pkl"); print(X.shape); print(X.isna().sum()[X.isna().sum() > 0])
# 4. sanity: segments sum to m
s = X[["seg1","seg2","seg3","seg4"]].sum(axis=1) / X.d / 1e4; ok = (s - X.m).abs().dropna(); print("seg-sum vs m: max diff", float(ok.max()), "n", len(ok))
