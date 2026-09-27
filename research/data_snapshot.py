"""Content-addressed, fail-closed data snapshots for preregistered experiments.

The manifest is deliberately independent of strategy code. A registered run must
use ``run`` below (or call ``verify_registered`` before calculating returns).
The runner supplies paths into a frozen view, never paths into a mutable archive.
"""
from __future__ import annotations

import argparse
import ctypes
import fnmatch
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA = 1
CHUNK = 8 * 1024 * 1024
TOKEN = "{snapshot_root}"
MEMBERSHIP_TOKEN = "{membership_path}"


class SnapshotError(RuntimeError):
    """The registered data state cannot be verified or reconstructed."""


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def digest(path: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while block := stream.read(CHUNK):
            h.update(block)
            size += len(block)
    return h.hexdigest(), size


def _safe_name(name: str) -> str:
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        raise SnapshotError(f"unsafe name: {name!r}")
    return name


def _timestamp(value: str, field: str) -> datetime:
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise SnapshotError(f"invalid ISO timestamp for {field}: {value!r}") from exc
    if stamp.tzinfo is None:
        raise SnapshotError(f"timestamp needs timezone for {field}: {value!r}")
    return stamp


def _files(scope: dict[str, Any]) -> list[tuple[str, Path]]:
    root = Path(scope["root"]).expanduser().resolve(strict=True)
    patterns = scope.get("include", ["**/*"])
    if not root.is_dir() or not patterns:
        raise SnapshotError(f"invalid input root or include patterns: {root}")
    found = []
    for directory, dirs, names in os.walk(root, followlinks=False):
        if any((Path(directory) / dirname).is_symlink() for dirname in dirs):
            raise SnapshotError(f"symlinked directory inside input scope: {directory}")
        dirs.sort()
        names.sort()
        for name in names:
            path = Path(directory) / name
            rel = path.relative_to(root).as_posix()
            if not any(fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(rel, pattern.removeprefix("**/"))
                       for pattern in patterns):
                continue
            if path.is_symlink() or not path.is_file():
                raise SnapshotError(f"input must be a regular file, not a symlink: {path}")
            found.append((rel, path))
    return found


def _object_path(store: Path, hexdigest: str) -> Path:
    return store / "objects" / "sha256" / hexdigest[:2] / hexdigest


def _copy_on_write_or_stream(source: Path, temporary: Path) -> None:
    """Prefer independent CoW clones; never hard-link a mutable source inode."""
    if sys.platform == "darwin":
        clonefile = getattr(ctypes.CDLL(None), "clonefile", None)
        if clonefile is not None:
            temporary.unlink()
            clonefile.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
            clonefile.restype = ctypes.c_int
            if clonefile(os.fsencode(source), os.fsencode(temporary), 0) == 0:
                return
    if sys.platform.startswith("linux"):
        try:
            import fcntl
            with source.open("rb") as original, temporary.open("wb") as copy:
                fcntl.ioctl(copy.fileno(), 0x40049409, original.fileno())  # FICLONE
            return
        except OSError:
            pass
    shutil.copyfile(source, temporary)


def _store_object(source: Path, store: Path, hexdigest: str, size: int) -> None:
    target = _object_path(store, hexdigest)
    if target.exists():
        if digest(target) != (hexdigest, size):
            raise SnapshotError(f"corrupt content-addressed object: {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".snapshot-", dir=target.parent)
    os.close(fd)
    tmp = Path(temporary)
    try:
        _copy_on_write_or_stream(source, tmp)
        if digest(tmp) != (hexdigest, size):
            raise SnapshotError(f"source changed while freezing: {source}")
        tmp.chmod(0o444)
        try:
            os.link(tmp, target)  # atomic create-if-absent, only within immutable store
        except FileExistsError:
            if digest(target) != (hexdigest, size):
                raise SnapshotError(f"object collision/corruption: {target}")
    finally:
        tmp.unlink(missing_ok=True)


REQUIRED_METADATA = ("source", "source_identifier", "retrieved_at", "logical_as_of",
                     "symbol", "first_timestamp", "last_timestamp", "row_count")


def freeze(spec: dict[str, Any], store: Path) -> dict[str, Any]:
    """Freeze an explicit file scope and all generated inputs; never discover returns.

    ``spec['metadata']`` is keyed by ``scope_name/relative/path``. A static
    metadata artifact may use null first/last timestamps with ``temporal=false``.
    Retrieval time must come from the ingestion record, not file mtime.
    """
    store = Path(store).resolve()
    version = _safe_name(spec["dataset_version"])
    scopes = spec["scopes"]
    if not scopes or not isinstance(scopes, list):
        raise SnapshotError("at least one explicit file scope is required")
    universe = spec["universe"]
    for key in ("membership_artifact", "exclusions", "symbol_mappings", "delistings"):
        if key not in universe:
            raise SnapshotError(f"universe missing {key}")
    records = []
    frozen_scopes = []
    seen = set()
    metadata = spec.get("metadata", {})
    for scope in scopes:
        name = _safe_name(scope["name"])
        root = Path(scope["root"]).expanduser().resolve(strict=True)
        if root == store or root in store.parents or store in root.parents:
            raise SnapshotError("snapshot store may not overlap an input scope")
        include = sorted(scope.get("include", ["**/*"]))
        frozen_scopes.append({"name": name, "root": str(root), "include": include})
        for rel, path in _files({"root": str(root), "include": include}):
            key = f"{name}/{rel}"
            if key in seen:
                raise SnapshotError(f"duplicate input: {key}")
            seen.add(key)
            info = metadata.get(key)
            if info is None:
                raise SnapshotError(f"missing provenance metadata: {key}")
            missing = [field for field in REQUIRED_METADATA if field not in info]
            if missing:
                raise SnapshotError(f"missing {missing} for {key}")
            if any(info[field] in (None, "") for field in ("source", "retrieved_at", "logical_as_of", "symbol")):
                raise SnapshotError(f"incomplete mandatory provenance: {key}")
            if not isinstance(info["row_count"], int) or info["row_count"] < 0:
                raise SnapshotError(f"invalid row count: {key}")
            _timestamp(info["retrieved_at"], f"{key}.retrieved_at")
            try:
                datetime.fromisoformat(info["logical_as_of"].replace("Z", "+00:00"))
            except (AttributeError, ValueError) as exc:
                raise SnapshotError(f"invalid logical as-of date: {key}") from exc
            if info.get("temporal", True) and (not info["first_timestamp"] or not info["last_timestamp"]):
                raise SnapshotError(f"time-series bounds missing: {key}")
            if info.get("temporal", True) and (_timestamp(info["first_timestamp"], f"{key}.first_timestamp") >
                                              _timestamp(info["last_timestamp"], f"{key}.last_timestamp")):
                raise SnapshotError(f"time-series bounds reversed: {key}")
            hexdigest, size = digest(path)
            _store_object(path, store, hexdigest, size)
            records.append({"key": key, "canonical_path": str(path.resolve()), "sha256": hexdigest,
                            "byte_size": size, "dataset_version": version,
                            **{field: info[field] for field in REQUIRED_METADATA},
                            "temporal": bool(info.get("temporal", True))})
    records.sort(key=lambda record: record["key"])
    frozen_scopes.sort(key=lambda scope: scope["name"])
    keys = {record["key"] for record in records}
    required_artifacts = [universe["membership_artifact"], *spec.get("intermediate_artifacts", []),
                          *universe.get("mapping_artifacts", []), *universe.get("delisting_artifacts", [])]
    if any(key not in keys for key in required_artifacts):
        raise SnapshotError(f"unfrozen generated/universe artifact: {sorted(set(required_artifacts) - keys)}")
    if set(metadata) != keys:
        raise SnapshotError(f"metadata/file-scope mismatch: {sorted(set(metadata) - keys)}")
    payload = {"schema_version": SCHEMA, "dataset_version": version,
               "scopes": frozen_scopes, "records": records,
               "universe": universe, "intermediate_artifacts": sorted(spec.get("intermediate_artifacts", []))}
    manifest_hash = hashlib.sha256(canonical(payload)).hexdigest()
    manifest = {"manifest_sha256": manifest_hash, "payload": payload}
    version_dir = store / "versions" / version
    manifest_path = version_dir / "manifest.json"
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text())
        if existing != manifest:
            raise SnapshotError(f"dataset version already exists with different contents: {version}")
    else:
        version_dir.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".manifest-", dir=version_dir)
        os.close(fd)
        tmp = Path(temporary)
        try:
            tmp.write_bytes(canonical(manifest) + b"\n")
            os.replace(tmp, manifest_path)
        finally:
            tmp.unlink(missing_ok=True)
    _build_view(store, manifest)
    return manifest


