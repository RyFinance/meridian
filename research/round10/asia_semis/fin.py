import pandas as pd, numpy as np, pickle
exec(open('test.py').read().split("rows=[]")[0])
pd.set_option('display.width',200)
R=pd.read_pickle('grid.pkl')
itb=pd.read_csv('/Users/rytty/CCP/quant_v7/research/zb_itb/verify/f3_trades_canonical.csv',index_col=0,parse_dates=True)
itbnet=(itb['g_off']-0.0004).dropna()*1e4
def one(a,t,sig,rule,ex,flip=False):
    x=trades(a,t,sig,rule,ex,flip); d=x[x.index<split]; c=x[x.index>=split]
    return x,stat(d),stat(c)
cands=[('8035.T','LRCX','raw','z1','1030'),('000660.KS','LRCX','res','z1','close'),('000660.KS','MU','raw','sign','1030'),('000660.KS','MU','res','z1','close'),('COMP','SMH','raw','sign','1030')]
for c in cands:
    x,d,k=one(*c); xf,df,kf=one(*c,flip=True)
    j=pd.concat([x,itbnet],axis=1,join='inner').dropna()
    print(c,'dev n%d m%.1f t%.2f w%.2f | chk n%d m%.1f t%.2f w%.2f'%(*d,*k),'| FLIP dev m%.1f t%.2f chk m%.1f t%.2f'%(df[1],df[2],kf[1],kf[2]),'| corrITB %.3f (n=%d)'%(j.iloc[:,0].corr(j.iloc[:,1]),len(j)))
    for ctl in ['SPY','XLP']:
        _,d2,k2=one(c[0],ctl,*c[2:]); print('   ctl',ctl,'dev m%.1f t%.2f chk m%.1f t%.2f'%(d2[1],d2[2],k2[1],k2[2]))
Rv=R[~R.t.isin(['SPY','XLP'])].copy()
# flip variants = recompute quickly: gross-based
print('\nvariants non-control',len(Rv),' max dev t',Rv.dt.max().round(2),' dev t>1.65:',(Rv.dt>1.65).sum(),' of which check t>0:',((Rv.dt>1.65)&(Rv.ct>0)).sum(), 'check t>1.65:',((Rv.dt>1.65)&(Rv.ct>1.65)).sum())
print('natural 168: max dev t',R[R.nat].dt.max().round(2),'; n dev t>1.65:',(R[R.nat].dt>1.65).sum())
# flip grid
fr=[]
for a in asia:
  for t in tick:
    if t in('SPY','XLP'):continue
    for sig in ['raw','res']:
      for rule in ['sign','z1']:
        for ex in ['1030','1130','close']:
          x=trades(a,t,sig,rule,ex,True); d=stat(x[x.index<split]); k=stat(x[x.index>=split])
          fr.append((a,t,sig,rule,ex,d[1],d[2],k[1],k[2]))
F=pd.DataFrame(fr,columns='a t sig rule ex dm dt cm ct'.split())
print('FLIP: max dev t',F.dt.max().round(2),' n dev t>2:',(F.dt>2).sum(),' with check t>0:',((F.dt>2)&(F.ct>0)).sum(),' check t>2:',((F.dt>2)&(F.ct>2)).sum())
print(F.sort_values('dt',ascending=False).head(8).round(2).to_string())
