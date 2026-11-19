# Forward assumptions and source evidence

Opened free primary sources on2026-09-28/29. These forecasts have different dates, asset definitions, horizons and methods; the US1 range is a **preregistered scenario synthesis**, not a statistically estimated confidence interval or a claim of provider consensus. Frozen central assumptions were set before US1 portfolio returns. Subsequent source inspection corroborates those assumptions and does not change them.

|Provider/source opened|Horizon and relevant evidence|Use in US1|
|---|---|---|
|[Vanguard VCMM, June30,2026](https://www.vanguardmexico.com/en/home/insights/economic-market-outlook/vanguard-capital-markets-model-forecasts-2026)|10-year nominal USD geometric ranges: US equity4.2–6.2%, intermediate Treasuries3.7–4.7%, cash3–4%, inflation1.5–2.5%. Treasury universe matters; all-Treasury and long-Treasury figures are different.|Low and central reference; no extrapolation of recent equity gains.|
|[AQR2026 CMA](https://www.aqr.com/-/media/AQR/Documents/Alternative-Thinking/AQR-Alternative-Thinking---2026-Capital-Market-Assumptions.pdf?sc_lang=en)|5–10-year compound assumptions, as of2025year-end. Appendix US large equity6.3%nominal/3.9%real; US10Y Treasury4.8%nominal/2.4%real. US equity arithmetic7.5% differs from geometric; do not average without conversion.|Upper Treasury/reference equity assumption; genuine valuation/growth haircut support.|
|[JPM2026 USD matrix](https://am.jpmorgan.com/content/dam/jpm-am-aem/global/en/insights/ltcma-2026-us-matrix_usd.pdf), [framework](https://am.jpmorgan.com/us/en/asset-management/adv/insights/portfolio-insights/ltcma/)|10–15years. Compound USlarge6.70%, intermediateTreasuries4.00%, globalACworld7.00%, gold5.50%. Cash and asset-class arithmetic/volatility columns are separate.|US equity/gold high-case references. Global equity only informs RSSB descriptive forward mapping.|
|[AQR Broad Strategic Asset Allocation](https://www.aqr.com/-/media/AQR/Documents/Alternative-Thinking/AQR-Alternative-Thinking---Broad-Strategic-Asset-Allocation.pdf?sc_lang=en)|Risk-mitigation building block is trend. Exhibit4 net-fee long-run Sharpe0.24, vol10%, geometric5.4% at3.5%cash,5.9%at4%cash. This is a2024 strategic framework, not2026 fund forecast.|Context for conservative net trend center4.5%, range3–6%; center/range are research assumptions. NotAQR's multifactor0.7Sharpe.|
|[BlackRock CMA page](https://www.blackrock.com/institutions/en-us/insights/thought-leadership/capital-market-assumptions)|Opened; interactive current forecasts and horizon/methodology. Existing downloadedAugust2026workbook preserved in support archive.|Not mixed into frozen numerical scenario set after returns. A downloaded workbook alone is not proof that every header/currency was mapped correctly.|
|[Research Affiliates asset-allocation tool](https://interactive.researchaffiliates.com/asset-allocation)|Opened; redirected toSyzygy interactive site; numeric forecasts not extractable in this run.|No guessed numerical forecast. Access/extraction limitation recorded.|

Preregistered USD compound scenarios:

|Sleeve|Low|Central|High|Fees|
|---|---:|---:|---:|---|
|US equity|4.2%|5.5%|6.7%|SPY0.0945% deducted|
|IntermediateTreasury|3.7%|4.25%|4.8%|IEF0.15% deducted|
|Gold|2.0%|3.0%|5.5%|GLD0.40% deducted|
|Managedfutures funded|3.0%|4.5%|6.0%|Already net implementation; no second2%charge|
|US cash|3.0%|3.5%|4.0%|No genericbill-fund fee; cashbenchmark|

For historical covariance matrixΣ, arithmetic sleeve means are geometric+Σii/2, and portfolio geometric is w'μ minus financing, implementation costs and w'Σw/2. This approximation is not exact lognormal mathematics for strongly non-Gaussian leveraged returns. It is a fixed screening approximation, not optimized weights. P5 uses its average predetermined trailing-vol weights for the forecast; all weights are recomputed on historical and bootstrap paths.

Forward borrowing cost is USDcash+1.5%. Primary historical borrowing uses lagged actualeffectiveFedfunds+1.5%; these are distinct constructions. The geometric-equity central5.5% vs historical US1equityCAGR11.16% imposes roughly5.7percentage points/year haircut before matching fee conventions. That reduces the expected benefit of leverage substantially. The historical1962+bond bull market and unusually successful US stock history are not projected unchanged.

For CAD growth forecasts, expected CAD/USD log drift is zero, a declared neutral scenario, so nominal geometric expectation matches USD; currency still affects volatility, drawdowns and CADSharpe. Real central projections divide nominal gross growth by1.024(US) and1.02(Canada). This is not a forecast that exchange rates stay fixed along the path. Cash financing and inflation uncertainty are not fully covered by the low/high return range.

The forward bootstrap shifts primitive sleeve monthly log-return means to the central expected growth, reuses joint historical innovations, re-estimates P5weights on each path, fixes forwardUSDfinancing at5%, and removes sample FXlog drift. Forward risk is reported separately from historical raw-return bootstrap eligibility. Both retain the historical covariance/crisis-library limitation.

Real ETF model cautions: NTSX90/60 is distinct from synthetic100/50. RSSBcontains globalstocks; its stand-alone global equity scenario5.5/6.5/7.5% is declared. RSST's trend mapping uses the nettrendscenario and also subtracts full fundfee, conservatively overlapping some implementation allowance. Real funds' historical returns already contain expenses, so historical fee subtraction is not repeated. ForwardP7long-bond volatility mapping is approximate; P7never enters winnerselection.
