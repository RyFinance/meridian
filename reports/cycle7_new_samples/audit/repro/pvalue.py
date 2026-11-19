import sys, json, numpy as np, pandas as pd
sys.path.insert(0, "/Users/rytty/CCP/quant_v7")
from research.amendment4.calib import calibrated_pvalues
def sharpe(x): x=np.asarray(x); return x.mean()*12/(x.std(ddof=1)*np.sqrt(12))
def p(x, seed=20260939):
    r = calibrated_pvalues(np.asarray(x,float)[None,:], B=9999, seed=seed, full=True, crash=(0.2/12, -6.0), bandwidth_fraction=0.10)
    return float(r["p"][0]), float(r["t"][0]), int(r["L"])
if __name__ == "__main__":
    f = sys.argv[1]; col = sys.argv[2]
    x = pd.read_csv(f)[col].to_numpy()
    print(json.dumps({"file": f, "n": len(x), "sharpe": sharpe(x), "p_t_L": p(x)}))
