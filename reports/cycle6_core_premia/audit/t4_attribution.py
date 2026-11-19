"""Test 4: attribution & concentration: P&L and risk contribution by sleeve / asset class; FX concentration; best
year / best 12m / 2022 share; drop-one-sleeve and drop-best-year."""
from common import *
R, G = sleeves_and_gross()
tb = tbill_monthly()
bk, W = build_book(R, G, tb, weights_out=True)
out = {}
for win_name, win in [("post", POST), ("full", None)]:
    b = bk.loc[win:] if win else bk
    Wp = W.reindex(b.index).fillna(0.0)
    contrib = Wp * R.reindex(b.index)[Wp.columns].fillna(0.0)
    pnl = contrib.sum(); pnl["cash/financing"] = b.cash_adj.sum()
    C = contrib.cov() * 12                         # risk contribution: cov(contrib_i, book)/var(book)
    tot = contrib.sum(axis=1)
    rc = contrib.apply(lambda c: np.cov(c, tot)[0, 1]) / tot.var()
    t = pd.DataFrame({"pnl_sum": pnl, "pnl_share": pnl / pnl.sum(), "risk_share": rc, "mean_weight": Wp.mean()})
    t["asset"] = [ASSET.get(i, "cash") for i in t.index]
    out[win_name] = t
    print(f"== {win_name}"); print(t.round(3).to_string())
    print(t.groupby("asset")[["pnl_share", "risk_share", "mean_weight"]].sum().round(3).to_string())
    pd.concat(out).to_csv(OUT / "t4_contrib.csv")

# concentration on the post window
x = bk.excess.loc[POST:]
yr = x.groupby(x.index.year).apply(lambda s: (1 + s).prod() - 1)
r12 = (1 + x).rolling(12).apply(np.prod, raw=True) - 1
conc = dict(best_year=int(yr.idxmax()), best_year_ret=yr.max(), best_12m_end=str(r12.idxmax()), best_12m_ret=r12.max(),
            share_2022=x.loc["2022"].sum() / x.sum(), share_best_year=x[x.index.year == yr.idxmax()].sum() / x.sum(),
            top5pct_months_share=x.nlargest(max(1, int(round(0.05 * len(x))))).sum() / x.sum())
xb = x[x.index.year != yr.idxmax()]; conc["sharpe_ex_best_year"] = stats(xb)["sharpe"]
c = calib_ci(xb.to_numpy(), 0.90, seed=9); conc["ci90_ex_best_year"] = f"[{c[0]:.2f}, {c[1]:.2f}]"
x22 = x[x.index.year != 2022]; conc["sharpe_ex_2022"] = stats(x22)["sharpe"]
c = calib_ci(x22.to_numpy(), 0.90, seed=9); conc["ci90_ex_2022"] = f"[{c[0]:.2f}, {c[1]:.2f}]"
print(pd.Series(conc).to_string()); pd.Series(conc).to_csv(OUT / "t4_concentration.csv")

# drop-one-sleeve (rebuild) and drop all FX
rows = []
for drop in [None] + list(R.columns) + ["ALL FX"]:
    cols = [c for c in R.columns if c != drop and not (drop == "ALL FX" and ASSET.get(c) == "FX")]
    b = build_book(R[cols], G[cols], tb).excess.loc[POST:]
    c = calib_ci(b.to_numpy(), 0.90, seed=9); st = stats(b)
    rows.append(dict(dropped=drop or "none", sharpe_post=st["sharpe"], ci90_lo=c[0], ci90_hi=c[1],
                     excludes_zero=c[0] > 0, mean_ann=st["mean_ann"], vol_ann=st["vol_ann"]))
d = pd.DataFrame(rows); print(d.round(3).to_string()); d.to_csv(OUT / "t4_drop_one.csv", index=False)
