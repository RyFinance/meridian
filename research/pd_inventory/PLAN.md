# Primary-dealer long-dated Treasury inventory → 10-year duration timing: pre-registration (template v2)

Status: DRAFT until its hash and code hashes are in `research/preregistrations.jsonl`. Written 2026-09-25 by the
director. This is cycle 5, experiment #1, and the only experiment registered this cycle: batch k = 1, α = 0.05.

## What has been viewed (disclosure)

- **NY Fed primary-dealer statistics** (`data/new_info_scout/nyfed_pd`):
  - the cycle-5 scout saw about 15 raw values in file headers;
  - the director printed coverage by segment and year, and the signal's mean (0.12), sd (0.62) and weekly
    autocorrelation (0.905);
  - no return or signal→return relationship has been computed.
- **Overlap guard:** the correlation of this signal with the weekly `tsy_auction_demand` signal is 0.06 (0.10 against
  the trailing 4-week sum), below the 0.3 threshold, so it is not charged to that family.
- **Sibling knowledge:** `tsy_auction_demand` (E2, a dealer-absorption flow measure) failed development in cycle 4;
  `auction_cycle` is spent. This test uses the inventory STOCK, which is new information: this dataset has never been
  used by the project.

## 1. Mechanism

- Primary dealers intermediate Treasury supply under balance-sheet constraints: the SLR, VaR limits and funding.
- When their net long-dated inventory is high relative to its recent norm, holding it needs a price concession, i.e.
  higher expected returns on duration.
- The concession is earned as the inventory is distributed.
- Literature: dealer inventory and balance-sheet constraints in Treasuries (e.g. Fleming & Rosenberg; He, Nagel &
  Song 2022; Duffie on dealer constraints).
- **Direction (fixed):** long duration when inventory is high, short when it is low. The reverse is never tested.

## 2. Information and data

- **Source:** NY Fed Primary Dealer Statistics (FR 2004), bulk CSV, keyless.
- **Series:** the net outright position ($mn) in Treasury coupons with more than 6 years to maturity, by segment:

  | Segment | Series |
  |---|---|
  | 1998-01 → 2001-06 | PDPUSGCS5MNOP (more than 5 years; the only split available) |
  | 2001-07 → 2013-03 | PDPUSGCS611NOP + PDPUSGCSM11NOP |
  | 2013-04 → 2021 | G6L7 + G7L11 + G11 |
  | 2022+ | G6L7 + G7L11 + G11L21 + G21 |

- **Series breaks:** the NY Fed break dates are 2001-07, 2013-04, 2015-01, 2022-01 and 2024-07. The z-score restarts
  at every break.
- **Timing and vintages:** values are as of Wednesday and published the next Thursday, about 16:15 ET (8 days later).
  The API holds latest values only, not vintages. That is a disclosed limitation; revisions are believed to be rare.
- **Returns:** FRED DGS10 (H.15, about 15:30 ET closing bid).

## 3. Construction (`research/pd_inventory/core.py`)

- **Signal:** z = (x − mean of the previous 52 weeks) / sd of the previous 52 weeks, within each segment, with at
  least 13 prior weeks. It is clipped to ±2, and w = z/2.
- **Availability:** as-of date + 9 days. The position is set at the first H.15 close on or after that date and held
  until the next update.
- **P&L:** w × (−7 × ΔDGS10/100), daily (price return, no carry). Position set at close t earns t → t+1.
- **Costs:** base 1 bp, stress 3 bp of price per unit |Δw|.
- **Gating series (amendment-4 proposal Q1, adopted voluntarily):** ACTIVE = book − (average w over the window) ×
  duration return, i.e. net of an exposure-matched control.

## 4. Windows

- **Development:** 1998-05-01 → 2012-06-29 (about 14.2 years).
- **Validation (locked):** 2012-07-02 → 2026-08-31.

## 5. Null

- **Gating:** a mean-centred circular block bootstrap of the daily active series (21-day blocks, 5,000 draws, seed
  20260925). A HAC t is not used (audit A1, finding 1). P(pass | null) comes from the same bootstrap.
- **Reported only:** a circular shift of the weekly signal by at least 52 weeks (1,000 draws).

## 6. Gates

- **Development (amendment 2, k = 1):** active Sharpe ≥ 1.8/√T (about 0.48), stress active mean > 0, and bootstrap
  p < 0.05.
- **Validation (amendment 3 P2 plus proposed amendment 4 Q4, adopted voluntarily):** p < 0.05, active Sharpe ≥ 0.30,
  and stress active Sharpe ≥ 0.30.
- **Promotion:** guards G1–G7.

## 7. Power

Spec: `research/power/examples/c5_pd_inventory_k1.json`, derived from the scout's
`research/new_info_scout/specs/nis_f1_pd_treasury_inventory.json` with batch k = 1. D = 1.1 (ASSUMPTION, ≥ 1 per
proposal Q6).

- 7,006 daily observations are worth about 6,369 effective ones. SE(Sharpe) is 0.28 per window.
- MDE (single test): Sharpe 0.49.
- **Joint power** at true S = 0.3 / 0.5 / 0.7 / 1.0: 0.07 / 0.29 / **0.62** / 0.94. False pass is 0.002.
- **Verdict: DECISIVE** at the 0.7 reference.
- **Honest caveat (proposal Q5):** the scout's literature-and-decay prior implies S ≈ 0.30, where joint power is 0.07.
  This test detects a LARGE effect only. A FAIL is informative only against S ≳ 0.5.

## 8. Burden

- Rates/duration and dealer-flow family: tsy_month_end, IEF−SHY, auction_cycle, tsy_auction_demand and others.
  About 12 earlier shots in rates/duration.
- Project-wide: about 240 shots; M_eff ≈ 25.

## 9. Rules

- **If development fails:** record it. No re-specification: no other maturity buckets, lookbacks, lags, instruments
  or sign.
- **If it passes:** stop. Two independent adversarial audits (implementation/data, statistical/economic), then
  validation only by a registered unlock.
