from core import *
U=pd.read_pickle('universe.pkl').drop(index=['ALKS'],errors='ignore')
D=pd.concat([build_name(t) for t in U.index])
D['dev']=D.index<CUT
d=D[D.dev].dropna(subset=['gB2'])
print(d.groupby('t').gB2.agg(['mean','count']).sort_values('mean').tail(8))
print(d.groupby('t').gB2.agg(['mean','count']).sort_values('mean').head(3))
print(d.gB2.describe())
x=d.sort_values('gB2').tail(5)[['t','O','o0h','c1030','o1030','Cl','gap','mv1030','beta','m','r_b']]; print(x)
