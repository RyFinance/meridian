"""Fixed equal-capital momentum/gold diversification; no weight optimization."""
import hashlib,json
from pathlib import Path
import pandas as pd
import statsmodels.api as sm
from research.return_search.run import execute,stats,cash_rates
from research.momentum_verification.codex_fund_designs import load
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'reports/momentum_gold_20260919'
SPEC={'hypothesis':'Diversify the documented momentum-stock return stream with gold; remove the losing timing/bond overlays rather than fitting new parameters. This is a separately recorded follow-up trial after those results.','primary':'50% SPMO,50% GLD,rebalance first trading session monthly at next open','control':'50% SPY,50% GLD with identical execution','weights':'equal fixed capital,no fitting','base':'5bps per side','stress':'15bps per side','selection_period':'2017-2019 descriptive; no model choice since there is only one new candidate','later_evaluation':'2020-2026-09-17','bias_note':'previously researched history, not an untouched holdout; follow-up testing contributes to project-wide multiple testing','leverage':False}


def main():
    reg=OUT/'registration.json';text=json.dumps(SPEC,indent=2,sort_keys=True)
    if reg.exists():assert reg.read_text()==text
    else:reg.write_text(text)
    if (OUT/'results.json').exists():raise RuntimeError('completed already')
    p=load('2026-09-17');rf=cash_rates(p['close'].index,'2026-09-17');c=p['close'];month=pd.Series(c.index.to_period('M'),index=c.index);decisions=month.ne(month.shift());results={};paths={}
    for key,stock in [('momentum_gold','SPMO'),('market_gold','SPY')]:
        t=c*float('nan');t.loc[decisions]=0;t.loc[decisions,stock]=.5;t.loc[decisions,'GLD']=.5;t.to_csv(OUT/f'{key}_targets.csv');results[key]={}
        for period,a,b in [('earlier','2017-01-01','2019-12-31'),('later','2020-01-01','2026-09-17'),('full','2017-01-01','2026-09-17')]:
            results[key][period]={}
            for label,stress in [('base',False),('stress',True)]:
                f=execute({k:v.loc[:b] for k,v in p.items()},t.loc[:b],rf,'etf',stress=stress,start=a);paths[key,period,label]=f;f.to_csv(OUT/f'{key}_{period}_{label}.csv');results[key][period][label]=stats(f,rf,252)
                if period=='full' and label=='base':results[key]['yearly']={str(y):stats(g,rf,252) for y,g in f.groupby(f.index.year)}
        print(key,json.dumps({period:results[key][period]['base'] for period in ['earlier','later','full']}),flush=True)
    for period in ['earlier','later','full']:
        excess=paths['momentum_gold',period,'base']['return']-paths['market_gold',period,'base']['return']
        fit=sm.OLS(excess,excess*0+1).fit(cov_type='HAC',cov_kwds={'maxlags':21})
        results['active_'+period]={'annual_mean':float(excess.mean()*252),'t_hac':float(fit.tvalues.iloc[0]),'ci95':(fit.conf_int().iloc[0]*252).tolist()}
    results['code_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();(OUT/'results.json').write_text(json.dumps(results,indent=2,allow_nan=False))
if __name__=='__main__':main()
