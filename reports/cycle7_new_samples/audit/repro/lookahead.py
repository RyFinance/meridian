"""Look-ahead perturbation test: replace every input dated after a cut with noise; weights formed at signal months
before the cut month-end (and net/control returns whose holding period ends before the cut) must be bit-identical.
Run on (A) this independent implementation and (B) the frozen engine's compute_component, in memory."""
import sys, json, copy, hashlib
from pathlib import Path
import numpy as np, pandas as pd
ROOT = "/Users/rytty/CCP/quant_v7"
sys.path.insert(0, ROOT); sys.path.insert(0, f"{ROOT}/reports/cycle7_new_samples/audit/repro")
import repro_carry_fx_em as r
CUTS = [pd.Timestamp("1995-06-30"), pd.Timestamp("2005-06-15"), pd.Timestamp("2015-06-30")]


def noise_after(df_or_s, cut, rng, sd, loc=0.0):
    x = df_or_s.copy()
    mask = x.index > cut
    if isinstance(x, pd.Series):
        m = mask & x.notna().to_numpy()
        x[m] = loc + sd * rng.standard_normal(m.sum())
    else:
        vals = x.to_numpy().copy()
        sub = vals[mask]
        nn = ~np.isnan(sub)
        sub[nn] = loc + sd * rng.standard_normal(nn.sum())
        vals[mask] = sub
        x = pd.DataFrame(vals, index=x.index, columns=x.columns)
    return x


def safe_label_max(cut):
    # a net period labelled m ends at the first session of m+1: unchanged iff first session of m+1 <= cut
    return cut.to_period("M") - 2 if cut.is_month_end else cut.to_period("M") - 2


def check(W0, W1, idx, sigmax, name, series0=None, series1=None, labmax=None):
    idx = pd.PeriodIndex(idx)
    pre = idx <= sigmax
    d_pre = float(np.nanmax(np.abs(W0[pre] - W1[pre]))) if pre.any() else 0.0
    d_post = float(np.nanmax(np.abs(W0[~pre] - W1[~pre]))) if (~pre).any() else 0.0
    out = {"impl": name, "sig_months_checked": int(pre.sum()), "max_abs_dW_pre": d_pre, "max_abs_dW_post": d_post}
    if series0 is not None:
        for k in series0:
            a, b = series0[k], series1[k]
            ii = a.index[a.index <= labmax].intersection(b.index)
            out[f"max_abs_d_{k}_pre"] = float(np.max(np.abs(a[ii].to_numpy() - b[ii].to_numpy()))) if len(ii) else 0.0
    return out


def repro_side(cut, rng):
    daily, fr, us = r.load()
    base, W0, lab = r.run("norm", daily=daily, fr=fr, us=us)
    d1 = noise_after(daily, cut, rng, 0.02)
    fr_ts = fr.copy(); fr_ts.index = fr.index.to_timestamp(how="end").normalize()
    us_ts = us.copy(); us_ts.index = us.index.to_timestamp(how="end").normalize()
    # month-period rates: a month whose end is after the cut is perturbed
    fr1 = noise_after(fr_ts, cut, rng, 0.1, 0.05); fr1.index = fr.index
    us1 = noise_after(us_ts, cut, rng, 0.02, 0.03); us1.index = us.index
    pert, W1, lab1 = r.run("norm", daily=d1, fr=fr1, us=us1)
    assert (lab == lab1).all()
    sigmax = (cut.to_period("M") - 1) if not cut.is_month_end else cut.to_period("M")
    s0 = {k: base.set_index(pd.PeriodIndex(base.month, freq="M"))[k] for k in ("net", "control", "active")}
    s1 = {k: pert.set_index(pd.PeriodIndex(pert.month, freq="M"))[k] for k in ("net", "control", "active")}
    # W rows are label months (signal = label-1)
    return check(W0, W1, lab - 1, sigmax, "repro", s0, s1, safe_label_max(cut))


def builder_side(cut, rng):
    from research.cycle6.engine import component, guards as eg
    from research.cycle7.runner import sample as smp, evaluate as ev, common
    eng = common.dir_py_sha256(common.engine_dir())
    assert eng == common.ENGINE_SHA256, eng
    s = smp.parse_sample(Path(f"{ROOT}/research/cycle7/samples/CARRY-FX__FX-EM.md").read_text())
    params = eg.parse_params(Path(f"{ROOT}/research/cycle6/specs/CARRY-FX.md").read_text())
    params, _ = smp.map_params(params, s)
    params = copy.deepcopy(params); params["inference"]["B"] = 19; params["inference"]["ci_B"] = 19  # speed only
    snap = Path(ROOT) / s["snapshot_root_rel"]
    data = component.load_inputs(params, snap, snap / s["membership"])
    data = ev.apply_filter(data, s["instrument_filter"]["include_market_ids"])
    res0 = component.compute_component(params, data)
    d1 = copy.copy(data)
    d1["daily"] = noise_after(data["daily"], cut, rng, 0.02)
    si = {}
    for k, v in data["signal_inputs"].items():
        vt = v.copy(); vt.index = v.index.to_timestamp(how="end").normalize()
        vt = noise_after(vt, cut, rng, 0.1, 0.05); vt.index = v.index; si[k] = vt
    d1["signal_inputs"] = si
    ser = {}
    for k, v in data["series"].items():
        vt = v.copy(); vt.index = v.index.to_timestamp(how="end").normalize()
        vt = noise_after(vt, cut, rng, 0.02, 0.03); vt.index = v.index; ser[k] = vt
    d1["series"] = ser
    res1 = component.compute_component(params, d1)
    W0, W1 = res0["W"], res1["W"].reindex_like(res0["W"])
    sigmax = (cut.to_period("M") - 1) if not cut.is_month_end else cut.to_period("M")
    s0 = {"net": res0["net"]["ret"], "control": res0["control"]["net"]}
    s1 = {"net": res1["net"]["ret"], "control": res1["control"]["net"]}
    return check(W0.to_numpy(), W1.to_numpy(), W0.index, sigmax, "builder_engine", s0, s1, safe_label_max(cut))


if __name__ == "__main__":
    out = []
    for cut in CUTS:
        for fn in (repro_side, builder_side):
            res = fn(cut, np.random.default_rng(7))
            res["cut"] = str(cut.date()); out.append(res); print(json.dumps(res))
    json.dump(out, open(f"{ROOT}/reports/cycle7_new_samples/audit/repro/lookahead_results.json", "w"), indent=1)
