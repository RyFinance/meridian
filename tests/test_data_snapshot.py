"""No market data, network, or existing research artifacts are used here."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from research.data_snapshot import (SnapshotError, freeze, load_manifest, register,
                                    run_registered, verify, verify_registered)


def fixture(tmp_path: Path, version: str = "dev_snapshot_v1"):
    source = tmp_path / "mutable_source"
    source.mkdir()
    (source / "AAA.csv").write_text("time,price\n2020-01-01,1\n2020-01-02,2\n")
    (source / "membership.csv").write_text("date,symbol\n2020-01-01,AAA\n2020-01-02,AAA\n")
    store = tmp_path / "snapshots"
    metadata = {}
    for file, symbol in (("AAA.csv", "AAA"), ("membership.csv", "UNIVERSE")):
        metadata[f"raw/{file}"] = {"source": "synthetic_test", "source_identifier": "test://input",
                                    "retrieved_at": "2026-09-25T12:00:00Z", "logical_as_of": "2020-01-02",
                                    "symbol": symbol, "first_timestamp": "2020-01-01T00:00:00Z",
                                    "last_timestamp": "2020-01-02T00:00:00Z", "row_count": 2}
    spec = {"dataset_version": version, "scopes": [{"name": "raw", "root": str(source),
                                                       "include": ["**/*.csv"]}],
            "metadata": metadata, "universe": {"membership_artifact": "raw/membership.csv",
                                               "exclusions": [], "symbol_mappings": {"AAA": "AAA"},
                                               "delistings": []},
            "intermediate_artifacts": []}
    return source, store, spec


def test_changed_historical_file_detected(tmp_path):
    source, store, spec = fixture(tmp_path)
    freeze(spec, store)
    (source / "AAA.csv").write_text("time,price\n2020-01-01,1\n2020-01-02,3\n")
    with pytest.raises(SnapshotError, match="input changed"):
        verify(store, "dev_snapshot_v1")


def test_new_file_detected(tmp_path):
    source, store, spec = fixture(tmp_path)
    freeze(spec, store)
    (source / "late_history.csv").write_text("time,price\n2020-01-01,9\n")
    with pytest.raises(SnapshotError, match="added=.*late_history"):
        verify(store, "dev_snapshot_v1")


def test_deleted_file_detected(tmp_path):
    source, store, spec = fixture(tmp_path)
    freeze(spec, store)
    (source / "AAA.csv").unlink()
    with pytest.raises(SnapshotError, match="removed=.*AAA"):
        verify(store, "dev_snapshot_v1")


def test_universe_change_detected(tmp_path):
    source, store, spec = fixture(tmp_path)
    freeze(spec, store)
    (source / "membership.csv").write_text("date,symbol\n2020-01-01,AAA\n2020-01-02,BBB\n")
    with pytest.raises(SnapshotError, match="input changed: raw/membership"):
        verify(store, "dev_snapshot_v1")


def test_deterministic_manifest_hash_and_immutable_version(tmp_path):
    source, store, spec = fixture(tmp_path)
    first = freeze(spec, store)["manifest_sha256"]
    assert first == freeze(spec, store)["manifest_sha256"]
    assert first == freeze(spec, tmp_path / "second_store")["manifest_sha256"]
    modified = json.loads(json.dumps(spec))
    modified["universe"]["exclusions"] = ["BBB"]
    with pytest.raises(SnapshotError, match="already exists"):
        freeze(modified, store)
    assert load_manifest(store, "dev_snapshot_v1")["manifest_sha256"] == first


def test_exact_snapshot_reconstruction_after_live_mutation(tmp_path):
    source, store, spec = fixture(tmp_path)
    freeze(spec, store)
    original = (source / "AAA.csv").read_bytes()
    (source / "AAA.csv").write_text("time,price\n2020-01-01,99\n")
    with pytest.raises(SnapshotError):
        verify(store, "dev_snapshot_v1", source=True)
    verify(store, "dev_snapshot_v1", source=False)
    frozen = store / "versions/dev_snapshot_v1/view/raw/AAA.csv"
    assert frozen.read_bytes() == original
    assert frozen.is_symlink()
    successor = json.loads(json.dumps(spec))
    successor["dataset_version"] = "dev_snapshot_v2"
    successor["metadata"]["raw/AAA.csv"]["row_count"] = 1
    successor["metadata"]["raw/AAA.csv"]["last_timestamp"] = "2020-01-01T00:00:00Z"
    assert freeze(successor, store)["manifest_sha256"] != load_manifest(store, "dev_snapshot_v1")["manifest_sha256"]
    assert (store / "versions/dev_snapshot_v1/view/raw/AAA.csv").read_bytes() == original
    assert (store / "versions/dev_snapshot_v2/view/raw/AAA.csv").read_bytes() != original


def test_large_directory_is_streamed_and_deduplicated(tmp_path):
    source, store, spec = fixture(tmp_path)
    sample = spec["metadata"]["raw/AAA.csv"]
    for index in range(1200):
        name = f"contract_{index:04d}.csv"
        (source / name).write_text("time,price\n2020-01-01,1\n")
        spec["metadata"][f"raw/{name}"] = {**sample, "symbol": f"S{index:04d}", "row_count": 1,
                                             "last_timestamp": "2020-01-01T00:00:00Z"}
    frozen = freeze(spec, store)
    assert len(frozen["payload"]["records"]) == 1202
    assert len(list((store / "objects/sha256").glob("*/*"))) == 3
    verify(store, "dev_snapshot_v1")


def test_registered_manifest_verification_blocks_run(tmp_path):
    source, store, spec = fixture(tmp_path)
    freeze(spec, store)
    marker = tmp_path / "ran.txt"
    command = [sys.executable, "-c",
               "import pathlib,sys; assert pathlib.Path(sys.argv[1]).is_dir(); "
               "assert pathlib.Path(sys.argv[2]).is_file(); pathlib.Path(sys.argv[3]).write_text('ran')",
               "{snapshot_root}", "{membership_path}", str(marker)]
    entry = register(store, "E1", "dev_snapshot_v1", command)
    assert verify_registered(store, "E1")[0] == entry
    assert run_registered(store, "E1") == 0
    assert marker.read_text() == "ran"
    marker.unlink()
    (source / "AAA.csv").write_text("time,price\n2020-01-01,77\n")
    with pytest.raises(SnapshotError):
        run_registered(store, "E1")
    assert not marker.exists()
    assert run_registered(store, "E1", replay=True) == 0
    assert marker.read_text() == "ran"


def test_registered_manifest_hash_tamper_detected(tmp_path):
    _, store, spec = fixture(tmp_path)
    freeze(spec, store)
    register(store, "E1", "dev_snapshot_v1", [sys.executable, "-c", "pass", "{snapshot_root}",
                                               "{membership_path}"])
    manifest_path = store / "versions/dev_snapshot_v1/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["payload"]["universe"]["exclusions"] = ["AAA"]
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(SnapshotError, match="manifest hash mismatch"):
        verify_registered(store, "E1")
