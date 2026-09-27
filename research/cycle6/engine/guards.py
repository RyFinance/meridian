"""Preregistration guards shared by run_component / run_book (FRAMEWORK §8).

Before anything is computed:
 (a) sha256(spec bytes) must appear as the SHA-256 cell of a row of research/cycle6_prereg_ledger.md whose ID cell
     equals the spec's params "id";
 (b) exactly one fenced ```json block is parsed from the spec as params;
 (c) engine hash = sha256 over the concatenated bytes of research/cycle6/engine/*.py sorted by file name
     (byte order) must equal params["engine_sha256"];
 (d) the snapshot manifest hash (<snapshot_root>/../manifest.json, payload re-hashed, and the
     QUANT_DATA_MANIFEST_SHA256 set by `research.data_snapshot run` if present) must equal
     params["snapshot_manifest_sha256"];
 (e) research/cycle6/trial_ledger.csv must hold no earlier row for this spec hash, unless --bugfix-entry names a
     prereg-ledger row (ID cell) not yet used by any trial;
 then a 'started' row is appended, and an 'ok'/'failed' row on completion.
Ledger paths may be overridden by CYCLE6_TEST_PREREG_LEDGER / CYCLE6_TEST_TRIAL_LEDGER ONLY while pytest is
running (PYTEST_CURRENT_TEST set); otherwise an override raises.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent
REPO = ENGINE_DIR.parents[2]
PREREG_LEDGER = REPO / "research" / "cycle6_prereg_ledger.md"
TRIAL_LEDGER = REPO / "research" / "cycle6" / "trial_ledger.csv"
TRIAL_FIELDS = ["utc", "kind", "id", "spec_sha256", "engine_sha256", "snapshot_manifest_sha256", "status",
                "bugfix_entry", "summary"]


class GuardError(RuntimeError):
    """A preregistration guard refused the run."""


def _override(env: str, default: Path) -> Path:
    v = os.environ.get(env)
    if not v:
        return default
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        raise GuardError(f"{env} is a test-only override and is refused outside pytest")
    return Path(v)


def prereg_ledger_path() -> Path:
    return _override("CYCLE6_TEST_PREREG_LEDGER", PREREG_LEDGER)


def trial_ledger_path() -> Path:
    return _override("CYCLE6_TEST_TRIAL_LEDGER", TRIAL_LEDGER)


def sha256_file(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def engine_sha256(engine_dir: Path = ENGINE_DIR) -> str:
    h = hashlib.sha256()
    for p in sorted(Path(engine_dir).glob("*.py"), key=lambda q: q.name.encode()):
        h.update(p.read_bytes())
    return h.hexdigest()


def parse_params(spec_text: str) -> dict:
    blocks = re.findall(r"```json[ \t]*\n(.*?)\n```", spec_text, flags=re.S)
    if len(blocks) != 1:
        raise GuardError(f"spec must contain exactly one ```json params block (found {len(blocks)})")
    return json.loads(blocks[0])


def ledger_rows(path: Path) -> list[dict]:
    if not path.exists():
        raise GuardError(f"prereg ledger missing: {path}")
    rows = []
    for line in path.read_text().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 5 and re.fullmatch(r"[0-9a-f]{64}", cells[4] or ""):
            rows.append({"utc": cells[0], "kind": cells[1], "id": cells[2], "file": cells[3], "sha256": cells[4]})
    return rows


def check_spec_ledgered(spec_sha: str, spec_id: str) -> dict:
    rows = [r for r in ledger_rows(prereg_ledger_path()) if r["sha256"] == spec_sha]
    if not rows:
        raise GuardError(f"spec hash {spec_sha} is not in the prereg ledger")
    if not any(r["id"] == spec_id for r in rows):
        raise GuardError(f"spec hash is ledgered under {[r['id'] for r in rows]}, not {spec_id}")
    return rows[0]


def check_engine(params: dict) -> str:
    actual = engine_sha256()
    if params.get("engine_sha256") != actual:
        raise GuardError(f"engine hash mismatch: spec {params.get('engine_sha256')} != code {actual}")
    return actual


def snapshot_manifest_sha(snapshot_root) -> str:
    from research.data_snapshot import canonical
    env = os.environ.get("QUANT_DATA_MANIFEST_SHA256")
    mf = Path(snapshot_root).parent / "manifest.json"
    found = None
    if mf.exists():
        m = json.loads(mf.read_text())
        actual = hashlib.sha256(canonical(m["payload"])).hexdigest()
        if actual != m.get("manifest_sha256"):
            raise GuardError("snapshot manifest payload hash mismatch")
        found = actual
    if env and found and env != found:
        raise GuardError("QUANT_DATA_MANIFEST_SHA256 disagrees with the view's manifest")
    if not (found or env):
        raise GuardError("snapshot root is not a frozen research.data_snapshot view (no manifest)")
    return found or env


def check_snapshot(params: dict, snapshot_root) -> str:
    sha = snapshot_manifest_sha(snapshot_root)
    if params.get("snapshot_manifest_sha256") != sha:
        raise GuardError(f"snapshot manifest mismatch: spec {params.get('snapshot_manifest_sha256')} != {sha}")
    return sha


def read_trials() -> list[dict]:
    p = trial_ledger_path()
    if not p.exists():
        return []
    with p.open(newline="") as f:
        return list(csv.DictReader(f))


def check_no_prior_run(spec_sha: str, bugfix_entry: str | None) -> None:
    trials = read_trials()
    prior = [t for t in trials if t["spec_sha256"] == spec_sha]
    if not prior:
        return
    if not bugfix_entry:
        raise GuardError(f"a run already exists for spec hash {spec_sha} (use --bugfix-entry with a ledgered bug-fix)")
    ids = {r["id"] for r in ledger_rows(prereg_ledger_path())}
    if bugfix_entry not in ids:
        raise GuardError(f"bug-fix entry {bugfix_entry} is not in the prereg ledger")
    if any(t.get("bugfix_entry") == bugfix_entry for t in trials):
        raise GuardError(f"bug-fix entry {bugfix_entry} was already used")


def append_trial(row: dict) -> None:
    p = trial_ledger_path()
    new = not p.exists()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=TRIAL_FIELDS)
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in TRIAL_FIELDS})
        f.flush()
        os.fsync(f.fileno())


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def preflight(spec_path, snapshot_root, bugfix_entry, kind: str) -> tuple[dict, dict]:
    """All guards (a)-(e); returns (params, base trial row). Raises GuardError before any computation."""
    spec_bytes = Path(spec_path).read_bytes()
    spec_sha = hashlib.sha256(spec_bytes).hexdigest()
    params = parse_params(spec_bytes.decode("utf-8"))
    if "id" not in params:
        raise GuardError("params missing 'id'")
    check_spec_ledgered(spec_sha, params["id"])
    eng = check_engine(params)
    snap = check_snapshot(params, snapshot_root)
    check_no_prior_run(spec_sha, bugfix_entry)
    base = {"kind": kind, "id": params["id"], "spec_sha256": spec_sha, "engine_sha256": eng,
            "snapshot_manifest_sha256": snap, "bugfix_entry": bugfix_entry or ""}
    return params, base
