"""Test 3 (robustness report, cannot create a pass): each component's own post-publication window, and a book whose
sleeves are held only from their own post-publication cutoff (covariance still uses earlier history)."""
from common import *
R, G = sleeves_and_gross()
tb = tbill_monthly()
rows = []
for c in SLEEVES:
    x = R[c].dropna().loc[CUTOFF[c]:]
    st = stats(x); ci = calib_ci(x.to_numpy(), 0.90, seed=3)
    rows.append(dict(series=c, own_cutoff=CUTOFF[c], n=st["n"], sharpe=st["sharpe"], ci90_lo=ci[0], ci90_hi=ci[1],
                     p_A4=calib_p(x.to_numpy(), crash=c in ("CARRY-FX", "XSMOM-FX"), bw=0.20, seed=4)))
bk = build_book(R, G, tb, include_from=CUTOFF)
for name, win in [("comp-post book, 2009-05+", "2009-05"), ("comp-post book, 2019-02+", POST)]:
    x = bk.excess.loc[win:]; st = stats(x); ci = calib_ci(x.to_numpy(), 0.90, seed=3)
    rows.append(dict(series=name, own_cutoff="per sleeve", n=st["n"], sharpe=st["sharpe"], ci90_lo=ci[0], ci90_hi=ci[1],
                     p_A4=calib_p(x.to_numpy(), crash=True, bw=0.20, seed=4)))
# same, ex-core
bx = build_book(R.drop(columns="CORE"), G.drop(columns="CORE"), tb, include_from=CUTOFF)
x = bx.excess.loc["2009-05":]; st = stats(x); ci = calib_ci(x.to_numpy(), 0.90, seed=3)
rows.append(dict(series="comp-post ex-core book, 2009-05+", own_cutoff="per sleeve", n=st["n"], sharpe=st["sharpe"],
                 ci90_lo=ci[0], ci90_hi=ci[1], p_A4=calib_p(x.to_numpy(), crash=True, bw=0.20, seed=4)))
o = pd.DataFrame(rows); print(o.round(3).to_string()); o.to_csv(OUT / "t3_postpub.csv", index=False)
