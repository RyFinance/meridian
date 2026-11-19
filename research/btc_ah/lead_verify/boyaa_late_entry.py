"""F1 tradability: the 09:30 open defines the signal, so enter LATER. Entry at the open of the first 60m bar starting >= 02:30 UTC (10:30 HKT); exit at the daily close. 2023-10-30..2026-08-10 (60m coverage)."""
import runpy, numpy as np, pandas as pd, io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    ns = runpy.run_path("research/btc_ah/lead_verify/boyaa_resid.py")
x, z, res = ns["x"], ns["z"], ns["res"]
raw = pd.read_parquet("research/btc_ah/asia/cache/0434_HK_1d.parquet")
h = pd.read_parquet("research/btc_ah/asia/cache/0434_HK_60m.parquet"); h = h[h.index <= "2026-08-10 23:59"]
h["d"] = h.index.normalize()
ent = h[h.index.time >= pd.Timestamp("02:30").time()].groupby("d").Open.first()
sel = (z <= -1.0) & (x.index >= "2023-10-30")
rows = []
for d in x.index[sel]:
    if d not in ent.index: continue
    rows.append(dict(d=d, at_open=np.log(raw.Close[d] / raw.Open[d]), at_1030=np.log(raw.Close[d] / ent[d]), at_1030_worst=np.log(raw.Close[d] / (ent[d] + 0.01))))
r = pd.DataFrame(rows).set_index("d") - 0.006
for c in r: s = r[c]; print(f"{c:8s} n {len(s)} mean {s.mean()*1e4:+.0f}bp t {s.mean()/s.std()*np.sqrt(len(s)):+.2f} win {(s>0).mean():.2f}")
print(r.groupby(r.index.year).mean().mul(1e4).round(0))
