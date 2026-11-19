import pandas as pd, numpy as np, pickle
exec(open('test.py').read().split("rows=[]")[0])
pd.set_option('display.width',200)
R=pd.read_pickle('grid.pkl')
Rv=R[~R.t.isin(['SPY','XLP'])]
print(Rv.groupby(['ex','sig','rule'])[['dm','dt','cm','ct']].mean().round(2))
print('controls mean dev t / check t:'); print(R[R.t.isin(['SPY','XLP'])].groupby('t')[['dm','dt','cm','ct']].mean().round(2))
print('COMP rows'); print(R[(R.a=='COMP')&R.t.isin(['SMH','MU','SOXX','SPY','XLP'])&(R.rule=='sign')].round(2).to_string())
# gap diagnostic: Asia signal vs US overnight gap (open/prevclose-1) and vs post-open return
for t in ['MU','SMH','AMAT']:
  u=US[t]; z=P['Zr']['COMP'].reindex(u.index); gap=(u.o/u.prevclose-1)*1e4
  r30=(u.x1030/u.o-1)*1e4; rc=(u.xcl/u.o-1)*1e4
  d=pd.DataFrame({'z':z,'gap':gap,'r30':r30,'rc':rc}).dropna()
  d=d[(d.gap.abs()<2000)]
  print(t,'corr z~gap %.3f z~r30 %.3f z~rc %.3f n=%d'%(d.z.corr(d.gap),d.z.corr(d.r30),d.z.corr(d.rc),len(d)),
        'slope r30/gap per z: %.2f / %.2f'%(np.polyfit(d.z,d.gap,1)[0],np.polyfit(d.z,d.r30,1)[0]))
# long history daily open->close: composite and pairs
import yfinance
def dl(t):
    d=pd.read_pickle(f'cache/{t}_1d.pkl'); d.index=pd.to_datetime(d.index.tz_localize(None).normalize()); return d
print('\nLONG HISTORY daily Open->Close, sign rule, gross bp mean/t, by 3-year block')
for a,t in [('000660.KS','MU'),('005930.KS','MU'),('8035.T','AMAT'),('8035.T','LRCX'),('8035.T','KLAC'),('2330.TW','NVDA'),('COMP','SMH'),('COMP','SPY'),('COMP','XLP')]:
  d=dl(t); r=(d.Close/d.Open-1)*1e4
  Zs=P['Zr'][a].reindex(d.index); x=(np.sign(Zs)*r).dropna()
  x=x[x.index>='2010-01-01']
  blocks=x.groupby(x.index.year//4*4)
  print(a,t,'n %d mean %.2f t %.2f | '%(len(x),x.mean(),x.mean()/x.std()*len(x)**.5)+' '.join('%d:%.1f'%(k,v.mean()) for k,v in blocks))
