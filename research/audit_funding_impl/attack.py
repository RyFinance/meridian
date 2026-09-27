import json, numpy as np, pandas as pd
from research.audit_funding_impl.replicate import *

K, F = load()
P = panels(K, F)
W = pd.read_parquet(OUT / "my_weights.parquet"); nU = pd.read_parquet(OUT / "my_universe_n.parquet").n
live = W.notna().all(axis=1); Wf = W.fillna(0.0)
base = daily(P, W); R = {}
idx = W.index
O, H, L, C, Vv, FU = (P[k].reindex(idx) for k in ("O", "H", "L", "C", "V", "FUND"))
ret = C / O - 1

# ---- 2. timing ----
Ph = panels(K, F, fund_mode="hour")
bh = daily(Ph, W)                      # same weights, funding attributed with hour-rounded calc_time (00:00 of t+1 -> day t)
Wh, _ = build_weights(Ph); bh2 = daily(Ph, Wh)
# partition check: every in-window settlement counted exactly once
Fm = F[(F.ts > idx[0]) & (F.ts <= idx[-1] + pd.Timedelta(days=1))]
tot_rates = Fm.groupby("sym").rate.sum(); tot_fund = FU.sum()
R["timing"] = {
  "sharpe_base_raw": sharpe(base.net), "sharpe_base_hour_rounded_same_weights": sharpe(bh.net),
  "sharpe_base_hour_rounded_signal_and_funding": sharpe(bh2.net),
  "funding_leg_ann_raw": float(base.fund.mean() * 365), "funding_leg_ann_hour": float(bh.fund.mean() * 365),
  "partition_max_abs_err": float((tot_rates.reindex(tot_fund.index).fillna(0) - tot_fund).abs().max()),
  "settlements_per_day_hist": {int(k): int(v) for k, v in P["NS"].reindex(idx).stack().pipe(lambda s: s[s > 0]).div(7).round().value_counts().head(6).items()},
  "fund_days_per_symbol_raw_vs_hour_count_mismatch": int(((FU != 0) != (Ph["FUND"].reindex(idx) != 0)).sum().sum()),
}
# look-ahead probe: correlation of the day-t selection with close_t (should be none) -- shift test:
# if weights secretly used day-t info, lagging weights by one day would collapse P&L far more than signal decay implies
lag = daily(P, W.shift(1)); R["timing"]["sharpe_weights_lagged_1d"] = sharpe(lag.net)
R["timing"]["sharpe_weights_lagged_2d"] = sharpe(daily(P, W.shift(2)).net)
# open vs previous close (is the 00:00 open a continuation price?)
pc = P["C"].shift(1).reindex(idx)
g = (O / pc - 1)[Wf != 0].stack()
R["timing"]["held_open_vs_prevclose"] = {"n": int(len(g)), "abs_gt_0.5pct": int((g.abs() > 0.005).sum()), "abs_gt_2pct": int((g.abs() > 0.02).sum()), "max_abs": float(g.abs().max())}

# ---- 3. data integrity: missing klines while held (Binance monthly-file holes) ----
miss = (ret.isna() & (Wf != 0))
md = miss.any(axis=1) & live
R["missing_while_held"] = {"days": [str(d.date()) for d in idx[md]], "position_days": int(miss[live].sum().sum()),
    "gross_weight_missing_by_day": {str(d.date()): float(Wf.abs()[miss].loc[d].sum()) for d in idx[md]},
    "stress_delist_penalty_total": float((miss * Wf.abs()).sum(axis=1)[live].sum() * 0.2)}
