from pathlib import Path
import json,datetime,hashlib
from research.lse_mcp_client import Terminal,content_text
P=Path('data/cycle8_us_only_followup/lse');P.mkdir(parents=True,exist_ok=True)
queries=[('spy_daily','get_history',{'symbol':'SPY','provider':'lse','timeframe':'1d','start':'2026-08-01','end':'2026-08-31','limit':5000}),('spy_minutes','get_history',{'symbol':'SPY','provider':'lse','timeframe':'1m','start':'2026-08-17T00:00:00Z','end':'2026-08-20T00:00:00Z','limit':5000}),('us10y_daily','macro_series',{'symbol':'US10Y','dataset':'bonds','start':'1990-01-01','end':'2026-08-31','limit':5000,'order':'asc'})]
with Terminal() as t:
 for name,tool,args in queries:
  r=t.call(tool,args,timeout=45);doc={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'tool':tool,'arguments':args,'result':r}
  (P/(name+'.json')).write_text(json.dumps(doc,indent=2));print(name,content_text(r)[:3000],flush=True)
