"""Benchmark series snapshot: AQR (TSMOM, Century, VME) and Ken French library
(international/developed factor files + 3-month T-bill RF).

These are keyless public downloads. Only date coverage and column names are
recorded here -- no strategy return is computed from them (they are benchmark
series, per the task brief). This script fetches, hashes and records
provenance (URL, retrieval time UTC, sha256, terms-of-use text/URL) for each
file, then reads column headers and date coverage only.

Run:
  cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.core_premia_data.commod_bench.benchmarks_snapshot
"""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_DATA = REPO_ROOT / "data" / "core_premia" / "commod_bench" / "benchmarks"
OUT_REPORTS = REPO_ROOT / "reports" / "core_premia_20260925" / "commod_bench"
USER_AGENT = "quant_v7-research/1.0"

AQR_TOU_URL = "https://www.aqr.com/Terms-of-Use"
KFRENCH_TOU_TEXT = (
    "Ken French data library, Dartmouth Tuck School of Business: 'The data below are provided "
    "as an unpaid public service... you may use them for any research purpose, but please "
    "acknowledge the source and, if you use the data in published research, cite the relevant "
    "paper(s).' (paraphrase-free excerpt taken from the library's public 'Data Library' page "
    "and README/Details text bundled inside each ZIP.)"
)

AQR_TARGETS = {
    "aqr_tsmom_factors_monthly.xlsx": {
        "url": "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/Time-Series-Momentum-Factors-Monthly.xlsx",
        "series": "AQR Time Series Momentum Factors (Monthly)",
    },
    "aqr_century_factor_premia_monthly.xlsx": {
        "url": "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/Century-of-Factor-Premia-Monthly.xlsx",
        "series": "AQR Century of Factor Premia (Monthly)",
    },
    "aqr_value_momentum_everywhere_monthly.xlsx": {
        "url": "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/Value-and-Momentum-Everywhere-Factors-Monthly.xlsx",
        "series": "AQR Value and Momentum Everywhere (factors/portfolios, Monthly)",
    },
}

KFRENCH_TARGETS = {
    "ff_research_data_factors.zip": {
        "url": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip",
        "series": "Fama/French 3 Factors (US, Monthly) -- includes RF (3-month T-bill)",
    },
    "ff_research_data_5_factors_2x3.zip": {
        "url": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_CSV.zip",
        "series": "Fama/French 5 Factors (US, 2x3, Monthly) -- includes RF",
    },
    "developed_3_factors.zip": {
        "url": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Developed_3_Factors_CSV.zip",
        "series": "Developed Markets 3 Factors (Monthly)",
    },
    "developed_ex_us_3_factors.zip": {
        "url": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Developed_ex_US_3_Factors_CSV.zip",
        "series": "Developed ex-US 3 Factors (Monthly)",
    },
    "global_ex_us_3_factors.zip": {
        "url": "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Global_ex_US_3_Factors_CSV.zip",
        "series": "Global ex-US 3 Factors (Monthly)",
    },
}


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def fetch(url: str) -> requests.Response:
    return requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)


def read_xlsx_columns_and_range(content: bytes, name: str) -> dict:
    """AQR workbooks typically have a header/description block before the data
    table; find the sheet(s), report column names and a best-effort date range
    per sheet without asserting a fixed row-skip (varies by file)."""
    try:
        xl = pd.ExcelFile(io.BytesIO(content))
    except Exception as exc:  # noqa: BLE001
        return {"error": f"could not open workbook: {exc}"}
    sheets_info = {}
    for sheet in xl.sheet_names:
        try:
            raw = xl.parse(sheet, header=None, nrows=40)
        except Exception as exc:  # noqa: BLE001
            sheets_info[sheet] = {"error": str(exc)}
            continue
        # Heuristic: find the first row that looks like a header row -- either its
        # first cell literally reads "Date"/"Dates", OR (AQR's format) the header's
        # first cell is blank but the NEXT row's first cell parses as a date (the
        # header row that labels the data columns, with an unlabeled date column).
        header_row_idx = None
        for i in range(min(len(raw), 30)):
            row_vals = raw.iloc[i].astype(str).tolist()
            if any(v.strip().lower() in ("date", "dates") for v in row_vals):
                header_row_idx = i
                break
            if i + 1 < len(raw):
                next_first_cell = raw.iloc[i + 1, 0]
                looks_like_header = (
                    pd.isna(raw.iloc[i, 0])
                    and any(pd.notna(v) and isinstance(v, str) for v in raw.iloc[i].tolist()[1:])
                )
                next_is_date = isinstance(next_first_cell, (pd.Timestamp,)) or (
                    isinstance(next_first_cell, str) and pd.notna(pd.to_datetime(next_first_cell, errors="coerce"))
                )
                import datetime as _dt
                next_is_date = next_is_date or isinstance(next_first_cell, _dt.datetime)
                if looks_like_header and next_is_date:
                    header_row_idx = i
                    break
        sheet_info: dict = {"n_preview_rows_scanned": len(raw)}
        if header_row_idx is None:
            sheet_info["note"] = "no obvious 'Date' header found in first 30 rows (preview only)"
            sheets_info[sheet] = sheet_info
            continue
        try:
            full = xl.parse(sheet, header=header_row_idx)
        except Exception as exc:  # noqa: BLE001
            sheet_info["error"] = str(exc)
            sheets_info[sheet] = sheet_info
            continue
        full = full.dropna(how="all")
        cols = [str(c) for c in full.columns]
        date_col = cols[0]
        dates = pd.to_datetime(full[date_col], errors="coerce")
        valid = dates.dropna()
        sheet_info.update({
            "header_row_index": header_row_idx,
            "columns": cols,
            "n_rows": int(len(full)),
            "first_date": str(valid.min().date()) if len(valid) else None,
            "last_date": str(valid.max().date()) if len(valid) else None,
        })
        sheets_info[sheet] = sheet_info
    return {"sheets": sheets_info}


