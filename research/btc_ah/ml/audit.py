"""Leakage audit for features.

Test: replace all BTC bars at or after a cutpoint T (ET) and all MSTR daily rows dated at or after
T_d with random multiplicative noise. Every feature for a trading day D whose 09:25 ET cutoff is
at or before T (and whose MSTR daily inputs are all dated before D) must be bit-identical.
Any change means the feature uses data at or after its decision time.
Also reports the feature-to-decision-time check: all features are rebuilt with the rows the
feature code can see; D's own 09:30 open is never read.
"""
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, '/Users/rytty/CCP/quant_v7/research/btc_ah/ml')
import features as F
from features import FEATURES

CUTS = ['2021-06-15 09:25', '2022-11-03 09:25', '2024-03-12 09:25', '2025-09-08 09:25']


def perturb_btc(btc, T, rng):
    b = btc.copy()
    m = b['t'].values >= T.value
    n = m.sum()
    for c in ['o', 'h', 'l', 'c']:
        b.loc[m, c] = b.loc[m, c].values * np.exp(rng.normal(0, 0.3, n))
    b.loc[m, 'v'] = b.loc[m, 'v'].values * np.exp(rng.normal(0, 1.0, n))
    return b


def perturb_daily(daily, Td, rng):
    d = daily.copy()
    m = d.index >= Td
    n = m.sum()
    for c in ['Open', 'High', 'Low', 'Close']:
        d.loc[m, c] = d.loc[m, c].values * np.exp(rng.normal(0, 0.3, n))
    return d


def main():
    btc = F.load_btc(); daily = F.load_daily()
    base = F.build(btc, daily)
    rng = np.random.default_rng(42)
    fails = 0
    checked_total = 0
    for cut in CUTS:
        T = pd.Timestamp(cut)
        # MSTR daily rows dated >= T.date() perturbed as well; D with cutoff <= T only use rows < D
        pb = perturb_btc(btc, T, rng)
        pdly = perturb_daily(daily, T.normalize(), rng)
        alt = F.build(pb, pdly)
        ok_days = base.index[[pd.Timestamp(d).normalize().value + 9 * 3600e9 + 25 * 60e9 <= T.value
                              for d in base.index]]
        # strict: the cutoff of D must be <= T and the row D itself is not part of the features
        ok_days = ok_days[ok_days.normalize() <= T.normalize()]
        a = base.loc[ok_days, FEATURES]; b = alt.loc[ok_days, FEATURES]
        same = np.isclose(a.values, b.values, equal_nan=True, rtol=0, atol=0)
        bad = (~same).sum()
        checked_total += same.size
        fails += bad
        cols_bad = [c for c, s in zip(FEATURES, (~same).any(axis=0)) if s]
        print(f'cut {cut}: days checked {len(ok_days)}, feature cells changed {bad}, cols {cols_bad}', flush=True)
    print(f'TOTAL feature cells checked {checked_total}, changed {fails}')


if __name__ == '__main__':
    main()
