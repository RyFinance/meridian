# Forward-prediction registry: what was built, how to use it, how to anchor it

2026-09-23. Code is in `research/forward/`, tests in `tests/test_forward.py` (20 tests, passing), and outputs here. No trade was placed and no scheduler was created. `bot/` and `bot/state/` were only read. See `PEAD_FORWARD_DIAGNOSIS.md` for the paper-bot findings and `proposed_fix.diff` for the unapplied patch.

*Written by the forward-integrity agent. Saved to disk by the main (director) session because the harness blocks subagents from writing report files.*

## 1. State of the real registry

`reports/forward/registry.jsonl` holds two records and **no forward decision**:

| seq | kind | strategy | spec_hash | record hash |
|---|---|---|---|---|
| 0 | genesis | — | — | `2d11892c…` |
| 1 | spec_registration | momentum_gold_v1 | `2bd36904…fd933f0` | `4e50ac9486652a2e643de5ae1e2b61fbd0a304f3ea9d39cd5f0238bdb96da67b` |

**Head to anchor now:** `quant_v7 forward registry head seq=1 sha256=4e50ac9486652a2e643de5ae1e2b61fbd0a304f3ea9d39cd5f0238bdb96da67b`

The momentum_gold_v1 registration stores:
- the frozen rules;
- the evaluator parameters derived from them;
- provenance checks.

Provenance findings:
- The spec file on disk has changed since registration (hash `459daa7a…`). An `audit_2026_09_21` annotation was appended to it.
- Dropping that annotation reproduces the registered `56ee118c…` hash byte for byte, so **the rules are unchanged**.
- The strategy code still hashes to the spec's `code_sha256`.
- `reports/momentum_gold_20260919/` is untracked in git, so nothing external anchored that spec until now.

## 2. What the registry guarantees, and what it doesn't

