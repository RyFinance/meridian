# Cycle-5 forward protocol: crypto_funding_xs — prepared, not registered

*Written by the cycle-5 C3 agent. Saved by the director session. Prepared, NOT registered.*

## What exists now (all new files; nothing frozen was edited)

- `research/crypto_funding_xs/{PLAN.md,core.py,evaluate.py}` — confirmed byte-identical to their committed state throughout (git diff empty; `targets.py` also hashes and reports them at every run).
- `research/forward/*` — confirmed unmodified; nothing here was imported except as read-only reference for design.
- `research/forward_crypto/collector.py` — keyless Binance snapshot collector.
- `research/forward_crypto/targets.py` — reproduces the frozen rule's target weights for one forward day, by importing and calling `core.weights()` unmodified.
- `research/forward_crypto/adapter_spec.json` — proposed registry spec (not consumed by any code; a proposal document).
- `tests/test_forward_crypto.py` — 12 tests, all passing, no network, no registry writes.
- `data/forward_crypto/raw/2026-09-25/` — a real, live-collected snapshot (see below), ~6 MB.
- `reports/forward/registry.jsonl` and `research/preregistrations.jsonl` — **untouched by this work** (both already existed/were modified before this session from unrelated prior work; verified via `git diff` / timestamps).

## Live test results

Two live keyless calls were made against `fapi.binance.com` from this environment, as instructed:

1. `collector.py --probe`: **HTTP 200**, not blocked. `exchangeInfo` returned 907 total futures symbols, 527 USDT-margined TRADING perpetuals.
2. `collector.py --collect --limit 150`: fetched exchangeInfo + fundingRate + klines + premiumIndex for 150 symbols, wrote 451 immutable JSON files, zero errors.

**Important caveat on geo-blocking**: this environment was **not** geo-blocked. That does *not* establish that the machine which will actually run daily collection (presumably the user's own, plausibly US-located) is unblocked — Binance is documented to 451 many endpoints for US IPs, and this sandbox's network egress location need not match the user's. `adapter_spec.json` records this explicitly and instructs the user to re-run `--probe` from wherever collection will really run before relying on it. No VPN or proxy was used anywhere. If a real 451 shows up on the user's machine, the fallback is `data.binance.vision`'s daily archive — but it is *lagged* (published only after the UTC day it covers), which means it **cannot support same-day 00:00 UTC execution**; it could only support a *slower*, next-day-open variant of the rule, which is a different spec (flagged, not proposed for registration in this batch).

One real operational bug found and fixed during the live test: Python's `urllib` intermittently truncated Binance's ~1.1 MB `exchangeInfo` response through this environment's proxy (`IncompleteRead`), even though `curl` and `requests` fetched it correctly every time. The collector was switched to `requests` with bounded retries; a 451 is still never retried.

## Correctness check: targets.py reproduces the frozen rule

Ran against the real snapshot for 2026-09-25 (a forward day, not touching 2023–2026): with 149 candidate symbols it correctly selected 20 long / 20 short (quintile of the eligible universe), each weighted ±0.025 (gross 1.0, net 0.0 — exactly `core.py`'s "+0.5 gross long and −0.5 gross short"). A dedicated pytest fixture with a synthetic 30-symbol universe and a monotone funding signal independently confirms the exact bottom/top-quintile selection, weight magnitude, and the exclusion of the still-forming "today" candle from the trailing-volume ranking.

## Power / years-needed (via `research/power`, reusing the c4a design's parameters — `research/power/examples/c4a_binance_funding_ls_daily.json`, `Autocorr`, skew −0.3, exkurt 10, D1≈1.105)

Single-test years to 80% power, daily (365/yr), across the plausible Sharpe range:

| True Sharpe | Years @ p<0.05 | Years @ p<0.01 |
|---|---|---|
| 0.50 | 27.4 | 44.5 |
| 0.70 | 14.0 | 22.7 |
| 1.00 | 6.9 | 11.2 |
| 1.30 | 4.1 | 6.6 |
| 1.65 | 2.6 | 4.1 |

Even at the *optimistic* end of the plausible range (1.65, already flagged INCAPABLE-adjacent territory for a moderate edge in the frozen PLAN), confirmation needs **2.5–4 years** of clean forward daily data; at a more realistic Sharpe (0.5–0.7) it needs **14–45 years**. This is consistent with the PLAN's own dev/val power verdict ("INCAPABLE for a moderate edge... registered because a LARGE effect is a priori plausible").

**Futility/kill boundary** (one-sided 90% test against the *optimistic* S=1.65 scenario — if the running forward Sharpe falls below this, even the best-case a priori scenario is already rejected):
- after 1 year: kill if running Sharpe < **+0.27**
- after 2 years: kill if running Sharpe < **+0.68**
- after 3 years: kill if running Sharpe < **+0.86**

i.e. the strategy can be killed for futility well before the multi-year confirmation horizon if it isn't even tracking the top of its own plausible range.

## Tamper-evidence design (proposed, in `adapter_spec.json`)

- Reuse `research/forward/registry.py`'s hash chain verbatim in a **separate** chain (`reports/forward_crypto/registry.jsonl`), not mixed into the existing NYSE-strategy chain — different calendar, different data source, different failure modes (geo-blocking has no NYSE analogue).
- One `decision` record per UTC day; `intended_execution_utc` = that day's 00:00:00Z; payload = `targets.decision_weights()`'s full output (weights, snapshot file hashes, frozen-file provenance hashes).
- Weekly anchoring of `registry.head_line()`'s seq+sha256 to an out-of-band channel the user controls (no commits are made — that's excluded by this task's constraints).
- **No backfill, ever**: a UTC day with no live-collected snapshot simply cannot produce a decision record (there is no code path for it); a missing day is reported as a gap, exactly like the existing evaluator's `missed_scheduled_decisions`, and breaks the counted series into separate contiguous runs rather than being papered over.
- Delisting is handled prospectively only (a symbol vanishing from `exchangeInfo` on a later day), with the eventual Binance settlement price recorded once known and dated the day it becomes known — never backfilled, never assumed.

## What is genuinely new work not covered by existing infra

The existing `research/forward/adapters.py` "generic" targets type assumes a **fixed** instrument list registered once. This strategy's universe changes daily (delistings, new listings, volume-rank churn). Registering it for real needs a small new adapter (`dynamic_targets` kind + a UTC-day calendar twin of `nyse.py`) that does not exist yet and was **not** built here — only specified, in `adapter_spec.json`.

## The one action needed to actually register anything

Nothing here writes to `reports/forward/registry.jsonl` or `research/preregistrations.jsonl`. To move from "prepared" to "registered," the single approval action is:

```
PYTHONPATH=. .venv/bin/python -m research.forward.record --strategy crypto_funding_xs_binance_um_v1 \
  --register-spec research/forward_crypto/adapter_spec.json --registry reports/forward_crypto/registry.jsonl
```

— run only after (a) the user has confirmed the collection machine is not geo-blocked, and (b) the small `dynamic_targets` adapter extension described above exists, since `register_generic`'s current schema cannot yet accept a dynamic instrument universe as-is.