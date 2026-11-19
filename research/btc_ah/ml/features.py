"""Feature builder for BTC off-hours -> MSTR open->close ML study.

Every feature for trading day D uses only data strictly before 09:25 ET on D
(BTC 1m bars whose start is < 09:25 ET) or MSTR daily rows dated strictly before D.
MSTR's own D open (09:30) is never used.
Sealed holdout: all BTC bars with ET wall time >= 2026-08-11 are dropped and all
daily rows after 2026-08-10 are dropped.
"""
import numpy as np
import pandas as pd

BTC = '/Users/rytty/CCP/BTC-Acum/data/btc_usd_1m_candles_polymarket_arb.parquet'
DAILY = '/Users/rytty/CCP/quant_v7/research/mstr_btc_0dte/mstr_daily_yf.parquet'
HOLD_EXCL = pd.Timestamp('2026-08-11')   # ET wall clock must be < this
HOLD_END = pd.Timestamp('2026-08-10')
MIN_NS = 60 * 10**9


def load_btc():
    b = pd.read_parquet(BTC)
    ts = b['timestamp'].dt.tz_convert('America/New_York').dt.tz_localize(None)
    keep = (ts < HOLD_EXCL).values
    t = ts.values[keep].astype('datetime64[ns]').astype(np.int64)
    out = pd.DataFrame({'t': t, 'o': b['open'].values[keep], 'h': b['high'].values[keep],
                        'l': b['low'].values[keep], 'c': b['close'].values[keep],
                        'v': b['volume'].values[keep]})
    return out.sort_values('t').reset_index(drop=True)


def load_daily():
    d = pd.read_parquet(DAILY)
    d = d[d.index <= HOLD_END]
    return d[['Open', 'High', 'Low', 'Close']].copy()


def _ts(date, hhmm):
    h, m = hhmm
    return pd.Timestamp(date).normalize().value + (h * 60 + m) * MIN_NS


