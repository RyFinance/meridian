from core import *
import warnings; warnings.filterwarnings('ignore')
import statsmodels.api as sm
U=pd.read_pickle('universe.pkl'); U['terc']=pd.qcut(U.adv,3,labels=['L','M','H'])
D=pd.concat([build_name(t) for t in list(U.index)+['SPY','IWM']])
D['terc']=D.t.map(U.terc)
def slope(y,x):
    d=pd.concat([y,x],axis=1).dropna(); d.columns=['y','x']
    r=sm.OLS(d.y,sm.add_constant(d.x)).fit(cov_type='HAC',cov_kwds={'maxlags':2})
    return r.params['x'],r.tvalues['x'],len(d)
print('Daily basket slopes on m (ES overnight). gap slope = fraction priced at open; r_a slope = 9:30-10:30 catch-up; r_b = 10:30-close')
for g in ['L','M','H']:
    x=D[D.terc==g].groupby(level=0)[['m','gap','r_a','r_b']].mean()
    for per,msk in [('dev',x.index<CUT),('chk',x.index>=CUT)]:
        xx=x[msk]; out=[]
        for c in ['gap','r_a','r_b']:
            b,t,n=slope(xx[c],xx.m); out.append(f'{c}: {b:.3f} (t {t:.1f})')
        print(g,per,len(xx),' | '.join(out))
for t in ['SPY','IWM']:
    x=D[D.t==t].set_index(D[D.t==t].index)[['m','gap','r_a','r_b']]
    for per,msk in [('dev',x.index<CUT),('chk',x.index>=CUT)]:
        xx=x[msk]; print(t,per,' | '.join(f'{c}: {slope(xx[c],xx.m)[0]:.3f} (t {slope(xx[c],xx.m)[1]:.1f})' for c in ['gap','r_a','r_b']))
# |m| conditioning for A, small ALL & L, gross
cost=lambda t: 2*(0.0010 if U.terc.get(t)=='L' else 0.0005)
S_=D[D.terc.notna()].dropna(subset=['gA']).copy()
S_['net']=S_.gA-S_.t.map(cost)
q=S_.m.abs().groupby(level=0).first()
S_['big']=S_.index.map(q>q[q.index<CUT].quantile(2/3))   # top-third |m| (threshold set on dev only)
for lab,msk in [('top-third |m|',S_.big),('bottom two-thirds',~S_.big)]:
    for g in ['ALL','L']:
        z=S_[msk] if g=='ALL' else S_[msk&(S_.terc=='L')]
        net=z.groupby(level=0).net.mean(); gr=z.groupby(level=0).gA.mean()
        a,b=split(net); ga,gb=split(gr)
        print(f'A {lab} {g}: dev n {len(a)} net {a.mean()*1e4:.1f} gross {ga.mean()*1e4:.1f} t(gross) {stats(ga)["t"]:.2f} | chk n {len(b)} net {b.mean()*1e4:.1f} gross {gb.mean()*1e4:.1f} t(gross) {stats(gb)["t"]:.2f}')
# per-name: gross mean A, check
nm=S_.groupby('t').apply(lambda z: pd.Series({'dev':z[z.index<CUT].gA.mean()*1e4,'chk':z[z.index>=CUT].gA.mean()*1e4,'chk_t':stats(z[z.index>=CUT].gA)['t']}))
print('names gross-positive dev/chk:',(nm.dev>0).mean().round(2),(nm.chk>0).mean().round(2),'| corr(dev,chk) across names',nm.dev.corr(nm.chk).round(2),'| n names chk |t|>2:',(nm.chk_t.abs()>2).sum(),'of',len(nm))
# ITB correlation
itb=pd.read_csv('../../zb_itb/verify/f3_trades_canonical.csv',index_col=0,parse_dates=True).g_off.dropna()-0.0004
for var,col in [('A','gA'),('B','gB')]:
    z=D[D.terc.notna()].dropna(subset=[col]); z=z.assign(net=z[col]-z.t.map(cost))
    s=z.groupby(level=0).net.mean(); j=pd.concat([s,itb],axis=1,join='inner').dropna(); 
    print(var,'corr with ITB net:',round(j.corr().iloc[0,1],3),'n',len(j), '| gross-based',round(pd.concat([z.groupby(level=0)[col].mean(),itb],axis=1,join='inner').corr().iloc[0,1],3))
