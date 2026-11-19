import pandas as pd, numpy as np, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from analyze import stats
O = Path(__file__).parent
pd.set_option("display.width", 220); pd.set_option("display.max_rows", 500)
TR = pd.read_parquet(O / "trades_daily.parquet")
R = pd.read_csv(O / "results_daily.csv")
C = R[R.part=="check"].set_index(["rule","inst"])
print("check t<-2 variants:"); print(C[C.t < -2][["n","mean_bp","t"]].round(2).to_string())
print("check t>2 variants:"); print(C[C.t > 2][["n","mean_bp","t"]].round(2).to_string())
TOP = [("D_GAP_k1.0","BOIL"),("D_GAP_k1.0","UNG"),("D_GAP_k2.0","BNO")]
rows=[]
for rule, ins in TOP:
    for kind in ["follow","flip"]:
        g = TR[(TR.rule==rule)&(TR.inst==ins)&(TR.kind==kind)]
        for part, gg in [("dev",g[g.dev]),("check",g[~g.dev])]:
            s = stats(gg,"net"); py = s.pop("per_year")
            gross = gg["gross"].mean()*1e4 if len(gg) else np.nan
            rows.append(dict(sel=f"{rule} {ins} {kind} {part}", n=s["n"], win=round(s.get("win",np.nan),3), gross_bp=round(gross,1),
                             net_bp=round(s.get("mean_bp",np.nan),1), t=round(s.get("t",np.nan),2), avg_win=round(s.get("avg_win_bp",np.nan),0), avg_loss=round(s.get("avg_loss_bp",np.nan),0), per_year=py))
for r in rows: print(r)
# pooled daily k=0 follow vs flip (gross and net), GAP and OD
for rule in ["D_GAP_k0.0","D_OD_k0.0"]:
    for kind in ["follow","flip"]:
        g = TR[(TR.rule==rule)&(TR.kind==kind)]
        for part, gg in [("dev",g[g.dev]),("check",g[~g.dev])]:
            print(rule, kind, part, "n",len(gg), "gross_bp", round(gg.gross.mean()*1e4,2), "net_bp", round(gg.net.mean()*1e4,2),
                  "t_net", round(gg.net.mean()/(gg.net.std()/np.sqrt(len(gg))),2))
