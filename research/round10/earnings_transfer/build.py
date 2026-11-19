"""Build per-ticker daily table from 60m prepost bars (START-labeled: bar '09:00' spans 09:00-09:30,
so its close is the last pre-open print; '09:30' bar open = official open, its close = 10:30 price)."""
import pickle, pandas as pd, numpy as np
from universe import CLUSTERS, ALL
px = pickle.load(open('px60.pkl','rb')); ed = pickle.load(open('earn.pkl','rb'))
def daily(df):
    df = df.copy(); df['date'] = df.index.normalize().tz_localize(None); df['tm'] = df.index.strftime('%H:%M')
    rows = {}
    for d, g in df.groupby('date'):
        reg = g[(g.tm >= '09:30') & (g.tm < '16:00')]
        if len(reg) == 0 or reg.tm.iloc[0] != '09:30': continue
        pm = g[g.tm == '09:00']
        b1030 = reg[reg.tm == '10:30']
        rows[d] = dict(open=reg.Open.iloc[0], c1030=reg.Close.iloc[0],
                       o1030=b1030.Open.iloc[0] if len(b1030) else np.nan,
                       close=reg.Close.iloc[-1], last=reg.tm.iloc[-1],
                       pm=pm.Close.iloc[0] if len(pm) else np.nan)
    t = pd.DataFrame(rows).T
    t = t[t['last'] >= '12:30']  # drop truncated sessions (today)
    t['prev_close'] = t.close.shift(1)
    # require consecutive sessions in the SPY calendar handled later
    return t.drop(columns='last').astype(float)
D = {t: daily(df) for t, df in px.items()}
pickle.dump(D, open('daily.pkl','wb'))
rows = []
for t, e in ed.items():
    if e is None: continue
    for d in e.index.tz_convert('America/New_York'):
        rows.append((t, d.tz_localize(None).normalize(), d.hour + d.minute/60))
E_ = pd.DataFrame(rows, columns=['t','date','h']); E_.to_pickle('earn_flat.pkl')
print(len(D), len(E_), D['SPY'].tail(3))
