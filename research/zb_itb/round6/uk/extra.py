"""Extra checks: gap vs intraday move, and homebuilder-minus-FTMC differential on the basket."""
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).parent
src = (HERE / "analysis.py").read_text().split("def fname")[0]
ns = {"__file__": str(HERE / "analysis.py")}; exec(src, ns)
DEV, CHK, HB = ns["DEV"], ns["CHK"], ns["HB"]
R = pd.read_pickle(HERE / "panel.pkl")
R = R[(R.date >= DEV[0]) & (R.date <= CHK[1])]
out = []
for sig in ["ZB_LON", "ZN_LON", "ZB_US"]:
    for sym in HB + ["VMID.L", "IDX_FTMC"]:
        s = R[R.sym == sym].set_index("date")
        pass
# gap: 08:00 open vs previous session 16:30 close (prior row for same stock)
gap_rows = []
for sym in HB:
    s = R[R.sym == sym].set_index("date").sort_index()
    gap = np.log(s.entry / s.x1630.shift(1))
    mv = np.log(s.x1630 / s.entry)
    mv1 = np.log(s.x09 / s.entry)
    sig = s["sig_ZB_LON"]
    ok = sig.notna() & gap.notna() & mv.notna() & (sig != 0)
    gap_rows.append(dict(sym=sym, corr_sig_gap=np.corrcoef(sig[ok], gap[ok])[0, 1], corr_sig_intraday=np.corrcoef(sig[ok], mv[ok])[0, 1], corr_sig_1h=np.corrcoef(sig[ok], mv1[ok.reindex(mv1.index, fill_value=False)].reindex(sig[ok].index).fillna(0))[0, 1] if False else np.nan, n=int(ok.sum())))
print(pd.DataFrame(gap_rows).round(3).to_string(index=False))
T = pd.read_csv(HERE / "grid.csv")
for sig, ex in [("ZB_LON", "x1630"), ("ZN_LON", "x1d"), ("ZB_LON", "x1d")]:
    for sp in ["dev", "chk"]:
        b = T[(T.sig == sig) & (T.ex == ex) & (T.split == sp)].set_index("name")
        print(sig, ex, sp, "HB basket gross", round(b.loc["HB_BASKET", "gross_bp"], 1), "FTMC", round(b.loc["IDX_FTMC", "gross_bp"], 1),
              "VMID", round(b.loc["VMID.L", "gross_bp"], 1), "diff vs FTMC", round(b.loc["HB_BASKET", "gross_bp"] - b.loc["IDX_FTMC", "gross_bp"], 1))
