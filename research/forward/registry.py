"""Append-only JSONL registry with a SHA-256 hash chain.

Every line is one record:

    {"v": 1, "seq": n, "kind": ..., "recorded_at_utc": "...Z",
     "strategy_id": ..., "spec_hash": ..., "market_asof": "YYYY-MM-DD",
     "intended_execution_utc": "...Z", "decision_key": ..., "payload": {...},
     "writer": {...}, "prev_hash": <hash of record n-1>, "hash": <sha256>}

`hash` is SHA-256 over the canonical JSON (sorted keys, no whitespace, UTF-8,
NaN forbidden) of the record without its `hash` field, so it covers
`prev_hash`: editing, reordering or deleting any record breaks every later
link. Record 0 is the genesis record, whose prev_hash is 64 zeros.

What the chain guarantees and what it does not
  * An edit, reorder, insertion or deletion anywhere BEFORE the last record is
    detected by `verify_chain` on its own.
  * Truncating the tail, or rewriting the whole file with recomputed hashes, is
    only detected against a head hash that was recorded somewhere the writer
    cannot change (an "anchor": a pushed git commit, an email, a third-party
    timestamp). `verify_chain(anchors=...)` checks those.
  * `recorded_at_utc` is the writer's wall clock. The chain proves ORDER; it
    proves TIME only up to the next external anchor that includes the record.
"""
from __future__ import annotations

import datetime as dt
import fcntl
import hashlib
import json
import os
import platform
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = ROOT / "reports" / "forward" / "registry.jsonl"
GENESIS_PREV = "0" * 64
SCHEMA_VERSION = 1
KINDS = {"genesis", "spec_registration", "decision", "void", "note"}
REQUIRED = ("v", "seq", "kind", "recorded_at_utc", "strategy_id", "spec_hash", "market_asof",
            "intended_execution_utc", "decision_key", "payload", "writer", "prev_hash", "hash")


class RegistryError(RuntimeError):
    pass


# -- hashing ------------------------------------------------------------------

def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def spec_hash(spec: dict) -> str:
    """Hash of a frozen spec: SHA-256 of its canonical JSON."""
    return sha256_text(canonical_json(spec))


def record_hash(record: dict) -> str:
    return sha256_text(canonical_json({k: v for k, v in record.items() if k != "hash"}))


# -- time -----------------------------------------------------------------------

def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso_utc(ts: dt.datetime) -> str:
    if ts.tzinfo is None:
        raise ValueError("naive datetime; pass an aware UTC datetime")
    return ts.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def parse_utc(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(dt.timezone.utc)


def _git_head() -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or None
    except Exception:
        return None


def writer_info() -> dict:
    return {"tool": "research.forward", "schema": SCHEMA_VERSION, "git_head": _git_head(),
            "python": platform.python_version()}


# -- reading ----------------------------------------------------------------------

@dataclass
class Issue:
    line: int
    code: str
    message: str


@dataclass
class VerifyReport:
    path: str
    n_records: int = 0
    head_seq: int | None = None
    head_hash: str | None = None
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)
    anchors_checked: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {"path": self.path, "ok": self.ok, "n_records": self.n_records, "head_seq": self.head_seq,
                "head_hash": self.head_hash, "anchors_checked": self.anchors_checked,
                "errors": [vars(e) for e in self.errors], "warnings": [vars(w) for w in self.warnings]}


def read_lines(path: Path) -> list[str]:
    if not Path(path).exists():
        return []
    return Path(path).read_text(encoding="utf-8").split("\n")


def load_records(path: Path) -> list[dict]:
    """Parsed records; raises RegistryError if the chain does not verify."""
    report = verify_chain(path)
    if not report.ok:
        raise RegistryError("registry does not verify: " + "; ".join(f"line {e.line}: {e.code}: {e.message}"
                                                                    for e in report.errors[:5]))
    return [json.loads(line) for line in read_lines(path) if line.strip()]


