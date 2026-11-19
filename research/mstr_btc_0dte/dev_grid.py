"""Dev-window grid over rule parameters (multiprocess). Output: dev_grid.parquet."""
import itertools, pickle
from multiprocessing import Pool
from pathlib import Path
import pandas as pd
from research.mstr_btc_0dte.engine import Rule, grid
H = Path(__file__).parent
DAYS = pickle.load(open(H / "dev_days.pkl", "rb"))

def rules():
    for side, ss, em, cf, tp, sl, st, mb in itertools.product(
            ["buy"], [-3, -2, -1, 0, 1, 2], [1, 5, 15, 30], [0.0, 0.003, 0.008], [0.0, 0.1, 0.2, 0.4, None],
            [None, 0.1, 0.2, 0.35], [30, 60, 120, 390], [0.0, 0.02]):
        if tp is None and sl is None and st < 390:
            pass
        yield Rule(side=side, strike_steps=ss, entry_min=em, confirm=cf, tp=tp, sl=sl, stop_min=st, min_btc=mb)
    for ss, em, tp, sl, st, mb in itertools.product([1, 2, 3, 4], [1, 5, 15], [0.5, 0.8, None], [1.0, 2.0, None],
                                                    [60, 390], [0.0, 0.02]):
        yield Rule(side="sell", strike_steps=ss, entry_min=em, tp=tp, sl=sl, stop_min=st, min_btc=mb)

def work(chunk):
    return grid(DAYS, chunk)

if __name__ == "__main__":
    rs = list(rules()); print(len(rs), "rules", flush=True)
    chunks = [rs[i:i + 40] for i in range(0, len(rs), 40)]
    with Pool(8) as p:
        out = pd.concat(p.map(work, chunks), ignore_index=True)
    out.to_parquet(H / "dev_grid.parquet"); print("done", out.shape)
