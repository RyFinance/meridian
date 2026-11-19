"""Test 5: crash exposure. Crash-declaration propagation, skew/drawdown, crisis windows, worst-case unmasking."""
from harness import *
import json
from scipy import stats as ss
base, res = run(return_res=True)
net = res["net"]["ret"]; net.index = pd.PeriodIndex(net.index.astype(str), freq="M")
m = json.load(open(REPO / "reports/cycle7_new_samples/runs/CARRY-FX__FX-EM/metrics.json"))
prop = dict(ledgered_p_crash=m["active"]["p"].get("crash"), bandwidth=m["active"]["p"].get("bandwidth_fraction"),
            n=m["active"]["n"], ci_primary_level=m["active"]["ci_level_primary"], ci95=m["active"]["ci_95"]["sharpe_ann"])
print("crash propagation:", prop)
def mdd(x):
    nav = (1 + x).cumprod(); return float((nav / nav.cummax() - 1).min())
desc = pd.DataFrame([dict(series=n_, skew=ss.skew(x.dropna()), exkurt=ss.kurtosis(x.dropna()), mdd=mdd(x.dropna()),
                          worst_month=float(x.min()), worst_month_at=str(x.idxmin())) for n_, x in [("active", base), ("book net", net)]])
print(desc.round(3).to_string(index=False))
W = [("Asian/Russian crisis", "1997-07", "1998-12"), ("GFC", "2008-08", "2009-03"), ("Taper tantrum", "2013-05", "2013-09"),
     ("CNY devaluation", "2015-08", "2015-09"), ("TRY/ARS 2018", "2018-04", "2018-09"), ("COVID", "2020-02", "2020-04"),
     ("RUB 2022", "2022-02", "2022-04")]
win = pd.DataFrame([dict(window=w, start=a, end=b, active_cum=float((1 + base.loc[a:b]).prod() - 1),
                         book_cum=float((1 + net.loc[a:b]).prod() - 1), months=len(base.loc[a:b])) for w, a, b in W])
print(win.round(4).to_string(index=False))
# worst-case unmasking: add the spot move of positions held into masked months to the BOOK (control unchanged)
h = pd.read_csv(REPO / "reports/cycle7_new_samples/diagnostics/carry_em_held_into_mask.csv")
adj = base.copy()
for _, r in h.iterrows():
    mm = pd.Period(r.month, "M")
    if mm in adj.index and pd.notna(r.missed_pnl_approx):
        adj.loc[mm] += r.missed_pnl_approx
rows = [summarize("5 worst-case unmask (held-into-mask spot moves booked)", adj),
        summarize("5 worst-case unmask | post-KMVP", adj, start=KMVP_CUT)]
print(pd.DataFrame(rows).round(3).to_string(index=False))
pd.concat([desc]).to_csv(OUT / "t5_distribution.csv", index=False); win.to_csv(OUT / "t5_crisis_windows.csv", index=False)
pd.DataFrame(rows).to_csv(OUT / "t5_unmask.csv", index=False); json.dump(prop, open(OUT / "t5_crash_propagation.json", "w"), indent=1, default=str)
