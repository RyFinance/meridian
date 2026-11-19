import pandas as pd,glob,os,io
px=pd.read_pickle('px.pkl')
tick=[c for c in px['Close'].columns if c!='SPY']
fn={t:t.replace('-','.') for t in tick}   # FINRA uses BF.B style
if os.path.exists('svr.pkl'):
    SV,TV=pd.read_pickle('svr.pkl')
else:
    fr=[]
    for f in sorted(glob.glob('raw/2*.txt')):
        d=pd.read_csv(f,sep='|',dtype={'Symbol':str},usecols=range(6)); d=d[d['Date'].astype(str).str.fullmatch(r'\d{8}')]
        d['Date']=pd.to_datetime(d['Date'].astype(int).astype(str)); fr.append(d)
    A=pd.concat(fr)
    A=A.groupby(['Date','Symbol'])[['ShortVolume','TotalVolume']].sum().reset_index()
    SV=A.pivot(index='Date',columns='Symbol',values='ShortVolume');TV=A.pivot(index='Date',columns='Symbol',values='TotalVolume')
    pd.to_pickle((SV,TV),'svr.pkl')
inv={v:k for k,v in fn.items()}
cols=[c for c in SV.columns if c in inv]
SV=SV[cols].rename(columns=inv);TV=TV[cols].rename(columns=inv)
print(SV.shape,'missing universe names',len(set(tick)-set(SV.columns)))
