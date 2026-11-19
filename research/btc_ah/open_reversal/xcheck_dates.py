"""Diagnose: compare trade dates of prior sim (with|PB10|time60) and this study's BC 1% 10:30 base."""
import sys
sys.path.insert(0, '/Users/rytty/CCP/quant_v7/research/btc_ah/shares_mgmt')
sys.path.insert(0, '/Users/rytty/CCP/quant_v7/research/btc_ah/open_reversal')
import pandas as pd
import sim
p = sim.get('with', 'PB10', ('time', 60), False)
p = p[p.period == 'dev'].set_index('date')
tr = pd.read_pickle('/Users/rytty/CCP/quant_v7/research/btc_ah/open_reversal/step1_trades.pkl')
m = tr[(tr.fam == 'BC') & (~tr.flip) & (tr.X == 0.01) & (tr.exit == '10:30') & (tr.stop == 'none') & (tr.fills == 'base')]
m = m.set_index('date')
print('prior dev n', len(p), ' mine (all period) n', len(m))
pd_ = set(p.index); md = set(m.index)
print('in prior not mine', len(pd_ - md), ' in mine not prior (dev period)', len([d for d in md if d <= sim.DEV_END]) - len([d for d in md if d in pd_]))
ex = sorted(pd_ - md)[:5]
print('example prior-only dates', ex)
for d in ex[:3]:
    r = next(x for x in sim.ROWS if x['date'] == d)
    print(d, 'sb', sim.sign_base(r, 'with'), 'O0', r['O'][0], 'min C 1..60', min(c for c in r['C'][1:61] if c == c), 'max', max(c for c in r['C'][1:61] if c == c))
    print('   mine m/t:', m.loc[d] if d in md else 'no trade in mine')