def verify_chain(path: Path, anchors: Iterable[tuple[int, str]] = (), text: str | None = None) -> VerifyReport:
    """Check every link, hash, sequence number and time; then the anchors.

    `anchors`: (seq, hash) pairs recorded outside this file. Each must match
    the record at that seq; a missing seq means the tail was truncated."""
    report = VerifyReport(path=str(path))
    lines = text.split("\n") if text is not None else read_lines(path)
    if lines and lines[-1] != "":
        report.errors.append(Issue(len(lines), "unterminated", "last line has no newline (partial write or edit)"))
    records: list[dict] = []
    prev_hash = GENESIS_PREV
    prev_time = None
    specs: dict[str, dict[str, int]] = {}
    keys: dict[tuple[str, str], int] = {}
    voided: set[int] = set()
    for i, line in enumerate(lines, start=1):
        if not line.strip():
            if i != len(lines):
                report.errors.append(Issue(i, "blank", "blank line inside the registry"))
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as e:
            report.errors.append(Issue(i, "parse", str(e)))
            prev_hash = None
            continue
        if not isinstance(rec, dict) or any(k not in rec for k in REQUIRED):
            missing = [k for k in REQUIRED if not isinstance(rec, dict) or k not in rec]
            report.errors.append(Issue(i, "schema", f"missing fields {missing}"))
            prev_hash = rec.get("hash") if isinstance(rec, dict) else None
            continue
        seq = len(records)
        if rec["seq"] != seq:
            report.errors.append(Issue(i, "seq", f"seq {rec['seq']} at position {seq} (record deleted, inserted or reordered)"))
        if rec["prev_hash"] != prev_hash:
            report.errors.append(Issue(i, "link", "prev_hash does not match the previous record's hash"))
        if record_hash(rec) != rec["hash"]:
            report.errors.append(Issue(i, "hash", "record content does not match its hash (edited)"))
        if rec["kind"] not in KINDS:
            report.errors.append(Issue(i, "kind", f"unknown kind {rec['kind']!r}"))
        if seq == 0 and rec["kind"] != "genesis":
            report.errors.append(Issue(i, "genesis", "first record is not a genesis record"))
        if seq > 0 and rec["kind"] == "genesis":
            report.errors.append(Issue(i, "genesis", "second genesis record"))
        try:
            t = parse_utc(rec["recorded_at_utc"])
            if prev_time is not None and t < prev_time:
                report.errors.append(Issue(i, "time_order", "recorded_at_utc earlier than the previous record's"))
            prev_time = t
        except Exception:
            report.errors.append(Issue(i, "time", f"bad recorded_at_utc {rec.get('recorded_at_utc')!r}"))
        if rec["kind"] == "spec_registration":
            specs.setdefault(rec["strategy_id"], {})[rec["spec_hash"]] = seq
        elif rec["kind"] == "decision":
            if rec["spec_hash"] not in specs.get(rec["strategy_id"], {}):
                report.errors.append(Issue(i, "spec", f"decision for {rec['strategy_id']} under an unregistered spec"))
            key = (rec["strategy_id"], rec["decision_key"])
            if key in keys and keys[key] not in voided:
                report.errors.append(Issue(i, "duplicate", f"second live decision {key} (void the first one instead)"))
            keys[key] = seq
            try:
                parse_utc(rec["intended_execution_utc"])
            except Exception:
                report.errors.append(Issue(i, "execution_time", "decision without a valid intended_execution_utc"))
        elif rec["kind"] == "void":
            target = rec["payload"].get("voids_seq")
            if not isinstance(target, int) or target >= seq:
                report.errors.append(Issue(i, "void", "void must reference an earlier record"))
            else:
                voided.add(target)
        records.append(rec)
        prev_hash = rec["hash"]
    report.n_records = len(records)
    if records:
        report.head_seq = records[-1]["seq"]
        report.head_hash = records[-1]["hash"]
    for seq, expected in anchors:
        report.anchors_checked += 1
        if seq >= len(records):
            report.errors.append(Issue(0, "anchor_missing", f"anchored seq {seq} no longer exists (tail truncated)"))
        elif records[seq]["hash"] != expected:
            report.errors.append(Issue(0, "anchor_mismatch", f"record {seq} differs from its anchored hash (rewritten)"))
    return report


def load_anchors(path: Path | None) -> list[tuple[int, str]]:
    """anchors.jsonl lines: {"seq": n, "hash": "...", "anchored_at_utc": "...", "channel": "..."}"""
    if path is None or not Path(path).exists():
        return []
    out = []
    for line in Path(path).read_text().splitlines():
        if line.strip():
            a = json.loads(line)
            out.append((int(a["seq"]), str(a["hash"])))
    return out


# -- writing ------------------------------------------------------------------------

