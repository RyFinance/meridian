"""Post-result consistency corrections and daily-tail supplement; US1 stays immutable."""
from pathlib import Path
import json, hashlib, datetime, time
import numpy as np
import pandas as pd
from research.cycle8_us_only import run, core, metrics as mx
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'reports/cycle8_us_only_followup'; OUT.mkdir(parents=True,exist_ok=True)
SEED=20260928; P=10000; BATCH=500
M=pd.read_parquet(run.O/'sleeves.parquet')
ORIG=pd.read_csv(run.O/'results.csv').set_index('key')
V=M.loc['1988-01':'2026-05',['E','B','G','T','C']].var()*12

def ar(c):
 if c in run.GEO:return run.GEO[c][1]+.5*V[c]-run.FEE.get(c,0)
 # Recover original forecast arithmetic sleeve mean; turnover/conversion are separate.
 values,var=run.forward(M,c,1.,0)
 return values[1]+.5*var+.002/20

def shifted(W,c,target):
 # Gross scale retains positivity and fits the declared simple arithmetic target exactly.
 g=1+W[c].to_numpy()
 return g*(1+target/12)/g.mean()-1

def forward_panel(item,mode='C2'):
 a,b=run.window(M,item);f,o=run.names(item)
 start=M.index[M.index.get_loc(a)-36] if item=='P5' else a
 cols=list(dict.fromkeys(f+o+['MR','C','FX']))
 W=M.loc[start:b,cols].copy()
 if mode=='C1':
  for c in f:
   target=run.GEO[c][1]-run.FEE.get(c,0) if c in run.GEO else run.forward(M,c,1)[0][1]
   W[c]=np.expm1(np.log1p(W[c])+np.log1p(target)/12-np.log1p(W[c]).mean())
  for c in o:
   funded='T' if c=='XT' else 'B';W[c]+= (ar(funded)-.035)/12-W[c].mean()
 else:
  for c in f:W[c]=shifted(W,c,ar(c))
  for c in o:
   funded='T' if c=='XT' else 'B'
   primitive=M.loc[W.index,funded]
   gross=1+primitive.to_numpy()
   W[c]=gross*(1+ar(funded)/12)/gross.mean()-1-.035/12
 W['MR']=.05/12;W['C']=.035/12
 W['FX']=np.expm1(np.log1p(W.FX)-np.log1p(W.FX).mean())
 assert W.notna().all().all()
 return W

def monthly(item,L,mode):
 f,o=run.names(item);cols=f+o+['MR','C','FX'];W=forward_panel(item,mode)
 ix=mx.stationary_indices(len(W),396,P,24,np.random.default_rng(SEED));Z=W[cols].values[ix]
 nf=len(f);no=len(o);R=Z[:,36:,:nf];X=Z[:,36:,nf:nf+no] if no else np.zeros((P,360,1));carry=Z[:,36:,nf+no:nf+no+2]
 if item=='P5':
  rr=Z[:,:,:nf];cs=np.cumsum(np.concatenate([np.zeros((P,1,nf)),rr],1),1);cs2=np.cumsum(np.concatenate([np.zeros((P,1,nf)),rr*rr],1),1);ts=np.arange(36,396)
  v=((cs2[:,ts]-cs2[:,ts-36])-(cs[:,ts]-cs[:,ts-36])**2/36)/35
  inv=1/np.sqrt(np.maximum(v,1e-12));w=inv/inv.sum(2,keepdims=True)
 else:w=run.weights(M,item)
 z=core.simulate(R,X,carry,w,np.array(list(run.MENU[item][1].values())) if no else np.zeros(1),L,np.array([run.COST[c] for c in f]),np.full(max(1,no),.0002 if no else 0),np.ones(360,bool))
 wealth=z['wealth'];cad=wealth*np.concatenate([np.ones((P,1)),np.cumprod(1+Z[:,36:,-1],axis=1)],1)
 r={'key':f'{item}@{L:g}','mode':mode,'calls_mean30':z['calls'].mean(),'ruin30':z['ruined'].mean()}
 for h in [120,240,360]:
  u=core.max_drawdown(wealth[:,:h+1]);c=core.max_drawdown(cad[:,:h+1])
  for t in [25,35,50]:
   for curr,d in [('usd',u),('cad',c),('either',np.maximum(u,c))]:r[f'p{t}_{h//12}y_{curr}']=np.mean(d>t/100)
  term=wealth[:,h];r[f'geo_median_{h//12}y']=np.median(term**(12/h)-1)
 return r

def daily_prepare(M,D,item,lens):
 a,b=run.window(M,item);f,o=run.names(item);assert not o
 W=M.loc[a:b,f+['MR','C','FX']].copy()
 if lens=='C2':W=forward_panel(item,'C2')
 days=D.loc[a.to_period('M').start_time:b].index;keys=run.mkey(days);counts=pd.Series(keys).value_counts();nmax=int(counts.max())
 R=np.zeros((len(W),nmax,len(f)));carry=np.zeros((len(W),nmax,2));FX=np.zeros((len(W),nmax));lenslog=[]
 for i,m in enumerate(W.index):
  dd=days[keys==m];n=len(dd);assert n
  for j,c in enumerate(f):
   R[i,:n,j]=run.spread(D[c].reindex(dd),W.at[m,c])
   assert np.isclose(np.prod(1+R[i,:,j])-1,W.at[m,c],rtol=1e-10,atol=1e-11)
  FX[i,:n]=run.spread(D.FX.reindex(dd),W.at[m,'FX']);assert np.isclose(np.prod(1+FX[i])-1,W.at[m,'FX'],atol=1e-10)
  carry[i,:n,0]=W.at[m,'MR']/n;carry[i,:n,1]=W.at[m,'C']/n
 return R,carry,FX,nmax,W

