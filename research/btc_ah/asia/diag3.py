import numpy as np, pandas as pd
OUT="/Users/rytty/CCP/quant_v7/research/btc_ah/asia"
pd.set_option("display.width",250); pd.set_option("display.max_colwidth",80)
T=pd.read_parquet(f"{OUT}/trades_all.parquet")
R=pd.read_csv(f"{OUT}/variants.csv")
print("intraday rows:")
print(R[R.fam.str.startswith("intra")][["ticker","fam","par","dev_n","dev_bp","dev_t","chk_n","chk_bp","chk_t","flip_dev_bp","flip_chk_bp"]].round(1).to_string(index=False))
print("\nBTC-dir and limit rows (all tickers):")
print(R[R.fam.str.startswith(("btc_dir","limit"))][["ticker","fam","par","dev_n","dev_bp","dev_t","chk_n","chk_bp","chk_t","flip_dev_bp","flip_chk_bp"]].round(1).to_string(index=False))
# pooled per family-param across tickers (dev/check)
def pooled(g):
    out={}
    for sp in ["dev","check"]:
        x=g[g.split==sp]["net"]
        out[sp+"_n"]=len(x); out[sp+"_bp"]=round(x.mean()*1e4,1) if len(x) else np.nan
        out[sp+"_t"]=round(x.mean()/x.std(ddof=1)*np.sqrt(len(x)),2) if len(x)>1 else np.nan
    return pd.Series(out)
P=T.groupby(["fam","par"]).apply(pooled).reset_index()
print("\nPooled across tickers, per family/params:")
print(P.to_string(index=False))
# per-year for selected rules
def yr(s,fam,par):
    g=T[(T.ticker==s)&(T.fam==fam)&(T.par==par)]
    y=g.groupby(g.date.dt.year).agg(n=("net","size"),bp=("net",lambda x: x.mean()*1e4),win=("net",lambda x:(x>0).mean()))
    return y.round(2)
for args in [("3825_T","btc_dir","|m|>=0.01"),("3350_T","btc_dir","|m|>=0.02"),("0434_HK","resid_fade","W=250,|z|>=0.5"),("0434_HK","intra_follow","|BTC 1h|>=0.0")]:
    print("\n",args); print(yr(*args).to_string())
