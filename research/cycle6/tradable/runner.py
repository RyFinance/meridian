"""Variant runner (guards first, then compute, then outputs).

  python -m research.cycle6.tradable.runner --spec research/cycle6/specs/TRADE-ETF-LF.md \
      --snapshot-root {snapshot_root} --membership {membership_path} \
      --out reports/cycle6_core_premia/variants/TRADE-ETF-LF/ [--bugfix-entry <prereg ledger ID>]

Scenarios (all fixed by the spec): for each account type x funding currency x account size (CAD) an integer-
rounded path, plus one unrounded ("ideal") path per account type x funding currency at the headline size, plus the
spec's sensitivities at the headline scenario. Every scenario is reported; the headline is named in the spec.
"""
from __future__ import annotations

import argparse
import copy
import json
import traceback
from pathlib import Path

import pandas as pd

from research.cycle6.engine import component as ecomp
from research.cycle6.engine import io as eio

from . import data as vdata
from . import mapping, report, sim, vguards


def load_book(params: dict, root) -> dict:
    inp = params["inputs"]
    bm = json.loads(eio.resolve(root, inp["book_metrics"]).read_text())
    if bm.get("run", {}).get("spec_sha256") != params["book_spec_sha256"]:
        raise vguards.GuardError("frozen BOOK output does not come from the ledgered BOOK spec hash")
    included = sorted(k for k, v in bm["sleeves"].items() if v.get("included"))
    declared = sorted(list(inp["components"]) + [inp["core"]["sleeve"]])
    if included != declared:
        raise vguards.GuardError(f"BOOK included sleeves {included} != spec sleeves {declared}")
    bw = pd.read_csv(eio.resolve(root, inp["book_weights"]))
    bk = pd.read_csv(eio.resolve(root, inp["book_csv"]), index_col=0)
    bk.index = pd.PeriodIndex(bk.index.astype(str), freq="M")
    comp = {s: pd.read_parquet(eio.resolve(root, p)) for s, p in inp["components"].items()}
    return {"weights": bw, "book": bk, "comp": comp, "metrics": bm}


def scenarios(params: dict, L0: float) -> list[dict]:
    out = []
    c = params["costs"]
    head = params["headline"]
    for acct in params["accounts"]:
        for F in params["funding"]:
            for size in params["sizes_cad"] + ["ideal"]:
                rounded = size != "ideal"
                cap_cad = size if rounded else head["size_cad"]
                out.append({"name": f"{acct}_{F}_{size if rounded else 'ideal'}", "account": acct, "F": F,
                            "size_cad": cap_cad, "rounded": rounded, "conv_rate": c["conv_rate"],
                            "spread_mult": 1.0, "borrow_mult": 1.0, "withholding_overrides": {}})
    base = next(s for s in out if s["account"] == head["account"] and s["F"] == head["F"]
                and s["size_cad"] == head["size_cad"] and s["rounded"])
    for sens in params.get("sensitivities", []):
        s = copy.deepcopy(base)
        s.update({k: v for k, v in sens.items() if k != "name"})
        s["name"] = f"SENS_{sens['name']}"
        out.append(s)
    for s in out:
        s["capital"] = s["size_cad"] if s["F"] == "CAD" else s["size_cad"] / L0
    return out


