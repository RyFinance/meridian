# Cycle 8 — highest expected return under a risk limit, US-listed instruments

**Portfolio construction from known US-tradable risk premia, not alpha research.** For a Canadian retail investor trading US-listed instruments, which pre-declared portfolio delivers the highest expected long-run return while keeping Sharpe at least that of plain 60/40 and limiting drawdown risk at 25%, 35% or 50%? The owner chooses the tolerance. Zero validated alpha edges remain. Cycle 6 failed and Cycle 7 EM FX carry weakened; both remain spent. Research only.

**All 56 portfolio and leverage combinations were evaluated. No weights were optimized, no leverage grid was searched, and no instruments were added after the returns were observed. Every requested work item is completed or documented infeasible below. No portfolio receives a fully validated claim of drawdown safety because essential data and implementation gates remain unresolved.**

The requested `reports/cycle8_max_return/RESULTS.md` already contains a separate study of global equity and Canadian bonds, written by another process. It was preserved. This report evaluates the requested US-only menu. A new `US_ONLY_RESULTS.md` companion in the requested directory links here without changing the existing report.

## Three tolerances: the decision

The preregistered historical screen requires a 20-year probability of breaching the drawdown limit in **either USD or CAD below 10%**, and historical point Sharpe at least that of 60/40 over the same available window in **both currencies**. Qualifying portfolios are ranked by the frozen forward expected geometric return. A separate forward risk check shifts sleeve means to the forward assumptions before running the joint bootstrap. The historical and forward risk lenses give different answers.

| Tolerance | Historical-screen winner | Expected nominal return range | Historical breach probability | Forward breach probability for that winner | Winner also passing forward risk | Fully validated winner |
|---|---|---|---|---|---|---|
| 25% | None | — | — | — | None | None: certification incomplete |
| 35% | P3@1 | 4.21%–6.15%; center 5.21% | 4.90% | 31.89% | None | None: certification incomplete |
| 50% | P6a@1 | 4.41%–7.91%; center 6.21% | 2.25% | 35.96% | P3@1 | None: certification incomplete |

**25% tolerance:** No portfolio passes the joint Sharpe and risk conditions. Nothing above 1x qualifies. Risk parity has low modeled drawdown probabilities, but misses the CAD Sharpe hurdle. Cash is a reference: its USD Sharpe against identical cash is undefined, and USD cash has currency risk for a Canadian investor.

**35% tolerance:** The historical screen selects **P3 at 1x: 60% US equity and 40% intermediate Treasuries**. Expected nominal return is 4.21%–6.15%, with a 5.21% center, before personal taxes. CAD has the same expected nominal range under the declared zero expected FX log drift. Central expected real growth is approximately 2.74% in USD and 3.14% in CAD. Its historical breach probability is 4.90%, but the forward mean-shifted probability is 31.89%. **No row passes the 35% forward risk check.** P4 at 1.25x passes the historical screen with 6.91% breach probability, but its lower forward expected return does not win. P4 already borrows at its nominal 1x setting because its literal additive base holds 120% of capital.

**50% tolerance:** The historical screen selects **P6a at 1x: 100% US equity plus a 50% trend excess-return overlay**, with expected nominal return of 4.41%–7.91% and a 6.21% center. Its 2.25% historical breach estimate rises to 35.96% under forward means. It lacks 1970s trend history and an exact validated ETF replication. **The highest-return row also passing the forward risk check is P3 at 1x**, with a 5.21% center, a 4.21%–6.15% range and a 2.65% forward probability of breaching 50%. P4 at 1.25x also passes this forward risk check at 8.28%, but offers a lower expected return of 4.95% and has missing 1970s trend evidence.

No externally levered portfolio is the highest-forward-return winner at any tolerance. This does not imply that every leveraged row fails every numerical screen; the P4 exceptions are reported explicitly. These monthly bootstrap probabilities do not certify intraday solvency. The forward check retains the preregistered historical Sharpe hurdle; it does not assert a proven future Sharpe advantage.

## Worst crisis paths and real implementations

For P3 at 1x, the worst named CAD crisis is 1973–74: a cumulative loss of 25.22% and an in-window month-end drawdown of 31.09%. Full-sample daily proxy drawdown reaches 32.98% in CAD and 32.08% in USD. There are zero margin calls because this row does not borrow. The bond proxy uses a ten-year par Treasury, with different duration from IEF; the long history is therefore SPY/IEF-style, rather than an exact history of those ETFs.