def wilson(k,n):
 z=1.959963984540054;v=k/n;den=1+z*z/n;c=(v+z*z/(2*n))/den;h=z*np.sqrt(v*(1-v)/n+z*z/(4*n*n))/den;return c-h,c+h

def daily(item,L,lens,D):
 source,carry,fx,nmax,W=daily_prepare(M,D,item,lens)
 # Same source row count, draw length and discarded 36-month burn-in as original.
 ix=mx.stationary_indices(len(W),396,P,24,np.random.default_rng(SEED))[:,36:276]
 totals={(freq,cur,t):0 for freq in ['daily','monthly'] for cur in ['usd','cad','either'] for t in [25,35,50]};calls=ruins=0;endgrowth=[]
 step=nmax*240;rebal=np.zeros(step,bool);rebal[::nmax]=True;monthends=np.arange(nmax,step+1,nmax)
 for lo in range(0,P,BATCH):
  sample=ix[lo:lo+BATCH];nb=len(sample)
  rr=source[sample].reshape(nb,step,len(run.names(item)[0]));cc=carry[sample].reshape(nb,step,2);ff=fx[sample].reshape(nb,step)
  z=core.simulate(rr,np.zeros((nb,step,1)),cc,run.weights(M,item),np.zeros(1),L,np.array([run.COST[c] for c in run.names(item)[0]]),np.zeros(1),rebal)
  wealth=z['wealth'];cad=wealth*np.concatenate([np.ones((nb,1)),np.cumprod(1+ff,axis=1)],1)
  for freq,sel in [('daily',np.arange(step+1)),('monthly',np.r_[0,monthends])]:
   u=core.max_drawdown(wealth[:,sel]);c=core.max_drawdown(cad[:,sel]);both=np.maximum(u,c)
   for cur,d in [('usd',u),('cad',c),('either',both)]:
    for t in [25,35,50]:totals[freq,cur,t]+=int(np.sum(d>t/100))
  calls+=int(z['calls'].sum());ruins+=int(z['ruined'].sum());endgrowth.extend((wealth[:,-1]**(1/20)-1).tolist())
 row={'key':f'{item}@{L:g}','lens':lens,'paths':P,'months':240,'max_days_in_month':nmax,'calls_mean20':calls/P,'ruin20':ruins/P,'median_terminal_cagr':np.median(endgrowth)}
 for (freq,cur,t),k in totals.items():
  field=f'{freq}_p{t}_20y_{cur}';row[field]=k/P;row[field+'_mc_lo'],row[field+'_mc_hi']=wilson(k,P)
  assert totals['daily',cur,t]>=totals['monthly',cur,t]
 return row

def deterministic():
 checks=[]
 for item in run.MENU:
  W=forward_panel(item,'C2');f,o=run.names(item)
  for c in f:
   target=.035 if c=='C' else ar(c)
   assert np.isclose(W[c].mean()*12,target,atol=1e-12),(item,c)
   checks.append({'item':item,'sleeve':c,'annual_arithmetic_target':target,'annual_arithmetic_observed':W[c].mean()*12,'implied_annual_geometric':np.expm1(12*np.log1p(W[c]).mean())})
  for c in o:
   funded='T' if c=='XT' else 'B';gross=1+M.loc[W.index,funded]
   expected=gross*(1+ar(funded)/12)/gross.mean()-1-.035/12
   assert np.allclose(W[c],expected,atol=1e-12)
   checks.append({'item':item,'sleeve':c,'annual_arithmetic_target':ar(funded)-.035,'annual_arithmetic_observed':W[c].mean()*12,'implied_annual_geometric':np.nan})
 pd.DataFrame(checks).to_csv(OUT/'moment_checks.csv',index=False)
 # Original crisis implementation accepts a partial ending; flag with a synthetic unit case.
 dates=pd.date_range('2022-01-31','2022-03-31',freq='ME');s=pd.Series([-.1,-.1,-.1],index=dates)
 old=mx.crisis_table(s)['2022 stocks+bonds'];assert np.isfinite(old[0])
 return {'all_arithmetic_targets_exact':True,'overlay_identity_exact':True,'original_crisis_end_coverage_bug_demonstrated':True}

def verify():
 receipt=json.loads((OUT/'receipt.json').read_text())
 for file,sha in receipt['files'].items():assert hashlib.sha256((ROOT/file).read_bytes()).hexdigest()==sha,file
 run.verify()

def main():
 verify();started=time.time();check=deterministic();(OUT/'checks.json').write_text(json.dumps(check,indent=2))
 rows=[]
 for mode,menu in [('C1',['P6a','P6b']),('C2',list(run.MENU))]:
  for item in menu:
   for L in run.LEVELS:
    r=monthly(item,L,mode);rows.append(r);pd.DataFrame(rows).to_csv(OUT/'correction_risk.csv',index=False);print('correction',mode,r['key'],r['p50_20y_either'],flush=True)
 _,D,_,_,_=run.prepare();ds=[]
 for lens in ['historical','C2']:
  for item in ['P1','P2','P3']:
   for L in run.LEVELS:
    r=daily(item,L,lens,D);ds.append(r);pd.DataFrame(ds).to_csv(OUT/'daily_risk.csv',index=False);print('daily',lens,r['key'],r['daily_p50_20y_either'],flush=True)
 verify();(OUT/'completed.json').write_text(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'elapsed_seconds':time.time()-started,'correction_rows':len(rows),'daily_rows':len(ds)},indent=2))
if __name__=='__main__':main()
