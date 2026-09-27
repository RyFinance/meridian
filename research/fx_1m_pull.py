"""Pull 1-minute FX candles from the LSE vault for later (separate) QA and a
pre-registered event study. DATA PULL ONLY: this script does not compute or
look at any event-conditional or economic-release-conditional statistics.

Pairs: EUR/USD, USD/JPY, GBP/USD, AUD/USD, USD/CAD, USD/CHF (dataset "fx").
Window: 2015-01-01 00:00 UTC through 2026-09-18 00:00 UTC.

Pulled year by year per pair so a failure is resumable: files already on disk
are skipped, and a year that keeps failing is recorded in the manifest under
"failed" rather than aborting the run.

Vault semantics (see data/lse_vault.py and the bar-start check this script
performs on the first pulled chunk): candles() pages 5,000 rows per call
internally and returns ts (UTC, tz-naive), open, high, low, close. ts marks
the START of the bar (confirmed below by resampling 1m to 1h and diffing
against a native 1h pull for the same window -- a purely mechanical check,
not tied to any event).

Run:
    PYTHONPATH=. .venv/bin/python research/fx_1m_pull.py
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import pandas as pd
from loguru import logger

from data.lse_vault import Vault

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "fx_1m"
MANIFEST_PATH = OUT / "manifest.json"

PAIRS = ["EUR/USD", "USD/JPY", "GBP/USD", "AUD/USD", "USD/CAD", "USD/CHF"]
DATASET = "fx"
TIMEFRAME = "1m"
START = pd.Timestamp("2015-01-01T00:00:00")
END = pd.Timestamp("2026-09-18T00:00:00")
YEARS = list(range(START.year, END.year + 1))

# Safety valve: stop pulling (but keep what's already on disk / in the
# manifest) if this run's vault usage would exceed this many bytes.
PULL_BYTE_CAP = 10 * 1024 ** 3


def _fname(pair: str) -> str:
    return pair.replace("/", "")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_atomic(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".parquet.tmp")
    df.to_parquet(tmp, index=False)
    tmp.replace(path)


def year_window(year: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    y_start = max(START, pd.Timestamp(f"{year}-01-01T00:00:00"))
    y_end = min(END, pd.Timestamp(f"{year + 1}-01-01T00:00:00"))
    return y_start, y_end


def confirm_bar_start_convention(vault: Vault) -> dict:
    """Mechanical, non-event check: pull one day of 1m and one day of native
    1h for the same pair/window, resample the 1m to 1h with label='left',
    closed='left', and diff against the native 1h pull. Zero diff confirms
    ts is the bar-START timestamp. Uses a window inside the pull range but
    picked with no reference to any economic release."""
    probe_start, probe_end = "2019-06-03", "2019-06-04"  # arbitrary weekday, well inside range
    m1 = vault.candles("EUR/USD", "1m", start=probe_start, end=probe_end, dataset=DATASET)
    h1 = vault.candles("EUR/USD", "1h", start=probe_start, end=probe_end, dataset=DATASET)
    m1i = m1.set_index("ts").sort_index()
    resampled = m1i.resample("1h", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"})
    h1i = h1.set_index("ts").sort_index()[["open", "high", "low", "close"]]
    common = resampled.index.intersection(h1i.index)
    max_diff = float((resampled.loc[common] - h1i.loc[common]).abs().max().max())
    return {
        "probe_window": [probe_start, probe_end],
        "max_abs_diff_resampled_1m_vs_native_1h": max_diff,
        "bars_compared": int(len(common)),
        "conclusion": "ts is bar-START (label=left, closed=left)" if max_diff == 0.0
                       else "INCONCLUSIVE -- diff is nonzero, do not assume bar-start",
    }


def _file_metadata(path: Path, skipped: bool) -> dict:
    """Metadata for the manifest, computed from the file on disk either way
    (freshly written or already present) so a resumed run's manifest entry
    is always complete -- never just a bare "skipped" flag."""
    existing = pd.read_parquet(path, columns=["ts"])
    return {
        "path": str(path.relative_to(ROOT)),
        "rows": int(len(existing)),
        "first_ts": str(existing["ts"].min()),
        "last_ts": str(existing["ts"].max()),
        "sha256": _sha256(path),
        "skipped": skipped,
    }


def pull_pair_year(vault: Vault, pair: str, year: int) -> dict:
    path = OUT / f"{_fname(pair)}_{year}.parquet"
    if path.exists():
        return _file_metadata(path, skipped=True)
    y_start, y_end = year_window(year)
    df = vault.candles(pair, TIMEFRAME, start=y_start.isoformat(), end=y_end.isoformat(), dataset=DATASET)
    if df.empty:
        raise RuntimeError(f"{pair} {year}: vault returned nothing")
    df = df[["ts", "open", "high", "low", "close"]].copy()
    df["ts"] = pd.to_datetime(df["ts"])
    if df["ts"].dt.tz is not None:
        df["ts"] = df["ts"].dt.tz_localize(None)
    df = df.sort_values("ts").reset_index(drop=True)
    _write_atomic(df, path)
    return _file_metadata(path, skipped=False)


def main() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    gitignore = OUT / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n!.gitignore\n")

    vault = Vault()
    usage_before = vault.usage()
    logger.info(f"vault usage before: {usage_before['bytes_used_month'] / 1e9:.3f} GB / "
                f"{usage_before['bytes_cap_month'] / 1e9:.1f} GB (month)")

    manifest: dict = {
        "pulled_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "dataset": DATASET,
        "timeframe": TIMEFRAME,
        "pairs": PAIRS,
        "window": [str(START), str(END)],
        "columns": ["ts", "open", "high", "low", "close"],
        "timestamp_convention": "bar-start, UTC, tz-naive",
        "files": {},
        "failed": {},
        "stopped_early_on_usage_cap": False,
    }
    if MANIFEST_PATH.exists():
        try:
            previous = json.loads(MANIFEST_PATH.read_text())
            manifest["files"].update(previous.get("files", {}))
        except Exception:
            pass

    manifest["bar_start_check"] = confirm_bar_start_convention(vault)
    logger.info(f"bar-start check: {manifest['bar_start_check']}")

    stop = False
    for pair in PAIRS:
        if stop:
            break
        for year in YEARS:
            key = f"{pair}/{year}"
            if vault.bytes_used > PULL_BYTE_CAP:
                logger.warning(f"stopping: this run's vault usage {vault.bytes_used / 1e9:.2f} GB "
                                f"exceeds the {PULL_BYTE_CAP / 1e9:.0f} GB pull safety cap")
                manifest["stopped_early_on_usage_cap"] = True
                stop = True
                break
            try:
                result = pull_pair_year(vault, pair, year)
                manifest["files"][key] = result
                tag = "already present, skipped" if result.get("skipped") else "pulled"
                logger.info(f"{key}: {tag}, {result['rows']} rows, {result['first_ts']} -> {result['last_ts']}")
                MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, default=str))  # checkpoint every chunk
            except Exception as e:
                manifest["failed"][key] = f"{type(e).__name__}: {str(e)[:300]}"
                logger.warning(f"{key} FAILED: {manifest['failed'][key]}")
                MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, default=str))

    usage_after = vault.usage()
    manifest["vault_bytes_used_this_run_client_tracked"] = vault.bytes_used
    manifest["vault_bytes_used_this_run_server_delta"] = (
        usage_after["bytes_used_month"] - usage_before["bytes_used_month"])
    manifest["usage_before"] = usage_before
    manifest["usage_after"] = usage_after
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, default=str))
    logger.info(f"done: {len(manifest['files'])} files ok, {len(manifest['failed'])} failed, "
                f"{vault.bytes_used / 1e9:.3f} GB used this run (client-tracked)")
    return manifest


if __name__ == "__main__":
    main()
