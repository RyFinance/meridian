# Cycle 6 framework addendum 1 (before any strategy return)

Written 2026-09-26 after the data pass and paper dossier, before any signal-conditioned, strategy, control or
portfolio return. Inputs seen: instrument-level QA only (construction error vs traded proxies), paper texts, AQR
column headers. No decision below uses any return of any style.

1. **History-start truncation (data agent's rule, adopted).** A series starts after its last unexplained gap
   > 10 business days and after its last flat run ≥ 10 business days; FRAMEWORK §3 QA (b)/(c) apply to the retained
   window. Pre-float pegs (AUD, NZD, JPY) and 1960s flat Treasury runs are truncated, not failed. Recorded per row
   in `candidates.csv` notes.
2. **QA fixes adopted as made by the data agent before any strategy return:** construction-error TE uses only
   months where the synthetic return exists on every day (removes WTI's April–May 2020 negative-price months);
   EXHB.DE is mapped to DE 2y (its actual 1.5–2.5y maturity).
3. **Equity total-return priority stands** (FRAMEWORK §3): CH and NO start 2013; no splice rule is added.
4. **Candidate list frozen** as the union of `data/cycle6/rates/candidates.csv` and
   `data/cycle6/equity/candidates.csv`, status PASS only.
5. **FI class components** (TSMOM, XSMOM, VAL, CARRY, SEAS) use one 10-year bond per country (the A5/AMP/KMVP
   unit). **BAB-FI** uses US maturity buckets available as PASS rows (2y, 5y, 10y, 30y), per FP Table VI.
6. **CARRY-CM** has two energy instruments (WTI, natgas) and fails the 4-asset rank floor: infeasible, not run.
7. **Paper-stat tier, published metrics only.** Where a paper publishes only some of mean/vol/Sharpe for a class
   (BSV publishes Sharpe only; KLN publishes means only), only the published metrics are compared; at least one is
   required; coverage ≥ 95% of the paper's months still binds. SEAS binding reference: BSV 2021 Table II
   (1981–2011) per class; KLN is secondary.
8. **Post-publication cutoffs (later candidate where uncertain):** AMP 2009-04; FP 2011-01; KLN 2015-01 (SEAS-EQ,
   SEAS-CM); BSV 2019-02 (SEAS-FI, SEAS-FX); MOP 2011-01; KMVP 2013-09.
9. **Value-EQ** uses 5-year reversal (no free MSCI BE/ME), benchmark AQR VME EQ value; declared deviation.
10. **BAB benchmarks (the "market" for betas), paper-silent defaults:** BAB-EQ: equal-weighted daily average of
    eligible PASS EQ excess returns; BAB-FI: equal-weighted daily average of the eligible US buckets. BAB-EQ
    fidelity: AQR Century `Equity indices Defensive` (AQR-class tier; construct differs, declared). BAB-FI: FP
    Table VI (paper-stat tier).
11. **Engine defaults adopted** (engine agent): m̄ = mean over window of book/control net-exposure ratio; turnover
    against drifted weights; a held position with a missing return contributes zero and is counted; one calendar
    permutation per year shared by all instruments; no book-level rebalancing cost beyond sleeve costs; 1/σ
    fallback uses diagonal variances.
