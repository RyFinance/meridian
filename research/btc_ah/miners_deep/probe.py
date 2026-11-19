import io, time, pandas as pd, yfinance as yf
from research.lse_mcp_client import Terminal, content_text
out = {}
with Terminal() as t:
    for sym in ["MARA", "HUT"]:
        for tf in ["30m", "1h", "60m"]:
            try:
                r = t.call("get_history", {"symbol": sym, "timeframe": tf, "start": "2021-01-04", "end": "2021-01-08", "limit": 1000})
                txt = content_text(r)
                print(sym, tf, "chars", len(txt), "| head:", txt[:300].replace("\n", " | "), flush=True)
            except Exception as e:
                print(sym, tf, "ERR", repr(e)[:200], flush=True)
            time.sleep(1)
for s in ["BTDR", "HIVE", "CORZ", "APLD", "GLXY", "BITF", "MARA", "CIFR", "WULF"]:
    try:
        d = yf.download(s, start="2019-01-01", end="2026-08-11", interval="1d", auto_adjust=False, progress=False, actions=False)
        if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
        print("YF", s, len(d), d.index.min() if len(d) else None, d.index.max() if len(d) else None, flush=True)
    except Exception as e:
        print("YF", s, "ERR", repr(e)[:150], flush=True)
