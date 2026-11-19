"""Pull 60m bars (yfinance, ~730d) for overnight signal futures and leveraged/high-beta ETF targets."""
import yfinance as yf, pandas as pd, os
OUT = "research/gap_scan_1027/bars"; os.makedirs(OUT, exist_ok=True)
SIG = ["ZB=F", "ZN=F", "CL=F", "GC=F", "ES=F", "NQ=F", "RTY=F", "HG=F", "NG=F", "6J=F", "BTC-USD"]
TGT = ["NAIL", "DRN", "DPST", "FAS", "TNA", "URTY", "UTSL", "ERX", "GUSH", "NUGT", "JNUG", "SOXL", "TQQQ", "LABU",
       "TMF", "TYD", "UWMC", "RKT", "KBH", "TOL", "MSTR", "BITX", "COIN", "FNGU", "BOIL", "UCO", "YINN", "EDC", "KRE", "XHB"]
for s in SIG + TGT:
    try:
        d = yf.download(s, period="729d", interval="60m", progress=False, auto_adjust=False)
        d.columns = d.columns.get_level_values(0); d.to_parquet(f"{OUT}/{s.replace('=', '_')}.parquet"); print(s, len(d))
    except Exception as e: print(s, "ERR", str(e)[:60])
