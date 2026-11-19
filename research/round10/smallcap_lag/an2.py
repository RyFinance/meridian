from core import *
import warnings; warnings.filterwarnings('ignore')
U=pd.read_pickle('universe.pkl'); U['terc']=pd.qcut(U.adv,3,labels=['L','M','H'])
Ln=set(U[U.terc=='L'].index)
def cost(t):
    if t in U.index: return 2*(0.0010 if t in Ln else 0.0005)
    if t=='IWC': return 2*0.0005
    return 2*0.0002
def bsk(names,col,sig='ES',cf=cost):
    D=pd.concat([build_name(t,sig) for t in names if t in P])
    D=D.dropna(subset=[col]); D['net']=D[col]-D.t.map(cf)
    return D.groupby(level=0).net.mean(), D.groupby(level=0)[col].mean(), D
def row(lab,net,gross):
    a,b=split(net); ga,gb=split(gross); s1,s2=stats(a),stats(b)
    return dict(lab=lab,devn=s1['n'],dev_net=s1['mean_bp'],dev_t=s1['t'],dev_gross=ga.mean()*1e4,chn=s2['n'],chk_net=s2['mean_bp'],chk_t=s2['t'],chk_win=s2['win'],chk_gross=gb.mean()*1e4,chk_gt=stats(gb)['t'])
rows=[]
LARGEc=[t for t in LARGE if t in P]
ETF=['SPY','IWM','IJR','IWC','QQQ']
for var,col in [('A','gA'),('B','gB')]:
    for lab,names in [('small ALL',list(U.index)),('small L',list(U[U.terc=='L'].index)),('small M',list(U[U.terc=='M'].index)),('small H',list(U[U.terc=='H'].index)),('LARGE caps',LARGEc),('SPY',['SPY']),('IWM',['IWM']),('IJR',['IJR']),('IWC',['IWC']),('QQQ',['QQQ'])]:
        net,gr,_=bsk(names,col)
        rows.append(dict(var=var,**row(lab,net,gr)))
        if lab in('small ALL','small L'):
            rows.append(dict(var=var,**row(lab+' FLIP',-gr-(gr-net),-gr)))   # flip: opposite sign, same cost
R=pd.DataFrame(rows); pd.set_option('display.width',250); print(R.round(2).to_string(index=False)); R.to_pickle('res_ctrl.pkl')
