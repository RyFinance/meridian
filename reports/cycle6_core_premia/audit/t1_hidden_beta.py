"""Test 1: hidden beta. (a) book minus vol-matched core-only control; (b) ex-core book; (c) regressions on SPY/IEF."""
from common import *
R, G = sleeves_and_gross()
tb = tbill_monthly()
book = build_book(R, G, tb)
core = R["CORE"]

# (a) control: 60/40 core scaled each month to the book's ex-ante vol, sigma_core from trailing 60m (earlier months, >=12)
sig = core.rolling(60, min_periods=12).std().shift(1) * np.sqrt(12)
rows = []
for h in book.index:
    s = sig.get(h, np.nan); r = core.get(h, np.nan)
    if pd.isna(s) or pd.isna(r) or s <= 0:
        rows.append(dict(month=h, ctrl=np.nan)); continue
    k = min(book.at[h, "exante"] / s, P["gross_cap"])          # core gross notional = 1 per unit
    tbm = book.at[h, "tb"]
    adj = (1 - k) * (max(0.0, tbm - P["cash_spread"] / 12) - tbm) if k <= 1 else -(k - 1) * P["fin_spread"] / 12
    rows.append(dict(month=h, ctrl=k * r + adj, k_ctrl=k))
ctrl = pd.DataFrame(rows).set_index("month")
# (b) ex-core
exc = build_book(R.drop(columns="CORE"), G.drop(columns="CORE"), tb)

# (c) regressors: SPY, IEF lagged-period excess returns
X = lagged_period_returns(core_etf_daily())

def reg(y, label, win):
    d = pd.concat([y.rename("y"), X[["SPY", "IEF"]]], axis=1).dropna()
    if win: d = d.loc[win:]
    b, t, r2 = ols_hac(d.y, d[["SPY", "IEF"]])
    resid_alpha = d.y - b[1] * d.SPY - b[2] * d.IEF
    return dict(series=label, window=win or "2002-08+", n=len(d), alpha_ann=b[0] * 12,
                t_alpha_HAC=t[0], b_SPY=b[1], t_SPY=t[1], b_IEF=b[2], t_IEF=t[2], R2=r2,
                p_alpha_A4=calib_p(resid_alpha.to_numpy(), crash=True, bw=0.20, seed=11),
                alpha_sharpe=resid_alpha.mean() / resid_alpha.std() * np.sqrt(12))

out, regs = [], []
active = (book.excess - ctrl.ctrl)
series = {"book (raw)": book.excess, "core control (vol-matched)": ctrl.ctrl, "book - control (active)": active,
          "ex-core book": exc.excess}
for win_name, win in [("post 2019-02+", POST), ("core era 2002-09+", "2002-09"), ("full 1975+", None)]:
    for name, x in series.items():
        x = x.dropna()
        if win: x = x.loc[win:]
        if len(x) < 24: continue
        st = stats(x)
        c90 = calib_ci(x.to_numpy(), 0.90, seed=5); c95 = calib_ci(x.to_numpy(), 0.95, seed=5)
        out.append(dict(window=win_name, series=name, n=st["n"], mean_ann=st["mean_ann"], vol_ann=st["vol_ann"],
                        sharpe=st["sharpe"], ci90_lo=c90[0], ci90_hi=c90[1], ci95_lo=c95[0], ci95_hi=c95[1],
                        p_A4_default=calib_p(x.to_numpy(), seed=7),
                        p_A4_crash_bw20=calib_p(x.to_numpy(), crash=True, bw=0.20, seed=7), mdd=st["mdd"]))
for win in [POST, "2002-09"]:
    regs += [reg(book.excess, "book", win), reg(exc.excess, "ex-core book", win)]
o = pd.DataFrame(out); r = pd.DataFrame(regs)
pd.set_option("display.width", 250)
print(o.round(3).to_string()); print(r.round(3).to_string())
o.to_csv(OUT / "t1_active_vs_core.csv", index=False); r.to_csv(OUT / "t1_regressions.csv", index=False)
print("corr(book, control) post:", round(book.excess.loc[POST:].corr(ctrl.ctrl.loc[POST:]), 3),
      "mean control k post:", round(ctrl.k_ctrl.loc[POST:].mean(), 3))
pd.concat([book.excess.rename("book"), ctrl, exc.excess.rename("excore")], axis=1).to_csv(OUT / "t1_series.csv")
