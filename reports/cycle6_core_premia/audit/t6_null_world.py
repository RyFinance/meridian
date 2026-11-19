"""Test 6: null world at book level. 10,000 null books: each component's pre-cost return multiplied by a random
sign process (stationary blocks, mean length 12 -> signal sign-randomised while keeping within-block autocorrelation;
costs always charged), core left intact, same book weights / cap / cash (weights frozen at the real book's; a 300-path
subset re-solves ERC+cap per null to check the approximation).
Variant A: one sign process shared by all six components (preserves their cross-correlation).
Variant B: independent sign processes per component (common block boundaries)."""
from common import *
from research.amendment4 import ci as a4ci, calib
R, G = sleeves_and_gross()
tb = tbill_monthly()
bk, W = build_book(R, G, tb, weights_out=True)
months = bk.index
Wm = W.reindex(months).fillna(0.0)
comp = {c: load_component(c).reindex(months) for c in SLEEVES}
g = np.column_stack([comp[c].ret_before_cost.fillna(0).to_numpy() for c in SLEEVES])
cst = np.column_stack([comp[c].cost.fillna(0).to_numpy() for c in SLEEVES])
w6 = Wm[SLEEVES].to_numpy()
core_part = (Wm["CORE"] * R["CORE"].reindex(months).fillna(0)).to_numpy()
cash = bk.cash_adj.fillna(0).to_numpy()
real = bk.excess.to_numpy()
assert np.allclose((w6 * (g - cst)).sum(1) + core_part + cash, real, atol=1e-10)
ctrl = pd.read_csv(OUT / "t1_series.csv", index_col=0)["ctrl"]; ctrl.index = pd.PeriodIndex(ctrl.index, freq="M")
ctrl = ctrl.reindex(months).to_numpy()
post = np.asarray(months >= pd.Period(POST, "M"))
T, N, B = len(months), 10_000, 499

def signs(rng, n_comp):
    S = np.empty((T, n_comp))
    t = 0
    while t < T:
        L = rng.geometric(1 / 12); S[t:t + L] = rng.choice([-1.0, 1.0], size=n_comp); t += L
    return S

def ci_batch(X, level=0.90, seed=100):
    L = calib.stat_lags(X.shape[1])
    est, tm, ts = a4ci.boot_t_batch(np.ascontiguousarray(X), L, B, seed, 50)
    a = 1 - level
    q_hi, q_lo = np.quantile(ts, 1 - a / 2, axis=1), np.quantile(ts, a / 2, axis=1)
    s, se = est[:, 2], est[:, 3]
    return (s - q_hi * se) * np.sqrt(12), (s - q_lo * se) * np.sqrt(12), s * np.sqrt(12)

real_post = real[post]; lo_r, hi_r, s_r = ci_batch(real_post[None, :])
act_r = real_post - ctrl[post]
res = {}
for var in ["A_common_sign", "B_independent_signs"]:
    rng = np.random.default_rng(20260927 + (var[0] == "B"))
    X = np.empty((N, T))
    for i in range(N):
        S = signs(rng, 1 if var[0] == "A" else 6)
        X[i] = (w6 * (S * g - cst)).sum(1) + core_part + cash
    Xp = X[:, post]
    lo, hi, s = ci_batch(Xp)
    act = Xp - ctrl[post][None, :]
    act_mean = act.mean(1)
    res[var] = dict(n_null=N, share_ci90_excludes_zero_raw=float(np.mean(lo > 0)),
                    share_null_sharpe_ge_real=float(np.mean(s >= s_r[0])),
                    share_active_mean_ge_real=float(np.mean(act_mean >= act_r.mean())),
                    null_median_sharpe=float(np.median(s)), null_median_ci_lo=float(np.median(lo)))
    np.save(OUT / f"t6_null_{var}_post_sharpe.npy", s)
# ERC re-solve check (variant B, 300 paths)
rng = np.random.default_rng(99); chk = []
for i in range(300):
    S = pd.DataFrame(signs(rng, 6), index=months, columns=SLEEVES)
    Rn = R.copy()
    for c in SLEEVES:
        d = load_component(c)
        Rn[c] = (S[c].reindex(R.index) * d.ret_before_cost.reindex(R.index) - d.cost.reindex(R.index))
    b = build_book(Rn, G, tb).excess.loc[POST:].to_numpy()
    chk.append(b)
lo2, hi2, s2 = ci_batch(np.array(chk), seed=7)
res["B_resolved_ERC_300"] = dict(n_null=300, share_ci90_excludes_zero_raw=float(np.mean(lo2 > 0)),
                                 share_null_sharpe_ge_real=float(np.mean(s2 >= s_r[0])), null_median_sharpe=float(np.median(s2)))
res["real"] = dict(sharpe_post=float(s_r[0]), ci90=[float(lo_r[0]), float(hi_r[0])], active_mean_ann=float(act_r.mean() * 12))
# core alone in the same weights (sleeves zeroed): how often would the core-only part be 'positive'?
core_only = core_part[post] + cash[post]
l3, h3, s3 = ci_batch(core_only[None, :])
res["core_part_only"] = dict(sharpe_post=float(s3[0]), ci90=[float(l3[0]), float(h3[0])])
import json; print(json.dumps(res, indent=1)); json.dump(res, open(OUT / "t6_null_world.json", "w"), indent=1)
