# Verification findings, 20 September 2026

The original stock result is reproducible but not proven free of selection bias. An independently implemented cash/unit ledger matches daily NAV within 9e-16 on the original later evaluation. Dollar P&L reconciles within $0.000001. A $1 charge per order in addition to the proportional fee barely changes that result. This validates the arithmetic on the supplied adjusted prices, not the historical stock universe.

The reconstructed membership diagnostic found approximately 21.1% of the original average target allocation before index admission (9.7% in the later evaluation). Restricting that original survivor pool to reconstructed historical members reduced 2019–2026 CAGR to 21.27% and excess Sharpe to 0.69. This diagnostic retained the original top-200 liquidity screen before the membership filter; it does not reconstruct the entire historical top-200 universe. Companies outside the index could have been legitimately tradable at the time, so this is a universe-sensitivity measurement, not a precise estimate or bound of survivorship bias.

The reconstruction used the current list and dated changes, reversed in time with reentries retained. It has inconsistencies, including the SATS event, and the earliest 2019 cache represents only about 76.5% of reconstructed names. Removed companies were not silently dropped from a claimed corrected full-universe test. Direct authenticated LSE queries for SIVB, ATVI, ANSS and TWTR returned zero daily rows. Consequently a complete point-in-time/delisting-corrected result is still unavailable.

Matched-entry/exit-cost momentum-fund benchmarks are in benchmark_results.json. Over 2019–2026, SPMO returned about 22.6% at 0.90 Sharpe. The original stock book shows positive six-factor alpha over that period, but its membership-filtered diagnostic has HAC t about 0.33. Attribution cannot repair a biased universe. Factor data ends July 31, 2026; regressions do not invent later observations.

Eighteen regular-session samples reconstructed from independent LSE 30-minute bars for STX, GEV and GLW gave median absolute intraday-return differences of about 9.8bps versus the cached official-session daily series, maximum 28.0bps. These checks support broad price consistency but do not verify exact auction fills or a 5bps execution cost. The strategy's additional-delay and higher-cost tests remain simulations.

Ten focused tests passed across the original return-search and new reconciliation/causality tests. The new fixed-fund designs and the equal-weight momentum/gold follow-up are documented separately. The latter is the stronger clean-input candidate from this continuation:

- [Momentum + gold results](../../momentum_gold_20260919/REPORT.md)
- [Frozen forward paper specification](../../momentum_gold_20260919/forward_paper_spec.json)

No real trades were placed. No assertion of a proven future or previously undiscovered edge is made.
