"""Fixed US1 evaluation. All inputs copied and hashed before execution."""
from pathlib import Path
import json, hashlib, datetime
import numpy as np
import pandas as pd
from research.cycle8_us_only import core, metrics as mx
ROOT=Path(__file__).resolve().parents[2]
S=ROOT/'data/cycle8_us_only/snapshot'; O=ROOT/'reports/cycle8_us_only/out'
SEED=20260928; LEVELS=[1.,1.25,1.5,2.]; END='2026-08-31'
MENU={'P1':({'E':1},{}),'P2':({'E':.8,'B':.2},{}),'P3':({'E':.6,'B':.4},{}),
 'P4':({'E':.6,'B':.4,'G':.1,'T':.1},{}),'P5':('RP',{}),
 'P6a':({'E':1},{'XT':.5}),'P6b':({'E':1},{'XB':.5})}
for name in ['NTSX','RSSB','RSST','GDE','P7a','P7b']:MENU[name]=({name:1},{})
MENU['P8']=({'C':1},{})
FEE={'E':.000945,'B':.0015,'G':.004,'T':0,'C':0}
COST={k:(.001 if k in ['G','T'] else .0005) for k in ['E','B','G','T','C','NTSX','RSSB','RSST','GDE','P7a','P7b']};COST['C']=0
# Net trend CMA already includes implementation; other asset CMAs are gross.
GEO={'E':(.042,.055,.067),'B':(.037,.0425,.048),'G':(.02,.03,.055),'T':(.03,.045,.06),'C':(.03,.035,.04)}
REAL_FEE={'NTSX':.002,'RSSB':.0039,'RSST':.0099,'GDE':.002}

def load(n):return pd.read_parquet(S/(n+'.parquet'))
def monthly(d):return (1+d).groupby(d.index.to_period('M')).prod(min_count=1).sub(1).to_timestamp('M')
def mkey(idx):return idx.to_period('M').to_timestamp('M')
def verify():
 for x in json.loads((S/'manifest.json').read_text()):
  p=ROOT/x['copy'];assert hashlib.sha256(p.read_bytes()).hexdigest()==x['sha256'],p
 receipt=json.loads((ROOT/'research/cycle8_us_only/prereg_receipt.json').read_text())
 assert hashlib.sha256((ROOT/receipt['path']).read_bytes()).hexdigest()==receipt['sha256']

def prepare():
 eq=load('eq_monthly');rt=load('rates_monthly');bm=load('bond_monthly');tr=load('trend_monthly')
 M=pd.DataFrame(index=eq.index);M['E']=eq.US_usd-FEE['E']/12;M['B']=bm.US10_ret-FEE['B']/12;M['C']=rt.rf_usd_ret
 M['T']=tr.tsmom_excess+M.C-.02/12;M['XT']=tr.tsmom_excess-.02/12;M['XB']=M.B-M.C
 gl=load('gold_monthly').gold_usd_wb_avg.pct_change(fill_method=None)-.004/12
 etfs={t:load('etf/'+t).loc[:END] for t in ['SPY','VTI','IEF','GLD','DBMF','KMLM','NTSX','RSSB','RSST','GDE','SSO','UPRO','TMF','TLT']}
 gm=etfs['GLD'].adjclose.resample('ME').last().pct_change(fill_method=None)
 M['G']=gm.combine_first(gl)
 fx=load('fx_monthly').USDCAD;M['FX']=fx.pct_change(fill_method=None);M['RFCA']=rt.tbill_cad.shift(1)/12
 fed=pd.read_csv(S/'FEDFUNDS.csv',index_col=0,parse_dates=True).iloc[:,0]/100;fed.index=fed.index+pd.offsets.MonthEnd(0)
 M['MR']=fed.shift(1).reindex(M.index)/12+.015/12
 M.loc[M.index<'1954-09-01','MR']=M.C+.015/12
 M['MRCA']=rt.policy_cad.shift(1)/12+.015/12
 M['WHT']=eq.US_dp.ffill().shift(1)*.15/12
 ed=load('eq_daily').US_usd.loc[:END].dropna();days=ed.index;bd=load('bond_daily').reindex(days)
 D=pd.DataFrame(index=days);D['E']=ed-.000945/252;D['B']=bd.US10_ret.fillna(0)-.0015/252
 D['G']=etfs['GLD'].adjclose.pct_change(fill_method=None).reindex(days);D['T']=np.nan;D['C']=np.nan;D['XT']=np.nan;D['XB']=D.B
 fxd=load('fx_daily').USDCAD;fxd=fxd.reindex(fxd.index.union(days)).sort_index().ffill().reindex(days)
 D['FX']=fxd.pct_change(fill_method=None)
 for t in ['NTSX','RSSB','RSST','GDE']:
  D[t]=etfs[t].adjclose.pct_change(fill_method=None).reindex(days);M[t]=etfs[t].adjclose.resample('ME').last().pct_change(fill_method=None)
 rf=load('rf_usd_daily').rf_usd.reindex(days).ffill();under={'SSO':ed,'UPRO':ed,'TMF':bd.US20_ret.fillna(0)};sim={}
 for t,k,sp,fee in [('SSO',2,.005,.0089),('UPRO',3,.005,.0089),('TMF',3,.0025,.0101)]:
  sim[t]=(k*under[t]-(k-1)*(rf+sp/252)-fee/252).clip(lower=-1)
 for name,t in [('P7a','SSO'),('P7b','UPRO')]:
  panel=pd.concat([sim[t],sim['TMF']],axis=1).loc['1971-02':].dropna();mk=mkey(panel.index)
  z=core.simulate(panel.values[None],np.zeros((1,len(panel),1)),np.zeros((1,len(panel),2)),np.array([.6,.4]),np.zeros(1),1.,np.array([.0005,.0005]),np.zeros(1),np.r_[True,mk[1:]!=mk[:-1]])
  w=z['wealth'][0];r=pd.Series(np.divide(w[1:],w[:-1],out=np.ones(len(panel)),where=w[:-1]>0)-1,index=panel.index)
  D[name]=r;M[name]=monthly(r)
 return M,D,etfs,pd.DataFrame(sim),load('cpi_ca_monthly')

