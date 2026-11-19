"""Download inputs into this folder's cache. Daily yfinance for ITB, ZB=F, ^TNX (full history) and FRED MORTGAGE30US.
60m ITB and ZB=F are copied from the frozen verify cache (last 730d only)."""
import shutil, subprocess, pandas as pd, yfinance as yf
C = "research/zb_itb/round7/mortgage_weekly/cache/"
for sym, fn in [("ITB", "ITB_1d"), ("ZB=F", "ZB_F_1d"), ("^TNX", "TNX_1d")]:
    d = yf.download(sym, start="1990-01-01", end="2026-10-17", interval="1d", auto_adjust=False, progress=False)
    d.columns = [c[0] if isinstance(c, tuple) else c for c in d.columns]
    d.to_parquet(C + fn + ".parquet"); print(sym, d.index.min(), d.index.max(), len(d))
    print(d.tail(2).to_string())
for f in ["ITB_60m", "ZB_F_60m"]:
    shutil.copy("research/zb_itb/verify/yf_cache/%s.parquet" % f, C + f + ".parquet")
subprocess.run(["curl", "-sS", "-m", "30", "-o", C + "MORTGAGE30US.csv",
                "https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US"], check=True)
print("FRED rows", sum(1 for _ in open(C + "MORTGAGE30US.csv")))
