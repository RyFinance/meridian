"""Declared descriptive supplements. No new weights or selection trials."""
from pathlib import Path
import pandas as pd,numpy as np,json
from research.cycle8_us_only import run,metrics as mx
O=run.O;M=pd.read_parquet(O/'sleeves.parquet');R=pd.read_parquet(O/'returns_usd.parquet');cpi=run.load('cpi_ca_monthly')
rows=[];tax=[];feas=[]
for key in R:
 item,lev=key.split('@');L=float(lev);r=R[key].dropna();rc=(1+r)*(1+M.FX.reindex(r.index))-1
 for c,rr,rf,cp in [('USD',r,M.C,cpi.CPI_US),('CAD',rc,M.RFCA,cpi.CPI_CA)]:
  s=rr.loc['1988-01':'2026-05']
  if len(s)==461:rows.append({'key':key,'currency':c,**run.stat(s,rf,cp,False)})
 if L==1 and item in ['P1','P2','P3','P5']:
  w=run.weights(M,item)
  e=w['E'].reindex(r.index) if item=='P5' else w[0]
  tr=r-e*M.WHT.reindex(r.index)
  tax.append({'key':key,'scope':'equity_dividend_withholding_only','rrsp_usd_cagr':run.stat(r,M.C,cpi.CPI_US,False)['cagr'],'tfsa_usd_cagr':run.stat(tr,M.C,cpi.CPI_US,False)['cagr'],'mean_withholding_ann':float((e*M.WHT.reindex(r.index)).mean()*12)})
 base=run.weights(M,item);gross=1 if item=='P5' else base.sum()
 # Treat fund leverage rules as constraints, not estimated historical house requirements.
 if item in ['P7a','P7b']:requirement=.72 if item=='P7a' else .90
 elif item in ['NTSX','RSSB','RSST','GDE']:requirement={'NTSX':.45,'RSSB':.60,'RSST':.60,'GDE':.54}[item]
 else:requirement=.3*gross+.1*sum(run.MENU[item][1].values())
 feasible=L*requirement<=1+1e-12
 feas.append({'key':key,'assumed_rule_maintenance_per_base':requirement,'rule_initially_feasible':feasible,'house_requirement_verified':False,'note':'Derived leverage-factor rule; real current/historical house requirements unverified. Generic30% paths in primary table are counterfactual for built-in-leverage funds.' if item in ['P7a','P7b','NTSX','RSSB','RSST','GDE'] else '30% funded /10%overlay assumption; house margins unverified.'})
pd.DataFrame(rows).to_csv(O/'common_window.csv',index=False);pd.DataFrame(tax).to_csv(O/'tfsa_equity_tax.csv',index=False);pd.DataFrame(feas).to_csv(O/'account_feasibility.csv',index=False)
# Data alignment and arithmetic invariants on final products.
x=pd.read_csv(O/'results.csv');assert len(x)==56 and x.key.is_unique
assert x.usd_cagr.notna().all() and x.cad_cagr.notna().all();assert x.fwd_central.notna().all()
for pre in ['hist_','forward_','block12_']:
 assert ((x[pre+'p25_20y_either']>=x[pre+'p35_20y_either'])&(x[pre+'p35_20y_either']>=x[pre+'p50_20y_either'])).all()
for c in ['usd','cad']:
 for pre in ['hist_','forward_','block12_']:
  assert (x[pre+'p35_30y_'+c]>=x[pre+'p35_20y_'+c]).all()
assert all(abs(x.loc[x.key=='P3@1','usd_sharpe'].values-x.loc[x.key=='P3@1','usd_hurdle'].values)<1e-12)
# Common-window counts require 1988-Jan through2026-May =461.
assert len(pd.period_range('1988-01','2026-05',freq='M'))==461
out={'rows':len(x),'all_finite_cagr_forward':True,'probability_monotonicity':True,'baseline_hurdle_identity':True,'full_crisis_rows':int(x.full_crisis_coverage.sum()),'no_new_menu_rows':True}
(O/'verification.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