def names(item):
 f,o=MENU[item];return (['E','B','G','T'] if f=='RP' else list(f)),list(o)
def weights(M,item):
 f,_=MENU[item]
 if f!='RP':return np.array(list(f.values()))
 inv=1/M[['E','B','G','T']].rolling(36,min_periods=36).std().shift(1)
 return inv.div(inv.sum(axis=1),axis=0)
def window(M,item,start='1971-02'):
 f,o=names(item);valid=M[f+o+['MR','C','FX','RFCA']].notna().all(axis=1)
 if item=='P5':valid &= weights(M,item).notna().all(axis=1)
 ix=valid.loc[start:];ix=ix.index[ix]
 assert len(ix)>0,item
 assert valid.loc[ix[0]:ix[-1]].all(),f'internal holes {item}'
 return ix[0],ix[-1]
def spread(proxy,total,add=False):
 n=len(proxy);p=proxy.to_numpy();
 if not np.isfinite(total):raise ValueError('missing month')
 if add:return p+(total-p.sum())/n if np.isfinite(p).all() else np.full(n,total/n)
 if not np.isfinite(p).all() or np.any(p<=-1):return np.full(n,np.expm1(np.log1p(total)/n))
 lp=np.log1p(p);return np.expm1(lp+(np.log1p(total)-lp.sum())/n)
def hist(M,D,item,L,maint=.3,spread_extra=0.,cad_finance=False):
 a,b=window(M,item);f,o=names(item);Mw=M.loc[a:b];days=D.loc[a.to_period('M').start_time:b].index;mk=mkey(days)
 vals={};cols=f+o
 for c in cols:
  v=np.empty(len(days));p=D[c]
  for m in mk.unique():
   sel=mk==m;v[sel]=spread(p.reindex(days[sel]),Mw.at[m,c],c.startswith('X'))
  vals[c]=v
 nd=pd.Series(mk).map(pd.Series(mk).value_counts()).to_numpy();carry=np.column_stack([(Mw.MR.reindex(mk).values+spread_extra/12)/nd,Mw.C.reindex(mk).values/nd])
 R=np.column_stack([vals[c] for c in f]);X=np.column_stack([vals[c] for c in o]) if o else np.zeros((len(days),1))
 if cad_finance:
  fx=np.empty(len(days))
  for m in mk.unique():
   sel=mk==m;fx[sel]=spread(D.FX.reindex(days[sel]),Mw.at[m,'FX'])
  R=(1+R)*(1+fx[:,None])-1
  # Monthly anchored USD overlay P&L translated at each day's rate; approximation explicit.
  X=X*(1+fx[:,None]);carry=np.column_stack([Mw.MRCA.reindex(mk).values/nd,Mw.RFCA.reindex(mk).values/nd])
 ww=weights(M,item);w=ww.loc[a:b].reindex(mk).values[None] if item=='P5' else ww
 core.MAINT_FUNDED=maint;core.RESTORE=(maint+.05)/maint
 z=core.simulate(R[None],X[None],carry[None],w,np.array(list(MENU[item][1].values())) if o else np.zeros(1),L,np.array([COST[c] for c in f]),np.full(max(1,len(o)),.0002 if o else 0),np.r_[True,mk[1:]!=mk[:-1]])
 wd=pd.Series(z['wealth'][0,1:],index=days);wm=wd.groupby(mk).last();w0=np.r_[1.,wm.values];r=pd.Series(np.divide(w0[1:],w0[:-1],out=np.ones(len(wm)),where=w0[:-1]>0)-1,index=wm.index)
 r.iloc[0]=(1+r.iloc[0])*.999-1;r.iloc[-1]=(1+r.iloc[-1])*.999-1
 fxidx=(1+D.FX.reindex(days).fillna(0)).cumprod()
 # Daily FX anchored to observed monthly changes, preserving monthly match.
 fd=np.empty(len(days))
 for m in mk.unique():
  sel=mk==m;fd[sel]=spread(D.FX.reindex(days[sel]),Mw.at[m,'FX'])
 wcad=wd.values*np.cumprod(1+fd) if not cad_finance else wd.values
 info={'calls':int(z['calls'][0]),'ruined':bool(z['ruined'][0]),'dd_daily_usd':float(mx.drawdowns(np.r_[1.,wd.values]).max()),'dd_daily_cad':float(mx.drawdowns(np.r_[1.,wcad]).max()),'turnover_ann':float(z['turnover'][0]/(len(r)/12))}
 core.MAINT_FUNDED=.3;core.RESTORE=.35/.3
 return r,info

