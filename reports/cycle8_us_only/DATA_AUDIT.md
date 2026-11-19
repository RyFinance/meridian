# US1 data audit and feasibility

This report uses copied, SHA-256-verified numerical inputs, not the concurrently generated global/Canadian portfolio results. Numerical snapshots were frozen before the first US1 return; raw support copies were archived afterwards and explicitly timestamped as such. No individual-stock universe enters any US1 calculation.

## LSE first and close convention

The active tool inventory exposed **no LSE Terminal/MCP tool**. Resource discovery also exposed no LSE server. Existing acquisition notes separately report that the Terminal engine was not running during their checks. No app, credential, network, permission, or sandbox setting was changed to get around that limitation. Thus LSE primary acquisition and a new empirical LSE/official-close reconciliation are **infeasible in this session**. This is not a completed LSE audit.

The [LSE MCP maintainer's data caveats](https://github.com/OlegDyukel/lse-data-mcp#data-caveats), opened during this run, report independently measured extended-session candles covering08:00–23:00UTC and a last post-market print, not the16:00ET auction. Those hours should not be assumed to map to the same Eastern hours in both daylight and standard time. The [official SDK](https://github.com/londonstrategicedge/lse-data) does not provide an official-closing-auction guarantee. We therefore **do not use LSE daily close as official close**.

The fallback is Yahoo exchange-local daily adjusted-close history, fetched in the existing source acquisition. The partial September2026 month is excluded; last evaluated monthAugust2026 (May2026 for trend). Split and distribution adjustments were independently compared to a close-plus-distributions total-return reconstruction. That verifies accounting consistency, not official auction provenance. Full historical official-close reconciliation remains unresolved; no claim that replacing the vendor by Yahoo completed this requirement is made.

Issuer market-price returns can be closing bid/ask midpoints, while NAV returns are4pm valuations; neither is necessarily the auction print. For example [WisdomTree GDE](https://www.wisdomtree.com/us/products/capital-efficient/gde) explicitly distinguishes4pm NAV from closing-midpoint performance. A valid future close fix needs exchange calendar, DST and early-close handling, verified regular-session/auction series, then a total-return reconstruction using splits and ex-distributions. Merely taking the last minute before16:00 is not sufficient evidence of the official auction.

## Frozen inventory and completeness

- `data/cycle8_us_only/snapshot/manifest.json` records each numerical file's SHA256, row count, first/last observations, numeric-column internal missing counts and duplicate-index count. Its SHA256 is `0b2f26ed45985a18206423045d31d5e6597a849a0456a34dfd7eb8e61c108dd7`.
- `snapshot/meta/` preserves the existing source URLs, retrieval times, units and construction notes. `source_archive/manifest.json` hashes copied raw sources and source notes; support archive timing is after run start, not backdated.
- `ETF_COMPLETENESS.csv` records every used ETF's sample, missing adjusted closes, duplicate dates, dividend/split events, large daily moves, maximum calendar gap, and annualized adjusted-close versus reconstructed-total-return difference.
- No used ETF has an internal missing adjusted close or duplicate date in its supplied rows. Calendar completeness was also compared with the SPY trading-date panel over each ETF's own span (see `ETF_CALENDAR_CHECK.csv`); a vendor's absent dates cannot be excluded solely by counting NaNs.
- UPRO has five daily moves exceeding25% in absolute value; they require crisis/event review, not automatic winsorization. No such row was removed. Split ratios are already reflected in split-adjusted close and must not be applied twice.

## Required histories and limitations

|Input|Coverage and treatment|Assessment|
|---|---|---|
|US equity|Ken French Mkt-RF+RF monthly1926-07..2026-08; daily1926-07-01..2026-08-31|Broad-market total-return proxy, not identical S&P500. Includes1930s and every requested crisis. No single-stock current-symbol selection.|
|US intermediate Treasury|10Y par-bond repricing from previous coupon/yield, elapsed maturity, current yield and coupon accrual; daily DGS10 from1962 and monthly last daily observation; earlier GS10 monthly averages, pre1953 interpolated Shiller yields|All required1970s+ windows available. Not an IEF index replication; pre1962 volatility artificially smoothed. Supplementary1926 results cannot establish daily margin safety.|
|US long Treasury for TMF|20Y par bond from DGS20; DGS30 changes in DGS20 gaps, priced at20Y; documented1973-01-04 series break uses DGS10 change|Not20+year Treasury index. Duration/roll mismatch is material; no parameter calibration to ETF results.|
|Gold|World Bank monthly-average prices before GLD; actual GLD adjusted total returns after inception, excluding partial first month|**Long-history drawdown input is inadequate for certification.** Monthly average levels smooth and lag losses; GLD begins2004. Historical approximation retained, never presented as official month-end gold.|
|Managed futures|AQR TSMOM monthly1985-01..2026-05; plus US cash once, minus2%annual implementation allowance|No1970s and no daily path. Daily interpolation is explicitly synthetic. Published century paper does not supply the required obtained free numerical series; no substitute strategy added.|
|FX|Fed H10 CAD per USD daily1971+, month-end last observation|CAD valuation available1971+. H10 timing not synchronized with4pmETF close. Monthly geometric decomposition is exact; daily currency paths are approximate.|
|Cash and financing|Ken French USD RF; downloaded FEDFUNDS lagged one month plus150bp; BoC lagged policy+150bp CAD sensitivity|Historical hypothetical broker schedule, not archived actual retail rates. FEDFUNDS monthly average effective rate is not contemporaneous target.|
|Inflation|Existing BLS US CPI and Statistics Canada all-items CPI|Used for USD/CAD real CAGR, not trading signals.|
|Actual stacked ETFs|NTSX2018+,GDE2022+,RSST/RSSB2023+|No full crisis validation; GDE begins after start of2022crisis, so that complete window is unavailable.|

The input snapshots show no internal monthly holes in the actual columns admitted to a portfolio window; the runner asserts continuous availability. P5 uses36complete trailing months and starts1988. Own windows differ, so baseline Sharpe is recomputed on each row's exact period; a common1988–2026-May table is provided separately.

## Validation, not calibration

`out/validation.csv` gives exact overlaps, correlations, tracking errors and arithmetic/CAGR gaps forSPY,IEF,DBMF,KMLM,SSO,UPRO,TMF. Parameters were not fitted to these outcomes. Important results:

- The10Y Treasury proxy correlates strongly with IEF but overstates duration; net-of-proxy-fee CAGR differs by approximately−0.69percentage point/year on2002–2026 overlap. Correlation alone does not establish replication.
- SyntheticTMF loses about2.81%/yr versus actualTMF about5.49%/yr over the compared months; annual tracking error8.84%. Its long backtest is cautionary proxy evidence, not validatedTMF history.
- NetTSMOM versusDBMF correlation0.60 and tracking error11.34%/yr; versusKMLM0.65 and10.78%/yr. Different universe, volatility targeting and replication make the abstract trend allocation an uncertain implementation.
- Fee allowances are fixed historical counterfactuals. CurrentSSOnet fee0.87% differs from preregistered0.89%; TMF1.01%gross allowance differs from current0.90%net. No post-result fee tuning.

## What the risk estimates can establish

Daily equity/bond/ETF proxy paths support approximate liquidation accounting. Trend monthly interpolation, old smoothed gold, daily-close instead of intraday maintenance, and missing actual historical house margins prevent hard daily-tail certification. The joint24-month stationary bootstrap preserves within-block cross-asset dependence and multi-month clustering but random block boundaries can split a crisis. It cannot create missing1970s trend, new structural regimes, or future unknown crises. Its20-year probability is model-conditional and is not a guarantee or a posterior probability of safety.

## Flagged ETF move review

[ETF_EXTREME_MOVES.csv](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only/ETF_EXTREME_MOVES.csv) records the five UPRO adjusted-close moves above 25% in absolute value, alongside SPY and a 3x daily comparator. Four occur during March 2020 and one on April 9, 2025. All have split factor 1 and zero distributions on the observation date. Their directions and broad magnitudes agree with the SPY move; the largest residual from 3x SPY is approximately 3.55 percentage points. Adjusted returns agree with the independently reconstructed close-plus-distribution series. This review finds no isolated split/dividend accounting spike to remove, but it does not verify auction prints or distinguish ETF market-price premiums from NAV tracking. All observations were retained.
