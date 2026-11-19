"""Sample-spec parsing, preregistration guards and the data-location-only parameter mapping.

Sample file: research/cycle7/samples/<SPEC>__<SAMPLE>.md holding exactly one ```json block:
  {"schema": "cycle7-sample-v1", "spec_id", "spec_path", "spec_sha256", "sample_id",
   "snapshot_root_rel", "snapshot_manifest_sha256", "membership",
   "input_map": {<input key or original path>: <new path relative to the snapshot root>},
   "instrument_filter": {"class": <spec class>, "include_market_ids": [...]  |  "exclude_market_ids": [...]
                         | neither (= every PASS row of the class), "instrument_list_sha256": optional},
   "month_window": {"start": null | "YYYY-MM", "end_exclusive": null | "YYYY-MM"},
   "seeds_offsets": [0, 1, 2, 3, 4], "cost_mult_sensitivity": 2}
Paths: spec_path and snapshot_root_rel are repo-relative; membership is relative to the snapshot root.
input_map keys: "daily_excess", "signal_inputs.<name>", "series.<name>", or an ORIGINAL spec path (replaces every
occurrence). Values: a relative path; for "series.<name>" also {"path", "market_id"} (both location keys) or null,
null only for a diagnostic series (used solely by "betas"/"fidelity", never by the signal): it is then not loaded.
Every input location of the spec must be covered by the map.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from research.cycle6.engine import guards as eguards

from . import common
from .common import GuardError

SCHEMA = "cycle7-sample-v1"
REQUIRED = ("schema", "spec_id", "spec_path", "spec_sha256", "sample_id", "snapshot_root_rel",
            "snapshot_manifest_sha256", "membership", "input_map", "instrument_filter", "month_window",
            "seeds_offsets", "cost_mult_sensitivity")


def parse_sample(text: str) -> dict:
    try:
        s = eguards.parse_params(text)
    except eguards.GuardError as exc:
        raise GuardError(f"sample file: {exc}") from exc
    missing = [k for k in REQUIRED if k not in s]
    if missing:
        raise GuardError(f"sample missing keys {missing}")
    if s["schema"] != SCHEMA:
        raise GuardError(f"sample schema must be {SCHEMA}")
    mw = s["month_window"]
    if not isinstance(mw, dict) or set(mw) != {"start", "end_exclusive"}:
        raise GuardError("month_window must be {'start': ..., 'end_exclusive': ...}")
    if not s["seeds_offsets"] or len(set(s["seeds_offsets"])) != len(s["seeds_offsets"]):
        raise GuardError("seeds_offsets must be a non-empty list of distinct ints")
    if s["seeds_offsets"][0] != 0:
        raise GuardError("seeds_offsets must start with 0 (the spec's own seed is the headline)")
    return s


# ------------------------------------------------------------------------------------------------ guards
def preflight(sample_path) -> dict:
    """Guards (a)-(f), all before any computation. Returns a context dict."""
    root = common.repo_root()
    sample_path = Path(sample_path)
    sbytes = sample_path.read_bytes()
    sample_sha = common.sha256_bytes(sbytes)
    s = parse_sample(sbytes.decode("utf-8"))
    spec_id, sample_id = s["spec_id"], s["sample_id"]
    run_id = f"{spec_id}__{sample_id}"
    if spec_id not in common.FROZEN_SPECS:
        raise GuardError(f"spec {spec_id} is not one of the six frozen cycle-7 specs")
    if sample_path.name != f"{run_id}.md":
        raise GuardError(f"sample file must be named {run_id}.md")
    c7 = common.prereg_ledger_path()
    c7rows = common.ledger_rows(c7)
    # (a) sample hash ledgered under ID <SPEC>__<SAMPLE>
    if not any(r["sha256"] == sample_sha and r["id"] == run_id for r in c7rows):
        raise GuardError(f"sample hash {sample_sha} is not in the cycle-7 prereg ledger under ID {run_id}")
    # (b) spec bytes == sample spec_sha256 == cycle-6 ledger == cycle-7 ledger
    spec_path = root / s["spec_path"]
    spec_bytes = spec_path.read_bytes()
    spec_sha = common.sha256_bytes(spec_bytes)
    if spec_sha != s["spec_sha256"]:
        raise GuardError(f"spec hash mismatch: file {spec_sha} != sample spec_sha256 {s['spec_sha256']}")
    if not any(r["sha256"] == spec_sha and r["id"] == spec_id for r in common.ledger_rows(common.cycle6_ledger_path())):
        raise GuardError(f"spec hash {spec_sha} is not in the cycle-6 prereg ledger under {spec_id}")
    if not any(r["sha256"] == spec_sha and r["id"] == spec_id for r in c7rows):
        raise GuardError(f"spec hash {spec_sha} is not in the cycle-7 prereg ledger under {spec_id}")
    params = eguards.parse_params(spec_bytes.decode("utf-8"))
    if params.get("id") != spec_id:
        raise GuardError(f"spec params id {params.get('id')} != sample spec_id {spec_id}")
    if params.get("schema") != "cycle6-component-v1":
        raise GuardError("spec params schema must be cycle6-component-v1")
    # (c) engine
    eng = common.dir_py_sha256(common.engine_dir())
    if eng != common.ENGINE_SHA256 or params.get("engine_sha256") != common.ENGINE_SHA256:
        raise GuardError(f"engine hash mismatch: code {eng}, spec {params.get('engine_sha256')}, "
                         f"frozen {common.ENGINE_SHA256}")
    # (d) snapshot manifest (frozen cycle-6 canonical-payload check) and ledgered
    snap_root = root / s["snapshot_root_rel"]
    try:
        snap = eguards.snapshot_manifest_sha(snap_root)
    except eguards.GuardError as exc:
        raise GuardError(str(exc)) from exc
    if snap != s["snapshot_manifest_sha256"]:
        raise GuardError(f"snapshot manifest mismatch: sample {s['snapshot_manifest_sha256']} != {snap}")
    if not any(r["sha256"] == snap for r in c7rows):
        raise GuardError(f"snapshot manifest {snap} is not in the cycle-7 prereg ledger")
    # (f) runner code hash ledgered (FRAMEWORK §6)
    rsha = common.runner_sha256()
    if not any(r["sha256"] == rsha for r in c7rows):
        raise GuardError(f"runner code hash {rsha} is not in the cycle-7 prereg ledger")
    # (e) one run per spec x sample
    prior = [t for t in common.read_trials() if t.get("status") in ("started", "ok")
             and (t.get("sample_sha256") == sample_sha or (t.get("spec_id"), t.get("sample_id")) == (spec_id, sample_id))]
    if prior:
        raise GuardError(f"a started/ok run already exists for {run_id} (sample hash {sample_sha})")
    # parameter mapping (data-location keys only) -- still before any computation
    new_params, dropped = map_params(params, s)
    membership = snap_root / s["membership"]
    return {"sample": s, "sample_sha256": sample_sha, "spec_sha256": spec_sha, "engine_sha256": eng,
            "runner_sha256": rsha, "snapshot_manifest_sha256": snap, "snapshot_root": snap_root,
            "membership": membership, "params_spec": params, "params": new_params, "dropped_series": dropped,
            "run_id": run_id}


# ------------------------------------------------------------------------------------------------ mapping
def _signal_names(params: dict) -> set:
    out = set()

    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, str):
            out.add(o)
    walk(params.get("signal", {}))
    return out


def _diagnostic_series(params: dict) -> set:
    fid = params.get("fidelity", {}) or {}
    d = set(params.get("betas", []) or [])
    for k in ("reference", "secondary_reference"):
        if fid.get(k):
            d.add(fid[k])
    return d - _signal_names(params)


def _locations(params: dict) -> list[tuple[str, str]]:
    inp = params["inputs"]
    locs = [("daily_excess", inp["daily_excess"])]
    locs += [(f"signal_inputs.{k}", v) for k, v in (inp.get("signal_inputs") or {}).items()]
    locs += [(f"series.{k}", v["path"]) for k, v in (inp.get("series") or {}).items()]
    return locs


def _strip(params: dict, drop: set) -> dict:
    p = copy.deepcopy(params)
    p.pop("snapshot_manifest_sha256", None)
    inp = p["inputs"]
    inp["daily_excess"] = None
    inp["signal_inputs"] = {k: None for k in (inp.get("signal_inputs") or {})}
    inp["series"] = {k: {kk: vv for kk, vv in v.items() if kk not in ("path", "market_id")}
                     for k, v in (inp.get("series") or {}).items() if k not in drop}
    return p


def _check_rel(v: str, key: str) -> str:
    if not isinstance(v, str) or not v or Path(v).is_absolute() or ".." in Path(v).parts:
        raise GuardError(f"input_map[{key!r}] must be a relative path inside the snapshot")
    return v


def map_params(params: dict, sample: dict) -> tuple[dict, list]:
    """Replace ONLY data-location keys; deep-compare everything else. Returns (new params, dropped series)."""
    imap = sample["input_map"]
    if not isinstance(imap, dict):
        raise GuardError("input_map must be an object")
    locs = _locations(params)
    keys = {k for k, _ in locs}
    paths = {v for _, v in locs}
    new = copy.deepcopy(params)
    inp = new["inputs"]
    covered, dropped = set(), []
    diag = _diagnostic_series(params)

    def set_loc(key, val):
        if key == "daily_excess":
            inp["daily_excess"] = _check_rel(val, key)
        elif key.startswith("signal_inputs."):
            inp["signal_inputs"][key.split(".", 1)[1]] = _check_rel(val, key)
        else:
            name = key.split(".", 1)[1]
            if val is None:
                if name not in diag:
                    raise GuardError(f"series {name!r} is used by the signal; it cannot be dropped")
                inp["series"].pop(name)
                dropped.append(name)
            elif isinstance(val, dict):
                if set(val) - {"path", "market_id"} or "path" not in val:
                    raise GuardError(f"input_map[{key!r}] may only set 'path' and 'market_id'")
                inp["series"][name]["path"] = _check_rel(val["path"], key)
                if "market_id" in val:
                    inp["series"][name]["market_id"] = str(val["market_id"])
            else:
                inp["series"][name]["path"] = _check_rel(val, key)
        covered.add(key)

    for k, v in imap.items():   # key-addressed entries first; they win over path-addressed ones
        if k in keys:
            set_loc(k, v)
    for k, v in imap.items():
        if k in keys:
            continue
        if k not in paths:
            raise GuardError(f"input_map key {k!r} is neither a spec input key nor a spec input path")
        for key, orig in locs:
            if orig == k and key not in covered:
                set_loc(key, v)
    missing = sorted(keys - covered)
    if missing:
        raise GuardError(f"input_map does not cover spec inputs {missing}")
    new["snapshot_manifest_sha256"] = sample["snapshot_manifest_sha256"]
    if _strip(params, set(dropped)) != _strip(new, set(dropped)):
        raise GuardError("parameter drift: a non-location key differs from the frozen spec")
    if json.dumps(sorted(new.keys())) != json.dumps(sorted(params.keys())):
        raise GuardError("parameter drift: top-level keys differ")
    return new, dropped


def assert_no_drift(orig: dict, new: dict, dropped=()) -> None:
    """Public deep-compare used by run_sample right before compute (and by tests)."""
    if _strip(orig, set(dropped)) != _strip(new, set(dropped)):
        raise GuardError("parameter drift: a non-location key differs from the frozen spec")
