import yfinance as yf,time
D="research/zb_itb/round5/rate_universe/cache/"
for s in ["EQR","AVB","TMHC","TPH","AZEK"]:
    for k in range(3):
        a=yf.download(s,period="730d",interval="60m",progress=False,auto_adjust=False,multi_level_index=False)
        b=yf.download(s,period="760d",interval="1d",progress=False,auto_adjust=False,multi_level_index=False)
        if len(a)>100 and len(b)>100: a.to_parquet(D+s+"_60m.parquet"); b.to_parquet(D+s+"_1d.parquet");break
        time.sleep(3)
    print(s,len(a),len(b))
