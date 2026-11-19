import yfinance as yf, pandas as pd, pickle, time, os
from universe import ALL
os.chdir(os.path.dirname(os.path.abspath(__file__)))
tick = ALL + ['SPY']
if not os.path.exists('px60.pkl'):
    out = {}
    for i in range(0, len(tick), 30):
        b = tick[i:i+30]
        d = yf.download(b, period='730d', interval='60m', prepost=True, progress=False, auto_adjust=False, group_by='ticker', threads=True)
        for t in b:
            try:
                x = d[t].dropna(how='all')
                if len(x): out[t] = x
            except Exception as e: print('miss', t, e)
        print(i, len(out), flush=True)
    pickle.dump(out, open('px60.pkl', 'wb'))
if not os.path.exists('earn.pkl'):
    ed = {}
    for t in ALL:
        for k in range(3):
            try:
                e = yf.Ticker(t).get_earnings_dates(limit=24)
                ed[t] = e; break
            except Exception as ex:
                print('retry', t, ex); time.sleep(2)
    pickle.dump(ed, open('earn.pkl', 'wb'))
print('done')
