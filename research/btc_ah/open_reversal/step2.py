"""Step 2: frozen rules (FROZEN.md) out of sample.
A. 2024-01-01..2026-08-10 Mon/Fri sessions from val_days_full.pkl: MSTR spot from put-call parity (engine.Day.spot),
   8 bp per side (3 bp base + 5 bp extra slippage). Bars are built from consecutive spot points:
   open(j) = spot(j-1), close(j) = spot(j), high/low = max/min of the two. Base and worst fills use these.
   Sensitivity: 3 bp per side on the same path.
B. Cross-check on real stock minutes 2026-04-29..2026-08-10 (regular hours, UTC->ET), 3 bp per side.
   Also the same spot path on those same days, to compare parity spot against real prints.
Nothing after 2026-08-10 is used.
"""
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, '/Users/rytty/CCP/quant_v7')                          # for the pickled Day class
sys.path.insert(0, '/Users/rytty/CCP/quant_v7/research/btc_ah/open_reversal')
from core import (load_btc, btc_move_fn, load_minutes, trades, stats, NB, HOLD_END, HERE)

FROZEN = {'DN': dict(X=0.005, exit='10:00', stop='1%'),
          'BC': dict(X=0.01, exit='10:00', stop='none')}
CHK_WIN_START = pd.Timestamp('2026-04-29').date()
OOS_START = pd.Timestamp('2024-01-01').date()
COST_8BP = 0.0016
COST_3BP = 0.0006

bser = load_btc()
move = btc_move_fn(bser)

# ---------- A. parity-spot path, 2024-01..2026-08-10 ----------
import research.mstr_btc_0dte.engine as eng  # noqa: F401  (needed to unpickle Day objects)
raw = pickle.load(open('/Users/rytty/CCP/quant_v7/research/mstr_btc_0dte/val_days_full.pkl', 'rb'))
spot_days = []
for dy in raw:
    D = pd.Timestamp(dy.d).date()
    if D < OOS_START or D > HOLD_END:
        continue
    s = dy.spot.reindex(range(NB + 1)).to_numpy(dtype=float)
    if s[0] != s[0]:
        continue
    C = s[:NB].copy()
    O = np.empty(NB); O[0] = s[0]; O[1:] = s[:NB - 1]
    H = np.maximum(O, C); L = np.minimum(O, C)
    bm = move(D)
    if bm != bm:
        continue
    spot_days.append(dict(date=D, year=D.year, dow=pd.Timestamp(D).dayofweek, sb=int(np.sign(bm)),
                          O=O, H=H, L=L, C=C))
spot_days.sort(key=lambda x: x['date'])
print(f'A. spot days 2024-01..2026-08-10: {len(spot_days)}  dow counts {pd.Series([d["dow"] for d in spot_days]).value_counts().to_dict()}')
print(f'   range {spot_days[0]["date"]} .. {spot_days[-1]["date"]}; max date loaded {max(d["date"] for d in spot_days)}')

# ---------- B. real stock minutes 2026-04-29..2026-08-10 ----------
real = load_minutes(dev=False, lse=True)
real_days = []
for D, (O, H, L, C) in sorted(real.items()):
    if D < CHK_WIN_START or D > HOLD_END or O[0] != O[0]:
        continue
    bm = move(D)
    if bm != bm:
        continue
    real_days.append(dict(date=D, year=D.year, dow=pd.Timestamp(D).dayofweek, sb=int(np.sign(bm)),
                          O=O, H=H, L=L, C=C))
print(f'B. real stock days 2026-04-29..2026-08-10: {len(real_days)}')

FILT = {'MonFri': lambda x: x.dow.isin([0, 4]), 'AllWeekdays': lambda x: x.dow.notna()}


def pick(tr, fam, flip, fills):
    f = FROZEN[fam]
    return tr[(tr.fam == fam) & (tr.flip == flip) & (tr.X == f['X']) & (tr.exit == f['exit'])
              & (tr.stop == f['stop']) & (tr.fills == fills)]


def block(tr, label):
    rows = []
    for fam in ('DN', 'BC'):
        for flip in (False, True):
            for fills in ('base', 'worst'):
                g = pick(tr, fam, flip, fills)
                s = stats(g.net)
                yr = {f'yr{y}_bp': round(float(v.net.mean() * 1e4), 1) for y, v in g.groupby('year')}
                yn = {f'n{y}': int(len(v)) for y, v in g.groupby('year')}
                rows.append(dict(sample=label, rule=fam, control='flip' if flip else 'frozen', fills=fills,
                                 **s, **yr, **yn))
    return pd.DataFrame(rows)


def show(df):
    cols = ['sample', 'rule', 'control', 'fills', 'n', 'win', 'mean_bp', 't', 'avg_win_bp', 'avg_loss_bp']
    yrc = [c for c in df.columns if c.startswith('yr') and c.endswith('_bp')]
    nc = [c for c in df.columns if c.startswith('n20')]
    pd.set_option('display.width', 260); pd.set_option('display.max_columns', 40)
    print(df[cols + yrc + nc].round(3).to_string(index=False))


results = []

# A1: spot path, 8 bp per side (primary)
for filt_name, filt in FILT.items():
    days = spot_days
    if filt_name == 'MonFri':
        days = [d for d in spot_days if d['dow'] in (0, 4)]
    tr8 = trades(days, cost_rt=COST_8BP)
    b = block(tr8, f'A spot 8bp/side {filt_name}')
    results.append(b)
    show(b)

# A2: spot path, 3 bp per side sensitivity (Mon/Fri)
tr3 = trades([d for d in spot_days if d['dow'] in (0, 4)], cost_rt=COST_3BP)
b = block(tr3, 'A spot 3bp/side MonFri (sensitivity)')
results.append(b)
show(b)

# B1: real bars 3 bp per side, Mon/Fri and all weekdays, 2026-04-29..08-10
for filt_name, filt in FILT.items():
    days = real_days if filt_name == 'AllWeekdays' else [d for d in real_days if d['dow'] in (0, 4)]
    trb = trades(days, cost_rt=COST_3BP)
    b = block(trb, f'B real bars 3bp {filt_name} 2026-04-29..08-10')
    results.append(b)
    show(b)

# B2: parity spot on the same 2026 days (8 bp) for comparison with real bars
same = [d for d in spot_days if d['date'] >= CHK_WIN_START]
trs = trades(same, cost_rt=COST_8BP)
b = block(trs, 'B spot 8bp same 2026 days (all dow)')
results.append(b)
show(b)

out = pd.concat(results, ignore_index=True)
out.to_csv(HERE / 'step2_results.csv', index=False)
print('\nwrote step2_results.csv')
