"""Test 7: costs. Per-side cost on traded notional (spec 3 bp) at 2x/3x and at institutional / retail EM spread
levels (see data/costs_reference.csv when available), plus a retail financing (tom-next) markup charged on gross
exposure. Book net AND active reported. SENSITIVITIES only."""
from harness import *
rows = []
for bp, label in [(3, "spec base 3bp"), (6, "2x (6bp)"), (9, "3x (9bp)"), (15, "institutional EM ~15bp"),
                  (30, "retail EM ~30bp"), (50, "retail EM wide ~50bp")]:
    a, res = run(fx_bp=bp, return_res=True)
    net = res["net"]["ret"]; net.index = a.index; g = res["net"]["gross_exposure"]; g.index = a.index
    to = res["net"]["turnover"].mean() * 12
    for fin in [0.0, 1.0, 2.0]:                       # financing markup pp/yr on gross notional (retail tom-next)
        nb = net - fin / 100 / 12 * g
        rec = dict(cost=label, bp_side=bp, fin_markup_pp=fin, turnover_ann=to,
                   book_sharpe_full=sharpe(nb), book_sharpe_post=sharpe(nb.loc[KMVP_CUT:]),
                   book_mean_post_pct=100 * nb.loc[KMVP_CUT:].mean() * 12)
        if fin == 0:
            s_full = summarize(label, a); s_post = summarize(label, a, start=KMVP_CUT)
            rec.update(active_sharpe_full=s_full["sharpe"], active_p_full=s_full["p_crash"], active_sharpe_post=s_post["sharpe"],
                       active_ci95_post=s_post["ci95"])
        rows.append(rec)
t = pd.DataFrame(rows); pd.set_option("display.width", 250); print(t.round(3).to_string(index=False))
t.to_csv(OUT / "t7_costs.csv", index=False)
