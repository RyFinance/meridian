"""Walk-forward ML: BTC off-hours features -> MSTR open->close (sign trade, 3bp/side).

Expanding train window starting 2020-08-12; OOS 2022-01-01..2026-08-10.
Schemes: yearly retrain and quarterly retrain. Models: LightGBM regressor on the
log return, and logistic regression on the sign. Trades: sign(pred) when |pred| is
above the q-quantile of |pred| on the training window (q=0 trades every day).
Shuffled control: same pipeline with training targets permuted within each training window.
"""
import json
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

import sys
sys.path.insert(0, '/Users/rytty/CCP/quant_v7/research/btc_ah/ml')
from features import FEATURES

OUT = '/Users/rytty/CCP/quant_v7/research/btc_ah/ml'
TRAIN_START = pd.Timestamp('2020-08-12')
OOS_START = pd.Timestamp('2022-01-01')
OOS_END = pd.Timestamp('2026-08-10')
DEV_END = pd.Timestamp('2022-06-30')          # brief rule 5: dev <= 2022-06
COST = 0.0006                                 # 3 bp per side, 2 sides
QS = [0.0, 0.5, 0.7, 0.8, 0.9]
SEEDS = [1, 2, 3, 4, 5]


def make_blocks(scheme):
    starts = []
    if scheme == 'yearly':
        for y in range(2022, 2027):
            starts.append(pd.Timestamp(f'{y}-01-01'))
        ends = [s + pd.DateOffset(years=1) for s in starts]
    else:
        starts = list(pd.date_range('2022-01-01', '2026-07-01', freq='QS'))
        ends = [s + pd.DateOffset(months=3) for s in starts]
    return [(s, min(e, OOS_END + pd.Timedelta(days=1))) for s, e in zip(starts, ends)]


def fit_predict(model_name, Xtr, ytr, Xte, seed):
    if model_name == 'lgb':
        m = lgb.LGBMRegressor(n_estimators=300, learning_rate=0.02, num_leaves=8,
                              min_child_samples=50, subsample=0.7, subsample_freq=1,
                              colsample_bytree=0.7, reg_lambda=5.0, verbose=-1,
                              random_state=seed, n_jobs=2)
        m.fit(Xtr, ytr)
        return m.predict(Xte), m.predict(Xtr)
    m = make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=2000))
    m.fit(Xtr, (ytr > 0).astype(int))
    return m.decision_function(Xte), m.decision_function(Xtr)


def walk_forward(df, scheme, model_name, shuffle_seed=None):
    parts = []
    importances = []
    for s, e in make_blocks(scheme):
        tr = df[(df.index >= TRAIN_START) & (df.index < s)]
        te = df[(df.index >= s) & (df.index < e)]
        if len(te) == 0:
            continue
        ytr = tr['y'].values.copy()
        if shuffle_seed is not None:
            rng = np.random.default_rng(shuffle_seed * 1000 + s.year * 10 + s.month)
            ytr = rng.permutation(ytr)
        Xtr = tr[FEATURES].values; Xte = te[FEATURES].values
        pte, ptr = fit_predict(model_name, Xtr, ytr, Xte, seed=7)
        if model_name == 'lgb' and shuffle_seed is None:
            imp = lgb.LGBMRegressor(n_estimators=300, learning_rate=0.02, num_leaves=8,
                                    min_child_samples=50, subsample=0.7, subsample_freq=1,
                                    colsample_bytree=0.7, reg_lambda=5.0, verbose=-1,
                                    random_state=7, n_jobs=2).fit(Xtr, ytr)
            importances.append(pd.Series(imp.booster_.feature_importance('gain'), index=FEATURES))
        block = pd.DataFrame({'D': te.index, 'pred': pte, 'y': te['y'].values, 'block': str(s.date())})
        # thresholds: quantiles of |pred| on the TRAINING window only
        for q in QS:
            block[f'thr_{q}'] = np.quantile(np.abs(ptr), q)
        parts.append(block)
    out = pd.concat(parts).set_index('D')
    imp = None
    if importances:
        imp = (pd.concat(importances, axis=1).div(pd.concat(importances, axis=1).sum()).mean(axis=1)
               .sort_values(ascending=False))
    return out, imp


def trades(oos, q, flip=False):
    pos = np.sign(oos['pred'].values)
    take = np.abs(oos['pred'].values) > oos[f'thr_{q}'].values
    if q == 0.0:
        take = np.abs(oos['pred'].values) > 0
    p = pos * (-1 if flip else 1)
    gross = p * (np.exp(oos['y'].values) - 1)
    net = np.where(take, gross - COST, np.nan)
    t = pd.DataFrame({'net': net, 'gross': np.where(take, gross, np.nan)}, index=oos.index).dropna()
    return t


