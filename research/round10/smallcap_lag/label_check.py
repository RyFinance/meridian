# verify 60m futures bars are START-labeled
import pandas as pd, numpy as np
ld=lambda t,iv:pd.read_pickle(f'cache/{t}_{iv}.pkl')
for f in ['ES=F','NQ=F','RTY=F']:
    z=ld(f,'60m'); z.index=z.index.tz_convert('America/New_York')
    hrs=pd.Series(z.index.hour).value_counts().sort_index()
    print(f,'bar counts by label hour:',dict(hrs))
# regress SPY 09:30-10:30 return (bar start 09:30) on ES bar returns by label hour
z=ld('ES=F','60m'); z.index=z.index.tz_convert('America/New_York')
s=ld('SPY','60m'); s.index=s.index.tz_convert('America/New_York')
zr=np.log(z.Close/z.Open)
rows=[]
for d,g in s.groupby(s.index.normalize()):
    b=g[g.index.time==pd.Timestamp('09:30').time()]
    if not len(b): continue
    r={'spy':np.log(b.Close.iloc[0]/b.Open.iloc[0])}
    for h in [8,9,10,11]:
        t=d+pd.Timedelta(hours=h)
        r[f'es{h}']=zr.get(t,np.nan)
    rows.append(r)
X=pd.DataFrame(rows).dropna()
print(X.corr()['spy'].round(3).to_dict())
# also 5-min check isn't available; cross-check close of bar 15:00 vs SPY close 15:30 bar Close
