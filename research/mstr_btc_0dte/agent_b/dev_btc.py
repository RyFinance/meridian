"""Step 1 (DEV ONLY, 2017-08..2022-12): BTC within-off-hours momentum and drift."""
import sys
sys.path.insert(0, "/Users/rytty/CCP/quant_v7/research/mstr_btc_0dte/agent_b")
import numpy as np
import pandas as pd
from scipy import stats as ss
from common import OUT, btc

P = pd.read_parquet(OUT + "/panel.parquet")
print("NaN rows by year:", P[P.off.isna()].year.value_counts().sort_index().to_dict())
MODE = sys.argv[1] if len(sys.argv) > 1 else "dev"
A, B = {"dev": ("2017-08-18", "2022-12-31"), "val": ("2023-01-01", "2026-08-10")}[MODE]
DEV = P[(P.date >= A) & (P.date <= B)]

SPLITS = [("weeknight", "E20", "R20"), ("weeknight", "E04", "R04"),
          ("long", "E20", "R20"), ("long", "Esat", "Rsat"), ("long", "Esun", "Rsun"), ("long", "E04", "R04")]


def tstat(x):
    x = x.dropna()
    return x.mean() / x.std() * np.sqrt(len(x))


def mom(df, e, r, label=""):
    d = df[[e, r]].dropna()
    E, R = d[e], d[r]
    pr = E.corr(R); sp = ss.spearmanr(E, R)[0]
    nz = (E != 0) & (R != 0)
    hit = (np.sign(E[nz]) == np.sign(R[nz])).mean()
    b = np.polyfit(E, R, 1)[0]
    # sign-trade on BTC itself (gross): sign(E)*R
    st = np.sign(E) * R
    lo = R[E > 0]
    return dict(n=len(d), pearson=pr, spearman=sp, hit=hit, slope=b,
                signR_bp=st.mean() * 1e4, signR_t=tstat(st),
                R_ifEpos_bp=lo.mean() * 1e4, R_ifEpos_t=tstat(lo),
                R_ifEneg_bp=R[E < 0].mean() * 1e4, R_all_bp=R.mean() * 1e4, R_all_t=tstat(R))


lines = []
def out(s=""):
    print(s); lines.append(str(s))

pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
out(f"=== Momentum E->R, {MODE} {A}..{B} ===")
res = pd.DataFrame([dict(kind=k, E=e, R=r, **mom(DEV[DEV.kind == k], e, r)) for k, e, r in SPLITS])
out(res.round(3).to_string())

out("\n=== By year (pearson / hit / signR_bp / R_ifEpos_bp) ===")
rows = []
for k, e, r in SPLITS:
    for y, g in DEV[DEV.kind == k].groupby("year"):
        m = mom(g, e, r)
        rows.append(dict(split=f"{k}:{e}", year=y, n=m["n"], pearson=m["pearson"], hit=m["hit"],
                         signR_bp=m["signR_bp"], R_ifEpos_bp=m["R_ifEpos_bp"], R_all_bp=m["R_all_bp"]))
out(pd.DataFrame(rows).round(3).to_string())

out("\n=== Mean R by E decile (bp) ===")
for k, e, r in SPLITS:
    d = DEV[DEV.kind == k][[e, r]].dropna()
    q = pd.qcut(d[e], 10, labels=False)
    g = d.groupby(q)[r].agg(["mean", "std", "count"])
    g["t"] = g["mean"] / g["std"] * np.sqrt(g["count"])
    out(f"{k}:{e}->{r}: " + " ".join(f"{m*1e4:+.0f}({t:+.1f})" for m, t in zip(g["mean"], g["t"])))

# Robustness: drop |E| outliers (top 1%) and use rank-based
out("\n=== Robust: winsorized 1/99 pearson ===")
for k, e, r in SPLITS:
    d = DEV[DEV.kind == k][[e, r]].dropna()
    w = d.clip(d.quantile(0.01), d.quantile(0.99), axis=1)
    out(f"{k}:{e}->{r} winsor corr {w[e].corr(w[r]):+.3f}")

# Drift in R regardless of E, and by DOW
out("\n=== Drift: mean R by weekday of session date (weeknights), bp (t) ===")
for r in ["R20", "R04", "E20", "E04", "off"]:
    g = DEV[DEV.kind == "weeknight"].groupby("dow")[r]
    out(f"{r}: " + " ".join(f"d{dw}:{x.mean()*1e4:+.0f}({tstat(x):+.1f})" for dw, x in g))

# Hour-of-day drift of BTC (ET), every calendar day, dev
s = btc()
h = s[(s.index >= A) & (s.index <= B + " 23:59")]
h = h.resample("1h").last().dropna()
r1 = np.log(h).diff().dropna()
r1 = r1[(r1.index.to_series().diff() == pd.Timedelta("1h")).values]
idx = r1.index.tz_convert("America/New_York")
df = pd.DataFrame({"r": r1.values, "hr": idx.hour, "dow": idx.dayofweek, "yr": idx.year})
out(f"\n=== BTC hourly return by ET hour (bin start, return over [h,h+1)), all days, {MODE}: bp (t) ===")
g = df.groupby("hr").r
out(" ".join(f"{hr:02d}:{x.mean()*1e4:+.1f}({tstat(x):+.1f})" for hr, x in g))
out("Bonferroni 24 tests: |t|>3.0 needed.")
# block sums: US-overnight block (20:00->04:00) and pre-market block (04:00->09:30) per year
df["blk"] = np.select([df.hr.isin([20, 21, 22, 23, 0, 1, 2, 3]), df.hr.isin([4, 5, 6, 7, 8])],
                      ["20-04", "04-09"], "other")  # 04-09 = 04:00-09:00
out("\n=== Block sums per day by year (bp/day mean, t) ===")
daily = df.assign(d=idx.date).groupby(["d", "blk"]).r.sum().unstack()
daily["yr"] = pd.to_datetime(daily.index).year
for b in ["20-04", "04-09", "other"]:
    out(f"{b}: " + " ".join(f"{y}:{x.mean()*1e4:+.0f}({tstat(x):+.1f})" for y, x in daily.groupby("yr")[b]))
    out(f"   all: {daily[b].mean()*1e4:+.1f} bp/day t={tstat(daily[b]):+.2f}")

open(OUT + f"/{MODE}_btc.txt", "w").write("\n".join(lines))
