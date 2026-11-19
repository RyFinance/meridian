from pathlib import Path
import json,hashlib,datetime,shutil
import pandas as pd,numpy as np
ROOT=Path(__file__).resolve().parents[2];S=ROOT/'data/cycle8_us_only/snapshot';O=ROOT/'reports/cycle8_us_only'
rows=[]
for p in sorted((S/'etf').glob('*.parquet')):
 d=pd.read_parquet(p).loc[:'2026-08-31'];a=d.adjclose.dropna();c=d.close.dropna();r=a.pct_change(fill_method=None)
 own=d.tr_own.dropna();idx=a.index.intersection(own.index);ratio=(a.loc[idx]/a.loc[idx[0]])/(own.loc[idx]/own.loc[idx[0]])
 yrs=(idx[-1]-idx[0]).days/365.25
 rows.append({'ticker':p.stem,'first':str(a.index.min().date()),'last':str(a.index.max().date()),'rows':len(d),'missing_adj':int(d.adjclose.isna().sum()),'duplicates':int(d.index.duplicated().sum()),'split_events':int((d.splits!=1).sum()),'dividend_events':int((d.dividends!=0).sum()),'abs_daily_over25pct':int((r.abs()>.25).sum()),'max_calendar_gap_days':int(a.index.to_series().diff().dt.days.max()),'adjusted_vs_own_tr_ann':float(ratio.iloc[-1]**(1/yrs)-1),'min_close':float(c.min())})
pd.DataFrame(rows).to_csv(O/'ETF_COMPLETENESS.csv',index=False)
# Preserve source documentation and raw source bytes separately, without modifying frozen numerical snapshot.
raw=ROOT/'data/cycle8_us_only/source_archive';raw.mkdir(exist_ok=True)
paths=[]
for pat in ['data/cycle8/raw/eq/F-F_Research_Data_Factors*zip','data/cycle8/raw/eq/frb_H10.zip','data/cycle8/raw/eq/bls_*.json','data/cycle8/raw/eq/statcan_18100004-eng.zip','data/cycle8/raw/trend/tsmom*.xlsx','data/cycle8/raw/rates/fred_DGS*.csv','data/cycle8/raw/rates/fred_GS10.csv','data/cycle8/raw/rates/ie_data.xls','data/cycle8/raw/rates/gold_prices*','data/cycle8/cma/raw/aqr_cma_2026*','data/cycle8/cma/raw/jpm_ltcma_2026_matrix_usd*','data/cycle8/cma/raw/blackrock_cma*']:
 paths.extend(ROOT.glob(pat))
for ticker in [r['ticker'] for r in rows]:paths.append(ROOT/'data/cycle8/raw/etf'/f'{ticker}.json')
paths.extend((ROOT/'data/cycle8/notes').glob('*.md'));paths.extend([ROOT/'data/cycle8/cma/cma_raw.csv',ROOT/'data/cycle8/cma/retrieval_log.csv'])
rec=[]
for p in paths:
 if not p.exists():continue
 q=raw/p.relative_to(ROOT/'data/cycle8');q.parent.mkdir(parents=True,exist_ok=True)
 if not q.exists():shutil.copy2(p,q)
 rec.append({'source':str(p.relative_to(ROOT)),'copy':str(q.relative_to(ROOT)),'sha256':hashlib.sha256(q.read_bytes()).hexdigest()})
(raw/'manifest.json').write_text(json.dumps({'archived_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'note':'Support archive captured after run start; numeric dataset snapshot predated run; no new numerical inputs.','files':rec},indent=2))
print(pd.DataFrame(rows).to_string(index=False))
