import pickle
from dataclasses import asdict
from multiprocessing import Pool
import pandas as pd
from research.premium_wide.bt import Rule, load, run, stats, grid, H
DATA = None
def init():
    global DATA
    DATA = pickle.load(open(H / "mstr_data.pkl", "rb"))
def work(r):
    row = asdict(r)
    for st in (False, True):
        s = stats(run(DATA, Rule(**{**asdict(r), "stress": st}), "2020-08-11", "2023-12-31"))
        row.update({("stress_" if st else "base_") + k: v for k, v in s.items()})
    return row
if __name__ == "__main__":
    pickle.dump(load("MSTR"), open(H / "mstr_data.pkl", "wb"))
    rs = list(grid()); print(len(rs), "rules", flush=True)
    with Pool(8, initializer=init) as p:
        g = pd.DataFrame(p.map(work, rs))
    g = g.drop(columns=["stress"]); g.to_csv(H / "dev_grid.csv", index=False)
    pd.set_option("display.width", 250)
    ok = g[(g.base_n >= 20) & (g.base_mean > 0) & (g.stress_mean > 0)]
    print("rules with base&stress mean>0 (n>=20):", len(ok), "of", len(g))
    print(ok.sort_values("base_t", ascending=False).head(25).to_string(index=False))
    for c in ["kind", "dte", "otm", "wing", "tp", "ivf"]:
        print(c, g.groupby(c, dropna=False)[["base_mean", "stress_mean"]].mean().round(4).to_dict("index"))
