import yfinance as yf, os
O="research/zb_itb/round6/rates2/cache/"
S="LQD VCIT IGIB HYG JNK EMB MUB PFF MBB TLT IEF SHY MET PRU LNC CRBG SCHW IBKR HOOD XBI IPO ARKG ARKK VPU IDU NEE DUK SO AWK AEP ARCC MAIN SPY".split()
for s in S:
    for iv,kw in [("60m",dict(period="730d",interval="60m")),("1d",dict(period="730d",interval="1d"))]:
        try:
            d=yf.download(s,progress=False,auto_adjust=False,**kw)
            if hasattr(d.columns,"levels"): d.columns=d.columns.get_level_values(0)
            if len(d): d.to_parquet(O+f"{s}_{iv}.parquet")
            print(s,iv,len(d))
        except Exception as e: print(s,iv,"ERR",e)
