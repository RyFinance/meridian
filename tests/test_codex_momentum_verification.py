import numpy as np
import pandas as pd
from research.momentum_verification.codex_ledger import ledger
from research.return_search.run import execute
from research.momentum_verification.codex_fund_designs import weights


def test_independent_ledger_reconciles_costs_and_overnight_moves():
    idx=pd.bdate_range('2020-01-01',periods=20);rng=np.random.default_rng(3)
    c=pd.DataFrame(100*np.exp(np.cumsum(rng.normal(0,.02,(20,2)),axis=0)),index=idx)
    o=c*.997;t=c*float('nan');t.iloc[0]=[.5,.5];t.iloc[8]=[1,0];t.iloc[15]=[0,1]
    rf=pd.Series(.0001,index=idx)
    a,_,_,error=ledger(o,c,t,rf,str(idx[0].date()))
    b=execute({'open':o,'close':c},t,rf,'stocks',start=str(idx[0].date()))
    np.testing.assert_allclose(a.nav,b.nav,atol=1e-11)
    assert abs(error)<1e-6


def test_minimum_order_fee_reduces_wealth():
    idx=pd.bdate_range('2020-01-01',periods=10);c=pd.DataFrame(100.,index=idx,columns=['A','B']);t=c*float('nan');t.iloc[0]=[.5,.5];rf=pd.Series(0.,index=idx)
    a,_,_,_=ledger(c,c,t,rf,str(idx[0].date()),order_fee=0)
    b,_,_,error=ledger(c,c,t,rf,str(idx[0].date()),order_fee=1)
    assert b.nav.iloc[-1]<a.nav.iloc[-1];assert abs(error)<1e-6


def test_fund_rules_are_causal_fully_funded():
    idx=pd.bdate_range('2015-01-01',periods=650);rng=np.random.default_rng(18)
    c=pd.DataFrame(100*np.exp(np.cumsum(rng.normal(.0003,.01,(650,4)),axis=0)),index=idx,columns=['SPMO','GLD','IEF','SPY'])
    changed=c.copy();changed.iloc[500:]*=4
    for name in ['vol_scaled','diversified_trend','defensive_rotation']:
        t=weights(c,name)
        pd.testing.assert_frame_equal(t.iloc[:500],weights(changed,name).iloc[:500])
        assert t.dropna().sum(axis=1).le(1+1e-12).all()
        assert t.dropna().ge(0).all().all()
