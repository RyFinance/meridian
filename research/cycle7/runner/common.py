"""Paths, hashes and ledgers for the cycle-7 runner.

Test-only overrides (refused unless pytest is running, i.e. PYTEST_CURRENT_TEST is set):
  CYCLE7_TEST_REPO_ROOT        root that spec_path / snapshot_root_rel / sample paths resolve against
  CYCLE7_TEST_PREREG_LEDGER    cycle-7 prereg ledger (default research/cycle7_prereg_ledger.md)
  CYCLE7_TEST_CYCLE6_LEDGER    cycle-6 prereg ledger (default research/cycle6_prereg_ledger.md)
  CYCLE7_TEST_TRIAL_LEDGER     cycle-7 trial ledger (default research/cycle7/trial_ledger.csv)
  CYCLE7_TEST_ENGINE_DIR       engine directory whose *.py are hashed (default research/cycle6/engine)
"""
from __future__ import annotations

import csv
import hashlib
import os
import re
from pathlib import Path

from research.cycle6.engine import guards as eguards

RUNNER_DIR = Path(__file__).resolve().parent
REPO = RUNNER_DIR.parents[2]
ENGINE_SHA256 = "e9cec9f0f81d15cc13968456abcbeb24fb84d85d1a29df29bc1e1eff95469422"
FROZEN_SPECS = ("TSMOM-FI", "TSMOM-CM", "XSMOM-FX", "VAL-FX", "CARRY-FX", "SEAS-FX")
TRIAL_FIELDS = ["utc", "kind", "spec_id", "sample_id", "sample_sha256", "spec_sha256", "engine_sha256",
                "runner_sha256", "snapshot_manifest_sha256", "instrument_list_sha256", "status", "summary"]


class GuardError(RuntimeError):
    """A cycle-7 preregistration guard refused the run (raised before any computation)."""


def _override(env: str, default: Path) -> Path:
    v = os.environ.get(env)
    if not v:
        return default
    if not os.environ.get("PYTEST_CURRENT_TEST"):
        raise GuardError(f"{env} is a test-only override and is refused outside pytest")
    return Path(v)


def repo_root() -> Path:
    return _override("CYCLE7_TEST_REPO_ROOT", REPO)


def prereg_ledger_path() -> Path:
    return _override("CYCLE7_TEST_PREREG_LEDGER", REPO / "research" / "cycle7_prereg_ledger.md")


def cycle6_ledger_path() -> Path:
    return _override("CYCLE7_TEST_CYCLE6_LEDGER", REPO / "research" / "cycle6_prereg_ledger.md")


def trial_ledger_path() -> Path:
    return _override("CYCLE7_TEST_TRIAL_LEDGER", REPO / "research" / "cycle7" / "trial_ledger.csv")


def engine_dir() -> Path:
    return _override("CYCLE7_TEST_ENGINE_DIR", eguards.ENGINE_DIR)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p) -> str:
    return sha256_bytes(Path(p).read_bytes())


def dir_py_sha256(d: Path) -> str:
    """sha256 over the concatenated bytes of d/*.py sorted by file name (byte order) -- the engine convention."""
    h = hashlib.sha256()
    for p in sorted(Path(d).glob("*.py"), key=lambda q: q.name.encode()):
        h.update(p.read_bytes())
    return h.hexdigest()


def runner_sha256() -> str:
    return dir_py_sha256(RUNNER_DIR)


def instrument_list_sha256(ids) -> str:
    """sha256 of the sorted market ids joined by '\\n' (no trailing newline)."""
    return sha256_bytes("\n".join(sorted(str(i) for i in ids)).encode())


# ------------------------------------------------------------------------------------------------ ledgers
def ledger_rows(path: Path) -> list[dict]:
    """Rows of a markdown prereg ledger that carry a 64-hex SHA-256 cell (frozen engine parser)."""
    try:
        return eguards.ledger_rows(Path(path))
    except eguards.GuardError as exc:
        raise GuardError(str(exc)) from exc


def ledger_all_rows(path: Path) -> list[list[str]]:
    if not Path(path).exists():
        raise GuardError(f"prereg ledger missing: {path}")
    out = []
    for line in Path(path).read_text().splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 6 and not set(cells[0]) <= set("-: "):
            out.append(cells)
    return out


def ledger_k(path: Path | None = None) -> int:
    """k (FRAMEWORK §5): exactly one cycle-7 ledger row whose Kind cell is 'k' and whose Note cell holds 'k=<int>'."""
    path = path or prereg_ledger_path()
    rows = [c for c in ledger_all_rows(path) if c[1].lower() == "k"]
    if len(rows) != 1:
        raise GuardError(f"cycle-7 ledger must hold exactly one Kind='k' row (found {len(rows)})")
    m = re.search(r"\bk\s*=\s*(\d+)\b", rows[0][5])
    if not m:
        raise GuardError("the Kind='k' ledger row's Note cell must contain 'k=<int>'")
    k = int(m.group(1))
    if k < 1:
        raise GuardError("k must be >= 1")
    return k


def read_trials() -> list[dict]:
    p = trial_ledger_path()
    if not p.exists():
        return []
    with p.open(newline="") as f:
        return list(csv.DictReader(f))


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
    return eguards.utc()
