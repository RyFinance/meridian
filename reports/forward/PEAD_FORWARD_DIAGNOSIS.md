# PEAD paper bot: diagnosis of the forward evidence (2026-09-23)

Read-only review. Nothing under `bot/`, `bot/state/` or `~/Library/LaunchAgents` was changed. The bot
code was not run. Evidence came from:
- `bot/state/*.jsonl`;
- `~/Library/Logs/quant_v7/pead_bot.log`;
- git history;
- yfinance and LSE Terminal reads, both read-only.

## Verdict

The PEAD forward record is **not trustworthy as clean forward evidence today**. Four facts decide it:

- **Only one entry decision is genuinely forward.** That is AZO on 2026-09-22. The only other live
  decision is LEN on 2026-09-17, which was rejected. Of the "3 genuine forward events", two (DE,
  ROST) are scheduled exits of backfilled positions, not decisions.
- **Every live entry is decided after the price it fills at.** The bot runs at 15:42 PT (18:42 ET),
  and the AZO cycle ended 19:35 ET. The fill is the 16:00 ET close.
- **The live book depends on a simulated one.** 11 of the 12 open positions (89.7% of gross
  notional) are backfilled. Their simulated P&L sets NAV, and so the size of every live trade:
  AZO's $5,320.43 = 5% × $106,408.53. They also consume the gross-exposure cap.
- **The files cannot prove anything about time.** The ledger and cycle log are mutable,
  un-chained and un-anchored. Backfill timestamps are fabricated to look like live cycle times.

AZO itself is informationally clean: its inputs predate the close it fills at. But its record
cannot show that, and n = 1.

## 1. What the record contains

| Item | Count | Source |
|---|---:|---|
| Ledger events | 92 | `bot/state/paper_ledger.jsonl` |
| … flagged `backfill: true` | 89 (51 opens, 38 closes) | same |
| … live | 3: DE close 09-17, ROST close 09-18, AZO open 09-22 | same |
| Live entry decisions in the cycle log | 2: LEN 09-17 (rejected, `no_conviction`), AZO 09-22 (placed) | `bot/state/cycle_log.jsonl` lines 32, 38 |
| Live cycle records | 38; 30 of them before 09-17, all with 0 candidates (the bot was blind; see `earnings/ingestion.py:189-195`) | cycle log |
| Records with `marked_nav` | 4, all from 2026-09-21 onward | cycle log lines 35–38 |
| Open positions now | 12: 11 backfilled + AZO | ledger replay |

## 2. Why the 2026-09-21 alerts fired

**Root cause: this Mac had no working network during an extra, unscheduled run.** It was not a
stale file, not an API change, and not a failure of Yahoo's feed.

- There were three runs on 2026-09-21: 13:17 PT, 15:42 PT (scheduled) and 16:57 PT. The first
  and third were not at the scheduled time, consistent with `RunAtLoad` or a manual start.
- The 16:57 PT run logged **503 × "earnings fetch failed (DNSError … Could not resolve host)"**.
  It logged the same for 503 `earnings_history` fetches and 503 calendar fetches, plus "no data"
  for all 75 price refreshes. See `pead_bot.log` lines 1191–4709.
- The two earlier runs that day worked. Their marked NAV was 107,422.09 each time. The 09-22 run
  also worked.

How that outage became two misleading alerts:

1. **Errors look the same as empty answers.**
   - `fetch_ticker_earnings` catches the exception and returns an empty frame
     (`earnings/ingestion.py:47-53`).
   - `fetch_ticker_earnings_live` then sets `primary_ok = not historical.empty`
     (`ingestion.py:222-224`).
   - A DNS failure therefore counts as the dated endpoint answering with nothing.
   - `EarningsWatcher.dated_feed_down` (`bot/earnings_watcher.py:229-231, 258-261`) reports
     "announcement-date feed down: answered for 0/503". That is true, but it names the wrong cause.
2. **The staleness check reads the frozen training cache.**
   - On an outage, `ingestion.py:229-230` substitutes `load_cached_earnings`
     (`data/earnings_raw/*.parquet`, the training cache).
   - It tags those rows `date_source="announced"`, the same tag as live rows.
   - `earnings_watcher.py:236-241` counts every non-`quarter_end` row as trusted.
   - So `newest_report` became the cache's newest row: **2025-06-26 16:15**, verified across all
     493 cache files.
   - `feed_looks_stale` (`:263-269`) and `run_cycle.py:250-254` then reported "newest report in the
     universe is 2025-06-26 (> 100d)".
   - The research ledger's note "SUE feed stale (newest report 2025-06-26)" is this artifact. The
     live SUE feed answered normally on 09-22.
3. **A cycle with no data still looks like a successful cycle.**
   - `prepare_market_session` found a 09-21 bar in the cache, left there by the earlier run, so it
     declared the session open (`run_cycle.py:151-166`).
   - Marking failed for all 11 positions, which were carried at cost (`bot/execution.py:235-241`).
     The cycle wrote `marked_nav = 106,408.53`, the cash-basis NAV, which is a −1,013.56 artifact
     (`run_cycle.py:314-325`).
   - It then touched the heartbeat (`:330`), so the watchdog stayed quiet.