def stats(t):
    n = len(t)
    if n < 3:
        return dict(n=n)
    x = t['net'].values
    sd = x.std(ddof=1)
    yr = t.groupby(t.index.year)['net'].mean() * 1e4
    return dict(n=n,
                hit=float((x > 0).mean()),
                mean_bp=float(x.mean() * 1e4),
                t=float(x.mean() / (sd / np.sqrt(n))) if sd > 0 else np.nan,
                avg_win_bp=float(x[x > 0].mean() * 1e4) if (x > 0).any() else np.nan,
                avg_loss_bp=float(x[x <= 0].mean() * 1e4) if (x <= 0).any() else np.nan,
                per_year_bp={int(k): round(float(v), 1) for k, v in yr.items()})


def evaluate(oos, q, flip=False):
    return stats(trades(oos, q, flip))


def main():
    df = pd.read_parquet(f'{OUT}/features.parquet')
    df = df[(df.index >= TRAIN_START) & (df.index <= OOS_END)]
    df = df.dropna(subset=FEATURES + ['y'])
    print('rows', len(df), 'first', df.index[0].date(), 'last', df.index[-1].date(), flush=True)

    results = {}
    tables = {}
    importances = {}
    for scheme in ['yearly', 'quarterly']:
        for mname in ['lgb', 'logit']:
            oos, imp = walk_forward(df, scheme, mname)
            tables[(scheme, mname)] = oos
            if imp is not None:
                importances[scheme] = imp
            for q in QS:
                key = f'{scheme}|{mname}|q{q}'
                full = trades(oos, q)
                dev = trades(oos[oos.index <= DEV_END], q)
                chk = trades(oos[oos.index > DEV_END], q)
                flip = trades(oos, q, flip=True)
                results[key] = dict(full=stats(full), dev=stats(dev), check=stats(chk),
                                    flip_full=stats(flip))
                results[key]['flip_full'].pop('per_year_bp', None)
                print(key, 'n', len(full), 'mean_bp', round(full['net'].mean() * 1e4, 1) if len(full) else None,
                      't', round(results[key]['full'].get('t', np.nan), 2), flush=True)

    # shuffled-label control, same pipeline
    shuf = {}
    for scheme in ['yearly', 'quarterly']:
        for mname in ['lgb', 'logit']:
            accum = {q: [] for q in QS}
            for seed in SEEDS:
                oos, _ = walk_forward(df, scheme, mname, shuffle_seed=seed)
                for q in QS:
                    t = trades(oos, q)
                    accum[q].append((len(t), t['net'].mean() * 1e4 if len(t) else np.nan,
                                     (t['net'] > 0).mean() if len(t) else np.nan,
                                     (t['net'].mean() / (t['net'].std(ddof=1) / np.sqrt(len(t)))) if len(t) > 2 else np.nan))
            for q in QS:
                a = np.array(accum[q], dtype=float)
                shuf[f'{scheme}|{mname}|q{q}'] = dict(n_mean=float(np.nanmean(a[:, 0])),
                                                      mean_bp_mean=float(np.nanmean(a[:, 1])),
                                                      mean_bp_sd=float(np.nanstd(a[:, 1])),
                                                      hit_mean=float(np.nanmean(a[:, 2])),
                                                      t_mean=float(np.nanmean(a[:, 3])),
                                                      t_max=float(np.nanmax(a[:, 3])))
                print('shuffled', scheme, mname, q, {k: round(v, 3) for k, v in shuf[f'{scheme}|{mname}|q{q}'].items()}, flush=True)

    # unconditional benchmarks on the same OOS days
    base = df[(df.index >= OOS_START) & (df.index <= OOS_END)]
    bench = {'always_long_net_bp': float((np.exp(base['y']) - 1 - COST).mean() * 1e4),
             'always_short_net_bp': float((-(np.exp(base['y']) - 1) - COST).mean() * 1e4),
             'n_days': int(len(base))}

    out = dict(results=results, shuffled=shuf, bench=bench,
               importance_yearly={k: round(v, 4) for k, v in importances.get('yearly', pd.Series()).items()},
               n_rules=len(results))
    with open(f'{OUT}/results.json', 'w') as f:
        json.dump(out, f, indent=1, default=float)
    tables[('yearly', 'lgb')].to_parquet(f'{OUT}/oos_yearly_lgb.parquet')
    tables[('yearly', 'logit')].to_parquet(f'{OUT}/oos_yearly_logit.parquet')
    print('bench', bench)
    print('importance', importances.get('yearly', pd.Series()).round(3).to_string())


if __name__ == '__main__':
    main()
