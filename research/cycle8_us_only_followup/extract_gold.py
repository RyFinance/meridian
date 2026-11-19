from pathlib import Path
import sys,json,hashlib
import pandas as pd,numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'research/cycle8_us_only_followup/vendor'))
from pyxlsb import open_workbook
DATA=ROOT/'data/cycle8_us_only_followup';rows=[];metadata=[]
with open_workbook(DATA/'Market_exchange_rates.xlsb') as book:
 with book.get_sheet('Daily') as sheet:
  for i,row in enumerate(sheet.rows()):
   v=[x.v for x in row]
   if i<14:
    metadata.append({'row':i,'label':v[3] if len(v)>3 else None,'am_usd':v[28] if len(v)>28 else None,'pm_usd':v[30] if len(v)>30 else None});continue
   if len(v)>30 and isinstance(v[3],str) and (isinstance(v[28],(int,float)) or isinstance(v[30],(int,float))):
    rows.append((v[3],v[28],v[30]))
   if i%25000==0:print('scanned',i,flush=True)
g=pd.DataFrame(rows,columns=['date','gold_am_usd','gold_pm_usd']);g['date']=pd.to_datetime(g.date,format='%Y.%m.%d');g=g.set_index('date').sort_index();assert g.index.is_unique
for col in ['gold_am_usd','gold_pm_usd']:g[col]=pd.to_numeric(g[col],errors='coerce')
g.to_csv(DATA/'gold_cfs_daily.csv');(DATA/'gold_columns.json').write_text(json.dumps(metadata,indent=2))
stats={'first':str(g.index.min().date()),'last':str(g.index.max().date()),'rows':len(g),'pm_first':str(g.gold_pm_usd.dropna().index.min().date()),'pm_last':str(g.gold_pm_usd.dropna().index.max().date()),'pm_rows':int(g.gold_pm_usd.notna().sum()),'duplicate_dates':int(g.index.duplicated().sum()),'nonpositive_pm':int((g.gold_pm_usd<=0).sum()),'monthly_holes_1971_2004':int(g.gold_pm_usd.loc['1971':'2004'].resample('ME').last().isna().sum())}
(DATA/'gold_completeness.json').write_text(json.dumps(stats,indent=2));print(stats,flush=True)
