import yfinance as yf, pandas as pd
e=yf.download('ES=F',period='730d',interval='60m',progress=False,auto_adjust=False)
if isinstance(e.columns,pd.MultiIndex): e.columns=e.columns.get_level_values(0)
e.index=e.index.tz_convert('UTC'); e.to_parquet('ES_F_60m.parquet'); print(e.shape,e.index[0],e.index[-1])
