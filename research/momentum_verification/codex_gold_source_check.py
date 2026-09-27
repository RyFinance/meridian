import json
import pandas as pd
from research.momentum_verification.codex_gold_recency_audit import ROOT,OUT
x=pd.read_excel(OUT/'official_gld_history.xlsx',sheet_name=1)
x['date']=pd.to_datetime(x.Date,format='%d-%b-%Y',errors='coerce');x['official']=pd.to_numeric(x['Closing Price'],errors='coerce');x=x.dropna(subset=['date','official']).set_index('date')
y=pd.read_parquet(ROOT/'data/multiasset/etf/GLD.parquet').set_index('date');y.index=pd.to_datetime(y.index).tz_localize(None).normalize()
a=x[['official']].join(y[['close']],how='inner').loc['2017-01-01':'2026-09-17'];a['difference_bps']=(a.close/a.official-1)*10000
r={'source':'https://api.spdrgoldshares.com/api/v1/historical-archive?exchange=NYSE&lang=en&product=gld','count':len(a),'start':str(a.index.min().date()),'end':str(a.index.max().date()),'median_abs_price_difference_bps':float(a.difference_bps.abs().median()),'max_abs_price_difference_bps':float(a.difference_bps.abs().max()),'annual_returns':{}}
for year in [2024,2025,2026]:
    z=x.official.loc[f'{year-1}-12-01':min(f'{year}-12-31','2026-09-17')];base=z.loc[:f'{year-1}-12-31'].iloc[-1];r['annual_returns'][str(year)]=float(z.iloc[-1]/base-1)
(OUT/'official_source_check.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
