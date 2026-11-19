import yfinance as yf, pandas as pd, os
here = os.path.dirname(os.path.abspath(__file__))
d = yf.download('ZN=F', period='max', interval='1d', auto_adjust=False, progress=False)
if isinstance(d.columns, pd.MultiIndex):
    d.columns = d.columns.get_level_values(0)
d = d[d.index <= '2026-10-16']
d.to_parquet(os.path.join(here, 'ZN_F_1d.parquet'))
print(d.shape, d.index.min(), d.index.max())
