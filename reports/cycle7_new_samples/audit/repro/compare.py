import pandas as pd, numpy as np, sys
R="/Users/rytty/CCP/quant_v7/reports/cycle7_new_samples/runs/CARRY-FX__FX-EM"
drift=sys.argv[1]
me=pd.read_csv(f"/Users/rytty/CCP/quant_v7/reports/cycle7_new_samples/audit/repro/repro_series_{drift}.csv").set_index("month")
net=pd.read_csv(f"{R}/net.csv").set_index("month"); ctl=pd.read_csv(f"{R}/control.csv").set_index("month"); act=pd.read_csv(f"{R}/active.csv").set_index("month"); gr=pd.read_csv(f"{R}/gross.csv").set_index("month")
print("mine months",len(me),me.index[0],me.index[-1],"builder",len(net),net.index[0],net.index[-1])
print("only mine",sorted(set(me.index)-set(net.index)),"only builder",sorted(set(net.index)-set(me.index)))
c=me.index.intersection(net.index)
for name,a,b in [("net",me.net,net.ret),("ret_before_cost",me.ret_before_cost,net.ret_before_cost),("cost",me.cost,net.cost),("turnover",me.turnover,net.turnover),("n_held",me.n_held,net.n_held),("unpriced",me.unpriced,net.unpriced),("gross",me.gross,gr.ret),("control",me.control,ctl.net),("active",me.active,act.active)]:
    a=a[c];b=b[c];d=(a-b).abs()
    print(f"{name:16s} corr={np.corrcoef(a,b)[0,1]:.8f} maxabs={d.max():.3e} at {d.idxmax()} n>1e-6={(d>1e-6).sum()}")
def sh(x): return x.mean()*12/(x.std(ddof=1)*np.sqrt(12))
print("Sharpe active mine",sh(me.active[c]),"builder",sh(act.active[c]))
