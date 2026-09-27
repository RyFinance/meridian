"""Earlier actual-fund control, explicitly not SPMO history."""
import json
import pandas as pd
from research.momentum_verification.codex_gold_recency_audit import ROOT,OUT,targets
from research.return_search.run import execute,stats,cash_rates
frames={}
for s in ['SPY','GLD']:
    d=pd.read_parquet(ROOT/f'data/multiasset/etf/{s}.parquet').set_index('date');d.index=pd.to_datetime(d.index).tz_localize(None).normalize();frames[s]=d
idx=frames['SPY'].index.intersection(frames['GLD'].index)
p={k:pd.DataFrame({s:d[k] for s,d in frames.items()}).reindex(idx).loc[:'2023-12-31'] for k in ['open','close']}
rf=cash_rates(p['close'].index,'2023-12-31');result={}
for name,w in [('market_gold',{'SPY':.5,'GLD':.5}),('market',{'SPY':1.})]:
    t=targets(p['close'],w);result[name]={}
    for label,start,end in [('2005_2016','2005-01-01','2016-12-31'),('2012_2015','2012-01-01','2015-12-31'),('2005_2023','2005-01-01','2023-12-31')]:
        f=execute({k:v.loc[:end] for k,v in p.items()},t.loc[:end],rf,'etf',start=start)
        result[name][label]=stats(f,rf,252)
(OUT/'early_control.json').write_text(json.dumps({'limitation':'SPY/GLD actual-fund proxy only. SPMO did not exist in these earlier years. These periods were not untouched research holdouts.','results':result},indent=2));print(json.dumps(result,indent=2))
