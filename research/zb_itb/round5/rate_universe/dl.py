import yfinance as yf, os
S="RKT UWMC PFSI COOP AGNC NLY MTG RDN ESNT FNF FAF MTH TMHC MHO CCS LGIH TPH DFH BLDR MAS OC TREX AZEK FBIN MHK SHW POOL LOW HD WHR INVH AMH EQR AVB MAA ESS UDR CPT SUI ELS O PLD XLRE NAIL REZ MORT ARKK IJT VBK ITB XHB".split()
D="research/zb_itb/round5/rate_universe/cache/"
for s in S:
    try:
        a=yf.download(s,period="730d",interval="60m",progress=False,auto_adjust=False,multi_level_index=False)
        b=yf.download(s,period="760d",interval="1d",progress=False,auto_adjust=False,multi_level_index=False)
        if len(a)>100: a.to_parquet(D+s+"_60m.parquet"); b.to_parquet(D+s+"_1d.parquet")
        print(s,len(a),len(b),flush=True)
    except Exception as e: print(s,"ERR",e)
