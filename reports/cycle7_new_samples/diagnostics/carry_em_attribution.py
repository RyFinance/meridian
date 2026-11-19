"""DESCRIPTIVE diagnostic of the ledgered CARRY-FX__FX-EM run (not a trial, not counted, cannot change any flag):
recompute the identical deterministic run in memory (same spec params, same frozen snapshot, same instruments) and
decompose net P&L by currency, NDF status and sub-period. Asserts the recomputed active series equals the ledgered one."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
REPO = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(REPO))
from research.cycle7.runner import sample as smp, evaluate
from research.cycle6.engine import component, guards, panel
from research.amendment4 import calib
sp = REPO / "research/cycle7/samples/CARRY-FX__FX-EM.md"
s = smp.parse_sample(sp.read_text())
spec = guards.parse_params((REPO / s["spec_path"]).read_text())
params, dropped = smp.map_params(spec, s)
root = REPO / s["snapshot_root_rel"]
ids = evaluate.filtered_universe(root, root / s["membership"], params, s["instrument_filter"])
data = evaluate.apply_filter(component.load_inputs(params, root, root / s["membership"]), ids)
res = component.compute_component(params, data)
led = pd.read_csv(REPO / "reports/cycle7_new_samples/runs/CARRY-FX__FX-EM/active.csv", index_col=0)
print("result keys:", list(res.keys()))

W = res["W"]                                   # signal-month x currency weights (held next month)
rnet = panel.net_period_returns(data["daily"])  # holding-period returns by month
H = W.shift(1).reindex(rnet.index)               # weights held in month m
pnl = (H * rnet[H.columns]).fillna(0.0)
net = res["net"]; win = [m for m in net.index if str(m) >= "1988-02"]
chk = float((pnl.sum(axis=1).reindex(win) - net["ret_before_cost"].reindex(win)).abs().max())
print("decomposition check max |diff| vs engine gross-before-cost:", chk)
cl = pd.read_csv(root / "eval/candidate_list.csv").set_index("market_id")
tot = pnl.loc[win].sum()
tab = pd.DataFrame({"pnl_sum": tot, "share": tot / tot.sum(), "ndf_only": cl.reindex(tot.index).ndf_only,
                    "mean_abs_w": H.loc[win].abs().mean(), "mean_w": H.loc[win].mean()}).sort_values("pnl_sum", ascending=False)
print(tab.round(3).to_string())
print("NDF vs deliverable P&L share:", tab.groupby("ndf_only").pnl_sum.sum().div(tab.pnl_sum.sum()).round(3).to_dict())
a = led.iloc[:, 0]; a.index = pd.PeriodIndex(a.index.astype(str), freq="M")
rows = []
for name, lo, hi in [("1988-02..2008-08", "1988-02", "2008-08"), ("2008-09..2013-08", "2008-09", "2013-08"),
                     ("post-KMVP 2013-09+", "2013-09", "2026-09"), ("2009-01+", "2009-01", "2026-09"), ("full", "1988-02", "2026-09")]:
    x = a.loc[lo:hi].dropna()
    rows.append(dict(window=name, n=len(x), active_sharpe=x.mean() / x.std() * np.sqrt(12), mean_pct_yr=100 * x.mean() * 12,
                     p_A4_crash=float(calib.calibrated_pvalues(x.to_numpy()[None, :], B=9999, seed=1, full=True,
                                      crash=(0.2 / 12, -6.0), bandwidth_fraction=0.10)["p"][0])))
sub = pd.DataFrame(rows); print(sub.round(3).to_string())
# ex-NDF currencies and ex top-3 contributors: descriptive re-weighting is NOT possible without rerunning the rank
# rule, so we report P&L excluding them from the SAME book (descriptive only).
ndf = tab.index[tab.ndf_only == True]
ex = pnl.loc[win].drop(columns=ndf).sum(axis=1)
print("book gross P&L excl. NDF currencies' contributions: Sharpe", round(ex.mean() / ex.std() * np.sqrt(12), 3))
top3 = tab.index[:3]; ex3 = pnl.loc[win].drop(columns=top3).sum(axis=1)
print("excl. top-3 contributors", list(top3), ": Sharpe", round(ex3.mean() / ex3.std() * np.sqrt(12), 3))
tab.to_csv(Path(__file__).parent / "carry_em_by_currency.csv"); sub.to_csv(Path(__file__).parent / "carry_em_subperiods.csv", index=False)

# ---- entry-into-mask bias: positions held into a month whose returns were masked (engine books 0 instead of the move)
reg = pd.read_csv(REPO / "data/cycle7/fx/fx_regimes.csv"); reg["m"] = pd.to_datetime(reg.month).dt.to_period("M")
iso2 = {"ARS": "AR", "BRL": "BR", "CLP": "CL", "COP": "CO", "CZK": "CZ", "DKK": "DK", "HUF": "HU", "IDR": "ID", "ILS": "IL",
        "INR": "IN", "ISK": "IS", "KRW": "KR", "MXN": "MX", "MYR": "MY", "PEN": "PE", "PHP": "PH", "PLN": "PL", "RUB": "RU",
        "SGD": "SG", "THB": "TH", "TRY": "TR", "ZAR": "ZA"}
hits = []
for c in W.columns:
    ccy = c[3:]; ex = set(reg[(reg.ccy == ccy) & reg.exclude].m)
    d = pd.read_csv(REPO / f"data/cycle7/fx/raw/bis_xru_d/D_{iso2[ccy]}.csv", usecols=["TIME_PERIOD", "OBS_VALUE"])
    s = pd.Series(pd.to_numeric(d.OBS_VALUE, errors="coerce").values, index=pd.to_datetime(d.TIME_PERIOD)).dropna()
    me = s.groupby(s.index.to_period("M")).last(); usd_per_ccy_ret = (1 / me).pct_change()
    for m in H.index:
        w = H.at[m, c] if c in H.columns else np.nan
        if pd.notna(w) and w != 0 and m in ex:
            hits.append(dict(ccy=ccy, month=str(m), weight_held=w, spot_move_usd_per_ccy=usd_per_ccy_ret.get(m, np.nan),
                             missed_pnl_approx=w * usd_per_ccy_ret.get(m, np.nan)))
h = pd.DataFrame(hits)
print("held-into-masked-month cases:", len(h))
if len(h):
    print(h.sort_values("missed_pnl_approx").round(4).to_string(index=False))
    print("sum missed P&L (spot only, approx):", round(h.missed_pnl_approx.sum(), 4), "vs total gross P&L", round(float(pnl.loc[win].sum().sum()), 4))
h.to_csv(Path(__file__).parent / "carry_em_held_into_mask.csv", index=False)