Secondary alert noise:
- The watchdog's 26-hour threshold fires on every weekend (`bot_alerts.jsonl` lines 422–430 and 617).
- Lines 1–421 of `bot_alerts.jsonl` are test-run alerts from 08-18 and 08-19. The test harness
  itself says it fixed this on 08-19 (`tests/test_bot_run_cycle.py:37-43`).

## 3. AZO: where the SUE and consensus came from, and whether they were knowable

- **Scoring path:**
  - `score_event` → `build_feature_row` (`bot/signal_pipeline.py:127-161`);
  - → `fetch_ticker_earnings_live("AZO")` (`ingestion.py:185-259`), whose primary source is
    yfinance `get_earnings_dates` with its announcement timestamps;
  - → `compute_sue` (`earnings/sue.py:46-62`): surprise ÷ standard deviation of the 8 prior
    winsorized surprises.
- **The data:** AZO reported **2026-09-22 06:00 ET**, before the open.
  - EPS estimate: 53.89. Actual: 56.05. Surprise: +4.01%.
  - Recomputed today from yfinance: SUE = **1.1837**, matching the logged 1.184.
  - Prior 8 surprises: 5.26, 1.24, −4.04, −3.88, −4.46, −2.35, −3.19, 1.89.
- **Was it knowable at the decision time?** Yes, everything except one input.
  - Consensus, actual and the trailing surprises were public by 06:00 ET.
  - The momentum features end at the 09-21 close: `_trailing_return` asks yfinance for data ending
    at the event date, and that end date is exclusive (`signal_pipeline.py:109-124`).
  - The model was fit on 2026-08-18 on data through 2025-06.
  - The universe file and dollar-volume ranking are static.
  - **The exception is the circuit-breaker tier.** It was computed from bars refreshed through the
    09-22 close (`run_cycle.py:216, 239`). It read `armed`, with the index move 0.21% against a 6%
    threshold, so this did not matter here. It is still a same-bar input by construction.
- **Not reproducible from the record.** The bot does not log the estimate, the actual, the surprise,
  the trailing surprises or the features (`EntryOutcome`, `run_cycle.py:108-118`). Yahoo's
  consensus values are not guaranteed point-in-time. The proposed fix logs them.

## 4. Are entries decided before outcomes?

| | AZO (live) | Backfilled opens (51) |
|---|---|---|
| Intended fill | 2026-09-22 close, 16:00 ET | close of each simulated day D |
| Cycle started | 18:45:31 ET (`pead_bot.log` line 4710) | — |
| Decision / ledger `ts` | **19:35:43 ET**, 3 h 36 m after the close | D at 18:42:00 ET exactly, **fabricated** by `SimulatedClock` (`live_backtest/backfill_missed_season.py:62-73, 87-89, 144-145, 173`) |
| Actually written | 2026-09-22 19:35 ET | 2026-09-17 ≈18:32 ET (see §5) |
| Fill price | 2894.73 | D's close from `yf.download` |
| Price source | `get_current_price` (`execution.py:46-62`): yfinance `fast_info.lastPrice`, i.e. the regular-session daily close or `regularMarketPrice` (yfinance `scrapers/quote.py:267-281`) | same function, patched to a pinned close (`backfill_missed_season.py:96-100, 131`) |

AZO's fill equals the closing-auction print: LSE shows 2894.74 in the first after-hours bar, the
last continuous trade was 2893.30, and the official open was 2894.25. The 50-minute run was caused
by 150-second yfinance timeouts (log lines 4720–4726).

Other timing weaknesses:
- **Same-day reruns write new records.** 09-21 ran 3 times.
- **Failed events can re-enter at a later close.** An event whose scoring raised or returned None
  is not marked as evaluated (`run_cycle.py:270-284`). It can be picked up again on any of the next
  3 days (`EARNINGS_LOOKBACK_DAYS`, `:81`).
- **Code changed during the "forward" period.** The line number of the `run_cycle` log call moved
  93 → 159 → 180 → 187 → 207 across 09-09 … 09-21. The code files were last modified 2026-09-18
  21:24 PT and committed in `30c27d1`. LEN (09-17) ran under earlier code; AZO ran under the
  current, committed code.

## 5. How backfill is distinguished, and whether that is permanent

- **Mechanism:** each ledger and alert line carries an in-band `"backfill": true`. The flag is added
  by monkey-patching `PaperExecutionClient._append_ledger` (`backfill_missed_season.py:123-132`).
  Cycles go to a separate `backfill_cycle_log.jsonl` (`:139`).
