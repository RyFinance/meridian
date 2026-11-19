# post-hoc diagnostics for the one combo that beat baseline (Ridge-reg skip pred<0). Run: PYTHONPATH=. .venv/bin/python research/zb_itb/ml_filter/diag.py
import sys; sys.path.insert(0,'research/zb_itb/ml_filter')
import walkforward as W, pandas as pd, numpy as np
O=W.T[W.T.index>=W.months[0].start_time]; net=O.net
w,p,mdl=W.run("Ridge-reg skip pred<0"); sk=O[w==0]
print(len(sk),"skipped; postholiday among them:",int(sk.postholiday.sum()),"net sum bp",round(sk.net_bp.sum()),"win",round((sk.net_bp>0).mean(),2))
print("OOS postholiday trades",int(O.postholiday.sum()),"net sum bp",round(O[O.postholiday==1].net_bp.sum()),"| in first training window",int(W.T[W.T.index<W.months[0].start_time].postholiday.sum()))
print("skip-all-postholiday:",{k:round(v,2) for k,v in W.metrics((O.postholiday==0).astype(float),net).items()})
W.FEATS=[f for f in W.FEATS if f!='postholiday']; w3,_,_=W.run("Ridge-reg skip pred<0"); print("ridge without postholiday feature:",{k:round(v,2) for k,v in W.metrics(w3,net).items()})
h=len(O)//2
for nm,sl in (("H1",slice(0,h)),("H2",slice(h,None))):
    print(nm,"base",{k:round(v,2) for k,v in W.metrics(pd.Series(1.0,index=O.index[sl]),net.iloc[sl]).items() if k in('win','total_bp','sharpe')},"ridge",{k:round(v,2) for k,v in W.metrics(w.iloc[sl],net.iloc[sl]).items() if k in('win','total_bp','sharpe','n')})