def forward(M,item,L,turnover=0):
 common=M.loc['1988-01':'2026-05'];vv=common[['E','B','G','T','C']].var()*12
 f,o=names(item);w=weights(M,item)
 if item=='P5':w=w.loc['1988-01':'2026-05'].dropna().mean().values
 w=np.asarray(w);base=dict(zip(f,w));vvpanel=M[f+o].dropna(); commonpanel=vvpanel.loc['1988-01':'2026-05']; v=(commonpanel if len(commonpanel)>=36 else vvpanel).cov()*12
 exposure=np.r_[w,list(MENU[item][1].values())];pvar=float(exposure@v.values@exposure)*L**2
 ans=[]
 for i in range(3):
  ar={c:GEO[c][i]+.5*vv[c]-FEE.get(c,0) for c in GEO}
  ar['XT']=ar['T']-GEO['C'][i];ar['XB']=ar['B']-GEO['C'][i]
  for t in REAL_FEE:
   if t=='NTSX':mu=.9*(ar['E']+FEE['E'])+.6*(ar['B']+FEE['B'])-.5*GEO['C'][i]
   elif t=='RSSB':mu=[.055,.065,.075][i]+.5*vv['E']+(ar['B']+FEE['B'])-GEO['C'][i]
   elif t=='RSST':mu=(ar['E']+FEE['E'])+ar['T']-GEO['C'][i] # trend already net2%; conservative double implementation allowance flagged
   else:mu=.9*(ar['E']+FEE['E'])+.9*(ar['G']+FEE['G'])-.8*GEO['C'][i]
   ar[t]=mu-REAL_FEE[t]
  for t,ke in [('P7a',2),('P7b',3)]:
   # use historical 20Y covariance from daily proxy for long bond; CMA long Treasury fixed Vanguard range.
   long=[.052,.057,.062][i];vb=M[t].var()*12
   ar[t]=.6*(ke*(ar['E']+FEE['E'])-(ke-1)*(GEO['C'][i]+.005)-.0089)+.4*(3*(long+.5*vv['B']*4)-2*(GEO['C'][i]+.0025)-.0101)
  debt=max(0,L*w.sum()-1)
  mu=L*sum(wi*ar[c] for c,wi in base.items())+L*sum(wi*ar[c] for c,wi in MENU[item][1].items())-debt*(GEO['C'][i]+.015)
  ans.append(mu-.5*pvar-turnover*.0005-.002/20)
 return ans,pvar

