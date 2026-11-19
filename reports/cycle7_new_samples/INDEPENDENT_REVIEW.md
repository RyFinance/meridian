# Cycle 7 read-only qualification of the completed results

2026-09-27. This note does not change a frozen spec, sample, trial, metric, or
PASS/FAIL record. No new returns were calculated. It qualifies the claims in
`RESULTS.md` using the already-frozen data/build records.

## Headline status

The eight ledgered computations are reproducible *as computations of the Cycle 7
snapshots*. Their interpretation as exact, unchanged-spec replications is more
limited. In particular, the reported CARRY-FX FX-EM `NEW-SAMPLE POSITIVE`
(active Sharpe 1.12; five calibrated p-values 0.0056–0.0071 against 0.00833)
must be described as **conditional on the preregistered proxy data**. It is not
an independently verified executable offshore carry premium, and it does not
establish an exact 3-month-rate replication for the full panel. Under the
owner's rule that a sample with a construction mismatch is infeasible, the
`POSITIVE` flag in `RESULTS.md` should **not** be promoted as an exact-spec
replication. The recorded numerical trial remains in the ledger; its label is
the issue, not a license to delete or rerun it.

## Construction and provenance qualifications

1. The owner requested FX spot from LSE. The Cycle 7 FX build instead uses BIS
   WS_XRU central-bank spot for most new currencies and Fed H.10 for others
   (`research/cycle7/data_fx/build.py`, `spots`). This was disclosed in the
   pre-return build and the final report, but it is a source deviation from the
   Cycle 7 request. The LSE USDMXN history probe returned no candles.
2. The frozen CARRY-FX spec calls its signal a local 3-month rate. The Cycle 7
   FX build uses a BIS WS_CBPOL *central-bank policy rate* when its OECD/LSE
   rate is missing (`short_rate`). The frozen PASS candidate list records this
   fallback for **9 of 22** new FX markets, totalling **36,490 daily source
   observations** in their used windows: ARS 5,933; BRL 1,870; DKK 4,021;
   HUF 987; MYR 7,129; PEN 5,720; PHP 8,845; RUB 816; THB 1,169. A policy
   rate is not in general an observed 3-month investable rate. Because the
   filter and returns are already frozen, excluding those markets now would be
   a new trial, not a correction of the reported trial. The positive flag is
   valid only for the declared proxy construction, not for the exact economic
   3-month-rate claim across all 22 markets.
3. The Cycle 7 framework explicitly included NDF-only currencies at onshore
   spot plus local rates. The completed report attributes 29% of CARRY-FX
   gross P&L to them. Offshore NDF-implied returns can differ materially; the
   result therefore does not yet demonstrate retail tradability. This is a
   disclosed implementation gap, not a newly discovered change to the rule.
4. `FI-DEEP` is a 44-month **pre-publication historical extension** ending
   1993-03. The frozen TSMOM-FI spec's post-publication cutoff is 2011-01 and
   its fidelity benchmark requires at least 60 overlapping AQR months.
   Consequently the FI-DEEP full-window p-value is descriptive and fidelity
   cannot be assessed there; it is not post-publication corroboration.
5. For heating oil and propane, the commodity build infers EIA roll days from
   a first-trading-day calendar rule. The existing price-level check does not
   independently verify held contract IDs/expiries. Both commodity pooled
   results fail the fixed positive rule, so no rerun is justified here.

`COMMODITY_FEASIBILITY.md` predates the completed runs and proposes gates that
conflict with the registered `FRAMEWORK.md`; it is superseded background, not
a governing Cycle 7 preregistration.

The official RBA daily 10-year Australian series may now be accessible even
though `RESULTS.md` lists that host as blocked. It was not in the frozen FI-NEW
snapshot. Adding it here would violate the one-run sample rule; it can only be
considered in a separately preregistered future dataset version.

## Verification performed in this review

- `python -m pytest -q tests/test_cycle7_forward_targets.py
  tests/test_cycle7_runner.py`: **22 passed**.
- Read-only inspection confirmed that `research/cycle7_prereg_ledger.md`
  records the six original spec hashes, sample hashes, five snapshot hashes,
  runner hash, and `k=6` at 2026-09-27T14:32:56Z, preceding the first
  `started` trial row at 14:33:02Z. The trial ledger contains eight `started`
  and eight `ok` rows, with no failed or repeated trial.
- Recomputing the five current snapshot-view manifest hashes with the frozen
  guard returned the five hashes in the preregistration ledger, with no drift.
- The noted FX rate-source counts come from the frozen
  `data/cycle7/fx/eval/candidate_list.csv` QA `notes`, not from strategy returns.
