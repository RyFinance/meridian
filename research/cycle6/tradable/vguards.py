"""Variant guards: the same semantics as research/cycle6/engine/guards.py (and reusing its ledger/trial functions,
including the pytest-only ledger overrides), with one addition -- the variant code hash.

Before anything is computed:
 (a) sha256(spec bytes) must be the SHA-256 cell of a prereg-ledger row whose ID cell equals params["id"];
 (b) exactly one ```json params block; params["schema"] == "cycle6-variant-v1";
 (c) engine hash (research/cycle6/engine/*.py, used read-only for panel/inference) == params["engine_sha256"];
 (d) variant code hash = sha256 over the concatenated bytes of research/cycle6/tradable/*.py sorted by file name
     (byte order) == params["code_sha256"];
 (e) snapshot manifest (<snapshot_root>/../manifest.json re-hashed; QUANT_DATA_MANIFEST_SHA256 if set) ==
     params["snapshot_manifest_sha256"];
 (f) no earlier trial-ledger row for this spec hash unless --bugfix-entry names an unused prereg-ledger row;
 then a 'started' row (kind 'variant') is appended, and an 'ok'/'failed' row on completion.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from research.cycle6.engine import guards as eg

CODE_DIR = Path(__file__).resolve().parent
SCHEMA = "cycle6-variant-v1"
GuardError = eg.GuardError


def code_sha256(code_dir: Path = CODE_DIR) -> str:
    h = hashlib.sha256()
    for p in sorted(Path(code_dir).glob("*.py"), key=lambda q: q.name.encode()):
        h.update(p.read_bytes())
    return h.hexdigest()


def check_code(params: dict) -> str:
    actual = code_sha256()
    if params.get("code_sha256") != actual:
        raise GuardError(f"variant code hash mismatch: spec {params.get('code_sha256')} != code {actual}")
    return actual


def preflight(spec_path, snapshot_root, bugfix_entry) -> tuple[dict, dict]:
    spec_bytes = Path(spec_path).read_bytes()
    spec_sha = hashlib.sha256(spec_bytes).hexdigest()
    params = eg.parse_params(spec_bytes.decode("utf-8"))
    if "id" not in params:
        raise GuardError("params missing 'id'")
    if params.get("schema") != SCHEMA:
        raise GuardError(f"params schema must be {SCHEMA}")
    eg.check_spec_ledgered(spec_sha, params["id"])
    eng = eg.check_engine(params)
    code = check_code(params)
    snap = eg.check_snapshot(params, snapshot_root)
    eg.check_no_prior_run(spec_sha, bugfix_entry)
    base = {"kind": "variant", "id": params["id"], "spec_sha256": spec_sha, "engine_sha256": eng,
            "snapshot_manifest_sha256": snap, "bugfix_entry": bugfix_entry or ""}
    return params, {**base, "code_sha256": code}


def append_trial(row: dict) -> None:
    """Trial-ledger row (engine columns; the variant code hash goes into the summary cell)."""
    r = dict(row)
    code = r.pop("code_sha256", None)
    if code:
        r["summary"] = (f"code_sha256={code} " + r.get("summary", "")).strip()
    eg.append_trial(r)