The exact named implementation is **60% SPY / 40% IEF**, fully funded and rebalanced monthly. The weighted stated fund fee is approximately 0.1167% per year, before trading costs. It is feasible in TFSA and RRSP accounts, subject to broker eligibility. Direct US equity dividends generally qualify for the pension treaty withholding exemption in an RRSP; TFSA dividends generally incur unrecoverable US withholding. The historical equity-dividend-only TFSA sensitivity reduces P3's USD CAGR from 9.44% to 9.17%, with a mean withholding charge of about 24 basis points per year. That historical charge reflects higher past dividend yields and is not a fixed future fee. Qualified interest-related bond distributions may be exempt; withholding is not charged against the entire total return. Distribution classification requires issuer records. Personal income tax, withdrawal tax and investor-specific tax credits are outside this comparison.

P6a at 1x has full-sample month-end USD drawdown of 43.12% and daily proxy drawdown of 47.89%; its CAD daily proxy drawdown is 35.77%. Its worst observed named USD crisis drawdown occurs in 1987. The 1973–74 and Volcker windows are unavailable, not zero. It has zero calls under the generic funded/overlay maintenance model. A purchased approximation is **50% RSST / 50% SPY**, algebraically providing 100% equity plus 50% managed-futures exposure, with weighted stated fees of approximately 0.54225% per year. This funded ETF mix can be held in a TFSA or RRSP, but RSST's strategy differs from AQR TSMOM. The synthetic row is not an exact validated TFSA implementation. This algebraic mapping is not a newly backtested menu addition. Purchasing SPY plus 50% DBMF using a loan has different financing and strategy costs and requires a nonregistered margin account.

Among the named equity wrappers, VTI's 0.03% stated fee is lower than SPY's. DBMF's 0.85% stated fee is lower than KMLM's 0.90%, but their exposures differ. No substitute ticker was introduced into the evaluated SPY/IEF/GLD rows. IBKR had the lower financing cost of the two ordinary retail broker schedules checked; a universal cheapest-broker claim is not established. Manual FX costs 0.20 basis points of notional with a USD 2 minimum, plus spread. Minimums matter for small transactions. The run assumes 10 basis points at entry and exit and retains USD between rebalances. A 1.5% each-way conversion scenario reduces annualized 20-year growth by approximately 0.14 percentage points relative to that assumption, absent interim conversions.

NTSX provides approximately 90% equity / 60% Treasury exposure; RSSB provides 100% global stocks / 100% Treasuries; RSST provides 100% US stocks / 100% trend; GDE provides approximately 90% US stocks / 90% gold. These are distinct exposures. Their actual inception histories are evaluated at all four outer multipliers, but are too short to certify all required crises. Leveraged ETF collateral requirements increase with internal leverage. Some externally borrowed stacked or P7 rows are initially infeasible. Their generic 30% maintenance call counts are counterfactual diagnostics, not verified broker permissions; the account feasibility table flags these constraints. Fully paid P7 ETF holdings require no account margin, but daily reset does not protect against large drawdowns.

## Preregistration and reproducibility

| Artifact | SHA-256 | Timing / meaning |
|---|---|---|
| US1 PREREG.md | 959f33191f8305e844ba987c9062c2e07e3df4d5d4010a0411dbdded518122cf | 2026-09-29T06:08:27.809357+00:00 |
| Code+snapshot receipt | fe0dfe7e17605c17a0ec40ad000f3f7727aec44c41f4a90f8be4588cc8a60563 | 2026-09-29T06:11:14Z; before first US1 return |
| Numerical snapshot manifest | 0b2f26ed45985a18206423045d31d5e6597a849a0456a34dfd7eb8e61c108dd7 | Copied and verified before US1 run |

The requested preregistration ledger contains append-only US1 entries. Earlier entries were preserved. Component diagnostics and prior work were visible before this continuation; the receipt certifies the US1 menu, assumptions, code and numerical snapshot before the first US1 portfolio return, rather than pretending this was an untouched dataset.

Six engine tests passed: compounding, borrowing cost, realized liquidation losses, absorbing ruin, P4's borrowing at base exposure, and avoiding double-counted cash in overlays. Verification checks confirm 56 unique rows, finite CAGR and forward expectations, baseline Sharpe identity, probability monotonicity and unchanged frozen source/code hashes. A4 confidence intervals use `research/amendment4/ci.py:calibrated_ci`, at 95%, q=12, B=499 and seed 20260928. This studentized AR-sieve procedure is descriptive; it is not a new alpha validation test.

