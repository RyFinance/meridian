"""Command line for the rebalancing autopilot (research only).

    python -m research.autopilot.cli --config CONFIG.json --holdings HOLDINGS.(json|csv) \\
        --price-store STORE --price-version VERSION --report-date YYYY-MM-DD --out OUT_DIR \\
        [--log reports/autopilot/paper_log.jsonl] [--price-key KEY ...] [--replay] \\
        [--expect-manifest-sha256 SHA]

Writes ``OUT_DIR/report_<date>_<config>.md`` and ``OUT_DIR/summary_<date>_<config>.json`` and appends one
hash-chained line to the paper log (never the forward research registry).

Exit codes: 0 = accepted (with or without proposed trades); 1 = refused (report, JSON and log line are still
written; no trades are proposed); 2 = fatal (bad arguments, unreadable config, invalid paper-log chain, forbidden
output path, conflicting existing output, or any unexpected error) -- nothing is written (a run that fails after
it started writing removes what it wrote before exiting).

No network, no broker, no scheduler: this runs once, when the owner runs it.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from research.autopilot.config import ConfigError, load_config
from research.autopilot.engine import EngineInputs, evaluate
from research.autopilot.holdings import load_holdings, parse_date
from research.autopilot.paperlog import DEFAULT_LOG_PATH, PaperLogError, append, guard_path, read_chain, sha256_hex
from research.autopilot.prices import load_prices
from research.autopilot.report import render_markdown, summary_json_bytes

EXIT_ACCEPTED, EXIT_REFUSED, EXIT_FATAL = 0, 1, 2


class FatalError(RuntimeError):
    """Nothing can be reported or logged (see module docstring)."""


@dataclass(frozen=True)
class RunResult:
    status: str
    report_path: Path
    summary_path: Path
    log_path: Path
    summary: dict[str, Any]
    report_bytes: bytes
    summary_bytes: bytes
    entry: dict[str, Any]

    @property
    def exit_code(self) -> int:
        return EXIT_ACCEPTED if self.status == "accepted" else EXIT_REFUSED


def _safe_stem(text: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9@._-]", "_", text)[:64].strip(".")
    return stem or "config"


def _stage(path: Path, data: bytes) -> Path:
    """Write ``data`` to a fsynced temporary file next to ``path``; the caller renames it into place."""
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        os.fchmod(fd, 0o644)             # mkstemp creates 0600; reports are ordinary readable files
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        os.unlink(tmp)
        raise
    return Path(tmp)


def _missing_dirs(directory: Path) -> list[Path]:
    """``directory`` and its ancestors that do not exist yet (deepest first), so they can be removed on failure."""
    out = []
    for d in (directory, *directory.parents):
        if d.exists():
            break
        out.append(d)
    return out


def _cleanup(paths: list[Path], dirs: list[Path]) -> None:
    for path in paths:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    for d in dirs:                       # deepest first; only directories this run created, and only if empty
        try:
            d.rmdir()
        except OSError:
            break


MANIFEST_SHA_RE = re.compile(r"[0-9a-f]{64}")


def run(*, config: Path, holdings: Path, price_store: Path, price_version: str, report_date: date | str,
        out: Path, log: Path = DEFAULT_LOG_PATH, price_keys: list[str] | None = None,
        replay: bool = False, expect_manifest_sha256: str | None = None) -> RunResult:
    """Load inputs, run the engine, write the report + JSON summary, append the paper-log line.

    All-or-nothing: the report and summary are staged as temporary files, renamed into place, and then the log line
    is appended; if anything fails before the append completes, every file and directory this run created is
    removed again, so a failed run leaves no report, summary or log line behind."""
    if isinstance(report_date, str):
        try:
            report_date = parse_date(report_date, "--report-date")
        except ValueError as exc:
            raise FatalError(str(exc)) from exc
    if expect_manifest_sha256 is not None and not MANIFEST_SHA_RE.fullmatch(expect_manifest_sha256):
        raise FatalError("--expect-manifest-sha256 must be 64 lowercase hex characters")
    try:
        log_target = guard_path(Path(log))
    except PaperLogError as exc:
        raise FatalError(str(exc)) from exc
    try:
        cfg, cfg_bytes = load_config(Path(config))
    except ConfigError as exc:
        raise FatalError(str(exc)) from exc
    h, h_err, h_sha = load_holdings(Path(holdings))
    prices, p_err = load_prices(Path(price_store), price_version, keys=price_keys, replay=replay)
    try:
        chain = read_chain(log_target)
    except PaperLogError as exc:
        raise FatalError(f"paper log {log_target.name} failed validation: {exc}") from exc

    inputs = EngineInputs(config=cfg, config_file=Path(config).name, config_sha256=sha256_hex(cfg_bytes),
                          holdings=h, holdings_error=h_err, holdings_file=Path(holdings).name, holdings_sha256=h_sha,
                          prices=prices, price_error=p_err, price_version=price_version, report_date=report_date,
                          expected_manifest_sha256=expect_manifest_sha256)
    summary = evaluate(inputs, chain)
    report_bytes = render_markdown(summary).encode("utf-8")
    stem = f"{report_date.isoformat()}_{_safe_stem(cfg.config_id)}"
    report_name, summary_name = f"report_{stem}.md", f"summary_{stem}.json"
    doc = {**summary, "report_file": report_name, "report_sha256": sha256_hex(report_bytes)}
    summary_bytes = summary_json_bytes(doc)

    try:
        report_path = guard_path(Path(out) / report_name)
        summary_path = guard_path(Path(out) / summary_name)
    except PaperLogError as exc:
        raise FatalError(str(exc)) from exc
    if log_target in (report_path, summary_path):
        raise FatalError("the paper log path may not be one of the report outputs")
    for path, data in ((report_path, report_bytes), (summary_path, summary_bytes)):
        if path.exists() and path.read_bytes() != data:
            raise FatalError(f"{path.name} already exists in --out with different content; move it or choose "
                             "another --out")

    new_dirs = _missing_dirs(report_path.parent)
    staged: list[Path] = []
    created: list[Path] = []
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        todo = [(path, data) for path, data in ((report_path, report_bytes), (summary_path, summary_bytes))
                if not path.exists()]
        for path, data in todo:
            staged.append(_stage(path, data))
        for (path, _data), tmp in zip(todo, staged):
            os.replace(tmp, path)
            created.append(path)
        staged = []
        entry = append(log_target, doc, expected_chain=chain)
    except BaseException as exc:
        _cleanup(staged + created, new_dirs)
        if isinstance(exc, PaperLogError):
            raise FatalError(f"paper log append refused: {exc}") from exc
        raise
    if entry["seq"] != summary["paper_log"]["seq"] or entry["prev_hash"] != summary["paper_log"]["prev_entry_hash"]:
        raise FatalError("internal error: the appended paper-log entry does not sit where the summary says")
    return RunResult(status=summary["status"], report_path=report_path, summary_path=summary_path,
                     log_path=log_target, summary=summary, report_bytes=report_bytes, summary_bytes=summary_bytes,
                     entry=entry)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m research.autopilot.cli",
                                 description="Offline rebalancing report for a menu portfolio (research only; "
                                             "not a recommendation to trade).")
    ap.add_argument("--config", required=True, type=Path, help="config JSON (config_id, account_type, ...)")
    ap.add_argument("--holdings", required=True, type=Path, help="owner-edited holdings file (.json or .csv)")
    ap.add_argument("--price-store", required=True, type=Path, help="research.data_snapshot store directory")
    ap.add_argument("--price-version", required=True, help="dataset version inside the store")
    ap.add_argument("--price-key", action="append", default=None,
                    help="snapshot record key(s) of the price CSV(s); default: every CSV with the price columns")
    ap.add_argument("--replay", action="store_true",
                    help="verify frozen objects only (not the live source scope); labelled REPLAY in the report")
    ap.add_argument("--report-date", required=True, help="report date YYYY-MM-DD (an input; no wall clock)")
    ap.add_argument("--out", required=True, type=Path, help="directory for the report and JSON summary")
    ap.add_argument("--log", type=Path, default=DEFAULT_LOG_PATH, help="paper log (default: %(default)s)")
    ap.add_argument("--expect-manifest-sha256", default=None,
                    help="refuse unless the verified price snapshot has exactly this manifest SHA-256")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run(config=args.config, holdings=args.holdings, price_store=args.price_store,
                     price_version=args.price_version, report_date=args.report_date, out=args.out, log=args.log,
                     price_keys=args.price_key, replay=args.replay,
                     expect_manifest_sha256=args.expect_manifest_sha256)
    except FatalError as exc:
        print(f"autopilot: FATAL (nothing written): {exc}", file=sys.stderr)
        return EXIT_FATAL
    except Exception as exc:  # any unexpected error is fatal (exit 2), never "refused" (exit 1)
        print(f"autopilot: FATAL (unexpected error; nothing written): {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_FATAL
    s = result.summary
    if result.status == "accepted":
        print(f"autopilot: ACCEPTED, {len(s['trades'])} proposed trade(s); report {result.report_path}; "
              f"paper log seq {result.entry['seq']}")
    else:
        print(f"autopilot: REFUSED, no trades ({len(s['refusal_reasons'])} reason(s)); report {result.report_path}; "
              f"paper log seq {result.entry['seq']}")
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
