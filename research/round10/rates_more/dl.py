"""Download yfinance bars for the rates_more sister-mechanism test. Caches parquet in ./cache."""
import os, yfinance as yf, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); CACHE = os.path.join(HERE, "cache"); os.makedirs(CACHE, exist_ok=True)
NAMES = {
 "auto": "CVNA KMX AN LAD ABG PAG ALLY CACC",
 "rv_boat_hvac": "THO WGO LCII BC MBUU MCFT POOL LII CARR WSO",
 "mortgage_services": "FAF FNF UHAL FTDR PRCH",
 "timber": "WY RYN PCH LPX UFPI BCC",
 "housing_banks": "FLG WAL BKU TFSL",
 "canada": "EQB.TO FN.TO MKP.TO FC.TO",
 "placebo": "SPY ITB",
 "fx": "CAD=X",
}
TICKERS = sorted({t for g in NAMES.values() for t in g.split()})
for t in TICKERS:
    for iv, per in [("60m", "730d"), ("1d", "max")]:
        f = os.path.join(CACHE, f"{t.replace('.', '_')}_{iv}.parquet")
        if os.path.exists(f): continue
        try:
            d = yf.Ticker(t).history(period=per, interval=iv, auto_adjust=False, prepost=False)
        except Exception as e:
            print(t, iv, "ERR", e); continue
        if len(d) == 0: print(t, iv, "EMPTY"); continue
        d.to_parquet(f); print(t, iv, len(d), d.index[0], d.index[-1], flush=True)
