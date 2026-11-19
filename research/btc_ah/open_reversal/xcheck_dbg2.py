import sys
sys.path.insert(0, '/Users/rytty/CCP/quant_v7/research/btc_ah/shares_mgmt')
sys.path.insert(0, '/Users/rytty/CCP/quant_v7/research/btc_ah/open_reversal')
import numpy as np, pandas as pd, datetime as dt
import sim
from core import *
bser = load_btc(); move = btc_move_fn(bser)
mins = load_minutes(dev=True)
for D in [dt.date(2020, 12, 9), dt.date(2021, 1, 12)]:
    r = next(x for x in sim.ROWS if x['date'] == D)
    O, H, L, C = mins[D]
    print(D, 'prior sb', sim.sign_base(r, 'with'), 'prior btc_move', round(r['btc_move'], 5), 'mine bm', round(move(D), 5))
    print('  prior O0', r['O'][0], 'prior ent', sim.entry_of('PB10', r, sim.sign_base(r, 'with'), False))
    print('  mine O0', O[0], 'C[:8]', np.round(C[:8], 3), 'first_trigger only=', first_trigger(O, C, 0.01, only=-int(np.sign(move(D)))))
    print('  prior C[:8]', np.round(np.array(r['C'][:8], dtype=float), 3))
