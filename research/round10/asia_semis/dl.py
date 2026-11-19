import yfinance as yf, pandas as pd, os
os.makedirs('cache',exist_ok=True)
asia=['000660.KS','005930.KS','2330.TW','8035.T','6857.T','6920.T']
us=['MU','NVDA','AMD','AVGO','AMAT','LRCX','KLAC','MRVL','SMH','SOXX','SPY','XLP','TER','^SOX','TSM']
for t in asia+us:
    for iv,per in [('1d','max'),('60m','730d')]:
        if iv=='60m' and t=='^SOX': continue
        f=f'cache/{t}_{iv}.pkl'
        if os.path.exists(f): continue
        try:
            d=yf.Ticker(t).history(period=per,interval=iv,auto_adjust=False)
            d.to_pickle(f); print(t,iv,len(d),d.index[0],d.index[-1])
        except Exception as e: print(t,iv,'ERR',e)