The primary joint stationary bootstrap uses 10,000 paths, a mean block length of 24 months and a 20-year horizon. Ten- and thirty-year horizons and a twelve-month block sensitivity are saved. Assets are sampled jointly to retain within-block dependence and crisis clustering. Block boundaries can truncate crises. Risk parity's lagged 36-month volatility weights are recalculated on each path. Liquidation retains the realized loss, charges 1% of sold assets and restores collateral. The frozen policy permits re-entry at the next monthly rebalance without outside capital, which is more permissive than permanently moving to cash after the first call. Margin is checked daily on historical proxies and monthly in the bootstrap. Intraday calls and historical house margin changes remain unverified.

## Data audit and unmet hard gates

| Requirement | Outcome and practical limit |
|---|---|
| LSE as primary source | Infeasible in this session: no LSE tool is exposed. Earlier acquisition notes also record engine unavailability. No settings or credentials were changed. |
| LSE close convention | Opened maintainer documentation reports extended-session last post-market prints rather than the 4pm auction. This is documentary evidence, not a fresh empirical audit of LSE bars. |
| Official-close repair | Free fallback adjusted ETF closes were checked for split/dividend accounting. Exact auction provenance remains unverified, so this hard gate is incomplete. |
| Required crisis history | Long equity, bond, stacked bond, P7 and cash proxies cover the 1970s onward. Trend-dependent rows lack 1970s history; actual funds start much later. |
| Long gold history | Before GLD, gold is a monthly average. It cannot certify historical month-end or daily drawdown tails. |
| Managed futures | AQR monthly TSMOM begins in 1985. No free numerical century series or daily trend history was obtained. Actual DBMF/KMLM tracking gaps are material. |
| Bonds | Yield-built ten- and twenty-year total returns were validated against actual ETFs. Duration/index mismatch is quantified. Pre-1962 supplementary history includes smoothed yields. |
| Canadian account realism | Current USD/CAD pricing, registered account limits, withholding and FX are sourced. Historical rates, maintenance and swap spreads are declared reconstructions. |
| Snapshots and completeness | Numerical inputs were frozen and hashed before the run. Supporting raw archives were copied later and their separate timing is recorded honestly. Calendar, adjustment and completeness records are saved. |

