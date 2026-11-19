import sys
sys.path.insert(0, '/Users/rytty/CCP/quant_v7/research/btc_ah/shares_mgmt')
import sim as S
import pandas as pd
pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 80)
specs = [
 ('conv', 'PB10', ('time', 60), None),
 ('with', 'PB10', ('time', 60), None),
 ('with', 'PB10', ('time', 60), 'Tue'),
 ('conv', 'E0931', ('time', 150), 'Fri'),
 ('with', 'E0931', ('time', 389), None),
 ('against', 'E0931', ('time', 389), None),
]
cols = ['rule','dev_n','dev_wr','dev_mean','dev_t','dev_aw','dev_al','chk_n','chk_wr','chk_mean','chk_t','dev_flip_mean','dev_flip_t','chk_flip_mean','chk_flip_t']
rows = []
for d, e, ex, f in specs:
    rows.append(S.evaluate(d, e, ex, filt=f))
    rows.append(S.evaluate(d, e, ex, filt=f, worst=True))
R = pd.DataFrame(rows)
print(R[cols].round(3).to_string(index=False))
print()
for d, e, ex, f in specs[:2]:
    r = S.evaluate(d, e, ex, filt=f)
    print(r['rule'], 'dev by year:', r['dev_by_year_bp'])
# per-year chk for top 1
tN = S.get('conv','PB10',('time',60),False)
print('conv|PB10 chk trades:', len(tN[tN.period=='chk']), 'chk days win', (tN[tN.period=='chk'].net>0).mean().round(3))
print('chk per-year means (bp):', (tN[tN.period=='chk'].groupby('year').net.mean()*1e4).round(1).to_dict())
tN2 = S.get('with','PB10',('time',60),False)
print('with|PB10 chk per-year (bp):', (tN2[tN2.period=='chk'].groupby('year').net.mean()*1e4).round(1).to_dict())
print('BETA', round(S.BETA,3), 'cuts', S.QS)
