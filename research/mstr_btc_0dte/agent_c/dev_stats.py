"""DEVELOPMENT ONLY (2019-01..2022-12): per-name gap beta, predictive correlations, hit rates."""
import numpy as np, pandas as pd
from pathlib import Path
H = Path(__file__).parent
P = pd.read_parquet(H / "panel.parquet"); P = P[P.date <= "2022-12-31"]
def tstat_corr(r, n): return r * np.sqrt((n - 2) / (1 - r * r))
out = []
for tk, s in P.groupby("tk"):
    s2 = s.dropna(subset=["u"])
    if len(s) < 100: continue
    gb = np.polyfit(s.btc_off, s.gap, 1)[0]; cg = s.btc_off.corr(s.gap)
    c1 = s.btc_off.corr(s.oc); c2 = s2.u.corr(s2.oc)
    big = s[s.btc_off.abs() > 0.02]
    out.append(dict(tk=tk, n=len(s), n_u=len(s2), gap_beta=gb, corr_gap=cg, corr_off_oc=c1, t1=tstat_corr(c1, len(s)),
                    hit_off=(np.sign(s.btc_off) == np.sign(s.oc)).mean(), corr_u_oc=c2, t2=tstat_corr(c2, len(s2)),
                    hit_u=(np.sign(s2.u) == np.sign(s2.oc)).mean(),
                    n_big=len(big), hit_big=(np.sign(big.btc_off) == np.sign(big.oc)).mean(),
                    mean_oc_signed_big_bp=1e4 * (np.sign(big.btc_off) * big.oc).mean(),
                    corr_btcday_oc=s.btc_day.corr(s.oc)))
R = pd.DataFrame(out).set_index("tk").round(3); print(R.to_string()); R.to_csv(H / "dev_per_name.csv")
# pooled
s = P.dropna(subset=["z"]); print("\npooled dev: corr(btc_off,oc)=%.3f n=%d; corr(z,oc)=%.3f n=%d" % (P.btc_off.corr(P.oc), len(P), s.z.corr(s.oc), len(s)))
print("pooled z-decile -> mean oc bp"); s = s.assign(q=pd.qcut(s.z, 10, labels=False))
print(s.groupby("q").agg(z=("z", "mean"), oc_bp=("oc", lambda x: 1e4 * x.mean()), n=("oc", "size")).round(2).T.to_string())
s = P.assign(q=pd.qcut(P.btc_off, 10, labels=False))
print("pooled btc_off decile -> mean oc bp"); print(s.groupby("q").agg(off_bp=("btc_off", lambda x: 1e4*x.mean()), oc_bp=("oc", lambda x: 1e4 * x.mean()), n=("oc", "size")).round(1).T.to_string())
