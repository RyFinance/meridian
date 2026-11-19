import sys
sys.path.insert(0, '/Users/rytty/CCP/quant_v7/research/btc_ah/open_reversal')
import numpy as np, pandas as pd, datetime as dt
from core import *
bser = load_btc(); move = btc_move_fn(bser)
mins = load_minutes(dev=True)
D = dt.date(2020, 8, 18)
O, H, L, C = mins[D]
bm = move(D)
print('bm', bm, 'sign', np.sign(bm))
print('O0', O[0], 'C first 5', C[:5], 'C 1..60 max', np.nanmax(C[1:61]), 'min', np.nanmin(C[1:61]))
print('trig rip 1%:', first_trigger(O, C, 0.01, only=1), ' dip:', first_trigger(O, C, 0.01, only=-1))
print('nan count O', np.isnan(O).sum(), 'C', np.isnan(C).sum())
