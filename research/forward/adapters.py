"""Adapters that turn strategy state into registry records.

pead_bot_v1       READ-ONLY ingest of bot/state/cycle_log.jsonl + paper_ledger.jsonl.
                  Only live (non-backfill) decisions, with the bot's own timestamps
                  kept as `source_decided_at_utc`; nothing in bot/ is imported or written.
momentum_gold_v1  Emits the frozen 50/50 SPMO/GLD targets on the first NYSE session of
                  a month, recorded between that close and the next open.
generic           Any fixed-targets candidate: register a spec file, then record
                  target weights per decision date.

Timing is always checked against the NYSE calendar: a record written after its
intended execution time is refused (or, with allow_late, written with the flag
"recorded_after_execution", which the evaluator excludes).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

from research.forward import nyse, registry
from research.forward.prices import PriceBook

ROOT = registry.ROOT
SETTLE = dt.timedelta(minutes=15)  # official closes are final a few minutes after the bell


class AdapterError(RuntimeError):
    pass


def _utc_from_epoch(ts: float) -> dt.datetime:
    return dt.datetime.fromtimestamp(float(ts), tz=dt.timezone.utc)


def _latest_spec(records: list[dict], strategy_id: str) -> dict | None:
    regs = registry.registered_specs(records).get(strategy_id, [])
    return regs[-1] if regs else None


def _asof_snapshot(pricebook: PriceBook | None, symbols: list[str], day: dt.date) -> tuple[dict, list[str]]:
    """Official closes on `day` per symbol with their source; flags if missing."""
    if pricebook is None:
        return {}, ["asof_prices_not_fetched"]
    snap, flags = {}, []
    for sym in symbols:
        df = pricebook.get(sym, day - dt.timedelta(days=10), day)
        if day in df.index and df.loc[day, "close"] is not None:
            row = df.loc[day]
            snap[sym] = {"close": row["close"], "source": row["close_source"], "lse_close": row["lse_close"],
                         "yf_close": row["yf_close"], "close_diff_bps": row["close_diff_bps"]}
        else:
            snap[sym] = None
            flags.append(f"no_official_close_{sym}")
    return _json_clean(snap), flags


def _json_clean(obj):
    """Floats that are NaN become None (the registry forbids NaN)."""
    if isinstance(obj, float):
        return obj if obj == obj and obj not in (float("inf"), float("-inf")) else None
    if isinstance(obj, dict):
        return {k: _json_clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_clean(v) for v in obj]
    if hasattr(obj, "item"):  # numpy scalar
        return _json_clean(obj.item())
    return obj


def _timing(now: dt.datetime, earliest: dt.datetime | None, execution: dt.datetime, allow_late: bool) -> list[str]:
    if earliest is not None and now < earliest:
        raise AdapterError(f"too early: this decision uses data final at {registry.iso_utc(earliest)}; now {registry.iso_utc(now)}")
    if now >= execution:
        if not allow_late:
            raise AdapterError(f"too late: intended execution was {registry.iso_utc(execution)}; now {registry.iso_utc(now)}. "
                               "A decision recorded after its execution is not forward evidence "
                               "(pass --allow-late to record it flagged; the evaluator excludes it).")
        return ["recorded_after_execution"]
    return []


# == targets strategies (momentum_gold_v1, generic) ===============================

def _validate_targets(targets: dict, instruments: list[str]) -> dict:
    out = {}
    for sym, w in targets.items():
        if sym not in instruments:
            raise AdapterError(f"{sym} is not an instrument of this spec ({instruments})")
        w = float(w)
        if not (w >= 0):
            raise AdapterError("targets must be non-negative (long-only fixed-targets evaluator)")
        out[sym] = w
    if sum(out.values()) > 1 + 1e-9:
        raise AdapterError("targets sum above 1 (no leverage)")
    return out


def record_targets_decision(path: Path, strategy_id: str, day: dt.date, targets: dict | None = None,
                            now: dt.datetime | None = None, pricebook: PriceBook | None = None,
                            allow_late: bool = False, dry_run: bool = False, extra: dict | None = None) -> dict:
    records = registry.load_records(path)
    reg = _latest_spec(records, strategy_id)
    if reg is None:
        raise AdapterError(f"{strategy_id} has no spec_registration in {path}")
    ev = reg["payload"]["evaluation"]
    if not nyse.is_session(day):
        raise AdapterError(f"{day} is not an NYSE session")
    rule = ev.get("decision_rule", "any_session")
    if rule == "first_session_of_month" and day != nyse.first_session_of_month(day.year, day.month):
        nxt = nyse.first_session_of_month(day.year + (day.month == 12), day.month % 12 + 1)
        this = nyse.first_session_of_month(day.year, day.month)
        upcoming = this if this > day else nxt
        raise AdapterError(f"{strategy_id} decides only on the first NYSE session of a month; "
                           f"{day} is not one (next: {upcoming})")
    targets = _validate_targets(targets if targets is not None else ev["fixed_targets"], ev["instruments"])
    if ev["execution"] == "next_open":
        exec_day = nyse.next_session(day)
        execution = nyse.open_utc(exec_day)
        earliest = nyse.close_utc(day) + SETTLE
        asof = day
    elif ev["execution"] == "close":
        exec_day = day
        execution = nyse.close_utc(day)
        earliest = None
        asof = nyse.previous_session(day)
    else:
        raise AdapterError(f"unknown execution convention {ev['execution']!r}")
    now = now or registry.utc_now()
    flags = _timing(now, earliest, execution, allow_late)
    symbols = sorted(set(ev["instruments"]) | set(ev.get("benchmark_targets") or {}))
    snapshot, data_flags = _asof_snapshot(pricebook, symbols, asof)
    payload = {
        "decision": "set portfolio to target weights of NAV",
        "targets": targets,
        "benchmark_targets": ev.get("benchmark_targets"),
        "decision_date": day.isoformat(),
        "execution": ev["execution"],
        "execution_date": exec_day.isoformat(),
        "asof_closes": snapshot,
        "data_sources": pricebook.sources_used() if pricebook else {},
        "data_errors": pricebook.errors() if pricebook else {},
        "flags": flags + data_flags,
        **(extra or {}),
    }
    kwargs = dict(strategy_id=strategy_id, spec_hash=reg["spec_hash"], market_asof=asof.isoformat(),
                  intended_execution_utc=registry.iso_utc(execution), decision_key=day.isoformat(),
                  payload=_json_clean(payload))
    if dry_run:
        return {"dry_run": True, "kind": "decision", **kwargs}
    return registry.append(path, "decision", now=now, **kwargs)


# -- momentum_gold_v1 --------------------------------------------------------------

MG_ID = "momentum_gold_v1"
MG_DIR = ROOT / "reports" / "momentum_gold_20260919"
MG_SPEC_PATH = MG_DIR / "forward_paper_spec.json"
MG_EVENTS_PATH = MG_DIR / "forward_paper_events.jsonl"
MG_CODE_PATH = ROOT / "research" / "momentum_verification" / "codex_momentum_gold.py"
MG_ANNOTATIONS = ("audit_2026_09_21",)  # appended 2026-09-21 without rule changes


def mg_frozen_spec(spec_path: Path = MG_SPEC_PATH, events_path: Path = MG_EVENTS_PATH,
                   code_path: Path = MG_CODE_PATH) -> tuple[dict, dict]:
    """The rule fields of the 2026-09-20 spec and a provenance check.

    The file on disk later gained an `audit_2026_09_21` annotation, so its hash
    no longer equals the one in forward_paper_events.jsonl. Dropping the
    annotation must reproduce that hash byte for byte, or the rules changed."""
    raw = json.loads(Path(spec_path).read_text())
    frozen = {k: v for k, v in raw.items() if k not in MG_ANNOTATIONS}
    events = [json.loads(line) for line in Path(events_path).read_text().splitlines() if line.strip()]
    registered = next((e["spec_sha256"] for e in events if e.get("event") == "strategy_registered"), None)
    rebuilt = hashlib.sha256(json.dumps(frozen, indent=2).encode()).hexdigest()
    code_now = registry.sha256_file(code_path) if Path(code_path).exists() else None
    provenance = {
        "spec_path": str(Path(spec_path).relative_to(ROOT)),
        "spec_file_sha256_now": registry.sha256_file(spec_path),
        "spec_sha256_in_registration_event": registered,
        "rules_rebuilt_sha256": rebuilt,
        "rules_match_registration_event": rebuilt == registered,
        "annotations_excluded": [k for k in MG_ANNOTATIONS if k in raw],
        "code_sha256_in_spec": frozen.get("code_sha256"),
        "code_sha256_now": code_now,
        "code_matches_spec": code_now == frozen.get("code_sha256"),
        "prior_events": events,
    }
    return frozen, provenance


def mg_evaluation(frozen: dict) -> dict:
    """Evaluator parameters, derived mechanically from the frozen rules."""
    assert frozen["decision"] == "first NYSE session close each month"
    assert frozen["fill"] == "following NYSE session open"
    return {
        "type": "targets",
        "instruments": sorted(frozen["weights"]),
        "fixed_targets": frozen["weights"],
        "decision_rule": "first_session_of_month",
        "execution": "next_open",
        "capital_usd": frozen["capital_usd"],
        "cost_per_side_bps": frozen["base_cost_per_side_bps"],
        "stress_cost_per_side_bps": frozen["stress_cost_per_side_bps"],
        "fee_per_order_usd": frozen["additional_order_fee_usd"],
        "benchmark_targets": frozen["benchmark"],
        "marks": "official session closes; dividends credited in cash on the ex-date",
    }


def register_momentum_gold(path: Path, now: dt.datetime | None = None, dry_run: bool = False) -> dict:
    frozen, provenance = mg_frozen_spec()
    if not provenance["rules_match_registration_event"]:
        raise AdapterError("momentum_gold_v1 rules no longer reproduce the registered hash; register a new version")
    payload = {"spec": frozen, "evaluation": mg_evaluation(frozen), "provenance": provenance,
               "note": "registered into the forward registry; zero decisions and zero fills at registration"}
    kwargs = dict(strategy_id=MG_ID, spec_hash=registry.spec_hash(frozen), payload=payload)
    if dry_run:
        return {"dry_run": True, "kind": "spec_registration", **kwargs}
    return registry.append(path, "spec_registration", now=now, **kwargs)


def record_momentum_gold(path: Path, day: dt.date, now: dt.datetime | None = None,
                         pricebook: PriceBook | None = None, allow_late: bool = False, dry_run: bool = False) -> dict:
    records = registry.load_records(path)
    reg = _latest_spec(records, MG_ID)
    if reg is None:
        raise AdapterError(f"{MG_ID} is not registered in {path}")
    frozen, provenance = mg_frozen_spec()
    if registry.spec_hash(frozen) != reg["spec_hash"]:
        raise AdapterError("the spec on disk no longer matches the registered momentum_gold_v1 spec; "
                           "a changed rule is a new strategy version")
    extra = {"spec_file_sha256_now": provenance["spec_file_sha256_now"],
             "code_matches_spec": provenance["code_matches_spec"],
             "targets_rule": "fixed weights from the frozen spec; no market data enters the targets"}
    return record_targets_decision(path, MG_ID, day, targets=None, now=now, pricebook=pricebook,
                                   allow_late=allow_late, dry_run=dry_run, extra=extra)


# -- generic ----------------------------------------------------------------------------

GENERIC_REQUIRED = ("instruments", "execution", "capital_usd", "cost_per_side_bps")


def register_generic(path: Path, strategy_id: str, spec_path: Path, now: dt.datetime | None = None,
                     dry_run: bool = False) -> dict:
    """spec JSON: any frozen rules plus an "evaluation" block:
        {"type": "targets", "instruments": [...], "execution": "next_open" | "close",
         "decision_rule": "any_session" | "first_session_of_month",
         "capital_usd": 100000, "cost_per_side_bps": 5, "stress_cost_per_side_bps": 15,
         "fee_per_order_usd": 0, "benchmark_targets": {...} (optional),
         "fixed_targets": {...} (optional)}"""
    spec = json.loads(Path(spec_path).read_text())
    ev = spec.get("evaluation")
    if not isinstance(ev, dict) or ev.get("type") != "targets" or any(k not in ev for k in GENERIC_REQUIRED):
        raise AdapterError(f"spec needs an evaluation block of type 'targets' with {GENERIC_REQUIRED}")
    if ev["execution"] not in {"next_open", "close"}:
        raise AdapterError("evaluation.execution must be 'next_open' or 'close'")
    ev = {"decision_rule": "any_session", "fee_per_order_usd": 0.0, "stress_cost_per_side_bps": None,
          "benchmark_targets": None, **ev}
    payload = {"spec": spec, "evaluation": ev,
               "provenance": {"spec_path": str(spec_path), "spec_file_sha256": registry.sha256_file(spec_path)}}
    kwargs = dict(strategy_id=strategy_id, spec_hash=registry.spec_hash(spec), payload=payload)
    if dry_run:
        return {"dry_run": True, "kind": "spec_registration", **kwargs}
    return registry.append(path, "spec_registration", now=now, **kwargs)


# == pead_bot_v1 (read-only) ==========================================================

PEAD_ID = "pead_bot_v1"
BOT_STATE = ROOT / "bot" / "state"
PEAD_CODE_FILES = (
    "bot/run_cycle.py", "bot/signal_pipeline.py", "bot/earnings_watcher.py", "bot/execution.py",
    "bot/position_manager.py", "bot/risk_gate.py", "bot/kill_switch.py",
    "earnings/ingestion.py", "earnings/sue.py", "earnings/features.py", "earnings/signal.py",
    "earnings/labeling.py", "data/ingestion.py", "risk/limits.py", "risk/kelly.py", "risk/transaction_costs.py",
)
PEAD_DATA_FILES = ("bot/state/model/pead_model_expanded.joblib", "data/expanded_universe_all_tickers.txt",
                   "reports/universe_ranking.csv")


def pead_spec(root: Path = ROOT) -> tuple[dict, dict]:
    """Spec = hashes of the code and fitted model the bot runs, plus the rules
    as coded. Returns (spec, provenance). Git HEAD is provenance, not spec."""
    files = {p: registry.sha256_file(root / p) for p in PEAD_CODE_FILES + PEAD_DATA_FILES if (root / p).exists()}
    mtimes = {p: (root / p).stat().st_mtime for p in PEAD_CODE_FILES if (root / p).exists()}
    spec = {
        "strategy_id": PEAD_ID,
        "rules_as_coded": {
            "entry": "close of the announcement's effective trading date (bot fills at the yfinance last price "
                     "fetched after the close)",
            "exit": "20 business days after entry, at the then-current price",
            "sizing": "fractional Kelly via risk gate; 5% per position, 100% gross cap",
            "round_trip_cost_bps": 10.0,
        },
        "file_sha256": files,
    }
    provenance = {"git_head": registry.writer_info()["git_head"],
                  "code_last_modified_utc": registry.iso_utc(_utc_from_epoch(max(mtimes.values()))) if mtimes else None}
    return spec, provenance


def pead_evaluation() -> dict:
    return {"type": "pead_events", "holding_business_days": 20, "round_trip_cost_bps": 10.0,
            "entry": "official close of as_of_date", "exit": "official close 20 business days later"}


def _read_jsonl_readonly(path: Path) -> list[tuple[int, str, dict]]:
    out = []
    if not Path(path).exists():
        return out
    with open(path, "r", encoding="utf-8") as f:  # read-only handle; bot/state is never written
        for n, line in enumerate(f, start=1):
            line = line.rstrip("\n")
            if not line.strip():
                continue
            try:
                out.append((n, line, json.loads(line)))
            except json.JSONDecodeError:
                continue
    return out


def _line_sha(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


def pead_candidates(state_dir: Path = BOT_STATE, code_frozen_since: dt.datetime | None = None) -> dict:
    """Every live entry decision in the cycle log, matched to its ledger fill.
    Pure read; returns decisions plus what was deliberately left out."""
    cycles = _read_jsonl_readonly(Path(state_dir) / "cycle_log.jsonl")
    ledger = _read_jsonl_readonly(Path(state_dir) / "paper_ledger.jsonl")
    opens = [(n, line, r) for n, line, r in ledger if r.get("event") == "open"]
    backfill_open_tickers = {}
    for n, line, r in opens:
        if r.get("backfill"):
            backfill_open_tickers.setdefault(r["ticker"], []).append(r.get("entry_date"))
    decisions, used_ledger_lines = [], set()
    skipped_backfill_cycles = 0
    for n, line, rec in cycles:
        if rec.get("backfill"):
            skipped_backfill_cycles += 1
            continue
        decided = _utc_from_epoch(rec["ts"])
        as_of = nyse.to_date(rec["as_of_date"])
        for entry in rec.get("entries") or []:
            flags = []
            execution = nyse.close_utc(as_of) if nyse.is_session(as_of) else None
            if execution is None:
                flags.append("as_of_not_a_session")
            elif decided > execution:
                flags.append("decided_after_execution")
            if code_frozen_since is not None and decided < code_frozen_since:
                flags.append("decided_under_earlier_code")
            fill = None
            if entry.get("allowed"):
                match = [(ln, l, r) for ln, l, r in opens if r["ticker"] == entry["ticker"]
                         and r.get("entry_date") == rec["as_of_date"] and ln not in used_ledger_lines]
                if match:
                    ln, l, r = match[0]
                    used_ledger_lines.add(ln)
                    fill = {"price": r["fill_price"], "notional": r["notional"], "size_fraction": r["size_fraction"],
                            "ts_utc": registry.iso_utc(_utc_from_epoch(r["ts"])),
                            "price_source": "bot PaperExecutionClient.get_current_price (yfinance fast_info "
                                            "lastPrice, fetched after the close)",
                            "ledger_line": ln, "ledger_line_sha256": _line_sha(l)}
                    if r.get("backfill"):
                        flags.append("ledger_fill_is_backfill")
                    if _utc_from_epoch(r["ts"]) > (execution or decided):
                        flags.append("filled_after_execution_time")
                else:
                    flags.append("allowed_but_no_ledger_fill")
            decisions.append({
                "decision_key": f"{entry['ticker']}|{str(entry.get('earnings_date', ''))[:10]}",
                "as_of_date": rec["as_of_date"],
                "intended_execution_utc": registry.iso_utc(execution) if execution else None,
                "payload": {
                    "ticker": entry["ticker"], "direction": entry.get("direction"), "allowed": entry.get("allowed"),
                    "reason": entry.get("reason"), "detail": entry.get("detail"), "sue": entry.get("sue"),
                    "calibrated_proba": entry.get("calibrated_proba"), "size_fraction": entry.get("size_fraction"),
                    "earnings_date": entry.get("earnings_date"), "as_of_date": rec["as_of_date"],
                    "execution": "close_of_as_of_date",
                    "source_decided_at_utc": registry.iso_utc(decided),
                    "source": {"file": "bot/state/cycle_log.jsonl", "line": n, "line_sha256": _line_sha(line)},
                    "fill": fill, "flags": flags,
                    "inputs_not_logged_by_bot": ["eps_estimate", "eps_actual", "surprise_pct", "trailing surprises",
                                                  "momentum features", "breaker inputs"],
                },
            })
    live_closes = [r for _, _, r in ledger if r.get("event") == "close" and not r.get("backfill")]
    orphan_opens = [r for ln, _, r in opens if not r.get("backfill") and ln not in used_ledger_lines]
    return {
        "decisions": decisions,
        "excluded": {
            "backfill_ledger_opens": sum(1 for _, _, r in opens if r.get("backfill")),
            "backfill_ledger_closes": sum(1 for _, _, r in ledger if r.get("event") == "close" and r.get("backfill")),
            "backfill_cycle_records_in_live_log": skipped_backfill_cycles,
            "live_exits_of_backfilled_positions": [
                {"ticker": r["ticker"], "exit_date": r.get("exit_date"), "realized_pnl": r.get("realized_pnl")}
                for r in live_closes if r["ticker"] in backfill_open_tickers],
            "live_ledger_opens_without_cycle_entry": [{"ticker": r["ticker"], "entry_date": r.get("entry_date")}
                                                       for r in orphan_opens],
        },
        "source_sha256": {name: registry.sha256_file(Path(state_dir) / name)
                          for name in ("cycle_log.jsonl", "paper_ledger.jsonl") if (Path(state_dir) / name).exists()},
    }


def ingest_pead(path: Path, state_dir: Path = BOT_STATE, now: dt.datetime | None = None,
                dry_run: bool = False, root: Path = ROOT) -> dict:
    """Register the running PEAD code (once per code version) and append every
    live decision not yet in the registry, in the bot's own time order."""
    records = registry.load_records(path)
    spec, provenance = pead_spec(root)
    s_hash = registry.spec_hash(spec)
    frozen_since = registry.parse_utc(provenance["code_last_modified_utc"]) if provenance["code_last_modified_utc"] else None
    found = pead_candidates(state_dir, code_frozen_since=frozen_since)
    existing = {r["decision_key"] for r in records if r["kind"] == "decision" and r["strategy_id"] == PEAD_ID}
    new = [d for d in found["decisions"] if d["decision_key"] not in existing]
    new.sort(key=lambda d: d["payload"]["source_decided_at_utc"])
    summary = {"strategy_id": PEAD_ID, "spec_hash": s_hash, "dry_run": dry_run,
               "n_live_decisions_in_bot_logs": len(found["decisions"]), "n_new": len(new),
               "n_already_in_registry": len(found["decisions"]) - len(new),
               "flag_counts": {}, "excluded": found["excluded"], "source_sha256": found["source_sha256"],
               "new_decisions": [{"key": d["decision_key"], "flags": d["payload"]["flags"],
                                  "decided": d["payload"]["source_decided_at_utc"],
                                  "execution": d["intended_execution_utc"]} for d in new]}
    for d in new:
        for flag in d["payload"]["flags"]:
            summary["flag_counts"][flag] = summary["flag_counts"].get(flag, 0) + 1
    if dry_run:
        return summary
    if not any(r["kind"] == "spec_registration" and r["strategy_id"] == PEAD_ID and r["spec_hash"] == s_hash
               for r in records):
        registry.append(path, "spec_registration", strategy_id=PEAD_ID, spec_hash=s_hash, now=now,
                        payload={"spec": spec, "evaluation": pead_evaluation(), "provenance": provenance})
    for d in new:
        if d["intended_execution_utc"] is None:
            continue
        registry.append(path, "decision", strategy_id=PEAD_ID, spec_hash=s_hash, market_asof=d["as_of_date"],
                        intended_execution_utc=d["intended_execution_utc"], decision_key=d["decision_key"],
                        payload=_json_clean(d["payload"]), now=now)
    return summary
