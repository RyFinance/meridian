"""Three fixed reversal hypotheses, next-open execution, no fitted model."""
import json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from research.return_search.run import panel,read,cash_rates,execute,stats
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'reports/reversal_research_20260921';END='2026-09-17'
SECTORS=['XLB','XLE','XLF','XLI','XLK','XLP','XLU','XLV','XLY']
PERIODS={'early':('2008-01-01','2016-12-31'),'pre_recent':('2017-01-01','2023-12-31'),'recent':('2024-01-01',END),'full':('2008-01-01',END)}
SPEC={'hypothesis':'Temporary liquidity shocks may reverse over the next week. Market-relative returns separate stock-specific moves from market moves.','source':'https://www.nber.org/papers/w17653','candidates':{'stock_residual_reversal':'Bottom 20 trailing-five-day beta-residual returns among trailing63day top200 dollar-volume stocks with ADV>=20m and252 observations; five overlapping equal-weight target sleeves.','stock_shock_rebound':'Same liquidity universe; daily residual below minus2 trailing63day residual standard deviations, stock close above trailing200day mean; most extreme20; unfilled slots cash; five overlapping target sleeves.','sector_reversal':'Bottom3 prior5day returns in nine original Select Sector ETFs; five overlapping equal-weight target sleeves.'},'controls':['same-universe equal stocks monthly','equal nine sectors monthly'],'costs':'5bps each side; stress15bps each side; final liquidation; adjusted fund/stock prices; cash prior-observed IRX','execution':'close signal, next-open trade; daily rebalanced average of last5 sleeve targets; not a fixed-unit five-day holding simulation','periods':PERIODS,'selection':'No optimization. Report every candidate and control in every period. No designation as untouched holdout.','limits':'Stock cache is current-survivor biased: stock results are screening diagnostics, never deployment evidence. Nine-sector universe fixed and known before all test periods. No gold, leverage or shorting.'}

def rank_weights(score,eligible,n,slots=None):
    ranks=score.where(eligible).rank(axis=1,method='first',ascending=True);chosen=ranks.le(n)
    denom=(chosen.sum(axis=1).clip(lower=1) if slots is None else slots)
    return chosen.astype(float).div(denom,axis=0) if not isinstance(denom,int) else chosen.astype(float)/denom

def make_targets(p,spy,family):
    c=p['close'];r=c.pct_change(fill_method=None);month=pd.Series(c.index.to_period('M'),index=c.index);first=month.ne(month.shift())
    if family=='stocks':
        adv=(p['volume']*c).rolling(63).mean();eligible=adv.ge(20e6)&adv.rank(axis=1,ascending=False,method='first').le(200)&c.shift(252).notna()&c.gt(5)
        market=spy.reindex(c.index).pct_change(fill_method=None)
        beta=r.rolling(126).cov(market).div(market.rolling(126).var(),axis=0).shift(1)
        residual=r-beta.mul(market,axis=0)
        score=(c/c.shift(5)-1)-beta.mul(spy.reindex(c.index)/spy.reindex(c.index).shift(5)-1,axis=0)
        z=residual/residual.rolling(63).std().shift(1)
        rule1=rank_weights(score,eligible,20,20).rolling(5,min_periods=5).mean().fillna(0)
        rule2=rank_weights(z,eligible&z.lt(-2)&c.gt(c.rolling(200).mean()),20,20).rolling(5,min_periods=5).mean().fillna(0)
        out={'stock_residual_reversal':rule1,'stock_shock_rebound':rule2}
    else:
        eligible=c.shift(252).notna();out={'sector_reversal':rank_weights(c/c.shift(5)-1,eligible,3,3).rolling(5,min_periods=5).mean().fillna(0)}
    control=eligible.astype(float).div(eligible.sum(axis=1).clip(lower=1),axis=0);control.loc[~first]=np.nan;out[family+'_equal_control']=control
    return out

def main():
    OUT.mkdir(exist_ok=True);spec=json.dumps(SPEC,indent=2,sort_keys=True);reg=OUT/'registration.json'
    if reg.exists():assert reg.read_text()==spec
    else:reg.write_text(spec)
    if (OUT/'results.json').exists():raise RuntimeError('Completed trial; do not silently rerun/change hypotheses')
    result={};spy=read(ROOT/'data/multiasset/etf/SPY.parquet',END)['close'];checks={}
    for family in ['etf','stocks']:
        p=panel(family,END)
        if family=='etf':p={k:v[SECTORS] for k,v in p.items()}
        c=p['close'];rf=cash_rates(c.index,END);ts=make_targets(p,spy,family)
        cut='2018-12-31';truncated=make_targets({k:v.loc[:cut] for k,v in p.items()},spy.loc[:cut],family)
        for name,t in ts.items():
            assert np.allclose(t.loc[:cut],truncated[name],equal_nan=True),name
            assert (t.dropna().sum(axis=1)<=1+1e-10).all()
            checks[name]={'future_truncation_invariant':True,'max_weight':float(t.max().max()),'max_target_sum':float(t.sum(axis=1).max())}
            t.to_parquet(OUT/f'{name}_targets.parquet');result[name]={}
            for period,(a,b) in PERIODS.items():
                result[name][period]={}
                for label,stress in [('base',False),('stress',True)]:
                    f=execute({k:v.loc[:b] for k,v in p.items()},t.loc[:b],rf,family,start=a,stress=stress)
                    f.to_csv(OUT/f'{name}_{period}_{label}.csv');result[name][period][label]=stats(f,rf,252)
                print(name,period,{k:round(result[name][period]['base'][k],4) for k in ['cagr','excess_sharpe','max_dd','annual_cost','average_exposure']},flush=True)
    (OUT/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False));(OUT/'checks.json').write_text(json.dumps(checks,indent=2));(OUT/'code_sha256.txt').write_text(hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
if __name__=='__main__':main()
