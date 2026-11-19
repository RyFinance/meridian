"""Cycle-7 run of ONE frozen cycle-6 spec on ONE new sample (FRAMEWORK §4, §6).

  python -m research.cycle7.runner.run_sample --sample research/cycle7/samples/<SPEC>__<SAMPLE>.md \
      --out reports/cycle7_new_samples/runs/<SPEC>__<SAMPLE>/

Order: guards (sample ledgered, spec hash x3, engine hash, snapshot manifest, runner hash ledgered, no prior
started/ok run) -> 'started' trial row -> frozen component.load_inputs from the sample's snapshot view with the
location-mapped params -> mechanical instrument filter -> frozen component.compute_component (full history, spec
params) -> window metrics (evaluate.py) -> outputs -> 'ok' (or 'failed') trial row.
"""
from __future__ import annotations

import argparse
import json
import traceback
from pathlib import Path

import pandas as pd

from research.cycle6.engine import component
from research.cycle6.engine.component import _clean

from . import common, evaluate
from . import sample as smp
from .common import GuardError


def _write_frame(df, path: Path) -> None:
    d = df.to_frame() if isinstance(df, pd.Series) else df.copy()
    d.index = [str(i) for i in d.index]
    d.index.name = "month"
    d.to_csv(path)


def run(sample_path, out) -> dict:
    ctx = smp.preflight(sample_path)
    out = Path(out)
    if (out / "metrics.json").exists():
        raise GuardError(f"output directory already holds a run: {out}")
    s, params = ctx["sample"], ctx["params"]
    # instrument list from the membership file only (no returns read yet)
    ids = evaluate.filtered_universe(ctx["snapshot_root"], ctx["membership"], params, s["instrument_filter"])
    ilsha = common.instrument_list_sha256(ids)
    want = s["instrument_filter"].get("instrument_list_sha256")
    if want and want != ilsha:
        raise GuardError(f"instrument list hash mismatch: sample {want} != filtered {ilsha}")
    smp.assert_no_drift(ctx["params_spec"], params, ctx["dropped_series"])
    base = {"kind": "cycle7-sample", "spec_id": s["spec_id"], "sample_id": s["sample_id"],
            "sample_sha256": ctx["sample_sha256"], "spec_sha256": ctx["spec_sha256"],
            "engine_sha256": ctx["engine_sha256"], "runner_sha256": ctx["runner_sha256"],
            "snapshot_manifest_sha256": ctx["snapshot_manifest_sha256"], "instrument_list_sha256": ilsha}
    out.mkdir(parents=True, exist_ok=True)
    common.append_trial({**base, "utc": common.utc(), "status": "started"})
    try:
        data = component.load_inputs(params, ctx["snapshot_root"], ctx["membership"])
        data = evaluate.apply_filter(data, ids)
        res = component.compute_component(params, data)
        m, frames = evaluate.window_metrics(res, params, s, ids)
        for name, fr in frames.items():
            _write_frame(fr, out / f"{name}.csv")
        metrics = _clean({"schema": "cycle7-run-v1", "spec_id": s["spec_id"], "sample_id": s["sample_id"],
                          "run": {**base, "sample": str(sample_path), "dropped_diagnostic_series": ctx["dropped_series"],
                                  "input_map": s["input_map"], "instrument_filter": s["instrument_filter"]},
                          **m})
        (out / "metrics.json").write_text(json.dumps(metrics, indent=1, sort_keys=True))
        a = metrics["active"]
        summ = (f"n={metrics['n_months']} sharpe={a.get('sharpe_ann')} p={a['p'].get('p')} "
                f"p_seeds={[x['p'].get('p') for x in metrics['seeds']]} "
                f"mean_c{s['cost_mult_sensitivity']}={metrics['cost_sensitivity']['active'].get('mean_m')}")
        common.append_trial({**base, "utc": common.utc(), "status": "ok", "summary": summ})
        return metrics
    except Exception as exc:
        common.append_trial({**base, "utc": common.utc(), "status": "failed",
                             "summary": f"{type(exc).__name__}: {str(exc)[:200]}"})
        raise


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="cycle-7 new-sample runner (frozen cycle-6 engine)")
    ap.add_argument("--sample", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    try:
        run(a.sample, a.out)
    except GuardError:
        raise
    except Exception:
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