def bootstrap(M,item,L,mean_block=24,P=10000,forward_lens=False):
 a,b=window(M,item);f,o=names(item);cols=f+o+['MR','C','FX'];start=M.index[M.index.get_loc(a)-36] if item=='P5' else a
 W=M.loc[start:b,list(dict.fromkeys(cols))].copy();assert W.notna().all().all()
 if forward_lens:
  for c in f:
   if c in GEO:target=GEO[c][1]-FEE.get(c,0)
   else:target=forward(M,c,1.)[0][1]
   W[c]=np.expm1(np.log1p(W[c])+(np.log1p(target)/12-np.log1p(W[c]).mean()))
  for c in o:
   target=GEO['T' if c=='XT' else 'B'][1]-FEE.get('B' if c=='XB' else 'T',0)-.035
   W[c]+=target/12-W[c].mean()
  W['MR']=.05/12;W['C']=.035/12
  W['FX']=np.expm1(np.log1p(W.FX)-np.log1p(W.FX).mean())
 idx=mx.stationary_indices(len(W),396,P,mean_block,np.random.default_rng(SEED));Z=W[cols].values[idx];nf=len(f);no=len(o)
 R=Z[:,36:,:nf];X=Z[:,36:,nf:nf+no] if no else np.zeros((P,360,1));carry=Z[:,36:,nf+no:nf+no+2]
 if item=='P5':
  r=Z[:,:,:nf];cs=np.cumsum(np.concatenate([np.zeros((P,1,nf)),r],1),1);cs2=np.cumsum(np.concatenate([np.zeros((P,1,nf)),r*r],1),1);ts=np.arange(36,396)
  v=((cs2[:,ts]-cs2[:,ts-36])-(cs[:,ts]-cs[:,ts-36])**2/36)/35;inv=1/np.sqrt(np.maximum(v,1e-12));w=inv/inv.sum(2,keepdims=True)
 else:w=weights(M,item)
 z=core.simulate(R,X,carry,w,np.array(list(MENU[item][1].values())) if no else np.zeros(1),L,np.array([COST[c] for c in f]),np.full(max(1,no),.0002 if no else 0),np.ones(360,bool))
 wealth=z['wealth'];wc=wealth*np.concatenate([np.ones((P,1)),np.cumprod(1+Z[:,36:,-1],axis=1)],axis=1)
 out={}
 for h in [120,240,360]:
  du=core.max_drawdown(wealth[:,:h+1]);dc=core.max_drawdown(wc[:,:h+1])
  for tol in [.25,.35,.5]:
   for currency,dd in [('usd',du),('cad',dc),('either',np.maximum(du,dc))]:out[f'p{int(tol*100)}_{h//12}y_{currency}']=float(np.mean(dd>tol))
 out['calls_mean30']=float(z['calls'].mean());out['ruin30']=float(z['ruined'].mean())
 return out

def stat(r,rf,cpi,ci=True):
 # Degenerate cash excess does not have a defined Sharpe or confidence interval.
 ex=(r-rf.reindex(r.index)).to_numpy()
 z=mx.summary(r,rf,cpi,sharpe_ci=ci and len(r)>=36 and np.std(ex)>1e-10)
 if np.std(ex)<1e-10:z.update(sharpe=np.nan,sharpe_lo=np.nan,sharpe_hi=np.nan)
 return z

