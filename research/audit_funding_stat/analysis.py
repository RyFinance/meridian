"""Statistical/economic adversarial audit of crypto_funding_xs corrected DEV (2020-2022 only; lock-safe).
PYTHONPATH=. .venv/bin/python -m research.audit_funding_stat.analysis"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

from research.audit_funding_stat.lockpanel import OUT, DEV, cached
from research.certify import guards as G
from research.crypto_funding_xs import core as c
from research.struct_common import centred_block_p

ANN = 365
END = pd.Timestamp("2022-12-31")


def sr(x):
    x = pd.Series(x).dropna()
    return float(x.mean() / x.std(ddof=1) * np.sqrt(ANN)) if len(x) > 2 and x.std() > 0 else float("nan")


def universe(P, FIRST):
    O, C, V, SIG = P["O"], P["C"], P["V"], P["SIG"]
    days = pd.date_range(*DEV, freq="D")
    cols = [s for s in O.columns if s in FIRST]
    medvol = V[cols].shift(1).rolling(c.VOL_LOOKBACK, min_periods=c.VOL_LOOKBACK // 2).median().reindex(days)
    first = pd.Series({s: FIRST[s] for s in cols})
    hist_ok = pd.DataFrame(((days.values[:, None] - first.values[None, :]) >= np.timedelta64(c.MIN_HIST, "D")),
                           index=days, columns=cols)
    elig = hist_ok & C[cols].shift(1).reindex(days).notna() & SIG[cols].reindex(days).notna() & medvol.notna()
    univ = medvol.where(elig).rank(axis=1, ascending=False, method="first") <= c.TOP_N
    return univ, medvol


def qls(score, univ, long_high=True):
    """+0.5/-0.5 quintile long-short on `score` within univ (same k rule as the frozen book)."""
    s = score.where(univ)
    n = s.notna().sum(axis=1)
    r = s.rank(axis=1, method="first")
    k = np.floor(c.Q * n).clip(lower=1)
    hi = r.gt(n - k, axis=0) & s.notna()
    lo = r.le(k, axis=0)
    W = hi.mul(0.5 / k, axis=0) - lo.mul(0.5 / k, axis=0)
    return W if long_high else -W


def hac(y, X, lag=10):
    X = sm.add_constant(X)
    m = sm.OLS(y, X, missing="drop").fit(cov_type="HAC", cov_kwds={"maxlags": lag})
    return {"alpha_ann": float(m.params.iloc[0] * ANN), "alpha_t": float(m.tvalues.iloc[0]), "r2": float(m.rsquared),
            "betas": {k: float(v) for k, v in m.params.iloc[1:].items()},
            "t": {k: float(v) for k, v in m.tvalues.iloc[1:].items()}, "n": int(m.nobs)}


def main():
    P, FIRST, W = cached()
    days = W.index
    live = W.notna().all(axis=1)
    Wf = W.fillna(0.0)
    O, C, F, V = (P[k].reindex(days) for k in ("O", "C", "FUND", "V"))
    R = (C / O - 1)
    S = {k: c.returns(P, W, k) for k in c.COSTS}
    b = S["base"]
    idx = b.index
    res = {"n_days": len(b), "first_day": str(idx[0].date()), "last_day": str(idx[-1].date())}
    assert idx.max() <= END

    # ---------------- distribution / dependence
    x = b.to_numpy()
    acf = sm.tsa.acf(x, nlags=10, fft=True)
    lb = sm.stats.acorr_ljungbox(x, lags=[5, 10, 21], return_df=True)
    acf2 = sm.tsa.acf(x ** 2, nlags=5, fft=True)
    # long-run variance ratio (Newey-West, Bartlett, lag 21)
    xc = x - x.mean(); n = len(x); L = 21
    lrv = xc @ xc / n + 2 * sum((1 - l / (L + 1)) * (xc[l:] @ xc[:-l]) / n for l in range(1, L + 1))
    kappa2 = float(lrv / (xc @ xc / n))
    res["distribution"] = {"skew": float(stats.skew(x)), "excess_kurt": float(stats.kurtosis(x)),
                           "acf1_5": [float(a) for a in acf[1:6]], "acf_sq_1_5": [float(a) for a in acf2[1:6]],
                           "ljungbox_p": {int(k): float(v) for k, v in lb["lb_pvalue"].items()},
                           "kappa2_NW21": kappa2, "daily_vol": float(x.std(ddof=1)),
                           "worst_days": {str(d.date()): float(v) for d, v in b.nsmallest(5).items()},
                           "best_days": {str(d.date()): float(v) for d, v in b.nlargest(5).items()},
                           "sharpe_iid_se": float(np.sqrt((1 + 0.5 * sr(b) ** 2 / ANN) / (n / ANN))),
                           "t_iid": float(x.mean() / x.std(ddof=1) * np.sqrt(n)),
                           "t_hac21": float(x.mean() / np.sqrt(lrv / n))}

    # ---------------- concentration
    tot = b.sum()
    def top_share(g, q=0.05):
        k = max(1, int(np.ceil(q * len(g))))
        return float(g.sort_values(ascending=False).iloc[:k].sum() / tot)
    wk = b.groupby(pd.Grouper(freq="W")).sum()
    mo = b.groupby(b.index.to_period("M")).sum()
    qt = b.groupby(b.index.to_period("Q")).sum()
    conc = {"total_sum": float(tot), "top5pct_days_share": top_share(b), "top1pct_days_share": top_share(b, 0.01),
            "top5pct_weeks_share": top_share(wk), "top10pct_weeks_share": top_share(wk, 0.10),
            "top5pct_months_share": top_share(mo), "n_weeks": len(wk), "n_months": len(mo),
            "pct_days_pos": float((b > 0).mean()), "pct_weeks_pos": float((wk > 0).mean()),
            "pct_months_pos": float((mo > 0).mean())}
    # drop top-k days
    for k in (5, 10, 20):
        bb = b.drop(b.nlargest(k).index)
        conc[f"sharpe_drop_top{k}_days"] = sr(bb)
        conc[f"p_drop_top{k}_days"] = centred_block_p(bb.to_numpy(), 21, 5000, 20260925)
    loqo = {}
    for q in qt.index:
        bb = b[b.index.to_period("Q") != q]
        loqo[str(q)] = {"sharpe": sr(bb), "q_sum": float(qt[q]), "q_sharpe": sr(b[b.index.to_period("Q") == q])}
    conc["by_quarter"] = loqo
    conc["loqo_min_sharpe"] = min(v["sharpe"] for v in loqo.values())
    lomo = {str(m): sr(b[b.index.to_period("M") != m]) for m in mo.index}
    conc["lomo_min_sharpe"] = float(min(lomo.values())); conc["lomo_min_month"] = min(lomo, key=lomo.get)
    conc["monthly"] = {str(k): float(v) for k, v in mo.items()}
    # leave-one-year-out
    conc["loyo"] = {}
    for y in (2020, 2021, 2022):
        bb = b[b.index.year != y]
        conc["loyo"][y] = {"sharpe": sr(bb), "p": centred_block_p(bb.to_numpy(), 21, 5000, 20260925),
                           "year_sharpe": sr(b[b.index.year == y]), "year_sum": float(b[b.index.year == y].sum()),
                           "year_days": int((b.index.year == y).sum()),
                           "year_p": centred_block_p(b[b.index.year == y].to_numpy(), 21, 5000, 20260925)}
    res["concentration"] = conc

    # ---------------- regimes
    btc = R["BTCUSDT"].reindex(idx)
    univ, medvol = universe(P, FIRST)
    mkt = R.where(univ).mean(axis=1).reindex(idx)
    nuniv = univ.sum(axis=1).reindex(idx)
    regimes = {
        "A 2020-07-26..2020-10-30 (days ADDED by the data fix; universe 25-~40)": ("2020-07-26", "2020-10-30"),
        "B 2020-11..2020-12 (BTC breakout)": ("2020-11-01", "2020-12-31"),
        "C 2021-01..2021-05-18 (leverage boom / alt mania I)": ("2021-01-01", "2021-05-18"),
        "D 2021-05-19..2021-07-31 (May-19 crash + summer)": ("2021-05-19", "2021-07-31"),
        "E 2021-08..2021-11 (alt mania II, peak)": ("2021-08-01", "2021-11-30"),
        "F 2021-12..2022-04 (topping)": ("2021-12-01", "2022-04-30"),
        "G 2022-05..2022-06 (LUNA / 3AC)": ("2022-05-01", "2022-06-30"),
        "H 2022-07..2022-10": ("2022-07-01", "2022-10-31"),
        "I 2022-11..2022-12 (FTX)": ("2022-11-01", "2022-12-31")}
    reg = {}
    for k, (a, z) in regimes.items():
        bb = b.loc[a:z]
        reg[k] = {"days": len(bb), "sum": float(bb.sum()), "ann_mean": float(bb.mean() * ANN), "sharpe": sr(bb),
                  "mean_universe_n": float(nuniv.loc[a:z].mean()), "btc_sum": float(btc.loc[a:z].sum()),
                  "mkt_sum": float(mkt.loc[a:z].sum())}
    res["regimes"] = reg
    res["covid_crash_in_sample"] = "NO: first live day is 2020-07-26 (universe < 25 before), March 2020 is not in the series"
    # state dependence
    btc30 = C["BTCUSDT"].reindex(idx).shift(1) / C["BTCUSDT"].reindex(idx).shift(31) - 1
    mk30 = mkt.rolling(30).sum().shift(1)
    res["state"] = {"sharpe_btc30_up": sr(b[btc30 > 0]), "sharpe_btc30_down": sr(b[btc30 <= 0]),
                    "sharpe_mkt30_up": sr(b[mk30 > 0]), "sharpe_mkt30_down": sr(b[mk30 <= 0]),
                    "sharpe_universe_lt40": sr(b[nuniv < 40]), "days_universe_lt40": int((nuniv < 40).sum()),
                    "sharpe_universe_ge60": sr(b[nuniv >= 60]), "days_universe_ge60": int((nuniv >= 60).sum()),
                    "sharpe_universe_ge100": sr(b[nuniv >= 100]), "days_universe_ge100": int((nuniv >= 100).sum())}
    # signal dispersion
    sig = P["SIG"].reindex(days).where(univ)
    res["state"]["signal_xs_sd_bp_by_year"] = {int(y): float(g.mean() * 1e4) for y, g in sig.std(axis=1).groupby(sig.index.year)}
    # ---------------- as-run vs corrected
    a = pd.read_csv(c.ROOT / "reports/crypto_funding_xs/dev_daily.csv", index_col=0, parse_dates=True)["base"]
    ov = a.index.intersection(idx)
    extra = idx.difference(a.index)
    res["asrun_vs_corrected"] = {"overlap_days": len(ov), "corr_overlap": float(np.corrcoef(a[ov], b[ov])[0, 1]),
                                 "sharpe_asrun_overlap": sr(a[ov]), "sharpe_corrected_overlap": sr(b[ov]),
                                 "p_corrected_overlap_only": centred_block_p(b[ov].to_numpy(), 21, 5000, 20260925),
                                 "extra_days": len(extra), "extra_first": str(extra.min().date()),
                                 "extra_last": str(extra.max().date()), "extra_sharpe": sr(b[extra]),
                                 "extra_sum": float(b[extra].sum()), "extra_share_of_total": float(b[extra].sum() / tot),
                                 "mean_universe_on_extra": float(nuniv[extra].mean()),
                                 "mean_names_per_leg_extra": float((Wf.loc[extra] > 0).sum(axis=1).mean())}

    # ---------------- decomposition & factors
    price = (Wf * R.fillna(0)).sum(axis=1)[live]
    fund = -(Wf * F.fillna(0)).sum(axis=1)[live]
    Rp = R.where(univ)
    Cl = C
    ret7 = (Cl.shift(1) / Cl.shift(8) - 1).where(univ)
    ret30 = (Cl.shift(1) / Cl.shift(31) - 1).where(univ)
    ret1 = (Cl.shift(1) / O.shift(1) - 1).where(univ)
    dret = (C / C.shift(1) - 1)
    vol30 = dret.shift(1).rolling(30, min_periods=20).std().where(univ)
    def fret(Wx):
        return (Wx.fillna(0) * R.fillna(0)).sum(axis=1).reindex(idx)
    fac = pd.DataFrame({
        "MKT_ew": mkt, "BTC": btc,
        "SMB_vol": fret(qls(-medvol, univ)),            # long small (low volume) minus big
        "MOM7": fret(qls(ret7, univ)), "MOM30": fret(qls(ret30, univ)),
        "REV1": fret(qls(-ret1, univ)),                 # long yesterday's losers
        "LOWVOL": fret(qls(-vol30, univ))}, index=idx)
    fac["MKT_ew"] = fac["MKT_ew"].fillna(0)
    res["factor_stats"] = {k: {"sharpe": sr(v), "ann_mean": float(v.mean() * ANN), "corr_base": float(v.corr(b)),
                               "corr_price_leg": float(v.corr(price))} for k, v in fac.items()}
    reg = {}
    for name, y in {"base": b, "price_leg": price, "funding_leg": fund}.items():
        reg[name] = {"mkt_btc": hac(y, fac[["MKT_ew", "BTC"]]), "all": hac(y, fac)}
    res["factor_regressions"] = reg
    # cross-sectional rank correlation of funding signal with past returns
    def xs_rankcorr(A, B):
        ra, rb = A.rank(axis=1), B.rank(axis=1)
        return ra.corrwith(rb, axis=1)
    s_live = sig.loc[idx]
    res["signal_vs_past_returns_rankcorr_mean"] = {
        "ret1": float(xs_rankcorr(s_live, ret1.loc[idx]).mean()), "ret7": float(xs_rankcorr(s_live, ret7.loc[idx]).mean()),
        "ret30": float(xs_rankcorr(s_live, ret30.loc[idx]).mean()), "vol30": float(xs_rankcorr(s_live, vol30.loc[idx]).mean()),
        "log_medvol": float(xs_rankcorr(s_live, np.log(medvol).loc[idx]).mean())}
    # diagnostic (NOT a re-spec): residualise the signal on ret7, ret30, vol30 each day, re-sort
    def resid_signal(Y, Xs):
        out = pd.DataFrame(np.nan, index=Y.index, columns=Y.columns)
        for t in Y.index:
            y = Y.loc[t]; X = pd.concat([x.loc[t] for x in Xs], axis=1, keys=range(len(Xs)))
            ok = y.notna() & X.notna().all(axis=1)
            if ok.sum() < 25:
                continue
            Xr = np.column_stack([np.ones(ok.sum())] + [stats.rankdata(X.loc[ok, j].to_numpy()) for j in X.columns])
            yr = stats.rankdata(y[ok])
            beta = np.linalg.lstsq(Xr, yr, rcond=None)[0]
            out.loc[t, ok[ok].index] = yr - Xr @ beta
        return out
    rs = resid_signal(s_live, [ret7.loc[idx], ret30.loc[idx], vol30.loc[idx]])
    Wr = -qls(rs, rs.notna())   # long LOW residual funding
    turn = Wr.fillna(0).diff().abs().sum(axis=1)
    pnl_r = (Wr.fillna(0) * R.reindex(idx).fillna(0)).sum(axis=1) - (Wr.fillna(0) * F.reindex(idx).fillna(0)).sum(axis=1) - turn * 7e-4
    res["residual_signal_book"] = {"sharpe_base": sr(pnl_r.iloc[1:]), "ann_mean": float(pnl_r.iloc[1:].mean() * ANN),
                                   "p": centred_block_p(pnl_r.iloc[1:].to_numpy(), 21, 5000, 20260925),
                                   "corr_with_frozen": float(pnl_r.corr(b)),
                                   "note": "diagnostic only: funding rank residualised on ranks of ret7, ret30, vol30"}
    # price-leg vs reversal: price leg alpha after MOM/REV/VOL/SIZE
    res["decomposition"] = {"price_ann": float(price.mean() * ANN), "funding_ann": float(fund.mean() * ANN),
                            "cost_ann": float((S["gross"] - b).mean() * ANN), "price_sharpe": sr(price),
                            "funding_sharpe": sr(fund)}
    # leg split
    Wl, Ws = Wf.clip(lower=0), Wf.clip(upper=0)
    long_leg = ((Wl * R.fillna(0)).sum(axis=1) - (Wl * F.fillna(0)).sum(axis=1))[live]
    short_leg = ((Ws * R.fillna(0)).sum(axis=1) - (Ws * F.fillna(0)).sum(axis=1))[live]
    res["legs"] = {"long_ann": float(long_leg.mean() * ANN), "short_ann": float(short_leg.mean() * ANN),
                   "long_sharpe": sr(long_leg), "short_sharpe": sr(short_leg),
                   "long_minus_half_mkt_ann": float((long_leg - 0.5 * mkt).mean() * ANN),
                   "short_plus_half_mkt_ann": float((short_leg + 0.5 * mkt).mean() * ANN),
                   "short_leg_worst_days": {str(d.date()): float(v) for d, v in short_leg.nsmallest(5).items()}}

    # ---------------- per-asset P&L (G4)
    cost_i = Wf.diff().abs() * 7e-4
    cost_i.iloc[0] = Wf.iloc[0].abs() * 7e-4
    A = (Wf * R.fillna(0) - Wf * F.fillna(0) - cost_i)[live]
    A = A.loc[:, (A != 0).any()]
    tots = A.sum().sort_values()
    res["per_asset"] = {"n_assets_traded": int(A.shape[1]), "top10": {k: float(v) for k, v in tots.tail(10).items()},
                        "bottom5": {k: float(v) for k, v in tots.head(5).items()},
                        "top10_share": float(tots.tail(10).sum() / tots.sum()),
                        "sharpe_ex_top10_assets": sr(A.drop(columns=tots.tail(10).index).sum(axis=1))}

    # ---------------- capacity & costs
    held = Wf != 0
    mv = medvol.reindex(days)
    cap = {}
    for pct in (0.01, 0.05, 0.10):
        aum = (pct * mv / Wf.abs()).where(held).min(axis=1)[live]
        cap[f"aum_cap_usd_at_{int(pct*100)}pct_ADV_position_median_by_half"] = {
            str(k): float(v) for k, v in aum.groupby([aum.index.year, (aum.index.month > 6)]).median().rename(
                index=lambda z: z).items()}
    hv = mv.where(held)[live]
    cap["held_name_ADV_usd_percentiles_2020H2"] = {q: float(np.nanpercentile(hv.loc["2020"].to_numpy(), q)) for q in (1, 5, 10, 50)}
    cap["held_name_ADV_usd_percentiles_2021"] = {q: float(np.nanpercentile(hv.loc["2021"].to_numpy(), q)) for q in (1, 5, 10, 50)}
    cap["held_name_ADV_usd_percentiles_2022"] = {q: float(np.nanpercentile(hv.loc["2022"].to_numpy(), q)) for q in (1, 5, 10, 50)}
    turn_d = Wf.diff().abs().sum(axis=1)[live]
    g = S["gross"]
    cap["gross_ann"] = float(g.mean() * ANN); cap["turnover_per_year"] = float(turn_d.mean() * ANN)
    cap["breakeven_cost_per_side_bp"] = float(g.mean() / turn_d.mean() * 1e4)
    # cost per side where Sharpe hits the 1.15 gate / 0.30 floor
    def sr_at(cost):
        return sr(g - turn_d * cost)
    grid = np.arange(0, 80.5, 0.5) * 1e-4
    srs = np.array([sr_at(x) for x in grid])
    cap["cost_bp_for_sharpe_1p15"] = float(grid[np.argmax(srs < 1.1534)] * 1e4)
    cap["cost_bp_for_sharpe_0p30"] = float(grid[np.argmax(srs < 0.30)] * 1e4)
    # square-root impact: per-side cost = fee+half-spread (h) + Y*sigma_d*sqrt(trade/ADV)
    sig_d = dret.shift(1).rolling(30, min_periods=20).std().reindex(days)
    dW = Wf.diff().abs(); dW.iloc[0] = Wf.iloc[0].abs()
    imp = {}
    for aum in (1e5, 1e6, 5e6, 2e7, 1e8):
        for h, Y in ((7e-4, 1.0), (15e-4, 1.0)):
            q = dW * aum
            ic = (dW * (h + Y * sig_d.fillna(0.1) * np.sqrt((q / mv).clip(lower=0).fillna(1.0)))).sum(axis=1)[live]
            imp[f"aum_{aum:.0e}_h{h*1e4:.0f}bp"] = {"sharpe": sr(g - ic), "ann_mean": float((g - ic).mean() * ANN),
                                                   "sharpe_2021H2_2022": sr((g - ic).loc["2021-07-01":])}
    cap["sqrt_impact_Y1"] = imp
    res["capacity_costs"] = cap

    # ---------------- guards
    # G7: one-day execution lag using frozen returns() on lagged weights (same universe rule)
    Wlag = W.shift(1)
    lagged = c.returns(P, Wlag.where(W.notna()), "base") if False else None
    Wl1 = W.copy(); Wl1.loc[:] = W.shift(1).to_numpy(); Wl1[W.isna().all(axis=1)] = np.nan
    Wl1 = Wl1.where(~(W.notna().all(axis=1) & Wl1.isna().all(axis=1)), 0.0)
    lagged = c.returns(P, Wl1, "base").reindex(idx)
    exposure = Wf.sum(axis=1)[live]
    benches = {"MKT_ew": fac["MKT_ew"], "BTC": fac["BTC"], "MOM7": fac["MOM7"], "MOM30": fac["MOM30"],
               "REV1": fac["REV1"], "SMB_vol": fac["SMB_vol"], "LOWVOL": fac["LOWVOL"]}
    res["guards_input_notes"] = {
        "periods_per_year": "guards.py infers 252 for daily data; crypto trades 365 -> guard Sharpes are x0.83 (ratios unaffected)",
        "G2": "exposure = daily net weight (dollar-neutral => ~0), benchmark MKT_ew",
        "G5": "uses the calibrated null pass rate from null_calibration.json if present, else the run's 0.028",
        "G6": "Schmeling-Schrimpf-Todorov 'Crypto carry' BIS WP 1087 dated April 2023 (2023-04-01 used); post-pub data is entirely inside the LOCK",
        "G7": "weights lagged one day (execute at the 00:00 open of t+1)"}
    try:
        npr = json.loads((OUT / "null_calibration.json").read_text())["calibrated_P_pass_given_null_worst"]
    except Exception:
        npr = 0.028
    cert = G.certify(b, benchmarks=benches, exposure=exposure, asset_pnl=A, null_pass_rate=npr,
                     publication_date="2023-04-01", lagged_returns=lagged)
    cert_simple = G.certify(b, benchmarks={"MKT_ew": fac["MKT_ew"], "BTC": fac["BTC"]}, exposure=exposure)
    res["guards_full_factor_benchmarks"] = {k: {"pass": v["pass"], "reason": v["reason"][:600]} for k, v in cert.items()}
    res["guards_G1_mkt_btc_only"] = {"pass": cert_simple["G1_beta"]["pass"], "reason": cert_simple["G1_beta"]["reason"]}
    res["G7_lagged_sharpe_365"] = sr(lagged)

    fac.to_csv(OUT / "factors_dev.csv")
    pd.DataFrame({"base": b, "price": price, "funding": fund, "lagged1": lagged, "resid_book": pnl_r}).to_csv(OUT / "series_dev.csv")
    (OUT / "analysis.json").write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
