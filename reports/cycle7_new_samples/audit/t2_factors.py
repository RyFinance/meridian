"""Test 2: hidden beta / known factors, and a static short-USD vs EW EM basket control at matched vol.
Factor months are calendar months; strategy months run first session -> first session (1-day offset, disclosed)."""
from harness import *
D = Path(__file__).parent / "data"
base, res = run(return_res=True)
net = res["net"]["ret"]; net.index = base.index
def pm(s):
    s = s.copy(); s.index = pd.PeriodIndex(pd.to_datetime(s.index), freq="M"); return s[~s.index.duplicated(keep="last")]
rf = pd.read_parquet(REPO / "data/cycle7/snapshot_store/versions/cycle7_fx_em_v1/view/eval/series/usd_rate_3m_monthly.parquet")
rf = pm(rf.set_index("date")["value"]) / 12
lrv = pm(pd.read_parquet(D / "lrv_currency_factors.parquet"))
eem = pm(pd.read_parquet(D / "yahoo_EEM_monthly.parquet").adjclose).pct_change() - rf.shift(0)
hyg = pm(pd.read_parquet(D / "yahoo_HYG_monthly.parquet").adjclose).pct_change() - rf
vix = pm(pd.read_parquet(D / "cboe_vix_monthly_eom.parquet").CLOSE).diff()
usd = pm(pd.read_parquet(D / "fed_h10_dollar_index_monthly_eom.parquet").broad).pct_change()
dxy = pm(pd.read_parquet(D / "yahoo_DX-Y.NYB_monthly.parquet").close).pct_change()
F = pd.DataFrame({"HML_FX": lrv.all_HML_FX, "DOL": lrv.all_RX_DOL, "EEM": eem, "dVIX": vix, "HYG": hyg, "USD_broad": usd, "DXY": dxy})

def ols(y, X):
    d = pd.concat([y.rename("y"), X], axis=1).dropna()
    Y = d.y.to_numpy(); Xm = np.column_stack([np.ones(len(d)), d.drop(columns="y").to_numpy()]); n = len(Y)
    b = np.linalg.lstsq(Xm, Y, rcond=None)[0]; e = Y - Xm @ b
    L = int(np.floor(4 * (n / 100) ** (2 / 9))); U = Xm * e[:, None]; S = U.T @ U
    for l in range(1, L + 1):
        G = U[l:].T @ U[:-l]; S += (1 - l / (L + 1)) * (G + G.T)
    XtXi = np.linalg.inv(Xm.T @ Xm); se = np.sqrt(np.diag(XtXi @ S @ XtXi))
    resid_alpha = pd.Series(Y - Xm[:, 1:] @ b[1:], index=d.index)
    out = dict(n=n, first=str(d.index.min()), last=str(d.index.max()), alpha_pct_yr=100 * b[0] * 12, t_alpha=b[0] / se[0],
               R2=1 - e.var() / Y.var(), p_alpha_A4=pval(resid_alpha), alpha_sharpe=sharpe(resid_alpha))
    for i, c in enumerate(d.drop(columns="y").columns):
        out[f"b_{c}"] = b[i + 1]; out[f"t_{c}"] = b[i + 1] / se[i + 1]
    return out
rows = []
for yname, y in [("active", base), ("book net", net)]:
    for spec, cols in [("LRV (HML_FX, DOL)", ["HML_FX", "DOL"]),
                       ("USD broad + EEM + dVIX + HYG", ["USD_broad", "EEM", "dVIX", "HYG"]),
                       ("LRV + EEM + dVIX + HYG", ["HML_FX", "DOL", "EEM", "dVIX", "HYG"]),
                       ("DXY only", ["DXY"])]:
        r = ols(y, F[cols]); r.update(series=yname, model=spec); rows.append(r)
t = pd.DataFrame(rows); cols = ["series", "model", "n", "first", "last", "alpha_pct_yr", "t_alpha", "p_alpha_A4", "alpha_sharpe", "R2"] + \
    [c for c in t.columns if c.startswith(("b_", "t_")) and c != "t_alpha"]
pd.set_option("display.width", 300); print(t[cols].round(3).to_string(index=False)); t[cols].to_csv(OUT / "t2_factor_regressions.csv", index=False)

# static control: long equal-weight basket of all eligible FX-EM currencies (short USD), vol-matched to the book
_, data, _ = base_inputs()
dly = data["daily"]
lvl = (1 + dly.fillna(0)).cumprod().where(dly.notna())
first = dly.apply(lambda s: s.dropna().groupby(s.dropna().index.to_period("M")).head(1).index if False else None)
# holding-period (first session -> first session) returns per currency, as in the book
def fs_ret(s):
    s = s.dropna(); l = (1 + s).cumprod(); f = l.groupby(l.index.to_period("M")).head(1); r = f.shift(-1) / f - 1
    r.index = r.index.to_period("M"); return r
R = pd.DataFrame({c: fs_ret(dly[c]) for c in dly.columns})
elig = R.shift(1).notna() & R.notna()                            # traded last month and this month
ew = R.where(elig).mean(axis=1).reindex(base.index)
# vol-match: ex-ante, trailing 36m vol ratio of book net vs basket (earlier months only), capped at 3x
k = (net.rolling(36, min_periods=12).std() / ew.rolling(36, min_periods=12).std()).shift(1).clip(upper=3)
static = (k * ew).dropna()
act_static = (net - static).dropna()
rows2 = [summarize("static short-USD EW EM basket (vol-matched)", static),
         summarize("book net - static", act_static), summarize("book net - static | post-KMVP", act_static, start=KMVP_CUT),
         summarize("book net", net), summarize("book net | post-KMVP", net, start=KMVP_CUT)]
t2 = pd.DataFrame(rows2); print(t2.round(3).to_string(index=False)); t2.to_csv(OUT / "t2_static_short_usd.csv", index=False)
print("corr(book net, static basket):", round(net.corr(ew), 3), "| corr(active, HML_FX):", round(base.corr(F.HML_FX), 3))
