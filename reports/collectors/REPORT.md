# Data-Collector Infrastructure — Report (Cycle 5, Program E)

*Written by the cycle-5 E agent. Saved by the director session. No schedule installed.*

**Code:** `research/collectors/` — `common.py` (shared snapshot writer), `binance_futures.py`, `bybit.py`, `okx.py`, `deribit.py`, `cboe_options.py`, `finra_regsho.py`, `finra_short_interest.py`, `etf_holdings.py`, `ibkr_borrow.py`, `collect_all.py`
**Tests:** `tests/test_collectors.py` — 18 tests, all HTTP mocked via `monkeypatch.setattr("requests.get", ...)`, no network in test runs. All pass.
**Data written this session:** `data/collect/` — 184 files, 16 MB (two live runs of `binance_futures` in the process of debugging, so its manifest has 2×; every other source has exactly one run). No existing files edited; `bot/`, `reports/forward/`, cron/launchd untouched; nothing committed or pushed.
**User-Agent used everywhere:** `quant_v7-research/1.0` (no email, per the task's rules).

## Ranked candidates

| Rank | Candidate | Research value | Access | ToS status | Storage/day | Storage/year | Built? | Why |
|---|---|---|---|---|---|---|---|---|
| 1 | Binance USD-M: open interest, open-interest history, top-trader position/account L-S ratio, global L-S ratio (15 liquid symbols) | High — crowding/positioning signals with a hard 30-day API lookback; collecting now is the *only* way to ever have pre-today history | Keyless REST, `fapi.binance.com` | robots.txt only disallows named search-crawler bots (Baiduspider etc.), not a generic API client; **not geo-blocked from this sandbox** (HTTP 200 throughout) | ~3.8 MB | ~1.4 GB | **Yes** | `run_once` OK, 75 files, 4.0 MB |
| 2 | Deribit option book summaries, BTC+ETH, all strikes (IV, OI, volume, bid/ask) + future/perp book summary | High — the only free, keyless, all-strikes option-surface snapshot found among any candidate (Cboe gives ratios, not per-strike) | Keyless JSON-RPC | No robots.txt restriction found (404, default-allow); public, documented API | ~0.80 MB | ~292 MB | **Yes** | `run_once` OK, 4 files, 836 KB |
| 3 | FINRA Reg SHO daily short volume — incremental (CNMS + FNSQ/FNYX/FORF/FNRA tapes) | High — highest existing FINRA ranking score in `reports/public_scout` (rank 1 of 24); the project's existing archive (`data/c4/finra_regsho/`) is a one-time backfill through 2026-09-24, not incremental | Keyless flat file, `cdn.finra.org` | Public bulk-file endpoint, previously used without incident by this project's scouts | ~1.35 MB | ~340 MB (252 trading days) | **Yes** | `run_once` OK: today (2026-09-25) not yet published (403, market still open), walked back to 2026-09-24, 5 files, 1.41 MB |
| 4 | Bybit linear-perp tickers (mark/index/funding/OI/volume, market-wide, one call) + per-symbol OI history (10 liquid symbols) | Medium-high — free geo-block-safe alternative/complement to Binance; market-wide tickers snapshot is cheap breadth | Keyless REST, `api.bybit.com/v5` | No robots.txt restriction (404) | ~0.82 MB | ~299 MB | **Yes** | `run_once` OK, 11 files, 859 KB |
| 5 | OKX SWAP tickers + open interest, market-wide, 2 calls | Medium — same rationale as Bybit; OKX explicitly `Allow: /api/*?` in robots.txt, the clearest of any venue tested | Keyless REST, `www.okx.com/api/v5` | robots.txt explicitly allows the API paths | ~0.20 MB | ~73 MB | **Yes** | `run_once` OK, 2 files, 213 KB |
| 6 | FINRA bi-monthly short interest — incremental settlement-date pickup | Medium-high — rank 3 in `reports/public_scout`; direct crowding measure, coarser cadence than Reg SHO but genuinely new (existing archive is also a one-time backfill) | Keyless flat file, `cdn.finra.org` | Same host/pattern as #3, already used safely by prior scouts | ~2.1 MB per publication (~24/yr) | ~50 MB | **Yes** | `run_once` OK: 2026-09-15 settlement found and fetched (2.20 MB); 2026-09-30 not yet due |
| 7 | ETF issuer daily holdings/shares-outstanding — IVV (iShares) + SPY (SPDR) | Medium — standard free creation/redemption proxy; two funds, two issuers, S&P 500-tracking, gives an issuer-independent starting pair | Keyless static file, `ishares.com` + `ssga.com` | Both files are the issuers' own "download holdings" product, intended for public download; robots.txt on both hosts does not disallow these paths | ~2.2 MB | ~554 MB (252 trading days) | **Yes** | `run_once` OK, 2 files, 2.31 MB (IVV CSV ~2.25 MB, SPY xlsx ~54 KB) |
| 8 | Cboe daily options market statistics (put/call ratios, volume by class) | Low-medium — coarse, index-level, but free, tiny, and no equivalent already in the project | Keyless static JSON, `cdn.cboe.com` | `www.cboe.com/robots.txt` disallows only `/book/` and `*market_statistics/volume_reports/`; this endpoint is neither | ~7 KB | ~1.7 MB | **Yes** | `run_once` OK: today not yet published, walked back to 2026-09-24, 1 file, 6.7 KB |
| 9 | IBKR public shortable-stock FTP (borrow rates + available shares) | High if reachable — the only free retail borrow-fee source identified anywhere in this project (`reports/data_scout/REPORT.md`), explicitly current-only so forward collection is the only way it will ever exist here | Anonymous keyless FTP-over-HTTPS, `ftp{1,2,3}.interactivebrokers.com/usa.txt` | Long-standing anonymous no-login public file (basis for third-party tools like iborrowdesk); could not re-verify a written ToS page this session (wrong page found) | Unverified (typically low single-digit MB, per third-party usage reports) | Unverified | **Built, but not confirmed reachable this session** | All 3 mirrors `ReadTimeout` (25s each) from this sandbox, while the rest of `interactivebrokers.com` was reachable (200) — looks like a network/egress issue specific to that host here, not a ToS block. Code is written and unit-tested (mocked); **must be re-tried from the machine that will run daily collection** before relying on it |
| 10 | Binance forced-liquidation orders | High in principle, but architecturally out of scope for this package | `wss://fstream.binance.com/ws/!forceOrder@arr` — **websocket only, no historical REST** | N/A | N/A | N/A | **Not built** | A `run_once()` snapshot tool cannot capture a stream; would need a long-lived subscriber process (different architecture, likely its own daemon/service). Documented, not faked |
| 11 | OCC daily volume/OI totals | Low-medium | `theocc.com/webapps/daily-volume-totals` | **Blocked**: HTTP 403 in this session's probe | — | — | **Not built** | Confirmed blocked; not pursued further (no bypass attempted) |
| 12 | SEC EDGAR daily index / 13F / 8-K feeds | Medium (mechanism value; see `reports/edgar_scout/REPORT.md`) | Mixed: `data.sec.gov`/`efts.sec.gov` reliable, `www.sec.gov` intermittently 403s regardless of UA | Compliant (no email added to UA, no bypass attempted) | — | — | **Not built here** | Already has a full one-time cycle-4 archive (`research/edgar_scout/`, `data/edgar_scout/`, ~129 MB) per this task's own context; that archive is not kept fresh either, but building a third EDGAR pipeline in this budget would duplicate rather than add new source coverage. Recommended as the next incremental-collector candidate after this batch, not built now |
| 13 | Kraken Futures, dated-futures basis (dedicated) | Low-medium | Keyless REST | Not independently probed this session | — | — | **Not built** | Deribit's future/perp `book_summary` (built, #2) already gives a basis snapshot; Bybit+OKX+Deribit is a diverse-enough triple for the crypto-derivatives side within this budget. Kraken is a reasonable follow-up, not a gap |

## `run_once` results (live, this session)

| Collector | Status | Files | Bytes | Notes |
|---|---|---|---|---|
| `binance_futures` | ok | 75 | 4,006,904 | 15 symbols × 5 endpoints; no 451 (not geo-blocked here) |
| `bybit` | ok | 11 | 858,865 | market-wide tickers + 10 symbols' OI |
| `okx` | ok | 2 | 212,904 | market-wide tickers + market-wide OI |
| `deribit` | ok | 4 | 835,564 | BTC+ETH option book summary + future book summary |
| `cboe_options` | partial | 1 | 6,693 | today (403, not yet published) → fell back to yesterday |
| `finra_regsho` | partial | 5 | 1,414,213 | today (403, not yet published) → fell back to yesterday, all 5 tapes |
| `finra_short_interest` | partial | 1 | 2,202,748 | 2026-09-30 not due yet (excluded); found 2026-09-15 |
| `etf_holdings` | ok | 2 | 2,305,719 | IVV (iShares) + SPY (SPDR) |
| `ibkr_borrow` | **failed** | 0 | 0 | all 3 mirrors `ReadTimeout` after 25s — see candidate #9 |

`status: partial` above means "found the data, but only after one or more expected 403/404s from walking back to the most recently published day/settlement" — not an error condition.

**Total new data this session:** `data/collect/` = 16 MB, 184 files across 8 successfully-writing sources (binance_futures counted twice due to a debugging re-run; steady-state daily total across all 8 working sources is **≈11.6 MB/day**, ≈2.65 GB/year at that same cadence, dominated by `binance_futures` (3.8 MB), `etf_holdings` (2.2 MB), and `finra_short_interest`/`finra_regsho` (amortized)).

## Recommended schedule (not installed — no cron/launchd/scheduled task was created)

```bash
cd /Users/rytty/CCP/quant_v7 && PYTHONPATH=. .venv/bin/python -m research.collectors.collect_all
```

- **Cadence:** once daily. Crypto venues (Binance/Bybit/OKX/Deribit) are 24/7 — any consistent UTC time works; **run after ~21:00 UTC** so `cboe_options` and `finra_regsho` land after US market close and Reg SHO's evening publication, reducing (not eliminating) the walk-back 403s seen above.
- `finra_short_interest` only actually changes twice a month; running it daily is harmless (it just re-finds the same settlement file until a new one publishes) and keeps the logic simple — no separate schedule needed.
- To skip a slow/unreachable source (e.g. `ibkr_borrow` from a network where it's known to hang): `--only binance_futures,bybit,okx,deribit,cboe_options,finra_regsho,finra_short_interest,etf_holdings`.
- **Storage:** ≈11.6 MB/day steady state (≈2.65 GB/year) across the 8 working sources; add `ibkr_borrow`'s unverified size once reachability is confirmed elsewhere.
- **ToS notes carried into scheduling:** nothing here requires an account, key, or login; every source was checked live for robots.txt/ToS text where a robots.txt exists (Cboe, iShares, SSGA, OKX, IBKR) and none disallows the paths used. `finra_short_interest`/`finra_regsho` reuse URL patterns this project has already fetched without incident in cycle 4. No source was scraped past a documented block (OCC 403, `cdn.finra.org`'s own not-yet-published 403s) or geo-circumvented.

## Limitations

1. **IBKR borrow file unreachable from this sandbox** (candidate #9) — all three documented mirrors timed out; this is the single highest-value unresolved item (only free retail borrow-fee source found project-wide) and should be re-tested from the actual collection host before being relied on.
2. **Binance was not geo-blocked in this session** — unlike the task's stated risk (451 from some locations), every Binance call here returned 200. If the machine that runs `collect_all.py` daily is geo-blocked, `binance_futures.run_once` will report it in `blocked` (tested in `test_binance_futures_run_once_records_451_as_blocked`) rather than fail silently or retry through a workaround; Bybit/OKX/Deribit remain as the geo-block-safe fallback set, exactly as the task anticipated.
3. **Cboe and FINRA "today" files are routinely unpublished at collection time** — both collectors correctly walk back to the most recent published day, but a same-day, pre-close run will always show one or two 403s in its error list; this is expected, not a bug, and is asserted in the tests.
4. **No forced-liquidation collector** — Binance only streams this over a websocket with no historical REST; capturing it would need a different (long-running) architecture than the `run_once()` snapshot pattern used everywhere else here, so it is documented as a gap rather than faked.
5. **EDGAR, Kraken, and a broader crypto/ETF symbol universe were deliberately left out of this batch** — not because they lack value, but because the existing EDGAR archive already covers that ground once (unrefreshed), and Bybit+OKX+Deribit already gives cross-venue diversity for the crypto side within this session's scope; both are reasonable next additions to this same `research/collectors/` package.
6. **No return, signal, or derived statistic was computed anywhere in this workload** — every collector writes raw bytes exactly as received; `sha256`/byte-count/status-code are the only "analysis" performed.