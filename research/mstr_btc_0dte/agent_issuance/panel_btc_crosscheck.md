# Panel BTC cross-check — issuance panel vs validated purchase events

Status: **COMPLETE — ALL CHECKS PASS** · 2026-10-17 · review-completion data QA, **no return statistic computed**
Script: `panel_btc_crosscheck.py` (this directory) · Run: `cd /Users/rytty/CCP/quant_v7 && .venv/bin/python research/mstr_btc_0dte/agent_issuance/panel_btc_crosscheck.py`
Inputs (read-only): `issuance_btc_raw.csv` (panel, 96 rows / 90 accessions, 2024-09-13..2026-10-05) vs `../agent_events/validated_purchase_events.csv` (106 events, 2020-08-11..2026-10-05). Filing bodies re-verified against scratch cache `…/T/opencode/mstr_8k_cache` (160/160 panel-window accessions cached).

## Headline

Overlapping accessions agree on quantity with **one** exception, and every asymmetric row classes into an enumerated cause; the window totals reconcile to the exact BTC:

```
overlap: 72 accessions / 75 rows — 71 exact matches, 1 mismatch (+3 BTC, panel correct)
panel purchases (excl. 3 quarterly recap rows): 621,231 BTC
validated purchases (filing >= 2024-09-13):     624,206 BTC
delta = -2,975 = (4,020 + 220 + 3) - (4,603 + 950 + 1,665)   [PASS]
```

`panel - validated = -2,975` is fully explained by six enumerated event-level discrepancies; nothing else differs.

## The six discrepancies (each adjudicated against the filing body)

| # | Event | Panel | Validated | Correct side | Cause |
|---|-------|-------|-----------|--------------|-------|
| 1 | ATM-2026-01-05 (acc 0001193125-26-001550) | 1,286 | 1,283 | **panel** (+3) | validated recorded only the Jan 1–4 kicker; the filing also has a Dec 29–31 segment (3 BTC) |
| 2 | 2025-05-27 (acc 0000950170-25-077387) | 4,020 | — | **panel** | BTC table only in Exhibit 99.1; validated parsed primaries only |
| 3 | 2025-10-14 (acc 0001193125-25-238132) | 220 | — | **panel** | same exhibit-only cause |
| 4 | 2026-08-31 (acc 0001193125-26-375463) | — | 4,603 | **validated** | panel extractor requires the header token `BTC Acquired`; Aug–Sep 2026 filings say `BTC Purchased` |
| 5 | 2026-09-21 (acc 0001193125-26-396093) | — | 950 | **validated** | same dialect cause |
| 6 | 2026-09-28 (acc 0001193125-26-403417) | — | 1,665 | **validated** | same dialect cause |

### Holdings-chain proof for each adjudication

Filing-printed aggregate holdings close the chain exactly around each disputed quantity:

- **#1 (panel correct):** Jan-5 filing: 672,497 as of Dec 28 (12-29 filing) → **+3** → 672,500 as of Dec 31 → **+1,283** → 673,783 as of Jan 4. Both segments are new purchases; validated undercounts by 3.
- **#2 (panel correct):** 576,230 as of May 18 (5-19 filing) → **+4,020** → 580,250 as of May 25 ("Now Holds 580,250 BTC", release headline) → **+705** → 580,955 as of Jun 1 (6-2 filing). Exact.
- **#3 (panel correct):** 640,031 as of Oct 5 (10-6 filing) → **220 purchased** (release/table) → 640,250 as of Oct 12 → **+168** → 640,418 as of Oct 19 (10-20 filing). Exact up to a ±1 print quirk on the Oct-12 checkpoint only.
- **#4–6 (validated correct):** 840,447 as of Aug 23 (8-24 filing, no activity) → **+4,603** → 845,050 as of Aug 30 (8-31 filing) → **+950** → 846,000 as of Sep 20 (9-21 filing) → **+1,665** → 847,666 as of Sep 27 (9-28 filing; printed value, visible +1 vs 847,665 strict arithmetic) → **+334** → 848,000 as of Oct 4 (10-5 filing). Quantities exact throughout.

### Root cause (panel side)

`extract_issuance.py:112` classifies a table as a BTC table only if `"btcacquired"` appears in its flattened text; filings whose header reads `BTC Purchased` (or `BTC Purchased / (Sold)`) are silently skipped (no `table_error`, no note — the extraction log row exists, the CSV row does not). Dialect timeline around the gap: `BTC Acquired` through 2026-07-27 → `BTC Sold` (8-03) / `BTC Purchased / (Sold)` (8-17, 8-24) → `BTC Purchased` (8-31, 9-21, 9-28) → back to `BTC Acquired` (10-05). Because the extractor is purchase-only by design, `BTC Sold` filings (see below) also produce no rows — correct for a purchase panel, but the parser would silently skip any future `BTC Purchased` event too.

### Sale-era coverage note (both datasets are purchase-only)

Cache scan of all 160 panel-window filings: BTC **sales** occur 2026-05-30..2026-08-10 — 32 (5-26..5-31), 1,363 + 2,225 (6-29..7-5, one filing, two segments), 1,638 (7-27..8-2), 1,690 (8-3..8-9) = **6,948 BTC sold**; no-activity weeks Aug 10–23 and Aug 31–Sep 13 (the latter two announced in prose, no table). Neither dataset represents sales (out of scope by design); any future consumer needing holdings reconciliation must add the sale series.

### Zero-week cost-field artifact (panel only)

Four zero-purchase weeks (filings 2026-06-29, 07-13, 07-20, 07-27) carry a nonzero `btc_cost_musd` (64,100 / 63,690 / 63,690 / 63,690) — the extractor's column-fill attached the holdings "Aggregate Purchase Price (in billions)" cell to the week cost. `btc_qty = 0` is correct in all four. Rule for consumers: **ignore `btc_cost_musd` whenever `btc_qty = 0`**.

### Quarterly recap rows (panel only, exact duplicates)

Three panel rows are full-quarter recaps (Q1–Q3 2025) that exactly duplicate the sum of their twelve weekly rows (80,715 / 69,140 / 42,706 — verified exact). Summing the raw panel must exclude rows with a ≥60-day segment; the reconciliation above already does.

### ±1 BTC print quirks (MSTR's own tables, not extraction)

Holdings columns print ±1 BTC off strict arithmetic at three checkpoints: Oct 12 2025 (640,250 vs 640,251 implied), Aug 2 2026 (842,138 vs 842,137 implied), Sep 27 2026 (847,666 vs 847,665 implied). No purchase or sale quantity is affected; all chains close on either side of each quirk.

## Disposition

- **No registered/hashed file was edited** (the 22 hashes from `research/preregistrations.jsonl` line 96 stand; re-verified same day).
- Panel CSVs were left byte-unchanged. Corrections above are the canonical delta record. A future consumer of a *complete* purchase-event series should union: panel rows (excl. recaps, cost-on-zero ignored) + `{375463: 4,603, 396093: 950, 403417: 1,665}`; future panel regeneration should first fix the dialect token.
- **Impact on the closed issuance study: none** — no return statistic involved (quantities only), no rule was frozen, no holdout window was touched, no re-run of any dev/holdout computation occurred.
- Descriptive extras confirmed against bodies (unchanged from prior QA), see `panel_qa_results.md` for the five anchor checks.

Artifacts: `panel_btc_crosscheck.py`, `panel_btc_crosscheck.md` (hashes registered in `research/preregistrations.jsonl` line 97). Run stdout archived at `…/T/opencode/issuance_audit_20261017/panel_btc_crosscheck_run.txt`.
