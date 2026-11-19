import yfinance as yf, pandas as pd, os
S="OPEN Z ZG RDFN COMP EXPI RMAX OPAD RH W WSM ETD LZB SNBR TAN ENPH RUN SEDG NOVA ARRY FSLR SOFI UPST AFRM LC ALLY COF SYF OMF IWO CVNA".split()
os.makedirs("cache",exist_ok=True)
for s in S:
    for iv,kw in [("60m",dict(period="730d",interval="60m")),("1d",dict(period="max",interval="1d"))]:
        try:
            d=yf.Ticker(s).history(auto_adjust=False,**kw)
            if len(d)>50: d.to_parquet(f"cache/{s}_{iv}.parquet")
            print(s,iv,len(d),d.index[0] if len(d) else "")
        except Exception as e: print(s,iv,"ERR",e)
