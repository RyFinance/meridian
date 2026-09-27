"""Three fixed designs on the live SPMO history; no parameter sweep."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
from research.return_search.run import execute,stats,cash_rates
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'reports/momentum_fund_designs_20260919'
SPEC={'date':'2026-09-19','instruments':['SPMO','GLD','IEF'],'candidate_count':3,'candidates':{'vol_scaled':'SPMO target exposure min(1,15% / trailing63-session annual volatility), weekly first-session close, next-open fill','diversified_trend':'fixed 60% SPMO,20% GLD,20% IEF; each slot invested only if asset close exceeds its trailing200-session mean; monthly first-session close, next-open fill','defensive_rotation':'100% SPMO while close above trailing200-session mean; otherwise hold the stronger trailing63-session positive-return asset among GLD and IEF; if neither positive, cash; monthly close decision,next-open fill'},'controls':['SPMO passive','SPY passive'],'development':['2017-01-01','2019-12-31'],'evaluation':['2020-01-01','2026-09-17'],'selection':'highest development net CAGR among candidates with drawdown no deeper than30% and positive stress excess mean','base_cost':'5bps per side','stress_cost':'15bps per side','leverage':False,'cash':'previous observed IRX pro rata elapsed days','limitations':'new fixed designs on previously researched history; not a pristine holdout; no parameters changed after evaluation; actual fund prices include fund expenses'}

def load(end):
    frames={}
    for s in ['SPMO','GLD','IEF','SPY']:
        p=ROOT/'reports/momentum_verification_20260919/inputs/SPMO.parquet' if s=='SPMO' else ROOT/f'data/multiasset/etf/{s}.parquet'
        d=pd.read_parquet(p)
        if s=='SPMO':d.index=d.index.tz_localize(None).normalize();d.columns=[x.lower() for x in d.columns]
        else:d=d.set_index('date');d.index=pd.to_datetime(d.index).tz_localize(None).normalize()
        frames[s]=d.loc['2015-10-12':end]
    dates=frames['SPY'].index
    return {k:pd.DataFrame({s:d[k] for s,d in frames.items()}).reindex(dates) for k in ['open','close']}

def weights(c,name):
    dates=c.index;out=pd.DataFrame(np.nan,index=dates,columns=c.columns)
    if name.startswith('passive_'):
        out.iloc[0]=0;out.iloc[0,out.columns.get_loc(name.split('_')[1])]=1;return out
    period='W' if name=='vol_scaled' else 'M'
    periods=pd.Series(dates.to_period(period),index=dates);decisions=periods.ne(periods.shift())
    vol=c.SPMO.pct_change(fill_method=None).rolling(63).std()*np.sqrt(252)
    trend=c>c.rolling(200).mean();momentum=c/c.shift(63)-1
    for date in dates[decisions]:
        out.loc[date]=0
        if name=='vol_scaled':
            if np.isfinite(vol.loc[date]) and vol.loc[date]>0:out.loc[date,'SPMO']=min(1,.15/vol.loc[date])
        elif name=='diversified_trend':
            for s,w in [('SPMO',.6),('GLD',.2),('IEF',.2)]:out.loc[date,s]=w if trend.loc[date,s] else 0
        elif name=='defensive_rotation':
            if trend.loc[date,'SPMO']:out.loc[date,'SPMO']=1
            else:
                s=momentum.loc[date,['GLD','IEF']].dropna()
                if len(s) and s.max()>0:out.loc[date,s.idxmax()]=1
        else:raise ValueError(name)
    return out

def main():
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['dev','evaluation']);phase=p.parse_args().phase
    encoded=json.dumps(SPEC,sort_keys=True,indent=2);registration=OUT/'registration.json'
    if registration.exists():assert registration.read_text()==encoded
    else:registration.write_text(encoded)
    end='2019-12-31' if phase=='dev' else '2026-09-17';start='2017-01-01' if phase=='dev' else '2020-01-01'
    if phase=='evaluation':
        selection=json.loads((OUT/'selection.json').read_text());assert selection['code_sha256']==hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        if (OUT/'evaluation_results.json').exists():raise RuntimeError('evaluation already completed')
    panels=load(end);rf=cash_rates(panels['close'].index,end);result={}
    for name in list(SPEC['candidates'])+['passive_SPMO','passive_SPY']:
        t=weights(panels['close'],name);result[name]={};t.to_csv(OUT/f'{phase}_{name}_targets.csv')
        for label,stress in [('base',False),('stress',True)]:
            f=execute(panels,t,rf,'etf',stress=stress,start=start);f.to_csv(OUT/f'{phase}_{name}_{label}.csv');result[name][label]=stats(f,rf,252)
            if not stress:result[name]['yearly']={str(y):stats(g,rf,252) for y,g in f.groupby(f.index.year)}
        print(name,json.dumps(result[name]['base']),flush=True)
    (OUT/f'{phase}_results.json').write_text(json.dumps(result,indent=2,allow_nan=False))
    if phase=='dev':
        eligible=[n for n in SPEC['candidates'] if result[n]['base']['max_dd']>=-.3 and result[n]['stress']['ann_excess_mean']>0]
        selected=max(eligible,key=lambda n:result[n]['base']['cagr']) if eligible else None
        (OUT/'selection.json').write_text(json.dumps({'selected':selected,'eligible':eligible,'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},indent=2));print('SELECTED',selected,flush=True)
if __name__=='__main__':main()