def _build_view(store: Path, manifest: dict[str, Any]) -> Path:
    version = manifest["payload"]["dataset_version"]
    view = store / "versions" / version / "view"
    for record in manifest["payload"]["records"]:
        link = view / record["key"]
        target = _object_path(store, record["sha256"])
        link.parent.mkdir(parents=True, exist_ok=True)
        relative_target = os.path.relpath(target, link.parent)
        if link.is_symlink():
            if os.readlink(link) != relative_target:
                raise SnapshotError(f"modified snapshot view: {link}")
        elif link.exists():
            raise SnapshotError(f"unexpected file in snapshot view: {link}")
        else:
            link.symlink_to(relative_target)
    return view


def load_manifest(store: Path, version: str) -> dict[str, Any]:
    path = Path(store).resolve() / "versions" / _safe_name(version) / "manifest.json"
    manifest = json.loads(path.read_text())
    actual = hashlib.sha256(canonical(manifest["payload"])).hexdigest()
    if actual != manifest.get("manifest_sha256"):
        raise SnapshotError(f"manifest hash mismatch: {path}")
    return manifest


def verify(store: Path, version: str, *, source: bool = True) -> dict[str, Any]:
    """Verify the registered manifest, immutable objects and optionally live input scope.

    Source verification catches changed, deleted and newly appeared matching
    files. Replay may set ``source=False`` and must then use the frozen view.
    """
    store = Path(store).resolve()
    manifest = load_manifest(store, version)
    payload = manifest["payload"]
    expected = {record["key"]: record for record in payload["records"]}
    for key, record in expected.items():
        blob = _object_path(store, record["sha256"])
        if not blob.is_file() or digest(blob) != (record["sha256"], record["byte_size"]):
            raise SnapshotError(f"missing/corrupt frozen object: {key}")
    if source:
        observed = {}
        for scope in payload["scopes"]:
            try:
                for rel, path in _files(scope):
                    observed[f"{scope['name']}/{rel}"] = path
            except FileNotFoundError as exc:
                raise SnapshotError(f"input scope disappeared: {scope['root']}") from exc
        added = sorted(set(observed) - set(expected))
        removed = sorted(set(expected) - set(observed))
        if added or removed:
            raise SnapshotError(f"input set drift: added={added}, removed={removed}")
        for key, path in observed.items():
            record = expected[key]
            if str(path.resolve()) != record["canonical_path"] or digest(path) != (record["sha256"], record["byte_size"]):
                raise SnapshotError(f"input changed: {key}")
    view = _build_view(store, manifest)
    for record in payload["records"]:
        link = view / record["key"]
        if not link.is_symlink() or link.resolve() != _object_path(store, record["sha256"]):
            raise SnapshotError(f"snapshot view changed: {link}")
    return manifest


