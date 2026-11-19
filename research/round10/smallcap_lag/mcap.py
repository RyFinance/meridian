import yfinance as yf, pandas as pd, os
from concurrent.futures import ThreadPoolExecutor
from univ import *
ts=sorted(t for t in set(SMALL) if os.path.exists(f'cache/{t}_60m.pkl') and os.path.exists(f'cache/{t}_1d.pkl'))
def f(t):
    try: return t,yf.Ticker(t).fast_info['marketCap']
    except Exception as e: return t,None
with ThreadPoolExecutor(8) as ex: r=dict(ex.map(f,ts))
pd.Series(r).to_pickle('mcap.pkl'); print(pd.Series(r).describe())
