"""Price loading from a verified ``research.data_snapshot`` store/version -- and nothing else.

The price CSV has columns ``date,ticker,close,currency`` (extra columns ignored).  The USD/CAD rate is a row with
ticker ``USDCAD`` and currency ``CAD`` (close = CAD per 1 USD).  ETF closes are in the listing currency.

``load_prices`` runs ``research.data_snapshot.verify`` first (manifest hash, every content-addressed object and, by
default, the live input scope) and refuses on any failure; it then reads the price CSV from the frozen view and
re-hashes the exact bytes it parses against the manifest record.  There is no fallback to any other file.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from research import data_snapshot
from research.autopilot.config import USDCAD
from research.autopilot.holdings import parse_date

PRICE_COLUMNS = ("date", "ticker", "close", "currency")
CURRENCIES = ("CAD", "USD")


class PriceError(ValueError):
    """Price snapshot unverifiable or price CSV malformed (a refusal, never a fallback)."""


@dataclass(frozen=True)
class PriceData:
    dataset_version: str
    manifest_sha256: str
    keys: tuple[str, ...]
    file_sha256: dict[str, str]
    mode: str                                   # "verified" (source scope checked) or "replay" (objects only)
    series: dict[str, tuple[tuple[date, float, str], ...]]
    max_date: date

    def latest(self, ticker: str, on_or_before: date) -> tuple[date, float, str] | None:
        best = None
        for row in self.series.get(ticker, ()):
            if row[0] <= on_or_before:
                best = row
        return best


_ABS_PATH = re.compile(r"(?<![\w.~<>-])/(?:[^\s'\"/:,;()\[\]]+/)*([^\s'\"/:,;()\[\]]*)")


def location_free(text: str, store: Path) -> str:
    """Strip machine-specific locations from a message that goes into a report, summary or log line: the price
    store (as given, absolute or resolved) becomes ``<price-store>`` and any other absolute path keeps only its last
    component (``<path>/name``).  Outputs then read the same wherever the store and the repo live."""
    variants = set()
    for v in (Path(os.path.abspath(store)), Path(store).resolve()):    # absolute forms only
        if str(v) != "/":
            variants.add(str(v))
    for v in sorted(variants, key=len, reverse=True):
        text = text.replace(v, "<price-store>")
    return _ABS_PATH.sub(lambda m: f"<path>/{m.group(1)}" if m.group(1) else "<path>", text)


def _header(data: bytes) -> list[str]:
    first = data.decode("utf-8-sig", errors="replace").splitlines()[:1]
    return [c.strip() for c in next(csv.reader(first), [])] if first else []


def _parse_rows(data: bytes, label: str, series: dict[str, list[tuple[date, float, str]]],
                seen: set[tuple[str, date]]) -> None:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise PriceError(f"{label}: not UTF-8") from exc
    reader = csv.DictReader(io.StringIO(text))
    header = [c.strip() for c in (reader.fieldnames or [])]
    if not set(PRICE_COLUMNS) <= set(header) or len(set(header)) != len(header):
        raise PriceError(f"{label}: needs columns {list(PRICE_COLUMNS)}; got {header}")
    for n, raw in enumerate(reader, start=2):
        row = {(k or "").strip(): (v or "").strip() for k, v in raw.items() if k is not None}
        if not any(row.values()):
            continue
        try:
            d = parse_date(row["date"], f"{label} line {n} date")
        except ValueError as exc:
            raise PriceError(str(exc)) from exc
        ticker = row["ticker"]
        if not ticker:
            raise PriceError(f"{label} line {n}: empty ticker")
        try:
            close = float(row["close"])
        except ValueError as exc:
            raise PriceError(f"{label} line {n}: close {row['close']!r} is not a number") from exc
        if not math.isfinite(close) or close <= 0:
            raise PriceError(f"{label} line {n}: close must be a positive finite number; got {row['close']!r}")
        ccy = row["currency"]
        if ccy not in CURRENCIES:
            raise PriceError(f"{label} line {n}: currency must be one of {CURRENCIES}; got {ccy!r}")
        if (ticker, d) in seen:
            raise PriceError(f"{label} line {n}: duplicate price for {ticker} on {d.isoformat()}")
        seen.add((ticker, d))
        series.setdefault(ticker, []).append((d, close, ccy))


def parse_price_csvs(files: list[tuple[str, bytes]]) -> tuple[dict[str, tuple[tuple[date, float, str], ...]], date]:
    """Parse one or more price CSVs; a (ticker, date) pair may appear only once across all of them."""
    series: dict[str, list[tuple[date, float, str]]] = {}
    seen: set[tuple[str, date]] = set()
    for label, data in files:
        _parse_rows(data, label, series, seen)
    if not series:
        raise PriceError("price CSV has no rows")
    out = {t: tuple(sorted(rows)) for t, rows in sorted(series.items())}
    return out, max(r[0] for rows in out.values() for r in rows)


def parse_price_csv(data: bytes) -> tuple[dict[str, tuple[tuple[date, float, str], ...]], date]:
    return parse_price_csvs([("price CSV", data)])


def load_prices(store: Path, version: str, *, keys: list[str] | None = None,
                replay: bool = False) -> tuple[PriceData | None, str | None]:
    """Verify the snapshot and load its price CSV(s).  Returns (data, None) or (None, refusal reason).

    Without ``keys`` every CSV record of the snapshot whose header has the price columns is used (e.g. an ETF
    price file plus a separate USDCAD file); a snapshot with none is refused.
    """
    store = Path(store)
    try:
        manifest = data_snapshot.verify(store, version, source=not replay)
    except Exception as exc:  # any failure to verify is a refusal; there is no fallback path
        return None, location_free(f"price snapshot failed research.data_snapshot.verify: {type(exc).__name__}: "
                                   f"{exc}", store)
    records = {r["key"]: r for r in manifest["payload"]["records"]}
    view = store.resolve() / "versions" / version / "view"
    if not keys:
        keys = []
        for k in sorted(records):
            if k.lower().endswith(".csv"):
                try:
                    if set(PRICE_COLUMNS) <= set(_header((view / k).read_bytes())):
                        keys.append(k)
                except OSError:
                    continue
        if not keys:
            return None, f"snapshot {version} contains no price CSV with columns {list(PRICE_COLUMNS)}"
    keys = sorted(set(keys))
    files, shas = [], {}
    for key in keys:
        if key not in records:
            return None, f"price key {key!r} is not a record of snapshot {version}"
        try:
            data = (view / key).read_bytes()
        except OSError as exc:
            return None, f"price file {key} unreadable in frozen view: {exc.strerror or exc}"
        sha = hashlib.sha256(data).hexdigest()
        if sha != records[key]["sha256"] or len(data) != records[key]["byte_size"]:
            return None, f"price file bytes do not match manifest record {key}"
        files.append((key, data))
        shas[key] = sha
    try:
        series, max_date = parse_price_csvs(files)
    except PriceError as exc:
        return None, f"price CSV malformed: {exc}"
    return PriceData(dataset_version=version, manifest_sha256=manifest["manifest_sha256"], keys=tuple(keys),
                     file_sha256=shas, mode="replay" if replay else "verified",
                     series=series, max_date=max_date), None


def build_price_snapshot_spec(csv_path: Path, version: str, *, source: str, source_identifier: str | None,
                              retrieved_at: str) -> dict[str, Any]:
    """Freeze spec for a single owner-provided price CSV (helper for the owner; the engine never calls it).

    ``retrieved_at`` must come from the owner's ingestion record (ISO timestamp with timezone), never file mtime.
    """
    csv_path = Path(csv_path).resolve(strict=True)
    series, max_date = parse_price_csv(csv_path.read_bytes())
    dates = [r[0] for rows in series.values() for r in rows]
    key = f"prices/{csv_path.name}"
    meta = {key: {"source": source, "source_identifier": source_identifier, "retrieved_at": retrieved_at,
                  "logical_as_of": max_date.isoformat(), "symbol": "AUTOPILOT_PRICES",
                  "first_timestamp": f"{min(dates).isoformat()}T00:00:00+00:00",
                  "last_timestamp": f"{max_date.isoformat()}T00:00:00+00:00",
                  "row_count": len(dates), "temporal": True}}
    return {"dataset_version": version,
            "scopes": [{"name": "prices", "root": str(csv_path.parent), "include": [csv_path.name]}],
            "metadata": meta,
            "universe": {"membership_artifact": key, "exclusions": [], "symbol_mappings": {}, "delistings": [],
                         "note": "autopilot ETF universe is fixed in research/autopilot/config.py"},
            "intermediate_artifacts": []}


def freeze_price_csv(csv_path: Path, store: Path, version: str, *, source: str, source_identifier: str | None,
                     retrieved_at: str) -> str:
    """Freeze one price CSV into ``store`` under an immutable ``version``; returns the manifest SHA-256."""
    spec = build_price_snapshot_spec(csv_path, version, source=source, source_identifier=source_identifier,
                                     retrieved_at=retrieved_at)
    json.dumps(spec)  # fail early on non-JSON metadata
    return data_snapshot.freeze(spec, Path(store))["manifest_sha256"]