def build(btc, daily):
    t = btc['t'].values
    C = btc['c'].values; H = btc['h'].values; L = btc['l'].values; V = btc['v'].values
    dates = daily.index
    n = len(dates)
    Od = daily['Open'].values; Hd = daily['High'].values; Ld = daily['Low'].values; Cd = daily['Close'].values
    lO, lC = np.log(Od), np.log(Cd)

    def price_at(x):
        i = np.searchsorted(t, x, side='left') - 1   # last bar starting strictly before x
        if i < 0 or t[i] < x - 10 * MIN_NS:
            return np.nan
        return C[i]

    # 16:00 ET anchor price for every trading day (used for BTC momentum; same as p0)
    c16 = np.array([price_at(_ts(d, (16, 0))) for d in dates])

    rows = []
    for k in range(1, n):
        D = dates[k]; P = dates[k - 1]
        a0 = _ts(P, (16, 0)); a1 = _ts(P, (20, 0)); a2 = _ts(D, (0, 0))
        a3 = _ts(D, (4, 0)); a4 = _ts(D, (8, 0)); a5 = _ts(D, (9, 25))
        p = [price_at(x) for x in (a0, a1, a2, a3, a4, a5)]
        lp = np.log(p)
        seg = np.diff(lp)                       # 5 segments
        lo = np.searchsorted(t, a0, side='left'); hi = np.searchsorted(t, a5, side='left')
        r = {'D': D, 'P': P, 'k': k}
        r['y'] = lC[k] - lO[k]                 # target (not a feature)
        r['btc_off'] = lp[-1] - lp[0]
        for i, nm in enumerate(['seg_16_20', 'seg_20_00', 'seg_00_04', 'seg_04_08', 'seg_08_0925']):
            r[nm] = seg[i]
        sabs = np.abs(seg).sum()
        r['late_share'] = seg[4] / sabs if sabs > 1e-9 else 0.0
        if hi > lo and np.isfinite(p[0]):
            path = np.concatenate([[p[0]], C[lo:hi]])
            lpath = np.log(path)
            r['rv_off'] = np.sqrt(np.sum(np.diff(lpath) ** 2))
            r['range_off'] = np.log(H[lo:hi].max() / L[lo:hi].min())
            rm = np.maximum.accumulate(path)
            r['maxdd_off'] = np.min(path / rm - 1)
            rn = np.minimum.accumulate(path)
            r['maxru_off'] = np.max(path / rn - 1)
            r['vsum_off'] = V[lo:hi].sum()
        else:
            for nm in ['rv_off', 'range_off', 'maxdd_off', 'maxru_off', 'vsum_off']:
                r[nm] = np.nan
        r['gap_days'] = (D - P).days
        r['weekend'] = int(r['gap_days'] >= 3)
        r['dow'] = D.weekday()
        # BTC momentum measured at the 16:00 anchor of P, back 1/5/20 trading days
        for m in (1, 5, 20):
            j = k - 1 - m
            r[f'btc_mom{m}'] = np.log(c16[k - 1] / c16[j]) if j >= 0 else np.nan
        rows.append(r)

    df = pd.DataFrame(rows).set_index('D')

    # volume vs trailing 20 windows (shifted: excludes today)
    vs = df['vsum_off']
    df['btc_volratio'] = np.log(vs / vs.shift(1).rolling(20, min_periods=20).mean())
    df = df.drop(columns=['vsum_off'])

    # MSTR daily features, using rows strictly before D (row j = k-1 = P)
    gap = pd.Series(np.r_[np.nan, lO[1:] - lC[:-1]], index=dates)   # gap of day j
    dret = pd.Series(np.r_[np.nan, np.diff(lC)], index=dates)
    mstr = pd.DataFrame(index=dates)
    mstr['m_prev_ret'] = dret
    mstr['m_mom5'] = lC - pd.Series(lC, index=dates).shift(5).values
    mstr['m_mom20'] = lC - pd.Series(lC, index=dates).shift(20).values
    mstr['m_prev_range'] = np.log(Hd / Ld)
    mstr['m_prev_oc'] = lC - lO
    mstr['m_gap_prev'] = gap
    mstr['m_gap_mean5'] = gap.rolling(5, min_periods=5).mean()
    mstr['m_gap_absmean20'] = gap.abs().rolling(20, min_periods=20).mean()
    mstr['m_vol20'] = dret.rolling(20, min_periods=20).std()
    mstr_lag = mstr.shift(1)                      # row P = date index k-1 -> used at D = date k
    mstr_lag = mstr_lag.reindex(df.index)         # aligned on D; values are from P
    feat = pd.concat([df, mstr_lag], axis=1)
    feat = feat.drop(columns=['P', 'k'])
    return feat


FEATURES = ['btc_off', 'seg_16_20', 'seg_20_00', 'seg_00_04', 'seg_04_08', 'seg_08_0925',
            'rv_off', 'range_off', 'maxdd_off', 'maxru_off', 'btc_volratio', 'late_share',
            'weekend', 'gap_days', 'dow',
            'btc_mom1', 'btc_mom5', 'btc_mom20',
            'm_prev_ret', 'm_mom5', 'm_mom20', 'm_prev_range', 'm_prev_oc',
            'm_gap_prev', 'm_gap_mean5', 'm_gap_absmean20', 'm_vol20']


if __name__ == '__main__':
    import os, time
    t0 = time.time()
    btc = load_btc(); daily = load_daily()
    print('btc bars', len(btc), 'last', pd.Timestamp(btc['t'].values[-1]), 'daily rows', len(daily), daily.index[-1].date(), flush=True)
    feat = build(btc, daily)
    feat.to_parquet('/Users/rytty/CCP/quant_v7/research/btc_ah/ml/features.parquet')
    print('built', feat.shape, 'in', round(time.time() - t0, 1), 's')
    print(feat[FEATURES + ['y']].isna().mean().round(3).to_string())
    print('last date', feat.index[-1].date(), 'first', feat.index[0].date())
