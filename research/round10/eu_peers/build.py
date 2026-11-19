import pandas as pd, numpy as np, pickle
B="/Users/rytty/CCP/quant_v7/research/round10/eu_peers/cache"
ET="America/New_York"
def ld(t,iv="60m"): return pd.read_pickle(f"{B}/{t}_{iv}.pkl")
EU="ASML.AS NOVO-B.CO AIR.PA SAP.DE MC.PA RMS.PA KER.PA VOW3.DE STLAM.MI BMW.DE SIE.DE ULVR.L NESN.SW BAS.DE AZN.L RIO.L SHEL.L ^STOXX50E".split()
US="AMAT LRCX KLAC LLY BA ORCL CRM TPR RL CPRI EL GM F GE HON PG CL GIS KHC DOW LYB MRK PFE FCX XOM CVX SPY JPM WMT COST NFLX ADBE UNH".split()
# ---- US per-day: entry = 09:30 bar open; exits
rows={}
for t in US:
    d=ld(t).tz_convert(ET); d=d[~d.index.duplicated()]
    d["date"]=d.index.normalize().tz_localize(None); d["hm"]=d.index.strftime("%H:%M")
    out={}
    for dt,g in d.groupby("date"):
        g=g.set_index("hm")
        if "09:30" not in g.index: continue
        ent=g.loc["09:30","Open"]
        x1=g.loc["09:30","Close"]
        x2=g.loc["10:30","Close"] if "10:30" in g.index else np.nan
        x3=g["Close"].iloc[-1] if "15:30" in g.index else np.nan
        out[dt]=(ent,x1,x2,x3)
    rows[t]=pd.DataFrame(out,index=["ent","x1030","x1130","xcl"]).T
us=pd.concat(rows,axis=1)
us.to_pickle("us_panel.pkl")
# ---- EU per-day signals. Bars START-labeled; convert to ET.
sig={}
for t in EU:
    d=ld(t).tz_convert(ET); d=d[~d.index.duplicated()]
    d=d[d["Close"].notna()]
    idx=d.index
    days=pd.DatetimeIndex(sorted(set(idx.normalize().tz_localize(None))))
    out={}
    for D in days:
        D0=pd.Timestamp(D).tz_localize(ET)
        cut=D0+pd.Timedelta(hours=8)   # bars starting <=08:00 ET end <=09:00 ET
        prev=d[idx<D0]
        today=d[(idx>=D0)&(idx<=cut)]
        if len(prev)==0 or len(today)==0: continue
        # require the first bar of today starts before 06:00 ET (a real session); and prev close from a session ending ~ 11:30
        pc=prev["Close"].iloc[-1]; p1=today["Close"].iloc[-1]; op=today["Open"].iloc[0]
        out[D]=(pc,op,p1,today.index[-1].hour, today.index[0].hour)
    sig[t]=pd.DataFrame(out,index=["pc","op","p1","lasthr","firsthr"]).T
pickle.dump(sig,open("eu_sig.pkl","wb"))
print(us.shape); print({k:len(v) for k,v in sig.items()})
print(sig["ASML.AS"].tail(3)); print(sig["ASML.AS"].lasthr.value_counts().to_dict(), sig["ASML.AS"].firsthr.value_counts().to_dict())
