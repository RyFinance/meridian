"""Snapshot-only loaders. Every path is resolved INSIDE the frozen snapshot view given on the command line
({snapshot_root}); the membership/candidate file ({membership_path}) must also lie inside it. Nothing here reads
the mutable data/ archive.

Panel file format (csv or parquet), long: columns ``date, market_id, value``; one row per (date, market_id).
Candidate list (membership) csv: at least ``class, market_id, qa_status``; status values PASS/FAIL.
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

LONG_COLS = ("date", "market_id", "value")
CAND_COLS = ("class", "market_id", "qa_status")


class SnapshotPathError(RuntimeError):
    pass


def _inside(root: Path, p: Path) -> bool:
    r = os.path.abspath(root)
    q = os.path.abspath(p)
    return q == r or q.startswith(r.rstrip(os.sep) + os.sep)


def resolve(snapshot_root, rel: str) -> Path:
    """Path of ``rel`` inside the snapshot view (no absolute paths, no '..', must exist)."""
    root = Path(snapshot_root)
    relp = Path(rel)
    if relp.is_absolute() or ".." in relp.parts:
        raise SnapshotPathError(f"input path must be relative to the snapshot root: {rel!r}")
    p = root / relp
    if not _inside(root, p):
        raise SnapshotPathError(f"input escapes snapshot root: {rel!r}")
    if not p.exists():
        raise SnapshotPathError(f"input missing from snapshot: {rel!r}")
    return p


def _read_table(p: Path) -> pd.DataFrame:
    s = p.name.lower()
    if s.endswith(".parquet"):
        return pd.read_parquet(p)
    if s.endswith(".csv") or s.endswith(".csv.gz"):
        return pd.read_csv(p)
    raise SnapshotPathError(f"unsupported file type: {p.name}")


def read_long(snapshot_root, rel: str, market_ids=None) -> pd.DataFrame:
    df = _read_table(resolve(snapshot_root, rel))
    missing = [c for c in LONG_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"{rel}: missing columns {missing}; long format is {LONG_COLS}")
    df = df.loc[:, list(LONG_COLS)].copy()
    df["date"] = pd.to_datetime(df["date"])
    df["market_id"] = df["market_id"].astype(str)
    df["value"] = pd.to_numeric(df["value"], errors="raise").astype(float)
    if market_ids is not None:
        df = df[df["market_id"].isin([str(m) for m in market_ids])]
    if df.duplicated(["date", "market_id"]).any():
        raise ValueError(f"{rel}: duplicate (date, market_id) rows")
    return df


def long_to_wide(df: pd.DataFrame, columns=None) -> pd.DataFrame:
    w = df.pivot(index="date", columns="market_id", values="value").sort_index()
    w.columns.name = None
    if columns is not None:
        w = w.reindex(columns=list(columns))
    return w


def read_wide(snapshot_root, rel: str, columns=None) -> pd.DataFrame:
    return long_to_wide(read_long(snapshot_root, rel, columns), columns)


def read_series(snapshot_root, ref: dict) -> pd.Series:
    """ref = {"path": rel, "market_id": id}."""
    df = read_long(snapshot_root, ref["path"], [ref["market_id"]])
    if df.empty:
        raise ValueError(f"series {ref} empty in snapshot")
    return df.set_index("date")["value"].sort_index().rename(str(ref["market_id"]))


def load_candidates(snapshot_root, membership_path) -> pd.DataFrame:
    p = Path(membership_path)
    if not _inside(Path(snapshot_root), p):
        raise SnapshotPathError("membership file must lie inside the snapshot root")
    if not p.exists():
        raise SnapshotPathError(f"membership file missing: {p}")
    df = _read_table(p)
    missing = [c for c in CAND_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"candidate list missing columns {missing}")
    df = df.copy()
    df["market_id"] = df["market_id"].astype(str)
    return df


def universe(cands: pd.DataFrame, cls: str) -> list[str]:
    """Every PASS row of the class (aliases, if an ``alias_of`` column exists, count once)."""
    d = cands[(cands["class"].astype(str) == cls) & (cands["qa_status"].astype(str).str.upper() == "PASS")]
    if "alias_of" in d.columns:
        d = d[d["alias_of"].isna() | (d["alias_of"].astype(str) == "")]
    return sorted(d["market_id"].unique().tolist())


def class_map(cands: pd.DataFrame) -> dict:
    return dict(zip(cands["market_id"].astype(str), cands["class"].astype(str)))
