import numpy as np, pandas as pd, pickle, warnings; warnings.filterwarnings("ignore")
exec(open("research/zb_itb/round5/rate_universe/an.py").read().split("UNI=[s for s")[0].split("D={s")[0]) if False else None
O="research/zb_itb/round5/rate_universe/"
D,net=pickle.load(open(O+"d.pkl","rb"))
two=set("HD LOW SHW PLD O XLRE ARKK ITB XHB AGNC NLY INVH AMH BLDR MAS POOL FNF SPY DHI LEN PHM TLT IWM MHK".split()); ten={"NAIL","REZ"}
cost=lambda s:(2 if s in two else 10 if s in ten else 5)/1e4
DEV=("2024-05-28","2025-06-30"); CHK=("2025-07-01","2026-10-16")
CL={"mortgage_orig":"RKT UWMC PFSI".split(),
"title_mi":"FNF FAF MTG RDN ESNT".split(),
"mREIT":"AGNC NLY".split(),
"small_builders":"MTH MHO CCS LGIH DFH".split(),
"large_builders":"DHI LEN PHM TOL KBH NVR".split(),
"all_builders":"MTH MHO CCS LGIH DFH DHI LEN PHM TOL KBH NVR".split(),
"bldg_products":"BLDR MAS OC TREX FBIN MHK SHW POOL LOW HD WHR".split(),
"HD_LOW_only":"HD LOW".split(),
"resi_REIT":"INVH AMH MAA ESS UDR CPT SUI ELS".split(),
"builders+prod+mort":"MTH MHO CCS LGIH DFH DHI LEN PHM TOL KBH NVR BLDR MAS OC TREX FBIN MHK SHW POOL LOW HD WHR RKT UWMC PFSI".split(),
"builders+mort":"MTH MHO CCS LGIH DFH DHI LEN PHM TOL KBH NVR RKT UWMC PFSI".split(),
"ITB":["ITB"],"XHB":["XHB"],"SPY":["SPY"]}
def st(x):
    x=x.dropna(); return len(x),x.mean()*1e4,x.mean()/x.std()*np.sqrt(len(x)),(x>0).mean(),x.mean()/x.std()*np.sqrt(252)
rows=[];B={}
for c,m in CL.items():
    for k in ["ZB","ZN","AGR"]:
        # basket net: average of per-name net on days when all names have signal
        X=pd.concat([net[(s,k)] for s in m],axis=1); b=X.mean(axis=1,skipna=True).where(X.notna().sum(axis=1)>=max(1,len(m)*0.7)); B[(c,k)]=b
        # flip: -g - cost = -(net) - 2*2cost
        avgc=np.mean([2*cost(s) for s in m]); fl=-(b)-2*avgc
        for nm,(a,z) in [("dev",DEV),("chk",CHK)]:
            n,mn,t,w,sh=st(b[a:z]); rows.append(dict(cl=c,sig=k,per=nm,N=len(m),n=n,mean=mn,t=t,win=w,sharpe=sh,flip=fl[a:z].mean()*1e4))
R=pd.DataFrame(rows); pd.set_option("display.width",250)
P=R.pivot(index=["cl","sig"],columns="per",values=["n","mean","t","win","sharpe","flip"]); P.columns=[a+"_"+b for a,b in P.columns]
print(P.reset_index()[["cl","sig","n_dev","mean_dev","t_dev","sharpe_dev","win_dev","n_chk","mean_chk","t_chk","sharpe_chk","win_chk","flip_chk"]].round(2).to_string(index=False))
R.to_csv(O+"clusters.csv",index=False)
# basket - ITB paired on check
print("\nbasket minus ITB (ZB), net bp/trade, paired t")
for c in CL:
    if c in("ITB",):continue
    for k in ["ZB","AGR"]:
        for nm,(a,z) in [("dev",DEV),("chk",CHK)]:
            d=(B[(c,k)]-B[("ITB",k)])[a:z].dropna(); print(c,k,nm,round(d.mean()*1e4,1),round(d.mean()/d.std()*np.sqrt(len(d)),2))
# SPY-hedged: need gross; hedge = subtract d*r_SPY, cost +4bp
print("\nSPY-hedged (beta1, extra 4bp) ZB, check")
spy=D["SPY"]
for c in ["ITB","XHB","mortgage_orig","all_builders","bldg_products","builders+prod+mort","builders+mort","title_mi"]:
    m=CL[c]; res={}
    for nm,(a,z) in [("dev",DEV),("chk",CHK)]:
        h=B[(c,"ZB")]-spy.ZB.where(spy.ZB!=0)*spy.r - 0.0004
        n,mn,t,w,sh=st(h[a:z]); res[nm]=(round(mn,1),round(t,2))
    print(c,res)
# agreement: ZB trades split by agree/disagree, for ITB and clusters (gross-ish net per trade)
print("\nagree vs disagree (ZB sign trade; net bp/trade, n, t)")
for c in ["ITB","XHB","mortgage_orig","all_builders","bldg_products","builders+prod+mort"]:
    m=CL[c]; out=[]
    for nm,(a,z) in [("dev",DEV),("chk",CHK)]:
        ag=pd.concat([D[s].ZB==D[s].ZN for s in m],axis=1).iloc[:,0]
        b=B[(c,"ZB")]; 
        for lab,mk in [("agree",ag),("disagree",~ag)]:
            x=b[a:z][mk.reindex(b[a:z].index).fillna(False)]; n,mn,t,_,_=st(x); out.append(f"{nm}-{lab}: n={n} {mn:.1f}bp t={t:.2f}")
    print(c,"|"," | ".join(out))
# unconditional beta check: mean ITB gross when disagree
