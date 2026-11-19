"""Test 2 (book level): independent A5 §E book vs builder book.csv, using builder sleeve series."""
from common import *
R, G = sleeves_and_gross()
tb = tbill_monthly()
mine = build_book(R, G, tb)
theirs = pidx(pd.read_csv(BOOKDIR / "book.csv", index_col=0))
j = mine.join(theirs[["method", "k", "gross", "excess"]], rsuffix="_b", how="outer")
d = (j.excess - j.excess_b)
rows = []
for name, sl in [("full", slice(None)), ("post", slice(POST, None))]:
    a, b = j.excess[sl], j.excess_b[sl]
    rows.append(dict(window=name, n_mine=a.notna().sum(), n_builder=b.notna().sum(), corr=a.corr(b),
                     max_abs_diff=float((a - b).abs().max()), sharpe_mine=stats(a)["sharpe"], sharpe_builder=stats(b)["sharpe"],
                     method_mismatch=int((j.method[sl] != j.method_b[sl]).sum())))
out = pd.DataFrame(rows); print(out.round(6).to_string())
out.to_csv(OUT / "t2_book_repro.csv", index=False)
j.to_csv(OUT / "t2_book_side_by_side.csv")
big = d.abs().sort_values(ascending=False).head(5); print(big)
