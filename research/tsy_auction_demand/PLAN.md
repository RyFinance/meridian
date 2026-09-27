# Treasury auction demand surprise → post-auction yield reversal: pre-registration (template v2)

Status: DRAFT until its hash and code hashes are in `research/preregistrations.jsonl`. Written 2026-09-25 by the
director, cycle 4, experiment E2. Batch: E1 (`crypto_funding_xs`) and E2 are registered together, so k = 2.

## What has been viewed (disclosure)

- **Auction data:** fields and per-year coverage only (`data/c4/tsy_auctions`, fiscaldata `auctions_query`). The
  signal's distribution (mean −0.02, sd 0.98) was printed. No yield change after any auction has been computed.
- **FRED constant-maturity yields:** only the first and last dates were printed.
- **Sibling knowledge:**
  - `research/auction_cycle` (Lou–Yan–Zhang calendar effect, unconditional) failed on IEF/TLT 2015–2026. This is the
    same dealer-inventory mechanism family (information family: calendar/flow), but with new information (the
    auction RESULT).
  - `research/audit_tsy` used 10-year yields around month-ends.
  - `reports/trial_accounting` puts 11 prior shots in the calendar/flow family and about 240 project-wide.

## 1. Mechanism

- Primary dealers must absorb the part of each auction that end investors do not take.
- When bidding demand is weak relative to recent auctions of the same tenor, dealers and marginal holders are left
  with excess duration inventory. The auction clears at a concession, which is then worked off over the following
  days, so yields partly reverse. Strong demand gives the opposite.
- Literature:
  - Lou, Yan & Zhang (2013, RFS): inventory price pressure around auctions;
  - Fleming & Rosenberg (2008): dealer inventory and Treasury returns;
  - Beetsma et al. (2016): the European version.
- **Direction (fixed):** after WEAK demand (bid-to-cover below its recent norm), go long duration; after STRONG
  demand, go short. The reverse is never tested.

## 2. Information and data

- **Auctions:** Treasury fiscaldata `auctions_query` (keyless), fetched 2026-09-24; see the manifest in
  `data/c4/tsy_auctions`.
  - Nominal fixed-rate Notes and Bonds only: TIPS and FRNs are excluded; reopenings are included.
  - Bid-to-cover is reliably populated from 2000.
  - Results are released at about 13:00–13:05 ET on the auction date.
  - Fields are final (no revisions); the data are point-in-time.
- **Yields:** FRED H.15 constant-maturity DGS2/3/5/7/10/20/30 (manifest in `data/c4/fred`). They are based on
  closing bid quotes (about 15:30 ET), i.e. after the auction result.
  - DGS30 has a gap (2002-02 → 2006-02), filled with DGS20.
  - H.15 yields are not revised in practice.
- **Survivorship:** none. Every auction is in the file.

## 3. Construction (code: `research/tsy_auction_demand/core.py`)

- **Tenor bucket** from issue → maturity: 2, 3, 5 (includes 4-year), 7, 10, 20, 30.
- **Surprise:** s = BTC − the median BTC of the previous 6 auctions in the same bucket (at least 4 required).
- **Standardisation:** z = s / sd of the previous 12 surprises (at least 6 required), clipped to ±2.
- **Position:** w = −z. Everything uses past auctions only (unit-tested).
- **Holding:** enter at the auction-date H.15 yield, exit 5 yield-dates later.
- **Event return:** w × (−Δy) × 7 (a fixed 7-year-duration notional per unit w, in the tenor's own yield).
- **Book:** the daily calendar-time return is the sum over active events, divided by 4. Excess over cash is
  implicit, since this is a duration position (yield change, no carry).
- **Costs:** base 2 bp of price per side per unit |w|; stress 6 bp. Charged on the entry and exit days.

## 4. Windows

- **Development:** auctions from 2000-01-01 to 2012-12-31 (about 515 events).
- **Validation (locked):** 2013-01-01 → 2026-08-31 (about 1,000 events). It needs a registered
  `VALIDATION_UNLOCK.md`.

## 5. Controls and null

- **Gating null (mean-zero):** a mean-centred 21-day block bootstrap of the daily base series, 5,000 draws, seed
  20260925. P(pass | null) is reported from the same bootstrap (`struct_common.null_pass_rate`).
- **Placebo:** w shuffled within each bucket, 1,000 permutations. It keeps the exposure profile and breaks the demand
  link. Its p and mean are reported.
- **Control (descriptive):** unconditional long-after-every-auction (w = +1), which is the auction_cycle sibling.

## 6. Gates

- **Development:** base Sharpe ≥ 1.8/√T (T ≈ 13 years, so about 0.50), stress mean > 0, and bootstrap p < 0.025
  (α = 0.05/2).
- **Validation (amendment 3, P2):** bootstrap p < 0.05 (k_val = 1), stress mean > 0, and Sharpe ≥ 0.30.
- **Promotion:** guards G1–G7 (`research/certify/guards.py`), with 10-year and 2-year yield-change benchmarks.

## 7. Power (`research/power/examples/c4_tsy_auction_demand.json`; `reports/power/c4_tsy_auction_demand.json`)

- 1,600 events are worth about 918 effective ones (deff 1.74, clusters of about 3, icc 0.3: ASSUMPTION).
- SE(Sharpe): dev 0.28, val 0.27.
- Single-test MDE: Sharpe 0.54, about 14 bp net per event.

| Gate | Joint power at S = 0.5 / 0.7 / 1.0 | False pass |
|---|---|---|
| Current | 0.08 / 0.30 / 0.78 | 0.0001 |
| Amendment 3 | 0.25 / **0.59** / 0.93 | 0.001 |

**Verdict: DECISIVE** under the amendment-3 gate (MARGINAL under the old gate). At the assumed 15 bp gross per event,
the implied net Sharpe is 0.76.

## 8. Burden

- Calendar/flow family: 11 earlier shots, including one sibling on the same mechanism.
- Project-wide: about 240 shots; M_eff ≈ 25.
- A dev pass must be read against this.

## 9. Rules

- **If development fails:** record it; no re-specification (tenor subsets, horizons, other demand measures,
  indirect-bidder share, sign).
- **If it passes:** freeze it, run an independent adversarial audit, and unlock only by a registered
  `VALIDATION_UNLOCK.md`.
