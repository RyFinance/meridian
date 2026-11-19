"""Test 4 (cont.): OANDA Canada CFD route (financing = market swap +/- admin fee: TRY 4pp, CZK/HUF/THB/ZAR 2pp, others 1pp,
charged on both long and short notional), OANDA currency list, RUB dropped. SENSITIVITY only."""
from harness import *
D = Path(__file__).parent / "data"
br = pd.read_csv(D / "broker_fx_availability.csv")
oanda = ["FX_" + c for c in br.currency[br.oanda_canada.astype(str).str.startswith("Y")] if c != "RUB"]
FEE = {"TRY": 4, "CZK": 2, "HUF": 2, "THB": 2, "ZAR": 2}
_, data, _ = base_inputs(); ALL = list(data["daily"].columns)
rows = []
for bp in (3, 10, 30):
    a, r = run(drop=[c for c in ALL if c not in oanda], fx_bp=bp, return_res=True)
    net = r["net"]["ret"]; net.index = a.index
    W = r["W"]; W.index = pd.PeriodIndex(W.index.astype(str), freq="M"); H = W.shift(1).reindex(a.index).fillna(0)
    drag = sum(H[c].abs() * FEE.get(c[3:], 1) / 100 / 12 for c in H.columns)
    nf = net - drag
    rec = dict(route="OANDA CFD", ccys=",".join(c[3:] for c in oanda), bp_side=bp, n=len(a), first=str(a.index.min()),
               book_sharpe=sharpe(net), book_sharpe_post=sharpe(net.loc[KMVP_CUT:]), fin_drag_post_pct=100 * drag.loc[KMVP_CUT:].mean() * 12,
               book_fin_sharpe=sharpe(nf), book_fin_sharpe_post=sharpe(nf.loc[KMVP_CUT:]), book_fin_mean_post_pct=100 * nf.loc[KMVP_CUT:].mean() * 12)
    if bp == 10:
        s = summarize("oanda fin post", nf, start=KMVP_CUT); rec.update(book_fin_ci95_post=s["ci95"], book_fin_p_post=s["p_crash"])
        s = summarize("oanda active post", a, start=KMVP_CUT); rec.update(active_sharpe_post=s["sharpe"], active_p_post=s["p_crash"])
    rows.append(rec)
t = pd.DataFrame(rows); pd.set_option("display.width", 300); print(t.round(3).to_string(index=False)); t.to_csv(OUT / "t4b_oanda.csv", index=False)
# IBKR drag in the post-KMVP window only (from t4 logic) for the record
t4 = pd.read_csv(OUT / "t4_tradable.csv"); print(t4[["set", "bp_side", "book_sharpe_post", "book_ibkr_fin_sharpe_post", "book_ibkr_fin_mean_post_pct"]].to_string(index=False))
