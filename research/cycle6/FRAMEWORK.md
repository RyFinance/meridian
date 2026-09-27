# Cycle 6 framework: Styles-Everywhere book (frozen before any strategy return)

Written 2026-09-26 by the director, before any signal-conditioned, strategy, control or portfolio return of cycle 6.
Its SHA-256 is the first entry in `research/cycle6_prereg_ledger.md`. Owner registration of Amendments 4 and 5 is
waived for this cycle; ledger hashes serve as registration. Where this file and Amendment 4
(`research/PROTOCOL_AMENDMENT_4_2026-09-26.md`) or Amendment 5 (`research/PROTOCOL_AMENDMENT_5_REPLICATION_2026-09-25.md`)
differ, the deviation is listed in §9 and nowhere else.

## 1. Menu and inclusion rule (fixed now)

Classes: **EQ** country equity indices; **FI** government bonds (10-year-equivalent per country unless a spec says
maturity buckets); **FX** currencies vs USD; **CM** commodities.

| Style | Paper(s) | Classes | Component IDs |
|---|---|---|---|
| Trend / TSMOM | Moskowitz–Ooi–Pedersen 2012 (Hurst–Ooi–Pedersen 2017 corroborating only) | EQ FI FX CM | TSMOM-EQ, -FI, -FX, -CM |
| XS momentum | Asness–Moskowitz–Pedersen 2013 | EQ FI FX CM | XSMOM-EQ, -FI, -FX, -CM |
| Value | Asness–Moskowitz–Pedersen 2013 | EQ FI FX CM | VAL-EQ, -FI, -FX, -CM |
| Carry | Koijen–Moskowitz–Pedersen–Vrugt 2018 | FI FX CM(energy only) | CARRY-FI, -FX, -CM |
| Defensive / BAB | Frazzini–Pedersen 2014 | EQ, FI (maturity buckets) | BAB-EQ, BAB-FI |
| Seasonality | Keloharju–Linnainmaa–Nyberg 2016; Baltussen–Swinkels–van Vliet 2021 | EQ FI FX CM | SEAS-EQ, -FI, -FX, -CM |

21 candidate components. Equity carry is infeasible with free data (no dividend futures) and is not a candidate.

**Feasibility** is decided once, after the data pass freezes the candidate list and before any component return, from
data availability only:
- a component is feasible iff its mechanical universe (§3) yields a defined class portfolio on **≥ 120 monthly dates**
  (A5 floor) and every input its spec needs exists in the frozen snapshot;
- a class portfolio is defined at month t iff at least **3** instruments are eligible (time-series styles) or **4**
  (cross-sectional rank styles: XSMOM, VAL, CARRY, BAB, SEAS). Paper-silent default; alternative not tested.

Every feasible component is built and run exactly once. Nothing is dropped or added on performance. **k** = the number
of components in the frozen run list; it is written into the ledger before the first component run and never changes.

## 2. Two series per component (A5 §B)

- **Gross paper-fidelity shadow**: the paper's timing (signal at month-end close t, hold month t+1 close-to-close), no
  costs, paper scaling. Used only for fidelity.
- **Net implementable**: same signals and weights, executed at the close of the **first trading day after** the signal
  month-end (one-session lag, A5 G7), base costs charged on traded notional. Used for Sharpe, p-values, book.

