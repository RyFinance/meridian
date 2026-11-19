"""Append-only, hash-chained JSONL paper log (separate from the forward research registry).

Each line is the canonical JSON (sorted keys, no whitespace) of::

    {"schema": "autopilot_paper_log_v1", "seq": n, "prev_hash": <entry_hash of line n-1 or 64 zeros>,
     "body": {...}, "entry_hash": sha256(canonical(entry without entry_hash))}

The whole chain is validated before every append; any mismatch (edited, reordered, deleted or re-serialised line)
is fatal.  A hard guard refuses ``reports/forward/registry.jsonl`` (by path, resolved path, same inode, or any
file named ``registry.jsonl`` / anything under ``reports/forward/``).
"""
from __future__ import annotations

import hashlib
import json
import os
import unicodedata
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
DEFAULT_LOG_PATH = REPO / "reports" / "autopilot" / "paper_log.jsonl"
FORWARD_REGISTRY_PATH = REPO / "reports" / "forward" / "registry.jsonl"
FORWARD_DIR = REPO / "reports" / "forward"
LOG_SCHEMA = "autopilot_paper_log_v1"
GENESIS = "0" * 64
REGISTRY_NAME = "registry.jsonl"


class PaperLogError(RuntimeError):
    """Paper log chain invalid, or a write to a forbidden path was attempted."""


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fold(text: str) -> str:
    """Case- and normalisation-insensitive form of a path string (APFS/HFS+ and NTFS are case-insensitive by
    default, and APFS is Unicode-normalisation-insensitive)."""
    return unicodedata.normalize("NFC", text).casefold()


def _lexically_within(path: Path, root: Path) -> bool:
    """``path`` equals or lies under ``root``, comparing components case-insensitively."""
    pp, rp = [_fold(x) for x in path.parts], [_fold(x) for x in root.parts]
    return len(pp) >= len(rp) and pp[:len(rp)] == rp


def _same(a: Path, b: Path) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError as exc:
        raise PaperLogError(f"cannot check output path identity: {exc.strerror or exc}") from exc


def guard_path(path: Path) -> Path:
    """Raise unless ``path`` is safe to write: never the forward registry (hard guard).

    Refused: any file named ``registry.jsonl`` (compared case-insensitively), anything equal to or under
    ``reports/forward/`` (case-insensitive comparison of the given absolute path and of the resolved path, and
    file-system identity of every existing ancestor with that directory), and any existing file that is the same
    file as the registry (symlink or hard link)."""
    p = Path(path).expanduser()
    absolute = Path(os.path.normpath(p if p.is_absolute() else Path.cwd() / p))
    resolved = absolute.resolve()
    forbidden = FORWARD_REGISTRY_PATH.resolve()
    forward_dirs = (Path(os.path.normpath(FORWARD_DIR)), FORWARD_DIR.resolve())
    if _fold(REGISTRY_NAME) in {_fold(p.name), _fold(absolute.name), _fold(resolved.name)}:
        raise PaperLogError(f"refusing to write a file named {REGISTRY_NAME}: {p}")
    for candidate in (absolute, resolved):
        for root in forward_dirs:
            if _lexically_within(candidate, root):
                raise PaperLogError(f"refusing to write under the forward research registry: {p}")
    if forward_dirs[1].exists():
        for ancestor in (resolved, *resolved.parents):
            if ancestor.exists() and _same(ancestor, forward_dirs[1]):
                raise PaperLogError(f"refusing to write under the forward research registry (same directory): {p}")
    if resolved.exists() and forbidden.exists() and _same(resolved, forbidden):
        raise PaperLogError(f"refusing to write the forward research registry (same file): {p}")
    return resolved


def entry_hash(entry: dict[str, Any]) -> str:
    return sha256_hex(canonical({k: v for k, v in entry.items() if k != "entry_hash"}))


def read_chain(path: Path) -> list[dict[str, Any]]:
    """Return all entries after validating the complete chain; missing file = empty log."""
    path = Path(path)
    if not path.exists():
        return []
    raw = path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        last_line = raw.count(b"\n") + 1
        raise PaperLogError(f"paper log does not end with a newline (truncated or edited): line {last_line}")
    entries = []
    prev = GENESIS
    for n, line in enumerate(raw.splitlines(), start=1):
        try:
            entry = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PaperLogError(f"paper log line {n} unparsable") from exc
        if not isinstance(entry, dict) or set(entry) != {"schema", "seq", "prev_hash", "body", "entry_hash"}:
            raise PaperLogError(f"paper log line {n} has unexpected structure")
        if canonical(entry) != line:
            raise PaperLogError(f"paper log line {n} is not canonical JSON (edited)")
        if entry["schema"] != LOG_SCHEMA or type(entry["seq"]) is not int or entry["seq"] != n - 1:
            raise PaperLogError(f"paper log line {n} has wrong schema or sequence number")
        if entry["prev_hash"] != prev:
            raise PaperLogError(f"paper log line {n}: prev_hash does not match line {n - 1}")
        if entry_hash(entry) != entry["entry_hash"]:
            raise PaperLogError(f"paper log line {n}: entry_hash mismatch (tampered)")
        prev = entry["entry_hash"]
        entries.append(entry)
    return entries


def validate(path: Path) -> bool:
    try:
        read_chain(path)
    except PaperLogError:
        return False
    return True


def make_entry(body: dict[str, Any], chain: list[dict[str, Any]]) -> dict[str, Any]:
    entry = {"schema": LOG_SCHEMA, "seq": len(chain),
             "prev_hash": chain[-1]["entry_hash"] if chain else GENESIS, "body": body}
    entry["entry_hash"] = entry_hash(entry)
    return entry


def append(path: Path, body: dict[str, Any], *, expected_chain: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Validate the chain, then append one canonical line.  ``expected_chain`` (the chain the caller computed
    against) must still be the current chain, so a concurrent writer cannot interleave silently."""
    target = guard_path(path)
    chain = read_chain(target)
    if expected_chain is not None and [e["entry_hash"] for e in chain] != [e["entry_hash"] for e in expected_chain]:
        raise PaperLogError("paper log changed while the report was being computed")
    entry = make_entry(body, chain)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(target, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, canonical(entry) + b"\n")
        os.fsync(fd)
    finally:
        os.close(fd)
    return entry


def check_summary_against_log(chain: list[dict[str, Any]], doc: dict[str, Any]) -> list[str]:
    """Problems (empty = consistent) between a written JSON summary and the validated chain.

    Every summary records where its entry sits (``paper_log.seq`` and ``paper_log.prev_entry_hash``).  Deleting
    trailing lines leaves a chain that still validates, but the summaries of the deleted runs then point past the
    end of the log, or at an entry with a different body; this function reports that."""
    head = doc.get("paper_log") if isinstance(doc, dict) else None
    if not isinstance(head, dict) or type(head.get("seq")) is not int:
        return ["summary records no paper-log position (written before log heads were recorded)"]
    seq = head["seq"]
    if seq >= len(chain):
        return [f"paper log holds {len(chain)} entries but this summary's entry is seq {seq}: trailing lines were "
                "removed (truncated log) or the summary belongs to another log"]
    entry = chain[seq]
    problems = []
    if entry["prev_hash"] != head.get("prev_entry_hash"):
        problems.append(f"entry seq {seq} chains after {entry['prev_hash']}, but the summary recorded "
                        f"{head.get('prev_entry_hash')}: the log was rewritten from that point")
    if entry["body"] != doc:
        problems.append(f"entry seq {seq} does not hold this summary (different body)")
    return problems
