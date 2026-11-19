import yfinance as yf,pandas as pd
t=[x for x in open('/Users/rytty/CCP/quant_v7/data/expanded_universe_all_tickers.txt').read().replace('\n',',').split(',') if x.strip()]
t=sorted(set(t+['SPY']))
df=yf.download(t,start='2021-11-01',end='2026-10-20',auto_adjust=True,progress=False,threads=True)
df.to_pickle('px.pkl');print(df.shape,df.index[-1])
