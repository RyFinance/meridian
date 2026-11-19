"""Test 3b (NDF profit in documented large-gap months), Test 4 (Canadian-retail tradable set + IBKR financing),
Test 8 (ETF vehicles). SENSITIVITIES / reports only."""
from harness import *
from research.cycle6.engine import panel
D = Path(__file__).parent / "data"
base, res = run(return_res=True)
_, data, cl = base_inputs()
Wt = res["W"]; rnet = panel.net_period_returns(data["daily"]); H = Wt.shift(1).reindex(rnet.index)
pnl = (H * rnet[H.columns]).fillna(0.0); pnl.index = pd.PeriodIndex(pnl.index.astype(str), freq="M"); pnl = pnl.loc["1988-02":]
tot = pnl.sum().sum()
# ---- 3b: documented large onshore/offshore gap episodes (>= ~1pp/yr or >=1% of spot per 3m), from opened sources only
EP = [("FX_INR", "1999-01", "2001-12", "BIS 2004: -4 to -10pp"), ("FX_INR", "2003-09", "2003-12", "BIS 2004: +4 to +10pp"),
      ("FX_KRW", "1998-11", "1999-03", "BIS 2004: 1.1-2.8pp"), ("FX_KRW", "2004-01", "2004-06", "BIS 2004: 0.75-1.44pp"),
      ("FX_IDR", "2001-01", "2001-06", "BIS 2004: large, brief"), ("FX_PHP", "2000-09", "2001-06", "BIS 2004: large"),
      ("FX_INR", "2008-09", "2009-07", "BIS 2014 T4: 1.17% of spot/3m"), ("FX_IDR", "2008-09", "2009-07", "BIS 2014 T4: 2.37%"),
      ("FX_PHP", "2008-09", "2009-07", "BIS 2014 T4: 1.62%"), ("FX_IDR", "2013-05", "2013-08", "BIS 2014 T4: 2.53%"),
      ("FX_IDR", "2020-03", "2020-06", "IMF WP/20/179: up to +/-50pp"), ("FX_INR", "2013-05", "2013-08", "IMF WP/20/179 (chart)"),
      ("FX_INR", "2020-03", "2020-06", "IMF WP/20/179 (chart)"), ("FX_PHP", "2020-03", "2020-06", "IMF WP/20/179 (chart)"),
      ("FX_BRL", "2006-07", "2014-12", "Du-Schreger: CIP-type gap mean 3.39pp"), ("FX_COP", "2005-06", "2014-12", "Du-Schreger: 1.59pp"),
      ("FX_PHP", "2005-03", "2014-12", "Du-Schreger: 1.42pp"), ("FX_IDR", "2005-04", "2014-12", "Du-Schreger: 1.02pp")]
rows = []
for c, a, b, src in EP:
    if c in pnl.columns:
        v = float(pnl.loc[a:b, c].sum()); rows.append(dict(ccy=c, start=a, end=b, source=src, pnl=v, share_of_total=v / tot))
ep = pd.DataFrame(rows); print(ep.round(4).to_string(index=False))
ndf = [c for c in ndf_ids() if c in pnl.columns]
print(f"NDF total P&L share {pnl[ndf].sum().sum() / tot:.3f}; in documented large-gap episodes {ep.pnl.sum() / tot:.3f} (overlapping windows may double count: dedup below)")
mask = pd.DataFrame(False, index=pnl.index, columns=pnl.columns)
for c, a, b, _ in EP:
    if c in mask.columns: mask.loc[a:b, c] = True
print(f"deduplicated episode P&L share: {pnl.where(mask).sum().sum() / tot:.3f}")
ep.to_csv(OUT / "t3b_ndf_episodes.csv", index=False)

# ---- 4: Canadian retail tradable set (IBKR Canada deliverable spot 'Y'), RUB dropped
br = pd.read_csv(D / "broker_fx_availability.csv"); ib_y = ["FX_" + c for c in br.currency[br.ibkr_canada_spot == "Y"]]
ALL = list(data["daily"].columns)
sets = {"4a IBKR-Y (incl BRL), no RUB": [c for c in ib_y if c != "FX_RUB"],
        "4b IBKR-Y excl BRL (no interest row), no RUB": [c for c in ib_y if c not in ("FX_RUB", "FX_BRL")]}