st = daily(P, W, 20e-4, 0.2); st_nod = daily(P, W, 20e-4, 0.0)
R["missing_while_held"]["stress_sharpe"] = sharpe(st.net); R["missing_while_held"]["stress_sharpe_no_delist_penalty"] = sharpe(st_nod.net)
holes = pd.to_datetime(["2022-02-26", "2022-02-27", "2022-02-28", "2022-03-01", "2022-04-01", "2022-04-02", "2022-04-03"])
R["missing_while_held"]["universe_n_on_hole_days"] = {str(d.date()): int(nU[d]) for d in holes}
R["missing_while_held"]["base_net_on_hole_days"] = float(base.net.reindex(holes).sum())
R["missing_while_held"]["sharpe_excluding_hole_days"] = sharpe(base.net.drop(holes, errors="ignore"))
# delistings inside dev
last = K.groupby("sym").day.max(); dl = last[last < pd.Timestamp("2022-12-31")]
rows = []
for s, d in dl.items():
    held = Wf[s].reindex(pd.date_range(d - pd.Timedelta(days=5), d + pd.Timedelta(days=3))).fillna(0)
    held_any = bool((held != 0).any())
    kk = K[(K.sym == s)].set_index("day").iloc[-4:]
    rows.append({"sym": s, "last_day": str(d.date()), "held_near_delist": held_any,
                 "w_on_last_day": float(Wf[s].get(d, 0.0)), "w_after_last_day": float(Wf[s].get(d + pd.Timedelta(days=1), 0.0)),
                 "last4_ret": [round(x, 4) for x in (kk.close / kk.open - 1).tolist()], "last4_qv_musd": [round(x / 1e6, 2) for x in kk.qv.tolist()],
                 "pnl_contrib_last5d": float((Wf[s] * ret[s].fillna(0)).reindex(pd.date_range(d - pd.Timedelta(days=4), d)).sum())})
R["delistings_in_dev"] = rows

# ---- 4/5. attribution & concentration ----
contrib = (Wf * ret.fillna(0)) - (Wf * FU.fillna(0))
contrib = contrib[live]
cy = contrib.groupby(contrib.index.year).sum()
R["attrib"] = {}
for y in cy.index:
    s = cy.loc[y].sort_values()
    tot = float(base.net[base.index.year == y].sum())
    R["attrib"][int(y)] = {"net_total": tot, "gross_sym_sum": float(s.sum()), "top10_pos": {k: round(v, 4) for k, v in s[::-1].head(10).items()},
                           "top10_neg": {k: round(v, 4) for k, v in s.head(10).items()},
                           "top5_share_of_gross": float(s[::-1].head(5).sum() / s.sum()), "n_syms_traded": int((cy.loc[y] != 0).sum()),
                           "k_per_leg_mean": float((Wf[live & (Wf.index.year == y)] > 0).sum(axis=1).mean()),
                           "live_days": int((live & (idx.year == y)).sum())}
# as-run comparison
aw = pd.read_parquet(ROOT / "reports/crypto_funding_xs/dev_weights.parquet")
ad = pd.read_csv(ROOT / "reports/crypto_funding_xs/dev_daily.csv", index_col=0, parse_dates=True)
new = sorted(set(W.columns[(Wf != 0).any()]) - set(aw.columns[(aw.fillna(0) != 0).any()]))
R["as_run_vs_corrected"] = {"new_traded_symbols": new, "as_run_first_live": str(ad.index[0].date()), "as_run_live_days_2020": int((ad.index.year == 2020).sum()),
    "corrected_live_days_2020": int((base.index.year == 2020).sum()),
    "as_run_2020_on_common_days": float(ad.base[ad.index.year == 2020].sum()),
    "corrected_2020_on_as_run_days": float(base.net.reindex(ad.index[ad.index.year == 2020]).sum()),
    "corrected_2020_on_extra_days": float(base.net[(base.index.year == 2020) & ~base.index.isin(ad.index)].sum()),
    "new_symbols_direct_contrib_by_year": {int(y): float(cy.loc[y, [c for c in new if c in cy.columns]].sum()) for y in cy.index},
    "new_symbols_top_2020": {k: round(v, 4) for k, v in cy.loc[2020, [c for c in new if c in cy.columns]].sort_values()[::-1].head(10).items()}}
