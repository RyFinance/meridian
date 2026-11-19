import numpy as np, pandas as pd, warnings, json, sys
warnings.filterwarnings("ignore")
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.preprocessing import StandardScaler
import lightgbm as lgb
OUT = "research/zb_itb/ml_filter/"
X = pd.read_pickle(OUT + "X.pkl"); tr = pd.read_csv("research/zb_itb/verify/f3_trades_canonical.csv", index_col=0, parse_dates=True)
T = X[X.d.notna() & (X.d != 0)].copy(); T["net"] = (tr.g_off.reindex(T.index) - 0.0004); T = T[T.net.notna()]
T["y"] = (T.net > 0).astype(int); T["net_bp"] = T.net * 1e4
FEATS = [c for c in X.columns if c not in ("m", "d")]
print("trades", len(T), "win", T.y.mean().round(4), "mean bp", T.net_bp.mean().round(2), "features", len(FEATS))
# ---- walk-forward folds: expanding window, monthly, start after >=200 training trades
mon = T.index.to_period("M"); first200 = T.index[199]
months = [m for m in mon.unique() if m.start_time > first200 - pd.Timedelta(days=0) or (mon == m).any() and T.index[mon == m][0] > first200]
months = [m for m in mon.unique() if T.index[mon == m][0] > first200]
months = sorted(set(months)); print("OOS months", len(months), months[0], "->", months[-1])
def make(kind):
    if kind == "lr": return LogisticRegression(C=0.02, max_iter=500)
    if kind == "ridge": return Ridge(alpha=500.0)
    p = dict(n_estimators=120, learning_rate=0.03, num_leaves=4, max_depth=2, min_child_samples=25, subsample=0.7, subsample_freq=1,
             colsample_bytree=0.7, reg_lambda=10.0, random_state=0, n_jobs=1, verbose=-1)
    return lgb.LGBMClassifier(**p) if kind == "gbc" else lgb.LGBMRegressor(**p)
def fit_predict(kind, Xtr, ytr, Xte):
    med = Xtr.median(); Xtr = Xtr.fillna(med).fillna(0); Xte = Xte.fillna(med).fillna(0)
    if kind in ("lr", "ridge"):
        sc = StandardScaler().fit(Xtr); a, b = sc.transform(Xtr), sc.transform(Xte)
    else: a, b = Xtr.values, Xte.values
    if kind in ("ridge", "gbr"):
        lo, hi = np.percentile(ytr, [2, 98]); ytr = np.clip(ytr, lo, hi)
    m = make(kind).fit(a, ytr)
    pred = m.predict_proba(b)[:, 1] if kind in ("lr", "gbc") else m.predict(b)
    return pred, m
def walk(kind, ycol, seed=None, keep_models=False):
    """returns OOS predictions (Series), plus train base rate / mean per fold, and models"""
    rng = np.random.default_rng(seed) if seed is not None else None
    yall = T[ycol].values.copy()
    if rng is not None: yall = rng.permutation(yall)          # permuted targets: same pipeline, no information
    preds, base, mdl = [], [], []
    for m in months:
        tri = np.where(T.index < m.start_time)[0]; tei = np.where(mon == m)[0]
        p, mo = fit_predict(kind, T[FEATS].iloc[tri], yall[tri], T[FEATS].iloc[tei])
        preds.append(pd.Series(p, index=T.index[tei])); base.append(pd.Series(yall[tri].mean(), index=T.index[tei])); mdl.append((mo, tri))
    return pd.concat(preds), pd.concat(base), mdl
def metrics(w, net):
    """w = weight per OOS trade (0 skip, 1 full); daily pnl series incl zeros on skipped days"""
    p = w * net; eq = np.exp(p.cumsum()); ex = w > 0
    return dict(n=int(ex.sum()), win=float((net[ex] > 0).mean()) if ex.any() else np.nan, mean_bp=float(net[ex].mean() * 1e4) if ex.any() else np.nan,
                total_bp=float(p.sum() * 1e4), sharpe=float(p.mean() / p.std() * np.sqrt(252)) if p.std() > 0 else np.nan,
                maxdd=float((eq / eq.cummax() - 1).min() * 100), avg_w=float(w.mean()))
def weights(combo, pred, base):
    kind, mode, thr = combo
    if mode == "filter_cls": return (pred >= base - thr).astype(float)
    if mode == "filter_reg": return (pred > 0).astype(float)
    if mode == "size_reg": return np.clip(pred / (base), 0, 2)         # base = mean train net
COMBOS = {  # name: (model, mode, thr, target)
 "LR-cls skip p<base-3pt": ("lr", "filter_cls", 0.03, "y"), "LR-cls skip p<base": ("lr", "filter_cls", 0.0, "y"),
 "GBM-cls skip p<base-3pt": ("gbc", "filter_cls", 0.03, "y"), "GBM-cls skip p<base": ("gbc", "filter_cls", 0.0, "y"),
 "Ridge-reg skip pred<0": ("ridge", "filter_reg", 0, "net_bp"), "GBM-reg skip pred<0": ("gbr", "filter_reg", 0, "net_bp"),
 "Ridge-reg size w=pred/mean": ("ridge", "size_reg", 0, "net_bp"), "GBM-reg size w=pred/mean": ("gbr", "size_reg", 0, "net_bp")}
