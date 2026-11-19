"""Dev-window grid over % OTM short-option specs (pct.py), multiprocess. Output: pct_grid.parquet.

Covers naked shorts (wing=None, return on Reg-T margin proxy) and defined-risk winged
shorts (margin = width - credit), safe/opposite/both sides, 0DTE-only and Mon+Fri,
entry timing, and |BTC off-hours move| filters. Dev data only (dev_days.pkl)."""
import itertools, pickle
from multiprocessing import Pool
from pathlib import Path
import pandas as pd
from research.mstr_btc_0dte.pct import Short, grid
H = Path(__file__).parent
DAYS = pickle.load(open(H / "dev_days.pkl", "rb"))

def specs():
    for side, otm, wing, em, mb, fo in itertools.product(
            ["safe", "opposite", "both"], [0.02, 0.03, 0.04, 0.06, 0.08, 0.12],
            [None, 0.04, 0.08, 0.16], [1, 5, 15], [0.0, 0.01, 0.02], [True, False]):
        yield Short(side=side, otm=otm, wing=wing, entry_min=em, min_btc=mb, fridays_only=fo)

def work(chunk):
    return grid(DAYS, chunk)

if __name__ == "__main__":
    sp = list(specs()); print(len(sp), "specs", flush=True)
    chunks = [sp[i:i + 24] for i in range(0, len(sp), 24)]
    with Pool(4) as p:
        out = pd.concat(p.map(work, chunks), ignore_index=True)
    out.to_parquet(H / "pct_grid.parquet"); print("done", out.shape)