# leave-one-symbol-out (drop symbol's P&L contribution; upper bound on its role) for 2020 and whole sample
tot_all = contrib.sum().sort_values()[::-1]
R["attrib"]["whole_top10"] = {k: round(v, 4) for k, v in tot_all.head(10).items()}
R["attrib"]["whole_bottom5"] = {k: round(v, 4) for k, v in tot_all.tail(5).items()}
bn = base.net
for n in (1, 3, 5):
    top = tot_all.index[:n]
    adj = bn - contrib[top].sum(axis=1).reindex(bn.index).fillna(0)
    R["attrib"][f"sharpe_minus_top{n}_symbols_pnl"] = sharpe(adj)
R["attrib"]["sharpe_2021_2022_only"] = sharpe(bn[bn.index >= "2021-01-01"])
R["attrib"]["sharpe_2020_only"] = sharpe(bn[bn.index < "2021-01-01"])
R["attrib"]["sharpe_universe_ge_50_days_only"] = sharpe(bn[nU.reindex(bn.index) >= 50])
R["attrib"]["legs_ann"] = {"long_price": float((Wf.clip(lower=0) * ret.fillna(0)).sum(axis=1)[live].mean() * 365),
                           "short_price": float((Wf.clip(upper=0) * ret.fillna(0)).sum(axis=1)[live].mean() * 365),
                           "long_fund": float(-(Wf.clip(lower=0) * FU.fillna(0)).sum(axis=1)[live].mean() * 365),
                           "short_fund": float(-(Wf.clip(upper=0) * FU.fillna(0)).sum(axis=1)[live].mean() * 365)}

# extremes
tot = bn.sum(); srt = bn.sort_values(ascending=False)
R["extremes"] = {"total_simple_sum": float(tot), "top10_days_share": float(srt.head(10).sum() / tot), "top20_share": float(srt.head(20).sum() / tot),
                 "days_gt_5pct": {str(d.date()): round(v, 4) for d, v in bn[bn > 0.05].items()},
                 "days_lt_-5pct": {str(d.date()): round(v, 4) for d, v in bn[bn < -0.05].items()},
                 "sharpe_ex_top10": sharpe(bn.drop(srt.index[:10])), "sharpe_winsor_1pct": sharpe(bn.clip(bn.quantile(.01), bn.quantile(.99)))}
det = {}
for d in srt.index[:10]:
    c = contrib.loc[d].sort_values(); c = c[c != 0]
    det[str(d.date())] = {"net": round(float(bn[d]), 4), "top3": {k: [round(v, 4), round(float(ret.loc[d, k]), 3), round(float(Vv.loc[d, k]) / 1e6, 1)] for k, v in c[::-1].head(3).items()},
                          "open_vs_prevclose_top3": {k: round(float(O.loc[d, k] / pc.loc[d, k] - 1), 4) for k in c[::-1].head(3).index}}
R["extremes"]["top10_detail_[contrib,ret,qv$m]"] = det

# ---- 6. costs & liquidation ----
bd = daily(P, W, drift_turnover=True)
R["costs"] = {"turnover_mean": float(base.turn.mean()), "turnover_with_drift": float(bd.turn.mean()),
              "sharpe_drift_turnover_7bp": sharpe(bd.net),
              "turnover_by_year": {int(y): float(g.mean()) for y, g in base.turn.groupby(base.index.year)},
              "gross_ann": float((base.price + base.fund).mean() * 365),
              "breakeven_bp_per_side": float((base.price + base.fund).mean() / base.turn.mean() * 1e4)}
for bp in (10, 15, 20, 30):
    x = daily(P, W, bp * 1e-4, 0.0, drift_turnover=True)
    R["costs"][f"sharpe_{bp}bp_drift_nodelist"] = sharpe(x.net); R["costs"][f"by_year_{bp}bp"] = {int(y): round(float(g.sum()), 3) for y, g in x.net.groupby(x.index.year)}
