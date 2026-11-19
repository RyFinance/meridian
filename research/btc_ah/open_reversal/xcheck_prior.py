"""Cross-check: run the prior agent's sim.py (read-only import) for the lead's rule to compare counts."""
import sys
sys.path.insert(0, '/Users/rytty/CCP/quant_v7/research/btc_ah/shares_mgmt')
import sim
for d in ['with', 'against', 'conv']:
    t = sim.get(d, 'PB10', ('time', 60), False)
    f = sim.get(d, 'PB10', ('time', 60), True)
    dv = t[t.period == 'dev']; ck = t[t.period == 'chk']
    print(d, 'dev n', len(dv), 'mean bp', round(dv.net.mean() * 1e4, 2), 'chk n', len(ck), 'mean bp', round(ck.net.mean() * 1e4, 2),
          '| flip dev mean', round(f[f.period == 'dev'].net.mean() * 1e4, 2), 'n', len(f[f.period == 'dev']))
# how many days had a 1% dip within 09:31-10:29 in BTC's direction, vs any move
import numpy as np
cnt = {'with_trig': 0, 'days': 0}
for r in sim.ROWS:
    if r['period'] != 'dev':
        continue
    cnt['days'] += 1
print('dev rows', cnt['days'])
