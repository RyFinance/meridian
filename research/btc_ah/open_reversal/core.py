"""Shared helpers for the MSTR open-reversal study (agent: open_reversal).

Rule family (direction-neutral, DN): after the 09:30 open, the first minute whose close is
<= open*(1-X) triggers a LONG; the first minute whose close is >= open*(1+X) triggers a SHORT.
The trade is the reversal: side = -trigger. Entry at the open of the next bar, exit at the
open of the exit bar (10:00/10:30/11:00/12:00 ET), optional stop (1%/2% from entry).

BTC-conditioned family (BC): same trigger, but only when the MSTR move runs AGAINST BTC's
16:00->09:25 ET direction (trigger = -sign(BTC move)). Side = -trigger = sign(BTC move).

Flip control: same trigger and same timing, side reversed (momentum instead of reversal).

Data: MSTR minutes are indexed by minute from 09:30 ET (index 0 = 09:30 bar, 389 = 15:59 bar).
Nothing dated after 2026-08-10 is loaded.
"""
from __future__ import annotations

import glob
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path('/Users/rytty/CCP/quant_v7')
HERE = ROOT / 'research/btc_ah/open_reversal'
BTC_PATH = Path('/Users/rytty/CCP/BTC-Acum/data/btc_usd_1m_candles_polymarket_arb.parquet')
DEV_DIR = ROOT / 'research/mstr_btc_0dte/stock_1m_dev'
LSE_PATH = ROOT / 'research/mstr_btc_0dte/mstr_stock_1m_lse.parquet'
ET = 'America/New_York'
HOLD_END = pd.Timestamp('2026-08-10').date()
NB = 390
RTH0 = 570
NAN = float('nan')
DEV_CUT = pd.Timestamp('2022-06-30').date()
CHK_START = pd.Timestamp('2022-07-01').date()
S1_END = pd.Timestamp('2023-12-31').date()
XS = [0.005, 0.01, 0.015, 0.02]
EXITS = {'10:00': 30, '10:30': 60, '11:00': 90, '12:00': 150}   # minutes after 09:30
STOPS = [None, 0.01, 0.02]
FAMS = ['DN', 'BC']
COST_3BP = 0.0006   # 3 bp per side, round trip


def load_btc() -> pd.Series:
    b = pd.read_parquet(BTC_PATH)
    b = b[b['timestamp'] <= pd.Timestamp('2026-08-10 23:59:59', tz='UTC')]
    bt = pd.DatetimeIndex(b['timestamp'].dt.tz_convert(ET).dt.tz_localize(None))
    s = pd.Series(b['close'].values, index=bt).sort_index()
    return s[~s.index.duplicated(keep='last')]


def btc_move_fn(bser: pd.Series):
    idx = bser.index

    def px(t):
        t0 = pd.Timestamp(t) - pd.Timedelta(minutes=1)   # last bar closed by t
        i = idx.searchsorted(t0, side='right') - 1
        if i < 0 or (t0 - idx[i]) > pd.Timedelta(minutes=10):
            return NAN
        return float(bser.iloc[i])

    def move(D):
        P = (pd.Timestamp(D) - pd.offsets.BDay(1)).date()        # previous weekday 16:00 ET
        a = px(pd.Timestamp(P) + pd.Timedelta(hours=16))
        b = px(pd.Timestamp(D) + pd.Timedelta(hours=9, minutes=25))
        return b / a - 1 if a == a and b == b else NAN
    return move


def load_minutes(dev=True, lse=False) -> dict:
    frames = []
    if dev:
        for f in sorted(glob.glob(str(DEV_DIR / '*.parquet'))):
            d = pd.read_parquet(f)
            ts = pd.to_datetime(d['time'], utc=True).dt.tz_convert(ET).dt.tz_localize(None)
            frames.append(pd.DataFrame({'ts': ts, 'o': d['open'].values, 'h': d['high'].values,
                                        'l': d['low'].values, 'c': d['close'].values}))
    if lse:
        L = pd.read_parquet(LSE_PATH)
        lts = pd.to_datetime(L['ts']).dt.tz_localize('UTC').dt.tz_convert(ET).dt.tz_localize(None)
        frames.append(pd.DataFrame({'ts': lts, 'o': L['open'].values, 'h': L['high'].values,
                                    'l': L['low'].values, 'c': L['close'].values}))
    m = pd.concat(frames, ignore_index=True)
    m['date'] = m.ts.dt.date
    m = m[m.date <= HOLD_END]
    m['mi'] = m.ts.dt.hour * 60 + m.ts.dt.minute - RTH0
    m = m[(m.mi >= 0) & (m.mi < NB)].drop_duplicates(['date', 'mi'], keep='last')
    out = {}
    for d, g in m.groupby('date'):
        O = np.full(NB, NAN); H = np.full(NB, NAN); L_ = np.full(NB, NAN); C = np.full(NB, NAN)
        k = g.mi.values
        O[k] = g.o.values; H[k] = g.h.values; L_[k] = g.l.values; C[k] = g.c.values
        # a minute with no print is a stale bar: price stays at the last close (same as prior sim's
        # last-close fallback); leading gaps before the first print stay NaN
        last = NAN
        for i in range(NB):
            if C[i] == C[i]:
                last = C[i]
            elif last == last:
                O[i] = H[i] = L_[i] = C[i] = last
        out[d] = (O, H, L_, C)
    return out


