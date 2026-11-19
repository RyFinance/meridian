from core import *
U=pd.read_pickle('universe.pkl').drop(index=['ALKS'],errors='ignore')
U['terc']=pd.qcut(U.adv,3,labels=['L','M','H'])   # L = least liquid
print(U.groupby('terc').adv.agg(['count','min','median','max']))
def longdf(names,sig='ES'):
    return pd.concat([build_name(t,sig) for t in names])
def basket(df,col,costfn,ntrade_filter=None):
    d=df.dropna(subset=[col]).copy()
    if ntrade_filter is not None: d=d[ntrade_filter(d)]
    d['net']=d[col]-d.t.map(costfn)
    return d.groupby(level=0).net.mean(), d.groupby(level=0)[col].mean()
cost_map={}
def mk_cost(names,L_names):
    return lambda t: 2*(0.0010 if t in L_names else 0.0005)
Lnames=set(U[U.terc=='L'].index)
cf=lambda t: 2*(0.0010 if t in Lnames else 0.0005)
cf5=lambda t: 2*0.0005
D=longdf(U.index)
D['lo']=D.index>=CUT
print('name-days',len(D))
res=[]
for sig in ['ES','NQ','RTY']:
    DD=longdf(U.index,sig)
    for g,names in [('ALL',list(U.index)),('L',U[U.terc=='L'].index),('M',U[U.terc=='M'].index),('H',U[U.terc=='H'].index)]:
        x=DD[DD.t.isin(names)]
        for var,col in [('A','gA'),('B','gB'),('B2','gB2')]:
            net,gross=basket(x,col,cf)
            for nm,ser in [('net',net),('gross',gross)]:
                a,b=split(ser)
                s1,s2=stats(a),stats(b)
                res.append(dict(sig=sig,grp=g,var=var,kind=nm,devn=s1['n'],dev_bp=s1['mean_bp'],dev_t=s1['t'],chn=s2['n'],chk_bp=s2['mean_bp'],chk_t=s2['t'],chk_win=s2['win']))
R=pd.DataFrame(res)
R.to_pickle('res_main.pkl')
pd.set_option('display.width',200)
print(R.round(2).to_string())