def _build(seq: int, prev_hash: str, kind: str, recorded_at: dt.datetime, strategy_id, spec_hash_, market_asof,
           intended_execution_utc, decision_key, payload) -> dict:
    rec = {
        "v": SCHEMA_VERSION, "seq": seq, "kind": kind, "recorded_at_utc": iso_utc(recorded_at),
        "strategy_id": strategy_id, "spec_hash": spec_hash_, "market_asof": market_asof,
        "intended_execution_utc": intended_execution_utc, "decision_key": decision_key,
        "payload": payload, "writer": writer_info(), "prev_hash": prev_hash,
    }
    canonical_json(rec)  # fails early on NaN / non-JSON values
    rec["hash"] = record_hash(rec)
    return rec


def append(path: Path, kind: str, *, strategy_id: str | None = None, spec_hash: str | None = None,
           market_asof: str | None = None, intended_execution_utc: str | None = None,
           decision_key: str | None = None, payload: dict | None = None,
           now: dt.datetime | None = None) -> dict:
    """Verify the whole chain under an exclusive lock, then append one record.

    Refuses to extend a chain that does not verify, a decision under an
    unregistered spec, and a second live decision with the same key."""
    if kind not in KINDS - {"genesis"}:
        raise RegistryError(f"cannot append kind {kind!r} (use init() for genesis)")
    path = Path(path)
    if not path.exists():
        raise RegistryError(f"{path} does not exist; initialise it first")
    with open(path, "a+", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.seek(0)
            text = f.read()
            report = verify_chain(path, text=text)
            if not report.ok:
                raise RegistryError("refusing to append to a registry that does not verify: "
                                    + "; ".join(f"{e.code}: {e.message}" for e in report.errors[:3]))
            records = [json.loads(line) for line in text.split("\n") if line.strip()]
            last = records[-1]
            recorded_at = now or utc_now()
            if recorded_at < parse_utc(last["recorded_at_utc"]):
                raise RegistryError("clock is behind the last record; refusing to append")
            if kind == "decision":
                registered = {r["spec_hash"] for r in records
                              if r["kind"] == "spec_registration" and r["strategy_id"] == strategy_id}
                if spec_hash not in registered:
                    raise RegistryError(f"no spec_registration for {strategy_id} with spec_hash {spec_hash}")
                voided = {r["payload"]["voids_seq"] for r in records if r["kind"] == "void"}
                if any(r["kind"] == "decision" and r["strategy_id"] == strategy_id and r["decision_key"] == decision_key
                       and r["seq"] not in voided for r in records):
                    raise RegistryError(f"decision {strategy_id}/{decision_key} already recorded")
                if intended_execution_utc is None:
                    raise RegistryError("a decision needs intended_execution_utc")
            if kind == "spec_registration" and any(
                    r["kind"] == "spec_registration" and r["strategy_id"] == strategy_id and r["spec_hash"] == spec_hash
                    for r in records):
                raise RegistryError(f"spec {spec_hash[:12]} for {strategy_id} already registered")
            rec = _build(last["seq"] + 1, last["hash"], kind, recorded_at, strategy_id, spec_hash, market_asof,
                         intended_execution_utc, decision_key, payload or {})
            f.seek(0, os.SEEK_END)
            f.write(canonical_json(rec) + "\n")
            f.flush()
            os.fsync(f.fileno())
            return rec
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def init(path: Path, note: str = "", now: dt.datetime | None = None) -> dict:
    """Create a registry holding only a genesis record. Refuses to overwrite."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"purpose": "forward-prediction registry: append-only, SHA-256 hash chain", "note": note}
    rec = _build(0, GENESIS_PREV, "genesis", now or utc_now(), None, None, None, None, None, payload)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)  # O_EXCL: never clobber an existing file
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(canonical_json(rec) + "\n")
        f.flush()
        os.fsync(f.fileno())
    return rec


def registered_specs(records: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in records:
        if r["kind"] == "spec_registration":
            out.setdefault(r["strategy_id"], []).append(r)
    return out


def live_decisions(records: list[dict]) -> tuple[list[dict], list[dict]]:
    """(decisions not voided, voided decisions)."""
    voided = {r["payload"]["voids_seq"] for r in records if r["kind"] == "void"}
    decisions = [r for r in records if r["kind"] == "decision"]
    return [d for d in decisions if d["seq"] not in voided], [d for d in decisions if d["seq"] in voided]


def head_line(report: VerifyReport) -> str:
    """One line to paste into an email / commit message / timestamping service."""
    return f"quant_v7 forward registry head seq={report.head_seq} sha256={report.head_hash}"
