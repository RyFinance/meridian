"""CLI entry points (guards first, then compute, then outputs). Wrapped by research/cycle6/run_component.py and
research/cycle6/run_book.py.

  python -m research.cycle6.run_component --spec research/cycle6/specs/<ID>.md \
      --snapshot-root {snapshot_root} --membership {membership_path} \
      --out reports/cycle6_core_premia/components/<ID>/ [--bugfix-entry <prereg ledger ID>]
  python -m research.cycle6.run_book --spec research/cycle6/specs/BOOK.md --snapshot-root {snapshot_root} \
      --membership {membership_path} --out reports/cycle6_core_premia/book/ [--bugfix-entry ID]
"""
from __future__ import annotations

import argparse
import json
import traceback
from pathlib import Path

import pandas as pd

from . import book as ebook
from . import component, guards, inference, panel, portfolio
from . import io as eio


def _write_frame(df: pd.DataFrame | pd.Series, path: Path) -> None:
    d = df.to_frame() if isinstance(df, pd.Series) else df.copy()
    d.index = [str(i) for i in d.index]
    d.index.name = "month"
    d.to_csv(path)


def _prepare_out(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    if (out / "metrics.json").exists():
        raise guards.GuardError(f"output directory already holds a run: {out}")


def write_component_outputs(res: dict, out: Path, run_info: dict) -> None:
    _write_frame(res["gross"], out / "gross.csv")
    _write_frame(res["net"], out / "net.csv")
    _write_frame(res["stress"], out / "net_stress.csv")
    _write_frame(res["control"], out / "control.csv")
    _write_frame(res["active"], out / "active.csv")
    portfolio.weights_long(res["W"]).to_parquet(out / "weights.parquet", index=False)
    (out / "metrics.json").write_text(json.dumps({**res["metrics"], "run": run_info}, indent=1, sort_keys=True))


def main_component(argv=None) -> int:
    ap = argparse.ArgumentParser(description="cycle-6 component runner")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--snapshot-root", required=True)
    ap.add_argument("--membership", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--bugfix-entry", default=None)
    a = ap.parse_args(argv)
    params, base = guards.preflight(a.spec, a.snapshot_root, a.bugfix_entry, "component")
    if params.get("schema") != "cycle6-component-v1":
        raise guards.GuardError("params schema must be cycle6-component-v1")
    out = Path(a.out)
    _prepare_out(out)
    guards.append_trial({**base, "utc": guards.utc(), "status": "started"})
    try:
        data = component.load_inputs(params, a.snapshot_root, a.membership)
        res = component.compute_component(params, data)
        write_component_outputs(res, out, {**base, "spec": str(a.spec)})
        m = res["metrics"]
        summ = (f"fidelity={'PASS' if m['fidelity']['pass'] else 'FAIL'} "
                f"post_sharpe={m['net_post'].get('sharpe_ann')} p_active_post={m['active_post']['p'].get('p')}")
        guards.append_trial({**base, "utc": guards.utc(), "status": "ok", "summary": summ})
    except Exception as exc:
        guards.append_trial({**base, "utc": guards.utc(), "status": "failed",
                             "summary": f"{type(exc).__name__}: {str(exc)[:200]}"})
        traceback.print_exc()
        return 1
    return 0


# ------------------------------------------------------------------------------------------------ book
def _read_month_csv(p: Path) -> pd.DataFrame:
    d = pd.read_csv(p, index_col=0)
    d.index = pd.PeriodIndex(d.index.astype(str), freq="M")
    return d


def load_sleeves(params: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    root = guards.REPO / params["components_root"]
    trials = guards.read_trials()
    net, gross, info = {}, {}, {}
    for cid in params["candidates"]:
        d = root / cid
        mpath = d / "metrics.json"
        if not mpath.exists():
            info[cid] = {"included": False, "reason": "no component output"}
            continue
        m = json.loads(mpath.read_text())
        ok = [t for t in trials if t["id"] == cid and t["status"] == "ok"
              and t["spec_sha256"] == m.get("run", {}).get("spec_sha256")]
        if not ok:
            info[cid] = {"included": False, "reason": "no ok trial-ledger row matching the output"}
            continue
        if not m["fidelity"]["pass"]:
            info[cid] = {"included": False, "reason": "fidelity FAIL"}
            continue
        n = _read_month_csv(d / "net.csv")
        net[cid], gross[cid] = n["ret"], n["gross_exposure"]
        info[cid] = {"included": True, "post_pub_cutoff": m["post_pub_cutoff"],
                     "net_csv_sha256": guards.sha256_file(d / "net.csv")}
    return pd.DataFrame(net), pd.DataFrame(gross), info


def core_sleeve(params: dict, snapshot_root) -> tuple[pd.Series, pd.Series]:
    """Fixed-weight core, monthly rebalanced at the next session. A5 §E: no backfill -- the core is defined only
    in holding months m where every core market has a period return and a return in calendar month m-1 (so it
    was trading before the entry close); it is entered (and charged) in its first such month."""
    c = params["core"]
    daily = eio.read_wide(snapshot_root, c["daily_excess"], c["markets"]).dropna(how="all")
    rnet = panel.net_period_returns(daily)[c["markets"]]
    months = rnet.index
    prior = panel.monthly_returns(daily)[c["markets"]].shift(1).reindex(months)
    full = (rnet.notna() & prior.notna()).all(axis=1)   # traded through the prior month and in this period
    hold_next = full.shift(-1, fill_value=False).astype(bool)
    W = pd.DataFrame([c["weights"]] * len(months), index=months, columns=c["markets"]).where(hold_next, 0.0)
    rate = pd.Series({m: c["cost_bp_per_side"] / 1e4 for m in c["markets"]})
    net = portfolio.net_implementable(W, rnet, rate, hold_next, drift=True)
    ok = full.reindex(net.index, fill_value=False)
    return net["ret"].where(ok).dropna(), net["gross_exposure"].where(ok).dropna()


def compute_book(params: dict, snapshot_root) -> dict:
    net, gross, info = load_sleeves(params)
    core, core_g = core_sleeve(params, snapshot_root)
    net["CORE"], gross["CORE"] = core, core_g
    idx = pd.period_range(net.index.min(), net.index.max(), freq="M")
    net, gross = net.reindex(idx), gross.reindex(idx)
    for col in net.columns:   # a sleeve enters from its first defined month (no backfill)
        fv = net[col].first_valid_index()
        info.setdefault(col, {"included": True})["first_defined_month"] = None if fv is None else str(fv)
    tb = component.load_series_monthly(snapshot_root, params["tbill"], None).reindex(idx)
    bk, wts = ebook.build_book(net, tb, params["book"], gross=gross)
    cut = max([pd.Period(v["post_pub_cutoff"], "M") for v in info.values()
               if v.get("included") and v.get("post_pub_cutoff")] or
              [pd.Period(params["core"]["post_pub_cutoff"], "M")])
    x = bk["excess"][bk["method"] != "cash"]
    first = x.index.min() if len(x) else bk.index.min()
    bk = bk[bk.index >= first]
    post = bk["excess"][bk.index >= cut]
    inf = params["inference"]
    ci_full = inference.calibrated_ci(bk["excess"], level=inf["ci_level"], B=inf["ci_B"], seed=inf["seed"])
    ci_post = inference.calibrated_ci(post, level=inf["ci_level"], B=inf["ci_B"], seed=inf["seed"])
    lc = params["leverage_calc"]
    tb_post = float(tb.reindex(post.index).mean()) if len(post) else float("nan")
    lev = ebook.leverage_for_target(post, tb_post, target_total_ann=lc["target_total_ann"],
                                    lcb_level=lc["lcb_level"], cash_spread=params["book"]["cash_spread"],
                                    financing_spread=params["book"]["financing_spread"], cap=lc["cap"],
                                    n_draws=lc["n_draws"], mean_block=lc["mean_block"], seed=lc["seed"])
    ms = params["mdd_sim"]
    mdd = ebook.mdd_simulation(bk["excess"].to_numpy(), n_paths=ms["n_paths"], horizon=ms["horizon_months"],
                               mean_block=ms["mean_block"], seed=ms["seed"])
    lo = ci_post.get("sharpe_ann", {}).get("lo")
    hi = ci_post.get("sharpe_ann", {}).get("hi")
    metrics = {"id": params["id"], "sleeves": info, "post_pub_cutoff": str(cut),
               "full": {**inference.basic_stats(bk["excess"]), "ci": ci_full},
               "post": {**inference.basic_stats(post), "ci": ci_post},
               "total_return_full": inference.basic_stats(bk["total"].dropna()),
               "years_post": inference.calendar_years(post),
               "method_counts": bk["method"].value_counts().to_dict(),
               "mean_gross": float(bk["gross"].mean()), "max_gross": float(bk["gross"].max()),
               "leverage_for_12pct": lev, "mdd_simulation": mdd,
               "positive": None if lo is None else bool(lo > 0 or hi < 0),
               "positive_rule": "post-pub net Sharpe calibrated 90% CI excludes zero (FRAMEWORK §6)"}
    return {"book": bk, "weights": wts, "sleeves": net, "metrics": component._clean(metrics)}


def main_book(argv=None) -> int:
    ap = argparse.ArgumentParser(description="cycle-6 book runner")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--snapshot-root", required=True)
    ap.add_argument("--membership", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--bugfix-entry", default=None)
    a = ap.parse_args(argv)
    params, base = guards.preflight(a.spec, a.snapshot_root, a.bugfix_entry, "book")
    if params.get("schema") != "cycle6-book-v1":
        raise guards.GuardError("params schema must be cycle6-book-v1")
    out = Path(a.out)
    _prepare_out(out)
    guards.append_trial({**base, "utc": guards.utc(), "status": "started"})
    try:
        res = compute_book(params, a.snapshot_root)
        _write_frame(res["book"], out / "book.csv")
        _write_frame(res["sleeves"], out / "sleeves.csv")
        res["weights"].to_csv(out / "weights.csv", index=False)
        (out / "metrics.json").write_text(json.dumps({**res["metrics"], "run": {**base, "spec": str(a.spec)}},
                                                     indent=1, sort_keys=True))
        m = res["metrics"]
        guards.append_trial({**base, "utc": guards.utc(), "status": "ok",
                             "summary": f"post_sharpe={m['post'].get('sharpe_ann')} positive={m['positive']}"})
    except Exception as exc:
        guards.append_trial({**base, "utc": guards.utc(), "status": "failed",
                             "summary": f"{type(exc).__name__}: {str(exc)[:200]}"})
        traceback.print_exc()
        return 1
    return 0
