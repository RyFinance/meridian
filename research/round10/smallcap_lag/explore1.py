from core import *
print('sig days',len(SIGDAYS),SIGDAYS[0],SIGDAYS[-1],'CUT',CUT)
rows=[]
for t in SMALL:
    if t not in P or t not in MC.index: continue
    p=P[t]; pd_=p[(p.index<CUT)]
    rows.append(dict(t=t,mc=MC[t],adv=pd_.dv.median(),n=len(p),start=p.index[0]))
U=pd.DataFrame(rows).set_index('t')
print(len(U))
sel=U[(U.mc>=3e8)&(U.mc<=3e9)&(U.adv>5e6)]
print('mcap&adv pass',len(sel)); print(sel.adv.describe()); 
print(U[(U.mc>=3e8)&(U.mc<=3e9)&(U.adv<=5e6)].index.tolist())
print('out of mcap range', U[(U.mc<3e8)|(U.mc>3e9)].shape)
sel=sel.drop(index=['ALKS','RGR'],errors='ignore')  # ALKS = pharma; RGR = bad 60m prices (2.67x daily)
print('final universe',len(sel))
sel.to_pickle('universe.pkl')