def main():
 verify();O.mkdir(parents=True,exist_ok=True)
 (O/'started.json').write_text(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'seed':SEED,'paths':10000},indent=2))
 M,D,etfs,sim,cpi=prepare();M.to_parquet(O/'sleeves.parquet');sim.to_parquet(O/'letf_sim.parquet')
 rows=[];crises=[];rets={};dailyinfo={}
 for item in MENU:
  for L in LEVELS:
   key=f'{item}@{L:g}';r,inf=hist(M,D,item,L);rets[key]=r;dailyinfo[key]=inf;print('hist',key,flush=True)
 pd.DataFrame(rets).to_parquet(O/'returns_usd.parquet')
 bench=rets['P3@1']
 for item in MENU:
  r1=rets[f'{item}@1'];kel=mx.kelly(r1.values,M.MR.reindex(r1.index).values,B=5000)
  for L in LEVELS:
   key=f'{item}@{L:g}';r=rets[key];rc=(1+r)*(1+M.FX.reindex(r.index))-1
   row={'key':key,'item':item,'L':L,**dailyinfo[key],**kel}
   for currency,rr,rf,cp in [('usd',r,M.C,cpi.CPI_US),('cad',rc,M.RFCA,cpi.CPI_CA)]:
    st=stat(rr,rf,cp);row.update({currency+'_'+k:v for k,v in st.items()})
    br=bench.reindex(r.index);br=(1+br)*(1+M.FX.reindex(r.index))-1 if currency=='cad' else br
    row[currency+'_hurdle']=stat(br,rf,cp,False)['sharpe']
    for name,(cum,dd) in mx.crisis_table(rr).items():crises.append({'key':key,'currency':currency,'crisis':name,'return':cum,'maxdd':dd})
   fg,var=forward(M,item,L,row['turnover_ann']);row.update(fwd_low=fg[0],fwd_central=fg[1],fwd_high=fg[2],fwd_variance=var)
   for pref,block,fl in [('hist_',24,False),('forward_',24,True),('block12_',12,False)]:
    row.update({pref+k:v for k,v in bootstrap(M,item,L,block,forward_lens=fl).items()})
   if L>1 or item in ['P4','P6a','P6b']:
    rs,ins=hist(M,D,item,L,spread_extra=.015);row['spread3_cagr']=stat(rs,M.C,cpi.CPI_US,False)['cagr'];row['spread3_calls']=ins['calls']
    rs,ins=hist(M,D,item,L,maint=.5);row['maint50_cagr']=stat(rs,M.C,cpi.CPI_US,False)['cagr'];row['maint50_calls']=ins['calls']
    rs,ins=hist(M,D,item,L,cad_finance=True);row['cad_financing_cagr']=stat(rs,M.RFCA,cpi.CPI_CA,False)['cagr'];row['cad_financing_calls']=ins['calls']
   f,o=names(item);base=weights(M,item);total=1 if item=='P5' else sum(base)
   row['base_gross']=total+sum(MENU[item][1].values());row['tfsa_exact']=L==1 and item not in ['P4','P6a','P6b']
   row['kelly_flag']=L>row['half_kelly'];row['full_crisis_coverage']=r.index[0]<=pd.Timestamp('1973-01-31')
   row['sharpe_pass']=row['usd_sharpe']>=row['usd_hurdle']-1e-12 and row['cad_sharpe']>=row['cad_hurdle']-1e-12
   for tol in [25,35,50]:row[f'model_eligible{tol}']=row['sharpe_pass'] and row[f'hist_p{tol}_20y_either']<.1 and item not in ['P7a','P7b','P8','NTSX','RSSB','RSST','GDE']
   rows.append(row);pd.DataFrame(rows).to_csv(O/'results.csv',index=False);print('evaluated',key,flush=True)
 pd.DataFrame(crises).to_csv(O/'crises.csv',index=False)
 # validation at monthly resolution, total return adjusted histories
 vr=[]
 for ticker,col,source in [('SSO','SSO',sim),('UPRO','UPRO',sim),('TMF','TMF',sim),('SPY','E',M),('IEF','B',M),('DBMF','T',M),('KMLM','T',M)]:
  actual=etfs[ticker].adjclose.resample('ME').last().pct_change(fill_method=None)
  proxy=monthly(source[col]) if source is sim else source[col]
  p=pd.concat([actual.rename('actual'),proxy.rename('proxy')],axis=1).dropna();gap=(p.proxy-p.actual)
  vr.append({'ticker':ticker,'start':str(p.index.min()),'end':str(p.index.max()),'months':len(p),'corr':p.actual.corr(p.proxy),'te_ann':gap.std()*np.sqrt(12),'arithmetic_gap_ann':gap.mean()*12,'actual_cagr':np.prod(1+p.actual)**(12/len(p))-1,'proxy_cagr':np.prod(1+p.proxy)**(12/len(p))-1})
 pd.DataFrame(vr).to_csv(O/'validation.csv',index=False)
 # Cash and direct ETF live descriptive metrics, benchmark on same span
 live=[]
 for ticker,e in etfs.items():
  r=e.adjclose.resample('ME').last().pct_change(fill_method=None).dropna()
  if len(r)<12:continue
  live.append({'ticker':ticker,**stat(r,M.C,cpi.CPI_US,False)})
 pd.DataFrame(live).to_csv(O/'live_etfs.csv',index=False)
 # US pre-1971 supplementary, directly monthly; missing yield periods declared smoothed.
 us=[]
 for item in ['P1','P2','P3']:
  f,o=names(item);W=M[f+['MR','C']].dropna().loc['1926-07':];R=W[f].values[None]
  for L in LEVELS:
   z=core.simulate(R,np.zeros((1,len(W),1)),W[['MR','C']].values[None],weights(M,item),np.zeros(1),L,np.array([COST[c] for c in f]),np.zeros(1),np.ones(len(W),bool));w=z['wealth'][0];r=pd.Series(np.divide(w[1:],w[:-1],out=np.ones(len(W)),where=w[:-1]>0)-1,index=W.index)
   us.append({'key':f'{item}@{L:g}',**stat(r,M.C,cpi.CPI_US,False),'calls_monthly':int(z['calls'][0]),'depression_return':mx.crisis_table(r,mx.CRISES_US1926)['1929-32 Depression'][0]})
 pd.DataFrame(us).to_csv(O/'us1926.csv',index=False)
 (O/'completed.json').write_text(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'rows':len(rows)},indent=2))
if __name__=='__main__':main()