# volume-scaled slippage: 7bp + 25bp * (1 / rank-percentile) ... simple: 30bp for names with trailing median qv < $20m, else 7bp
medv = P["V"].shift(1).rolling(30, min_periods=15).median().reindex(idx)
dW = (bd.turn * 0)  # placeholder
drifted = (Wf * (1 + ret.fillna(0))).shift(1).fillna(0.0); tr = (Wf - drifted).abs()
for thr, bp in ((20e6, 30), (50e6, 30)):
    c = (tr * np.where(medv.fillna(0).to_numpy() < thr, bp * 1e-4, 7e-4)).sum(axis=1)[live]
    R["costs"][f"sharpe_{bp}bp_if_medqv<{int(thr/1e6)}m_else_7bp"] = sharpe(base.price + base.fund - c)
    R["costs"][f"share_turnover_in_names_medqv<{int(thr/1e6)}m_2020"] = float(tr[live & (idx.year == 2020)].where(medv < thr).sum().sum() / tr[live & (idx.year == 2020)].sum().sum())
up = (H / O - 1).where(Wf < 0); dn = (L / O - 1).where(Wf > 0)
up = up[live]; dn = dn[live]
R["liquidation"] = {"short_pos_days": int(up.notna().sum().sum()),
    "short_intraday_high_ge_25pct": int((up >= .25).sum().sum()), "ge_50pct": int((up >= .5).sum().sum()), "ge_100pct": int((up >= 1).sum().sum()),
    "long_intraday_low_le_-25pct": int((dn <= -.25).sum().sum()), "le_-50pct": int((dn <= -.5).sum().sum()),
    "short_ge_50pct_events": {f"{d.date()} {s}": round(float(v), 3) for (d, s), v in up.stack()[up.stack() >= .5].items()},
    "max_short_intraday_up": float(up.max().max())}
# worst-case: short positions whose high >= 1/lev are liquidated (lose full margin = w/lev*... ) -> approximate loss = position loses high-move capped by 1/lev margin? with isolated margin at leverage L, loss = w*1/L... model: close at high (stop-out at the high) instead of close
for lev_thr in (0.5, 0.3, 0.2):
    hit = (up >= lev_thr)
    adj_ret = ret.copy()[live]
    adj_ret = adj_ret.where(~hit, lev_thr)  # stopped out at +thr adverse
    alt = (Wf[live] * adj_ret.fillna(0)).sum(axis=1) + base.fund - base.cost
    R["liquidation"][f"sharpe_if_shorts_stopped_at_+{int(lev_thr*100)}pct_intraday"] = sharpe(alt); R["liquidation"][f"n_stops_{int(lev_thr*100)}"] = int(hit.sum().sum())
# multi-day run-up for continuously held shorts (margin not topped up): max cumulative close/entry during a holding spell
runs = []
for s in Wf.columns:
    w = Wf[s][live]; sh = (w < 0).astype(int)
    if sh.sum() == 0: continue
    spell = (sh.diff().fillna(sh.iloc[0]) == 1).cumsum()[sh == 1]
    for _, dd in spell.groupby(spell).groups.items():
        e = O.loc[dd[0], s]; hmax = H.loc[dd, s].max()
        if np.isfinite(e) and np.isfinite(hmax): runs.append((s, str(dd[0].date()), len(dd), hmax / e - 1))
rr = pd.DataFrame(runs, columns=["sym", "start", "len", "maxup"])
R["liquidation"]["short_spells"] = int(len(rr)); R["liquidation"]["spells_maxup_ge_50pct"] = int((rr.maxup >= .5).sum()); R["liquidation"]["spells_maxup_ge_100pct"] = int((rr.maxup >= 1).sum())
R["liquidation"]["worst_spells"] = rr.sort_values("maxup").tail(8).round(3).values.tolist()

(OUT / "attack.json").write_text(json.dumps(R, indent=1, default=str))
print(json.dumps(R, indent=1, default=str))