Each line is canonical JSON with these fields:
- `seq`, `kind`;
- `recorded_at_utc` (the writer's wall clock);
- `strategy_id`, `spec_hash`;
- `market_asof`, `intended_execution_utc`, `decision_key`;
- `payload`: targets or decision, inputs, price sources, flags;
- `writer`: git HEAD and Python version;
- `prev_hash`, and `hash` (SHA-256 over everything except `hash`).

Appends:
- run under an exclusive file lock;
- re-verify the entire chain first and refuse to extend a broken one;
- refuse a decision under an unregistered spec, a duplicate decision key, or a clock earlier than the last record.

Mistakes are retracted with a `void` record, never edited.

**Guaranteed (detected by `verify` alone):**
- any edit;
- any reorder;
- any insertion or deletion before the head;
- a partial last line;
- time going backwards;
- decisions under unregistered specs;
- duplicate live decisions.

The tests cover each case.

**Not guaranteed without an external anchor:**
- truncation of the tail;
- a complete rewrite with recomputed hashes;
- a writer who sets the clock wrong at write time.

The chain proves **order**. It proves **time** only up to the next anchor that includes the record.

**The evaluator counts a decision only if:**
- the chain verifies;
- the decision was recorded before its intended execution, and therefore before any outcome;
- the source's own decision time, when present, is before execution and not after the record time;
- its `market_asof` close was final when it was recorded;
- it is not voided and carries no excluding flag (backfill, decided after execution, earlier code, …).

For momentum_gold it also lists any scheduled month with no record. Skipping a month is selection, so gaps are reported and never filled in.

## 3. Prices: LSE caveat and what is used

LSE `1d` bars for US listings are UTC-day bars that include pre- and post-market trades. They are not session prices. `research.forward.prices` rebuilds sessions from LSE **30-minute** bars filtered to 09:30–16:00 ET: the open is the first bar's open and the close is the last bar's close. yfinance official prices serve as the cross-check and as the fallback. Every price records its source.

The check is in `lse_reconstruction_check.json`: GLD, SPY and AZO on 2026-09-17/18/21/22, against yfinance official prices.

| Comparison | Mean abs | Max abs |
|---|---:|---:|
| LSE 30m reconstructed open vs official | 4.7 bps | 32 bps (AZO) |
| LSE 30m reconstructed close vs official | 2.4 bps | 15 bps (AZO) |
| **LSE `1d` open vs official** | **66 bps** | **253 bps** (AZO earnings day) |
| **LSE `1d` close vs official** | **18 bps** | **50 bps** |

- **ETFs** (GLD, SPY) reconstruct within 3 bps. That is fine for momentum_gold.
- **Single stocks** differ by up to 32 bps, because the official open and close are **auction** prints: LSE stamps the closing auction in the first after-hours bar.
- So `evaluate --price-source auto`, the default, uses the LSE reconstruction for ETF targets and yfinance official prices for PEAD trades, each falling back to the other.
- SPMO is not carried by LSE and always comes from yfinance.
- On 2026-09-23, yfinance returned NaN for every 2026-09-22 close. The LSE reconstruction covers that gap.
- The PEAD bot itself uses only yfinance regular-session prices, never LSE daily bars.

## 4. Commands

These are manual commands. **Nothing is scheduled.** All take `--registry PATH` and `--dry-run`.

| When | Command | Note |
|---|---|---|
| Now | `PYTHONPATH=. .venv/bin/python -m research.forward.verify` | Then anchor the printed head (§5). |
| **2026-10-01, between 13:15 PT (16:15 ET) and 06:30 PT on 10-02 (09:30 ET)** | `PYTHONPATH=. .venv/bin/python -m research.forward.record --strategy momentum_gold_v1 --date 2026-10-01` | Refused before the close and after the next open. Then run `verify`, then **anchor before 06:30 PT 10-02**. |
| First NYSE session of each later month, same window | the same command with that date (2026-11-02, 2026-12-01, 2027-01-04, …) | A missed month shows up in `evaluate`. `--allow-late` records it flagged and excluded. |
| After the bot's evening cycle finishes (after about 16:45 PT) | `PYTHONPATH=. .venv/bin/python -m research.forward.record --strategy pead_bot_v1 --ingest` | Reads bot/state read-only. Registers the running code hash on first use and after any code change. Under today's convention every PEAD decision is flagged late and excluded; they appear only in the "late-repriced" section. `pead_ingest_dryrun.json` shows what would be ingested today (LEN, AZO). |
| Any time | `PYTHONPATH=. .venv/bin/python -m research.forward.evaluate --out reports/forward/evaluation_YYYYMMDD.json` | Needs the LSE Terminal running for LSE prices; falls back to yfinance. |
| A new research candidate | `... record --strategy X_v1 --register-spec spec.json`, then `... record --strategy X_v1 --date D --targets '{"SPY":1.0}'` | The spec needs an `evaluation` block (see `adapters.register_generic`). |
| Retract a mistaken record | `... record --void SEQ --reason "..."` | The original stays; the evaluator excludes it. |

## 5. Anchoring the chain head externally (you do this; nothing here does it for you)

An anchor is the line printed by `verify`, `head seq=N sha256=H`, stored somewhere you cannot silently rewrite, **before the execution time of the decisions it covers**. Use at least one channel:

1. **Git push.**
   - Commit `reports/forward/registry.jsonl` and push to `origin`.
   - GitHub's push log is server-timestamped; commit dates are self-reported and prove nothing.
   - Putting the head line in the commit message makes it searchable.
2. **Email.**
   - Send the head line to yourself, and ideally to one other person.
   - The receiving server's `Received:` headers timestamp it.
   - This is the easiest channel for the 10-01 evening deadline.
3. **A trusted timestamp.**
   - Either `ots stamp reports/forward/registry.jsonl` (OpenTimestamps, anchored in Bitcoin), or
   - an RFC 3161 timestamp authority: `openssl ts -query -data registry.jsonl -sha256 -cert` sent to a public TSA.
   - Keep the proof file.

Record every anchor in `reports/forward/anchors.jsonl`, one line each:

```json
{"seq": 1, "hash": "4e50ac94…", "anchored_at_utc": "…", "channel": "email to …", "proof": "message-id / commit / .ots path"}
```

Then `verify --anchors reports/forward/anchors.jsonl` also detects truncation and full rewrites.

**Cadence:** after every write that records a decision, before that decision's execution. Also weekly, even when nothing was written.

## 6. Minimal operational changes so that every forward observation from now on is clean

1. **momentum_gold_v1: no change is needed.** Run the one command in the 10-01 window, anchor it, and repeat monthly. This is the only strategy able to produce clean observations immediately.
2. **Change PEAD's entry convention.** This is required: without it, no PEAD observation can be clean. Today every entry is decided about 3 hours after the close it fills at. Choose one:
   - **(a) Decide before the close.**
     - Run at about 12:30 PT (15:30 ET), with candidates taken from the schedule log so the fetch takes minutes.
     - Fill at the price available at decision time.
     - Keep the post-close run for exits and marks.
   - **(b) Fill at the next official open** after a post-close decision.
   - Either is a code change and a **new spec version** (`pead_bot_v2`), registered before its first decision. (a) keeps the validated close-entry convention. (b) gives up the overnight drift and should be replay-checked first on already-spent data, as a robustness check only.
3. **Separate the forward book from the backfill.**
   - Today 11 of 12 open positions are backfilled. Their simulated P&L sets live sizing and uses the exposure cap.
   - Start the forward PEAD book from a fixed NAV with no inherited positions, or accept that its sizing is contaminated.
   - The evaluator already prices each trade independently of the paper account.
   - Never write replays into the live ledger again.
4. **Freeze the bot code.** Any change produces a new fingerprint, which the ingest registers as a new spec automatically. Decisions under older code are flagged and excluded.
5. **Apply `proposed_fix.diff`, or its equivalent.** It:
   - logs decision inputs and `decided_at`;
   - separates provenance;
   - stops outages from being written as normal records;
   - stops writing a partial mark as a NAV.
6. **Ingest, verify and anchor every night after the bot's cycle.** For PEAD under convention (b), and for momentum_gold, this is what makes the registry time precede execution.
7. **Avoid extra runs.** Avoid `RunAtLoad` and manual runs on trading days. Events are de-duplicated, but the cycle records and marks multiply.

## 7. What forward evidence can and cannot do here

- **Detection takes years.** At the pre-2024 backtest Sharpe of 0.8, a 2-standard-error detection needs about **1,575 sessions (about 6.2 years)** of clean marks.
- **SPMO/GLD against its SPY/GLD control needs far longer.** The backtest's active return was +3.1%/yr with a HAC t of 1.58.
- **PEAD needs volume.** A usable per-trade interval needs roughly 30 or more clean trades, which is about one earnings season once the entry convention is fixed.
- **What the registry buys is integrity.** It does not buy speed: the evidence it accumulates will hold up to a skeptical reviewer.

## Files

- `research/forward/`:
  - `registry.py`: chain, append, verify;
  - `nyse.py`: session calendar;
  - `prices.py`: LSE 30m reconstruction and yfinance;
  - `adapters.py`: PEAD, momentum_gold and generic adapters;
  - `record.py`: CLI;
  - `verify.py`: CLI;
  - `evaluate.py`: evaluator;
  - `lse_check.py`: the LSE reconstruction check.
- `tests/test_forward.py`: 20 offline tests on temporary registries. One reads `bot/state` and asserts that its bytes and mtimes are unchanged.
- `reports/forward/`:
  - `registry.jsonl`;
  - `REPORT.md` (this file);
  - `PEAD_FORWARD_DIAGNOSIS.md`;
  - `proposed_fix.diff`;
  - `lse_reconstruction_check.json`;
  - `pead_ingest_dryrun.json`;
  - `evaluation_20260923.json`: no decisions yet.