def compute_variant(params: dict, root, membership) -> dict:
    params = copy.deepcopy(params)
    params["_vehicle_status"] = vdata.vehicle_status(root, membership)
    b = load_book(params, root)
    X = mapping.instrument_weights(b["weights"], b["comp"], params["inputs"]["core"])
    X = X.reindex(b["book"].index).fillna(0.0)
    mkt = vdata.load_market(params, root)
    Y, info, drops, chosen = mapping.vehicle_targets(X, params["mapping"], mkt["available"],
                                                     long_only=params["long_only"], gross_cap=params["gross_cap"])
    first = mapping.first_active_month(Y)
    if first is None:
        raise ValueError("variant never holds a vehicle")
    Yv = Y[Y.index >= first]
    meta = params["vehicles"]
    for v in Yv.columns:
        if v not in meta:
            raise ValueError(f"vehicle {v} has no spec entry")
    L0 = float(mkt["L"].get(first))
    post = params["post_pub_cutoff"]
    inf = params["inference"]
    book_x = b["book"]["excess"]
    res, series = {}, {}
    ideal = {}
    for s in scenarios(params, L0):
        acc = params["accounts"][s["account"]]
        wht = {**acc["withholding"], **s.get("withholding_overrides", {})}
        acct = {"F": s["F"], "capital": s["capital"], "rounded": s["rounded"], "withholding": wht,
                "creditable": acc.get("creditable", {}), "conv_rate": s["conv_rate"],
                "cash_spread": params["costs"]["cash_spread"], "financing_spread": params["costs"]["financing_spread"],
                "spread_mult": s["spread_mult"], "borrow_mult": s["borrow_mult"]}
        fr, q = sim.simulate(Yv, mkt, meta, acct)
        series[s["name"]] = fr
        blk = {"scenario": {k: s[k] for k in ("account", "F", "size_cad", "capital", "rounded", "conv_rate",
                                              "spread_mult", "borrow_mult", "withholding_overrides")},
               **report.series_block(fr, post, inf)}
        if s["F"] == "USD":
            blk["tracking_vs_paper_book"] = report.tracking(fr["excess"], book_x, post)
        if not s["rounded"]:
            ideal[(s["account"], s["F"])] = fr
        res[s["name"]] = blk
    for name, fr in series.items():
        sc = res[name]["scenario"]
        if sc["rounded"] and not name.startswith("SENS_"):
            res[name]["rounding_vs_unrounded"] = report.rounding_block(fr, ideal[(sc["account"], sc["F"])], post)
    Rp = vdata.paper_instrument_returns(params, root)
    dec = mapping.paper_decomposition(X, Rp)
    dd = pd.concat([dec, b["book"]["sleeve_ret"]], axis=1, join="inner").dropna()
    head = params["headline"]
    hname = f"{head['account']}_{head['F']}_{head['size_cad']}"
    metrics = {"id": params["id"], "variant": params["variant"], "headline": hname,
               "headline_post_sharpe_ci": res[hname]["post"]["ci"],
               "post_pub_cutoff": post, "first_active_month": str(first), "last_month": str(Yv.index[-1]),
               "vehicle_first_available_month": mkt["first_month"],
               "dropped_instrument_mean_abs_weight": report.drop_summary(
                   drops[drops["month"] >= str(first)] if len(drops) else drops, X[X.index >= first], post),
               "mapping_info_means": {c: float(info.loc[info.index >= first, c].mean()) for c in info.columns},
               "paper_decomposition_check": {"n": len(dd), "corr_vs_book_sleeve_ret":
                                             float(dd.corr().iloc[0, 1]) if len(dd) > 2 else None,
                                             "mean_abs_diff": float((dd.iloc[:, 0] - dd.iloc[:, 1]).abs().mean())
                                             if len(dd) else None},
               "paper_book_same_window": {"full": report.inference.basic_stats(book_x[book_x.index >= first]),
                                          "post": report.inference.basic_stats(book_x[book_x.index >= pd.Period(post, "M")])},
               "scenarios": res}
    return {"X": X, "Y": Y, "info": info, "drops": drops, "chosen": chosen, "series": series,
            "metrics": ecomp._clean(metrics)}


def write_outputs(res: dict, out: Path, run_info: dict) -> None:
    (out / "series").mkdir(parents=True, exist_ok=True)
    for name, fr in res["series"].items():
        d = fr.copy()
        d.index = [str(i) for i in d.index]
        d.index.name = "month"
        d.to_csv(out / "series" / f"{name}.csv")
    for key in ("X", "Y", "info"):
        d = res[key].copy()
        d.index = [str(i) for i in d.index]
        d.index.name = "month"
        d.to_csv(out / {"X": "instrument_targets.csv", "Y": "vehicle_targets.csv", "info": "mapping_info.csv"}[key])
    res["drops"].to_csv(out / "dropped.csv", index=False)
    res["chosen"].to_csv(out / "chosen_vehicles.csv", index=False)
    (out / "metrics.json").write_text(json.dumps({**res["metrics"], "run": run_info}, indent=1, sort_keys=True))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="cycle-6 tradable variant runner")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--snapshot-root", required=True)
    ap.add_argument("--membership", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--bugfix-entry", default=None)
    a = ap.parse_args(argv)
    params, base = vguards.preflight(a.spec, a.snapshot_root, a.bugfix_entry)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if (out / "metrics.json").exists():
        raise vguards.GuardError(f"output directory already holds a run: {out}")
    vguards.append_trial({**base, "utc": vguards.eg.utc(), "status": "started"})
    try:
        res = compute_variant(params, a.snapshot_root, a.membership)
        write_outputs(res, out, {**base, "spec": str(a.spec)})
        m = res["metrics"]
        h = m["scenarios"][m["headline"]]["post"]
        vguards.append_trial({**base, "utc": vguards.eg.utc(), "status": "ok",
                              "summary": f"headline={m['headline']} post_sharpe={h['excess'].get('sharpe_ann')} "
                                         f"ci90=[{h['ci'].get('sharpe_ann', {}).get('lo')},"
                                         f"{h['ci'].get('sharpe_ann', {}).get('hi')}]"})
    except Exception as exc:
        vguards.append_trial({**base, "utc": vguards.eg.utc(), "status": "failed",
                              "summary": f"{type(exc).__name__}: {str(exc)[:200]}"})
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    import sys
    try:
        sys.exit(main())
    except vguards.GuardError as exc:
        sys.exit(f"REFUSED: {exc}")
