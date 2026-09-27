"""Frozen-weight recency diagnostics; no strategy selection or optimization."""
import json
from pathlib import Path
import pandas as pd
from research.momentum_verification.codex_fund_designs import load
from research.momentum_verification.codex_ledger import ledger
from research.return_search.run import cash_rates,stats
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'reports/momentum_gold_audit_20260921'
WINDOWS={'full':('2017-01-01','2026-09-17'),'pre_2024':('2017-01-01','2023-12-31'),'pre_2025':('2017-01-01','2024-12-31'),'pre_2026':('2017-01-01','2025-12-31'),'2020_2023':('2020-01-01','2023-12-31'),'2022_2023':('2022-01-01','2023-12-31'),'recent':('2024-01-01','2026-09-17')}
def targets(c,w):
    m=pd.Series(c.index.to_period('M'),index=c.index);t=c*float('nan');t.loc[m.ne(m.shift())]=0
    for s,v in w.items():t.loc[m.ne(m.shift()),s]=v
    return t

def main():
    (OUT/'protocol.json').write_text(json.dumps({'windows':WINDOWS,'weights_frozen':True,'no_optimization':True,'end':'2026-09-17','cost_per_side':.0005,'purpose':'diagnose recent-regime dependence, not a new holdout'},indent=2))
    p=load('2026-09-17');c=p['close'];rf=cash_rates(c.index,'2026-09-17');results={};paths={}
    designs={'momentum_gold':{'SPMO':.5,'GLD':.5},'market_gold':{'SPY':.5,'GLD':.5},'momentum_cash':{'SPMO':.5},'momentum':{'SPMO':1.}}
    for name,w in designs.items():
        results[name]={};t=targets(c,w)
        for period,(a,b) in WINDOWS.items():
            f,fills,contrib,error=ledger(p['open'].loc[:b],c.loc[:b],t.loc[:b],rf,a)
            assert abs(error)<1e-6
            results[name][period]={'metrics':stats(f,rf,252),'asset_pnl_dollars':contrib.to_dict(),'cost_dollars':float(f.cost_dollars.sum()),'interest_dollars':float(f.interest_dollars.sum()),'reconciliation_error':error}
            paths[name,period]=f
            f.to_csv(OUT/f'{name}_{period}.csv')
        print(name,{k:{s:round(v['metrics'][s],4) for s in ['cagr','excess_sharpe','max_dd']} for k,v in results[name].items()},flush=True)
    # Raw asset calendar returns use the previous year-end close, including January's first session.
    returns=c.pct_change(fill_method=None)
    results['asset_year_returns']={str(y):((1+g).prod()-1).to_dict() for y,g in returns.loc['2017':].groupby(returns.loc['2017':].index.year)}
    # Reconstruct actual close weights from independent fills (adjusted units) before final liquidation.
    f,fills,_,_=ledger(p['open'],c,targets(c,designs['momentum_gold']),rf,'2017-01-01')
    fills=fills[fills.get('execution',pd.Series(index=fills.index,dtype=object)).ne('final liquidation at close')]
    u=fills.pivot_table(index='date',columns='symbol',values='adjusted_units_delta',aggfunc='sum');u.index=pd.to_datetime(u.index)
    u=u.reindex(f.index).fillna(0).cumsum();values=u*c.reindex(f.index)[u.columns];weights=values.div(values.sum(axis=1),axis=0)
    weights.to_csv(OUT/'actual_close_weights.csv');results['gold_weight']={'mean':float(weights.GLD.mean()),'min':float(weights.GLD.min()),'max':float(weights.GLD.max())}
    rolling=[]
    for months in [36,60]:
        for end in pd.date_range('2019-12-31','2026-08-31',freq='ME'):
            start=(end-pd.DateOffset(months=months))+pd.Timedelta(days=1)
            if start<pd.Timestamp('2017-01-01'):continue
            f,_,_,_=ledger(p['open'].loc[:end],c.loc[:end],targets(c,designs['momentum_gold']).loc[:end],rf,start)
            rolling.append({'months':months,'start':str(start.date()),'end':str(end.date()),**stats(f,rf,252)})
    pd.DataFrame(rolling).to_csv(OUT/'rolling_windows.csv',index=False)
    results['rolling_summary']={str(m):{'min_cagr':float(g.cagr.min()),'median_cagr':float(g.cagr.median()),'min_sharpe':float(g.excess_sharpe.min()),'median_sharpe':float(g.excess_sharpe.median())} for m,g in pd.DataFrame(rolling).groupby('months')}
    original=pd.read_csv(ROOT/'reports/momentum_gold_20260919/momentum_gold_full_base.csv',index_col=0,parse_dates=True)
    results['max_original_nav_difference']=float((original.nav-paths['momentum_gold','full'].nav).abs().max());assert results['max_original_nav_difference']<1e-10
    (OUT/'results.json').write_text(json.dumps(results,indent=2,allow_nan=False))
if __name__=='__main__':main()