The [LSE MCP caveats](https://github.com/OlegDyukel/lse-data-mcp#data-caveats) document the extended-session issue; the [official SDK](https://github.com/londonstrategicedge/lse-data) provides no auction-close guarantee. These sources do not establish the vendor's current implementation with certainty. Completing the repair requires verified regular-session or auction prices, exchange-calendar handling including DST and early closes, split/distribution adjustments and overlap reconciliation. The fallback is useful research data; it does not prove this hard requirement has been met.

Ken French daily and monthly market returns extend to 1926 and use Mkt-RF plus RF. They are a broad US market proxy rather than SPY itself. Treasury returns are constructed from free yields, with a declared twenty-year yield gap repair and a documented 1973 vendor discontinuity repair. Fed H10 CAD/USD observations use a different observation time from ETF closes. Inflation is drawn from BLS and Statistics Canada. The main long window starts in February 1971; AQR availability limits trend rows, and risk parity requires a further three-year warm-up. Partial September ETF observations are excluded. All fourteen ETF histories have no internal missing adjusted observations or duplicates; their dates match the SPY trading calendar over their respective observed spans. Large leveraged ETF moves were retained. The five flagged UPRO events were compared with same-day SPY returns and the independently reconstructed total-return series; they have matching direction and broad magnitude, without split or dividend events. Auction/NAV provenance remains unresolved. ETF_EXTREME_MOVES.csv records this review. Detailed provenance, completeness and adjustment evidence are in the saved data audit.

## Forward assumptions and the US history haircut

The frozen USD geometric scenarios are:

| Sleeve | Low | Central | High |
|---|---|---|---|
| US equity | 4.2% | 5.5% | 6.7% |
| Intermediate Treasury | 3.7% | 4.25% | 4.8% |
| Gold | 2.0% | 3.0% | 5.5% |
| Managed futures, net | 3.0% | 4.5% | 6.0% |
| Cash | 3.0% | 3.5% | 4.0% |

These are declared scenarios, not confidence intervals or a pooled provider consensus. Equity, bond and gold fees are deducted once; net trend does not receive a second 2% charge. Arithmetic means add half the sleeve variance; portfolio geometric return subtracts half the portfolio variance, financing and turnover costs. The forward covariance is historical and fixed. Risk parity uses average predeclared weights for its expected-return approximation. Expected CAD/USD log drift is zero, while FX risk remains in the simulated paths. Central inflation assumptions are 2.4% for the US and 2.0% for Canada. Central retail borrowing costs 5%, reconstructed as cash/policy plus a 1.5% spread. Historical financing uses lagged effective policy observations rather than a verified historical broker tariff.

Primary sources opened include [Vanguard's June 2026 VCMM](https://www.vanguardmexico.com/en/home/insights/economic-market-outlook/vanguard-capital-markets-model-forecasts-2026), [AQR's 2026 capital-market assumptions](https://www.aqr.com/-/media/AQR/Documents/Alternative-Thinking/AQR-Alternative-Thinking---2026-Capital-Market-Assumptions.pdf?sc_lang=en), [J.P. Morgan's 2026 USD matrix](https://am.jpmorgan.com/content/dam/jpm-am-aem/global/en/insights/ltcma-2026-us-matrix_usd.pdf), and [AQR's strategic trend framework](https://www.aqr.com/-/media/AQR/Documents/Alternative-Thinking/AQR-Alternative-Thinking---Broad-Strategic-Asset-Allocation.pdf?sc_lang=en). The [BlackRock assumptions page](https://www.blackrock.com/institutions/en-us/insights/thought-leadership/capital-market-assumptions) and an existing download were reviewed, but no new figures were inserted after returns were observed. [Research Affiliates](https://interactive.researchaffiliates.com/asset-allocation) redirected to an interactive page without usable figures; no forecasts were guessed. Source horizons range from 5–10 to 10–15 years. Extrapolating these expectations to multi-decade drawdown probabilities is a modeling assumption.

Unlevered US equity's historical USD CAGR of 11.16% becomes 5.40% net in the central forward lens: an annual haircut of 5.77 percentage points. The 60/40 historical CAGR of 9.44% becomes 5.21%, and equity/trend's 17.55% becomes 6.21%. These compare realized returns over different available windows with declared scenarios; they do not estimate alpha decay. At retail borrowing rates, extra exposure can reduce expected compound growth despite attractive historical CAGR. Common-window comparisons and ranking changes are saved separately.

## All portfolio × leverage results

The fixed menu contains fourteen rows at four outer multipliers: P1, P2, P3, literal additive P4, inverse-volatility P5, two synthetic P6 stacks, four actual stacked ETFs, two cautionary P7 constructions and P8 cash. P4 is 60/40 plus 10% gold plus 10% trend, with 120% base exposure. P6 overlays use excess returns and count collateral cash only once. P7 holds 60% simulated SSO or UPRO and 40% simulated TMF. Its daily reset includes declared fees and swap financing. P7 is excluded from winners as a cautionary benchmark, and actual stacked funds are excluded from certification because their histories are too short.

Probabilities below are the 20-year **historical bootstrap**, with breach defined in either USD or CAD. The complete appendix reports nominal and real CAGR, volatility, A4 Sharpe intervals, month-end and daily proxy drawdown, longest underwater, worst twelve months, ulcer index, margin calls and half-Kelly. The CSV contains forward risk, horizon, block-length and financing sensitivities.

| Row | USD CAGR | CAD CAGR | Sharpe USD / CAD | Forward center | P DD>25 /35 /50 | Calls | Sharpe hurdle pass |
|---|---|---|---|---|---|---|---|
| P1@1 | 11.16% | 11.80% | 0.48 / 0.48 | 5.40% | 87.16% / 64.02% / 25.23% | 0 | no |
| P1@1.25 | 11.89% | 12.54% | 0.45 / 0.46 | 5.14% | 97.49% / 84.49% / 55.95% | 0 | no |
| P1@1.5 | 12.44% | 13.09% | 0.44 / 0.43 | 4.74% | 99.76% / 92.70% / 65.96% | 0 | no |
| P1@2 | 12.83% | 13.48% | 0.41 / 0.40 | 3.50% | 99.96% / 99.50% / 87.79% | 1 | no |
| P2@1 | 10.36% | 11.00% | 0.50 / 0.50 | 5.36% | 69.33% / 46.46% / 2.83% | 0 | no |
| P2@1.25 | 11.05% | 11.69% | 0.47 / 0.47 | 5.22% | 91.23% / 64.83% / 14.26% | 0 | no |
| P2@1.5 | 11.61% | 12.26% | 0.45 / 0.45 | 4.99% | 96.06% / 83.11% / 53.94% | 0 | no |
| P2@2 | 12.38% | 13.02% | 0.42 / 0.41 | 4.25% | 99.75% / 96.20% / 71.79% | 0 | no |
| P3@1 | 9.44% | 10.07% | 0.52 / 0.49 | 5.21% | 47.26% / 4.90% / 0.09% | 0 | yes |
| P3@1.25 | 9.99% | 10.63% | 0.48 / 0.47 | 5.12% | 75.42% / 41.63% / 1.87% | 0 | no |
| P3@1.5 | 10.48% | 11.11% | 0.45 / 0.44 | 4.98% | 89.56% / 55.57% / 8.70% | 0 | no |
| P3@2 | 11.22% | 11.86% | 0.41 / 0.41 | 4.53% | 97.79% / 88.86% / 48.54% | 0 | no |
| P4@1 | 10.93% | 11.04% | 0.77 / 0.74 | 5.08% | 31.50% / 0.97% / 0.00% | 0 | yes |
| P4@1.25 | 12.25% | 12.37% | 0.74 / 0.74 | 4.95% | 63.60% / 6.91% / 0.21% | 0 | yes |
| P4@1.5 | 13.52% | 13.63% | 0.71 / 0.72 | 4.77% | 85.83% / 38.66% / 1.55% | 0 | yes |
| P4@2 | 15.86% | 15.97% | 0.68 / 0.70 | 4.22% | 92.67% / 84.66% / 14.56% | 0 | no |
| P5@1 | 8.30% | 8.46% | 0.86 / 0.60 | 4.61% | 0.27% / 0.00% / 0.00% | 0 | no |
| P5@1.25 | 9.13% | 9.30% | 0.80 / 0.63 | 4.45% | 0.52% / 0.01% / 0.00% | 0 | no |
| P5@1.5 | 9.94% | 10.11% | 0.76 / 0.65 | 4.27% | 1.77% / 0.02% / 0.00% | 0 | no |
| P5@2 | 11.50% | 11.67% | 0.71 / 0.66 | 3.83% | 14.33% / 0.78% / 0.00% | 0 | no |
| P6a@1 | 17.55% | 17.67% | 0.89 / 0.91 | 6.21% | 77.34% / 40.35% / 2.25% | 0 | yes |
| P6a@1.25 | 20.36% | 20.48% | 0.87 / 0.89 | 6.14% | 90.69% / 74.87% / 28.00% | 0 | yes |
| P6a@1.5 | 22.99% | 23.12% | 0.85 / 0.87 | 5.92% | 97.00% / 81.23% / 40.68% | 0 | yes |
| P6a@2 | 27.35% | 27.48% | 0.82 / 0.83 | 5.03% | 99.96% / 93.67% / 76.77% | 2 | yes |
| P6b@1 | 12.03% | 12.68% | 0.51 / 0.52 | 5.77% | 90.76% / 63.58% / 20.76% | 0 | no |
| P6b@1.25 | 12.96% | 13.61% | 0.49 / 0.49 | 5.59% | 96.79% / 88.25% / 48.98% | 0 | no |
| P6b@1.5 | 13.67% | 14.33% | 0.47 / 0.47 | 5.25% | 99.33% / 95.20% / 66.29% | 0 | no |
| P6b@2 | 14.10% | 14.75% | 0.44 / 0.43 | 4.13% | 99.99% / 99.20% / 92.94% | 3 | no |
| NTSX@1 | 12.45% | 13.28% | 0.64 / 0.83 | 5.36% | 93.43% / 17.83% / 0.77% | 0 | yes |
| NTSX@1.25 | 14.11% | 14.95% | 0.62 / 0.77 | 5.02% | 96.61% / 91.43% / 7.22% | 0 | no |
| NTSX@1.5 | 15.60% | 16.45% | 0.61 / 0.72 | 4.50% | 97.66% / 95.72% / 19.46% | 0 | no |
| NTSX@2 | 18.02% | 18.89% | 0.59 / 0.67 | 2.95% | 100.00% / 97.30% / 92.19% | 0 | no |
| RSSB@1 | 17.18% | 19.34% | 0.92 / 1.28 | 7.33% | 0.00% / 0.00% / 0.00% | 0 | no |
| RSSB@1.25 | 19.77% | 21.98% | 0.90 / 1.19 | 7.62% | 0.08% / 0.00% / 0.00% | 0 | no |
| RSSB@1.5 | 22.27% | 24.53% | 0.88 / 1.12 | 7.80% | 0.62% / 0.00% / 0.00% | 0 | no |
| RSSB@2 | 26.96% | 29.30% | 0.86 / 1.03 | 7.79% | 17.80% / 0.40% / 0.00% | 0 | no |
| RSST@1 | 21.35% | 22.34% | 0.94 / 1.08 | 5.86% | 25.25% / 1.88% / 0.02% | 0 | no |
| RSST@1.25 | 24.86% | 25.89% | 0.92 / 1.04 | 5.59% | 50.99% / 12.68% / 0.16% | 0 | no |
| RSST@1.5 | 28.23% | 29.29% | 0.91 / 1.01 | 5.12% | 100.00% / 29.14% / 0.92% | 0 | no |
| RSST@2 | 34.47% | 35.57% | 0.90 / 0.97 | 3.59% | 100.00% / 100.00% / 16.03% | 0 | no |
| GDE@1 | 27.21% | 30.27% | 1.02 / 1.27 | 4.28% | 99.94% / 99.28% / 7.17% | 0 | yes |
| GDE@1.25 | 32.13% | 35.30% | 1.00 / 1.19 | 3.36% | 100.00% / 99.88% / 29.08% | 0 | yes |
| GDE@1.5 | 36.76% | 40.05% | 0.99 / 1.14 | 2.14% | 100.00% / 100.00% / 99.33% | 0 | yes |
| GDE@2 | 45.01% | 48.50% | 0.98 / 1.08 | -1.18% | 100.00% / 100.00% / 99.94% | 0 | yes |
| P7a@1 | 13.04% | 13.69% | 0.45 / 0.44 | 7.31% | 98.89% / 93.67% / 63.92% | 0 | no |
| P7a@1.25 | 13.66% | 14.31% | 0.43 / 0.43 | 7.13% | 99.86% / 98.45% / 86.06% | 0 | no |
| P7a@1.5 | 13.83% | 14.49% | 0.42 / 0.41 | 6.63% | 99.99% / 99.72% / 95.26% | 0 | no |
| P7a@2 | 12.20% | 12.84% | 0.40 / 0.39 | 4.71% | 100.00% / 99.98% / 98.92% | 3 | no |
| P7b@1 | 14.95% | 15.61% | 0.46 / 0.45 | 6.84% | 99.97% / 98.89% / 88.20% | 0 | no |
| P7b@1.25 | 15.13% | 15.80% | 0.45 / 0.44 | 5.89% | 99.99% / 99.96% / 96.80% | 0 | no |
| P7b@1.5 | 14.45% | 15.11% | 0.44 / 0.43 | 4.38% | 100.00% / 99.99% / 98.99% | 0 | no |
| P7b@2 | 7.96% | 8.58% | 0.41 / 0.40 | -0.34% | 100.00% / 100.00% / 99.97% | 7 | no |
| P8@1 | 4.38% | 4.98% | undefined / -0.03 | 3.49% | 23.70% / 2.34% / 0.05% | 0 | no |
| P8@1.25 | 3.84% | 4.44% | -7.50 / -0.11 | 3.11% | 25.81% / 3.47% / 0.08% | 0 | no |
| P8@1.5 | 3.31% | 3.90% | -7.67 / -0.18 | 2.74% | 28.74% / 4.73% / 0.20% | 0 | no |
| P8@2 | 2.25% | 2.84% | -7.70 / -0.34 | 1.98% | 35.99% / 9.68% / 0.62% | 0 | no |

P8 at 1x has undefined USD Sharpe against the same cash. Entry/exit costs create a transient numerical excess-return variance in the raw CSV; that artifact is not used as a qualifying Sharpe. Initial margin infeasibility overrides any counterfactual path result. Cash borrowing at higher outer multipliers is retained only to satisfy the fixed matrix.

## Crisis table

Cells show cumulative return / in-window month-end maximum drawdown in CAD. These are base 1x rows with different availability windows. NA means the complete crisis is unavailable. The full crisis appendix contains all 56 combinations, both currencies and all seven crisis windows.

| Row | 1973-74 oil/inflation | 1979-81 Volcker | 1987 crash | 2000-02 dot-com | 2007-09 GFC | 2020 COVID | 2022 stocks+bonds |
|---|---|---|---|---|---|---|---|
| P1@1 | -42.11% / 47.12% | 25.62% / 13.30% | -23.46% / 30.48% | -40.84% / 40.84% | -33.58% / 34.03% | -14.78% / 14.78% | -13.36% / 21.22% |
| P2@1 | -34.08% / 39.55% | 18.80% / 11.76% | -18.46% / 24.38% | -28.81% / 28.81% | -20.31% / 22.30% | -9.10% / 9.10% | -13.07% / 19.11% |
| P3@1 | -25.22% / 31.09% | 11.99% / 10.19% | -13.56% / 18.14% | -14.88% / 14.88% | -4.86% / 9.76% | -3.24% / 3.24% | -12.88% / 16.99% |
| P4@1 | NA / NA | NA / NA | -13.45% / 18.56% | -11.30% / 11.30% | -1.19% / 8.77% | -2.37% / 2.37% | -11.68% / 15.22% |
| P5@1 | NA / NA | NA / NA | NA / NA | 28.06% / 4.57% | 35.81% / 4.14% | 8.14% / 0.00% | -2.61% / 4.20% |
| P6a@1 | NA / NA | NA / NA | -24.72% / 32.47% | -26.61% / 26.61% | -23.87% / 23.87% | -9.85% / 9.85% | -0.07% / 12.48% |
| P6b@1 | -44.31% / 50.09% | 4.43% / 19.36% | -22.83% / 29.69% | -33.90% / 33.90% | -28.41% / 30.41% | -11.10% / 11.10% | -22.55% / 27.02% |
| P7a@1 | -56.91% / 63.44% | -34.04% / 39.23% | -25.58% / 32.93% | -36.83% / 36.83% | -37.17% / 40.44% | -9.55% / 9.55% | -48.31% / 49.88% |
| P7b@1 | -72.26% / 77.21% | -38.08% / 48.93% | -37.17% / 46.38% | -60.08% / 60.08% | -64.70% / 65.46% | -24.79% / 24.79% | -57.00% / 60.02% |
| P8@1 | 15.02% / 1.58% | 32.28% / 1.73% | 0.14% / 0.48% | 15.67% / 4.83% | 36.82% / 2.93% | 7.09% / 0.00% | 7.58% / 2.31% |

## Validation and uncertainty

SSO and UPRO have high correlation with their daily-reset simulations, but annual tracking errors are 3.21% and 4.96%. TMF tracking error is 8.84%; its simulated CAGR of −2.81% versus actual −5.49% is materially different. AQR net trend has correlation 0.60 and tracking error 11.34% against DBMF, and correlation 0.65 and tracking error 10.78% against KMLM. A real trend ETF's return range cannot be inferred solely from the hypothetical factor. The IEF comparison has tracking error of 1.37% per year and a simulated CAGR shortfall of approximately 0.69 percentage points, demonstrating that the ten-year par-bond model is not an exact seven-to-ten-year Treasury index.

P3's historical USD Sharpe is 0.516 with a 95% A4 interval of [0.239, 0.768]; its CAD Sharpe is 0.492 with interval [0.075, 0.896]. P6a's USD Sharpe is 0.888 [0.507, 1.267], and CAD Sharpe is 0.907 [0.409, 1.382]. The intervals are wide and the windows differ. The point hurdle is not statistical proof of superior Sharpe. P5 at 2x misses its CAD point hurdle by about 0.00008; no epsilon relaxation or weight adjustment was made to manufacture a qualifying answer.

Half-Kelly median / fifth-percentile bound is 1.58 / 0.45 for P3, 2.38 / 1.59 for P6a and 1.14 / 0.42 for unlevered US equity. These use 5,000 joint block-bootstrap samples. US and trend history and the borrowing rate strongly affect the estimates. They are approximate margin growth checks, not safe leverage limits; below 1x the cash-versus-borrowing-rate kink matters. No outer multiple was changed based on these estimates.

Costs and account sensitivities are declared rather than fitted: trading costs are 5 basis points for equity/bonds, 10 for gold/trend and 2 for overlays; USD/CAD entry and exit conversions cost 10 basis points. Trend history deducts a declared 2% implementation drag. The daily-reset simulations include fees and financing on excess exposure. The frozen SSO fee assumption differs slightly from the subsequently verified current fee and was not changed after results. Financing at policy plus 3%, maintenance at 50%, and CAD borrowing are separate sensitivities. Historical house margins and actual historical swap spreads remain infeasible to verify from the available free evidence.

## What 12% per year would require

**No fixed-menu row has a 12% central forward expected compound return under these assumptions.** Historically, US equity at 2x earned 12.83% in USD but suffered an 86.31% daily proxy drawdown, or 87.89% in CAD, and a modeled forced sale. Its historical 20-year probability of exceeding 50% drawdown is 87.79%; its forward expected return is only 3.50%. The 3x daily-reset equity/Treasury cautionary portfolio earned 14.95% historically but lost approximately 79% on daily proxy paths and has an 88.20% historical probability of breaching 50% over twenty years. Equity/trend's high historical return also does not establish a 12% planning assumption: its forward center is 6.21%, its forward 50% breach probability is 35.96%, and its 1970s history is missing. Achieving 12% would require substantially greater drawdown risk, cheaper financing or materially stronger return assumptions. This menu provides no validated combination of 12% expected return and a 25%, 35% or 50% drawdown ceiling.

## Completion and infeasibility record

| Requested work | Status |
|---|---|
| Fixed menu and preregistration | Completed: 56 rows and four multipliers; SHA-256 and UTC receipts precede US1 portfolio returns. |
| LSE audit and official-close repair | Documented infeasible/partial: no tool, documentary extended-session finding, fallback accounting checks, unresolved auction provenance. |
| 1926 equity and yield-built bonds | Completed with declared proxy and smoothing limits; supplementary long-history CSV saved. |
| Every required crisis | Evaluated where history exists. Missing 1970s trend and old gold tail evidence documented infeasible. |
| Dataset snapshots and completeness | Completed: numerical hashes, raw support provenance, calendar and adjustment records. |
| USD/CAD financing, maintenance and liquidation | Completed as declared reconstructions; historical house margins infeasible to verify and initial collateral constraints flagged. |
| Daily-reset decay, fees, swaps and actual ETF validation | Completed with quantified index/tracking mismatch; historical swap tariffs unverified. |
| TFSA/RRSP, withholding, FX, spreads and rebalancing | Completed with classification and personal-tax limitations. |
| All requested metrics, A4 intervals and half-Kelly | Completed; short-history or degenerate intervals explicitly unavailable rather than fabricated. |
| Bootstrap preserving crisis clustering | Completed: 10,000 joint paths, 24-month blocks, 10/20/30-year horizons, 12-month sensitivity; monthly margin limitation disclosed. |
| Historical and forward lenses | Completed: frozen assumptions, forward mean-shifted risk, history haircut and common-window ranking changes. |
| Three tolerance answers and implementations | Completed conditionally; no fully validated safety claim. |
| Plain 12% paragraph | Completed with modeled drawdown evidence. |
| Heavy subagents | Three agents supplied data, forward-source and account evidence; usage limits prevented further agent work, which the coordinator completed. |
| Requested report location | Existing report preserved; new US_ONLY_RESULTS.md companion links this US-only deliverable. |

## Saved artifacts

- [ALL_METRICS.md](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only/ALL_METRICS.md)
- [ALL_CRISES.md](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only/ALL_CRISES.md)
- [DATA_AUDIT.md](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only/DATA_AUDIT.md)
- [FORWARD_SOURCES.md](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only/FORWARD_SOURCES.md)
- [ACCOUNT_IMPLEMENTATION.md](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only/ACCOUNT_IMPLEMENTATION.md)
- [RESEARCH_LIMITATIONS.md](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only/RESEARCH_LIMITATIONS.md)
- [ETF_COMPLETENESS.csv](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only/ETF_COMPLETENESS.csv)
- [ETF_EXTREME_MOVES.csv](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only/ETF_EXTREME_MOVES.csv)
- [ETF_CALENDAR_CHECK.csv](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only/ETF_CALENDAR_CHECK.csv)
- [results.csv](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only/out/results.csv)
- [crises.csv](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only/out/crises.csv)
- [common_window.csv](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only/out/common_window.csv)
- [ranking_flips.csv](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only/out/ranking_flips.csv)
- [validation.csv](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only/out/validation.csv)
- [live_etfs.csv](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only/out/live_etfs.csv)
- [us1926.csv](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only/out/us1926.csv)
- [tfsa_equity_tax.csv](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only/out/tfsa_equity_tax.csv)
- [account_feasibility.csv](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only/out/account_feasibility.csv)
- [verification.json](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only/out/verification.json)

The chart displays the fixed synthetic families before the Sharpe hurdle: a point left of the dashed risk boundary can still fail the Sharpe requirement. Lines connect only the four declared leverage levels.

![Forward return and drawdown risk](/Users/rytty/CCP/quant_v7/reports/cycle8_us_only/forward_risk.png)
