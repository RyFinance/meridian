"""Test 9: costs 1x/2x/3x at book level, FX forward-point bias, economic size (cash + excess).
Test 10: TFSA ETF long/flat variant vs a static exposure-matched ETF mix (report only)."""
from common import *
tb = tbill_monthly()
rows = []
for mult in [1, 2, 3]:
    R, G = sleeves_and_gross(cost_mult=mult)
    b = build_book(R, G, tb)
    for wn, w in [("post", POST), ("full", None)]:
        x = b.excess.loc[w:] if w else b.excess
        c = calib_ci(x.to_numpy(), 0.90, seed=20260946); st = stats(x)
        tot = (x + b.tb.loc[x.index]).dropna()
        rows.append(dict(costs=f"{mult}x", window=wn, sharpe=st["sharpe"], ci90_lo=c[0], ci90_hi=c[1], excess_pct_yr=100 * st["mean_ann"],
                         cash_plus_excess_pct_yr=100 * tot.mean() * 12, tbill_pct_yr=100 * b.tb.loc[x.index].mean() * 12,
                         vol_pct=100 * st["vol_ann"], cagr_total_pct=100 * ((1 + tot).prod() ** (12 / len(tot)) - 1)))
o = pd.DataFrame(rows); print(o.round(3).to_string()); o.to_csv(OUT / "t9_costs.csv", index=False)

# FX forward-point bias: synthetic carry (rate diff) minus forward-implied, %/yr per ccy (2015-01..2026-09)
fp = pd.read_csv(REPO / "reports/core_premia_20260925/rates_fx_eq/carry_input_error_fx_forward_points.csv").set_index("ccy")
bias = fp.mean_diff_pct_pa / 100
Rb, Gb = sleeves_and_gross(); _, W = build_book(Rb, Gb, tb, weights_out=True)
brow = []
for c in ["XSMOM-FX", "VAL-FX", "CARRY-FX", "SEAS-FX"]:
    w = pd.read_parquet(COMP / c / "weights.parquet")
    w["m"] = pd.PeriodIndex(w.signal_month.astype(str), freq="M") + 1; w["ccy"] = w.market_id.str[3:]
    w = w[w.m >= pd.Period("2015-01", "M")]
    per_month = w.assign(b=w.weight * w.ccy.map(bias)).groupby("m").b.sum()     # sleeve %/yr overstatement if diff = synth - fwd
    bw = W[c].reindex(per_month.index).fillna(0)
    brow.append(dict(sleeve=c, sleeve_bias_pct_yr=100 * per_month.mean(), book_bias_pct_yr=100 * (bw * per_month).mean()))
bb = pd.DataFrame(brow); print(bb.round(4).to_string()); print("total book bias %/yr:", round(bb.book_bias_pct_yr.sum(), 4))
bb.to_csv(OUT / "t9_fx_forward_bias.csv", index=False)

# ---- Test 10
T = REPO / "data/cycle6/snapshot_store/versions/cycle6_trade_v1/view/trade"
px = pd.read_parquet(T / "etf_adjclose_daily.parquet"); fx = pd.read_parquet(T / "usdcad_daily.parquet")
def wide(d):
    if "market_id" in d.columns:
        d = d.pivot(index="date", columns="market_id", values="value")
    else:
        d = d.set_index(d.columns[0])
    d.index = pd.to_datetime(d.index); return d.sort_index()
px, fx = wide(px), wide(fx).iloc[:, 0]
fs = px.groupby(px.index.to_period("M")).head(1)                     # first session each month
fs.index = fs.index.to_period("M"); r_usd = fs.shift(-1) / fs - 1
fxf = fx.groupby(fx.index.to_period("M")).head(1); fxf.index = fxf.index.to_period("M"); rfx = fxf.shift(-1) / fxf - 1
r_cad = r_usd.copy()
for c in r_cad.columns:
    if not c.endswith(".TO"):
        r_cad[c] = (1 + r_usd[c]) * (1 + rfx) - 1
V = pidx(pd.read_csv(REPO / "reports/cycle6_core_premia/variants/TRADE-ETF-LF/vehicle_targets.csv", index_col=0))
var = pidx(pd.read_csv(REPO / "reports/cycle6_core_premia/variants/TRADE-ETF-LF/series/TFSA_CAD_100000.csv", index_col=0))
out = []
for wn, w0 in [("post 2019-02+", POST), ("full 2002-08+", "2002-08")]:
    idx = var.loc[w0:].index
    wbar = V.reindex(idx).mean()                                     # static weights = variant's average target (ex post)
    rv = r_cad.reindex(idx)[wbar.index].fillna(0.0)
    static_ex = (rv * wbar).sum(1) - 0.15 * 0.0                      # withholding approximated below
    # TFSA withholding on US-listed distributions: 15% x trailing distribution yield (approx: 0.15 x 2%/yr on US ETFs held)
    us = [c for c in wbar.index if not c.endswith(".TO")]
    static_ex = static_ex - 0.15 * 0.02 / 12 * wbar[us].sum() - 0.0002 * wbar.sum() / 12   # + 2bp/yr rebalancing
    va = var.excess.loc[idx]
    d = va - static_ex
    c90 = calib_ci(d.to_numpy(), 0.90, seed=5)
    out.append(dict(window=wn, n=len(idx), static_gross=wbar.sum(), variant_sharpe=stats(va)["sharpe"],
                    static_sharpe=stats(static_ex)["sharpe"], diff_mean_pct_yr=100 * d.mean() * 12, diff_sharpe=stats(d)["sharpe"],
                    diff_ci90=f"[{c90[0]:.2f}, {c90[1]:.2f}]", p_diff_A4=calib_p(d.to_numpy(), bw=0.20, seed=6),
                    corr=va.corr(static_ex)))
    print(wn, "static weights:", wbar[wbar > 0.005].round(3).to_dict())
o10 = pd.DataFrame(out); print(o10.round(3).to_string()); o10.to_csv(OUT / "t10_variant_vs_static.csv", index=False)
