from pathlib import Path
import re, json, hashlib, datetime
ROOT=Path(__file__).resolve().parents[2]
P=ROOT/'reports/cycle8_us_only'
old=(P/'RESULTS.md').read_text()
def saved_table(section):
 text=old.split('## '+section+'\n',1)[1].split('\n## ',1)[0]
 lines=text.splitlines(); start=next(i for i,l in enumerate(lines) if l.startswith('|'))
 end=start
 while end<len(lines) and lines[end].startswith('|'): end+=1
 return '\n'.join(lines[start:end]).replace('P6 a','P6a').replace('P6 b','P6b').replace('P7 a','P7a').replace('P7 b','P7b').replace('2026-09-29 T','2026-09-29T').replace('14 Z','14Z')+'\n'
answer=saved_table('Three tolerances: the decision')
results=saved_table('All portfolio × leverage results')
# Suppress the degenerate cash Sharpe rather than display a numerical artifact.
results=results.replace('| -0.19 / -0.03 |','| undefined / -0.03 |')
crisis=saved_table('Crisis table')
hashes=saved_table('Preregistration and reproducibility').replace('firstUS1','first US1')
text='''# Cycle 8 — highest expected return under a risk limit, US-listed instruments

**Portfolio construction from known US-tradable risk premia, not alpha research.** For a Canadian retail investor trading US-listed instruments, which pre-declared portfolio delivers the highest expected long-run return while keeping Sharpe at least that of plain 60/40 and limiting drawdown risk at 25%, 35% or 50%? The owner chooses the tolerance. Zero validated alpha edges remain. Cycle 6 failed and Cycle 7 EM FX carry weakened; both remain spent. Research only.

**All 56 portfolio and leverage combinations were evaluated. No weights were optimized, no leverage grid was searched, and no instruments were added after the returns were observed. Every requested work item is completed or documented infeasible below. No portfolio receives a fully validated claim of drawdown safety because essential data and implementation gates remain unresolved.**

The requested `reports/cycle8_max_return/RESULTS.md` already contains a separate study of global equity and Canadian bonds, written by another process. It was preserved. This report evaluates the requested US-only menu. A new `US_ONLY_RESULTS.md` companion in the requested directory links here without changing the existing report.

## Three tolerances: the decision

The preregistered historical screen requires a 20-year probability of breaching the drawdown limit in **either USD or CAD below 10%**, and historical point Sharpe at least that of 60/40 over the same available window in **both currencies**. Qualifying portfolios are ranked by the frozen forward expected geometric return. A separate forward risk check shifts sleeve means to the forward assumptions before running the joint bootstrap. The historical and forward risk lenses give different answers.

'''+answer+'''
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

'''+hashes+'''
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

Ken French daily and monthly market returns extend to 1926 and use Mkt-RF plus RF. They are a broad US market proxy rather than SPY itself. Treasury returns are constructed from free yields, with a declared twenty-year yield gap repair and a documented 1973 vendor discontinuity repair. Fed H10 CAD/USD observations use a different observation time from ETF closes. Inflation is drawn from BLS and Statistics Canada. The main long window starts in February 1971; AQR availability limits trend rows, and risk parity requires a further three-year warm-up. Partial September ETF observations are excluded. All fourteen ETF histories have no internal missing adjusted observations or duplicates; their dates match the SPY trading calendar over their respective observed spans. Large leveraged ETF moves were retained and flagged rather than removed. Detailed provenance, completeness and adjustment evidence are in the saved data audit.

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

'''+results+'''
P8 at 1x has undefined USD Sharpe against the same cash. Entry/exit costs create a transient numerical excess-return variance in the raw CSV; that artifact is not used as a qualifying Sharpe. Initial margin infeasibility overrides any counterfactual path result. Cash borrowing at higher outer multipliers is retained only to satisfy the fixed matrix.

## Crisis table

Cells show cumulative return / in-window month-end maximum drawdown in CAD. These are base 1x rows with different availability windows. NA means the complete crisis is unavailable. The full crisis appendix contains all 56 combinations, both currencies and all seven crisis windows.

'''+crisis+'''
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

'''
for name in ['ALL_METRICS.md','ALL_CRISES.md','DATA_AUDIT.md','FORWARD_SOURCES.md','ACCOUNT_IMPLEMENTATION.md','RESEARCH_LIMITATIONS.md','ETF_COMPLETENESS.csv','ETF_CALENDAR_CHECK.csv','out/results.csv','out/crises.csv','out/common_window.csv','out/ranking_flips.csv','out/validation.csv','out/live_etfs.csv','out/us1926.csv','out/tfsa_equity_tax.csv','out/account_feasibility.csv','out/verification.json']:
 text+=f'- [{Path(name).name}]({P/name})\n'
text+=f'\n![Forward return and drawdown risk]({P/"forward_risk.png"})\n'
(P/'RESULTS.md').write_text(text)
comp=ROOT/'reports/cycle8_max_return/US_ONLY_RESULTS.md'
if not comp.exists():
 comp.write_text(f'''# Cycle 8 — US-only fixed-menu evaluation\n\nThe complete requested US-listed portfolio evaluation is [RESULTS.md]({P/'RESULTS.md'}). It includes all 56 portfolio/leverage rows, preregistration hashes, both risk lenses, crisis tables, Canadian account feasibility, source audits and documented infeasibilities.\n\nThe existing RESULTS.md in this directory evaluates a separate global-equity/Canadian-bond framework and was preserved. Use the linked US-only report for the menu specified in the Cycle 8 request.\n\nUnder the forward mean-shifted risk check, no row clears the 25% or 35% tolerance. Unlevered 60/40 is the highest-return modeled candidate for the 50% tolerance, with expected nominal return of 4.21%–6.15% and a 5.21% center. No result is certified as drawdown-safe: official-close provenance, old gold tails, early trend history and historical house margin evidence remain incomplete.\n''')
print(json.dumps({'report_bytes':len(text.encode()),'companion':str(comp)}))