def run(name, seed=None):
    kind, mode, thr, ycol = COMBOS[name]; p, b, mdl = walk(kind, ycol, seed)
    w = weights((kind, mode, thr), p, b); return w, p, mdl
if __name__ == "__main__":
    first_oos = T.index[T.index >= months[0].start_time][0]; O = T[T.index >= months[0].start_time]; net = O.net
    print("OOS trades", len(O), O.index[0].date(), "->", O.index[-1].date(), "| training trades at first fold", int((T.index < months[0].start_time).sum()))
    base = metrics(pd.Series(1.0, index=O.index), net); print("BASELINE", base)
    res = {"baseline": base}; W = {}; PR = {}; MD = {}
    for n in COMBOS:
        w, p, mdl = run(n); W[n] = w; PR[n] = p; MD[n] = mdl; res[n] = metrics(w, net)
    # AUC / correlation of OOS predictions with outcomes
    from sklearn.metrics import roc_auc_score
    for n in COMBOS:
        res[n]["auc"] = float(roc_auc_score(O.y, PR[n])) if COMBOS[n][3] == "y" else float(roc_auc_score(O.y, PR[n]))
        res[n]["ic_spearman"] = float(pd.Series(PR[n]).corr(O.net_bp, method="spearman"))
        if COMBOS[n][1] == "size_reg": res[n]["total_bp_per_avg_w"] = res[n]["total_bp"] / res[n]["avg_w"]
    # controls
    rng = np.random.default_rng(123); NS = 20; ND = 2000
    for n in COMBOS:
        w = W[n]; k = int((w == 0).sum()); mode = COMBOS[n][1]; r = []
        if mode != "size_reg":
            for _ in range(ND):
                ww = pd.Series(1.0, index=O.index); ww.iloc[rng.choice(len(O), k, replace=False)] = 0; r.append(metrics(ww, net))
            R = pd.DataFrame(r); res[n]["random"] = {c: [float(R[c].mean()), float(R[c].quantile(.05)), float(R[c].quantile(.95))] for c in ["win", "total_bp", "sharpe"]}
            res[n]["random"]["p_win"] = float((R.win >= res[n]["win"]).mean()) if k else None
            res[n]["random"]["p_sharpe"] = float((R.sharpe >= res[n]["sharpe"]).mean()); res[n]["random"]["p_total"] = float((R.total_bp >= res[n]["total_bp"]).mean())
        else:  # random sizing: random permutation of the same weights
            for _ in range(ND):
                ww = pd.Series(rng.permutation(w.values), index=O.index); r.append(metrics(ww, net))
            R = pd.DataFrame(r); res[n]["random"] = {c: [float(R[c].mean()), float(R[c].quantile(.05)), float(R[c].quantile(.95))] for c in ["total_bp", "sharpe"]}
            res[n]["random"]["p_sharpe"] = float((R.sharpe >= res[n]["sharpe"]).mean()); res[n]["random"]["p_total"] = float((R.total_bp >= res[n]["total_bp"]).mean())
        sh = []
        for s in range(NS):
            ws, _, _ = run(n, seed=1000 + s); sh.append(metrics(ws, net))
        S = pd.DataFrame(sh); res[n]["shuffle"] = {c: [float(S[c].mean()), float(S[c].min()), float(S[c].max())] for c in ["win", "total_bp", "sharpe", "n"]}
        res[n]["shuffle"]["p_sharpe"] = float((S.sharpe >= res[n]["sharpe"]).mean()); res[n]["shuffle"]["p_total"] = float((S.total_bp >= res[n]["total_bp"]).mean())
        res[n]["shuffle"]["p_win"] = float((S.win >= res[n]["win"]).mean())
        print(n, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in res[n].items() if not isinstance(v, dict)}, flush=True)
    # importances: LR coef (std units) / GBM gain, averaged over folds, + final model trained on all pre-last-month data
    imp = {}
    for n, kind in (("LR-cls skip p<base", "lr"), ("GBM-cls skip p<base", "gbc"), ("Ridge-reg skip pred<0", "ridge"), ("GBM-reg skip pred<0", "gbr")):
        L = []
        for mo, tri in MD[n]:
            if kind in ("lr", "ridge"): v = np.abs(mo.coef_.ravel())
            else: v = mo.booster_.feature_importance("gain"); v = v / max(v.sum(), 1e-12)
            L.append(v)
        L = np.array(L); imp[n] = pd.Series(L.mean(0), index=FEATS)
        if kind in ("lr", "ridge"):  # signed average coef too
            imp[n + " signed"] = pd.Series(np.mean([mo.coef_.ravel() for mo, _ in MD[n]], 0), index=FEATS)
    pd.DataFrame(imp).to_csv(OUT + "importances.csv")
    pd.DataFrame({n: W[n] for n in COMBOS}).assign(net=net).to_csv(OUT + "oos_weights.csv")
    json.dump(res, open(OUT + "results.json", "w"), indent=1)