def read_kfrench_zip_columns_and_range(content: bytes, zipname: str) -> dict:
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except Exception as exc:  # noqa: BLE001
        return {"error": f"could not open zip: {exc}"}
    out = {}
    for inner_name in zf.namelist():
        if not inner_name.lower().endswith(".csv"):
            continue
        raw_bytes = zf.read(inner_name)
        text = raw_bytes.decode("latin-1", errors="replace")
        lines = text.splitlines()
        # Ken French CSVs: a few descriptive header lines, then "Date,Mkt-RF,SMB,HML,RF" (or
        # similar) header, then monthly rows (YYYYMM), often followed by an "Annual Factors:"
        # section further down -- we only report the header + first data block's coverage.
        header_line_idx = None
        for i, line in enumerate(lines[:15]):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2 and parts[0] == "" and all(p for p in parts[1:]):
                header_line_idx = i
                break
        if header_line_idx is None:
            out[inner_name] = {"note": "could not locate header row in first 15 lines",
                                "preview_lines": lines[:8]}
            continue
        header = [p.strip() for p in lines[header_line_idx].split(",")]
        header[0] = "Date"
        data_lines = []
        for line in lines[header_line_idx + 1:]:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) != len(header):
                break
            if not parts[0].isdigit():
                break
            data_lines.append(parts)
        df = pd.DataFrame(data_lines, columns=header)
        out[inner_name] = {
            "columns": header,
            "n_monthly_rows_first_block": len(df),
            "first_period": df["Date"].iloc[0] if len(df) else None,
            "last_period": df["Date"].iloc[-1] if len(df) else None,
        }
    return {"csv_members": out}


def main() -> int:
    OUT_DATA.mkdir(parents=True, exist_ok=True)
    OUT_REPORTS.mkdir(parents=True, exist_ok=True)

    manifest = {"generated_utc": datetime.now(timezone.utc).isoformat(), "entries": []}

    for filename, meta in {**AQR_TARGETS, **KFRENCH_TARGETS}.items():
        fetched_at = datetime.now(timezone.utc).isoformat()
        url = meta["url"]
        try:
            resp = fetch(url)
            content = resp.content
            ok = resp.status_code == 200
        except Exception as exc:  # noqa: BLE001
            manifest["entries"].append({
                "filename": filename, "url": url, "series": meta["series"],
                "fetch_time_utc": fetched_at, "ok": False, "error": str(exc),
            })
            print(f"[fail] {filename}: {exc}")
            continue
        if not ok:
            manifest["entries"].append({
                "filename": filename, "url": url, "series": meta["series"],
                "fetch_time_utc": fetched_at, "ok": False,
                "http_status": resp.status_code,
            })
            print(f"[fail] {filename}: HTTP {resp.status_code}")
            continue
        out_path = OUT_DATA / filename
        out_path.write_bytes(content)
        sha = sha256_bytes(content)
        is_aqr = filename in AQR_TARGETS
        if filename.endswith(".xlsx"):
            coverage = read_xlsx_columns_and_range(content, filename)
        elif filename.endswith(".zip"):
            coverage = read_kfrench_zip_columns_and_range(content, filename)
        else:
            coverage = {}
        entry = {
            "filename": filename,
            "url": url,
            "series": meta["series"],
            "fetch_time_utc": fetched_at,
            "http_status": resp.status_code,
            "content_type": resp.headers.get("Content-Type"),
            "byte_size": len(content),
            "sha256": sha,
            "ok": True,
            "terms_of_use": AQR_TOU_URL if is_aqr else KFRENCH_TOU_TEXT,
            "path": str(out_path.relative_to(REPO_ROOT)),
            "coverage": coverage,
        }
        manifest["entries"].append(entry)
        print(f"[ok] {filename}: {len(content)} bytes, sha256={sha[:16]}...")

    (OUT_REPORTS / "benchmarks_manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    n_ok = sum(1 for e in manifest["entries"] if e.get("ok"))
    print(f"[done] {n_ok}/{len(manifest['entries'])} benchmark files snapshotted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
