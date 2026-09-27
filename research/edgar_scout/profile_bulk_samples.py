"""Extract the sample ZIPs fetched by sample_bulk_downloads.py and measure real row counts,
column names/dtypes and a few sanity stats (date ranges, distinct filer counts) for each
table. Writes data/edgar_scout/profile.json.

Run: cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.edgar_scout.profile_bulk_samples
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pandas as pd

from research.edgar_scout.common import DATA_DIR

RAW = DATA_DIR / "raw"
EXTRACT = DATA_DIR / "extracted"


def extract_all() -> None:
    EXTRACT.mkdir(parents=True, exist_ok=True)
    for zpath in RAW.glob("*.zip"):
        dest = EXTRACT / zpath.stem
        dest.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zpath) as zf:
            zf.extractall(dest)
        print(f"extracted {zpath.name} -> {dest}")


def profile_tsv(path: Path, sep: str = "\t", nrows_full: bool = True) -> dict:
    # Count lines cheaply first (avoids loading huge num.txt fully into memory twice).
    with open(path, "rb") as f:
        n_lines = sum(1 for _ in f)
    n_rows = max(n_lines - 1, 0)
    df = pd.read_csv(path, sep=sep, dtype=str, nrows=5000, on_bad_lines="skip",
                      quoting=3, engine="python")
    return {
        "path": str(path.relative_to(DATA_DIR)),
        "n_rows": n_rows,
        "n_cols": df.shape[1],
        "columns": list(df.columns),
        "sample_row": df.iloc[0].to_dict() if len(df) else {},
        "file_size_bytes": path.stat().st_size,
    }


def profile_13f() -> dict:
    d = EXTRACT / "13f_2013q2"
    sub = profile_tsv(d / "SUBMISSION.tsv")
    info = profile_tsv(d / "INFOTABLE.tsv")
    cover = profile_tsv(d / "COVERPAGE.tsv")
    # distinct filers (CIK) and distinct issuers (CUSIP) in INFOTABLE via full-column scan
    filers = pd.read_csv(d / "SUBMISSION.tsv", sep="\t", dtype=str, usecols=["CIK", "FILING_DATE", "SUBMISSIONTYPE"])
    n_filers = filers["CIK"].nunique()
    n_submissions = len(filers)
    by_type = filers["SUBMISSIONTYPE"].value_counts().to_dict()
    date_min, date_max = filers["FILING_DATE"].min(), filers["FILING_DATE"].max()
    cusips = pd.read_csv(d / "INFOTABLE.tsv", sep="\t", dtype=str, usecols=["CUSIP"])
    n_issuers = cusips["CUSIP"].nunique()
    return {
        "tables": {"SUBMISSION": sub, "INFOTABLE": info, "COVERPAGE": cover},
        "n_filers_distinct_cik": int(n_filers),
        "n_submissions": int(n_submissions),
        "submissions_by_type": by_type,
        "filing_date_range": [date_min, date_max],
        "n_distinct_issuers_cusip": int(n_issuers),
        "n_position_rows": info["n_rows"],
    }


def profile_insider() -> dict:
    d = EXTRACT / "insider_2025q3_form345"
    sub = profile_tsv(d / "SUBMISSION.tsv")
    nd_trans = profile_tsv(d / "NONDERIV_TRANS.tsv")
    d_trans = profile_tsv(d / "DERIV_TRANS.tsv")
    owner = profile_tsv(d / "REPORTINGOWNER.tsv")
    subs = pd.read_csv(d / "SUBMISSION.tsv", sep="\t", dtype=str,
                        usecols=["ACCESSION_NUMBER", "FILING_DATE", "DOCUMENT_TYPE", "ISSUERCIK", "PERIOD_OF_REPORT"])
    by_type = subs["DOCUMENT_TYPE"].value_counts().to_dict()
    n_issuers = subs["ISSUERCIK"].nunique()
    date_min, date_max = subs["FILING_DATE"].min(), subs["FILING_DATE"].max()
    return {
        "tables": {"SUBMISSION": sub, "NONDERIV_TRANS": nd_trans, "DERIV_TRANS": d_trans, "REPORTINGOWNER": owner},
        "n_submissions": len(subs),
        "submissions_by_document_type": by_type,
        "n_distinct_issuers": int(n_issuers),
        "filing_date_range": [date_min, date_max],
    }


def profile_xbrl() -> dict:
    d = EXTRACT / "xbrl_fsds_2024q1"
    sub = profile_tsv(d / "sub.txt")
    num = profile_tsv(d / "num.txt")
    tag = profile_tsv(d / "tag.txt")
    pre = profile_tsv(d / "pre.txt")
    subs = pd.read_csv(d / "sub.txt", sep="\t", dtype=str,
                        usecols=["adsh", "cik", "name", "form", "period", "fy", "fp", "filed", "accepted"])
    n_filers = subs["cik"].nunique()
    by_form = subs["form"].value_counts().head(15).to_dict()
    date_min, date_max = subs["filed"].min(), subs["filed"].max()
    return {
        "tables": {"sub.txt": sub, "num.txt": num, "tag.txt": tag, "pre.txt": pre},
        "n_filers_distinct_cik": int(n_filers),
        "n_submissions": len(subs),
        "submissions_by_form": by_form,
        "filed_date_range": [date_min, date_max],
    }


def profile_ftd() -> dict:
    d = EXTRACT / "ftd_2024q1a"
    fname = next(d.iterdir())
    prof = profile_tsv(fname, sep="|")
    df = pd.read_csv(fname, sep="|", dtype=str, on_bad_lines="skip", quoting=3, engine="python")
    n_cusips = df["CUSIP"].nunique() if "CUSIP" in df.columns else None
    settle_col = "SETTLEMENT DATE" if "SETTLEMENT DATE" in df.columns else df.columns[0]
    date_vals = df[settle_col].unique().tolist()[:5]
    return {"table": prof, "n_distinct_cusips_in_5000row_sample": n_cusips,
            "settlement_dates_seen_in_sample": date_vals}


def main() -> None:
    extract_all()
    out = {
        "13F": profile_13f(),
        "insider_form345": profile_insider(),
        "xbrl_financial_statement_data_sets": profile_xbrl(),
        "fails_to_deliver": profile_ftd(),
    }
    (DATA_DIR / "profile.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "tables"} for k, v in out.items()},
                      indent=1, default=str))


if __name__ == "__main__":
    main()
