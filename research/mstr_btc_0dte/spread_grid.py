import itertools, pickle
from multiprocessing import Pool
from pathlib import Path
import pandas as pd
from research.mstr_btc_0dte.spreads import Spread, grid
H = Path(__file__).parent
DAYS = pickle.load(open(H / "dev_days.pkl", "rb"))
def specs():
    for ss, w, em, tp, sl, mb, fl, bo in itertools.product([1, 2, 3, 4, 5, 6], [1, 2, 3], [1, 5, 15, 30],
            [None, 0.5, 0.8], [None, 1.0, 2.0], [0.0, 0.01, 0.02], [False, True], [False, True]):
        if bo and fl:
            continue
        yield Spread(short_steps=ss, width=w, entry_min=em, tp=tp, sl=sl, min_btc=mb, flip=fl, both=bo)
def work(c): return grid(DAYS, c)
if __name__ == "__main__":
    sp = list(specs()); print(len(sp), flush=True)
    with Pool(8) as p:
        out = pd.concat(p.map(work, [sp[i:i + 30] for i in range(0, len(sp), 30)]), ignore_index=True)
    out.to_parquet(H / "spread_grid.parquet"); print("done", out.shape)