def register(store: Path, experiment: str, version: str, command: list[str]) -> dict[str, Any]:
    """Pin a data hash and a snapshot-consuming command before returns exist."""
    experiment = _safe_name(experiment)
    if not command or not any(TOKEN in part for part in command) or not any(MEMBERSHIP_TOKEN in part for part in command):
        raise SnapshotError("registered command must consume snapshot_root and membership_path placeholders")
    manifest = verify(store, version, source=True)
    entry = {"experiment": experiment, "dataset_version": version,
             "manifest_sha256": manifest["manifest_sha256"], "command": command}
    ledger = Path(store).resolve() / "registrations.jsonl"
    prior = [] if not ledger.exists() else [json.loads(line) for line in ledger.read_text().splitlines() if line]
    matches = [row for row in prior if row["experiment"] == experiment]
    if matches:
        if len(matches) != 1 or matches[0] != entry:
            raise SnapshotError(f"experiment is already registered differently: {experiment}")
        return entry
    with ledger.open("ab") as stream:
        stream.write(canonical(entry) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    return entry


def verify_registered(store: Path, experiment: str, *, replay: bool = False) -> tuple[dict[str, Any], Path]:
    store = Path(store).resolve()
    ledger = store / "registrations.jsonl"
    if not ledger.exists():
        raise SnapshotError("no data snapshot registrations")
    matches = [json.loads(line) for line in ledger.read_text().splitlines() if line
               and json.loads(line)["experiment"] == experiment]
    if len(matches) != 1:
        raise SnapshotError(f"expected exactly one registration for {experiment}; found {len(matches)}")
    entry = matches[0]
    manifest = verify(store, entry["dataset_version"], source=not replay)
    if manifest["manifest_sha256"] != entry["manifest_sha256"]:
        raise SnapshotError(f"registered manifest hash changed: {experiment}")
    view = store / "versions" / entry["dataset_version"] / "view"
    return entry, view


def run_registered(store: Path, experiment: str, *, replay: bool = False) -> int:
    entry, view = verify_registered(store, experiment, replay=replay)
    membership = view / load_manifest(store, entry["dataset_version"])["payload"]["universe"]["membership_artifact"]
    command = [part.replace(TOKEN, str(view)).replace(MEMBERSHIP_TOKEN, str(membership))
               for part in entry["command"]]
    env = os.environ.copy()
    env["QUANT_DATA_SNAPSHOT_ROOT"] = str(view)
    env["QUANT_DATA_MANIFEST_SHA256"] = entry["manifest_sha256"]
    env["QUANT_DATASET_VERSION"] = entry["dataset_version"]
    return subprocess.run(command, env=env, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", required=True, type=Path)
    commands = parser.add_subparsers(dest="operation", required=True)
    create = commands.add_parser("freeze")
    create.add_argument("spec", type=Path)
    registration = commands.add_parser("register")
    registration.add_argument("experiment")
    registration.add_argument("version")
    registration.add_argument("command_json", type=Path)
    check = commands.add_parser("verify")
    check.add_argument("experiment")
    check.add_argument("--replay", action="store_true")
    execute = commands.add_parser("run")
    execute.add_argument("experiment")
    execute.add_argument("--replay", action="store_true")
    args = parser.parse_args()
    if args.operation == "freeze":
        result = freeze(json.loads(args.spec.read_text()), args.store)
        print(result["manifest_sha256"])
    elif args.operation == "register":
        result = register(args.store, args.experiment, args.version, json.loads(args.command_json.read_text()))
        print(result["manifest_sha256"])
    elif args.operation == "verify":
        result, view = verify_registered(args.store, args.experiment, replay=args.replay)
        print(json.dumps({"manifest_sha256": result["manifest_sha256"], "snapshot_root": str(view)}))
    else:
        return run_registered(args.store, args.experiment, replay=args.replay)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SnapshotError, OSError, ValueError, KeyError) as exc:
        raise SystemExit(f"snapshot verification failed: {exc}") from exc
