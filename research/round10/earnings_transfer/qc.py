import pickle,pandas as pd
ed=pickle.load(open('earn.pkl','rb')); px=pickle.load(open('px60.pkl','rb'))
rows=[]
for t,e in ed.items():
    if e is None: print("none",t); continue
    for d in e.index.tz_convert('America/New_York'): rows.append((t,d))
df=pd.DataFrame(rows,columns=['t','d']); df['h']=df.d.dt.hour+df.d.dt.minute/60
print(df.h.value_counts().sort_index().head(30))
print(df.groupby('t').d.min().sort_values().tail(8))
d=df[(df.d>='2024-05-01')&(df.d<'2026-10-19')]; print(len(d),((d.h<9.5)&(d.h>0)).sum())
