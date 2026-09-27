"""
EIA NYMEX futures data: download (to quarantine) + coverage/metadata check.

Workload E, research cycle 4. This script implements the CRITICAL NO-CONTAMINATION RULE
from the task brief:
  - It downloads raw EIA files to data/eia_futures_QUARANTINE/ with a manifest
    (URL, fetch time, sha256, row counts, first/last date).
  - It does NOT compute or print any return, price change, spread, ratio, difference
    between contracts, level statistic (mean/min/max of prices), or plot of prices.
  - It does NOT look at contango/backwardation.
  - Coverage checks use dates and non-null counts only. Column names/dtypes and the
    first/last DATE may be printed; price VALUES are never printed or written anywhere
    in this script's outputs.

Run with:
  cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python research/eia_futures/download_and_coverage.py

Outputs:
  data/eia_futures_QUARANTINE/raw/*.xls   - raw downloaded bytes, untouched
  data/eia_futures_QUARANTINE/manifest.json - fetch manifest (URL, sha256, size, counts, first/last date)
  reports/eia_futures/series_table.json   - one row per (commodity, contract) series: dates/counts/units only
  reports/eia_futures/coverage_by_year.json - per series, per year: n_obs, n_expected_bdays, n_missing
  reports/eia_futures/all_contracts_present.json - per commodity: dates where contracts 1-4 are ALL non-null (count only)
  reports/eia_futures/duplicate_dates.json - per series: count of duplicate Date index entries
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
QUARANTINE_DIR = REPO_ROOT / "data" / "eia_futures_QUARANTINE"
RAW_DIR = QUARANTINE_DIR / "raw"
REPORT_DIR = REPO_ROOT / "reports" / "eia_futures"

USER_AGENT = "quant_v7-research/1.0"
HEADERS = {"User-Agent": USER_AGENT}
TIMEOUT = 60

# ---------------------------------------------------------------------------
# Targets. Bulk workbook files are the primary source (they carry the
# "Sourcekey" -> series-ID mapping plus the human-readable description for
# each contract, which we need for the series table). The individual
# per-series files (RCLC1d.xls etc., listed as "candidate free access paths"
# in the task brief) are also fetched for redundancy / cross-check, since
# the brief explicitly asked to test those URLs.
# ---------------------------------------------------------------------------
BULK_TARGETS = {
    "PET_PRI_FUT_S1_D.xls": "https://www.eia.gov/dnav/pet/xls/PET_PRI_FUT_S1_D.xls",
    "NG_PRI_FUT_S1_D.xls": "https://www.eia.gov/dnav/ng/xls/NG_PRI_FUT_S1_D.xls",
}

INDIVIDUAL_TARGETS = {
    # Crude oil (WTI, Cushing), contracts 1-4
    "RCLC1d.xls": "https://www.eia.gov/dnav/pet/hist_xls/RCLC1d.xls",
    "RCLC2d.xls": "https://www.eia.gov/dnav/pet/hist_xls/RCLC2d.xls",
    "RCLC3d.xls": "https://www.eia.gov/dnav/pet/hist_xls/RCLC3d.xls",
    "RCLC4d.xls": "https://www.eia.gov/dnav/pet/hist_xls/RCLC4d.xls",
    # Natural gas (Henry Hub), contracts 1-4
    "RNGC1d.xls": "https://www.eia.gov/dnav/ng/hist_xls/RNGC1d.xls",
    "RNGC2d.xls": "https://www.eia.gov/dnav/ng/hist_xls/RNGC2d.xls",
    "RNGC3d.xls": "https://www.eia.gov/dnav/ng/hist_xls/RNGC3d.xls",
    "RNGC4d.xls": "https://www.eia.gov/dnav/ng/hist_xls/RNGC4d.xls",
    # RBOB gasoline, contract 1 (bulk file has 1-4; single-series file kept for cross-check)
    "RBOB_C1.xls": "https://www.eia.gov/dnav/pet/hist_xls/EER_EPMRR_PE1_Y35NY_DPGd.xls",
    # Propane, contract 1 (bulk file has 1-4; single-series file kept for cross-check)
    "PROPANE_C1.xls": "https://www.eia.gov/dnav/pet/hist_xls/EER_EPLLPA_PE1_Y44MB_DPGd.xls",
}

ALL_TARGETS = {**BULK_TARGETS, **INDIVIDUAL_TARGETS}

# Which (workbook, sheet) hold which commodity group, for the bulk files.
# Values are metadata only (labels / sourcekeys), never price data.
BULK_SHEET_MAP = {
    "PET_PRI_FUT_S1_D.xls": {
        "Data 1": "crude_oil_wti_cushing",
        "Data 2": "gasoline_conventional_ny_harbor",  # discontinued 2006-12-29, replaced by RBOB
        "Data 3": "gasoline_rbob_ny_harbor",
        "Data 4": "heating_oil_no2_ny_harbor",
        "Data 5": "propane_mont_belvieu",
    },
    "NG_PRI_FUT_S1_D.xls": {
        "Data 1": "natural_gas_henry_hub_spot",  # spot, not futures contracts 1-4; kept for reference only
        "Data 2": "natural_gas_henry_hub_futures",
    },
}


def fetch(url: str) -> requests.Response:
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download_all() -> list[dict]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    manifest_entries = []
    for filename, url in ALL_TARGETS.items():
        dest = RAW_DIR / filename
        fetch_time = datetime.now(timezone.utc).isoformat()
        try:
            resp = fetch(url)
            content = resp.content
            dest.write_bytes(content)
            entry = {
                "filename": filename,
                "url": url,
                "fetch_time_utc": fetch_time,
                "http_status": resp.status_code,
                "content_type": resp.headers.get("Content-Type"),
                "byte_size": len(content),
                "sha256": sha256_bytes(content),
                "ok": True,
            }
        except Exception as exc:  # noqa: BLE001 - want to record failures in manifest
            entry = {
                "filename": filename,
                "url": url,
                "fetch_time_utc": fetch_time,
                "http_status": None,
                "content_type": None,
                "byte_size": None,
                "sha256": None,
                "ok": False,
                "error": str(exc),
            }
        manifest_entries.append(entry)
        print(f"[fetch] {filename}: ok={entry['ok']} bytes={entry.get('byte_size')}")
    return manifest_entries


# ---------------------------------------------------------------------------
# Parsing: dates / counts / dtypes ONLY. Never touch or print a price value.
# ---------------------------------------------------------------------------

def business_days_expected(first_date: pd.Timestamp, last_date: pd.Timestamp) -> int:
    """Count Mon-Fri calendar business days in [first_date, last_date] (no holiday calendar;
    this is a coarse expectation, NYMEX/US holidays will show up as 'missing' business days
    too, which is fine for a coverage scan)."""
    if pd.isna(first_date) or pd.isna(last_date):
        return 0
    return int(np.busday_count(first_date.date(), (last_date + pd.Timedelta(days=1)).date()))


def parse_bulk_workbook(filename: str, raw_bytes: bytes) -> tuple[dict, list[dict], dict]:
    """Returns (contents_metadata, per_series_rows, per_commodity_date_index)
    per_commodity_date_index maps commodity_key -> pd.DataFrame with Date + boolean
    non-null columns per contract (booleans only, no prices) for the all-4-present check.
    """
    buf = io.BytesIO(raw_bytes)
    xl = pd.ExcelFile(buf, engine="xlrd")

    contents_df = xl.parse("Contents", header=None)
    # Keep only the textual/metadata rows (drop fully-empty rows) as a JSON-safe structure.
    contents_rows = []
    for _, row in contents_df.iterrows():
        vals = [None if pd.isna(v) else (str(v) if not isinstance(v, (int, float)) else v) for v in row.tolist()]
        if any(v is not None for v in vals):
            contents_rows.append(vals)
    contents_meta = {"sheet": "Contents", "rows": contents_rows}

    series_rows = []
    commodity_presence = {}

    sheet_map = BULK_SHEET_MAP.get(filename, {})
    for sheet_name, commodity_key in sheet_map.items():
        if sheet_name not in xl.sheet_names:
            continue
        raw = xl.parse(sheet_name, header=None)
        # Row 0: "Back to Contents" / "Data N: <description>"
        # Row 1: Sourcekey row -> ["Sourcekey", "RCLC1", "RCLC2", ...]
        # Row 2: Date / <long description with units> per column
        # Row 3+: data, first column = Date, rest = numeric (NEVER read as values here)
        header_desc = str(raw.iloc[0, 1]) if raw.shape[0] > 0 else None
        sourcekey_row = raw.iloc[1].tolist() if raw.shape[0] > 1 else []
        longdesc_row = raw.iloc[2].tolist() if raw.shape[0] > 2 else []

        data = raw.iloc[3:].copy()
        data.columns = raw.iloc[2].tolist()  # ["Date", "<desc1>", "<desc2>", ...]
        date_col = data.columns[0]
        # Parse dates only (needed for coverage); this is metadata (calendar), not a price value.
        dates = pd.to_datetime(data[date_col], errors="coerce")

        n_cols = data.shape[1] - 1
        presence_frame = {"Date": dates}
        for i in range(1, data.shape[1]):
            sourcekey = sourcekey_row[i] if i < len(sourcekey_row) else None
            longdesc = longdesc_row[i] if i < len(longdesc_row) else None
            colname = data.columns[i]
            col_series = data[colname]
            # non-null mask only -- we never read/print the numeric content itself.
            non_null_mask = col_series.notna() & (dates.notna())
            n_obs = int(non_null_mask.sum())
            valid_dates = dates[non_null_mask]
            first_date = valid_dates.min() if n_obs > 0 else pd.NaT
            last_date = valid_dates.max() if n_obs > 0 else pd.NaT
            dup_dates = int(dates[dates.notna()].duplicated().sum())
            expected_bdays = business_days_expected(first_date, last_date) if n_obs > 0 else 0
            dtype_str = str(col_series.dtype)

            series_rows.append(
                {
                    "workbook": filename,
                    "sheet": sheet_name,
                    "commodity_key": commodity_key,
                    "sourcekey": sourcekey,
                    "column_description": longdesc,
                    "contract_position": i,  # 1..4 (or 1 for single-series propane/RBOB cross-checks)
                    "dtype": dtype_str,
                    "n_rows_total": int(len(data)),
                    "n_obs_non_null": n_obs,
                    "first_date": None if pd.isna(first_date) else first_date.strftime("%Y-%m-%d"),
                    "last_date": None if pd.isna(last_date) else last_date.strftime("%Y-%m-%d"),
                    "n_duplicate_dates_in_sheet": dup_dates,
                    "n_expected_bdays_in_span": expected_bdays,
                    "n_missing_vs_expected_bdays": (expected_bdays - n_obs) if n_obs > 0 else None,
                }
            )
            presence_frame[f"contract_{i}_present"] = non_null_mask.values

        commodity_presence[commodity_key] = pd.DataFrame(presence_frame)

    return contents_meta, series_rows, commodity_presence


def coverage_by_year(commodity_presence: dict[str, pd.DataFrame]) -> list[dict]:
    rows = []
    for commodity_key, df in commodity_presence.items():
        d = df.copy()
        d["year"] = d["Date"].dt.year
        contract_cols = [c for c in d.columns if c.startswith("contract_")]
        for year, grp in d.groupby("year"):
            if pd.isna(year):
                continue
            for c in contract_cols:
                n_obs = int(grp[c].sum())
                n_rows = int(len(grp))
                rows.append(
                    {
                        "commodity_key": commodity_key,
                        "year": int(year),
                        "contract_column": c,
                        "n_obs_non_null": n_obs,
                        "n_calendar_rows_in_sheet_for_year": n_rows,
                    }
                )
    return rows


def all_contracts_present_summary(commodity_presence: dict[str, pd.DataFrame]) -> list[dict]:
    rows = []
    for commodity_key, df in commodity_presence.items():
        contract_cols = sorted([c for c in df.columns if c.startswith("contract_")])
        if len(contract_cols) < 2:
            continue
        all_present = df[contract_cols].all(axis=1)
        any_present = df[contract_cols].any(axis=1)
        rows.append(
            {
                "commodity_key": commodity_key,
                "n_contract_columns": len(contract_cols),
                "n_dates_any_contract_present": int(any_present.sum()),
                "n_dates_all_contracts_present": int(all_present.sum()),
                "first_date_any_present": None
                if not any_present.any()
                else df.loc[any_present, "Date"].min().strftime("%Y-%m-%d"),
                "last_date_any_present": None
                if not any_present.any()
                else df.loc[any_present, "Date"].max().strftime("%Y-%m-%d"),
                "first_date_all_present": None
                if not all_present.any()
                else df.loc[all_present, "Date"].min().strftime("%Y-%m-%d"),
                "last_date_all_present": None
                if not all_present.any()
                else df.loc[all_present, "Date"].max().strftime("%Y-%m-%d"),
            }
        )
    return rows


def parse_individual_file(filename: str, raw_bytes: bytes) -> dict:
    """Cross-check: parse a single-series hist_xls file (e.g. RCLC1d.xls). Same
    dates/counts-only discipline as the bulk parser."""
    buf = io.BytesIO(raw_bytes)
    xl = pd.ExcelFile(buf, engine="xlrd")
    sheet_name = "Data 1" if "Data 1" in xl.sheet_names else xl.sheet_names[-1]
    raw = xl.parse(sheet_name, header=None)
    sourcekey_row = raw.iloc[1].tolist() if raw.shape[0] > 1 else []
    longdesc_row = raw.iloc[2].tolist() if raw.shape[0] > 2 else []
    data = raw.iloc[3:].copy()
    if raw.shape[0] > 2:
        data.columns = raw.iloc[2].tolist()
    date_col = data.columns[0]
    dates = pd.to_datetime(data[date_col], errors="coerce")
    col = data.columns[1] if data.shape[1] > 1 else None
    non_null_mask = data[col].notna() & dates.notna() if col is not None else pd.Series(dtype=bool)
    n_obs = int(non_null_mask.sum())
    valid_dates = dates[non_null_mask]
    first_date = valid_dates.min() if n_obs > 0 else pd.NaT
    last_date = valid_dates.max() if n_obs > 0 else pd.NaT
    dup_dates = int(dates[dates.notna()].duplicated().sum())
    return {
        "filename": filename,
        "sheet": sheet_name,
        "sourcekey": sourcekey_row[1] if len(sourcekey_row) > 1 else None,
        "column_description": longdesc_row[1] if len(longdesc_row) > 1 else None,
        "dtype": str(data[col].dtype) if col is not None else None,
        "n_rows_total": int(len(data)),
        "n_obs_non_null": n_obs,
        "first_date": None if pd.isna(first_date) else first_date.strftime("%Y-%m-%d"),
        "last_date": None if pd.isna(last_date) else last_date.strftime("%Y-%m-%d"),
        "n_duplicate_dates_in_sheet": dup_dates,
    }


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)

    manifest_entries = download_all()
    manifest_path = QUARANTINE_DIR / "manifest.json"
    manifest_path.write_text(json.dumps({"generated_utc": datetime.now(timezone.utc).isoformat(),
                                          "user_agent": USER_AGENT,
                                          "entries": manifest_entries}, indent=2))
    print(f"[manifest] wrote {manifest_path}")

    all_series_rows = []
    all_contents_meta = {}
    all_commodity_presence: dict[str, pd.DataFrame] = {}
    individual_rows = []

    for filename in BULK_TARGETS:
        entry = next((e for e in manifest_entries if e["filename"] == filename), None)
        if not entry or not entry["ok"]:
            print(f"[skip] {filename} not downloaded successfully")
            continue
        raw_bytes = (RAW_DIR / filename).read_bytes()
        contents_meta, series_rows, commodity_presence = parse_bulk_workbook(filename, raw_bytes)
        all_contents_meta[filename] = contents_meta
        all_series_rows.extend(series_rows)
        all_commodity_presence.update(commodity_presence)

    for filename in INDIVIDUAL_TARGETS:
        entry = next((e for e in manifest_entries if e["filename"] == filename), None)
        if not entry or not entry["ok"]:
            print(f"[skip] {filename} not downloaded successfully")
            continue
        raw_bytes = (RAW_DIR / filename).read_bytes()
        try:
            individual_rows.append(parse_individual_file(filename, raw_bytes))
        except Exception as exc:  # noqa: BLE001
            individual_rows.append({"filename": filename, "error": str(exc)})

    (REPORT_DIR / "series_table.json").write_text(json.dumps(all_series_rows, indent=2, default=str))
    (REPORT_DIR / "contents_metadata.json").write_text(json.dumps(all_contents_meta, indent=2, default=str))
    (REPORT_DIR / "individual_file_crosscheck.json").write_text(json.dumps(individual_rows, indent=2, default=str))

    cov_rows = coverage_by_year(all_commodity_presence)
    (REPORT_DIR / "coverage_by_year.json").write_text(json.dumps(cov_rows, indent=2, default=str))

    presence_rows = all_contracts_present_summary(all_commodity_presence)
    (REPORT_DIR / "all_contracts_present.json").write_text(json.dumps(presence_rows, indent=2, default=str))

    print(f"[done] series_table rows={len(all_series_rows)}, coverage_by_year rows={len(cov_rows)}, "
          f"all_contracts_present rows={len(presence_rows)}, individual cross-check rows={len(individual_rows)}")
    print("[reminder] No price value was read, printed, or written by this script. "
          "Only dates, counts, dtypes and textual metadata.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
