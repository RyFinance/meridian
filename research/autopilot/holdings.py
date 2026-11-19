"""Holdings file (hand-edited by the owner): CSV or JSON.

JSON::

    {"as_of": "2026-09-25", "cash_cad": 1250.00, "cash_usd": 0, "margin_loan_cad": 0,
     "net_external_flow_cad": 0, "positions": {"XEQT.TO": 1200, "ZAG.TO": 800}}

CSV (header ``record,key,value``)::

    record,key,value
    field,as_of,2026-09-25
    field,cash_cad,1250.00
    field,cash_usd,0
    field,net_external_flow_cad,0
    position,XEQT.TO,1200

Required fields: ``as_of``, ``cash_cad``, ``cash_usd``, ``net_external_flow_cad`` (net CAD deposited minus
withdrawn since the last *accepted* report in the paper log); ``margin_loan_cad`` is required for margin accounts
and must be 0 or absent otherwise (that check is an account-constraint refusal in the engine).  Shares are
whole, non-negative numbers; cash balances and the loan are non-negative.  Anything else is unparsable.
"""
from __future__ import annotations

import csv
import hashlib
import io
import math
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from research.autopilot.config import UNIVERSE, strict_json_loads

FIELDS = ("as_of", "cash_cad", "cash_usd", "margin_loan_cad", "net_external_flow_cad")
MAX_SHARES = 10**9            # sanity bound: anything larger is treated as a typo (unparsable)
MAX_MONEY = 1e12              # sanity bound on cash / loan / flow magnitudes (CAD or USD)
REQUIRED = ("as_of", "cash_cad", "cash_usd", "net_external_flow_cad")


class HoldingsError(ValueError):
    """Holdings file unparsable, unknown ticker, negative/fractional shares or negative balances."""


@dataclass(frozen=True)
class Holdings:
    as_of: date
    positions: dict[str, int]
    cash_cad: float
    cash_usd: float
    margin_loan_cad: float
    margin_loan_given: bool
    net_external_flow_cad: float
    sha256: str
    extra: dict[str, Any] = field(default_factory=dict)


def parse_date(text: Any, what: str) -> date:
    if not isinstance(text, str) or len(text) != 10:
        raise ValueError(f"{what} must be an ISO date YYYY-MM-DD; got {text!r}")
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{what} must be an ISO date YYYY-MM-DD; got {text!r}") from exc


def _number(value: Any, what: str) -> Decimal:
    if isinstance(value, bool):
        raise HoldingsError(f"{what}: not a number: {value!r}")
    try:
        d = Decimal(str(value).strip()) if isinstance(value, (str, int, float)) else None
    except InvalidOperation:
        d = None
    if d is None or not d.is_finite():
        raise HoldingsError(f"{what}: not a finite number: {value!r}")
    return d


def _money(value: Any, what: str, *, allow_negative: bool = False) -> float:
    d = _number(value, what)
    if d < 0 and not allow_negative:
        raise HoldingsError(f"{what} is negative ({value!r}); record borrowing as margin_loan_cad")
    out = float(d)
    if not math.isfinite(out) or abs(out) > MAX_MONEY:
        raise HoldingsError(f"{what}: out of range ({value!r})")
    return out


def _shares(value: Any, ticker: str) -> int:
    d = _number(value, f"shares of {ticker}")
    if d < 0:
        raise HoldingsError(f"negative shares for {ticker} ({value!r}); shorts are never allowed")
    if d != d.to_integral_value():
        raise HoldingsError(f"fractional shares for {ticker} ({value!r}); whole shares only")
    if d > MAX_SHARES:
        raise HoldingsError(f"shares of {ticker} out of range ({value!r})")
    return int(d)