def first_trigger(O, C, X, only=None):
    """First minute m (close-based, known at bar m close) where the close is beyond open*(1 -/+ X).
    only=None: either side (DN). only=-1 or +1: wait for that side only (BC: the side against BTC).
    Returns (m, t) with t=-1 for a dip, +1 for a rip, or None."""
    o0 = O[0]
    if o0 != o0:
        return None
    lo, hi = o0 * (1 - X), o0 * (1 + X)
    for m in range(NB - 1):
        c = C[m]
        if c != c:
            continue
        if c <= lo and only in (None, -1):
            return m, -1
        if c >= hi and only in (None, 1):
            return m, 1
    return None


def simulate(O, H, L, C, m, g, T, stop, fills):
    """Entry at open of bar m+1 (worst: bar high for longs / low for shorts); exit at open of bar T
    (worst: bar low for longs / high for shorts) unless a stop is hit first. g = +1 long, -1 short.
    Stops are checked on bars e..T-1. Gross return (sign adjusted), or None."""
    e = m + 1
    if e >= T:
        return None
    P = O[e] if fills == 'base' else (H[e] if g > 0 else L[e])
    if P != P:
        return None
    exit_px = None
    if stop is not None:
        sl = P * (1 - g * stop)
        for j in range(e, T):
            if O[j] != O[j] or H[j] != H[j] or L[j] != L[j]:
                continue
            if g > 0:
                if O[j] <= sl:
                    exit_px = O[j] if fills == 'base' else L[j]; break
                if L[j] <= sl:
                    exit_px = sl if fills == 'base' else L[j]; break
            else:
                if O[j] >= sl:
                    exit_px = O[j] if fills == 'base' else H[j]; break
                if H[j] >= sl:
                    exit_px = sl if fills == 'base' else H[j]; break
    if exit_px is None:
        if fills == 'base':
            exit_px = O[T]
        else:
            exit_px = L[T] if g > 0 else H[T]
        if exit_px != exit_px:
            return None
    return g * (exit_px / P - 1)


def trades(days, cost_rt=COST_3BP, fills_list=('base', 'worst'), flips=(False, True)) -> pd.DataFrame:
    """One trade per day per variant. days: list of dicts with date, year, dow, sb (BTC sign), O,H,L,C."""
    rows = []
    for dd in days:
        for X in XS:
            for fam in FAMS:
                if fam == 'DN':
                    trig = first_trigger(dd['O'], dd['C'], X)
                else:   # BC: wait for the move against BTC's direction (prior rule's directional wait)
                    if dd['sb'] == 0:
                        continue
                    trig = first_trigger(dd['O'], dd['C'], X, only=-dd['sb'])
                if trig is None:
                    continue
                m, t = trig
                for flip in flips:
                    g = t if flip else -t          # reversal = -trigger; flip control = +trigger
                    for tn, T in EXITS.items():
                        for stop in STOPS:
                            for fills in fills_list:
                                r = simulate(dd['O'], dd['H'], dd['L'], dd['C'], m, g, T, stop, fills)
                                if r is None:
                                    continue
                                rows.append((dd['date'], dd['year'], dd['dow'], fam, flip, X, tn,
                                             'none' if stop is None else f'{stop * 100:g}%',
                                             fills, t, dd['sb'], m, r - cost_rt))
    return pd.DataFrame(rows, columns=['date', 'year', 'dow', 'fam', 'flip', 'X', 'exit', 'stop',
                                       'fills', 'trig', 'sb', 'm', 'net'])


def stats(x) -> dict:
    x = np.asarray(x, dtype=float)
    n = len(x)
    if n < 2:
        return dict(n=n, win=NAN, mean_bp=NAN, t=NAN, avg_win_bp=NAN, avg_loss_bp=NAN)
    sd = x.std(ddof=1)
    w, lo = x[x > 0], x[x <= 0]
    return dict(n=n, win=float((x > 0).mean()), mean_bp=float(x.mean() * 1e4),
                t=float(x.mean() / sd * np.sqrt(n)) if sd > 0 else NAN,
                avg_win_bp=float(w.mean() * 1e4) if len(w) else NAN,
                avg_loss_bp=float(lo.mean() * 1e4) if len(lo) else NAN)


KEYS = ['fam', 'flip', 'X', 'exit', 'stop', 'fills']


def summarize(tr: pd.DataFrame, periods: dict) -> pd.DataFrame:
    """periods: name -> boolean mask function on the trade frame."""
    out = []
    for key, g in tr.groupby(KEYS):
        row = dict(zip(KEYS, key))
        for pname, pmask in periods.items():
            s = stats(g.loc[pmask(g), 'net'])
            row.update({f'{pname}_{k}': v for k, v in s.items()})
        for yr, gy in g.groupby('year'):
            row[f'yr{yr}_mean_bp'] = float(gy.net.mean() * 1e4)
        out.append(row)
    return pd.DataFrame(out)
