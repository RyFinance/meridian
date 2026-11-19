from pathlib import Path
import json,datetime,hashlib
from research.lse_mcp_client import Terminal,content_text
OUT=Path('data/cycle8_us_only_followup/lse');OUT.mkdir(parents=True,exist_ok=True)
queries=[('spy_search','search_instruments',{'query':'SPY','provider':'lse','limit':20}),('10y_search','macro_search',{'query':'10Y yield','country':'US','limit':50})]
with Terminal() as t:
 for name,tool,args in queries:
  r=t.call(tool,args,timeout=30);p=OUT/(name+'.json');p.write_text(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'tool':tool,'arguments':args,'result':r},indent=2));print(name,content_text(r)[:8000],flush=True)