def _build(fields: dict[str, Any], positions: dict[str, Any], digest: str) -> Holdings:
    missing = [f for f in REQUIRED if f not in fields]
    if missing:
        raise HoldingsError(f"missing required fields {missing}")
    unknown = sorted(t for t in positions if t not in UNIVERSE)
    if unknown:
        raise HoldingsError(f"unknown tickers {unknown} (universe: {sorted(UNIVERSE)})")
    try:
        as_of = parse_date(fields["as_of"], "as_of")
    except ValueError as exc:
        raise HoldingsError(str(exc)) from exc
    pos = {t: _shares(v, t) for t, v in sorted(positions.items())}
    return Holdings(
        as_of=as_of, positions=pos,
        cash_cad=_money(fields["cash_cad"], "cash_cad"),
        cash_usd=_money(fields["cash_usd"], "cash_usd"),
        margin_loan_cad=_money(fields.get("margin_loan_cad", 0), "margin_loan_cad"),
        margin_loan_given="margin_loan_cad" in fields,
        net_external_flow_cad=_money(fields["net_external_flow_cad"], "net_external_flow_cad",
                                     allow_negative=True),
        sha256=digest)


def _parse_json(text: str, digest: str) -> Holdings:
    try:
        raw = strict_json_loads(text)
    except ValueError as exc:  # JSONDecodeError is a ValueError; so are duplicate keys / NaN literals
        raise HoldingsError(f"holdings JSON unparsable: {exc}") from exc
    if not isinstance(raw, dict):
        raise HoldingsError("holdings JSON must be an object")
    unknown = sorted(set(raw) - set(FIELDS) - {"positions"})
    if unknown:
        raise HoldingsError(f"unknown holdings fields {unknown}")
    positions = raw.get("positions", {})
    if isinstance(positions, list):
        as_map: dict[str, Any] = {}
        for row in positions:
            if not isinstance(row, dict) or set(row) != {"ticker", "shares"} or not isinstance(row["ticker"], str):
                raise HoldingsError(f"position rows must be {{ticker, shares}}; got {row!r}")
            if row["ticker"] in as_map:
                raise HoldingsError(f"duplicate position {row['ticker']}")
            as_map[row["ticker"]] = row["shares"]
        positions = as_map
    if not isinstance(positions, dict):
        raise HoldingsError("positions must be an object or a list of {ticker, shares}")
    return _build({k: v for k, v in raw.items() if k != "positions"}, positions, digest)


def _parse_csv(text: str, digest: str) -> Holdings:
    rows = list(csv.reader(io.StringIO(text)))
    rows = [r for r in rows if r and any(c.strip() for c in r)]
    if not rows or [c.strip() for c in rows[0]] != ["record", "key", "value"]:
        raise HoldingsError("holdings CSV must start with header 'record,key,value'")
    fields: dict[str, str] = {}
    positions: dict[str, str] = {}
    for n, row in enumerate(rows[1:], start=2):
        if len(row) != 3:
            raise HoldingsError(f"line {n}: expected 3 columns, got {len(row)}")
        record, key, value = (c.strip() for c in row)
        if record == "field":
            if key not in FIELDS:
                raise HoldingsError(f"line {n}: unknown field {key!r}")
            if key in fields:
                raise HoldingsError(f"line {n}: duplicate field {key!r}")
            fields[key] = value
        elif record == "position":
            if key in positions:
                raise HoldingsError(f"line {n}: duplicate position {key!r}")
            positions[key] = value
        else:
            raise HoldingsError(f"line {n}: unknown record type {record!r}")
    return _build(fields, positions, digest)


def parse_holdings(data: bytes, *, fmt: str) -> Holdings:
    digest = hashlib.sha256(data).hexdigest()
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HoldingsError("holdings file is not UTF-8") from exc
    if fmt == "json":
        return _parse_json(text, digest)
    if fmt == "csv":
        return _parse_csv(text, digest)
    raise HoldingsError(f"unsupported holdings format {fmt!r} (use .csv or .json)")


def load_holdings(path: Path) -> tuple[Holdings | None, str | None, str | None]:
    """Return (holdings, error, sha256_of_bytes).  Never raises for content problems (they are refusals)."""
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError as exc:
        return None, f"holdings file unreadable: {exc.strerror or exc}", None
    digest = hashlib.sha256(data).hexdigest()
    try:
        return parse_holdings(data, fmt=path.suffix.lower().lstrip(".")), None, digest
    except HoldingsError as exc:
        return None, str(exc), digest
