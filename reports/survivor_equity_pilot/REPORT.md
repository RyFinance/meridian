# Free survivor-free US equity panel: feasibility (cycle 5, Program B2)

*The B2 agent built the code (`research/survivor_equity_pilot/`), the data (`data/survivor_equity_pilot/`, 44 MB with a
manifest) and the outputs in this folder. It was cut off by an API session limit before writing its report. The
director compiled this report from its output files on 2026-09-25.*

## Verdict: PARTIAL. The universe can be rebuilt for free; prices for delisted names cannot. The chain breaks at PRICES.

## What works (the universe side)

| Link | Source (free, keyless) | Evidence |
|---|---|---|
| CIK history for dead firms | data.sec.gov submissions JSON | 200 for dead CIKs; 49 of 51 pilot names resolved to a CIK |
| Historical ticker ↔ CIK map | Wayback snapshots of SEC `company_tickers.json` | 8 snapshots, 2017-12 → 2025-07; 13,749 distinct CIKs |
| Listed universe by date | Wayback snapshots of Nasdaq Trader `nasdaqlisted` and `otherlisted` | 11 + 5 snapshots, 2008 → 2025 |
| Listing and delisting dates | Tiingo public `supported_tickers` list (no key needed for the list) | 108,834 rows; 16,801 US stocks ended before 2026-06 |
| Daily point-in-time "traded that day" universe | FINRA Reg SHO CNMS files (`data/c4/finra_regsho`) | 1,737 files, 2018-08 → 2026-09; 9–14k symbols per year; about 10k symbols disappear over 2018–2026 (an upper bound, since it includes ticker changes) |

## Where the chain breaks (prices for delisted names)

| Source | Result |
|---|---|
| Yahoo chart endpoints | In a stratified random sample of 150 delisted names (50 ended on exchange, 50 OTC, 50 Q-suffix), **146 were NOT FOUND**, 2 were ticker-recycled after the end date, and 2 had a mismatched window. In the 51-name pilot, the recycled tickers (SBNY, BBBY, SI) give false histories that start after the original company died. |
| Tiingo, Alpha Vantage, EODHD price APIs | Need an account or key, which is not allowed. |
| Stooq | JavaScript bot challenge, which was not bypassed. |
| SEC, FINRA | No prices. |
| LSE Terminal | Only 127 non-live names, all delisted after 2026-04. |
| Kaggle "price-volume-data-for-all-us-stocks-etfs" | The endpoint served a 515 MB zip without a login when probed. It was inspected (17,078 files) but **not retained or used**: its licence and provenance are unverified, and it is frozen at 2017-11-10. That makes it survivor-biased as of 2017, and it lacks Enron, Lehman, Bear Stearns, Countrywide, WaMu and others. The probe was changed so it cannot re-download. |

## Consequence

- quant_v7 **cannot** build a usable survivor-free US equity return panel from free, legitimate sources.
- It **can** build a survivor-free *event and universe* panel: who was listed, when each name delisted, and CIK
  continuity.
- **The exact missing field is the daily close (and the delisting return) for US common stocks after they delisted.**
  Sources that have it: CRSP DSF/DSEDELIST, Sharadar SEP plus ACTIONS, or Norgate.
- **If paid data is ever justified:** Sharadar SEP (about $500/yr) would unlock:
  - the FINRA short-volume design;
  - the 8-K item-event designs;
  - a corrected re-measurement of fundamentals F1–F3 (amendment 1 §C).

  Even then, these designs are MARGINAL at best under the power framework, so the purchase is not recommended on
  power grounds alone.
