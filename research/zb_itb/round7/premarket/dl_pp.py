"""Download yfinance 5m bars with prepost=True for ITB and XHB (last 60 days) into this folder."""
from pathlib import Path
import yfinance as yf
OUT = Path(__file__).parent / "data"; OUT.mkdir(exist_ok=True)
for s in ["ITB", "XHB"]:
    d = yf.download(s, period="60d", interval="5m", auto_adjust=False, progress=False, prepost=True)
    d.columns = d.columns.get_level_values(0)
    f = OUT / f"{s}_5m_pp.parquet"; d.to_parquet(f)
    print(f.name, len(d), d.index.min(), d.index.max(), flush=True)
