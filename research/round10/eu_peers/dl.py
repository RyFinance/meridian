import yfinance as yf, pandas as pd, os, pickle
eu="ASML.AS NOVO-B.CO AIR.PA SAP.DE MC.PA RMS.PA KER.PA VOW3.DE STLAM.MI BMW.DE SIE.DE ULVR.L NESN.SW BAS.DE AZN.L RIO.L SHEL.L ^STOXX50E".split()
us="AMAT LRCX KLAC LLY BA ORCL CRM TPR RL CPRI EL GM F GE HON PG CL GIS KHC DOW LYB MRK PFE FCX XOM CVX SPY JPM WMT COST NFLX ADBE UNH".split()
B="/Users/rytty/CCP/quant_v7/research/round10/eu_peers/cache"; os.makedirs(B,exist_ok=True)
for t in eu+us:
    for iv,per in [("60m","730d"),("1d","max")]:
        f=f"{B}/{t}_{iv}.pkl"
        if os.path.exists(f): continue
        try:
            d=yf.Ticker(t).history(period=per,interval=iv,auto_adjust=False,prepost=False)
        except Exception as e:
            print(t,iv,"ERR",e); continue
        d.to_pickle(f); print(t,iv,len(d),d.index[0],d.index[-1])
