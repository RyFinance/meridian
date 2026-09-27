"""Read-only parsers for the existing project evidence.

Everything here reads files already on disk (preregistrations.jsonl, the
other agent's evidence_audit_20260923 outputs, null_lab2's outputs, and raw
per-trial daily/event return CSVs). Nothing here computes new strategy
performance; series loaders only reshape existing return columns onto a
monthly grid so correlation structure can be measured (task instruction:
"for correlation structure only").
"""
from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone

import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _p(*parts: str) -> str:
    return os.path.join(REPO_ROOT, *parts)


# ---------------------------------------------------------------------------
# preregistrations.jsonl
# ---------------------------------------------------------------------------

def load_preregistrations(path: str = "research/preregistrations.jsonl") -> list[dict]:
    """Parse every line of the registration ledger.

    Adds a normalized `registered_at_utc` (timezone-aware datetime) field for
    chronological comparisons, and a best-effort `family_id` guess derived
    from the file path's directory (overridable by the caller for special
    cases like the two protocol-amendment files).
    """
    out = []
    with open(_p(path)) as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            d["_lineno"] = lineno
            ts = d.get("registered_at")
            dt = _parse_ts(ts)
            d["registered_at_utc"] = dt
            d["_dir_guess"] = _dir_of(d["file"])
            out.append(d)
    out.sort(key=lambda r: r["registered_at_utc"])
    return out


def _parse_ts(ts: str):
    # Two formats seen in the file: "2026-09-17T18:44:54-0700" and
    # "2026-09-23T13:04:23.773567-07:00"
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            return datetime.strptime(ts, fmt).astimezone(timezone.utc)
        except ValueError:
            continue
    # last resort: fromisoformat handles both with a small normalization
    ts2 = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(ts2).astimezone(timezone.utc)


def _dir_of(file_path: str) -> str:
    parts = file_path.split("/")
    if len(parts) >= 2 and parts[0] in ("research", "reports"):
        return parts[1]
    return parts[0]


# ---------------------------------------------------------------------------
# The other agent's evidence_audit_20260923 outputs, and null_lab2 outputs
# ---------------------------------------------------------------------------

def load_registered_trials_csv(path: str = "reports/evidence_audit_20260923/registered_trials.csv") -> list[dict]:
    with open(_p(path)) as f:
        return list(csv.DictReader(f))


def load_gate_table(path: str = "reports/null_lab2/gate_table.csv") -> list[dict]:
    with open(_p(path)) as f:
        return list(csv.DictReader(f))


def load_multiple_testing_json(path: str = "reports/null_lab2/multiple_testing.json") -> dict:
    with open(_p(path)) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Generic return-series loader -> monthly-aggregated pandas Series
# ---------------------------------------------------------------------------

def load_series_monthly(path: str, date_col: str, value_col: str, header: int = 0) -> pd.Series:
    """Load one (date, return) pair from a CSV and aggregate to monthly sums.

    Monthly-sum is a simple additive approximation (not compounding) used
    solely to put heterogeneous-frequency series (daily marks, multi-week
    option-cycle marks) onto a common grid for correlation estimation. It is
    not used to report any performance number.
    """
    df = pd.read_csv(_p(path), header=header)
    if date_col not in df.columns:
        raise KeyError(f"{path}: no column {date_col!r}; have {list(df.columns)[:8]}")
    if value_col not in df.columns:
        raise KeyError(f"{path}: no column {value_col!r}; have {list(df.columns)[:8]}")
    dates = pd.to_datetime(df[date_col], errors="coerce")
    vals = pd.to_numeric(df[value_col], errors="coerce")
    s = pd.Series(vals.values, index=dates)
    s = s[s.index.notna()]
    monthly = s.groupby(s.index.to_period("M")).sum(min_count=1)
    return monthly


def load_etf_hybrids_multiindex(path: str, sleeve_cols: list[str], value_row_label: str = "net_ex") -> dict[str, pd.Series]:
    """etf_hybrids/{dev,validation}/daily.csv has a 2-row multi-index header:
    row0 = sleeve name (E1..E5,B,R0,SPY), row1 = field (net_ex, gross_ex, ...).
    The date column is unlabeled in both header rows.
    """
    raw = pd.read_csv(_p(path), header=[0, 1])
    out = {}
    date_col = raw.columns[0]
    dates = pd.to_datetime(raw[date_col].iloc[:, 0] if isinstance(raw[date_col], pd.DataFrame) else raw[date_col], errors="coerce")
    for sleeve in sleeve_cols:
        try:
            col = raw[(sleeve, value_row_label)]
        except KeyError:
            continue
        vals = pd.to_numeric(col, errors="coerce")
        s = pd.Series(vals.values, index=dates)
        s = s[s.index.notna()]
        out[sleeve] = s.groupby(s.index.to_period("M")).sum(min_count=1)
    return out


def build_monthly_panel(series_specs: list[dict]) -> pd.DataFrame:
    """series_specs: list of {id, path, date_col, value_col, header?} ->
    wide DataFrame indexed by month, one column per series id. Skips (and
    records) any spec whose file is missing or unparsable rather than
    failing the whole build.
    """
    cols = {}
    failures = []
    for spec in series_specs:
        try:
            s = load_series_monthly(spec["path"], spec["date_col"], spec["value_col"], header=spec.get("header", 0))
            if s.dropna().shape[0] < 3:
                failures.append((spec["id"], "too few non-null monthly obs"))
                continue
            cols[spec["id"]] = s
        except Exception as e:  # noqa: BLE001 - want to keep going and report
            failures.append((spec["id"], str(e)))
    panel = pd.DataFrame(cols)
    panel.index = panel.index.astype(str)
    return panel, failures
