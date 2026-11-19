import yfinance as yf, pandas as pd, os, sys
from univ import *
os.makedirs('cache',exist_ok=True)
tick = sorted(set(SMALL+LARGE+ETFS))+FUT
for iv,per in [('1d','max'),('60m','730d')]:
    todo=[t for t in tick if not os.path.exists(f'cache/{t}_{iv}.pkl')]
    for i in range(0,len(todo),40):
        b=todo[i:i+40]
        d=yf.download(b,period=per,interval=iv,auto_adjust=False,group_by='ticker',threads=True,progress=False)
        for t in b:
            try:
                x=d[t].dropna(how='all')
                if len(x): x.to_pickle(f'cache/{t}_{iv}.pkl')
                else: print('empty',t,iv)
            except Exception as e: print('err',t,iv,e)
        print(iv,i,flush=True)
