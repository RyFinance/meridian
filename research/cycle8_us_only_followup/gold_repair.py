from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,datetime
from research.cycle8_us_only import run,metrics as mx
from research.cycle8_us_only_followup import analyze as a
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'reports/cycle8_us_only_followup';DATA=ROOT/'data/cycle8_us_only_followup'

def main():
 receipt=json.loads((OUT/'gold_receipt.json').read_text())
 for f,h in receipt['files'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
 M,D,etfs,_,cpi=run.prepare();g=pd.read_csv(DATA/'gold_cfs_daily.csv',index_col=0,parse_dates=True).gold_pm_usd.dropna()
 gm=g.resample('ME').last().pct_change(fill_method=None)-.004/12
 actual=etfs['GLD'].adjclose.resample('ME').last().pct_change(fill_method=None)
 M['G']=actual.combine_first(gm).reindex(M.index)
 gd=g.reindex(g.index.union(D.index)).sort_index().ffill().reindex(D.index)
 early=gd.pct_change(fill_method=None)-.004/252
 D['G']=D.G.combine_first(early)
 # Source PM/ETF close timing and implementation diagnostic; no fit.
 overlap=pd.concat([g.pct_change(fill_method=None).rename('gold_pm'),etfs['GLD'].adjclose.pct_change(fill_method=None).rename('gld')],axis=1).dropna();gap=overlap.gold_pm-overlap.gld
 diagnostics={'overlap_first':str(overlap.index.min().date()),'overlap_last':str(overlap.index.max().date()),'days':len(overlap),'daily_correlation':overlap.gold_pm.corr(overlap.gld),'tracking_error_ann':gap.std()*np.sqrt(252),'note':'London 15:00 fixing vs US ETF daily adjusted close, unsynchronized intervals; not a NAV replication.'}
 (OUT/'gold_overlap.json').write_text(json.dumps(diagnostics,indent=2))
 a.M=M;a.V=M.loc['1988-01':'2026-05',['E','B','G','T','C']].var()*12
 bench=pd.read_parquet(run.O/'returns_usd.parquet')['P3@1'];hist=[];risk=[];crises=[]
 for item in ['P4','P5']:
  for L in run.LEVELS:
   key=f'{item}@{L:g}';r,info=run.hist(M,D,item,L);row={'key':key,**info}
   for curr,rr,rf,cp in [('usd',r,M.C,cpi.CPI_US),('cad',(1+r)*(1+M.FX.reindex(r.index))-1,M.RFCA,cpi.CPI_CA)]:
    row.update({curr+'_'+k:v for k,v in run.stat(rr,rf,cp).items()})
    br=bench.reindex(r.index);br=(1+br)*(1+M.FX.reindex(r.index))-1 if curr=='cad' else br
    row[curr+'_hurdle']=run.stat(br,rf,cp,False)['sharpe']
    for name,(cr,dd) in mx.crisis_table(rr).items():crises.append({'key':key,'currency':curr,'crisis':name,'return':cr,'maxdd':dd})
   row['sharpe_pass']=row['usd_sharpe']>=row['usd_hurdle']-1e-12 and row['cad_sharpe']>=row['cad_hurdle']-1e-12
   expected,var=run.forward(M,item,L,info['turnover_ann']);row.update(fwd_low=expected[0],fwd_central=expected[1],fwd_high=expected[2],fwd_variance=var)
   hist.append(row);pd.DataFrame(hist).to_csv(OUT/'gold_corrected_results.csv',index=False)
   z=a.monthly(item,L,'C2');z['mode']='C3_gold';risk.append(z);pd.DataFrame(risk).to_csv(OUT/'gold_corrected_risk.csv',index=False)
   print('gold_repair',key,'sharpe_pass',row['sharpe_pass'],'p25',z['p25_20y_either'],'p35',z['p35_20y_either'],'p50',z['p50_20y_either'],flush=True)
 pd.DataFrame(crises).to_csv(OUT/'gold_corrected_crises.csv',index=False)
 for f,h in receipt['files'].items():assert hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h
 (OUT/'gold_completed.json').write_text(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'rows':len(hist)},indent=2))
if __name__=='__main__':main()
