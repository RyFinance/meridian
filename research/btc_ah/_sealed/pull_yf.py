"""Sealed holdout: daily OHLC 2026-07-01..2026-10-17 and MSTR 5m incl. pre/post (last 60d). Saved, not inspected."""
import yfinance as yf
from pathlib import Path
H = Path(__file__).parent
T = ["MSTR","MARA","RIOT","CLSK","HUT","CIFR","WULF","IREN","COIN","BTBT","IBIT","BITO"]
d = yf.download(T, start="2026-07-01", end="2026-10-18", auto_adjust=False, progress=False, group_by="ticker"); d.to_pickle(H/"daily_holdout.pkl")
m = yf.download("MSTR", period="60d", interval="5m", prepost=True, auto_adjust=False, progress=False); m.to_pickle(H/"mstr_5m_prepost_holdout.pkl")
print("saved", d.shape, m.shape)