Base cost per side on traded notional (half-spread + 1 bp commission, from Sol's component-1 defaults): EQ 2 bp,
FI 2 bp, FX 3 bp, CM 6 bp. **Stress** = 3× base. Financing: synthetic excess returns already net of the local
short rate; no additional financing inside components.

## 3. Universe (mechanical)

The data pass freezes `candidate_list.csv` (one row per unique economic market: class, market id, construction,
source, first/last date, QA status). Instruments that stopped trading are kept for the dates they traded.

**Instrument QA (applied by the data pass, before returns; instrument-level returns only):** status FAIL if any of
(a) construction error vs a real traded proxy TE/σ_proxy > 0.60 on ≥ 36 overlapping months, where a proxy exists;
(b) an unexplained gap > 10 business days; (c) an unexplained duplicate/stale run ≥ 10 business days;
(d) not point-in-time (a value used before it was published). Otherwise PASS. REVIEW is not a status in cycle 6.

**Construction priority (one construction per market, chosen by this order, never by returns):**
EQ: local total-return index − local cash > local price index + declared dividend estimate − local cash > USD ETF
total return − USD cash (declared unhedged deviation). FI: official constant-maturity yield →
y·Δt − D·Δy + ½C·Δy² − local cash (spec declares D, C). FX: spot + lagged short-rate differential. CM: futures
continuation spliced by contract (EIA, crude/natgas, history only) and commodity ETF total return − USD cash; a
market with both uses ETF from the ETF's first full month and the splice before it.

A component's universe = every candidate-list row of its class with status PASS, eligible at month t iff it has the
warm-up history its spec requires at t. Aliases of one market count once.

## 4. Inference (A4 as written, plus §9 deviations)

- **Active series** (A4 §1): active = net book − c, where c is the exposure-matched control on identical dates,
  instruments, scaling, lag and costs:
  - time-series styles (TSMOM): c = m̄ × (always-long book, same instruments and scale), m̄ = mean over the window of
    the book's net exposure ÷ the control's (A4 `active_series`);
  - rank styles (XSMOM, VAL, CARRY, BAB): c = mean of 100 seeded random-rank placebo books with identical
    class/date/weight construction (seed 20260926);
  - SEAS: c = mean of 100 seeded calendar-shuffled books (the month-of-year labels permuted within each year's
    history; seed 20260926).
- **p-value**: A4 §2 null-calibrated HAC t, one-sided (mean > 0) on the monthly net active series in the
  post-publication window. Crash layer (0.2/yr, −6σ) declared for CARRY, XSMOM, BAB. Bandwidth fraction 0.20 for
  TSMOM, XSMOM, VAL, SEAS; 0.10 plus crash layer for CARRY and BAB. **B = 9,999** (§9).
- **Intervals**: A4 §6 studentised bootstrap-t, B = 499, 90%; 95% for crash-declared components with < 120 months.
  Reported for full-sample and post-publication Sharpe of the net series.
- **Post-publication cutoff**: earliest evidenced public circulation; first full month after. Fixed: MOP 2011-01-01,
  KMVP 2013-09-01 (A5). Others are fixed in their specs with evidence; if uncertain, the later candidate date.

## 5. Fidelity tiers (A5 where it speaks; same bands elsewhere)

| Tier | Used by | Rule |
|---|---|---|
| AQR-class | TSMOM-* (AQR TSMOM class column); XSMOM-*, VAL-* (AQR VME class column); BAB-* (AQR Century defensive class column, if it exists) | gross shadow vs benchmark on identical months: n ≥ 60, ρ ≥ 0.65, 0.70 ≤ β ≤ 1.30, TE/σ_ref ≤ 0.90 (A5 class thresholds). Scale follows the benchmark's documented convention; if the benchmark is scaled ex post to a constant vol, the replica is scaled ex post to that vol by its own full-sample vol (a unit convention, never fitted to the benchmark). |
| Paper-stat | CARRY-* (KMVP Table 2 Carry1M, binding; AQR Century carry secondary, ρ < 0.35 flagged only); SEAS-* (BSV 2021 / KLN 2016 class tables) ; BAB-* if no AQR class column (FP 2014 class tables) | over the paper's reported sample: ≥ 95% of its monthly observations; \|Δmean\| ≤ max(2 pp, 0.25·\|mean_paper\|), \|Δvol\| ≤ max(2 pp, 0.20·vol_paper), \|ΔSharpe\| ≤ 0.30 (A5 §C). |

Unassessable fidelity (coverage short, benchmark column absent) = **fidelity FAIL**, reported, not repaired.

## 6. Definition of POSITIVE (owner, fixed)

Component POSITIVE iff fidelity passes AND post-publication net active p (§4) < 0.05/k. Book POSITIVE iff its
post-publication net Sharpe's calibrated 90% interval excludes zero. Everything is reported; no rescue narratives.

## 7. Combined book (rule fixed now; its spec is ledgered before any combined return)

Sleeves: every component that passed fidelity (net implementable series), plus the core 60% SPY / 40% IEF (A5 §E).
Weights: A5 §E exactly — trailing 60-month covariance of sleeve net excess returns using earlier months only, 25%
shrink to diagonal, nonnegative equal-risk-contribution weights, fallback 1/σ then cash; scale to 10% ex-ante vol;
2× gross cap; cash and financing per A5 §E; monthly rebalance at the next session. No expected-return input.
Post-publication window of the book = the latest cutoff among its included components. Report leverage needed for
12%/yr per A5 §E (information only).

## 8. Runs, bugs, trial ledger

- Each component, the book and each tradable variant has a spec `research/cycle6/specs/<ID>.md`; its SHA-256 and UTC
  time are appended to `research/cycle6_prereg_ledger.md` before its first return.
- The runner (`research/cycle6/run_component.py`) refuses to run unless the spec's current hash is in the ledger, the
  code hash and snapshot manifest match those recorded, and no previous run exists for that spec hash.
- Every run (including failed or crashed ones) is appended to `research/cycle6/trial_ledger.csv`.
- A genuine bug may be fixed only when diagnosed against fidelity to an external benchmark or the frozen paper rule
  (never our own Sharpe), with a ledger entry (evidence, before/after hashes, predicted direction) written before the
  rerun. Both outputs are kept and reported.

## 9. Deviations from A4/A5 as written (declared before returns)

1. **B = 9,999 instead of 159** for component p-values. With B = 159 the smallest attainable p is 1/160 = 0.00625,
   above the Bonferroni level 0.05/k for any k ≥ 8, so no component could ever be positive. Only Monte Carlo
   resolution changes; statistic, null model, bandwidth and crash layer are as written.
2. **Components are style × class**, not A5's two components. A5 trend class thresholds and carry tier (a) are
   applied per class. The A5 overall-trend fidelity row (all four classes, ρ ≥ 0.80 …) is reported as information.
3. **Book sleeves** = all fidelity-passing components plus core (A5 §E allowed only trend, carry, core).
4. **Cost defaults** are applied per side on traded notional of synthetic constructions for all classes, not only to
   ETF/FX proxies.