CREDIT = {"CZK": ("bm", 2), "DKK": ("bm", .5), "HUF": ("bm", 3), "ILS": ("flat", 0), "MXN": ("bm", 4), "PLN": ("bm", 2),
          "SGD": ("bm", 1), "TRY": ("flat", 5), "ZAR": ("bm", 1), "BRL": ("flat", 0)}
DEBIT = {"CZK": 3, "DKK": 3, "HUF": 5, "ILS": 5, "MXN": 3, "PLN": 3, "SGD": 1.5, "TRY": 5, "ZAR": 1.5, "BRL": 5}
fr = data["signal_inputs"]["fx_foreign_rate"].copy(); fr.index = pd.PeriodIndex(fr.index.astype(str), freq="M")
rows = []
for label, keep in sets.items():
    drop = [c for c in ALL if c not in keep]
    for bp in (3, 10, 30):
        a, r2 = run(drop=drop, fx_bp=bp, return_res=True)
        net = r2["net"]["ret"]; net.index = a.index
        W2 = r2["W"]; W2.index = pd.PeriodIndex(W2.index.astype(str), freq="M"); Hh = W2.shift(1).reindex(a.index).fillna(0)
        drag = pd.Series(0.0, index=a.index)
        for c in Hh.columns:
            ccy = c[3:]; rr = fr[c].reindex(a.index).ffill()
            kind, s = CREDIT[ccy]
            earned = (rr - s / 100).clip(lower=0) if kind == "bm" else pd.Series(s / 100, index=a.index)
            long_hair = (rr - earned).clip(lower=0)
            drag += (Hh[c].clip(lower=0) * long_hair + (-Hh[c]).clip(lower=0) * DEBIT[ccy] / 100) / 12
        netf = net - drag
        rec = dict(set=label, n_ccy=len(keep), bp_side=bp, n=len(a), first=str(a.index.min()),
                   book_sharpe=sharpe(net), book_sharpe_post=sharpe(net.loc[KMVP_CUT:]),
                   book_ibkr_fin_sharpe=sharpe(netf), book_ibkr_fin_sharpe_post=sharpe(netf.loc[KMVP_CUT:]),
                   book_ibkr_fin_mean_post_pct=100 * netf.loc[KMVP_CUT:].mean() * 12, fin_drag_pct_yr=100 * drag.mean() * 12)
        if bp == 3:
            s1 = summarize(label, a); s2 = summarize(label, a, start=KMVP_CUT)
            rec.update(active_sharpe=s1["sharpe"], active_p=s1["p_crash"], active_ci95=s1["ci95"], active_sharpe_post=s2["sharpe"],
                       active_p_post=s2["p_crash"], active_ci95_post=s2["ci95"])
            f1 = summarize(label + " ibkr-fin", netf, start=KMVP_CUT); rec["book_ibkr_fin_ci95_post"] = f1["ci95"]
        rows.append(rec)
t4 = pd.DataFrame(rows); pd.set_option("display.width", 300); print(t4.round(3).to_string(index=False)); t4.to_csv(OUT / "t4_tradable.csv", index=False)

# ---- 8: ETF vehicles
rf = pd.read_parquet(REPO / "data/cycle7/snapshot_store/versions/cycle7_fx_em_v1/view/eval/series/usd_rate_3m_monthly.parquet")
rf = rf.set_index("date")["value"]; rf.index = pd.PeriodIndex(pd.to_datetime(rf.index), freq="M"); rf = rf[~rf.index.duplicated(keep="last")] / 12
netb = res["net"]["ret"]; netb.index = base.index
rows = []
for tk in ["CEW", "EMLC", "LEMB", "EBND"]:
    px = pd.read_parquet(D / f"yahoo_{tk}_monthly.parquet").adjclose; px.index = pd.PeriodIndex(pd.to_datetime(px.index), freq="M")
    ex = (px.pct_change() - rf).dropna().loc[:"2026-08"]
    for w in [None, KMVP_CUT]:
        x = ex.loc[w:] if w else ex
        b = netb.reindex(x.index)
        rows.append(dict(vehicle=tk, window=w or f"inception {x.index.min()}", n=len(x), excess_sharpe=sharpe(x),
                         excess_mean_pct=100 * x.mean() * 12, vol_pct=100 * x.std() * np.sqrt(12), corr_with_book=x.corr(b),
                         book_sharpe_same_window=sharpe(b)))
t8 = pd.DataFrame(rows); print(t8.round(3).to_string(index=False)); t8.to_csv(OUT / "t8_vehicles.csv", index=False)
