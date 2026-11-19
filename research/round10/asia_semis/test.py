import pandas as pd, numpy as np, pickle, itertools
P=pickle.load(open('panel.pkl','rb'))
US=P['US']
asia=['000660.KS','005930.KS','2330.TW','8035.T','6857.T','6920.T','COMP']
tick=['MU','NVDA','AMD','AVGO','AMAT','LRCX','KLAC','MRVL','SMH','SOXX','SPY','XLP','TER']
cost={t:2 for t in tick}; cost['TER']=5; cost['MRVL']=5   # bp per side
natural={('000660.KS','MU'),('005930.KS','MU'),('8035.T','AMAT'),('8035.T','LRCX'),('8035.T','KLAC'),
 ('6920.T','AMAT'),('6920.T','LRCX'),('6920.T','KLAC'),('6857.T','TER'),('6857.T','KLAC'),
 ('2330.TW','NVDA'),('2330.TW','AMD'),('2330.TW','SMH'),('COMP','SMH')}
dates=US['SPY'].index
split=dates[int(len(dates)*0.55)]
print('sample',dates[0].date(),dates[-1].date(),len(dates),'split',split.date())
def trades(a,t,sig,rule,exit_,flip=False):
    u=US[t]; Z=P['Zr'] if sig=='raw' else P['Zs']
    z=Z[a].reindex(u.index)
    if rule=='sign': pos=np.sign(z)
    else: pos=pd.Series(np.where(z>=1,1,np.where(z<=-1,-1,0)),index=u.index).where(z.notna())
    if flip: pos=-pos
    ex=u[{'1030':'x1030','1130':'x1130','close':'xcl'}[exit_]]
    r=(ex/u['o']-1)
    net=pos*r*1e4-2*cost[t]
    m=(pos!=0)&pos.notna()&r.notna()
    return net[m]
def stat(x):
    if len(x)<10: return (len(x),np.nan,np.nan,np.nan)
    return (len(x),x.mean(),x.mean()/x.std()*np.sqrt(len(x)),(x>0).mean())
rows=[]
for a in asia:
  for t in tick:
    for sig in ['raw','res']:
      for rule in ['sign','z1']:
        for ex in ['1030','1130','close']:
          x=trades(a,t,sig,rule,ex)
          d=x[x.index<split]; c=x[x.index>=split]
          # gross (add costs back) for info
          s=stat(d); k=stat(c)
          rows.append(dict(a=a,t=t,sig=sig,rule=rule,ex=ex,nat=(a,t) in natural,dn=s[0],dm=s[1],dt=s[2],dw=s[3],cn=k[0],cm=k[1],ct=k[2],cw=k[3]))
R=pd.DataFrame(rows); R.to_pickle('grid.pkl')
print('variants total',len(R),'natural',R.nat.sum())
pd.set_option('display.width',200); pd.set_option('display.max_rows',200)
Rv=R[R.t.isin(['SPY','XLP'])==False]
print('\nTOP 25 natural-pair by dev t'); print(Rv[Rv.nat].sort_values('dt',ascending=False).head(25).round(2).to_string())
print('\nTOP 25 any by dev t'); print(Rv.sort_values('dt',ascending=False).head(25).round(2).to_string())
print('\nDistribution dev t (non-control): mean',Rv.dt.mean().round(2),'frac>2',(Rv.dt>2).mean().round(3),'frac<-2',(Rv.dt<-2).mean().round(3))