- **It is not permanent or robust:**
  - `--undo` rewrites the ledger and alert files in place (`backfill_missed_season.py:195-200`,
    `path.write_text`). The ledger is mutable by design.
  - Live records carry **no positive marker**. A backfill line that loses its flag becomes "live",
    and its fabricated `ts` looks like a real 18:42 ET cycle.
  - **The backfill was regenerated at least once.**
    - The live cycle at 09-17 16:40 ET logged `nav_before` 104,384.39.
    - The next live cycle, at 18:44 ET, logged 106,351.25, with no live trade in between.
    - `backfill_cycle_log.jsonl` has mtime 15:32 PT. Configuration sweeps in
      `live_backtest/state/sweep_*` are timestamped 15:19–15:27 PT.
    - The earlier version is not preserved.
  - The backfill used 09-17's view of earnings history and the current 503-name universe
    (`backfill_missed_season.py:18-19`). It is a replay, not a record.
  - The dashboard's Sharpe (`live_backtest/dashboard/backend.py:450-499`) and
    `bot/performance.daily_marked_nav` mix backfilled and live trades.
- **What still proves timing:** git.
  - Commit `ccc9932` (dated 2026-09-16 14:48 PT) has an **empty** ledger.
  - `30c27d1` (2026-09-19 23:47 PT, pushed to origin) has the 91 lines.
  - In `bot_alerts.jsonl`, the backfill block (lines 431–614) sits after a 09-14 watchdog alert.
  - So records stamped July 1 – September 16 were written between 09-16 and 09-19.

## 6. Are the marks stale? Which price data do they use?

- **The bot never uses LSE data.** `grep lse bot/` finds nothing. Fills and marks are yfinance
  regular-session prices. They are **not** LSE `1d` bars, which are UTC-day bars including pre- and
  post-market trades.
  - LSE `1d` bars are off by up to 253 bps; AZO's 09-22 open was 2821 against the official 2894.25.
  - See `reports/forward/lse_reconstruction_check.json`.
- **09-21 marks** equal yfinance's official closes to the cent for all 11 positions, in both working
  runs. They are not stale.
- **09-21 19:58 ET record:** all positions were unmarked and `marked_nav` fell back to cash basis.
  `performance.recorded_marks` (`bot/performance.py:193-204`) skips records with empty `marks`, so
  the dashboard series used the 18:44 run. The raw `marked_nav` field in the cycle log is still
  wrong for that record.
- **09-22 marks** cannot be checked against Yahoo's daily close today, because Yahoo currently
  returns NaN for 09-22. AZO's mark agrees with the LSE auction print.
- **Days without a recorded mark** (everything before 09-21) are marked from `data/raw` closes.
  - Those closes are dividend-adjusted (`data/ingestion.py:32`, `auto_adjust=True`), while fills are
    unadjusted. Example: AVGO on 09-18 was 356.96 cached against 357.61 unadjusted.
  - This biases the marked series around ex-dividend dates.

## 7. Would a skeptical reviewer accept today's record?

No:
1. n = 1 live entry, with no inference possible.
2. Every entry is decided after its fill price exists.
3. Live sizing and capacity are conditioned on a simulated book.
4. The files are mutable and unanchored, and backfill timestamps are fabricated.
5. The code changed three times in the first week.
6. Decision inputs are not logged.

The earliest clean forward observation requires all of the following:

- **Fix the entry convention.** Either change is a new strategy version to register:
  - **(a)** decide before the close: run at about 15:30 ET, with candidates taken from the schedule
    log so the fetch takes minutes rather than 50, and fill at the price available at decision time;
    or
  - **(b)** decide after the close and fill at the **next official open**.
  - (a) keeps the validated close-entry convention; (b) needs no schedule change but gives up the
    overnight drift, and should be replay-checked first.
- **Start a separate forward book at a fixed NAV.** Alternatively, have the evaluator price
  decisions independently of the paper account, as `research/forward/evaluate.py` does.
- **Freeze the code under a registered hash.** `research.forward.record --strategy pead_bot_v1
  --ingest` does this automatically.
- **Ingest every night** before the next execution time, and **anchor the head externally**
  (REPORT.md).

## 8. Proposed fix (`reports/forward/proposed_fix.diff`, NOT applied)

What it changes:
- Fetch errors are distinguished from empty answers.
- Training-cache rows are tagged `cached_announced` and excluded from staleness.
- There is one accurate "data unreachable" alert. Such a cycle is marked `degraded`: no entries,
  no heartbeat, no `marked_nav`.
- `marked_nav` is recorded only when every position was priced.
- Every cycle carries `provenance`, `started_at` and a code-plus-model fingerprint.
- Every entry carries `decided_at`, `decided_after_close` and its exact inputs.
- Ledger records carry `provenance`, `price_source` and `decided_at`.
- A future backfill writes `provenance: "backfill"` plus its real write time.

Testing:
- The patch applies cleanly (`git apply --check`).
- It was tested only in a scratch copy of the repo: 125 passed, 6 skipped (skips are network tests),
  including 7 new tests in `tests/test_bot_forward_hygiene.py`.

What it does not do: it does not change the entry convention. That is a strategy decision (§7).
