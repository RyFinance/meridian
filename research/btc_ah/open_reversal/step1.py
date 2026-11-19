"""Step 1: reproduce on MSTR regular-hours minutes 2020-08-12..2023-12-31, 3 bp/side, base and worst fills.
Dev = dates <= 2022-06-30 (selection), check = 2022-07-01..2023-12-31. Nothing after 2026-08-10 is loaded.
Output: step1_summary.csv (all 96 rules x 2 fills, plus flip controls), step1_top_dev.csv.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from core import (load_btc, btc_move_fn, load_minutes, trades, summarize, DEV_CUT, CHK_START,
                  S1_END, COST_3BP, HERE)

pd.set_option('display.width', 250)
pd.set_option('display.max_columns', 40)

bser = load_btc()
move = btc_move_fn(bser)
mins = load_minutes(dev=True, lse=False)
days = []
for D, (O, H, L, C) in sorted(mins.items()):
    if D > S1_END or O[0] != O[0]:
        continue
    bm = move(D)
    if bm != bm:
        continue
    days.append(dict(date=D, year=D.year, dow=pd.Timestamp(D).dayofweek, sb=int(np.sign(bm)),
                     O=O, H=H, L=L, C=C))
print(f'step1 days: {len(days)}  [{days[0]["date"]} .. {days[-1]["date"]}]')
print(f'  dev days {sum(d["date"] <= DEV_CUT for d in days)}, check days {sum(d["date"] >= CHK_START for d in days)}')

tr = trades(days, cost_rt=COST_3BP)
tr.to_pickle(HERE / 'step1_trades.pkl')
periods = {'dev': lambda g: g.date <= DEV_CUT,
           'chk': lambda g: g.date >= CHK_START,
           'all': lambda g: g.date.notna()}
S = summarize(tr, periods)
S.to_csv(HERE / 'step1_summary.csv', index=False)
print(f'rules (fam x X x exit x stop) = {S[["fam","X","exit","stop"]].drop_duplicates().shape[0]}, '
      f'x 2 fill models, plus flip controls')

cols = ['fam', 'flip', 'X', 'exit', 'stop', 'fills', 'dev_n', 'dev_win', 'dev_mean_bp', 'dev_t',
        'chk_n', 'chk_win', 'chk_mean_bp', 'chk_t', 'all_mean_bp', 'all_t']
base = S[(~S.flip)]
print('\nBase fills (3 bp/side), DN and BC, top 8 by dev t (dev n>=50):')
top = base[(base.fills == 'base') & (base.dev_n >= 50)].sort_values('dev_t', ascending=False)
print(top[cols].head(8).round(3).to_string(index=False))
top.head(8).to_csv(HERE / 'step1_top_dev.csv', index=False)

print('\nSelection candidates (dev only, base fills, not flip): best per family by dev t, n>=50:')
for fam in ['DN', 'BC']:
    print(base[(base.fam == fam) & (base.fills == 'base') & (base.dev_n >= 50)]
          .sort_values('dev_t', ascending=False)[cols].head(1).round(3).to_string(index=False))

print('\nFlip control (same triggers, side reversed), base fills, dev/check means:')
fl = S[S.flip & (S.fills == 'base')]
print(fl[['fam', 'X', 'exit', 'stop', 'dev_n', 'dev_mean_bp', 'dev_t', 'chk_n', 'chk_mean_bp', 'chk_t']]
      .sort_values(['fam', 'dev_t'], ascending=[True, False]).head(12).round(3).to_string(index=False))

print('\nWorst fills: count of rules with dev mean > 0 and chk mean > 0 (base fills):')
bb = base[base.fills == 'base']
ww = base[base.fills == 'worst']
print('  base dev>0:', int((bb.dev_mean_bp > 0).sum()), ' base chk>0:', int((bb.chk_mean_bp > 0).sum()),
      ' worst dev>0:', int((ww.dev_mean_bp > 0).sum()), ' worst chk>0:', int((ww.chk_mean_bp > 0).sum()))
