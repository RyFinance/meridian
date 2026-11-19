"""Test 5: is fidelity pass/fail correlated with components' own performance? (all 20 components)"""
from common import *
import json
from scipy import stats as ss
rows = []
for c in ALL20:
    m = json.load(open(COMP / c / "metrics.json"))
    d = load_component(c)
    cut = m["post_pub_cutoff"]
    pre = d.ret.loc[:str(pd.Period(cut, "M") - 1)].dropna(); post = d.ret.loc[cut:].dropna()
    rows.append(dict(id=c, fid=int(m["fidelity"]["pass"]), sharpe_post=stats(post)["sharpe"],
                     sharpe_pre=stats(pre)["sharpe"] if len(pre) > 24 else np.nan,
                     active_post=m["active_post"]["sharpe_ann"], sharpe_full=stats(d.ret)["sharpe"]))
t = pd.DataFrame(rows).set_index("id"); print(t.round(3).to_string())
res = []
for col in ["sharpe_post", "active_post", "sharpe_pre", "sharpe_full"]:
    a, b = t.loc[t.fid == 1, col].dropna(), t.loc[t.fid == 0, col].dropna()
    rpb = ss.pointbiserialr(t.fid[t[col].notna()], t[col].dropna())
    # exact permutation p of mean difference (one-sided pass > fail), 100k random relabels
    rng = np.random.default_rng(20260927); x = t[col].dropna().to_numpy(); f = t.fid[t[col].notna()].to_numpy()
    obs = x[f == 1].mean() - x[f == 0].mean()
    perm = np.array([(lambda g: x[g == 1].mean() - x[g == 0].mean())(rng.permutation(f)) for _ in range(100000)])
    res.append(dict(metric=col, mean_pass=a.mean(), mean_fail=b.mean(), diff=obs, point_biserial=rpb.statistic,
                    perm_p_one_sided=(perm >= obs).mean(), optimism_vs_all=a.mean() - x.mean()))
r = pd.DataFrame(res); print(r.round(3).to_string())
t.to_csv(OUT / "t5_components.csv"); r.to_csv(OUT / "t5_selection.csv", index=False)
